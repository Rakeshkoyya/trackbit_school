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
class CycleCreate(BaseModel):
    # term_id omitted = derive the term covering `date` (daily-test quick create).
    term_id: uuid.UUID | None = None
    type: str = Field(pattern="^(diagnostic|unit_test|term_exam|daily_test)$")
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


# ── photo score capture (SC-1) ───────────────────────────────────────────────
class CaptureCreate(BaseModel):
    cycle_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID | None = None      # exactly one of subject/skill
    skill_area_id: uuid.UUID | None = None


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
    score: float
    max_score: float | None = None
    student_id: uuid.UUID | None = None
    confidence: str | None = None            # roll | exact | fuzzy | None
    candidates: list[CaptureCandidate] = Field(default_factory=list)


class CaptureRosterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None


class CaptureOut(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID | None
    skill_area_id: uuid.UUID | None
    status: str
    parse_error: str | None
    pages: list[CapturePageOut]
    parsed_rows: list[CaptureParsedRow] | None
    roster: list[CaptureRosterRow]
    created_at: object


class CaptureSummary(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
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


# ── bands ────────────────────────────────────────────────────────────────────
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
    goal_text: str = Field(min_length=1, max_length=300)
    target_tier: str = Field(default="B", pattern="^(A|B|C)$")
    board_id: uuid.UUID   # where the checklist tasks land (M5)
    items: list[str] = Field(default_factory=list, max_length=20)


class InterventionItemOut(BaseModel):
    id: uuid.UUID
    text: str
    task_instance_id: uuid.UUID | None
    done: bool


class InterventionOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_text: str
    target_tier: str
    status: str
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
