"""Homework analytics schemas (HW-1)."""

import uuid
from datetime import date as date_
from datetime import datetime

from pydantic import BaseModel


class HomeworkFunnel(BaseModel):
    """Set → checked → done, and all three in ONE unit.

    The board used to report `assigned`/`checked` in **sets of homework** and
    `done` in **students**, which is why its three headline numbers could never
    be drawn on one track or read as one story. Everything here counts
    *student-homeworks*: one row per student a homework was given to, so the
    stages nest — `given ⊇ checked ⊇ graded` — and each gap is a length.

    The two gaps are two different problems and never the same colour:

      * `given − checked` — **nobody has gone through it**. HW-1's rule: the
        teacher's gap, never a child's. It is a state, drawn as the
        no-record texture, and it is never a zero and never red.
      * `graded − done_weighted` — the work that was not done. This one is
        about children, and it is the only one that may carry a judgement.

    `carried` and `waived` sit between the two: checked, but outside the
    denominator entirely (`D-34`/`S-98`), so they are reported and never
    silently folded into either gap.
    """
    # Stage 1 — every student a homework was given to.
    given: int = 0
    # Stage 2 — of those, the ones under homework a teacher went through.
    checked: int = 0
    # Stage 3's denominator — of the checked, those carrying a real verdict.
    # `given − checked` is not-checked; `checked − graded` is carried + waived.
    graded: int = 0

    done: int = 0
    late: int = 0            # did it, after the deadline — counts as done (S-99)
    partial: int = 0
    not_done: int = 0
    carried: int = 0         # absent when it was set — outside the denominator
    waived: int = 0          # teacher decided it isn't required — likewise
    # done + late + PARTIAL_WEIGHT·partial. The numerator `completion` divides,
    # carried here so no screen re-derives it and gets a different answer.
    done_weighted: float = 0.0

    # What the stages are made of, so the figures can carry their denominators.
    assignments: int = 0
    class_subjects: int = 0

    # Both rates, each named for the denominator it actually uses. Keeping them
    # apart is the point: "74% of what was set has been checked" and "89% of
    # what was graded was done" are different facts about different things.
    check_rate: float | None = None      # checked / given
    completion: float | None = None      # done_weighted / graded


class HomeworkMatrixCell(BaseModel):
    """One class × one subject. The cell the class/subject bar charts could not
    draw: they each collapsed a whole axis, so "6-B is low" and "Hindi is low"
    could not resolve into "6-B Hindi is where it happens".

    `completion is None` means nothing under this pair was checked — a state,
    rendered as the no-record texture, never a 0%.
    """
    class_key: str
    subject_key: str
    assigned: int = 0
    checked: int = 0
    given: int = 0
    graded: int = 0
    completion: float | None = None
    # Decided server-side (the V1-15 precedent): three surfaces render these
    # cells and a tone each worked out for itself would be three verdicts about
    # one teacher on one morning.
    tone: str = "neutral"


class HomeworkDay(BaseModel):
    """One bucket of the series — a day, or a week once the range is long.

    Accumulated inside `overview()`'s single pass, so it goes through
    `core/homework_verdict` like every other figure on the board. It used to be
    a second walk with its own arithmetic: `late` was dropped from the
    numerator, `carried`/`waived` stayed in the denominator, and the
    absent→carried rewrite never ran — so the chart read lower than the
    sentence directly above it.
    """
    date: date_
    label: str = ""              # server-formatted; a week bucket is not a date
    days: int = 1                # how many days this bucket covers
    assigned: int = 0            # sets of homework
    checked: int = 0             # of those, gone through
    given: int = 0               # student-homeworks given
    expected: int = 0            # of those, graded — the completion denominator
    done: int = 0                # done + late: whole students who did the work
    partial: int = 0
    not_done: int = 0
    not_checked: int = 0         # student-homeworks nobody has gone through
    completion: float | None = None


class HomeworkScopeRow(BaseModel):
    """One class, subject or teacher rolled up over the window."""
    key: str                     # class label / subject name / teacher name
    id: uuid.UUID | None = None
    assigned: int                # homework set
    checked: int                 # of those, how many the teacher went through
    students_expected: int       # graded student-assignments — the denominator
    # The funnel's first two stages at this scope, in student-homeworks, so a
    # row can be drawn on the same track as the school-level figure.
    students_set: int = 0
    students_checked: int = 0
    done: int
    not_done: int
    partial: int
    # Did it, after the deadline. Counts as done in `completion` and is reported
    # beside it, never inside it (S-99) — folding it in hides a class where
    # everything arrives four days late.
    late: int = 0
    # Absent when it was set. NOT a miss and NOT in the denominator (D-34).
    carried: int = 0
    # Teacher decided it isn't required (S-98). Also outside the denominator —
    # it was missing from this row entirely, so waived work was invisible on the
    # by-class and by-subject tables while the student history reported it.
    waived: int = 0
    completion: float | None     # None = nothing checked, which is not zero
    check_rate: float | None     # checked / assigned — the discipline number


class TeacherCheckingRow(BaseModel):
    """Is this teacher actually checking what they set?

    `unchecked_overdue` is the one that matters: homework whose due date has
    passed with no check recorded. Recently-set homework being unchecked is
    normal, and counting it would cry wolf every afternoon.
    """
    member_id: uuid.UUID | None = None
    teacher_name: str
    assigned: int
    checked: int
    unchecked_overdue: int
    check_rate: float | None
    last_checked_at: datetime | None = None


class StudentHomeworkRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str
    roll_no: str | None = None
    assigned: int
    done: int
    not_done: int
    partial: int
    late: int = 0
    carried: int = 0
    completion: float | None
    # Consecutive school days ending most-recently with a miss. Days carrying
    # only a neutral verdict (not_checked / carried / waived) are skipped, never
    # counted as clean and never as a miss (S-102).
    streak: int = 0
    # Misses in the earlier half of the window minus the recent half. Its own
    # field because the improvement delta used to be smuggled through `streak`,
    # which meant the row said "3 day streak" and the screen rendered "3 fewer
    # misses" from the same number — a lie any second consumer would inherit.
    improvement: int = 0
    subjects: list[str] = []
    teachers: list[str] = []


class RoughClassRow(BaseModel):
    """D-85's second admin signal: this class WAS checked, and N children missed
    it. A different problem from "nobody checked", and a different conversation.
    """
    assignment_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    date: date_
    text: str
    missed: int
    students_expected: int
    teacher_name: str | None = None


class HomeworkOverview(BaseModel):
    window_days: int
    from_date: date_
    to_date: date_
    # These two count SETS of homework, not students — kept because the teacher
    # checking table is denominated in sets ("she set 9 and went through 4").
    # Anything comparing set → checked → done reads `funnel` instead.
    assigned: int
    checked: int
    check_rate: float | None
    overall_completion: float | None
    late: int = 0
    carried: int = 0
    # The three stages in one unit, and the series, both accumulated in the same
    # single pass over the same loaded window — so they cannot disagree with the
    # figures beside them.
    funnel: HomeworkFunnel = HomeworkFunnel()
    daily: list[HomeworkDay] = []
    matrix: list[HomeworkMatrixCell] = []
    # The matrix axes, ordered by the server so every renderer draws the same
    # grid and an empty pair is a hole rather than a missing column.
    matrix_classes: list[str] = []
    matrix_subjects: list[str] = []
    by_class: list[HomeworkScopeRow] = []
    by_subject: list[HomeworkScopeRow] = []
    teachers: list[TeacherCheckingRow] = []
    # Students who keep not doing it — the red list, worst first.
    needs_attention: list[StudentHomeworkRow] = []
    # Zero misses over the window, and the biggest improvers. Recognition needs a
    # list, not a single "best": in a healthy class dozens tie at zero.
    perfect: list[StudentHomeworkRow] = []
    most_improved: list[StudentHomeworkRow] = []
    # The two signals D-85 sends the admin. Both are derived; neither writes
    # anything into a child's record.
    delayed_teachers: list[TeacherCheckingRow] = []
    rough_classes: list[RoughClassRow] = []


class HomeworkQueueItem(BaseModel):
    """One homework on the teacher's Homework screen (D-36 / S-101)."""
    assignment_id: uuid.UUID
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    date: date_
    due_date: date_ | None = None
    text: str
    student_id: uuid.UUID | None = None      # set = a personal homework
    student_name: str | None = None
    checked: bool = False
    checked_at: datetime | None = None
    # The deadline passed with nothing gone through. A fact about the RECORD —
    # never a judgement about a child, and nothing expires (D-85).
    overdue: bool = False
    days_waiting: int = 0
    missed: int = 0                          # not_done + partial on this one
    carried: int = 0                         # absent when it was set


class HomeworkQueue(BaseModel):
    from_date: date_
    to_date: date_
    items: list[HomeworkQueueItem] = []
    # S-100 — the number on the button. Without it the screen is optional.
    to_check: int = 0
    overdue: int = 0


class HomeworkLoadCell(BaseModel):
    """One class's evening: how many subjects set homework that day (D-37/S-87)."""
    class_id: uuid.UUID
    class_label: str
    date: date_
    subjects: int
    assignments: int


class HomeworkLoad(BaseModel):
    """Admin and class teacher only. Informational — no cap, no rota (D-37)."""
    from_date: date_
    to_date: date_
    cells: list[HomeworkLoadCell] = []
    busiest_class_label: str | None = None
    busiest_date: date_ | None = None
    busiest_subjects: int = 0


class StudentHomeworkItem(BaseModel):
    """One homework as it applies to one student."""
    assignment_id: uuid.UUID
    date: date_
    due_date: date_ | None = None
    subject_name: str | None = None
    class_label: str | None = None
    text: str
    personal: bool = False       # set for this student alone
    # See core/homework_verdict.py — done | late | partial | not_done | carried |
    # waived | not_checked. `not_checked` is the TEACHER's gap and `carried` is
    # an absence; neither may be presented as a miss on any surface.
    status: str
    note: str | None = None


class StudentHomeworkHistory(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    window_days: int
    assigned: int
    done: int
    not_done: int
    partial: int
    late: int = 0
    carried: int = 0
    waived: int = 0
    not_checked: int
    completion: float | None
    streak: int = 0
    items: list[StudentHomeworkItem] = []
