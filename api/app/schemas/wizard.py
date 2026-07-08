"""Setup wizard schemas (V2-M1, SPRD2 §5.1)."""

from pydantic import BaseModel, Field

TOTAL_STEPS = 9


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


class WizardStateOut(BaseModel):
    current_step: int
    total_steps: int = TOTAL_STEPS
    status: str
    payload: dict
    progress: WizardProgress


class WizardAdvanceIn(BaseModel):
    to_step: int = Field(ge=1, le=TOTAL_STEPS)
    payload: dict = {}
