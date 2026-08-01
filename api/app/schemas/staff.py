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
    present: bool
    # An approved leave covers this date — the sheet opens with them already
    # unchecked and says why, so the admin isn't retyping what they approved.
    on_leave: bool = False
    leave_reason: str | None = None
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


class StaffAttendanceIn(BaseModel):
    """Full replace of the day's absence set — "everyone in" is an empty list.

    Idempotent, so the admin can reopen a day and correct it with no undo
    machinery (the same contract as AttendanceService.mark).
    """
    date: Date | None = None
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


class TimesheetDay(BaseModel):
    date: date
    weekday: int
    is_working_day: bool
    slots: list[TimesheetSlot]
    teaching_count: int
    work_count: int
    free_count: int
    cover_count: int = 0


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
    # org_day rows only: why this person is away today (S-72). None = in.
    away_reason: str | None = None


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
    approved_days: int
    pending_days: int
    remaining: int


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
    days: int
    reason: str
    status: str
    created_at: datetime
    # Set when the application breaks the school's own policy. Advisory: the
    # request still reaches the admin, flagged, because an emergency is a human
    # decision and not a validation error.
    warnings: list[str] = []
    events: list[LeaveEventOut] = []


class LeaveApplyIn(BaseModel):
    start_date: Date
    end_date: Date
    reason: str = Field(min_length=3, max_length=1000)


class LeaveDecisionIn(BaseModel):
    action: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)


class LeaveListOut(BaseModel):
    requests: list[LeaveRequestOut]
    pending_count: int
    policy: LeavePolicy
