"""After-school session schemas (M2, SPRD §5.2 — SS-1/SS-2)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

# Fields named `date` would shadow the `date` type in the class body; alias it.
Date = date


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int] = Field(default_factory=list)  # Mon=0 … Sun=6
    time: str | None = Field(default=None, max_length=10)  # "16:15"
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class SessionOut(BaseModel):
    id: uuid.UUID
    name: str
    weekdays: list[int]
    time: str | None
    active: bool
    roster_count: int


class SessionStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None


class SessionDetail(SessionOut):
    students: list[SessionStudentOut] = Field(default_factory=list)


# ── capture (SS-2) ───────────────────────────────────────────────────────────
class AttendanceIn(BaseModel):
    student_id: uuid.UUID
    status: str = Field(pattern="^(present|late|absent)$")
    late_minutes: int | None = Field(default=None, ge=0, le=240)
    homework_done: bool | None = None


class AttendanceRecordIn(BaseModel):
    rows: list[AttendanceIn] = Field(max_length=200)


class MeetingRosterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None
    status: str | None = None
    late_minutes: int | None = None
    homework_done: bool | None = None


class MeetingOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    date: Date
    evidence_url: str | None
    roster: list[MeetingRosterRow]


# ── records feed (P1.5-B / dashboard precursor) ──────────────────────────────
class SessionRecord(BaseModel):
    session_id: uuid.UUID
    meeting_id: uuid.UUID
    session_name: str
    date: Date
    present: int
    late: int
    absent: int
    homework_done: int
    total: int
    evidence_url: str | None
