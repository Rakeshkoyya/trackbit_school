"""The admin operating board (DASH3) — every module's read contract.

One rule runs through all of it: **a number that cannot be resolved to a name is
not on this board.** Each module returns the shape (school-level roll-ups a
chart can draw), the drill-down (class → subject → teacher/student), and the red
rows that carry an action. Nothing here is stored — every field is a computed
join over capture that already exists (P5).

Two states are kept distinct everywhere, because folding them together is how a
dashboard starts lying:

  * **not captured** vs **captured as zero** — an unmarked period is not a period
    with nobody present, and unchecked homework is not homework nobody did.
  * **unplanned / unallocated / unestimated** vs a RAG colour — hard-won in
    V2-P11, and they stay their own words here (DASH3 §4.2).
"""

import uuid
from datetime import date as date_
from datetime import datetime, time

from pydantic import BaseModel, Field

from app.schemas.dashboard import AttendancePulse
from app.schemas.homework import HomeworkOverview

# ─────────────────────────────────────────────────────────────────────────────
# M1 — Attendance
# ─────────────────────────────────────────────────────────────────────────────


class CaptureCell(BaseModel):
    """One class × period on today's capture heatmap.

    `state` separates the three things a blank cell could mean, which is the
    single most useful distinction on the tab: `free` (no lesson scheduled),
    `pending` (scheduled, not marked yet), `marked`, `not_held` (the teacher
    said the class did not happen — captured, not missing).
    """
    period_no: int
    # free | pending | marked | not_held | not_expected — the last is V1-3
    # (D-01): scheduled, but the org's mode doesn't mark this period; neutral,
    # out of the denominator.
    state: str
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    absent: int = 0
    late: int = 0


class CaptureRow(BaseModel):
    class_id: uuid.UUID
    class_label: str
    roster: int
    cells: list[CaptureCell]
    marked: int
    expected: int


class PeriodCaptureGrid(BaseModel):
    date: date_
    periods_per_day: int
    period_times: list[dict] = []
    rows: list[CaptureRow] = []
    marked: int = 0
    expected: int = 0
    # V1-3 (D-01): what the denominator means — every_period | first_period |
    # twice_daily. The UI states it beside the count.
    mode: str = "every_period"


class StaffAbsentee(BaseModel):
    member_id: uuid.UUID
    name: str
    role: str
    on_leave: bool = False
    reason: str | None = None
    periods_due: int = 0            # periods they were on the timetable for today
    periods_covered: int = 0        # of those, how many have a live substitute


class StaffPresence(BaseModel):
    """`marked=False` is information, not a failure — nobody has taken staff
    attendance yet, which is different from a full house."""
    date: date_
    marked: bool
    total: int
    present: int
    absent: int
    on_leave: int
    absentees: list[StaffAbsentee] = []


class AttendanceBoard(BaseModel):
    date: date_
    students: AttendancePulse
    capture: PeriodCaptureGrid
    staff: StaffPresence
    streak_count: int = 0           # students already at the red-list threshold


class AbsenceStreak(BaseModel):
    """A student absent for every marked period of N consecutive SCHOOL days.

    Absent in some but not all marked periods is `partial` (came late, left
    early) and never counts toward a streak — the same rule `services/timeline.py`
    and the parent portal use, so the two surfaces can never disagree.
    """
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    streak: int
    last_present: date_ | None = None
    days_partial: int = 0
    guardian_count: int = 0
    class_teacher_member_id: uuid.UUID | None = None
    class_teacher_name: str | None = None
    reminded_today: bool = False
    followup_assigned_today: bool = False


class StreakBoard(BaseModel):
    as_of: date_
    min_days: int
    window_days: int
    rows: list[AbsenceStreak] = []


# ── V1-3: the admin tab as questions (S-08, D-02/D-86) ───────────────────────
class CallRow(AbsenceStreak):
    """One "needs a call" row. `status` answers "has anybody dealt with this?"
    (D-86): explained = a reason is on record (amber) · unexplained = nobody has
    explained this (red, sorts first). Colour is a RENDERING of this status —
    never logic in a component (S-22)."""

    status: str = "unexplained"  # explained | unexplained
    reason_code: str | None = None
    reason_note: str | None = None


class DriftRow(BaseModel):
    """S-07: the slow fade the red list can't see — attendance below the org's
    threshold over the window, denominated on the class's MARKED days."""

    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_label: str | None = None
    present_days: int
    marked_days: int
    pct: float


class LateRow(BaseModel):
    """S-06: chronic lateness — an admin row, never a parent message."""

    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    late_days: int
    window_days: int


class LeftRow(BaseModel):
    """Q-03/S-05: present this morning, absent after lunch — today."""

    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None


class CallBoard(BaseModel):
    """The attendance tab's questions, in the order the admin asks them:
    who needs a call · who is drifting · who is chronically late · who left
    after lunch. The heatmap ("is the record even complete?") and the charts
    stay on the existing board read."""

    date: date_
    roster_considered: int = 0  # students in classes that marked anything today
    present_today: int = 0
    min_attendance_pct: int = 75
    mode: str = "every_period"
    needs_call: list[CallRow] = []
    drifting: list[DriftRow] = []
    chronic_late: list[LateRow] = []
    left_after_lunch: list[LeftRow] = []


class SubstituteCandidate(BaseModel):
    member_id: uuid.UUID
    name: str
    reason: str                     # why they are ranked where they are
    rank: int
    teaches_subject_elsewhere: bool = False
    teaches_this_class: bool = False
    teaching_periods_today: int = 0
    # S-74: what they recorded for that period, if anything — shown, never a
    # block. "Free" and "free but marking Class 10 scripts" are different offers.
    work_label: str | None = None


class ImpactPeriod(BaseModel):
    period_no: int
    start: str | None = None
    end: str | None = None
    class_id: uuid.UUID
    class_label: str
    class_subject_id: uuid.UUID
    subject_name: str | None = None
    substitution_id: uuid.UUID | None = None
    covered_by_member_id: uuid.UUID | None = None
    covered_by_name: str | None = None
    candidates: list[SubstituteCandidate] = []


class ImpactTask(BaseModel):
    task_id: uuid.UUID
    title: str
    board_name: str | None = None
    due_at: datetime | None = None
    is_critical: bool = False
    days_overdue: int = 0


class StaffImpact(BaseModel):
    """What one absent member's day breaks. Teachers lose periods; an absent
    admin loses tasks — both are listed, because both have an action."""
    member_id: uuid.UUID
    name: str
    role: str
    date: date_
    on_leave: bool = False
    reason: str | None = None
    periods: list[ImpactPeriod] = []
    tasks: list[ImpactTask] = []


# ─────────────────────────────────────────────────────────────────────────────
# M2 — Syllabus
# ─────────────────────────────────────────────────────────────────────────────


class SyllabusRow(BaseModel):
    """One class-subject against its plan. `status` carries the V2-P11 words —
    green/amber/red are pace, but `unplanned`/`unallocated`/`none` are states,
    never a colour."""
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID | None = None
    subject_name: str
    teacher_member_id: uuid.UUID | None = None
    teacher_name: str | None = None
    status: str
    total_topics: int = 0
    planned_topics: int = 0
    taught_topics: float = 0        # partial coverage counts half
    coverage_pct: float | None = None
    weeks_behind: int = 0
    baseline_finish: date_ | None = None
    projected_finish: date_ | None = None
    unestimated_topics: int = 0
    current_term_unplanned: bool = False
    # Lesson logs recorded for this class-subject — the sample size behind any
    # ranking, shown so a rank can always be checked against how much it rests on.
    logged_periods: int = 0


class SyllabusNode(BaseModel):
    """A scope roll-up — a class, a subject, or a teacher.

    `rank_eligible` is the honesty guard (DASH3 §4.2): below the minimum sample a
    node reads "not enough data yet" and is never ranked. `score` exists only to
    order the eligible ones.
    """
    key: str
    id: uuid.UUID | None = None
    label: str
    sublabel: str | None = None
    class_subjects: int = 0
    on_track: int = 0
    slipping: int = 0
    behind: int = 0
    unplanned: int = 0
    unallocated: int = 0
    planned_topics: int = 0
    taught_topics: float = 0
    coverage_pct: float | None = None
    weeks_behind_max: int = 0
    unestimated_topics: int = 0
    logged_periods: int = 0
    rank_eligible: bool = False
    score: float | None = None


class ExamCheckpointSubject(BaseModel):
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str
    verdict: str                    # short | tight | fits | surplus | no_portion | unallocated
    required_periods: int = 0
    capacity_periods: float = 0
    unsized_topics: int = 0


class ExamCheckpoint(BaseModel):
    exam_event_id: uuid.UUID
    title: str
    start_date: date_
    end_date: date_
    days_to_exam: int
    teaching_days_in_gap: int = 0
    short: int = 0
    tight: int = 0
    ok: int = 0
    subjects: list[ExamCheckpointSubject] = []


class SyllabusBoard(BaseModel):
    scope: str                      # school | class | subject | teacher
    checkpoint: str                 # year | term | exam
    as_of: date_
    academic_year_id: uuid.UUID | None = None
    term_id: uuid.UUID | None = None
    term_label: str | None = None
    school: SyllabusNode | None = None
    nodes: list[SyllabusNode] = []
    rows: list[SyllabusRow] = []
    exams: list[ExamCheckpoint] = []
    ahead: list[SyllabusNode] = []
    needs_support: list[SyllabusNode] = []
    min_class_subjects: int = 3
    min_logged_periods: int = 10


# ─────────────────────────────────────────────────────────────────────────────
# M3 — Staff load
# ─────────────────────────────────────────────────────────────────────────────


class NowPerson(BaseModel):
    member_id: uuid.UUID
    name: str
    role: str
    class_label: str | None = None
    subject_name: str | None = None
    work_type: str | None = None
    work_label: str | None = None
    note: str | None = None
    open_tasks: int = 0
    substituting: bool = False
    reason: str | None = None


class NowBoard(BaseModel):
    """The live period board. `phase` degrades honestly: `before`/`after` school,
    `break` between periods, `unset` when the school never entered its timings."""
    now: time
    date: date_
    phase: str                      # before | period | break | after | unset | holiday
    period_no: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    teaching: list[NowPerson] = []
    working: list[NowPerson] = []
    free: list[NowPerson] = []
    absent: list[NowPerson] = []
    staff_marked: bool = False


class WorkBucket(BaseModel):
    key: str
    label: str
    periods: int


class LoadStripCell(BaseModel):
    period_no: int
    kind: str                       # class | work | free | absent | substituting
    label: str | None = None


class TeacherLoad(BaseModel):
    member_id: uuid.UUID
    name: str
    role: str
    teaching_periods: int = 0
    work_periods: int = 0
    free_periods: int = 0
    delta_vs_mean: float = 0
    load_flag: str = "balanced"     # over | under | balanced
    open_tasks: int = 0
    today: list[LoadStripCell] = []


class WorkloadWeek(BaseModel):
    week_start: date_
    date: date_
    working_weekdays: list[int] = []
    periods_per_day: int = 8
    mean_teaching: float = 0
    teachers: list[TeacherLoad] = []
    buckets: list[WorkBucket] = []
    unfilled_free_periods: int = 0  # free periods today with no timesheet entry


class LeaveQueueRow(BaseModel):
    """A pending application as the admin needs to weigh it: the request, plus
    the policy warnings SF-1 attaches (over-policy is flagged, never blocked)."""
    request_id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    start_date: date_
    end_date: date_
    days: int
    reason: str
    warnings: list[str] = []
    created_at: datetime


class LeavePulse(BaseModel):
    pending: int = 0
    on_leave_today: int = 0
    approved_days_this_month: int = 0
    allowed_per_year: int = 0
    allowed_per_month: int = 0
    queue: list[LeaveQueueRow] = []


class StaffBoard(BaseModel):
    """The people tab (DASH3 §4.3, revision 2). Presence, leave, live period
    board and load in one payload — the operational screens under `/staff` stay
    where they are and this links to them."""
    date: date_
    presence: StaffPresence
    leave: LeavePulse
    now: NowBoard
    week: WorkloadWeek
    uncovered_periods: int = 0      # periods today whose teacher is away, no cover


# ─────────────────────────────────────────────────────────────────────────────
# M4 — Homework
# ─────────────────────────────────────────────────────────────────────────────


class HomeworkDay(BaseModel):
    date: date_
    assigned: int
    checked: int
    expected: int
    done: int
    completion: float | None = None


class HomeworkBoard(BaseModel):
    overview: HomeworkOverview
    daily: list[HomeworkDay] = []


# ─────────────────────────────────────────────────────────────────────────────
# M5 — Tasks + daily duties
# ─────────────────────────────────────────────────────────────────────────────


class TaskScopeRow(BaseModel):
    key: str
    id: uuid.UUID | None = None
    label: str
    open: int = 0
    overdue: int = 0
    completed: int = 0
    completion: float | None = None


class TaskRedRow(BaseModel):
    task_id: uuid.UUID
    title: str
    board_id: uuid.UUID
    board_name: str
    assignee_user_id: uuid.UUID | None = None
    assignee_name: str | None = None
    due_at: datetime | None = None
    days_overdue: int = 0
    is_critical: bool = False


class TaskDayPoint(BaseModel):
    date: date_
    completed: int
    created: int


class DutyRow(BaseModel):
    """A teacher's daily classroom duties, denominated by the periods they were
    actually due to teach — a teacher whose classes were all cancelled cannot
    read as 0%."""
    member_id: uuid.UUID
    name: str
    due_periods: int = 0
    attendance_marked: int = 0
    logged: int = 0
    homework_set: int = 0
    checks_confirmed: int = 0
    completion: float | None = None


class TaskBoardOut(BaseModel):
    date: date_
    window_days: int
    open: int = 0
    overdue: int = 0
    completed_window: int = 0
    critical_overdue: int = 0
    unassigned: int = 0
    daily: list[TaskDayPoint] = []
    by_board: list[TaskScopeRow] = []
    by_assignee: list[TaskScopeRow] = []
    red_rows: list[TaskRedRow] = []
    duties: list[DutyRow] = []
    duty_completion: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# M6 — Exams
# ─────────────────────────────────────────────────────────────────────────────


class ExamRollup(BaseModel):
    cycle_id: uuid.UUID
    name: str
    type: str
    date: date_
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    avg_pct: float | None = None
    scored: int = 0
    roster: int = 0
    participation: float | None = None


class ExamScopeRow(BaseModel):
    key: str
    id: uuid.UUID | None = None
    label: str
    exams: int = 0
    scored: int = 0
    avg_pct: float | None = None


class ExamTrendPoint(BaseModel):
    label: str
    date: date_
    avg_pct: float


class ExamTrend(BaseModel):
    key: str
    label: str
    points: list[ExamTrendPoint] = []


class ExamBand(BaseModel):
    label: str
    count: int


class ExamsBoard(BaseModel):
    as_of: date_
    academic_year_id: uuid.UUID | None = None
    types: list[str] = []
    type_filter: str | None = None
    exams: int = 0
    scored: int = 0
    avg_pct: float | None = None
    recent: list[ExamRollup] = []
    by_class: list[ExamScopeRow] = []
    by_subject: list[ExamScopeRow] = []
    trends: list[ExamTrend] = []
    distribution: list[ExamBand] = []


# ─────────────────────────────────────────────────────────────────────────────
# The action rail (DASH3 §5)
# ─────────────────────────────────────────────────────────────────────────────


class SubstitutionIn(BaseModel):
    date: date_
    class_id: uuid.UUID
    period_no: int = Field(ge=1)
    class_subject_id: uuid.UUID
    substitute_member_id: uuid.UUID
    absent_member_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class SubstitutionOut(BaseModel):
    id: uuid.UUID
    date: date_
    class_id: uuid.UUID
    class_label: str | None = None
    period_no: int
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    absent_member_id: uuid.UUID | None = None
    absent_name: str | None = None
    substitute_member_id: uuid.UUID
    substitute_name: str | None = None
    note: str | None = None
    cancelled_at: datetime | None = None


class ActionIn(BaseModel):
    """One request model for every rail button — each `kind` reads the fields it
    needs and the service validates them, so the frontend has one call to make."""
    student_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    board_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None
    substitution: SubstitutionIn | None = None


class ActionOut(BaseModel):
    kind: str
    ok: bool
    message: str
    subject_type: str | None = None
    subject_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    substitution: SubstitutionOut | None = None
    already_done: bool = False


class FollowupRow(BaseModel):
    id: int
    kind: str
    subject_type: str
    subject_id: uuid.UUID | None = None
    actor_name: str | None = None
    target_name: str | None = None
    detail: dict | None = None
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# The overview
# ─────────────────────────────────────────────────────────────────────────────
#
# The overview used to be six one-number tiles. A tile could say "78%" and be
# read in a second, but it could not say *what* was 78% or *who* — so the admin
# opened a tab to find out, every single morning, for every single module.
#
# It is now one block per module, each carrying the two or three figures that
# together mean something, plus NAMED specifics underneath. The tab is still
# where the work happens; the overview's job is to make opening one a decision
# rather than a search.


class OverviewMetric(BaseModel):
    """One figure inside a section. Two or three of these, never more — the
    overview is a summary and a fourth number always turns it into a table."""
    key: str
    label: str
    value: str
    sub: str | None = None
    tone: str = "neutral"           # neutral | green | amber | red
    href: str | None = None
    # The shape behind the number, when the module already computes a series.
    # Never a second axis, never a second figure — just the trajectory.
    spark: list[float | None] = []


class OverviewNote(BaseModel):
    """A named specific — the board's rule (DASH3), enforced here too: a number
    that cannot be resolved to a name does not belong on this page. "3 uncovered
    periods" sends you looking; "Priya away — 3 periods, none covered" does not.
    """
    text: str
    tone: str = "neutral"
    href: str | None = None


class OverviewSection(BaseModel):
    key: str
    label: str
    href: str                       # the tab that owns this module
    headline: str                   # the module in one plain sentence
    tone: str = "neutral"
    metrics: list[OverviewMetric] = []
    notes: list[OverviewNote] = []


class QuickAction(BaseModel):
    """Something waiting on the admin *right now*, with the screen that clears it.

    Derived, never configured: an action appears only while its condition holds,
    so an empty rail is a real "nothing is waiting" rather than a rail nobody
    wired up. These are deliberately not alerts — an alert describes the school,
    an action describes a thing this person has to do.
    """
    key: str
    label: str
    detail: str
    href: str
    tone: str = "neutral"
    count: int = 0


class OverviewBoard(BaseModel):
    date: date_
    # The school clock, so the page can head itself with the moment it describes
    # ("Period 4 · 11:20–12:00") instead of just a date. Degrades honestly —
    # before/after/break/holiday/unset, never an invented period.
    phase: str = "unset"
    period_no: int | None = None
    period_label: str | None = None
    sections: list[OverviewSection] = []
    actions: list[QuickAction] = []
