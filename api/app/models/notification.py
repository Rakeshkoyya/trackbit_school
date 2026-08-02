"""Notification outbox + push device registry.

notifications rows are an outbox: enqueued by app code / jobs, delivered by the
2-minute sweep (Phase 2). dedupe_key guarantees at-most-once per type per
instance (e.g. 'reminder:<instance_id>').
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

NOTIF_TYPES = (
    "assigned", "passed", "reminder", "overdue", "digest", "report_card", "nudge",
    "unassigned",  # F9: a task left you (board went private / you left a board)
    # DASH3 PR-2: you are covering someone's period today. Push-only — cover is
    # decided minutes before the bell, and an email that lands after the period
    # is worse than nothing.
    "substitute",
    # V1-10 (`D-66`): a fee reminder to a guardian. Deliberately its own type —
    # it is throttled per instalment per week, respects quiet hours, stops the
    # moment the payment lands, and goes to the PRIMARY guardian only (`Q-70`),
    # none of which is true of the absence alert.
    "fee_reminder",
)


class Notification(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "notifications"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_instances.id", ondelete="CASCADE"), nullable=True
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    notif_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    # Render context for the channel adapter (subject/body parts), kept small.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'push', 'email')", name="channel_valid"),
        CheckConstraint(
            "notif_type IN ({})".format(", ".join(f"'{t}'" for t in NOTIF_TYPES)),
            name="notif_type_valid",
        ),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="status_valid"),
        Index("ix_notifications_sweep", "status", "scheduled_at"),
    )


class DeviceToken(Base, UUIDPKMixin, CreatedAtMixin):
    """Push registrations (FCM for Track FL, webpush for the PWA)."""

    __tablename__ = "device_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("platform IN ('fcm', 'webpush')", name="platform_valid"),
        Index("ix_device_tokens_user", "user_id"),
    )
