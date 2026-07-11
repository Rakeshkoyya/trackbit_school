"""Setup wizard schemas (V2-M1, SPRD2 §5.1).

Step order is a real dependency chain, not a preference (reordered in V2-P7):

  1  year + terms      everything hangs off the academic year
  2  timings           periods_per_day bounds the timetable grid
  3  classes           a class needs a year
  4  subjects          the school's subject list
  5  staff             teachers, then class_subjects — the join row carries the
                       teacher and the weekly period budget, so the teacher must
                       exist first. (A staff sheet's "6-A Mathematics" hints can
                       only resolve once classes and subjects are both in.)
  6  syllabus          syllabus_units hang off class_subject_id — so this CANNOT
                       come before classes and subjects, whatever the setup
                       narrative suggests
  7  calendar + exams  exam portions point at syllabus topics, so exams follow
                       syllabus; that ordering is what unlocks the V5
                       exam-coverage validator ("this chapter won't be taught
                       before the exam that examines it")
  8  students          independent of the plan, but needed before the year runs
  9  timetable         needs classes, class_subjects and timings
  10 generate + lock   needs all of the above
"""

from pydantic import BaseModel, Field

TOTAL_STEPS = 10

# The stepper is rendered from this, so the order lives in exactly one place.
STEPS: list[tuple[str, str]] = [
    ("year", "Academic year"),
    ("timings", "School timings"),
    ("classes", "Classes"),
    ("subjects", "Subjects"),
    ("staff", "Teachers & assignments"),
    ("syllabus", "Syllabus & lesson plan"),
    ("calendar", "Calendar, holidays & exams"),
    ("students", "Students"),
    ("timetable", "Timetable"),
    ("generate", "Generate & lock"),
]


class WizardProgress(BaseModel):
    """Derived from the REAL tables (no parallel store) — the wizard is truthful
    even after manual edits made outside it."""
    has_year: bool
    terms: int
    has_timings: bool
    classes: int
    subjects: int
    class_subjects: int
    syllabus_topics: int
    teachers: int
    students: int
    timetable_slots: int
    plans_total: int
    plans_approved: int
    # V2-P7: the calendar/exam step.
    calendar_events: int = 0
    exams: int = 0
    exam_portions: int = 0
    # V2-P12: capture gaps that will make the generated plan wrong — shown on the
    # generate step so the admin fixes the data instead of locking fiction.
    gaps: list[str] = []


class WizardStepOut(BaseModel):
    key: str
    title: str
    index: int  # 1-based
    complete: bool


class WizardStateOut(BaseModel):
    current_step: int
    total_steps: int = TOTAL_STEPS
    status: str
    payload: dict
    progress: WizardProgress
    steps: list[WizardStepOut] = []


class WizardAdvanceIn(BaseModel):
    to_step: int = Field(ge=1, le=TOTAL_STEPS)
    payload: dict = {}
