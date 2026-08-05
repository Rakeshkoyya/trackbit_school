"""Assessments & bands schemas (M3, SPRD §5.3)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

Date = date  # fields named `date` would shadow the type; alias it


# ── skill areas ──────────────────────────────────────────────────────────────
class SkillAreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    position: int


class SkillAreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


# ── cycles ───────────────────────────────────────────────────────────────────
_TYPE_PATTERN = ("^(diagnostic|unit_test|term_exam|daily_test|chapter_test|class_test"
                 "|slip_test|objective|band_test)$")


class CycleCreate(BaseModel):
    # term_id omitted = derive the term covering `date` (daily-test quick create).
    term_id: uuid.UUID | None = None
    type: str = Field(pattern=_TYPE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    date: Date
    # A daily test is class × subject × date; org-wide cycles leave both NULL.
    class_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None


class CycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    term_id: uuid.UUID
    type: str
    name: str
    date: Date
    class_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    topic: str | None = None
    total_marks: float | None = None
    student_ids: list[uuid.UUID] | None = None


# ── scores / grid ────────────────────────────────────────────────────────────
class ScoreIn(BaseModel):
    student_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    skill_area_id: uuid.UUID | None = None
    score: float = Field(ge=0)
    max_score: float = Field(default=100, gt=0)


class ScoresBulkIn(BaseModel):
    rows: list[ScoreIn] = Field(max_length=5000)


class GridColumn(BaseModel):
    id: uuid.UUID
    name: str
    kind: str  # subject | skill


class GridCell(BaseModel):
    student_id: uuid.UUID
    column_id: uuid.UUID
    score: float
    max_score: float


class ScoreGrid(BaseModel):
    cycle_id: uuid.UUID
    cycle_type: str
    verified: bool
    columns: list[GridColumn]
    students: list[dict]   # [{student_id, full_name}]
    cells: list[GridCell]


class QuestionMark(BaseModel):
    """One question's marks, transcribed off the marked script. A transcription,
    never a judgement about the answer (`Q-51`/`S-117`)."""
    q: str
    score: float
    max: float | None = None


# ── photo score capture (SC-1) ───────────────────────────────────────────────
class CaptureCreate(BaseModel):
    # NULL cycle = draft exam capture (SC-5): the cycle is created on exam save.
    cycle_id: uuid.UUID | None = None
    class_id: uuid.UUID
    subject_id: uuid.UUID | None = None      # at most one of subject/skill
    skill_area_id: uuid.UUID | None = None
    # V1-8 (D-80): `scripts` = one page per student's marked paper, the primary
    # exam flow. `register` = the SC-1 mark register, one page listing many.
    mode: str = Field(default="register", pattern="^(register|scripts)$")
    # Few-students capture: only these students sat the test.
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class CapturePageOut(BaseModel):
    id: uuid.UUID
    page_no: int
    url: str
    content_type: str


class CaptureCandidate(BaseModel):
    student_id: uuid.UUID
    full_name: str


class CaptureParsedRow(BaseModel):
    name_text: str
    roll_text: str | None = None
    # V1-8: nullable, because an unreadable page is still a row — the teacher
    # attaches the student and the marks herself (D-80 step 5). A page we cannot
    # read must never become a page we discard.
    score: float | None = None
    max_score: float | None = None
    student_id: uuid.UUID | None = None
    confidence: str | None = None            # roll | exact | fuzzy | None
    candidates: list[CaptureCandidate] = Field(default_factory=list)
    # V1-8 `scripts` mode: which photographed paper this row came off, so the
    # review grid can show it, and so the confirmed row files the paper against
    # the student (S-119).
    page_no: int | None = None
    page_id: uuid.UUID | None = None
    unreadable: bool = False
    question_marks: list[QuestionMark] | None = None
    sum_mismatch: float | None = None        # S-116: the marks don't add up


class CaptureRosterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None


class CaptureParsedMeta(BaseModel):
    """The AI-read exam header — a form prefill, never persisted as-is (§8)."""
    title: str | None = None
    subject_text: str | None = None
    subject_id: uuid.UUID | None = None      # deterministic match, or None
    total_marks: float | None = None
    topic: str | None = None
    date: str | None = None


class CaptureOut(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID | None
    class_id: uuid.UUID
    subject_id: uuid.UUID | None
    skill_area_id: uuid.UUID | None
    mode: str = "register"
    status: str
    parse_error: str | None
    pages: list[CapturePageOut]
    parsed_rows: list[CaptureParsedRow] | None
    parsed_meta: CaptureParsedMeta | None
    student_ids: list[uuid.UUID] | None
    roster: list[CaptureRosterRow]
    created_at: object


class CaptureSummary(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID | None
    class_id: uuid.UUID
    subject_id: uuid.UUID | None
    skill_area_id: uuid.UUID | None
    status: str
    page_count: int
    created_at: object


class CaptureConfirmRow(BaseModel):
    student_id: uuid.UUID
    score: float = Field(ge=0)
    max_score: float = Field(default=100, gt=0)


class CaptureConfirmIn(BaseModel):
    rows: list[CaptureConfirmRow] = Field(min_length=1, max_length=5000)


# ── exam types (V1-8, D-55) — the school's own word ──────────────────────────
class ExamTypeOut(BaseModel):
    id: uuid.UUID
    name: str            # what every screen displays and groups by
    system_type: str     # the code's kind — never rendered
    scale: str           # minor | major (S-114)
    position: int
    active: bool
    exams: int = 0       # how many exams already carry it (retire, never delete)


class ExamTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    system_type: str = Field(pattern=_TYPE_PATTERN)
    scale: str | None = Field(default=None, pattern="^(minor|major)$")
    position: int | None = None


class ExamTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    scale: str | None = Field(default=None, pattern="^(minor|major)$")
    position: int | None = None
    active: bool | None = None


# ── exams (SC-5) — the scores screen's exam-first surface ────────────────────
class ExamRowIn(BaseModel):
    student_id: uuid.UUID
    score: float = Field(ge=0)
    # Omitted = the exam's total_marks.
    max_score: float | None = Field(default=None, gt=0)
    # V1-8: read off the marked paper when the exam was captured by photo.
    # Absent for a hand-typed exam — which the report says as a word, not a zero.
    question_marks: list[QuestionMark] | None = Field(default=None, max_length=100)
    # V1-8 (`D-80`/`S-119`): the photographed script this mark came off. Set on
    # save — the page↔student link is written when a HUMAN confirms the grid,
    # never by the matcher on its own (§8). It is also how an unreadable page
    # gets mapped by hand: the teacher picks the student, and the page follows.
    page_id: uuid.UUID | None = None
    # The teacher's optional word about THIS paper (founder, 2026-08-05). She is
    # holding it while she types the mark, which is the only moment she knows
    # why the mark is what it is. Optional, always — a required remark is forty
    # sentences typed to record one, which P1v2 does not permit.
    remark: str | None = Field(default=None, max_length=500)


class ExamSaveIn(BaseModel):
    # Set = edit that exam in place; omitted = create.
    cycle_id: uuid.UUID | None = None
    class_id: uuid.UUID
    subject_id: uuid.UUID
    type: str = Field(pattern=_TYPE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    date: Date
    topic: str | None = Field(default=None, max_length=200)
    total_marks: float = Field(default=100, gt=0)
    # V1-8 (D-55): the school's own type — it carries the scale, so the teacher
    # picks one thing, not two.
    exam_type_id: uuid.UUID | None = None
    # V1-8 (S-115): the planned exam block this belongs to. None for a Tuesday
    # slip test, which has no calendar block and never will.
    exam_event_id: uuid.UUID | None = None
    # Few-students test: only these students sat it. None = the whole class.
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    # A draft photo capture to file as this exam's evidence.
    capture_id: uuid.UUID | None = None
    rows: list[ExamRowIn] = Field(default_factory=list, max_length=5000)


class ExamSummary(BaseModel):
    id: uuid.UUID
    type: str
    # V1-8: the school's own word (D-55) and the never-pool bucket (S-114).
    # `type_label` is the fallback for exams recorded before a school named its
    # own types — a fallback, never the primary rendering.
    exam_type_id: uuid.UUID | None = None
    exam_type_name: str | None = None
    type_label: str = ""
    scale: str = "minor"
    locked: bool = False
    name: str
    date: Date
    class_id: uuid.UUID | None
    class_label: str | None          # None = org-wide cycle ("all classes")
    subject_id: uuid.UUID | None
    subject_name: str | None
    topic: str | None
    total_marks: float | None
    few_students: bool
    roster_count: int
    scored_count: int
    avg_pct: float | None
    verified: bool
    created_by_name: str | None
    page_count: int                  # photo evidence pages
    # Org-wide / diagnostic cycles have no single-subject exam page — they open
    # in the score grid instead.
    grid_only: bool


class ExamFeedPage(BaseModel):
    """The feed, paginated (founder, 2026-08-05).

    A school records dozens of tests a term and the landing page returned a flat
    `limit`-capped list, so the 31st was unreachable from any screen. `total` is
    what lets the table say which page of what — a pager without a denominator
    is a Next button that may or may not do anything.
    """

    rows: list[ExamSummary] = []
    page: int = 1
    size: int = 20
    total: int = 0


class ExamRosterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None
    score: float | None
    max_score: float | None
    # V1-8: the per-question marks read off this student's script, and the
    # paper itself — `S-119`, one tap from the mark, which is the one question a
    # parent meeting actually produces.
    question_marks: list[QuestionMark] | None = None
    paper_url: str | None = None
    # `S-116`'s surviving half: the per-question marks don't sum to the total
    # written on the paper. Arithmetic about the TEACHER's paper, never a claim
    # about the child. Signed difference, or None when there is nothing to check.
    sum_mismatch: float | None = None
    remark: str | None = None


class ExamLockRow(BaseModel):
    """One appended lock/unlock (law 3 — the history is the record, the columns
    on the cycle are its cache)."""
    action: str          # lock | unlock
    reason: str | None
    by_name: str | None
    at: object


class ExamDetail(BaseModel):
    id: uuid.UUID
    type: str
    exam_type_id: uuid.UUID | None = None
    exam_type_name: str | None = None
    type_label: str = ""
    scale: str = "minor"
    exam_event_id: uuid.UUID | None = None
    exam_event_name: str | None = None
    name: str
    date: Date
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    subject_name: str
    topic: str | None
    total_marks: float | None
    student_ids: list[uuid.UUID] | None
    verified: bool
    # V1-8 (D-53): locked = this is the record. Editing is refused until an
    # admin unlocks with a reason, and the unlock is appended, never a mutation.
    locked: bool = False
    locked_at: object = None
    locked_by_name: str | None = None
    lock_history: list[ExamLockRow] = Field(default_factory=list)
    avg_pct: float | None
    rows: list[ExamRosterRow]
    pages: list[CapturePageOut]


class ExamLockIn(BaseModel):
    # Required on unlock (Q-62): an unlock without a reason is an edit nobody
    # can account for six months later.
    reason: str | None = Field(default=None, max_length=300)


# ── bands ────────────────────────────────────────────────────────────────────
class BandConfig(BaseModel):
    """Categorization thresholds: pct >= a_min → A, >= b_min → B, else C."""
    a_min: int = Field(ge=2, le=100)
    b_min: int = Field(ge=1, le=99)


class BandCategorizeIn(BaseModel):
    cycle_id: uuid.UUID


class BandCategorizeOut(BaseModel):
    applied: int          # students whose band moved (appended rows)
    counts: dict          # {"A": n, "B": n, "C": n, "no_score": n}


class BandRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    current_tier: str | None
    suggested_tier: str | None
    latest_pct: float | None


class BandBoard(BaseModel):
    class_id: uuid.UUID
    term_id: uuid.UUID | None
    rows: list[BandRow]


class BandSetIn(BaseModel):
    student_id: uuid.UUID
    term_id: uuid.UUID
    tier: str = Field(pattern="^(A|B|C)$")
    # V1-9 (`D-75`): the band belongs to a SUBJECT. Omitting it writes the
    # legacy overall row, which no current computation reads.
    subject_id: uuid.UUID | None = None
    # `D-70`: which route produced this row — marks, or the teacher's own
    # assessment against the descriptors.
    source: str = Field(default="observation", pattern="^(test|observation)$")
    scope_skill_area_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=300)


class BandApplyIn(BaseModel):
    class_id: uuid.UUID
    term_id: uuid.UUID


class BandApplyOut(BaseModel):
    applied: int


class BandHistoryRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tier: str
    scope_skill_area_id: uuid.UUID | None
    note: str | None
    created_at: object


# ── interventions ────────────────────────────────────────────────────────────
class InterventionCreate(BaseModel):
    student_id: uuid.UUID
    term_id: uuid.UUID
    # V1-9 (`D-77`): one plan per (child × subject), with a named owner.
    subject_id: uuid.UUID | None = None
    owner_member_id: uuid.UUID | None = None
    goal_text: str = Field(min_length=1, max_length=300)
    # `S-167`: written when the child ENTERS. A goal decided at the end is a
    # judgement, not a target.
    exit_criterion: str | None = Field(default=None, max_length=300)
    target_tier: str = Field(default="B", pattern="^(A|B|C)$")
    # Optional since V1-9 (§4.6): nobody setting up support for Kabir wants to
    # pick a task board from the school's data model mid-conversation.
    board_id: uuid.UUID | None = None
    items: list[str] = Field(default_factory=list, max_length=20)


class InterventionItemOut(BaseModel):
    id: uuid.UUID
    text: str
    task_instance_id: uuid.UUID | None
    done: bool


class InterventionOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    owner_member_id: uuid.UUID | None = None
    owner_name: str | None = None
    goal_text: str
    exit_criterion: str | None = None
    target_tier: str
    status: str
    closed_at: object = None
    outcome_note: str | None = None
    items: list[InterventionItemOut]


# ── skill profile + trends ───────────────────────────────────────────────────
class SkillProfileCycle(BaseModel):
    cycle_id: uuid.UUID
    name: str
    date: Date
    scores: dict   # skill_name -> pct


class SkillProfile(BaseModel):
    student_id: uuid.UUID
    skills: list[str]
    cycles: list[SkillProfileCycle]


class SubjectTrend(BaseModel):
    subject_id: uuid.UUID
    subject_name: str
    points: list[dict]   # [{cycle_name, date, avg_pct}]
    weak: bool           # dropped across the two most recent cycles


# ── class analysis (SC-4) ────────────────────────────────────────────────────
class AnalysisCyclePoint(BaseModel):
    cycle_id: uuid.UUID
    name: str
    date: Date
    type: str
    # V1-8: the never-pool bucket and the school's own word for the type.
    scale: str = "minor"
    type_label: str = ""
    avg_pct: float | None
    subjects: list[dict]      # [{subject_id, name, avg_pct}]


class AnalysisMover(BaseModel):
    student_id: uuid.UUID
    full_name: str
    latest_pct: float
    prev_pct: float
    delta: float              # latest - prev, in points


class ClassAnalysis(BaseModel):
    class_id: uuid.UUID
    band_counts: dict         # {"A": n, "B": n, "C": n, "unset": n}
    cycles: list[AnalysisCyclePoint]
    movers: list[AnalysisMover]          # sorted, biggest drop first
    histogram: list[dict]     # latest test cycle: [{bucket, count}]
    latest_cycle_name: str | None
