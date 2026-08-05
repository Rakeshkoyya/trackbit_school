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
    """The capture sheet. `period_no` is the period the register ACTUALLY sits
    on, which in a once-per-day school is not necessarily the one that was asked
    for — the sheet opens on the day's register wherever it was taken, and the
    write lands there too."""
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


# ── the teacher's own attendance board (founder, 2026-08-05) ─────────────────
# Attendance was reachable only from a My Day period card, so a teacher who was
# not standing in front of the class at that moment had no way to open it — and
# the school's rule is the opposite of that: **the class teacher takes it at
# period one, and if she is away ANY teacher of the class can.** A register that
# only one person can open is a register that does not get taken on the days it
# matters most.
#
# `assert_can_take_class` already permitted exactly this set (subject teacher,
# substitute, admin). What was missing was the screen.

class MyAttendanceClass(BaseModel):
    """One class this teacher may open, and where its register stands today.

    `roster` is the class's strength and is populated whether or not anything is
    marked — the rule the admin board and My Class were both corrected to on the
    same day. `marked=False` with `present=0` is a register nobody opened, not
    an empty classroom, and the UI must render the word rather than the zero.
    """

    class_id: uuid.UUID
    class_label: str
    roster: int = 0
    is_class_teacher: bool = False
    # Which of this class's subjects this teacher takes — the one the mark will
    # be filed against. Empty for a class teacher who takes none of them, which
    # is legitimate and must not stop her marking the roll.
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None

    marked: bool = False
    marked_period_no: int | None = None
    marked_by_name: str | None = None
    marked_at: datetime | None = None
    periods_marked: int = 0

    present: int = 0
    absent: int = 0
    late: int = 0
    pct: float | None = None
    absentee_names: list[str] = []

    # The two facts the screen keys its buttons off. `can_mark` is about
    # PERMISSION, `first_of_day` about whether this would be the day's opening
    # register — the one that fires the guardian alerts.
    can_mark: bool = True
    first_of_day: bool = True
    # The suggested period to open: the first one this teacher has in front of
    # this class today, else period 1. A suggestion, never a restriction.
    suggested_period_no: int = 1
    headline: str = ""
    tone: str = "neutral"


class MyAttendanceOut(BaseModel):
    date: date
    is_today: bool = True
    school_open: bool = True
    # The school's mode, so the screen knows whether it is showing a DAY's
    # register or a period's. `once_per_day` is the one the UI branches on:
    # it hides the period picker (the register is the day's, so choosing a
    # period is a question with no meaning) and words the buttons accordingly.
    mode: str = "every_period"
    once_per_day: bool = False
    classes: list[MyAttendanceClass] = []
    headline: str = ""
