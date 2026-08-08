"""Package tiers — pricing, the plan history, and the upgrade queue (`D-106`).

Named `tiers`, not `plans`: this codebase already uses "plan" for the *academic*
plan (`models/planner.py`, `plans`, `plan_approvals`), and a second meaning in a
sibling module would be read wrong at a glance for years.

Four tables with three different scoping rules, and the differences are
load-bearing:

- **`plan_prices`** is *platform* data — no `org_id`, no RLS, super-admin
  writes. One curation serves every school, the same shape as the observance
  catalogue. `D-106`: "the plan number and costing might change regularly", so
  a price is a row the operator edits, never a constant we redeploy.
- **`plan_changes`** is *org-scoped* with an isolation policy (law 2). A school
  may read its own plan history; that is its billing record.
- **`upgrade_requests`** is *org-scoped* too — the school needs to see that its
  request is pending, so it does not ask twice.
- **`upgrade_request_notes`** is *platform* data on purpose. It carries the
  operator's working commentary on a live sales conversation ("called, asked
  for a discount, ringing back Tuesday"). Giving it an `org_id` would put it one
  join away from the school it is about. Same shape, and same reasoning, as
  `demo_request_notes`.

Law 3 governs both histories: a status move and a plan assignment are
*decisions*, so each is an append row. `organizations.plan` and
`upgrade_requests.status` are the derived caches of the newest row, exactly as
`plans.status` caches the newest `plan_approvals` row.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.features import TIERS
from app.models.base import CreatedAtMixin, UUIDPKMixin

UPGRADE_REQUEST_STATUSES = ("new", "contacted", "won", "lost")

# Built from `core/features.TIERS` so the tier list has exactly one home. The
# migrations spell it out literally instead — a migration is a historical
# artifact and must not change meaning when this tuple does.
_PLANS_SQL = ", ".join(f"'{t}'" for t in TIERS)
_STATUS_SQL = ", ".join(f"'{s}'" for s in UPGRADE_REQUEST_STATUSES)


class PlanPrice(Base, UUIDPKMixin, CreatedAtMixin):
    """The list price of one tier, as of a date. Append-only.

    The current list price is the newest row per plan. History is kept because
    an old quote has to stay explainable: a school signed at ₹10 keeps paying
    ₹10 (that is `PlanChange.unit_amount_snapshot`), and this table is how we
    can still say what the list said the day they signed.
    """

    __tablename__ = "plan_prices"

    plan: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    #: Paise per student per month. Paise, not rupees — money is never a float.
    amount_paise_per_student: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="INR")
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))
    # SET NULL: the price list outlives the operator account that set it.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(f"plan IN ({_PLANS_SQL})", name="ck_plan_prices_plan_valid"),
        CheckConstraint("amount_paise_per_student >= 0",
                        name="ck_plan_prices_amount_non_negative"),
    )


class PlanChange(Base, UUIDPKMixin, CreatedAtMixin):
    """One plan assignment. Append-only (law 3) — undo is a compensating row.

    The amounts are **snapshots, never recomputed**. Two things move underneath
    a school independently: its student count, and the list price (`D-106`).
    Recomputing would silently reprice every existing school the day we raise
    the list, which is the one thing a price change must not do.
    """

    __tablename__ = "plan_changes"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    #: NULL on the very first row — the org had no prior plan to move from.
    from_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_plan: Mapped[str] = mapped_column(Text, nullable=False)
    # SET NULL: the history outlives the operator account that wrote it.
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Active students the day this was agreed — the multiplier in the quote.
    student_count_at_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Paise per student, as sold. This is what the school keeps paying.
    unit_amount_snapshot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: unit × students, in paise. Stored rather than derived so the invoice does
    #: not move when a child joins mid-month.
    monthly_amount_snapshot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"))
    #: Mirrors `organizations.plan_expires_at` at the time of the change.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"to_plan IN ({_PLANS_SQL})", name="ck_plan_changes_to_plan_valid"),
        CheckConstraint(f"from_plan IS NULL OR from_plan IN ({_PLANS_SQL})",
                        name="ck_plan_changes_from_plan_valid"),
    )


class UpgradeRequest(Base, UUIDPKMixin, CreatedAtMixin):
    """A school asking to be moved up a tier. There is no payment gateway: the
    operator reads this, phones the school, takes the money, sets the plan.

    `D-110`: only an admin may create one. A teacher who hits a wall is told to
    contact her admin — one locked screen must not generate forty requests from
    forty teachers for the operator to dedupe by hand.
    """

    __tablename__ = "upgrade_requests"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    requested_plan: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    #: Which wall they hit (a `core/features.Feature` id), or NULL if they came
    #: from the plan screen rather than a locked surface. This is the product
    #: signal the whole queue is worth building for: it says which paywall
    #: actually converts, per school, without anyone being asked.
    feature_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Derived cache of the newest note's `status_to` (law 3).
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="new")

    __table_args__ = (
        CheckConstraint(f"requested_plan IN ({_PLANS_SQL})",
                        name="ck_upgrade_requests_plan_valid"),
        CheckConstraint(f"status IN ({_STATUS_SQL})",
                        name="ck_upgrade_requests_status_valid"),
    )


class UpgradeRequestNote(Base, UUIDPKMixin, CreatedAtMixin):
    """One entry in a request's history — a remark, a status move, or both.

    **Platform-level on purpose: no `org_id`, no RLS, super-admin only.** These
    are the operator's notes on a live negotiation, and the school they are
    about must never be able to read them. Never expose this table through any
    org-scoped endpoint.
    """

    __tablename__ = "upgrade_request_notes"

    upgrade_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upgrade_requests.id", ondelete="CASCADE"),
        nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Both NULL on a remark-only row; both set on a status move.
    status_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_to: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("note IS NOT NULL OR status_to IS NOT NULL",
                        name="ck_upgrade_request_notes_not_empty"),
    )
