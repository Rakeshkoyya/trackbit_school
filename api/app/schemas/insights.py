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
from app.schemas.homework import HomeworkDay, HomeworkOverview

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
    # The day this row describes, and — when it is an approved leave — the whole
    # span it covers. Cover is arranged for the absence, not for whichever day
    # the reader happens to be on (V1-14): a teacher away Mon–Wed leaves three
    # days of periods, and a sheet that only knew "today" hid two of them.
    date: date_ | None = None
    leave_start: date_ | None = None
    leave_end: date_ | None = None
    # absent | half_day (V1-4, D-04). `late` never reaches this list — a late
    # member is in, and offering to cover their periods would be nonsense.
    status: str = "absent"
    portion: str | None = None      # which half, when status is half_day
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
    # V1-14: the primary guardian, named and dialable. The row's whole purpose
    # is the call, and "2 guardians on file" is not a phone number.
    guardian_name: str | None = None
    guardian_phone: str | None = None
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
    # D-29/S-79(a): this cover can be a real lesson, not a study period — she
    # teaches the subject, so the class's next planned topic can move forward.
    can_teach_next_topic: bool = False
    # D-29/S-79(b): don't rob Peter to pay Paul. Named subjects where this
    # candidate is behind her own plan. A warning on the row, never a block.
    behind_note: str | None = None


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
    # What the class GAINS if the right person takes it (D-29): the next topic
    # the plan has scheduled and nobody has logged yet.
    next_topic: str | None = None
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

    # ── V1-6 ─────────────────────────────────────────────────────────────────
    # `S-51`: both denominators, side by side, because they answer different
    # questions. `coverage_pct` above stays coverage of the PLAN ("are we on
    # pace?"); this is coverage of the whole portion ("will we finish?") and is
    # the only one a parent may ever see, because it cannot go down (`S-54`).
    syllabus_pct: float | None = None
    syllabus_taught: float = 0

    # `S-45`/`S-41`: pace a person can check by hand. Topics whose planned week
    # has arrived, and how many of them are still untaught. This — not a
    # composite score — is what "behind" means on this board now.
    due_topics: int = 0
    taught_due: float = 0
    behind_topics: float = 0

    # ── V1-15 ────────────────────────────────────────────────────────────────
    # The portion split into the states a person can act on. `taught_topics`
    # above is WEIGHTED, and a weighted figure cannot be taken back apart —
    # 12.5 is 12 finished plus one half-done or 11 finished plus three. The
    # board draws the split, so the split is computed once, here.
    taught_full: int = 0
    taught_partial: int = 0
    # Where the approved plan said this class-subject would be by today, as a
    # share of the planned portion. The marker on every bar and ring: the arc
    # is where teaching actually is, the marker is where it was meant to be.
    # Computed server-side because a percentage divided in the browser is
    # exactly the drift `S-51` exists to remove.
    expected_pct: float | None = None
    # The same marker on the OTHER denominator (`S-51` again: both bases, each
    # naming itself). A marker may only ever be drawn against a figure sharing
    # its denominator, so the pair travels together and a screen picks the one
    # matching the arc it is drawing.
    expected_syllabus_pct: float | None = None
    # `D-89`: will it finish? The plan has always carried both dates and no
    # screen has ever rendered either. Positive = running late against its own
    # baseline; `overruns_year` = the projection lands past the year's end,
    # which is the only version of "late" a parent would ever notice.
    overrun_days: int | None = None
    overruns_year: bool = False

    # `S-41`: *why*. One of never_sized · not_logged · periods_lost · slower,
    # with the sentence that makes it a different conversation. Absent when the
    # row is not behind — a green row needs no excuse.
    cause: str | None = None
    cause_detail: str | None = None
    periods_not_held: int = 0

    # `S-46`: what to teach next, so the board and her own screen agree.
    next_topic_title: str | None = None
    next_chapter_title: str | None = None

    # `D-16`/`S-60`: a catch-up plan was asked for. The row clears on the
    # recorded OUTCOME, never on the press — so this stays set while the task is
    # open and carries the outcome once the meeting has happened.
    catchup_task_id: uuid.UUID | None = None
    catchup_requested_on: date_ | None = None
    catchup_outcome: str | None = None


class SyllabusTrendPoint(BaseModel):
    """One week of `S-40`'s coverage-over-time chart.

    `actual` is cumulative taught weight; `baseline` is the cumulative topics
    the approved plan had scheduled by that week. The gap between the two lines
    IS the story — a widening band is slipping, a closing one is catching up —
    which no snapshot on this board could show.
    """
    week_start: date_
    actual: float = 0
    baseline: int = 0


class SectionCompareRow(BaseModel):
    class_subject_id: uuid.UUID
    class_label: str
    teacher_name: str | None = None
    status: str
    coverage_pct: float | None = None
    taught_topics: float = 0
    planned_topics: int = 0
    behind_topics: float = 0


class SectionCompare(BaseModel):
    """`S-43` — 6-A Maths against 6-B Maths.

    The fairest comparison in a school: same syllabus, same weeks, same exam,
    different teacher. Only emitted where a grade genuinely has more than one
    section teaching that subject, and it carries the same honesty guard as
    everything else here — a section with no logs is `unknown` and is not the
    one "behind".
    """
    grade: str
    subject_name: str
    spread_pct: float | None = None     # best minus worst, in points
    rows: list[SectionCompareRow] = []


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
    # `S-42`: has a plan, but nobody has logged a lesson against it. Counted
    # apart from every RAG bucket and apart from `unplanned`, because "we don't
    # know" is a third thing and folding it into either one loses the finding.
    unknown: int = 0
    planned_topics: int = 0
    taught_topics: float = 0
    coverage_pct: float | None = None
    total_topics: int = 0
    syllabus_pct: float | None = None
    weeks_behind_max: int = 0
    unestimated_topics: int = 0
    logged_periods: int = 0
    rank_eligible: bool = False
    score: float | None = None
    # `S-45`: the sentence the ordering rests on — *"3 of 4 on track · 68%
    # covered"*. A rank that cannot be explained to the person it is about has
    # no business being on the screen, and `score` alone could not be
    # reconstructed by anybody who read it.
    rank_reason: str | None = None

    # ── V1-15 ────────────────────────────────────────────────────────────────
    # Everything a node needs to be DRAWN, decided here rather than by whichever
    # screen happens to be drawing it. Three surfaces render these nodes now —
    # the overview block, the scope ledger and the teacher matrix — and a tone
    # each of them derived for itself would be three different verdicts about
    # one teacher on one morning.
    due_topics: int = 0
    taught_due: float = 0
    behind_topics: float = 0
    taught_full: int = 0
    taught_partial: int = 0
    # The complement, carried rather than subtracted. The portion meter draws
    # three disjoint states and a component that worked the third one out for
    # itself would be one refactor away from subtracting a WEIGHTED figure from
    # a count of topics — which reads fine and is nonsense.
    untaught_topics: int = 0
    periods_not_held: int = 0
    # The plan's own marker, on each denominator — see `SyllabusRow`. A marker
    # is only ever drawn against a figure that shares its denominator.
    expected_pct: float | None = None
    expected_syllabus_pct: float | None = None
    tone: str = "neutral"           # neutral | green | amber | red
    # The status in words, because the tone is a colour and a colour alone is
    # never allowed to carry a verdict (dataviz; the same rule the RAG chips
    # follow). Reads *"2 of 5 behind"* or *"nothing logged yet"*.
    pace_caption: str | None = None
    # The teacher pivot's own denominators (`D-90`) — "3 classes · 2 subjects"
    # is the load a pace figure has to be read against, and a node that only
    # knew its class-subject count could not say it.
    classes: int = 0
    subjects: int = 0


class CauseTally(BaseModel):
    """`S-41` counted. Four causes, four different conversations — and the
    proportions between them are the finding: a school where most behind rows
    say *nothing logged* has a capture problem, not a teaching one, and no
    amount of talking to teachers about pace will move it."""
    key: str                        # not_logged | periods_lost | never_sized | slower
    label: str
    detail: str
    count: int = 0
    behind_topics: float = 0


class TermOption(BaseModel):
    """A term the boards can be narrowed to. Served with the payload so the
    switcher never needs a second round-trip, and so `is_current` is decided
    against the school's own clock rather than the browser's."""
    id: uuid.UUID
    name: str
    start_date: date_
    end_date: date_
    is_current: bool = False


class SyllabusPulse(BaseModel):
    """The overview's syllabus block: one ring, two breakdowns, one term switch.

    A deliberately small read beside `SyllabusBoard` — the same `_rows` batch
    and the same `_node` roll-up, minus the exam checkpoints, the trend and the
    per-row detail that only the tab has room for. Its own endpoint because the
    term switcher re-fetches on every press and `/insights/overview` composes
    seven modules that have no business being recomputed to change one filter.
    """
    as_of: date_
    academic_year_id: uuid.UUID | None = None
    term_id: uuid.UUID | None = None
    term_label: str | None = None
    headline: str = ""
    school: SyllabusNode | None = None
    classes: list[SyllabusNode] = []
    subjects: list[SyllabusNode] = []
    terms: list[TermOption] = []


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

    # ── V1-6 ─────────────────────────────────────────────────────────────────
    # `S-50`: schools manage against exams, not against April-to-March, so the
    # nearest one leads the page whatever checkpoint is selected. Always
    # computed now (batched via `exam_fit_org`), not only on the exam tab.
    next_exam: ExamCheckpoint | None = None
    # The sentence the page opens with (rule 3). Composed here so the board and
    # the overview cannot describe the same day differently.
    headline: str | None = None
    trend: list[SyllabusTrendPoint] = []
    sections: list[SectionCompare] = []

    # ── V1-15 ────────────────────────────────────────────────────────────────
    # `S-41` rolled up. The board has named the cause on every behind row since
    # V1-6 and never counted them, so the shape of the problem — capture, or
    # calendar, or sizing, or teaching — could only be read by eye down a list.
    causes: list[CauseTally] = []
    # The terms the checkpoint switcher offers, and the year's own end date,
    # which is what makes a projected finish late rather than merely later.
    terms: list[TermOption] = []
    year_end_date: date_ | None = None


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
    # S-68: hostel/evening blocks she runs this week. Reported BESIDE teaching
    # periods and never folded into them — an evening is not a period, and the
    # mean would stop being comparable the moment they were added together.
    evening_sessions: int = 0
    delta_vs_mean: float = 0
    load_flag: str = "balanced"     # over | under | balanced
    open_tasks: int = 0
    today: list[LoadStripCell] = []


class SlackSlot(BaseModel):
    """One (weekday, period) on the slack profile (D-21/S-66).

    `free` legitimately means **free or unrecorded** — `D-23` decided an unfilled
    period is free, so there is no third state to draw. The screen says so once,
    in the hint, rather than pretending the number is only genuine slack.
    """
    weekday: int
    period_no: int
    teaching: int = 0
    working: int = 0                # recorded a piece of work
    free: int = 0


class SlackProfile(BaseModel):
    """When the whole staff could meet. Its job is finding slack, not surveillance."""
    week_start: date_
    teacher_count: int = 0          # people who teach at all — the denominator
    periods_per_day: int = 8
    working_weekdays: list[int] = []
    slots: list[SlackSlot] = []
    best_weekday: int | None = None
    best_period_no: int | None = None
    best_free: int = 0


class WorkloadWeek(BaseModel):
    week_start: date_
    date: date_
    working_weekdays: list[int] = []
    periods_per_day: int = 8
    mean_teaching: float = 0
    teachers: list[TeacherLoad] = []
    buckets: list[WorkBucket] = []
    # S-66 — the one genuinely new chart in the module.
    slack: SlackProfile | None = None


class LeaveQueueRow(BaseModel):
    """A pending application as the admin needs to weigh it: the request, plus
    the policy warnings SF-1 attaches (over-policy is flagged, never blocked)."""
    request_id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    start_date: date_
    end_date: date_
    days: float
    is_half_day: bool = False
    portion: str | None = None
    reason: str
    warnings: list[str] = []
    created_at: datetime
    # D-27: the days this leave still needs cover for (approved rows only), so
    # "Arrange cover" is a press away from the queue rather than a second visit.
    cover_dates: list[date_] = []


class UpcomingCover(BaseModel):
    """An approved future absence whose periods nobody has covered yet (S-81).

    The rail's job is to raise this *when the leave is approved*, not on the
    morning it starts — which is the morning nobody has a spare minute.
    """
    date: date_
    member_id: uuid.UUID
    member_name: str
    request_id: uuid.UUID | None = None
    periods_due: int = 0
    periods_covered: int = 0


class LeavePulse(BaseModel):
    pending: int = 0
    on_leave_today: int = 0
    approved_days_this_month: float = 0
    allowed_per_year: int = 0
    allowed_per_month: int = 0
    queue: list[LeaveQueueRow] = []
    upcoming: list[UpcomingCover] = []


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


# `HomeworkDay` now lives beside the rest of the homework vocabulary, in
# `schemas/homework.py`, because it is accumulated inside `overview()`'s single
# pass rather than by a second walk here. It is imported at the top of this
# file, so `schemas.insights.HomeworkDay` still resolves for existing importers.


class HomeworkBoard(BaseModel):
    # V1-12 (§7 rule 3): the sentence the tab opens with, composed server-side
    # like the syllabus board's — so this tab and the overview block can never
    # describe the same week differently.
    headline: str | None = None
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
    headline: str | None = None      # V1-12 §7
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
    # V1-8: the school's own word for the type (D-55) and the never-pool bucket
    # (S-114). `type_label` falls back to the system kind's label only where a
    # school has not named its own.
    type_label: str = ""
    scale: str = "minor"
    locked: bool = False
    date: date_
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    avg_pct: float | None = None
    scored: int = 0
    roster: int = 0
    participation: float | None = None


class ScaleFigure(BaseModel):
    """One never-pooled bucket, with its denominators attached (`S-114`/`S-118`).
    Returned even when empty — *"no major exams yet"* is information, and
    dropping the row is how a screen implies there were none."""
    scale: str                    # minor | major
    label: str                    # "Minor tests" / "Major exams"
    purpose: str                  # why the two are apart, in a sentence
    exams: int = 0
    scored: int = 0
    avg_pct: float | None = None


class ExamScopeRow(BaseModel):
    key: str
    id: uuid.UUID | None = None
    label: str
    exams: int = 0
    scored: int = 0
    # The average **within the board's basis scale** (never blended across the
    # two — `S-114`). The other bucket rides along beside it so the screen can
    # show both without a second request.
    avg_pct: float | None = None
    minor_pct: float | None = None
    minor_exams: int = 0
    major_pct: float | None = None
    major_exams: int = 0


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
    headline: str | None = None      # V1-12 §7
    as_of: date_
    academic_year_id: uuid.UUID | None = None
    types: list[str] = []
    type_filter: str | None = None
    exams: int = 0
    scored: int = 0
    # V1-8 (`S-114`, `Q-50`): **never a blended number.** `avg_pct` and every
    # row below are computed within `scale_basis` alone — the bucket the board
    # is currently reading — and `standing` / `trajectory` carry the two
    # separately so the screen can lead with a sentence that names which.
    avg_pct: float | None = None
    scale_filter: str | None = None      # what the caller asked for
    scale_basis: str = "minor"           # what the figures below are computed from
    standing: ScaleFigure | None = None  # major exams — where they stand
    trajectory: ScaleFigure | None = None  # minor tests — which way they're moving
    trend_scale: str = "minor"           # which bucket drew the trajectories
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
    # `D-16` — the class-subject a catch-up plan is being asked about.
    class_subject_id: uuid.UUID | None = None


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
    # How many named rows there were BEFORE the block kept its first few. A
    # block that silently shows three of eleven reads as "three things are
    # wrong"; carrying the total is what lets it say "+8 more" and stay honest
    # about what it dropped.
    notes_total: int = 0


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


# ── S-62 · reach (V1-11) ────────────────────────────────────────────────────
class ReachRow(BaseModel):
    """One family the school did not reach, with the number to ring.

    Named, not counted — the board's rule. `phone` is here because the whole
    point of the row is the call: without it the admin has a problem and no way
    to act on it."""
    student_id: uuid.UUID
    student_name: str
    guardian_name: str
    phone: str | None = None
    kind: str
    title: str
    reason: str          # the sentence shown to a human
    reason_code: str     # no_login | no_device | push_failed
    created_at: datetime


class ReachBoard(BaseModel):
    date: date_
    messages_sent: int = 0
    delivered: int = 0
    unreachable: int = 0
    # Kept apart from `unreachable` on purpose: a family that asked not to be
    # messaged is not a delivery failure and must never join a list the office
    # is told to clear.
    opted_out: int = 0
    summary: str = ""
    rows: list[ReachRow] = []


# ─────────────────────────────────────────────────────────────────────────────
# V1-14 — the presence panorama: three rings, three named blocks, one month
# ─────────────────────────────────────────────────────────────────────────────


class PresenceRing(BaseModel):
    """One of the three rings — students · teachers · admin staff.

    `pct` is `None` when nothing has been marked, and the UI paints that neutral
    with the word instead of a number. A ring at 0% and a ring nobody has filled
    in are opposite facts and must never share a colour.
    """
    key: str                      # students | teachers | admins
    label: str
    marked: bool
    present: int = 0
    absent: int = 0
    total: int = 0
    pct: float | None = None
    # The sentence under the ring, with its denominator — "428 of 470 in".
    caption: str = ""
    tone: str = "neutral"         # neutral | green | amber | red
    href: str = "/dashboard/attendance"


class PresenceRow(BaseModel):
    """A named person in one of the three blocks, with what can be done to them.

    `actions` are VERBS the rail already implements (`services/insights/actions.py`)
    — the UI maps each to a button, and `done` is what has already been fired
    today, so three admins looking at the same absent child in one morning do not
    send three messages.
    """
    id: uuid.UUID
    name: str
    subtitle: str = ""            # class · parent · class teacher · reason
    tone: str = "amber"
    href: str | None = None
    actions: list[str] = []       # remind_guardian | assign_followup | ...
    done: list[str] = []
    badge: str | None = None      # "4d", "6 periods", "3 tasks"


class PresenceGroup(BaseModel):
    """One block under the rings.

    The founder's rule, encoded server-side so every surface obeys it: **at or
    under `inline_limit` the people are NAMED with their actions right there;
    above it the block collapses to one sentence and a link.** Three names with
    a button beside each is a morning's work; fourteen is a screen nobody reads.
    """
    key: str                      # students | teachers | admins
    label: str
    headline: str
    tone: str = "neutral"
    count: int = 0
    inline_limit: int = 3
    inline: bool = True           # were the rows named, or is this the one-liner?
    rows: list[PresenceRow] = []
    href: str = "/dashboard/attendance"
    action_label: str = "Open"
    # A second fact the block carries beside its people — uncovered periods for
    # staff, pending work for admins. Empty when there is nothing to say.
    note: str | None = None
    note_href: str | None = None


class PresenceBoard(BaseModel):
    # The last day the school actually ran — not necessarily today. On a Sunday
    # or a holiday every list would come back empty, and an empty board reads as
    # "nobody was absent" rather than "the school was shut".
    date: date_
    is_today: bool = True
    rings: list[PresenceRing] = []
    groups: list[PresenceGroup] = []
    headline: str = ""
    # The roll: how many people are in the building, out of how many the school
    # marked. Summed HERE and not in a component, and summed only over the
    # cohorts that were actually marked — `roll_caption` says which, because a
    # total that quietly includes an unmarked cohort is the exact lie the three
    # separate denominators exist to prevent.
    in_building: int = 0
    roll: int = 0
    away: int = 0
    roll_caption: str = ""


# ── the month, for the tab's visual layer ────────────────────────────────────
class PresenceDay(BaseModel):
    """One day on a 30-day series. `marked=False` days are carried, not dropped,
    so a gap in the record is visible as a gap rather than closing up."""
    date: date_
    marked: bool = False
    present: int = 0
    absent: int = 0
    total: int = 0
    pct: float | None = None


class ClassMonthCell(BaseModel):
    date: date_
    # marked | unmarked | closed — three states, three renderings. `unmarked` is
    # never drawn as 100% present, which is the whole reason the cell exists.
    state: str = "unmarked"
    absent: int = 0
    roster: int = 0
    pct: float | None = None


class ClassMonthRow(BaseModel):
    class_id: uuid.UUID
    class_label: str
    roster: int = 0
    cells: list[ClassMonthCell] = []
    marked_days: int = 0
    absent_days: int = 0          # student-days absent across the window
    pct: float | None = None      # the class's own month average
    tone: str = "neutral"


class AbsenceProfile(BaseModel):
    """A student's month in one row — the table's "absent 4 times this month".

    `days_absent` is denominated on the days the student's class actually marked
    (`marked_days`), never on the calendar: a class that captured nothing for a
    week must not make every child in it look present.
    """
    student_id: uuid.UUID
    full_name: str
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    roll_no: str | None = None
    days_absent: int = 0
    marked_days: int = 0
    pct: float | None = None
    current_streak: int = 0
    absent_today: bool = False
    status: str = "unexplained"   # explained | unexplained (D-86)
    reason_code: str | None = None
    reason_note: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    class_teacher_name: str | None = None
    reminded_today: bool = False
    followup_assigned_today: bool = False
    # The one-line reading of the row — computed here so the table, the overview
    # and Lucy cannot describe the same child differently.
    summary: str = ""
    tone: str = "neutral"


class PresenceAnomaly(BaseModel):
    """Something in the month worth a second look, said as a sentence.

    Deliberately not a score: each row states the fact, the figure it rests on
    and where to go. Nothing here is a prediction.
    """
    key: str
    title: str
    detail: str
    tone: str = "neutral"
    href: str | None = None


class AdminWorkRow(BaseModel):
    """An admin and the work sitting on them — the third table.

    Present here too, not only when they are away: "who is carrying what" is the
    question, and it is answerable on a day nobody is absent.
    """
    member_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    present: bool = True
    on_leave: bool = False
    reason: str | None = None
    open_tasks: int = 0
    overdue: int = 0
    critical_overdue: int = 0
    due_today: int = 0
    rows: list[TaskRedRow] = []
    tone: str = "neutral"
    summary: str = ""


class PresenceMonth(BaseModel):
    """The whole visual + action layer of the attendance tab, in one read."""
    date: date_
    window_days: int = 30
    from_date: date_
    to_date: date_
    dates: list[date_] = []             # the working days in the window, in order
    students: list[PresenceDay] = []
    teachers: list[PresenceDay] = []
    admins: list[PresenceDay] = []
    classes: list[ClassMonthRow] = []
    profiles: list[AbsenceProfile] = []
    staff_absent: list[StaffAbsentee] = []
    admin_work: list[AdminWorkRow] = []
    anomalies: list[PresenceAnomaly] = []
    # Every admin who could receive a transferred task (D — the third table's
    # one write). Names only; the transfer itself is `task_reassigned`.
    admin_options: list[PresenceRow] = []
    headline: str = ""


# ── V1-16 · the day-book ─────────────────────────────────────────────────────
# The whole staff's day as one grid, plus the one person's record you reach by
# tapping a name. See `services/insights/daybook.py` for the rules.


class DaybookPeriod(BaseModel):
    """A column of the grid. `label` is set only on breaks."""
    period_no: int
    start: str = ""
    end: str = ""
    label: str | None = None


class DaybookCell(BaseModel):
    """One person, one period.

    `color` is resolved server-side and is one of: a category hex from
    `core/work_types.CATEGORY_COLORS`, `"slate"`, or the two structural tokens
    `"teaching"` / `"free"` that the client paints from its own theme. The client
    never decides what a category looks like — otherwise the grid, the ring and
    the settings swatch would each have their own idea.
    """
    period_no: int
    #: class | cover | work | free | away | **closed**.
    #: `closed` = a period nobody was asked to work (a holiday, a non-school day,
    #: a `day_lock`ed period). It is NOT free, it leaves every denominator, and
    #: it is the difference between "the school was shut" and "nobody worked".
    kind: str
    label: str | None = None      # "6-A" or "Notebook checking"
    detail: str | None = None     # the subject, or what the teacher typed
    work_type: str | None = None
    color: str = "free"


class DaybookRow(BaseModel):
    member_id: uuid.UUID
    name: str
    role: str
    cells: list[DaybookCell] = []
    teaching: int = 0
    cover: int = 0
    work: int = 0
    free: int = 0
    away_reason: str | None = None
    summary: str = ""
    #: On the timetable at all. Sorts teachers above office staff; never filters.
    teaches: bool = False


class DaybookSlice(BaseModel):
    key: str
    label: str
    periods: int
    color: str


class Daybook(BaseModel):
    date: date_
    is_today: bool = True
    weekday: int = 0
    is_working_day: bool = True
    closed_reason: str | None = None
    locked_periods: list[int] = []
    periods: list[DaybookPeriod] = []
    breaks: list[DaybookPeriod] = []
    rows: list[DaybookRow] = []
    #: Set only by `glimpse`, where `rows` is trimmed — so the overview can say
    #: "and 6 more" rather than quietly showing a partial school.
    rows_total: int | None = None
    slots_total: int = 0
    slots_teaching: int = 0
    slots_work: int = 0
    slots_free: int = 0
    slots_away: int = 0
    occupied_pct: float | None = None
    slices: list[DaybookSlice] = []
    headline: str = ""


# ── V1-16 · one person's record ──────────────────────────────────────────────


class RecordDaySlot(BaseModel):
    """A row of the person's own day — the vertical timeline, breaks included."""
    period_no: int
    start: str = ""
    end: str = ""
    kind: str
    label: str | None = None
    detail: str | None = None
    work_type: str | None = None
    color: str = "free"


class RecordMonthDay(BaseModel):
    """One cell of the month grid. `state` outranks the counts, so a holiday can
    never read as a day somebody failed to work (`S-34`, `S-145`)."""
    date: date_
    weekday: int
    state: str  # working | off | holiday | leave | future
    label: str | None = None
    teaching: int = 0
    cover: int = 0
    work: int = 0
    free: int = 0
    #: teaching + cover + work — what the grid's ramp is keyed on.
    busy: int = 0


class RecordSlice(BaseModel):
    key: str
    label: str
    periods: int
    color: str


class RecordPoint(BaseModel):
    """A point on the month's workload line."""
    date: date_
    teaching: int = 0
    work: int = 0


class StaffRecord(BaseModel):
    """What one member of staff's time went on — a record, never a score.

    There is no completeness figure, no rank against colleagues and no path to
    pay (`D-25`/`S-67`). `days_not_marked` is its own count in its own word and
    is never an absence (`S-34`).
    """
    member_id: uuid.UUID
    name: str
    role: str
    month: str
    start_date: date_
    end_date: date_
    date: date_                       # the day the "today" block is for
    is_today: bool = True

    # today
    today: list[RecordDaySlot] = []
    today_breaks: list[DaybookPeriod] = []
    today_summary: str = ""
    away_reason: str | None = None
    evening_labels: list[str] = []

    # the month
    days: list[RecordMonthDay] = []
    series: list[RecordPoint] = []
    slices: list[RecordSlice] = []
    teaching_periods: int = 0
    cover_periods: int = 0
    work_periods: int = 0
    evening_sessions: int = 0
    busiest_day: date_ | None = None
    busiest_periods: int = 0

    # attendance & leave (SF-1 / V1-4 figures, read not recomputed)
    working_days: int = 0
    days_marked: int = 0
    days_not_marked: int = 0
    days_present: float = 0
    days_absent: float = 0
    half_days: int = 0
    lates: int = 0
    leave_days: float = 0
    leave_remaining: float = 0

    # the written part
    headline: str = ""
    where_time_went: list[str] = []
    highlights: list[str] = []
    watch: list[str] = []
    summary: str = ""
    summary_source: str = "computed"   # computed | ai
