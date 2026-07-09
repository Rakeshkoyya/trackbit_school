"""The class period — the anchor every per-period capture hangs off (V2-P6).

Formerly `attendance_marks`, which was already "one row per class-period actually
taken", keyed on exactly (class_id, date, period_no). V2-P6 promotes it to the
first-class thing it always was: a **period**, opened when the teacher taps
"Start attendance", closed when they finish the card.

Why this exists (SPRD2 §5.4, and the double-period bug it fixes):

  * `attendance_marks` was period-scoped, but `lesson_logs` was keyed
    (class_subject_id, date, topic_id) — no period. A class with two Maths
    periods on the same day could not record what happened in each, and My Day
    rendered both period cards off one shared class-subject row.
  * With `lesson_logs.period_id` pointing here, "what happened in 3-A Maths,
    period 4, Tuesday" is a real query.

`teacher_member_id` is the teacher who *actually took* this occurrence, which is
how a substitution is recorded — `class_subjects.teacher_member_id` remains the
year-long assignment. A period whose teacher differs from the class-subject's is
a substitution; nothing else needs to be stored.

Deliberate asymmetry (do not "fix" this): attendance and the lesson log are
period-scoped; **homework and daily_checks stay day-scoped**. Setting homework
twice for a double period would duplicate the guardian notification, and
generating a second check set would double the very work the P1v2 volume cap
exists to prevent. Both render as already-done on the second card.

Present is still DERIVED — the roster of a marked period minus its exceptions.
There are no per-student present rows (P1v2). The first *attendance-marked*
period of the day fires guardian absence alerts (§7); `alerted_at` makes that
idempotent across re-marks.
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


class ClassPeriod(Base, UUIDPKMixin, CreatedAtMixin):
    """One occurrence of one timetabled period. Created on the teacher's first
    action (open-on-action) — the timetable already says the period was
    *scheduled*, so a missing row unambiguously means "nothing was captured"."""

    __tablename__ = "class_periods"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # 1-based period index within the day (aligns with timetable_slots.period_no).
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # Which subject was taught this period (null = no specific subject, e.g. assembly).
    class_subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="SET NULL"), nullable=True
    )
    # Who actually took this occurrence. Differs from class_subjects.teacher_member_id
    # exactly when it was a substitution — no separate override table needed.
    teacher_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    # ── lifecycle ────────────────────────────────────────────────────────────
    # Set when the teacher taps "Start attendance" (open-on-action).
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when the card is closed out. Drives the 16:00 reminder job and the
    # daily report's closed/scheduled coverage number.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="held")
    not_held_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── attendance ───────────────────────────────────────────────────────────
    # NULL while the period is open but attendance not yet submitted. Its
    # not-null-ness IS the "class marked" signal (was `marked_at`).
    attendance_marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marked_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    # Set when this period's absences fired guardian alerts (§7) — idempotency guard.
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exceptions: Mapped[list["AttendanceException"]] = relationship(
        back_populates="period", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("class_id", "date", "period_no", name="uq_class_periods_class_period"),
        CheckConstraint("period_no >= 1", name="period_no_valid"),
        CheckConstraint("status IN ('held', 'not_held')", name="status_valid"),
    )

    @property
    def attendance_marked(self) -> bool:
        return self.attendance_marked_at is not None


class AttendanceException(Base, UUIDPKMixin):
    """A single deviation from "all present" for a class period."""

    __tablename__ = "attendance_exceptions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_periods.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    period: Mapped["ClassPeriod"] = relationship(back_populates="exceptions")

    __table_args__ = (
        UniqueConstraint("period_id", "student_id", name="uq_attendance_exceptions_period_student"),
        CheckConstraint("status IN ('absent', 'late')", name="status_valid"),
    )
