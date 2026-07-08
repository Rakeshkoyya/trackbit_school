"""Per-period attendance (V2-M4, SPRD2 §4.4, §5.4) — capture-by-exception.

The fence moved IN (founder decision, July 2026): per-period attendance, but ONLY
exception-style (P1v2). "All present" is one tap that writes a single
`attendance_marks` row for the class-period actually taken; the teacher then taps
only the deviations, which become `attendance_exceptions` rows (absent | late).

Present is DERIVED — the roster of a marked period minus its exceptions. There are
**no per-student present rows** (that would be mandatory per-student capture, which
the P1v2 budget forbids). The first marked period of the day fires guardian absence
alerts (§7); `alerted_at` makes that idempotent across re-marks.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
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


class AttendanceMark(Base, UUIDPKMixin, CreatedAtMixin):
    """One row per class-period actually taken. Its presence IS the "class marked"
    signal; absent/late students hang off it as exceptions."""

    __tablename__ = "attendance_marks"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # 1-based period index within the day (aligns with timetable_slots.period_no).
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # Which subject was taught this period (null = attendance taken without a
    # specific subject, e.g. an assembly period).
    class_subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="SET NULL"), nullable=True
    )
    marked_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when this mark's absences fired guardian alerts (§7) — idempotency guard.
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exceptions: Mapped[list["AttendanceException"]] = relationship(
        back_populates="mark", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("class_id", "date", "period_no", name="uq_attendance_marks_class_period"),
        CheckConstraint("period_no >= 1", name="period_no_valid"),
    )


class AttendanceException(Base, UUIDPKMixin):
    """A single deviation from "all present" for a marked class-period."""

    __tablename__ = "attendance_exceptions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    mark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attendance_marks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    mark: Mapped["AttendanceMark"] = relationship(back_populates="exceptions")

    __table_args__ = (
        UniqueConstraint("mark_id", "student_id", name="uq_attendance_exceptions_mark_student"),
        CheckConstraint("status IN ('absent', 'late')", name="status_valid"),
    )
