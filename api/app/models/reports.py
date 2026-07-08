"""Daily report (V2-M6, SPRD2 §4.4, §5.6) — the school's day, written by the system.

Nobody writes a report (P5). At 19:00 org-local the system assembles the day from
what was already captured (attendance, logs, homework, sessions, checks, plan pace,
fees) and stores a `daily_reports` row: a short narrative (`content_md`) plus
structured `highlights` (risks / ambiguities / wins). 06:00 regenerates a *draft* if
late data arrived; a `final` the admin has annotated is never overwritten. 08:00 it
leads the Dashboard and an email/WhatsApp summary goes to admins.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPKMixin


class DailyReport(Base, UUIDPKMixin):
    __tablename__ = "daily_reports"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    for_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # {"risks": [...], "ambiguities": [...], "wins": [...]}
    highlights: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")

    __table_args__ = (
        UniqueConstraint("org_id", "for_date", name="uq_daily_reports_org_date"),
        CheckConstraint("status IN ('draft', 'final')", name="status_valid"),
    )
