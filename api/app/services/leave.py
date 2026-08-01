"""Leave applications and approvals (SF-1).

A teacher applies with dates and a reason; the admin approves or rejects. The
school's allowance (days per year, days per month) is configured once in
Setup → Settings and defaults to the founder's figures — 8 a year, 1 a month.

**The decision history is append-only** (law 3). `leave_request_events` is the
record — applied · approved · rejected · cancelled, each with its actor and note
— and `leave_requests.status` is a derived cache of the newest event, exactly the
shape `plan_approvals`/`plans.status` and `demo_request_notes`/`demo_requests.status`
already use here. An approval is never overwritten by a later one; it is
superseded by another row.

**Over-limit applications are flagged, not blocked.** A validator that refuses a
second leave in a month is a validator that gets worked around with a phone call,
and the school loses the record entirely. So `warnings` rides along on the
request, the admin sees "2nd this month · over the 1-day limit" next to the
Approve button, and a human decides — the same "surfaced, not squeezed" rule the
planner follows when a syllabus does not fit.

Days are counted as **working days**, not raw span: the year's `working_weekdays`
minus calendar holidays. A Friday-to-Monday leave over a closed Sunday is two
days, and any other arithmetic would quietly overcharge the teacher's balance.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    LeaveRequest,
    LeaveRequestEvent,
    Membership,
    User,
)
from app.schemas.staff import (
    LeaveApplyIn,
    LeaveBalance,
    LeaveDecisionIn,
    LeaveEventOut,
    LeaveListOut,
    LeavePolicy,
    LeaveRequestOut,
)
from app.services.calendar import event_rows, expand_blocked_dates, teaching_days

# Statuses that still consume allowance. A rejected or cancelled request frees
# its days back up immediately.
LIVE_STATUSES = ("pending", "approved")


class LeaveService:
    def __init__(self, db: Session):
        self.db = db
        # Per-call memo for `balance`, so listing N pending requests costs two
        # queries per distinct APPLICANT rather than two per row. Every read here
        # is a round-trip to a remote database; an inbox of 20 requests from 4
        # teachers would otherwise be 40 of them.
        self._balance_memo: dict[uuid.UUID, LeaveBalance] = {}

    # ── policy ───────────────────────────────────────────────────────────────
    def policy(self, m: CurrentMember) -> LeavePolicy:
        return LeavePolicy(leaves_per_year=m.org.leaves_per_year,
                           leaves_per_month=m.org.leaves_per_month)

    def set_policy(self, m: CurrentMember, body: LeavePolicy) -> LeavePolicy:
        m.org.leaves_per_year = body.leaves_per_year
        m.org.leaves_per_month = body.leaves_per_month
        self.db.flush()
        return self.policy(m)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _active_year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(AcademicYear.org_id == org_id,
                                       AcademicYear.is_active.is_(True)))

    def _working_days(self, org_id: uuid.UUID, start: date, end: date) -> int:
        """Working days in the span, holidays excluded. Never below 1 — a leave
        applied for entirely over a holiday is still an application someone must
        answer, and returning 0 would make it invisible to the balance."""
        year = self._active_year(org_id)
        if year is None:
            return max(1, (end - start).days + 1)
        events = list(self.db.scalars(
            select(CalendarEvent).where(CalendarEvent.org_id == org_id,
                                        CalendarEvent.academic_year_id == year.id)))
        # `event_rows` first: the calendar engine is pure and consumes tuples, not
        # ORM rows. Without it this raises the moment a school has ANY calendar
        # event — which is every real school, and no test org.
        blocked = expand_blocked_dates(event_rows(events))
        return max(1, teaching_days(start, end, year.working_weekdays, blocked))

    def _member_names(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        return {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.org_id == org_id)).all()
        }

    def _resolve_member(self, m: CurrentMember, member_id: uuid.UUID | None) -> uuid.UUID:
        """Teachers act only on themselves; admins may read anyone."""
        if member_id is None or member_id == m.membership.id:
            return m.membership.id
        if not m.is_admin:
            raise ForbiddenError("You can only see your own leave")
        exists = self.db.scalar(
            select(Membership.id).where(Membership.id == member_id,
                                        Membership.org_id == m.org_id))
        if exists is None:
            raise NotFoundError("Member")
        return exists

    # ── balance ──────────────────────────────────────────────────────────────
    def balance(self, m: CurrentMember, member_id: uuid.UUID | None = None) -> LeaveBalance:
        mid = self._resolve_member(m, member_id)
        cached = self._balance_memo.get(mid)
        if cached is not None:
            return cached
        year = self._active_year(m.org_id)
        window = (
            (year.start_date, year.end_date) if year
            else (date(date.today().year, 1, 1), date(date.today().year, 12, 31))
        )
        rows = self.db.execute(
            select(LeaveRequest.status, func.coalesce(func.sum(LeaveRequest.days), 0))
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.member_id == mid,
                   LeaveRequest.status.in_(LIVE_STATUSES),
                   LeaveRequest.start_date >= window[0], LeaveRequest.start_date <= window[1])
            .group_by(LeaveRequest.status)
        ).all()
        by_status = {status: int(total) for status, total in rows}
        approved = by_status.get("approved", 0)
        pending = by_status.get("pending", 0)
        out = LeaveBalance(
            member_id=mid, academic_year_id=year.id if year else None,
            allowed_per_year=m.org.leaves_per_year,
            allowed_per_month=m.org.leaves_per_month,
            approved_days=approved, pending_days=pending,
            remaining=max(0, m.org.leaves_per_year - approved - pending))
        self._balance_memo[mid] = out
        return out

    def _warnings(self, m: CurrentMember, mid: uuid.UUID, start: date, end: date,
                  days: int, exclude_id: uuid.UUID | None = None) -> list[str]:
        """Policy breaches, phrased for the admin who has to decide."""
        out: list[str] = []
        bal = self.balance(m, mid)
        # `balance` already counts THIS request (it is flushed before we get here,
        # and listed requests are obviously stored) — so the test is total live
        # demand against the allowance. Comparing `remaining < days` would charge
        # the same days twice and warn on a request that exactly fits.
        committed = bal.approved_days + bal.pending_days
        if committed > bal.allowed_per_year:
            out.append(
                f"Over the yearly allowance — {committed} days committed against "
                f"{bal.allowed_per_year}")
        # Monthly cap counts days whose leave STARTS in the same calendar month.
        month_start = start.replace(day=1)
        next_month = (month_start.replace(year=month_start.year + 1, month=1)
                      if month_start.month == 12
                      else month_start.replace(month=month_start.month + 1))
        q = (
            select(func.coalesce(func.sum(LeaveRequest.days), 0))
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.member_id == mid,
                   LeaveRequest.status.in_(LIVE_STATUSES),
                   LeaveRequest.start_date >= month_start,
                   LeaveRequest.start_date < next_month)
        )
        if exclude_id is not None:
            q = q.where(LeaveRequest.id != exclude_id)
        used_this_month = int(self.db.scalar(q) or 0)
        if used_this_month + days > m.org.leaves_per_month:
            out.append(
                f"Over the monthly limit — {used_this_month + days} day(s) in "
                f"{start.strftime('%B')} against a limit of {m.org.leaves_per_month}")
        return out

    # ── apply / cancel ───────────────────────────────────────────────────────
    def apply(self, m: CurrentMember, body: LeaveApplyIn) -> LeaveRequestOut:
        if body.end_date < body.start_date:
            raise ValidationError("The end date cannot be before the start date")
        overlap = self.db.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.org_id == m.org_id, LeaveRequest.member_id == m.membership.id,
                LeaveRequest.status.in_(LIVE_STATUSES),
                LeaveRequest.start_date <= body.end_date,
                LeaveRequest.end_date >= body.start_date))
        if overlap is not None:
            raise ConflictError("You already have a leave request covering those dates")

        days = self._working_days(m.org_id, body.start_date, body.end_date)
        req = LeaveRequest(
            org_id=m.org_id, member_id=m.membership.id, start_date=body.start_date,
            end_date=body.end_date, days=days, reason=body.reason.strip(), status="pending")
        self.db.add(req)
        self.db.flush()
        self.db.add(LeaveRequestEvent(
            org_id=m.org_id, request_id=req.id, action="applied",
            actor_member_id=m.membership.id))
        self.db.flush()
        return self._out(m, req)

    def cancel(self, m: CurrentMember, request_id: uuid.UUID) -> LeaveRequestOut:
        req = self._get(m, request_id)
        if req.member_id != m.membership.id:
            raise ForbiddenError("You can only cancel your own leave request")
        if req.status != "pending":
            raise ConflictError(f"This request is already {req.status}")
        self._append(req, "cancelled", m)
        req.status = "cancelled"  # derived cache of the event just appended
        self.db.flush()
        return self._out(m, req)

    # ── admin decision ───────────────────────────────────────────────────────
    def decide(self, m: CurrentMember, request_id: uuid.UUID,
               body: LeaveDecisionIn) -> LeaveRequestOut:
        req = self._get(m, request_id)
        if req.status != "pending":
            raise ConflictError(f"This request is already {req.status}")
        self._append(req, body.action, m, body.note)
        req.status = body.action
        self.db.flush()
        return self._out(m, req)

    def _append(self, req: LeaveRequest, action: str, m: CurrentMember,
                note: str | None = None) -> None:
        """Add a history row AND invalidate the loaded collection.

        `_get` eager-loads `req.events`, so a row inserted with `request_id` set
        never lands in that already-populated list — the decision would be real
        in the database but missing from the response the admin just got back.
        Expiring is the same discipline `StaffAttendanceService.mark` uses after
        replacing an absence set.
        """
        self.db.add(LeaveRequestEvent(
            org_id=m.org_id, request_id=req.id, action=action,
            actor_member_id=m.membership.id, note=note))
        self.db.flush()
        self.db.expire(req, ["events"])

    # ── reads ────────────────────────────────────────────────────────────────
    def _get(self, m: CurrentMember, request_id: uuid.UUID) -> LeaveRequest:
        req = self.db.scalar(
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.events))
            .where(LeaveRequest.id == request_id, LeaveRequest.org_id == m.org_id))
        if req is None:
            raise NotFoundError("Leave request")
        if not m.is_admin and req.member_id != m.membership.id:
            raise ForbiddenError("You can only see your own leave")
        return req

    def _out(self, m: CurrentMember, req: LeaveRequest,
             names: dict[uuid.UUID, str] | None = None) -> LeaveRequestOut:
        names = names if names is not None else self._member_names(m.org_id)
        warnings = (
            self._warnings(m, req.member_id, req.start_date, req.end_date, req.days,
                           exclude_id=req.id)
            if req.status == "pending" else []
        )
        return LeaveRequestOut(
            id=req.id, member_id=req.member_id,
            member_name=names.get(req.member_id, "—"),
            start_date=req.start_date, end_date=req.end_date, days=req.days,
            reason=req.reason, status=req.status, created_at=req.created_at,
            warnings=warnings,
            events=[
                LeaveEventOut(action=e.action, note=e.note, created_at=e.created_at,
                              actor_name=names.get(e.actor_member_id) if e.actor_member_id else None)
                for e in sorted(req.events, key=lambda e: e.created_at)
            ])

    def list_requests(self, m: CurrentMember, status: str | None = None,
                      mine: bool = False) -> LeaveListOut:
        """Admins see the school; teachers only ever see their own rows."""
        q = (
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.events))
            .where(LeaveRequest.org_id == m.org_id)
            .order_by(LeaveRequest.created_at.desc())
        )
        if mine or not m.is_admin:
            q = q.where(LeaveRequest.member_id == m.membership.id)
        if status:
            q = q.where(LeaveRequest.status == status)
        rows = list(self.db.scalars(q))
        names = self._member_names(m.org_id)

        # Pending count is deliberately computed unfiltered, so a status filter
        # on screen can never make the "N waiting on you" badge lie.
        pending_q = select(func.count(LeaveRequest.id)).where(
            LeaveRequest.org_id == m.org_id, LeaveRequest.status == "pending")
        if mine or not m.is_admin:
            pending_q = pending_q.where(LeaveRequest.member_id == m.membership.id)
        pending = int(self.db.scalar(pending_q) or 0)

        return LeaveListOut(
            requests=[self._out(m, r, names) for r in rows],
            pending_count=pending, policy=self.policy(m))

    def pending_count(self, m: CurrentMember) -> int:
        return int(self.db.scalar(
            select(func.count(LeaveRequest.id))
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.status == "pending")) or 0)
