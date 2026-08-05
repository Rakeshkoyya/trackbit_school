"""My Class — the class teacher's area (V1-3, D-03)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class MyClassSummary(BaseModel):
    class_id: uuid.UUID
    class_label: str
    roster: int = 0
    is_mine: bool = True


class MyClassOut(BaseModel):
    classes: list[MyClassSummary] = []


class RegisterCell(BaseModel):
    """One student × school day. `status` is THE day status
    (`classify_marked_day`) — the UI paints it, never re-derives. `not_marked`
    is a gap in the record and must render neutral, never red (ux §5)."""

    date: date
    # present | partial | absent | left_after_lunch | not_marked | no_school
    status: str
    late: bool = False
    # An exception reason or a covering informed-absence note (D-86: amber).
    has_reason: bool = False


class RegisterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    cells: list[RegisterCell] = []
    # "present 18 of 21 marked school days" — the denominator is the days this
    # class actually marked, and the label must say so (ux §4).
    present_days: int = 0
    marked_days: int = 0


class DayTally(BaseModel):
    """One column's total — the figure a paper register carries in its bottom
    margin. `pct`/`marked` are **null/false** on a day nobody marked: the one
    number this grid must never invent is a day it has no record of."""

    date: date
    marked: bool = False
    present: int = 0
    absent: int = 0
    counted: int = 0
    pct: float | None = None


class RegisterOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    month: str  # YYYY-MM
    mode: str = "every_period"
    # The screen branches on this: a once-per-day school's register is a DAY per
    # column, so the grid needs no period dimension and the capture sheet shows
    # no period picker.
    once_per_day: bool = False
    days: list[date] = []
    school_days: int = 0
    rows: list[RegisterRow] = []
    day_totals: list[DayTally] = []
    marked_days: int = 0
    pct: float | None = None
    headline: str = ""


# ── the class teacher's area, expanded (founder, 2026-08-05) ─────────────────
# One class, six questions: is everyone here · is the syllabus moving · did the
# work come back · how did they do · who needs support · and each child's file.
#
# Every figure below is READ from the service that already owns it — coverage
# from `CoverageReader`, homework from `core/homework_verdict`, exams from
# `ExamService.feed`, bands from `BandService.placements`, attendance from
# `day_matrix`. Nothing here re-derives a number, so a class teacher and her
# principal cannot be shown different figures for the same Tuesday (`S-51`).

class MyClassAbsentee(BaseModel):
    """One child not in today, with what can be done about it.

    Carries the guardian's own number because the next action is a phone call,
    and `reminded_today` so three people looking at the same child in one
    morning do not send the family three messages.
    """

    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    status: str = "absent"            # absent | partial | left_after_lunch
    streak: int = 1                   # consecutive marked days absent
    reason_code: str | None = None
    reason_note: str | None = None
    explained: bool = False
    guardian_name: str | None = None
    guardian_phone: str | None = None
    reminded_today: bool = False
    tone: str = "red"                 # explained absences are never red (D-86)


class MyClassAttendance(BaseModel):
    """Today's register for THIS class, and the month behind it.

    `roster` is the class's strength and is populated whether or not anything
    has been marked — the same rule the admin board was corrected to on
    2026-08-05. `marked` is what says whether the rest of the block means
    anything; a `present` of 0 under `marked=False` is a register nobody opened,
    not an empty classroom.
    """

    date: date
    is_today: bool = True
    school_open: bool = True
    marked: bool = False
    roster: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    periods_marked: int = 0
    periods_scheduled: int = 0
    pct: float | None = None
    # The month the register tab draws, summarised.
    month_pct: float | None = None
    month_marked_days: int = 0
    month_school_days: int = 0
    absentees: list[MyClassAbsentee] = []
    headline: str = ""
    tone: str = "neutral"


class MyClassHomework(BaseModel):
    """The V1-17 funnel, for one class.

    Counts **student-homeworks** throughout — one unit per child a homework was
    given to — so the stages nest (`given ⊇ checked ⊇ graded`) and each gap is a
    length rather than two numbers in different units.

    `not_checked` is the TEACHER's gap and is excluded from `completion_pct`
    (HW-1's load-bearing rule). A class nobody has checked must never read as a
    class that did nothing.
    """

    from_date: date
    to_date: date
    given: int = 0
    checked: int = 0
    graded: int = 0
    not_checked: int = 0
    done_weighted: float = 0
    completion_pct: float | None = None
    late: int = 0
    carried: int = 0
    waived: int = 0
    missed: int = 0
    assignments: int = 0
    unchecked_assignments: int = 0
    headline: str = ""
    tone: str = "neutral"


# ── homework, as it was actually set (founder, 2026-08-05) ───────────────────
# The funnel above says *how much* came back. It cannot say **what was given**,
# which is the first thing a class teacher is asked at a parent's gate and the
# only thing the old tab could not answer at all. So the same window is also
# read as a day book: today's homework in full, and every earlier day as a row
# that opens.
#
# The verdict vocabulary is `core/homework_verdict.py`'s and is never
# re-decided here — in particular `checked=False` is the TEACHER's gap: those
# rows carry no completion figure at all rather than a 0%.

class HomeworkMissRow(BaseModel):
    """One child who did not simply do it, named.

    Only exception rows exist (P1v2), so this list IS the record — everybody
    absent from it did the work on time. `carried` and `waived` appear here
    because the teacher needs to see them, but they are not misses and the
    completion figure never counts them (`D-34`/`S-98`).
    """

    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    status: str                       # not_done | partial | late | carried | waived
    note: str | None = None


class HomeworkItem(BaseModel):
    """One homework as the children received it.

    `text` is the thing the tab existed to show and never did. `student_id` set
    means it was a personal addition — its roster is exactly one child, and the
    figures beside it are that child's.
    """

    assignment_id: uuid.UUID
    date: date
    class_subject_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    subject_name: str
    teacher_name: str | None = None
    text: str
    due_date: date | None = None
    student_id: uuid.UUID | None = None
    student_name: str | None = None
    given: int = 0
    # HW-1: the absence of a check row is `not_checked`, which is never
    # "everyone did it". Nothing about the children is reported while this is
    # false — `completion_pct` stays null rather than becoming 0.
    checked: bool = False
    checked_at: datetime | None = None
    checked_by_name: str | None = None
    done: int = 0
    late: int = 0
    partial: int = 0
    not_done: int = 0
    carried: int = 0
    waived: int = 0
    graded: int = 0
    completion_pct: float | None = None
    misses: list[HomeworkMissRow] = []


class HomeworkDayRow(BaseModel):
    """One school day of homework, rolled up — the table's row.

    Same units as the funnel (student-homeworks), so a day's figures and the
    window's figures are the same arithmetic at two scales.
    """

    date: date
    assignments: int = 0
    subjects: list[str] = []
    given: int = 0
    checked: int = 0
    not_checked: int = 0
    graded: int = 0
    done_weighted: float = 0
    completion_pct: float | None = None
    late: int = 0
    missed: int = 0
    unchecked_assignments: int = 0
    tone: str = "neutral"


class MyClassHomeworkDays(BaseModel):
    """The day book: today in full, every earlier day as an openable row.

    Paginated over DAYS rather than assignments — a school year is ~200 rows and
    the question is always "what went home on the 14th", never "show me
    assignment 4,312".
    """

    class_id: uuid.UUID
    class_label: str
    today: date
    today_items: list[HomeworkItem] = []
    rows: list[HomeworkDayRow] = []
    page: int = 1
    size: int = 20
    total_days: int = 0
    headline: str = ""


class MyClassHomeworkDay(BaseModel):
    """One day, opened — every homework that went home, in full."""

    class_id: uuid.UUID
    class_label: str
    date: date
    day: HomeworkDayRow
    items: list[HomeworkItem] = []
    headline: str = ""


class MyClassBandStudent(BaseModel):
    """One child under a subject's band, with how they are actually doing.

    The percentage is the child's own average in THAT subject, and it carries
    the scale it came from — `core/exams.py` refuses to pool a slip test with a
    term paper, so a bare number here would be the one thing the exam module
    exists to prevent. `pct` is null when nothing has been recorded, never 0.
    """

    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    tier: str                          # A | B | C
    pct: float | None = None
    scale: str | None = None           # minor | major — which figure `pct` is
    tests_taken: int = 0
    tests_held: int = 0
    sentence: str | None = None
    attendance_pct: float | None = None


class MyClassBandSubject(BaseModel):
    """One monitored subject's A/B/C shape for this class.

    The unit is the PLACEMENT, not the child (`D-75`): there is no overall
    letter, so a boy who is A in Maths and C in Hindi is counted in both. The
    percentages divide by `assessed`, never by the roster — `not_assessed` is
    its own number in its own word and is never a step on the ramp.
    """

    subject_id: uuid.UUID
    subject_name: str
    a: int = 0
    b: int = 0
    c: int = 0
    assessed: int = 0
    # Kept as the DENOMINATOR only ("11 of 15 assessed"), which every figure in
    # this product has to carry (ux §4). Founder 2026-08-05 removed it as a
    # fourth tile beside A/B/C — it was reading as a band, which is exactly what
    # it must never be.
    not_assessed: int = 0
    # Expanded: who is in each tier, and how they are doing in this subject.
    students: list[MyClassBandStudent] = []


class MyClassBands(BaseModel):
    subjects: list[MyClassBandSubject] = []
    monitored: int = 0
    headline: str = ""


class MyClassExams(BaseModel):
    """The last few exams this class sat.

    Minor and major are never pooled (`core/exams.py`): the headline names the
    scale its figure came from, and there is no blended average anywhere here.
    """

    recent: list[dict] = []           # ExamSummary rows, passed through
    headline: str = ""


class MyClassOverview(BaseModel):
    class_id: uuid.UUID
    class_label: str
    roster: int = 0
    as_of: date
    # The sentence first, the figures under it (ux §7). Composed server-side so
    # this block and each tab it links to cannot describe the day differently.
    headline: str = ""
    attendance: MyClassAttendance
    homework: MyClassHomework
    bands: MyClassBands
    exams: MyClassExams
    # `ClassSyllabusOut` verbatim from `MySyllabusService` — not a second shape.
    syllabus: dict | None = None


class MyClassStudentRow(BaseModel):
    """One child in the class table — the door to their file.

    Deliberately NOT a ranking. Every figure carries its own denominator, an
    unmarked or unchecked denominator is `None` rather than 0, and the band chip
    is `"C · Hindi"` (`S-186`) — the lowest band with the subject that earned
    it, never a bare letter and never an average.
    """

    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    admission_no: str | None = None
    category: str | None = None
    attendance_pct: float | None = None
    marked_days: int = 0
    days_absent: int = 0
    absent_today: bool = False
    homework_pct: float | None = None
    homework_missed: int = 0
    homework_graded: int = 0
    band_chips: list[str] = []
    latest_exam_pct: float | None = None
    latest_exam_name: str | None = None
    note_count: int = 0
    guardian_name: str | None = None
    guardian_phone: str | None = None
    tone: str = "neutral"


class MyClassStudentsOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    from_date: date
    to_date: date
    rows: list[MyClassStudentRow] = []
    headline: str = ""


# ── the class teacher's own log about a child ────────────────────────────────
class StudentNoteIn(BaseModel):
    kind: str = Field(default="general", pattern=r"^(general|behaviour|wellbeing"
                                                 r"|achievement|parent_contact|concern"
                                                 r"|support|assessment)$")
    note: str = Field(min_length=1, max_length=4000)
    # Founder 2026-08-05: what occasioned it, when it came off a support
    # assessment's sheet. A pointer on the ONE log about a child rather than a
    # second per-assessment note store — a year later his teacher wants to read
    # everything anyone noticed in a single scroll.
    assessment_id: uuid.UUID | None = None


class StudentNoteOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    kind: str
    note: str
    assessment_id: uuid.UUID | None = None
    author_name: str | None = None
    created_at: datetime


class StudentNotesOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    can_write: bool = False
    rows: list[StudentNoteOut] = []
