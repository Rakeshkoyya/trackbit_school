"""Daily checks / recommendations schemas (V2-M5, SPRD2 §5.5)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

Date = date


class CheckResultOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    status: str  # not_done | note
    note: str | None = None


class DailyCheckOut(BaseModel):
    id: uuid.UUID
    description: str
    source: str
    band_scope: str
    student_id: uuid.UUID | None = None
    student_name: str | None = None
    confirmed: bool = False
    results: list[CheckResultOut] = []


class ChecksOut(BaseModel):
    class_subject_id: uuid.UUID
    date: date
    checks: list[DailyCheckOut]


class CheckExceptionIn(BaseModel):
    student_id: uuid.UUID
    status: str = Field(pattern="^(not_done|note)$")
    note: str | None = Field(default=None, max_length=500)


class CheckConfirmIn(BaseModel):
    """"Class did it ✓" = an empty exceptions list. Deviations are the only
    per-student rows written (P1v2)."""

    exceptions: list[CheckExceptionIn] = []
