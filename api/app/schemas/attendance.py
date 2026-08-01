"""Per-period attendance schemas (V2-M4, SPRD2 §5.4) — capture-by-exception."""

import uuid
from datetime import date, datetime

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
    # Guardians notified because this was the day's first marked period (§7) —
    # or, in twice_daily mode, because a child present in the morning was absent
    # after lunch (V1-3, Q-03/S-05).
    alerted_count: int


# ── absence reasons + informed absence (V1-3, D-02/D-86/S-24) ────────────────
# A small shared vocabulary for the chips; free text rides in the note. Stored
# as plain text — a school's own word is kept, never flattened.
REASON_CODES = ("sick", "family", "travel", "informed", "other")


class AbsenceReasonIn(BaseModel):
    """Recorded AFTER capture, by admin or teacher (D-02 step 3). Stamps every
    absent exception for that student on that day — the reason belongs to the
    absence, not to one period of it."""

    student_id: uuid.UUID
    date: Date
    reason_code: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=300)


class AbsenceReasonOut(BaseModel):
    student_id: uuid.UUID
    date: date
    reason_code: str | None = None
    note: str | None = None
    updated_periods: int


class AbsenceNoteIn(BaseModel):
    """Informed/planned absence (S-24): "away 12–15 Aug, family function"."""

    student_id: uuid.UUID
    from_date: Date
    to_date: Date
    reason_code: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=500)
    source: str = Field(default="office", pattern="^(parent_call|office|teacher)$")


class AbsenceNoteOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    from_date: date
    to_date: date
    reason_code: str | None = None
    note: str | None = None
    source: str
    created_by_name: str | None = None
    created_at: datetime | None = None
