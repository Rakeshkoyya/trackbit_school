"""The syllabus board (SY-1) — one table of every chapter in the school.

The module could already answer *how much* (V1-6's coverage, V1-15's pace) and
could not show **the syllabus itself**. Plan → Syllabus was a one-class,
one-subject editor: to answer "which chapters are late?" an admin picked her way
through class × subject, one plan at a time, holding the comparison in her head.

This is the same facts as a table — one row per chapter, grouped by class,
filterable and sortable — and every figure on it comes from a roll-up a module
already computes (`services/coverage.py`, `PlannerService.forecast_org`), so the
board and the tab it links to cannot disagree.

Two rules the shape encodes:

  * **Topic detail is optional and the row says which.** Most schools track a
    chapter and nothing finer; some track topics. `has_topic_detail` is decided
    server-side from the chapter's own topics, so the browser never guesses
    whether a row expands.
  * **Planned dates and actual dates are different columns and never merge.**
    The planned pair is the promise (frozen at approval); the actual pair is
    what the lesson logs say happened. A single "date" column would have to pick
    one, and the gap between them is the entire finding.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class SyllabusTopicRow(BaseModel):
    """A topic inside a chapter — only rendered when the school tracks topics."""

    id: uuid.UUID
    title: str
    position: int
    # None = not sized yet, never 0. An unsized topic is not scheduled at all.
    est_periods: int | None = None
    # not_scheduled | not_started | in_progress | completed
    status: str
    # The best lesson-log state: full | partial | None (never logged).
    coverage: str | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    logs: int = 0


class SyllabusChapterRow(BaseModel):
    """One chapter — the board's unit, and the founder's unit of decision."""

    unit_id: uuid.UUID
    class_subject_id: uuid.UUID
    title: str
    position: int
    term_id: uuid.UUID | None = None
    term_name: str | None = None

    # The school's own annotation. Both NULL until somebody writes them; neither
    # is defaulted, so "nobody judged this" stays visible as its own state.
    difficulty: str | None = None
    remarks: str | None = None

    # The school's decision that this chapter is out of scope this year. The one
    # STORED word on a board of derived ones: it forces `status` to
    # `not_scheduled` and takes the chapter's topics out of every coverage
    # numerator and denominator. The row still carries its real `topics_total`
    # and `est_periods`, so the table can show what is being excluded and the
    # decision can be reversed from the same cell that made it.
    not_planned: bool = False

    # Σ of the sized topics. None when NOT ONE topic is sized — the chapter has
    # no estimate at all, which is different from an estimate of zero.
    est_periods: int | None = None
    topics_total: int = 0
    unsized_topics: int = 0
    # Does this chapter have topics worth expanding into? Decided here, not in
    # the browser: a chapter whose single topic repeats its own title is a
    # chapter-only school's row and expanding it shows the same words twice.
    has_topic_detail: bool = False

    # The plan. `planned_*` is the live schedule; `baseline_*` is what was locked
    # at approval, present only once a baseline exists. They differ exactly when
    # somebody rescheduled, and that difference is the point of showing both.
    planned_start: date | None = None
    planned_end: date | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None

    # The record. First and last lesson log against any of its topics.
    actual_start: date | None = None
    actual_end: date | None = None

    # not_scheduled | not_started | in_progress | completed
    #
    # SY-2: this is what the ROW SHOWS — the human's word when she has typed
    # one, the logs' word otherwise. Both are always sent separately as well, so
    # a screen can say which it is looking at and no client has to guess.
    status: str
    # What the lesson logs say, always, whatever the human typed over it.
    derived_status: str = ""
    # What the human typed, or None. Non-null means `status == manual_status`
    # and the row states its progress rather than observing it.
    manual_status: str | None = None
    # Of this chapter's own topics — carries its denominator (`topics_total`).
    # UNAFFECTED by `manual_status`: typing "completed" moves the word on the
    # row, never the percentage under it — coverage stays `core/coverage.py`'s
    # one computation.
    completion_pct: float | None = None
    # V1-15's pace marker, at chapter scale: the share of this chapter's own
    # planned window that has already gone by, in TEACHING days. It is what
    # makes `completion_pct` readable — 40% is fine in the chapter's first week
    # and alarming in its last — and it is divided here rather than in the
    # browser, because two of the five places "syllabus covered" used to be
    # computed were `.reduce()` calls in React (`S-51`). None when the chapter
    # is not scheduled: there is no window to have elapsed.
    expected_pct: float | None = None
    taught_full: int = 0
    taught_partial: int = 0
    # Planned to finish before today and not finished. Never true for a chapter
    # nobody scheduled: an unplanned chapter has not been missed (rule 2).
    overdue: bool = False
    # Days late (or early, negative) — actual finish vs planned finish. None
    # while either end of the comparison is missing.
    finish_drift_days: int | None = None
    topics: list[SyllabusTopicRow] = Field(default_factory=list)


class SyllabusSubjectGroup(BaseModel):
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None = None
    periods_per_week: int = 0
    # none | draft | partial | approved — the plan's own derived cache.
    plan_status: str = "none"
    # The pace, already run through `rated_status` (`S-42`): a subject nobody has
    # logged is **unknown**, never behind.
    pace: str = "unknown"
    coverage_pct: float | None = None
    chapters: list[SyllabusChapterRow] = Field(default_factory=list)


class SyllabusClassGroup(BaseModel):
    class_id: uuid.UUID
    label: str
    subjects: list[SyllabusSubjectGroup] = Field(default_factory=list)


class SyllabusTermOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    # Ended before this school started using TrackBit: its chapters are before
    # our time and are never warned about (V3-P0).
    pre_tracking: bool = False


class SyllabusBoardOut(BaseModel):
    academic_year_id: uuid.UUID | None = None
    as_of: date
    # school = every class (admin) · mine = only the caller's class-subjects.
    scope: str = "school"
    headline: str
    terms: list[SyllabusTermOut] = Field(default_factory=list)
    classes: list[SyllabusClassGroup] = Field(default_factory=list)
    # Counts over the chapters actually returned, so a filtered board's summary
    # describes what is on screen rather than a school nobody is looking at.
    chapters_total: int = 0
    completed: int = 0
    in_progress: int = 0
    not_started: int = 0
    not_scheduled: int = 0
    overdue: int = 0


# ── writes ───────────────────────────────────────────────────────────────────
class ChapterPatchIn(BaseModel):
    """Every field optional; only the ones present are written. `None` for
    `difficulty`/`remarks` cannot be expressed here on purpose — use the
    dedicated clear values (empty string clears a remark, "unset" clears a
    difficulty), so a partial update can never blank a column by omission."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    difficulty: str | None = Field(default=None)  # easy | moderate | hard | unset
    remarks: str | None = Field(default=None, max_length=2000)
    term_id: uuid.UUID | None = None
    clear_term: bool = False
    # True = out of scope this year, False = back in. Absent leaves it alone,
    # like every other field here.
    not_planned: bool | None = None

    # SY-2 — the typed teaching status. "unset" hands the row back to the
    # lesson logs, the same shape `difficulty` uses, so a cell can always be
    # returned to its derived state from the control that overrode it.
    status: str | None = Field(default=None)  # not_started|in_progress|completed|unset

    # The chapter's period estimate, set from the chapter row rather than by
    # opening its topics. Only meaningful when the chapter holds exactly ONE
    # topic — the chapter-only shape every importer produces and the one the
    # grid renders as a single line. A chapter genuinely split into topics is
    # sized topic by topic and the service says so rather than silently
    # picking one to carry the whole number.
    est_periods: int | None = Field(default=None, ge=0, le=400)
    clear_est_periods: bool = False


class ChapterScheduleIn(BaseModel):
    """Move one chapter to a date range. Dates, not weeks: the teacher is looking
    at a calendar and an exam, and asking her to think in Monday-indices would be
    asking her to do the conversion the server can do."""

    unit_id: uuid.UUID
    start_date: date
    end_date: date


class RescheduleIn(BaseModel):
    chapters: list[ChapterScheduleIn] = Field(min_length=1, max_length=200)


class RescheduleViolation(BaseModel):
    unit_id: uuid.UUID | None = None
    code: str  # too_short | overlaps | outside_year | unsized | past_exam
    message: str


class RescheduleOut(BaseModel):
    """Saved either way. `fits` False means the dates she chose do not hold the
    chapters she put in them — reported, never squeezed (V2-P5's rule), because
    the teacher is the one who knows whether she can go faster."""

    fits: bool
    violations: list[RescheduleViolation] = Field(default_factory=list)
    chapters: list[SyllabusChapterRow] = Field(default_factory=list)


# ── the plan timeline (the reschedule dialog's own read) ─────────────────────
class TimelineChapter(BaseModel):
    unit_id: uuid.UUID
    title: str
    position: int
    est_periods: int | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    status: str
    difficulty: str | None = None
    locked: bool = False


class TimelineMarker(BaseModel):
    """An exam, a term boundary or today — the fixed points she is planning
    against. Everything she can move is a chapter; everything she cannot is a
    marker."""

    kind: str  # exam | term_start | term_end | today
    label: str
    date: date
    end_date: date | None = None


class PlanTimelineOut(BaseModel):
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str
    window_start: date
    window_end: date
    # Working days per week and periods per week, so the dialog can say what a
    # week of a chapter is worth without a second round trip.
    periods_per_week: int = 0
    locked: bool = False
    # Why she cannot edit, when she cannot. Present only when `locked`.
    lock_reason: str | None = None
    chapters: list[TimelineChapter] = Field(default_factory=list)
    markers: list[TimelineMarker] = Field(default_factory=list)


# ── exam ↔ syllabus mapping ──────────────────────────────────────────────────
class ExamMapChapter(BaseModel):
    unit_id: uuid.UUID
    title: str
    position: int
    est_periods: int | None = None
    term_id: uuid.UUID | None = None
    # In THIS exam's portion.
    selected: bool = False
    # Already examined by an earlier exam — so selecting it here is a deliberate
    # re-examination, not an omission somebody forgot to fix.
    covered_earlier: bool = False
    status: str = "not_scheduled"
    planned_end: date | None = None


class ExamMapSubject(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    # legacy_prefix = the portion came from `upto_topic_id` and has never been
    # restated as a chapter set. Shown as such rather than silently converted.
    source: str = "none"  # none | chapters | legacy_prefix
    # From `PlannerService.exam_fit`, unchanged: short | tight | fits | surplus |
    # no_portion | unallocated.
    verdict: str = "no_portion"
    required_periods: int = 0
    capacity_periods: float = 0
    unsized_topics: int = 0
    chapters: list[ExamMapChapter] = Field(default_factory=list)


class ExamMapExam(BaseModel):
    exam_event_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    days_to_exam: int
    teaching_days_in_gap: int
    subjects: list[ExamMapSubject] = Field(default_factory=list)


class ExamMapOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    headline: str
    exams: list[ExamMapExam] = Field(default_factory=list)


class ExamPortionSetIn(BaseModel):
    """Full replace of one (exam, class-subject) portion. An empty list clears
    it — "this exam examines nothing of this subject" is a real answer for a
    languages-only exam block, and a delete-shaped API cannot say it."""

    exam_event_id: uuid.UUID
    class_subject_id: uuid.UUID
    unit_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
