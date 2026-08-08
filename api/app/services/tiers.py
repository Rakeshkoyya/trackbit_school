"""Package tiers — pricing, assignment and the upgrade queue (`D-106`…`D-111`).

There is no payment gateway. The whole commercial loop is: a school's admin
hits a wall and asks; the operator reads the queue, phones them, takes the
money, and sets the plan by hand. This service is all four of those steps.

Three rules run through it:

- **A plan assignment is a decision, so it is an append row** (law 3).
  `organizations.plan` is the derived cache of the newest `plan_changes` row.
  Never write `org.plan` anywhere else.
- **Amounts are snapshotted, never recomputed.** The list price moves (`D-106`)
  and the student count moves, independently. A school signed at ₹10 keeps
  paying ₹10 until someone deliberately changes it.
- **Only an admin may ask** (`D-110`). A teacher gets a refusal she can act on
  — "ask your admin" — not a form that quietly floods the operator's queue.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.features import (
    TIER_LABELS,
    TIERS,
    features_for,
    normalise_plan,
    tier_at_least,
)
from app.models import (
    UPGRADE_REQUEST_STATUSES,
    Organization,
    PlanChange,
    PlanPrice,
    Student,
    UpgradeRequest,
    UpgradeRequestNote,
    User,
)
from app.schemas.tiers import (
    AssignPlanIn,
    PlanChangeOut,
    PlanPriceOut,
    PlanQuoteOut,
    SetPriceIn,
    TierQuoteOut,
    UpgradeRequestDetailOut,
    UpgradeRequestIn,
    UpgradeRequestNoteIn,
    UpgradeRequestNoteOut,
    UpgradeRequestOut,
)

#: A request the operator has not finished with. Anything else is history.
OPEN_STATUSES = ("new", "contacted")

_CHANGE_FIELDS = (
    "id", "from_plan", "to_plan", "reason", "student_count_at_change",
    "unit_amount_snapshot", "monthly_amount_snapshot", "effective_from",
    "expires_at", "created_at",
)


class TierService:
    def __init__(self, db: Session):
        self.db = db

    # ---- helpers ------------------------------------------------------
    def _set_org_scope(self, value: str) -> None:
        """Point the RLS GUC at one org before writing into it.

        The operator's session has the scope lifted, which is right for reading
        across schools but leaves an INSERT with no org to satisfy the policy's
        WITH CHECK. Same dance as `PlatformService.create_school`.
        """
        self.db.execute(
            text("SELECT set_config('app.current_org_id', :v, true)"), {"v": value})

    def _active_students(self, org_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Student).where(
                Student.org_id == org_id, Student.status == "active")) or 0

    def _names(self, user_ids: set) -> dict:
        ids = {u for u in user_ids if u is not None}
        if not ids:
            return {}
        return dict(self.db.execute(
            select(User.id, User.name).where(User.id.in_(ids))).all())

    def _current_prices(self) -> dict[str, PlanPrice]:
        """Newest already-effective row per plan. A future-dated price is a
        scheduled change, not today's price."""
        rows = self.db.scalars(
            select(PlanPrice)
            .where(PlanPrice.effective_from <= datetime.now(UTC))
            .order_by(PlanPrice.plan, PlanPrice.effective_from.desc(),
                      PlanPrice.created_at.desc())
            .distinct(PlanPrice.plan)
        ).all()
        return {p.plan: p for p in rows}

    def _unit_paise(self, plan: str) -> int:
        row = self._current_prices().get(plan)
        return int(row.amount_paise_per_student) if row else 0

    @staticmethod
    def _validate_plan(plan: str) -> str:
        if plan not in TIERS:
            raise ValidationError(f"Unknown plan '{plan}'.", code="unknown_plan")
        return plan

    # ---- prices (platform data, operator-editable) --------------------
    def list_prices(self) -> list[PlanPriceOut]:
        current = self._current_prices()
        now = datetime.now(UTC)
        return [
            PlanPriceOut(
                plan=plan,
                amount_paise_per_student=(
                    int(current[plan].amount_paise_per_student)
                    if plan in current else 0),
                currency=current[plan].currency if plan in current else "INR",
                effective_from=(current[plan].effective_from
                                if plan in current else now),
            )
            for plan in TIERS
        ]

    def set_price(self, operator_user_id: uuid.UUID, body: SetPriceIn) -> PlanPriceOut:
        """Append a new list price. Never updates a row — an old quote has to
        stay explainable, and existing schools keep their own snapshot."""
        self._validate_plan(body.plan)
        row = PlanPrice(
            plan=body.plan,
            amount_paise_per_student=body.amount_paise_per_student,
            created_by_user_id=operator_user_id,
            note=body.note,
        )
        self.db.add(row)
        self.db.flush()
        return PlanPriceOut.model_validate(row)

    # ---- the quote a school sees --------------------------------------
    def quote(self, org: Organization) -> PlanQuoteOut:
        students = self._active_students(org.id)
        prices = self._current_prices()
        current = normalise_plan(org.plan)
        tiers = []
        for plan in TIERS:
            unit = int(prices[plan].amount_paise_per_student) if plan in prices else 0
            tiers.append(TierQuoteOut(
                plan=plan,
                label=TIER_LABELS[plan],
                unit_paise_per_student=unit,
                students=students,
                monthly_paise=unit * students,
                features=sorted(str(f) for f in features_for(plan)),
                is_current=(plan == current),
                is_upgrade=(plan != current and tier_at_least(plan, current)),
            ))
        return PlanQuoteOut(current_plan=current, students=students,
                            currency="INR", tiers=tiers)

    # ---- assignment (operator only) -----------------------------------
    def assign_plan(self, operator_user_id: uuid.UUID, org_id: uuid.UUID,
                    body: AssignPlanIn) -> PlanChangeOut:
        """Move a school to a tier, appending the decision to its history."""
        self._validate_plan(body.plan)
        org = self.db.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization")

        students = self._active_students(org_id)
        unit = self._unit_paise(body.plan)
        change = PlanChange(
            # Stamped in Python, not by the column's `now()` default: `now()` is
            # the TRANSACTION timestamp, so two appends in one transaction tie
            # and the history sorts arbitrarily. In an append-only log the order
            # is the meaning.
            created_at=datetime.now(UTC),
            org_id=org_id,
            from_plan=org.plan,
            to_plan=body.plan,
            changed_by_user_id=operator_user_id,
            reason=body.reason,
            student_count_at_change=students,
            unit_amount_snapshot=unit,
            monthly_amount_snapshot=unit * students,
            expires_at=body.expires_at,
        )
        self._set_org_scope(str(org_id))
        self.db.add(change)
        # The cache. `plan_source='manual'` is what makes the Razorpay webhook
        # keep its hands off this org (`D-106`, billing.handle_webhook).
        org.plan = body.plan
        org.plan_source = "manual"
        org.plan_expires_at = body.expires_at
        org.plan_status = "active" if body.plan != "free" else "none"
        self.db.flush()
        self._set_org_scope("")
        return self._change_out(change, operator_user_id)

    def history(self, org_id: uuid.UUID) -> list[PlanChangeOut]:
        rows = list(self.db.scalars(
            select(PlanChange).where(PlanChange.org_id == org_id)
            .order_by(PlanChange.created_at.desc())))
        names = self._names({r.changed_by_user_id for r in rows})
        return [
            PlanChangeOut(
                **{k: getattr(r, k) for k in _CHANGE_FIELDS},
                changed_by_name=names.get(r.changed_by_user_id),
            )
            for r in rows
        ]

    def _change_out(self, change: PlanChange,
                    user_id: uuid.UUID | None) -> PlanChangeOut:
        names = self._names({user_id})
        return PlanChangeOut(
            **{k: getattr(change, k) for k in _CHANGE_FIELDS},
            changed_by_name=names.get(user_id) if user_id else None,
        )

    # ---- the upgrade request (the school's side) ----------------------
    def open_request(self, org_id: uuid.UUID) -> UpgradeRequest | None:
        return self.db.scalar(
            select(UpgradeRequest)
            .where(UpgradeRequest.org_id == org_id,
                   UpgradeRequest.status.in_(OPEN_STATUSES))
            .order_by(UpgradeRequest.created_at.desc()))

    def raise_request(self, member: CurrentMember,
                      body: UpgradeRequestIn) -> UpgradeRequestOut:
        """`D-110` — admins only, and idempotent while one is open."""
        if not member.is_admin:
            raise ForbiddenError(
                "Only an admin can change your school's plan. "
                "Please contact your school admin.",
                code="admin_only")
        self._validate_plan(body.plan)
        current = normalise_plan(member.org.plan)
        if body.plan == current or not tier_at_least(body.plan, current):
            raise ValidationError(
                f"Your school is already on {TIER_LABELS[current]}.",
                code="not_an_upgrade")

        # Asking twice is not an error — it is the same ask. Returning the open
        # row keeps the operator's queue one-row-per-school and lets the UI show
        # "requested on the 3rd" instead of a failure.
        existing = self.open_request(member.org_id)
        if existing is not None:
            return self._request_out(existing, member.user.name)

        row = UpgradeRequest(
            org_id=member.org_id,
            requested_plan=body.plan,
            requested_by_user_id=member.user_id,
            feature_id=body.feature_id,
            message=body.message,
        )
        self.db.add(row)
        self.db.flush()
        return self._request_out(row, member.user.name)

    def request_summary(self, row: UpgradeRequest) -> UpgradeRequestOut:
        """One request, as the SCHOOL sees it — no operator commentary.

        The note trail is deliberately absent: `upgrade_request_notes` holds our
        working notes on a live negotiation about this very school
        (`models/tiers.py`), and nothing org-scoped may reach it.
        """
        names = self._names({row.requested_by_user_id})
        return self._request_out(row, names.get(row.requested_by_user_id))

    @staticmethod
    def _request_out(row: UpgradeRequest, by_name: str | None = None,
                     **extra) -> UpgradeRequestOut:
        return UpgradeRequestOut(
            id=row.id, org_id=row.org_id, requested_plan=row.requested_plan,
            feature_id=row.feature_id, message=row.message, status=row.status,
            created_at=row.created_at, requested_by_name=by_name, **extra)

    # ---- the operator's queue -----------------------------------------
    def list_requests(self, status: str | None = None) -> list[UpgradeRequestOut]:
        """Every school's requests, newest first, with the context the operator
        needs to make the call: who, which plan, how many students, how much."""
        stmt = select(UpgradeRequest).order_by(UpgradeRequest.created_at.desc())
        if status:
            stmt = stmt.where(UpgradeRequest.status == status)
        rows = list(self.db.scalars(stmt))
        if not rows:
            return []

        names = self._names({r.requested_by_user_id for r in rows})
        org_ids = {r.org_id for r in rows}
        orgs = {o.id: o for o in self.db.scalars(
            select(Organization).where(Organization.id.in_(org_ids)))}
        counts = dict(self.db.execute(
            select(Student.org_id, func.count(Student.id))
            .where(Student.org_id.in_(org_ids), Student.status == "active")
            .group_by(Student.org_id)).all())
        prices = self._current_prices()

        out = []
        for r in rows:
            org = orgs.get(r.org_id)
            students = counts.get(r.org_id, 0)
            price = prices.get(r.requested_plan)
            unit = int(price.amount_paise_per_student) if price else 0
            out.append(self._request_out(
                r, names.get(r.requested_by_user_id),
                org_name=org.name if org else None,
                current_plan=org.plan if org else None,
                students=students,
                monthly_paise=unit * students,
            ))
        return out

    def request_detail(self, request_id: uuid.UUID) -> UpgradeRequestDetailOut:
        row = self.db.get(UpgradeRequest, request_id)
        if row is None:
            raise NotFoundError("Upgrade request")
        notes = list(self.db.scalars(
            select(UpgradeRequestNote)
            .where(UpgradeRequestNote.upgrade_request_id == request_id)
            .order_by(UpgradeRequestNote.created_at.asc())))
        names = self._names(
            {n.author_user_id for n in notes} | {row.requested_by_user_id})
        return UpgradeRequestDetailOut(
            request=self._request_out(row, names.get(row.requested_by_user_id)),
            notes=[
                UpgradeRequestNoteOut(
                    id=n.id, note=n.note, status_from=n.status_from,
                    status_to=n.status_to, created_at=n.created_at,
                    author_name=names.get(n.author_user_id),
                )
                for n in notes
            ],
        )

    def add_note(self, operator_user_id: uuid.UUID, request_id: uuid.UUID,
                 body: UpgradeRequestNoteIn) -> UpgradeRequestDetailOut:
        """Append a remark, a status move, or both. Never edits an earlier row."""
        row = self.db.get(UpgradeRequest, request_id)
        if row is None:
            raise NotFoundError("Upgrade request")
        note_text = (body.note or "").strip() or None
        if not note_text and not body.status_to:
            raise ValidationError("Write a note or move the status.",
                                  code="empty_note")
        if body.status_to and body.status_to not in UPGRADE_REQUEST_STATUSES:
            raise ValidationError(f"Unknown status '{body.status_to}'.",
                                  code="unknown_status")

        self.db.add(UpgradeRequestNote(
            created_at=datetime.now(UTC),  # see `assign_plan` — ordering is meaning
            upgrade_request_id=row.id,
            author_user_id=operator_user_id,
            note=note_text,
            status_from=row.status if body.status_to else None,
            status_to=body.status_to,
        ))
        if body.status_to:
            row.status = body.status_to  # the derived cache
        self.db.flush()
        return self.request_detail(request_id)

    # ---- the expiry watch (a list, not a job) -------------------------
    def expiring_soon(self, days: int = 30) -> list[Organization]:
        """Schools whose hand-set plan lapses within `days`, soonest first.

        Deliberately a list the operator reads, not a background downgrade:
        `ENABLE_SCHEDULER` is off, and a plan silently dropping at 3am is how a
        school arrives on Monday with its fee screen locked and no warning.
        """
        cutoff = datetime.now(UTC) + timedelta(days=days)
        return list(self.db.scalars(
            select(Organization)
            .where(Organization.plan_expires_at.is_not(None),
                   Organization.plan_expires_at <= cutoff,
                   Organization.plan != "free")
            .order_by(Organization.plan_expires_at.asc())))
