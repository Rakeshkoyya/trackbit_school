"""Exam portions (V2-P7) — which syllabus an exam actually examines.

The planner's `validate_coverage` only asked whether topics fit before the YEAR
ends. Nobody cares about year end. What an admin needs to know in June is whether
the Term-1 portion will be finished before the Term-1 exam starts.

An exam is a `calendar_events` row of type `exam_block`. A portion says: for this
class-subject, these chapters are examined.

**Two ways to say it, one shape at read time.**

  * `upto_topic_id` — the original prefix: "everything up to and including this
    topic, in syllabus order". Never a stored list, so re-ordering the syllabus
    re-scopes the portion for free.
  * `exam_portion_units` — an explicit SET of chapters (SY-1). The prefix cannot
    express what schools actually do: Term 1 examines chapters 1, 2, 3 and 5,
    with chapter 4 held over to Term 2. A skipped chapter is not an edge case;
    it is how a teacher who ran out of days in November tells the truth about
    what she will examine.

The prefix is kept rather than migrated away, so every portion recorded before
SY-1 keeps its exact meaning and its exact arithmetic. When explicit chapters
exist they define the portion and the prefix is ignored.
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class ExamPortion(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "exam_portions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    exam_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The last topic examined. The portion is every topic up to and including it,
    # in syllabus order — never a stored list, so re-ordering can't desync it.
    # NULLABLE since SY-1: a portion given as an explicit chapter set has no
    # prefix, and inventing one ("the last chapter you picked") would silently
    # sweep in the chapter the teacher deliberately skipped.
    upto_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=True
    )

    units: Mapped[list["ExamPortionUnit"]] = relationship(
        back_populates="portion", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("exam_event_id", "class_subject_id", name="uq_exam_portions_exam_cs"),
    )


class ExamPortionUnit(Base, UUIDPKMixin, CreatedAtMixin):
    """One chapter inside an exam's portion (SY-1).

    Chapters, not topics: the founder's unit of decision is *"1, 2, 3 and 5"*,
    and a chapter contributes all of its topics. Storing topics would let a
    portion drift out of step with a chapter that gained a topic after it was
    mapped — the new topic would silently fall outside the exam.
    """

    __tablename__ = "exam_portion_units"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_portions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_units.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    portion: Mapped["ExamPortion"] = relationship(back_populates="units")

    __table_args__ = (
        UniqueConstraint("portion_id", "unit_id", name="uq_exam_portion_units"),
    )
