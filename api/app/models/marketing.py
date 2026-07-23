"""Marketing capture — the public "book a demo" lead.

Deliberately NOT org-scoped: a demo request arrives from the public site before
any organization exists for that school, so there is no `org_id` to isolate on
and no RLS policy (same shape as `users`). It is a platform-level table, read
only by super-admins through `/marketing/demo-requests`.

Nothing here is ever exposed to an org member: the write endpoint is public and
returns an acknowledgement only, and the read endpoint is `require_super_admin`.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

DEMO_REQUEST_STATUSES = ("new", "contacted", "scheduled", "won", "lost")


class DemoRequest(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "demo_requests"

    school_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the school told us they run — drives the ₹100/student quote, and is
    # the first thing the operator reads (below 500 students we are not a fit).
    student_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which surface the lead came from (hero form, pricing CTA, …).
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="landing")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="new")

    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'contacted', 'scheduled', 'won', 'lost')",
            name="ck_demo_requests_status_valid",
        ),
    )


class DemoRequestNote(Base, UUIDPKMixin, CreatedAtMixin):
    """One entry in a lead's history — a remark, a status move, or both.

    Append-only (law 3): a status change never rewrites an earlier row and a
    remark is never edited, so "who said what, when" survives intact.
    `demo_requests.status` is the derived cache of the newest `status_to`, the
    same shape as `plans.status` over the append-only `plan_approvals`.

    Platform-level like its parent — no org_id, no RLS policy, super-admin only.
    """

    __tablename__ = "demo_request_notes"

    demo_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("demo_requests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # SET NULL: the history outlives the operator account that wrote it.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Both null on a remark-only row; both set on a status move.
    status_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_to: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("note IS NOT NULL OR status_to IS NOT NULL",
                        name="ck_demo_request_notes_not_empty"),
    )
