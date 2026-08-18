"""Class-period lifecycle + period-card schemas (V2-P6).

The period card is the teacher's whole interaction with one class-period: who is
here, what was planned, what got taught, what homework went out. It is assembled
from existing modules — nothing here is a new capture surface.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.assessments import ExamSummary
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
    """V1-7 `S-147`: the reason POINTS AT THE EVENT, not at free text.

    "Not held — Independence Day rehearsal" typed by forty teachers in forty
    spellings answers nothing. With `event_id` set, the school can ask what
    Diwali cost it in periods and which classes lost the most to functions this
    term. Free text stays available as the note — it is what she types when the
    reason is not on the calendar at all, which is `S-146`'s per-class case
    (8-A went to the rehearsal while 8-B carried on teaching).
    """
    reason: str = Field(min_length=1)
    event_id: uuid.UUID | None = None


class PeriodOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    date: date
    period_no: int
    class_subject_id: uuid.UUID | None = None
    teacher_member_id: uuid.UUID | None = None
    status: str
    not_held_reason: str | None = None
    not_held_event_id: uuid.UUID | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    attendance_marked_at: datetime | None = None

    model_config = {"from_attributes": True}


class TopicProgressRow(BaseModel):
    """One syllabus topic and how far the class actually got with it."""

    topic_id: uuid.UUID
    topic_title: str
    unit_title: str
    # None = the chapter has no period estimate yet, so it is not scheduled.
    est_periods: int | None = None
    # done (a full-coverage log exists) | in_progress (only partial logs) | pending
    status: str


class PeriodLogOut(BaseModel):
    """One topic actually taught this period. A period can hold several (the
    class finished one topic and started the next), and the same topic can span
    many days via `partial` coverage until it's finished."""

    id: uuid.UUID
    topic_id: uuid.UUID | None = None
    topic_title: str | None = None
    coverage: str
    note: str | None = None


class PeriodPlanOut(BaseModel):
    """What the plan says this period is for, plus the chapter's running progress."""

    planned_topic_id: uuid.UUID | None = None
    planned_topic_title: str | None = None
    planned_unit_title: str | None = None
    # First log of the period — kept for existing callers; `logged` is the full list.
    logged_topic_id: uuid.UUID | None = None
    logged_coverage: str | None = None
    logged: list[PeriodLogOut] = []
    progress: list[TopicProgressRow] = []


class PeriodHomeworkOut(BaseModel):
    id: uuid.UUID
    text: str
    # Set when this is a per-student addition rather than class-wide (§5.5).
    student_id: uuid.UUID | None = None
    due_date: date | None = None


class CombinedClassCard(BaseModel):
    """One class's half of a combined period (TT-4).

    The teacher captures once; the record is still each class's own. Attendance,
    the lesson log and the homework all land per class — so what this carries is
    one class's state of that shared meeting, and the card renders as many of
    these as there are classes in the room.

    The **plan stays per class and is not pooled.** A 5th-class Maths chapter is
    not a 6th-class Maths chapter, however identical the lesson in the room was;
    one shared topic list would either move the wrong syllabus or invent a
    seventh definition of "covered" (see `core/coverage.py` on why that matters).
    """

    class_id: uuid.UUID
    class_label: str
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    # This class's own register for the period.
    period_id: uuid.UUID | None = None
    attendance_marked: bool = False
    roster_count: int = 0
    present_count: int | None = None
    absent_count: int | None = None
    late_count: int | None = None
    plan: "PeriodPlanOut" = Field(default_factory=lambda: PeriodPlanOut())
    homework: list["PeriodHomeworkOut"] = []


class PeriodEventOut(BaseModel):
    """One approved calendar row running on this date, offered as the reason."""
    id: uuid.UUID
    title: str
    type: str
    affects_teaching: bool
    blocks_periods: list[int] | None = None


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

    # TT-4 — the classes sitting in this room. EMPTY on an ordinary period, so a
    # caller can branch on `combined` alone; when set it includes THIS class, so
    # the card can iterate one list rather than "this one, plus the others".
    combined_id: uuid.UUID | None = None
    combined_label: str | None = None
    combined: list[CombinedClassCard] = []

    # Lifecycle — period_id is NULL until the teacher opens it.
    period_id: uuid.UUID | None = None
    status: str = "held"
    not_held_reason: str | None = None
    not_held_event_id: uuid.UUID | None = None
    # The approved events running on this date — the picker behind "not held,
    # because" (`S-147`). Empty on an ordinary day, and the teacher types
    # instead.
    day_events: list["PeriodEventOut"] = []
    # V1-7 `S-145`: the admin already locked this period school-wide, so the
    # teacher is never ASKED about it. `S-146`: the admin's lock and the
    # teacher's block are different scopes and must not both be recorded, or the
    # day is subtracted from capacity twice.
    locked: bool = False
    lock_reason: str | None = None
    opened: bool = False
    closed: bool = False

    # Attendance
    attendance_marked: bool = False
    # V1-3 (D-01/Q-02a): False when the org's mode doesn't take attendance in
    # this period — the card's OTHER sections (topic, homework, checks) stay.
    #
    # Dynamic in `first_period` (founder, 2026-08-05): the register belongs to
    # the DAY, so this is true on every period until somebody takes it and only
    # on the holder afterwards. Read it with `day_attendance_taken`, which is
    # what separates "not asked because it is done" from "not asked because this
    # period never marks" — the card says the first out loud and stays silent
    # about the second.
    marks_attendance: bool = True
    day_attendance_taken: bool | None = None
    roster: list[AttendanceRosterRow] = []
    roster_count: int = 0
    present_count: int | None = None
    absent_count: int | None = None
    late_count: int | None = None

    plan: PeriodPlanOut = PeriodPlanOut()
    homework: list[PeriodHomeworkOut] = []

    # The tests already recorded for this class-subject TODAY (SC-2/V1-8).
    #
    # Founder, 2026-08-18: photographing a test from the period card left no
    # trace on it — the review sheet closed and the section went back to
    # offering a capture that had already happened, so the teacher had no way
    # to see what she had just recorded, or back to the papers. This is the
    # same `ExamSummary` the exams feed renders, deliberately: the row on My
    # Day and the row on Students → Exams are the same exam, and a second
    # shape here would be a second place for "how many scored" to drift.
    #
    # Empty is the ordinary case. Only exams with something ON them (a mark or
    # a photographed paper) are listed — a started-then-discarded capture
    # leaves an empty cycle behind, and offering that as a record would be a
    # ghost the teacher cannot act on.
    tests: list[ExamSummary] = []
