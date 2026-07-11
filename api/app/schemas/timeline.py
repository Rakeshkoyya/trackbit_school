"""Student timeline schemas (V2-M7, SPRD2 §5.7) — a computed join, no new tables."""

import uuid
from datetime import date

from pydantic import BaseModel


class TimelinePeriod(BaseModel):
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str | None = None
    topic: str | None = None
    # present | late | absent | unmarked
    attendance: str
    late_minutes: int | None = None
    checks_flagged: list[str] = []
    homework: list[str] = []
    gap: bool = False  # absent periods render as gaps


class TimelineSession(BaseModel):
    session_name: str
    kind: str = "study"  # study | homework | activity (HS-1)
    status: str  # present | late | absent
    homework_done: bool | None = None
    # HS-1: what the student worked on in a study session, when the teacher noted it.
    log_note: str | None = None


class StudentTimelineOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    date: date
    periods: list[TimelinePeriod]
    sessions: list[TimelineSession]
