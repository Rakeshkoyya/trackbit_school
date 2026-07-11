"""After-school & hostel session schemas (M2 + HS-1, SPRD §5.2)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# Fields named `date` would shadow the `date` type in the class body; alias it.
Date = date

_TIME = r"^\d{2}:\d{2}$"
_KIND = "^(study|homework|activity)$"


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int] = Field(default_factory=list)  # Mon=0 … Sun=6
    time: str | None = Field(default=None, max_length=10)  # "16:15"
    end_time: str | None = Field(default=None, max_length=10)  # "17:30"
    kind: str = Field(default="study", pattern=_KIND)
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    class_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    hostellers_only: bool = False
    # Admin assigns the teacher who runs the block; non-admins always own their own.
    owner_member_id: uuid.UUID | None = None


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    weekdays: list[int] | None = None
    time: str | None = Field(default=None, max_length=10)
    end_time: str | None = Field(default=None, max_length=10)
    kind: str | None = Field(default=None, pattern=_KIND)
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    class_ids: list[uuid.UUID] | None = Field(default=None, max_length=30)
    hostellers_only: bool | None = None
    owner_member_id: uuid.UUID | None = None
    active: bool | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    name: str
    weekdays: list[int]
    time: str | None
    end_time: str | None = None
    kind: str = "study"
    hostellers_only: bool = False
    active: bool
    roster_count: int
    class_labels: list[str] = Field(default_factory=list)
    teacher_name: str | None = None
    owner_member_id: uuid.UUID | None = None


class SessionStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None
    # True when the student is an explicit session_students row (ad-hoc addition),
    # False when they come in via a linked class.
    explicit: bool = False


class SessionDetail(SessionOut):
    students: list[SessionStudentOut] = Field(default_factory=list)
    class_ids: list[uuid.UUID] = Field(default_factory=list)


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
    class_label: str | None = None
    status: str | None = None
    late_minutes: int | None = None
    homework_done: bool | None = None
    # HS-2: tonight's study log — section count + a one-line preview.
    log_count: int = 0
    log_note: str | None = None
    media_count: int = 0


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str  # photo | video
    url: str  # minted at read time from the stored object key
    content_type: str
    caption: str | None = None
    # NULL = whole-class memory; set = that student's own memory (HS-2).
    student_id: uuid.UUID | None = None
    created_at: datetime


class MeetingOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    date: Date
    kind: str = "study"
    evidence_url: str | None
    roster: list[MeetingRosterRow]
    media: list[MediaOut] = Field(default_factory=list)


# ── per-student study logs (HS-2: named sections, like the class deep log) ──
class StudentLogEntry(BaseModel):
    section: str = Field(default="", max_length=80)
    note: str = Field(min_length=1, max_length=2000)


class StudentLogsReplaceIn(BaseModel):
    entries: list[StudentLogEntry] = Field(max_length=30)  # full-replace for one student


# ── homework board (HS-1) ────────────────────────────────────────────────────
class HomeworkItem(BaseModel):
    assignment_id: uuid.UUID
    subject: str
    text: str
    assigned_on: Date
    due_date: Date | None = None
    personal: bool = False  # per-student addition vs whole-class


class HomeworkBoardRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    homework_done: bool | None = None
    items: list[HomeworkItem] = Field(default_factory=list)


class HomeworkBoardOut(BaseModel):
    meeting_id: uuid.UUID
    date: Date
    rows: list[HomeworkBoardRow]


# ── media (HS-1) ─────────────────────────────────────────────────────────────
class MediaPresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=1)
    student_id: uuid.UUID | None = None  # set = this student's memory


class MediaPresignOut(BaseModel):
    key: str
    # None when R2 isn't configured — client falls back to the direct upload route.
    upload_url: str | None


class MediaConfirmIn(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    caption: str | None = Field(default=None, max_length=300)
    student_id: uuid.UUID | None = None


# ── per-student card (HS-2) — one round trip for the student page ───────────
class SessionStudentCard(BaseModel):
    meeting_id: uuid.UUID
    date: Date
    session_id: uuid.UUID
    session_name: str
    kind: str
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_label: str | None = None
    status: str | None = None
    late_minutes: int | None = None
    homework_done: bool | None = None
    homework: list[HomeworkItem] = Field(default_factory=list)
    logs: list[StudentLogEntry] = Field(default_factory=list)
    media: list[MediaOut] = Field(default_factory=list)


# ── records feed (P1.5-B / dashboard precursor) ──────────────────────────────
class SessionRecord(BaseModel):
    session_id: uuid.UUID
    meeting_id: uuid.UUID
    session_name: str
    date: Date
    kind: str = "study"
    present: int
    late: int
    absent: int
    homework_done: int
    total: int
    evidence_url: str | None
    media_count: int = 0
