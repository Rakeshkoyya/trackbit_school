"""Students / guardians / categories schemas (SPRD §4.2)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingest import AnalyzeOut


# ── Fee category ─────────────────────────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


# ── Guardian ─────────────────────────────────────────────────────────────────
class GuardianCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=32)
    phone: str = Field(min_length=5, max_length=20)  # E.164
    is_primary: bool = False
    notify_opt_out: bool = False


class GuardianUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, min_length=5, max_length=20)
    is_primary: bool | None = None
    notify_opt_out: bool | None = None


class GuardianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    name: str
    relation: str | None
    phone: str
    is_primary: bool
    notify_opt_out: bool


# ── Student ──────────────────────────────────────────────────────────────────
class StudentCreate(BaseModel):
    admission_no: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=120)
    class_id: uuid.UUID | None = None
    roll_no: str | None = Field(default=None, max_length=16)
    category_id: uuid.UUID | None = None
    # Optional inline guardians so roster import / add-student is one round-trip.
    guardians: list[GuardianCreate] = Field(default_factory=list, max_length=10)


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    class_id: uuid.UUID | None = None
    roll_no: str | None = Field(default=None, max_length=16)
    category_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|left)$")


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    admission_no: str
    full_name: str
    class_id: uuid.UUID | None
    roll_no: str | None
    status: str
    category_id: uuid.UUID | None


class StudentDetailOut(StudentOut):
    """ST-2 Overview: student + resolved labels + guardians."""
    class_label: str | None = None
    category_name: str | None = None
    guardians: list[GuardianOut] = Field(default_factory=list)


# ── roster xlsx import (SPRD §5.6, students mode) ────────────────────────────
class RosterAnalyzeOut(AnalyzeOut):
    """Same envelope as staff/syllabus (services/ingest.py). `mapping` is roster's own
    tuned heuristic; `questions` cover only the fields commit() would reject a row for."""


class RosterCommitIn(BaseModel):
    mapping: dict[str, str]
    rows: list[dict] = Field(max_length=5000)
    academic_year_id: uuid.UUID | None = None  # scopes class matching


class RosterCommitOut(BaseModel):
    created: int
    skipped: int
    errors: list[dict] = Field(default_factory=list)
