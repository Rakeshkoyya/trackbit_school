"""Students / guardians / categories schemas (SPRD §4.2)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingest import AnalyzeOut


# ── Fee category ─────────────────────────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    # What depends on this category right now. Settings shows both before
    # offering to remove one (`D-129`); zero is a real answer, not missing data.
    student_count: int = 0
    block_count: int = 0


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
    date_of_birth: date | None = None  # V1-2 (D-13): the parent's password
    category_id: uuid.UUID | None = None
    # Optional inline guardians so roster import / add-student is one round-trip.
    guardians: list[GuardianCreate] = Field(default_factory=list, max_length=10)


class StudentUpdate(BaseModel):
    # Correctable in place, deliberately: an admission number is transcribed from
    # a paper register at import and a wrong one is a typo, not a decision, so
    # law 3's append-only rule does not apply. `update_student` re-checks it
    # against the org's unique constraint — without that the PATCH is a 500.
    admission_no: str | None = Field(default=None, min_length=1, max_length=32)
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    class_id: uuid.UUID | None = None
    roll_no: str | None = Field(default=None, max_length=16)
    date_of_birth: date | None = None
    category_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|left)$")


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    admission_no: str
    full_name: str
    class_id: uuid.UUID | None
    roll_no: str | None
    date_of_birth: date | None = None
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
    # V1-2 (D-13): DOB values that would not parse — reported, never guessed.
    unresolved: list[dict] = Field(default_factory=list)
