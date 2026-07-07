"""Assessments & bands (M3, SPRD §4.5).

TrackBit records and tracks; it never authors or conducts tests (§8 fence). Bands
are private intervention tiers (P4) — staff-only, append-only history. Activating
an intervention spins its checklist into tasks for the class teacher (M5).
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

_SCORE = Numeric(6, 2)


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


def _actor_fk() -> Mapped[uuid.UUID | None]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SkillArea(Base, UUIDPKMixin, CreatedAtMixin):
    """Configurable diagnostic skill area (seed: Reading/Writing/Speaking/Math)."""

    __tablename__ = "skill_areas"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_skill_areas_org_id"),)


class AssessmentCycle(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "assessment_cycles"

    org_id: Mapped[uuid.UUID] = _org_fk()
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # diagnostic|unit_test|term_exam
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('diagnostic', 'unit_test', 'term_exam')", name="type_valid"),
    )


class AssessmentScore(Base, UUIDPKMixin, CreatedAtMixin):
    """A student's score in one cycle, against EITHER a subject (tests) or a skill
    area (diagnostic) — exactly one. Verified by a coordinator before it's trusted."""

    __tablename__ = "assessment_scores"

    org_id: Mapped[uuid.UUID] = _org_fk()
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="CASCADE"),
        nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    score: Mapped[float] = mapped_column(_SCORE, nullable=False)
    max_score: Mapped[float] = mapped_column(_SCORE, nullable=False, server_default="100")
    entered_by: Mapped[uuid.UUID | None] = _actor_fk()
    verified_by: Mapped[uuid.UUID | None] = _actor_fk()

    __table_args__ = (
        CheckConstraint("num_nonnulls(subject_id, skill_area_id) = 1", name="one_target"),
    )


class StudentBand(Base, UUIDPKMixin, CreatedAtMixin):
    """A/B/C tier for a student in a term — overall or per skill area. Append-only:
    a new row per change keeps the movement history (never update tier in place)."""

    __tablename__ = "student_bands"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)  # A|B|C
    # NULL scope = overall; else the skill area this band is for.
    scope_skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    set_by: Mapped[uuid.UUID | None] = _actor_fk()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("tier IN ('A', 'B', 'C')", name="tier_valid"),
    )


class Intervention(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "interventions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="B")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")

    items: Mapped[list["InterventionItem"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'achieved', 'dropped')", name="status_valid"),
    )


class InterventionItem(Base, UUIDPKMixin, CreatedAtMixin):
    """A checklist line. Activating the intervention spawns a task for the class
    teacher (M5); we link it so completion shows back in the intervention view."""

    __tablename__ = "intervention_items"

    org_id: Mapped[uuid.UUID] = _org_fk()
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    task_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_instances.id", ondelete="SET NULL"), nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="items")
