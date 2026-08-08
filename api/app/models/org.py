"""Organization (tenant + billing boundary) and Membership."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class Organization(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="Asia/Kolkata")
    # V1-2 (D-13/S-57): random 6–8 char code — how a parent picks their school at
    # login. Unique, unguessable, never derived from the name. Generated at
    # platform create; backfilled for older orgs by the migration.
    school_code: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    # V1-2 (§6 ①): collected at school creation. `state` + `board` (CBSE / state
    # board) are what scope the V1-7 observance catalogue to a school — a school
    # is never asked to declare a region or a religion (D-61).
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # V1-3 (S-25): the number behind the parent's "tell the school why" tel: link.
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    board: Mapped[str | None] = mapped_column(Text, nullable=True)
    # V1-2 (D-01): how often attendance is taken. Drives what teachers are asked
    # for, what the capture heatmap expects, and what "absent today" means (V1-3).
    attendance_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="every_period")
    # V1-2: thresholds the later packets consume — minimum attendance % (V1-3's
    # drifting list) and the homework nothing-checked-for-N-days admin signal
    # (D-85, V1-5). Settings live here so the consumers never hardcode them.
    min_attendance_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="75")
    homework_gap_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    # V1-2 (D-19/S-69): org work-category config — [{key, label, active}].
    # NULL = the core/work_types.py defaults. Keys are stable, labels mutable,
    # retired entries keep rendering on historical rows, never deleted.
    work_categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # V1-2 (§6 ⑤): set when the operator marks the school handed over.
    handed_over_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    # `D-103`: who may issue an agent connector (an MCP / Lucy machine
    # credential). `off` for a brand-new org — a school still being set up has
    # nothing to connect to yet — then `admins` once it is live. `all_staff`
    # lets a teacher issue her own, always scoped to her own authority.
    agent_access: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="off")
    # One of `core/features.TIERS` — free | pro | max | ultra (`D-106`). The
    # derived cache of the newest `plan_changes` row (law 3): read it freely,
    # but write it only through the service that appends the history.
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    # `D-106`: how this org's plan got set. `manual` = the operator assigned it
    # from the platform screen, which is the only path today. The Razorpay
    # webhook REFUSES to touch a `manual` org — otherwise one replayed
    # subscription event would quietly downgrade a school we just put on ultra.
    plan_source: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    # When a hand-set plan lapses. NULL = no end date. Nothing downgrades on
    # this automatically (`ENABLE_SCHEDULER` is off); the operator's "expiring
    # soon" list reads it.
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    # Subscription lifecycle (plan P4-BE-01). 'none' on Free; 'active'/'grace' on
    # a paid tier. Grace = a payment failed but we don't downgrade for 7 days,
    # and we never delete anything — a downgrade only re-locks screens.
    plan_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    plan_renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    razorpay_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Org-local hour for the admin report card (F7); configurable in settings.
    report_card_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="18")
    # Band categorization thresholds (SC-5): pct >= band_a_min → A,
    # >= band_b_min → B, else C. Admin-configurable on the Bands screen.
    band_a_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="75")
    band_b_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    # Parent portal (phone-OTP login for guardians). Per-school switch so rollout
    # can go school-by-school; OTP requests are refused while it's off.
    parent_portal_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # Leave policy (SF-1). Defaults are the founder's starting figures; every
    # school tunes them in Setup → Settings. `leaves_per_month` is the monthly
    # cap in DAYS — an application over either limit is still submittable and
    # arrives at the admin flagged, never silently blocked (a human decides
    # whether an emergency is worth the allowance).
    leaves_per_year: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    leaves_per_month: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # V1-8 (`D-54`/`S-138`, A-4): keep the model-read-vs-human-locked diff on
    # locked exam captures, for training our own marks reader later. **Default
    # off, and asked for** — this is the first data in the product whose purpose
    # is not running the school that entered it: it is children's handwriting
    # with their names on it, and it is the school's. There is no export path in
    # v1; de-identification has to exist before the first export, not before the
    # first row (`Q-61`).
    training_data_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"))

    @property
    def features(self) -> list[str]:
        """Every feature this plan includes (`core/features.py`), computed.

        A property rather than a column: the tier map changes when we ship
        something, and a stored copy would go stale silently on every school at
        once. Reading it here means every `OrgOut` — the session, the org
        switcher, `/auth/me` — carries the same list without anyone remembering
        to populate it.
        """
        from app.core.features import features_for  # noqa: PLC0415 - cycle-safe

        return sorted(str(f) for f in features_for(self.plan))

    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro', 'max', 'ultra')", name="plan_valid"),
        CheckConstraint("plan_source IN ('manual', 'billing')", name="plan_source_valid"),
        CheckConstraint("plan_status IN ('none', 'active', 'grace')", name="plan_status_valid"),
        CheckConstraint("band_b_min > 0 AND band_b_min < band_a_min AND band_a_min <= 100",
                        name="band_thresholds_valid"),
        CheckConstraint("leaves_per_year >= 0 AND leaves_per_month >= 0",
                        name="leave_policy_valid"),
        CheckConstraint(
            "attendance_mode IN ('every_period', 'first_period', 'twice_daily')",
            name="attendance_mode_valid"),
        CheckConstraint("min_attendance_pct >= 0 AND min_attendance_pct <= 100",
                        name="min_attendance_pct_valid"),
        CheckConstraint("homework_gap_days >= 1", name="homework_gap_days_valid"),
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name!r})>"


class Membership(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "memberships"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    # V1-2: staff date of birth — feeds the V1-7 birthday feed. Optional always.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Throttled heartbeat for the Members screen "Last active" column (plan G2).
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-member channel/digest preferences; consumed from Phase 2 on (plan B6/O4).
    notification_prefs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Bumped on removal/role change to revoke outstanding sessions (plan G11).
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    user: Mapped["User"] = relationship("User")
    org: Mapped["Organization"] = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id"),
        # SPRD v2 §2: two roles — admin (runs the school) · teacher (all staff).
        CheckConstraint(
            "org_role IN ('admin', 'teacher')", name="org_role_valid"
        ),
        CheckConstraint("status IN ('active', 'removed')", name="status_valid"),
        Index("ix_memberships_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Membership(org={self.org_id}, user={self.user_id}, role={self.org_role})>"


from app.models.user import User  # noqa: E402 — avoid circular import
