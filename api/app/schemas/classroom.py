"""Classroom log / homework schemas (M2, SPRD §5.2)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# Several fields are named `date`, which shadows the `date` type inside the class
# body before its own annotation is evaluated. Annotate those via this alias so
# the field name can't clobber the type.
Date = date


# ── My Day (CL-1) ────────────────────────────────────────────────────────────
class MyDayClass(BaseModel):
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str
    planned_topic: str | None = None
    planned_topic_id: uuid.UUID | None = None
    logged: bool = False
    homework_set: bool = False


class HomeworkPending(BaseModel):
    assignment_id: uuid.UUID
    class_label: str
    subject_name: str
    text: str


class MyDayPeriod(BaseModel):
    """One timetabled period today (V2-P1 §5.4) — My Day rendered from the grid,
    with the period card's attendance state (V2-P2 §5.4) and its own lifecycle
    (V2-P6). Two periods of the same class-subject on one day are independent:
    `logged` and `planned_topic` are resolved per period, never per class-subject."""
    period_no: int
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    planned_topic: str | None = None
    planned_topic_id: uuid.UUID | None = None
    logged: bool = False
    # Period lifecycle — period_id is NULL until the teacher opens the card.
    period_id: uuid.UUID | None = None
    status: str = "held"
    opened: bool = False
    closed: bool = False
    # Attendance step of the card (capture-by-exception).
    attendance_marked: bool = False
    roster_count: int = 0
    present_count: int | None = None
    absent_count: int | None = None
    late_count: int | None = None
    # Day-scoped by design: homework is set once per class-subject per day, so a
    # second period of the same subject shows it as already done.
    homework_set: bool = False


class MyDayOut(BaseModel):
    date: date
    classes: list[MyDayClass]
    periods: list[MyDayPeriod] = []
    homework_pending: list[HomeworkPending]


# ── quick log (CL-2) ─────────────────────────────────────────────────────────
class LessonLogIn(BaseModel):
    class_subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    coverage: str = Field(default="full", pattern="^(full|partial)$")
    date: Date | None = None
    note: str | None = Field(default=None, max_length=500)
    # Anchor the log to one period occurrence (V2-P6). Either pass period_id
    # directly, or pass period_no and the service resolves/opens it. Omit both for
    # a quick log with no period (the old CL-2 behaviour).
    period_id: uuid.UUID | None = None
    period_no: int | None = Field(default=None, ge=1)


class LessonLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_subject_id: uuid.UUID
    date: date
    topic_id: uuid.UUID | None
    coverage: str
    period_id: uuid.UUID | None = None


# ── homework (CL-2 / CL-3) ───────────────────────────────────────────────────
class HomeworkIn(BaseModel):
    class_subject_id: uuid.UUID
    text: str = Field(min_length=1, max_length=1000)
    due_date: date | None = None
    date: Date | None = None
    # Set to target one student (a per-student addition); null = whole class (V2-P3).
    student_id: uuid.UUID | None = None


class HomeworkOut(BaseModel):
    id: uuid.UUID
    class_subject_id: uuid.UUID
    date: date
    text: str
    due_date: date | None
    student_id: uuid.UUID | None = None
    notified_count: int  # guardians notified (the teacher's payback, P3)


class HomeworkCheckIn(BaseModel):
    done_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


# ── deep log — lesson observations (teacher-view redesign) ──────────────────
class ObservationStudentIn(BaseModel):
    """One tapped deviation — the only per-student rows that exist (P1v2)."""

    student_id: uuid.UUID
    rating: str = Field(pattern="^(excellent|needs_work)$")
    note: str | None = Field(default=None, max_length=300)


class ObservationConceptIn(BaseModel):
    concept: str = Field(min_length=1, max_length=80)
    students: list[ObservationStudentIn] = []


class ObservationSectionIn(BaseModel):
    """Full-replace save of ONE section of a period's deep log ("Vocabulary" with
    its concepts and tapped students). Saving again with the same section name
    replaces its rows, like re-marking attendance."""

    class_subject_id: uuid.UUID
    section: str = Field(min_length=1, max_length=80)
    date: Date | None = None
    period_id: uuid.UUID | None = None
    period_no: int | None = Field(default=None, ge=1)
    concepts: list[ObservationConceptIn] = []


class ObservationStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    rating: str
    note: str | None = None


class ObservationConceptOut(BaseModel):
    concept: str | None = None
    students: list[ObservationStudentOut] = []


class ObservationSectionOut(BaseModel):
    section: str
    period_id: uuid.UUID | None = None
    concepts: list[ObservationConceptOut] = []


class ObservationsOut(BaseModel):
    class_subject_id: uuid.UUID
    date: date
    sections: list[ObservationSectionOut] = []


# ── compliance (CL-4) ────────────────────────────────────────────────────────
class ComplianceRow(BaseModel):
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str
    teacher_name: str | None = None
    logged: bool


class ComplianceOut(BaseModel):
    date: date
    logged_count: int
    total: int
    rows: list[ComplianceRow]
