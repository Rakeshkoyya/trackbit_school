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
    topics_taught: int
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


class GrowthSubject(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None = None
    attendance: GrowthAttendance
    chapters: list[GrowthChapter] = []
    homework_assigned: int = 0
    homework_personal: int = 0  # per-student additions targeted at this student
    checks_flagged: int = 0  # daily-check "didn't do it" exceptions
    observations: list[GrowthObservation] = []
    scores: list[GrowthScore] = []


class GrowthSkill(BaseModel):
    skill_area: str
    score: float
    max_score: float
    cycle_name: str


class GrowthBandEntry(BaseModel):
    tier: str
    set_on: date
    note: str | None = None


class StudentGrowthOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    band: str | None = None  # latest overall tier — staff-only (P4)
    band_history: list[GrowthBandEntry] = []
    attendance: GrowthAttendance
    subjects: list[GrowthSubject] = []
    skills: list[GrowthSkill] = []
    # Derived attention list — repeated needs_work concepts, repeated check
    # flags, weak scores, low attendance. Phrases, never tiers.
    growth_areas: list[str] = []
    # The mirror list — high attendance, 'excellent' observations, strong scores.
    strengths: list[str] = []
