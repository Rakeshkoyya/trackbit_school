"""Organization (tenant + billing boundary) and Membership."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    # Subscription lifecycle (plan P4-BE-01). 'none' on Free; 'active'/'grace' on
    # Pro. Grace = a payment failed but we don't downgrade for 7 days, and we
    # never delete anything — Free simply re-limits.
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

    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro')", name="plan_valid"),
        CheckConstraint("plan_status IN ('none', 'active', 'grace')", name="plan_status_valid"),
        CheckConstraint("band_b_min > 0 AND band_b_min < band_a_min AND band_a_min <= 100",
                        name="band_thresholds_valid"),
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
