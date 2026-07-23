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
    # The term ended before the school adopted TrackBit (tracking_start_date):
    # "before our time" — never planned, never warned about.
    pre_tracking: bool = False


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
    # rag: green | amber | red | none | unplanned | unallocated
    # `unplanned` = NOTHING is scheduled yet (no plan entries at all).
    # `unallocated` = the class-subject has 0 periods/week, so no pace exists.
    # A partially planned subject gets a real RAG over its planned portion, with
    # `unestimated_topics` counting the chapters still to be sized — info, not a
    # warning (the school plans term by term; that's normal, not broken).
    # Chapters filed under terms that ended before tracking_start_date are
    # excluded from every number here — they are before our time.
    status: str
    total_topics: int
    baseline_finish: date | None = None
    projected_finish: date | None = None
    weeks_behind: int = 0
    unestimated_topics: int = 0
    planned_topics: int = 0
    # The term running today has chapters but not one of them is scheduled —
    # the one "no plan" state worth an alert.
    current_term_unplanned: bool = False


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


# ── exam-gap fit (V2-P12): does each portion fit the days before its exam? ────
class ExamFitSubject(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    # short (won't fit) | tight (manageable) | fits (perfect) | surplus (spare days)
    # | no_portion (nothing mapped) | unallocated (0 periods/week)
    verdict: str
    required_periods: int  # Σ est_periods of the topics this exam adds
    capacity_periods: float  # effective periods in the gap before the exam
    unsized_topics: int  # topics in the segment with no estimate (not counted above)


class ExamFitExam(BaseModel):
    exam_event_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    days_to_exam: int  # calendar days from today (negative = past)
    gap_start: date
    gap_end: date
    teaching_days_in_gap: int
    subjects: list[ExamFitSubject]


class ExamFitOut(BaseModel):
    class_id: uuid.UUID
    exams: list[ExamFitExam]


# ── computed week/day schedule (V2-P12) — nothing stored, ever (P2) ──────────
class DaySlotOut(BaseModel):
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None = None
    topic_id: uuid.UUID | None = None
    topic_title: str | None = None
    unit_title: str | None = None
    # actual (a lesson log exists — what really happened) | planned (projected from
    # remaining syllabus) | blocked (holiday/exam eats the period) | past (gone,
    # nothing captured)
    state: str


class DayScheduleOut(BaseModel):
    date: date
    weekday: int
    blocked: bool
    slots: list[DaySlotOut]


class WeekScheduleOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    week_start: date
    periods_per_day: int
    days: list[DayScheduleOut]


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
