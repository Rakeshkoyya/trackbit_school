"""Post-setup read models (V2-P10). Everything here is derived on read."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class YearFacts(BaseModel):
    academic_year_id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    periods_per_day: int
    terms: int
    exams: int
    exam_portions: int
    # An exam with no portion can never fire the "syllabus won't finish in time"
    # warning — it's configured but inert, which is worth saying out loud.
    exams_without_portions: int


class ClassRow(BaseModel):
    class_id: uuid.UUID
    label: str
    students: int
    subjects: int
    subjects_without_teacher: int
    subjects_without_syllabus: int
    timetable_slots: int
    plans_approved: int
    plans_total: int
    worst_forecast: str  # green | none | amber | red


class SchoolOverviewOut(BaseModel):
    year: YearFacts
    teachers: int
    students: int
    classes: list[ClassRow]


class SubjectRow(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    teacher_member_id: uuid.UUID | None = None
    teacher_name: str | None = None

    # What the admin typed vs what the timetable actually gives. When these
    # disagree, every plan date for this subject is computed from the wrong number.
    periods_per_week: int
    timetabled_periods: int
    periods_mismatch: bool

    chapters: int
    topics: int
    est_periods: int
    topics_taught: int

    plan_status: str  # none | draft | approved
    plan_approved_at: datetime | None = None
    forecast: str  # none | green | amber | red
    weeks_behind: int | None = None
    baseline_finish: date | None = None
    projected_finish: date | None = None


class ClassOverviewOut(BaseModel):
    class_id: uuid.UUID
    label: str
    academic_year_id: uuid.UUID
    year_label: str
    students: int
    class_teacher_name: str | None = None
    subjects: list[SubjectRow]


class TeacherLoadRow(BaseModel):
    member_id: uuid.UUID
    name: str
    # Periods actually on the grid — the commitment, not the intent.
    periods_per_week: int
    classes: int
    subjects: int
