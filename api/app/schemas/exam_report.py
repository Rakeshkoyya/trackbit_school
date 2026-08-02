"""The exam Report tab's payload (V1-8, `D-80`).

The **Score** tab is `ExamDetail` — the roster and their marks, nothing else.
This is the other tab: the analysis a teacher and an admin arrive asking for.
Every figure here carries its denominator, no row carries a rank, and the
question detail is **absent as a word** when nobody photographed a marked paper.
"""

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.insights import ExamBand

Date = date


class ExamReportRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    score: float | None = None
    max_score: float | None = None
    pct: float | None = None


class ExamReportQuestion(BaseModel):
    """One question across everybody who sat it — from the marks the teacher
    wrote on the paper, never from a judgement about the answers (`Q-51`)."""
    q: str
    attempted: int = 0
    avg_score: float | None = None
    max: float | None = None
    avg_pct: float | None = None


class ExamReport(BaseModel):
    cycle_id: uuid.UUID
    name: str
    date: Date
    type_label: str = ""          # the school's own word (D-55)
    scale: str = "minor"
    scale_label: str = ""
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    subject_name: str
    topic: str | None = None
    total_marks: float | None = None
    locked: bool = False

    # The sentence and the figures behind it.
    summary: str = ""
    summary_source: str = "fixture"
    roster: int = 0
    scored: int = 0
    avg_pct: float | None = None
    participation: float | None = None

    distribution: list[ExamBand] = []
    rows: list[ExamReportRow] = []
    # Named rows, each with a stated criterion — never a rank.
    not_sat: list[ExamReportRow] = []
    struggling: list[ExamReportRow] = []
    strong: list[ExamReportRow] = []
    gap_points: float = 15.0

    # Absent, as a word, for an exam typed in by hand.
    questions: list[ExamReportQuestion] = []
    question_note: str | None = None

    # What the class had been taught by then — `services/coverage.py`, the one
    # syllabus computation.
    coverage_taught: float = 0.0
    coverage_total: int = 0
    coverage_pct: float | None = None
    coverage_note: str | None = None
    latest_topic: str | None = None
    exam_event_name: str | None = None
