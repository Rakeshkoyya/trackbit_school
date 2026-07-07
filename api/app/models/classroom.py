"""Classroom capture (M2, SPRD §4.4) — the daily 30-second record.

lesson_logs = what was actually taught; homework = what was set (posting it
auto-notifies guardians, the teacher's immediate payback, P3); homework_checks =
next-day completion as a count, never per-item grading (P1 fence).
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
from sqlalchemy.orm import Mapped, mapped_column

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
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True
    )
    coverage: Mapped[str] = mapped_column(Text, nullable=False, server_default="full")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("class_subject_id", "date", "topic_id", name="uq_lesson_logs_class_subject_id"),
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
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set when guardian notifications were enqueued (the teacher's payback, P3).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HomeworkCheck(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "homework_checks"

    org_id: Mapped[uuid.UUID] = _org_fk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("homework_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    done_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
