"""Classroom capture (M2, SPRD §4.4) — the daily 30-second record.

lesson_logs = what was actually taught; homework = what was set (posting it
auto-notifies guardians, the teacher's immediate payback, P3); homework_checks =
the teacher went through it, with `homework_results` naming only the students who
didn't do it (HW-1, 2026-07-29 — the counts are now derived from those rows).
Still never per-item grading (P1 fence);
lesson_observations = the OPTIONAL deep log (teacher-view redesign, 2026-07) —
named sections a teacher adds to a period ("Vocabulary" → "Reading"/"Writing")
with per-student rows only for exceptions, never the whole class (P1v2).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class LessonLog(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "lesson_logs"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Which occurrence of the period this log belongs to (V2-P6). NULL for a log
    # captured outside a period card — a quick log with no attendance taken, or a
    # row that predates the class_periods anchor.
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_periods.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True
    )
    coverage: Mapped[str] = mapped_column(Text, nullable=False, server_default="full")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Period-scoped logs dedupe per (period, topic) — which is what lets a class
        # with two Maths periods on one day record a different topic in each. Logs
        # with no period fall back to the old (class_subject, date, topic) key.
        # Both are partial so the two regimes can't collide. (NULLs compare distinct
        # in a unique index, so topic_id=NULL dedup stays app-enforced, as before.)
        Index("uq_lesson_logs_period_topic", "period_id", "topic_id", unique=True,
              postgresql_where=text("period_id IS NOT NULL")),
        Index("uq_lesson_logs_cs_date_topic", "class_subject_id", "date", "topic_id", unique=True,
              postgresql_where=text("period_id IS NULL")),
        CheckConstraint("coverage IN ('full', 'partial')", name="coverage_valid"),
    )


class HomeworkAssignment(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "homework_assignments"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL = whole-class homework; set = a per-student addition (V2-P3 §5.4/§5.5).
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set when guardian notifications were enqueued (the teacher's payback, P3).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LessonObservation(Base, UUIDPKMixin, CreatedAtMixin):
    """One line of the optional deep log for a period.

    Three shapes, one table:
      * section only (`concept` NULL, `student_id` NULL) — "we did Vocabulary";
      * concept row (`student_id` NULL) — "Vocabulary → Reading happened";
      * per-student exception (`student_id` set) — ONLY the deviations a teacher
        tapped (`rating` needs_work / excellent, optional note). The absence of a
        row means "fine", exactly like attendance (P1v2). Growth reads these as
        the topic-level signal under each chapter.

    The set for one (period-or-day, section) is replaced wholesale on save,
    mirroring attendance_exceptions — this is current-state capture, not history
    (law 3 governs "who did it" records; the log's actor is `member_id`).
    """

    __tablename__ = "lesson_observations"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Anchored to the period occurrence when there is one (V2-P6); a section
    # added off a quick log without a timetable stays day-scoped, like the log.
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_periods.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    section: Mapped[str] = mapped_column(Text, nullable=False)
    concept: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("rating IN ('excellent', 'needs_work')", name="rating_valid"),
        # A rating only means something about a particular student.
        CheckConstraint("rating IS NULL OR student_id IS NOT NULL", name="rating_needs_student"),
        Index("ix_lesson_observations_cs_date", "class_subject_id", "date"),
    )


class HomeworkCheck(Base, UUIDPKMixin, CreatedAtMixin):
    """The teacher sat down and went through this homework (HW-1).

    **The row's existence is the fact.** Its absence means "not checked yet",
    which is emphatically NOT the same as "everybody did it" — that distinction
    is the whole point of the checking-discipline analytic, and it is the same
    one `class_periods.attendance_marked_at` draws for attendance and
    `staff_attendance_days` draws for staff. Without it, a teacher who never
    checks anything reads as a teacher whose class has perfect completion.

    `done_count`/`total_count` are now **derived caches** recomputed from the
    roster minus `homework_results` on every check. They are kept because the
    dashboard's homework health chart already sums them; nothing writes them by
    hand any more.
    """

    __tablename__ = "homework_checks"

    org_id: Mapped[uuid.UUID] = _org_fk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("homework_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    done_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Who actually checked — a substitute may check a colleague's homework, and
    # "which teacher isn't checking" has to name the person, not the timetable.
    checked_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    results: Mapped[list["HomeworkResult"]] = relationship(
        back_populates="check", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # One check per assignment. Previously only a convention in the service;
        # a double-submit could silently create a second row and double-count the
        # class in the dashboard's homework totals.
        UniqueConstraint("assignment_id", name="uq_homework_checks_assignment"),
    )


class HomeworkResult(Base, UUIDPKMixin, CreatedAtMixin):
    """One student who did NOT do the homework (HW-1) — exception rows only.

    Capture-by-exception, exactly like `attendance_exceptions` and
    `check_results`: the teacher taps "everyone did it" and flags the few who
    didn't. Every student's status is still knowable — roster minus these rows is
    the done list — but the teacher never touches 40 names to record 3 facts
    (P1v2).

    Hangs off the check rather than the assignment so that clearing a check
    clears its verdicts with it: a teacher who reopens the sheet is re-checking,
    not amending a record that outlived its check.
    """

    __tablename__ = "homework_results"

    org_id: Mapped[uuid.UUID] = _org_fk()
    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("homework_checks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Denormalised from the check so per-student history is one query, not a join
    # through checks for every read (the parent portal asks for exactly this).
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("homework_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # not_done = nothing · partial = started it. Anything else is "done", which
    # has no row.
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="not_done")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    check: Mapped["HomeworkCheck"] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_homework_results_student"),
        CheckConstraint("status IN ('not_done', 'partial')", name="homework_result_status_valid"),
    )
