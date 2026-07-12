"""Assessments & bands (M3, SPRD §4.5).

TrackBit records and tracks; it never authors or conducts tests (§8 fence). Bands
are private intervention tiers (P4) — staff-only, append-only history. Activating
an intervention spins its checklist into tasks for the class teacher (M5).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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


CYCLE_TYPES = ("diagnostic", "unit_test", "term_exam", "daily_test",
               "chapter_test", "class_test", "slip_test", "objective", "band_test")


class AssessmentCycle(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "assessment_cycles"

    org_id: Mapped[uuid.UUID] = _org_fk()
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # one of CYCLE_TYPES
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # SC-1: a daily test is class × subject × date; NULL on both = org-wide cycle
    # (diagnostics, term exams) exactly as before.
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    # SC-5: the paper's own metadata — what was tested and out of how much.
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_marks: Mapped[float | None] = mapped_column(_SCORE, nullable=True)
    # A few-students test: only these students sat it. NULL = the whole class.
    student_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ({})".format(", ".join(f"'{t}'" for t in CYCLE_TYPES)),
            name="type_valid"),
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


class ScoreCapture(Base, UUIDPKMixin, CreatedAtMixin):
    """A batch of photos of evaluated papers for one (cycle × class × subject-or-skill).

    A draft container: the AI transcription + deterministic roster match live in
    `parsed_rows`; `assessment_scores` are written ONLY when a human confirms the
    review grid (§8 — every AI output lands in a human-confirm surface). The photo
    pages are kept forever as evidence (P5)."""

    __tablename__ = "score_captures"

    org_id: Mapped[uuid.UUID] = _org_fk()
    # NULL = a draft exam capture: papers dropped first, the cycle is created
    # when the human saves the reviewed exam (SC-5).
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="CASCADE"),
        nullable=True, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="uploaded")
    # [{name_text, roll_text, score, max_score, student_id, confidence, candidates}]
    parsed_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # AI-read exam header {title, subject_text, subject_id, total_marks, topic, date}
    # — proposals only, the human-confirm form is what persists (§8).
    parsed_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Few-students capture: the picked subset. NULL = the whole class roster.
    student_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # ai_off|unreadable_page
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)
    confirmed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pages: Mapped[list["ScoreCapturePage"]] = relationship(
        back_populates="capture", cascade="all, delete-orphan",
        order_by="ScoreCapturePage.page_no")

    __table_args__ = (
        # At most one — a draft capture's subject is unknown until the parse.
        CheckConstraint("num_nonnulls(subject_id, skill_area_id) <= 1", name="capture_one_target"),
        CheckConstraint("status IN ('uploaded', 'parsed', 'confirmed', 'discarded')",
                        name="status_valid"),
    )


class ScoreCapturePage(Base, UUIDPKMixin, CreatedAtMixin):
    """One photographed page of a capture — an R2 object key (URLs minted per read)."""

    __tablename__ = "score_capture_pages"

    org_id: Mapped[uuid.UUID] = _org_fk()
    capture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("score_captures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    capture: Mapped["ScoreCapture"] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("capture_id", "page_no", name="uq_score_capture_pages_capture_id"),
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
