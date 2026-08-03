"""Staff presence, timesheet and leave schemas (SF-1)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# `date` is a field name throughout; alias the type so annotations stay valid.
Date = date


# ── staff attendance ─────────────────────────────────────────────────────────
class StaffRosterRow(BaseModel):
    member_id: uuid.UUID
    name: str
    role: str
    # Derived, never stored: True unless an absence row exists for this day.
    # A `late` member is present (D-04 counts days present; late is a flag).
    present: bool
    # present | absent | half_day | late (V1-4, D-04). `present` above stays as
    # the boolean every existing caller reads, so nothing had to be rewritten.
    status: str = "present"
    portion: str | None = None      # am | pm — which half a half_day was away
    # An approved leave covers this date — the sheet opens with them already
    # unchecked and says why, so the admin isn't retyping what they approved.
    on_leave: bool = False
    leave_reason: str | None = None
    # The whole span the leave covers — cover is arranged for all of it, not
    # just for the day somebody happens to be looking at (V1-14).
    leave_start: Date | None = None
    leave_end: Date | None = None
    note: str | None = None


class StaffAttendanceOut(BaseModel):
    date: date
    # False = nobody has taken attendance for this date yet. The difference
    # between "nobody was absent" and "nobody marked it".
    marked: bool
    marked_at: datetime | None = None
    marked_by: str | None = None
    roster: list[StaffRosterRow]
    total: int
    present_count: int
    absent_count: int
    half_day_count: int = 0
    late_count: int = 0
    # Days-present value of the day, half-days counted as 0.5 (D-04/D-78). The
    # month summary sums exactly this, so the two can never disagree.
    present_days: float = 0


class StaffMarkIn(BaseModel):
    """One deviation from a normal full day. Present people are never sent."""
    member_id: uuid.UUID
    status: str = Field(pattern="^(absent|half_day|late)$")
    portion: str | None = Field(default=None, pattern="^(am|pm)$")
    note: str | None = Field(default=None, max_length=500)


class StaffAttendanceIn(BaseModel):
    """Full replace of the day's exception set — "everyone in, on time" is empty.

    Idempotent, so the admin can reopen a day and correct it with no undo
    machinery (the same contract as AttendanceService.mark).

    `absent_member_ids` is the pre-V1-4 shorthand and still means "plain absent";
    it is merged with `marks`, which `marks` wins. Kept because the seed, Lucy
    and any script that only needs "these people were away" should not have to
    learn the richer shape to say the simple thing.
    """
    date: Date | None = None
    marks: list[StaffMarkIn] = []
    absent_member_ids: list[uuid.UUID] = []
    notes: dict[uuid.UUID, str] = {}


# ── timesheet ────────────────────────────────────────────────────────────────
class TimesheetSlot(BaseModel):
    period_no: int
    start: str
    end: str
    # 'class' = the timetable owns this period (locked) · 'cover' = a live
    # substitution puts them in a colleague's class (locked, Q-37) · 'work' =
    # the teacher recorded something · 'free' = nothing yet · 'away' = absent
    # or on approved leave that day (S-72 — never rendered as free).
    kind: str
    class_label: str | None = None
    subject_name: str | None = None
    work_type: str | None = None
    work_label: str | None = None
    note: str | None = None
    # S-75: what she has recorded in this slot before. The picker opens with it
    # highlighted and **writes nothing** — no row exists that a human did not
    # put there, which is the property D-23 removed any other way to guarantee.
    suggested_work_type: str | None = None
    suggested_work_label: str | None = None


class TimesheetBreak(BaseModel):
    """A non-teaching interval, for the day view's vertical timeline (D-18)."""
    after_period_no: int
    label: str
    start: str
    end: str


class TimesheetDay(BaseModel):
    date: date
    weekday: int
    is_working_day: bool
    slots: list[TimesheetSlot]
    teaching_count: int
    work_count: int
    free_count: int
    cover_count: int = 0
    breaks: list[TimesheetBreak] = []
    # Evening/hostel blocks she runs on this day (S-68) — reported BESIDE the
    # periods, never added into them, so the load mean stays comparable.
    evening_labels: list[str] = []


class TimesheetWeek(BaseModel):
    member_id: uuid.UUID
    member_name: str
    week_start: date
    days: list[TimesheetDay]
    # Totals across the week — the workload figure the dashboard will read.
    teaching_periods: int
    work_periods: int
    free_periods: int
    covered_periods: int = 0
    # S-68 — hostel evenings she runs this week. Counted separately for the same
    # reason: an evening is not a period and adding them would flatter one
    # person's load while distorting everyone's comparison.
    evening_sessions: int = 0
    # org_day rows only: why this person is away today (S-72). None = in.
    away_reason: str | None = None


class TimesheetMonthDay(BaseModel):
    """One cell in the month grid (D-18/S-64) — a day's SHAPE, not its detail.

    `state` carries the whole-day facts that outrank the period counts, so the
    grid never shows "gaps" on Diwali: working · off (non-working weekday) ·
    holiday · leave · away · future.
    """
    date: date
    weekday: int
    state: str
    teaching: int = 0
    work: int = 0
    cover: int = 0
    free: int = 0
    label: str | None = None        # holiday name, leave reason, …


class TimesheetMonth(BaseModel):
    member_id: uuid.UUID
    member_name: str
    month: str                      # YYYY-MM
    start_date: date
    end_date: date
    days: list[TimesheetMonthDay]
    teaching_periods: int = 0
    work_periods: int = 0
    covered_periods: int = 0
    evening_sessions: int = 0


# ── the month summary (D-78) ─────────────────────────────────────────────────
class StaffMonthRow(BaseModel):
    """One member's month. **No money anywhere on it** (D-78/D-25).

    `days_not_marked` is the load-bearing field: a day nobody took staff
    attendance on is NOT an absence (S-34). It is its own count, in its own
    word, and it is excluded from `days_present` and from the denominator's
    "accounted for" total. The moment this figure informs pay in v2, that
    distinction is the difference between a clerical gap and an unpaid day.
    """
    member_id: uuid.UUID
    name: str
    role: str
    working_days: int               # working days in the month, up to today
    days_marked: int                # of those, days attendance was taken
    days_not_marked: int
    days_present: float             # half-days count 0.5
    days_absent: float
    half_days: int
    lates: int
    leave_days: float               # approved leave days falling in the month
    leave_remaining: float          # from the same balance the leave screen shows


class StaffMonthOut(BaseModel):
    month: str                      # YYYY-MM
    start_date: date
    end_date: date                  # clamped to today — a month is not over yet
    working_days: int
    days_marked: int                # school-wide: days staff attendance was taken
    rows: list[StaffMonthRow] = []


class TimesheetEntryIn(BaseModel):
    date: Date
    period_no: int = Field(ge=1)
    work_type: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=500)
    # Admin filling in for someone else; teachers may only write their own.
    member_id: uuid.UUID | None = None


class WorkTypeOut(BaseModel):
    key: str
    label: str


# ── leave ────────────────────────────────────────────────────────────────────
class LeavePolicy(BaseModel):
    leaves_per_year: int = Field(ge=0, le=365)
    leaves_per_month: int = Field(ge=0, le=31)


class LeaveBalance(BaseModel):
    member_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    allowed_per_year: int
    allowed_per_month: int
    # Floats since V1-4 — a half-day is 0.5 of the allowance, not 0 and not 1.
    approved_days: float
    pending_days: float
    remaining: float


class LeaveEventOut(BaseModel):
    action: str
    actor_name: str | None = None
    note: str | None = None
    created_at: datetime


class LeaveRequestOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    start_date: date
    end_date: date
    days: float
    is_half_day: bool = False
    portion: str | None = None
    reason: str
    status: str
    created_at: datetime
    # Set when the application breaks the school's own policy. Advisory: the
    # request still reaches the admin, flagged, because an emergency is a human
    # decision and not a validation error.
    warnings: list[str] = []
    events: list[LeaveEventOut] = []
    # D-27: the working days this leave actually removes someone from, today
    # onwards. The admin who just pressed Approve gets "arrange cover for these
    # days" from the same response — the alternative is remembering on Friday
    # morning, which is the morning nobody has a spare minute.
    cover_dates: list[date] = []


class LeaveApplyIn(BaseModel):
    start_date: Date
    end_date: Date
    reason: str = Field(min_length=3, max_length=1000)
    # D-04 — half a day. Only meaningful on a single date; the service refuses a
    # multi-day half-day rather than silently halving a week.
    is_half_day: bool = False
    portion: str | None = Field(default=None, pattern="^(am|pm)$")


class LeaveDecisionIn(BaseModel):
    action: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)


class LeaveListOut(BaseModel):
    requests: list[LeaveRequestOut]
    pending_count: int
    policy: LeavePolicy
