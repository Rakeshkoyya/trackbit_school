"""Daily checks — the recommendations engine's output (V2-M5, SPRD2 §4.4, §5.5).

Nightly (or lazily, on first My Day load) the system turns each class-subject's
planned topic × band distribution into a few concrete `daily_checks` — "5 practice
sums reviewed" for all, "reads the worked example aloud" for C-band, one line per
intervention student. The teacher confirms "class did it ✓" (sets confirmed_at) and
taps only the deviations, which become `check_results` (P1v2 exception capture).

Volume is capped in the generator (≤2 class-wide + ≤1 per intervention student) so
the period card never becomes a chore.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class DailyCheck(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "daily_checks"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 'ai' when a model drafted it, 'teacher' when hand-added on the card.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai")
    # Who the check is for: 'all' (whole class) or a band tier ('A'|'B'|'C').
    band_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="all")
    # Set when the check targets ONE student (an intervention line); null = group.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=True
    )
    # "Class did it ✓" — the confirmation IS the norm; results hold only exceptions.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    results: Mapped[list["CheckResult"]] = relationship(
        back_populates="check", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("source IN ('ai', 'teacher')", name="source_valid"),
        CheckConstraint("band_scope IN ('all', 'A', 'B', 'C')", name="band_scope_valid"),
        Index("ix_daily_checks_cs_date", "class_subject_id", "date"),
    )


class CheckResult(Base, UUIDPKMixin):
    """A single deviation from "class did it" — exception rows only (P1v2)."""

    __tablename__ = "check_results"

    org_id: Mapped[uuid.UUID] = _org_fk()
    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_checks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)  # not_done | note
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    check: Mapped["DailyCheck"] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("check_id", "student_id", name="uq_check_results_check_student"),
        CheckConstraint("status IN ('not_done', 'note')", name="status_valid"),
    )
