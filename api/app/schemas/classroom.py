"""Classroom log / homework schemas (M2, SPRD §5.2)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskOut

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
    # V1-3 (D-01/Q-02a): the org's mode may not take attendance this period.
    #
    # In `first_period` this is DYNAMIC (founder, 2026-08-05): true on every
    # period of a class whose day has not been captured, false on all of them
    # once it has — except the one holding the register, which keeps the row so
    # its taker can still correct it. A fixed "period 1 only" rule left the
    # afternoon asking for a roll that was taken at 9am, and left a class whose
    # period 1 never happened with no way to record the day at all.
    marks_attendance: bool = True
    # Once-per-day schools only (null elsewhere): has THIS class's day been
    # captured? What lets a period card say "the register was taken this
    # morning" instead of silently dropping the section.
    day_attendance_taken: bool | None = None
    roster_count: int = 0
    present_count: int | None = None
    absent_count: int | None = None
    late_count: int | None = None
    # Day-scoped by design: homework is set once per class-subject per day, so a
    # second period of the same subject shows it as already done.
    homework_set: bool = False
    # DASH3 PR-2: this period is not on my timetable — I am covering it for
    # someone who is away today. Rendered differently so the teacher knows why a
    # class they don't teach is in their day.
    substituting: bool = False
    covering_for: str | None = None


class MyDayOut(BaseModel):
    date: date
    classes: list[MyDayClass]
    periods: list[MyDayPeriod] = []
    homework_pending: list[HomeworkPending]
    # V1-7 `S-145`: when the school has locked today (or some of its periods),
    # those period cards are GONE from `periods` — not sitting there red. The
    # teacher is told why instead, in one line she is asked nothing about.
    # `S-132`: this is the one thing on My Day that gives without asking.
    day_closed: bool = False
    locked_periods: list[int] = []
    lock_reason: str | None = None
    # D-41/D-43: the narrow task window BELOW the periods — rail follow-ups from
    # the last 3 working days ∪ due today, tickable in place, capped at 5.
    tasks: list[TaskOut] = []
    # The window is never silent: "n older tasks →" links to /tasks (D-43).
    older_task_count: int = 0


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
    # The same thing for several children at once (founder, 2026-08-05) — one
    # assignment row EACH, not a shared row with a list on it, so every existing
    # reader (the check sheet, the parent portal, the streak) keeps working
    # unchanged and a child's history stays one row per piece of work.
    student_ids: list[uuid.UUID] = []


class HomeworkOut(BaseModel):
    id: uuid.UUID
    class_subject_id: uuid.UUID
    date: date
    text: str
    due_date: date | None
    student_id: uuid.UUID | None = None
    notified_count: int  # guardians notified (the teacher's payback, P3)
    # Every assignment this call wrote. One entry for the class-wide and
    # single-student cases; one per child when `student_ids` named several.
    # `id` above is the first of them — the whole batch is here, so a caller
    # never has to infer how many rows it just created.
    created_ids: list[uuid.UUID] = []


# ── the log books (founder, 2026-08-05) ──────────────────────────────────────
# Two register-shaped reads over capture that already exists. Neither adds a
# table: the class log is `lesson_logs` (+ the per-student lines that live as
# `lesson_observations` of kind `log`), and the homework log is
# `homework_assignments` with its check state.
class ClassLogEntryOut(BaseModel):
    """One line of the class log book.

    `kind` is the whole reason both shapes share a list: `class` is what the
    class was taught and is what the syllabus board counts; `student` is a line
    a teacher wrote about ONE child and counts towards nothing. Rendering them
    together is right — it is one register — but a screen must be able to tell
    them apart, and so must anyone reading the coverage figure beside it.
    """

    id: uuid.UUID
    kind: str  # class | student
    date: date
    topic_id: uuid.UUID | None = None
    topic_title: str | None = None
    unit_title: str | None = None
    # What the teacher actually wrote when there was no syllabus topic to pick.
    title: str | None = None
    coverage: str | None = None  # full | partial — class entries only
    note: str | None = None
    teacher_name: str | None = None
    period_no: int | None = None
    student_id: uuid.UUID | None = None
    student_name: str | None = None


class ClassLogBookOut(BaseModel):
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_name: str
    since: date
    until: date
    entries: list[ClassLogEntryOut] = []
    can_write: bool = False


class ClassLogIn(BaseModel):
    """One class log entry, for the whole class or for named children.

    `student_ids` empty = the class was taught this, which is a `lesson_logs`
    row and moves the syllabus. `student_ids` set = a line about those children
    only, which moves nothing — a lesson that reached three children is not
    coverage, and recording it as one would inflate every pace figure in the
    school.
    """

    class_subject_id: uuid.UUID
    date: Date | None = None
    topic_id: uuid.UUID | None = None
    # Free text for a school that doesn't track the syllabus topic by topic, or
    # a period that wasn't on the plan. Required when no topic is picked.
    title: str | None = Field(default=None, max_length=200)
    coverage: str = Field(default="full", pattern="^(full|partial)$")
    note: str | None = Field(default=None, max_length=500)
    student_ids: list[uuid.UUID] = []


class HomeworkLogEntryOut(BaseModel):
    """One homework, and what is known about how it went.

    `checked` false means nobody has gone through it, and `completion` is then
    None — never 0%. That is HW-1's load-bearing rule: a teacher who checks
    nothing must never read as a class with perfect completion, and the absence
    of a check may never render as a child's miss.
    """

    id: uuid.UUID
    date: date
    due_date: date | None = None
    text: str
    student_id: uuid.UUID | None = None
    student_name: str | None = None
    checked: bool = False
    checked_at: datetime | None = None
    checked_by: str | None = None
    roster: int = 0
    completion: float | None = None
    not_done: int = 0
    partial: int = 0
    late: int = 0
    carried: int = 0
    waived: int = 0


class HomeworkBookOut(BaseModel):
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_name: str
    since: date
    until: date
    entries: list[HomeworkLogEntryOut] = []
    can_write: bool = False


class HomeworkResultIn(BaseModel):
    """One student whose homework was NOT done-on-time. Done has no row.

    `late`, `carried` and `waived` joined the vocabulary in V1-5 — see
    `core/homework_verdict.py` for what each is worth. `late` is a status the
    teacher sets whenever she likes, with no threshold and nothing locking
    (`D-85`); `carried` is an absence, not a refusal (`D-34`); `waived` is how a
    carried item stops being pending (`S-98`).
    """

    student_id: uuid.UUID
    status: str = Field(default="not_done",
                        pattern="^(not_done|partial|late|carried|waived)$")
    note: str | None = Field(default=None, max_length=300)


class HomeworkCheckIn(BaseModel):
    """"Everyone did it ✓" = an empty `results` list (HW-1).

    Full replace, like attendance: submitting again is the corrected truth, not
    an addition, so a teacher can reopen the sheet and fix a mis-tap.
    """

    results: list[HomeworkResultIn] = []


class HomeworkSheetRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    # See core/homework_verdict.py. `done` is the derived default (no row).
    status: str = "done"
    note: str | None = None
    # S-85: this child was absent the day it was set. Shown, and **not**
    # preselected as a miss — the teacher may know a friend passed it on, and a
    # hard exclusion cannot be overridden. Absent is not a refusal.
    absent_when_set: bool = False
    # S-97: items still carried from while they were away. She is already
    # holding these notebooks; nothing new to remember.
    carried_pending: int = 0
    # S-89: the intervention, at the moment she is standing in front of the
    # child holding the book — the cheapest intervention moment in the product,
    # and until now this number lived only on the principal's dashboard.
    miss_streak: int = 0


class HomeworkSheetOut(BaseModel):
    """The capture sheet for one homework: its roster, pre-loaded with whatever
    was recorded last time."""

    assignment_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    text: str
    date: date
    due_date: date | None = None
    # False = never checked. NOT the same as "everybody did it" — the whole
    # reason the check row exists.
    checked: bool = False
    checked_at: datetime | None = None
    checked_by: str | None = None
    # A per-student assignment has a one-row sheet: only its target.
    student_id: uuid.UUID | None = None
    roster: list[HomeworkSheetRow] = []
    done_count: int = 0
    not_done_count: int = 0
    partial_count: int = 0
    late_count: int = 0
    carried_count: int = 0
    waived_count: int = 0


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
