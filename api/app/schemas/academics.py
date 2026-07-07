"""Academic master-data schemas (SPRD §4.2 / §5.1)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Dated(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _order(self) -> "_Dated":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


# ── Academic year ────────────────────────────────────────────────────────────
class YearCreate(_Dated):
    label: str = Field(min_length=1, max_length=32)  # "2026-27"


class YearUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=32)
    start_date: date | None = None
    end_date: date | None = None


class YearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    is_active: bool


# ── Term ─────────────────────────────────────────────────────────────────────
class TermCreate(_Dated):
    academic_year_id: uuid.UUID
    name: str = Field(min_length=1, max_length=64)


class TermUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    start_date: date | None = None
    end_date: date | None = None


class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    start_date: date
    end_date: date


# ── Subject ──────────────────────────────────────────────────────────────────
class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


# ── Class ────────────────────────────────────────────────────────────────────
class ClassCreate(BaseModel):
    academic_year_id: uuid.UUID
    name: str = Field(min_length=1, max_length=32)  # "6"
    section: str | None = Field(default=None, max_length=16)  # "B"
    class_teacher_member_id: uuid.UUID | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    section: str | None = Field(default=None, max_length=16)
    class_teacher_member_id: uuid.UUID | None = None


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    section: str | None
    class_teacher_member_id: uuid.UUID | None


# ── Class–subject (periods/week is entered, never generated: §11 fence) ───────
class ClassSubjectCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_member_id: uuid.UUID | None = None
    periods_per_week: int = Field(default=0, ge=0, le=60)


class ClassSubjectUpdate(BaseModel):
    teacher_member_id: uuid.UUID | None = None
    periods_per_week: int | None = Field(default=None, ge=0, le=60)


class ClassSubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str | None = None
    teacher_member_id: uuid.UUID | None
    periods_per_week: int
