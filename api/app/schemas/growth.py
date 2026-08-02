"""Student growth report schemas (teacher-view redesign, 2026-07).

Chapter-level is the default reading; every chapter carries its topic rows so the
UI can drill to topic level without a second call. Staff-only surface: admin sees
every student, a teacher only students in classes they teach. Bands appear here
because this never reaches a guardian (P4 stays intact).
"""

import uuid
from datetime import date

from pydantic import BaseModel


class GrowthAttendance(BaseModel):
    marked_periods: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    pct: float | None = None  # None until anything is marked


class GrowthTopic(BaseModel):
    """Topic-level tracking: what the class did with it, and whether THIS student
    was in the room when it happened."""

    topic_id: uuid.UUID
    title: str
    status: str  # done | in_progress | pending
    taught_on: date | None = None
    # present | absent | late — None when the topic hasn't been taught or the
    # teaching period had no attendance capture.
    student_attendance: str | None = None


class GrowthChapter(BaseModel):
    unit_id: uuid.UUID
    title: str
    topics_total: int
    # V1-0d: `topics_taught` = FULLY covered only; a topic still in progress is
    # its own count. Folding them together was the parent-side half of S-51 —
    # coverage read one way on the admin board and another on this report.
    topics_taught: int
    topics_in_progress: int = 0
    # Topics taught in a period this student was absent from — the chapter-level
    # red flag that makes the drill-down worth opening.
    topics_missed: int
    topics: list[GrowthTopic] = []


class GrowthObservation(BaseModel):
    date: date
    section: str
    concept: str | None = None
    rating: str
    note: str | None = None


class GrowthScore(BaseModel):
    cycle_name: str
    date: date
    score: float
    max_score: float
    # ── V1-8 ────────────────────────────────────────────────────────────────
    # Before this, the score history was `{cycle_name, date, score, max_score}`
    # with **no type** (module §4.3), so `/students/[id]` drew one series
    # through a 5-mark slip test and an 80-mark final: a child at 40% on slips
    # and 85% in the finals read as erratic. `scale` is what keeps the two
    # apart (`S-114`) and `type_label` is the school's own word (`D-55`).
    cycle_id: uuid.UUID | None = None
    type: str | None = None
    type_label: str | None = None
    scale: str = "minor"
    # `S-119`: this student's own marked script, kept forever as evidence and —
    # until V1-8 — unreachable from the screen a parent meeting happens over.
    paper_url: str | None = None


class GrowthScaleFigure(BaseModel):
    """`S-118`: an average that carries its denominator, one level below the
    school figure. *"61% across 5 of the 9 tests 8-B sat"* — because a child who
    is absent for the hard ones otherwise reads as strong."""
    scale: str
    label: str
    avg_pct: float | None = None
    tests_taken: int = 0
    tests_held: int = 0
    sentence: str = ""


class GrowthSubject(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None = None
    attendance: GrowthAttendance
    chapters: list[GrowthChapter] = []

    # ── V1-6, `S-51`/`S-54`/`Q-16` ───────────────────────────────────────────
    # Coverage computed by `core.coverage`, not by the browser. Two pages used
    # to sum `topics_taught / topics_total` in JavaScript — a third and fourth
    # definition of "syllabus covered" that no test could ever have caught.
    #
    # The basis is **the whole syllabus**, deliberately (`Q-16`): it is the only
    # denominator that cannot go down. Coverage against the *plan* falls the day
    # a school sizes next term's chapters — nothing was un-taught, the
    # denominator simply grew — and a parent reads that as the school going
    # backwards (`S-54`). Staff surfaces get both bases; this one gets the safe
    # one, and `coverage_basis` says which so no screen has to guess.
    coverage_taught: float = 0
    coverage_total: int = 0
    coverage_pct: float | None = None
    coverage_basis: str = "syllabus"

    # `S-48` — *"This week in Maths: Fractions — addition and subtraction"*.
    # A chapter name beats a percentage for a parent, because it is the thing
    # they can ask their child about at dinner. Derived from lesson logs.
    latest_chapter: str | None = None
    latest_topic: str | None = None
    latest_taught_on: date | None = None
    homework_assigned: int = 0
    homework_personal: int = 0  # per-student additions targeted at this student
    # This student's own record on that homework (HW-1). `homework_not_checked`
    # is the teacher's gap — reported so the other three read honestly, and never
    # counted against the child.
    homework_done: int = 0
    homework_not_done: int = 0
    # V1-0d: 'partly' is its own count — it used to be folded into not_done,
    # which wrote a wrong fact onto the report card (Q-40).
    homework_partial: int = 0
    # V1-5: `late` is INSIDE homework_done (it is done — S-99) and named here so
    # the pattern stays visible. `carried` is an absence, not a refusal (D-34):
    # its own count, in neither done nor not_done.
    homework_late: int = 0
    homework_carried: int = 0
    homework_not_checked: int = 0
    checks_flagged: int = 0  # daily-check "didn't do it" exceptions
    observations: list[GrowthObservation] = []
    scores: list[GrowthScore] = []
    # V1-8: the two never-pooled figures for this subject, each with its own
    # denominator. The list is what the history chart draws; these are what a
    # sentence may quote.
    score_figures: list[GrowthScaleFigure] = []


class GrowthSkill(BaseModel):
    skill_area: str
    score: float
    max_score: float
    cycle_name: str


class GrowthBandEntry(BaseModel):
    tier: str
    set_on: date
    note: str | None = None
    # V1-9: which subject earned it. None on the legacy overall rows, which are
    # kept as history and read by no current computation (`D-75`).
    subject_name: str | None = None


class StudentGrowthOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    # V1-7 `S-133`: the FULL date belongs on the student's own record — the
    # register and board registration both need it. It is the shared surfaces
    # (class lists, the what's-on feed) that get the day only, never the age.
    date_of_birth: date | None = None
    # V1-9 (`S-186`): **"C · Hindi"** — the lowest band the child holds, named
    # with the subject that earned it. Never a bare letter, never an average
    # across subjects, and staff-only throughout (P4).
    band: str | None = None
    band_history: list[GrowthBandEntry] = []
    attendance: GrowthAttendance
    subjects: list[GrowthSubject] = []
    skills: list[GrowthSkill] = []
    # Derived attention list — repeated needs_work concepts, repeated check
    # flags, weak scores, low attendance. Phrases, never tiers.
    growth_areas: list[str] = []
    # The mirror list — high attendance, 'excellent' observations, strong scores.
    strengths: list[str] = []
