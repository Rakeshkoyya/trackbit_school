"""Marketing capture — the public "book a demo" lead.

Deliberately NOT org-scoped: a demo request arrives from the public site before
any organization exists for that school, so there is no `org_id` to isolate on
and no RLS policy (same shape as `users`). It is a platform-level table, read
only by super-admins through `/marketing/demo-requests`.

Nothing here is ever exposed to an org member: the write endpoint is public and
returns an acknowledgement only, and the read endpoint is `require_super_admin`.
"""

from sqlalchemy import CheckConstraint, Integer, Text
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
