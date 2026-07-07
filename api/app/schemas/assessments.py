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
    term_id: uuid.UUID
    type: str = Field(pattern="^(diagnostic|unit_test|term_exam)$")
    name: str = Field(min_length=1, max_length=120)
    date: Date


class CycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    term_id: uuid.UUID
    type: str
    name: str
    date: Date


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
