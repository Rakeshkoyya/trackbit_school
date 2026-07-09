"""Class-period lifecycle + period-card schemas (V2-P6).

The period card is the teacher's whole interaction with one class-period: who is
here, what was planned, what got taught, what homework went out. It is assembled
from existing modules — nothing here is a new capture surface.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.attendance import AttendanceRosterRow

# `date` is a field name below; alias the type so the annotation stays valid.
Date = date


class PeriodOpenIn(BaseModel):
    """Sent when the teacher taps "Start attendance" (open-on-action)."""

    class_id: uuid.UUID
    period_no: int = Field(ge=1)
    class_subject_id: uuid.UUID | None = None
    date: Date | None = None


class PeriodNotHeldIn(BaseModel):
    reason: str = Field(min_length=1)


class PeriodOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    date: date
    period_no: int
    class_subject_id: uuid.UUID | None = None
    teacher_member_id: uuid.UUID | None = None
    status: str
    not_held_reason: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    attendance_marked_at: datetime | None = None

    model_config = {"from_attributes": True}


class TopicProgressRow(BaseModel):
    """One syllabus topic and how far the class actually got with it."""

    topic_id: uuid.UUID
    topic_title: str
    unit_title: str
    est_periods: int
    # done (a full-coverage log exists) | in_progress (only partial logs) | pending
    status: str


class PeriodPlanOut(BaseModel):
    """What the plan says this period is for, plus the chapter's running progress."""

    planned_topic_id: uuid.UUID | None = None
    planned_topic_title: str | None = None
    planned_unit_title: str | None = None
    logged_topic_id: uuid.UUID | None = None
    logged_coverage: str | None = None
    progress: list[TopicProgressRow] = []


class PeriodHomeworkOut(BaseModel):
    id: uuid.UUID
    text: str
    # Set when this is a per-student addition rather than class-wide (§5.5).
    student_id: uuid.UUID | None = None
    due_date: date | None = None


class PeriodCardOut(BaseModel):
    """Everything the period-detail page renders in one call.

    Daily checks are deliberately NOT here — they are day-scoped and generated
    lazily by /checks, which the page calls separately (see models/periods.py on
    why homework and checks stay day-scoped while attendance and logs do not)."""

    class_id: uuid.UUID
    class_label: str
    period_no: int
    date: date
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None

    # Lifecycle — period_id is NULL until the teacher opens it.
    period_id: uuid.UUID | None = None
    status: str = "held"
    not_held_reason: str | None = None
    opened: bool = False
    closed: bool = False

    # Attendance
    attendance_marked: bool = False
    roster: list[AttendanceRosterRow] = []
    roster_count: int = 0
    present_count: int | None = None
    absent_count: int | None = None
    late_count: int | None = None

    plan: PeriodPlanOut = PeriodPlanOut()
    homework: list[PeriodHomeworkOut] = []
