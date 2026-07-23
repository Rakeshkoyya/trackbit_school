"""Lucy — the agentic chat layer (founder decision 2026-07-12, supersedes the
SPRD2 §11 "no chat UI" fence).

Four tables, all org-scoped + RLS, all member-PRIVATE in the service layer: a
teacher's conversation contains their students' data, so even admins do not
read other members' chats.

- `lucy_conversations` / `lucy_messages` — plain chat history. Messages store
  the visible text; the tool trace goes in `meta` for debugging, never replayed
  to the model.
- `lucy_widgets` — the rich answer surface. `payload` holds the materialized
  widget (data + config), always shaped server-side from a real tool result —
  the model chooses the representation, it never types the numbers.
  `source_tool`/`source_params` let a pinned widget refresh itself later.
- `lucy_pending_actions` — write-tool proposals (law 3: append-only). The agent
  proposing a write creates a row; the human confirming it is the confirm
  surface the AI doctrine requires. Rows never mutate params and are never
  deleted — resolution is a status transition + result/error columns.
"""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class LucyConversation(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "lucy_conversations"

    org_id: Mapped[uuid.UUID] = _org_fk()
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["LucyMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="LucyMessage.created_at")

    __table_args__ = (
        Index("ix_lucy_conversations_member_updated",
              "org_id", "membership_id", "updated_at"),
    )


class LucyMessage(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "lucy_messages"

    org_id: Mapped[uuid.UUID] = _org_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Debug trace: which tools ran with which params. Never replayed to the model.
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped[LucyConversation] = relationship(back_populates="messages")
    widgets: Mapped[list["LucyWidget"]] = relationship(
        back_populates="message", cascade="all, delete-orphan",
        order_by="LucyWidget.created_at")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role_valid"),
    )


class LucyWidget(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "lucy_widgets"

    org_id: Mapped[uuid.UUID] = _org_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    spec_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # {"data": <materialized widget data>, "config": <presentational config>}
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Where the data came from — lets a pin re-execute the same query later.
    source_tool: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped[LucyMessage] = relationship(back_populates="widgets")

    __table_args__ = (
        Index("ix_lucy_widgets_pinned", "org_id", "pinned",
              postgresql_where=text("pinned")),
    )


class LucyView(Base, UUIDPKMixin, CreatedAtMixin):
    """A composed answer (GA §5): titled sections of widgets + narrative, saved
    as one reopenable artifact. Self-contained — it owns COPIES of its widget
    envelopes (snapshot + source bindings), so it survives its conversation's
    deletion and can refresh itself with the viewer's live role.

    `signature` is the request fingerprint (sorted source tools) recorded for
    the GA-3 frequency judgment — written from day one so the data accrues."""

    __tablename__ = "lucy_views"

    org_id: Mapped[uuid.UUID] = _org_fk()
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"sections": [{"heading", "narrative"?, "widget_ids": [...]}]}
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # The referenced widget envelopes, copied verbatim (data+config+source).
    widgets: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    signature: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_lucy_views_member_created",
              "org_id", "membership_id", "created_at"),
    )


class LucyPendingAction(Base, UUIDPKMixin, CreatedAtMixin):
    """A write-tool proposal awaiting human confirmation (append-only, law 3)."""

    __tablename__ = "lucy_pending_actions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lucy_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Human-readable one-liner the agent wrote for the confirm card.
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="proposed")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'executed', 'failed', 'cancelled', 'expired')",
            name="status_valid"),
    )
