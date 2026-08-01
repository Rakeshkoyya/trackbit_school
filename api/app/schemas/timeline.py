"""Student timeline schemas (V2-M7, SPRD2 §5.7) — a computed join, no new tables."""

import uuid
from datetime import date

from pydantic import BaseModel


class TimelineHomework(BaseModel):
    """One homework as it applies to THIS student (HW-1).

    `not_checked` is the teacher not having gone through it — a gap in the
    record, never a mark against the child, and no parent-facing surface may
    render it as a miss.
    """
    assignment_id: uuid.UUID
    text: str
    # done | not_done | partial | not_checked
    status: str = "not_checked"
    due_date: date | None = None
    personal: bool = False


class TimelinePeriod(BaseModel):
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str | None = None
    topic: str | None = None
    # present | late | absent | unmarked
    attendance: str
    late_minutes: int | None = None
    checks_flagged: list[str] = []
    homework: list[TimelineHomework] = []
    gap: bool = False  # absent periods render as gaps


class TimelineSession(BaseModel):
    session_name: str
    kind: str = "study"  # study | homework | activity (HS-1)
    status: str  # present | late | absent
    homework_done: bool | None = None
    # HS-1: what the student worked on in a study session, when the teacher noted it.
    log_note: str | None = None


class TimelineFollowup(BaseModel):
    """D-46: a follow-up raised ABOUT this student, on this day — staff-only
    surface; the parent projection never carries it."""

    task_id: uuid.UUID
    title: str
    status: str  # open | done | missed
    assignee_name: str | None = None
    outcome: str | None = None  # "what happened?", once completed


class StudentTimelineOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    date: date
    periods: list[TimelinePeriod]
    sessions: list[TimelineSession]
    followups: list[TimelineFollowup] = []
    # THE day status (V1-0d, ux §9) — computed once here by `classify_day`;
    # the parent portal, the report card and the admin board all render it.
    day_status: str = "no_school"
    marked_periods: int = 0
    absent_periods: int = 0
    late_periods: int = 0
