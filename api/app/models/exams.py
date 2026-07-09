"""Exam portions (V2-P7) — which syllabus an exam actually examines.

The planner's `validate_coverage` only asked whether topics fit before the YEAR
ends. Nobody cares about year end. What an admin needs to know in June is whether
the Term-1 portion will be finished before the Term-1 exam starts.

An exam is a `calendar_events` row of type `exam_block`. A portion says: for this
class-subject, that exam covers the syllabus up to and including `upto_topic_id`.
Everything before that topic in syllabus order is in the portion — so one row per
(exam, class-subject) is enough, and re-ordering the syllabus re-scopes the
portion for free.
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
    upto_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("exam_event_id", "class_subject_id", name="uq_exam_portions_exam_cs"),
    )
