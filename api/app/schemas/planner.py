"""Syllabus + plan + forecast schemas (M1, SPRD §5.1)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ── syllabus ─────────────────────────────────────────────────────────────────
class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    # None = not sized yet, so not scheduled. Distinct from 1 (see SyllabusTopic).
    est_periods: int | None = None
    position: int


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    position: int
    term_id: uuid.UUID | None = None
    topics: list[TopicOut] = Field(default_factory=list)


class UnitCreate(BaseModel):
    class_subject_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    term_id: uuid.UUID | None = None


class TopicCreate(BaseModel):
    unit_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    # Defaults to unsized: recording a chapter is not the same as estimating it.
    est_periods: int | None = Field(default=None, ge=1, le=40)


class TopicEstimateIn(BaseModel):
    est_periods: int | None = Field(default=None, ge=1, le=40)


class SplitIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class SplitUnit(BaseModel):
    title: str
    topics: list[str]


class SplitOut(BaseModel):
    units: list[SplitUnit]


# ── plan + forecast ──────────────────────────────────────────────────────────
class PlanEntryOut(BaseModel):
    topic_id: uuid.UUID
    topic_title: str
    unit_title: str
    week_start: date


class PlanTermOut(BaseModel):
    """One planning window. `term_id=None` is the untermed bucket — the whole year
    for a school that doesn't use terms."""
    term_id: uuid.UUID | None
    name: str
    start_date: date
    end_date: date
    topic_count: int
    unestimated_topics: int
    approved: bool


class PlanOut(BaseModel):
    class_subject_id: uuid.UUID
    status: str  # none | draft | partial | approved
    approved_at: datetime | None = None
    total_est_periods: int
    # Chapters recorded but not yet sized. > 0 means the plan is incomplete by
    # design, not broken — the later terms haven't been planned yet.
    unestimated_topics: int = 0
    terms: list[PlanTermOut] = Field(default_factory=list)
    entries: list[PlanEntryOut]


class ForecastOut(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    class_label: str
    # rag: green | amber | red | none | unplanned
    # `unplanned` = chapters remain unsized, so no finish date can be computed.
    status: str
    total_topics: int
    baseline_finish: date | None = None
    projected_finish: date | None = None
    weeks_behind: int = 0
    unestimated_topics: int = 0


# ── generation pipeline (V2-M2, SPRD2 §5.2) ──────────────────────────────────
class ViolationOut(BaseModel):
    code: str  # capacity | coverage | ordering | teacher_load | exam_coverage | unsized
    message: str


class PlanGenerateOut(BaseModel):
    """Proposer + deterministic validators. `fits` is False when the syllabus is
    over capacity — a human decision, surfaced not squeezed."""
    fits: bool
    violations: list[ViolationOut]
    plan: PlanOut


class PlanCommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    topic_id: uuid.UUID | None = None


class PlanCommentOut(BaseModel):
    id: uuid.UUID
    class_subject_id: uuid.UUID
    topic_id: uuid.UUID | None
    author_name: str | None
    text: str
    status: str
    created_at: datetime
