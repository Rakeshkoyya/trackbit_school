"""Syllabus + academic plan (M1, SPRD §4.3).

The approved set of plan_entries is the **baseline** (P2). Re-forecast is computed
from baseline + effective periods — never stored as mutated plan rows.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class SyllabusUnit(Base, UUIDPKMixin, CreatedAtMixin):
    """A chapter within a class-subject's syllabus."""

    __tablename__ = "syllabus_units"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(Text, nullable=False)

    topics: Mapped[list["SyllabusTopic"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", order_by="SyllabusTopic.position",
    )


class SyllabusTopic(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "syllabus_topics"

    org_id: Mapped[uuid.UUID] = _org_fk()
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_units.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    est_periods: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    unit: Mapped["SyllabusUnit"] = relationship(back_populates="topics")


class Plan(Base, UUIDPKMixin, CreatedAtMixin):
    """One plan per class-subject. Approving it locks the baseline (P2)."""

    __tablename__ = "plans"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("class_subject_id", name="uq_plans_class_subject_id"),
    )


class PlanEntry(Base, UUIDPKMixin, CreatedAtMixin):
    """A topic scheduled into a week (Monday date). The approved set is the baseline."""

    __tablename__ = "plan_entries"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=False,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_subject_id", "topic_id", name="uq_plan_entries_class_subject_id"),
    )
