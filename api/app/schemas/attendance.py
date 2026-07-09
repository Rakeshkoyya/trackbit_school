"""Per-period attendance schemas (V2-M4, SPRD2 §5.4) — capture-by-exception."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

# `date` is a field name below; alias the type so the annotation stays valid.
Date = date


class AttendanceExceptionIn(BaseModel):
    student_id: uuid.UUID
    status: str = Field(pattern="^(absent|late)$")
    late_minutes: int | None = Field(default=None, ge=0)


class AttendanceMarkIn(BaseModel):
    """"All present ✓" = an empty `exceptions` list. Tapped deviations are the
    only per-student rows written (P1v2)."""

    class_id: uuid.UUID
    period_no: int = Field(ge=1)
    class_subject_id: uuid.UUID | None = None
    date: Date | None = None
    exceptions: list[AttendanceExceptionIn] = []


class AttendanceRosterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    # Current exception state for the capture sheet (None = present).
    status: str | None = None
    late_minutes: int | None = None


class AttendanceRosterOut(BaseModel):
    """The class roster for one period, pre-loaded with any existing exceptions —
    what the period card's attendance sheet renders."""

    class_id: uuid.UUID
    class_label: str
    period_no: int
    date: date
    # NULL until the period is opened (open-on-action, V2-P6).
    period_id: uuid.UUID | None = None
    marked: bool
    roster: list[AttendanceRosterRow]
    present_count: int
    absent_count: int
    late_count: int


class AttendanceMarkOut(BaseModel):
    period_id: uuid.UUID
    # Deprecated alias for period_id, kept so existing callers keep working
    # across the V2-P6 rename. Prefer period_id.
    mark_id: uuid.UUID
    class_id: uuid.UUID
    period_no: int
    date: date
    roster_count: int
    present_count: int
    absent_count: int
    late_count: int
    # Guardians notified because this was the day's first marked period (§7).
    alerted_count: int
