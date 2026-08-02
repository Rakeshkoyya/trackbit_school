"""Report card + analysis schemas (V1-8, `D-81`).

**Two levels, deliberately.**

*Level 1 — the report card.* Standard, familiar, **numbers only**: this child's
subjects and the exams they sat, per student and (the same thing for everybody)
per class. It carries no narrative, no tier, no advice.

*Level 2 — the analysis.* Per topic, skill abilities, and an AI-written
per-subject summary **over figures the product already computes** — never over
numbers the model invented.

> This is a report card **output**, not the report-card **designer** SPRD2 §11
> fences. A fixed, well-made card is a rendering; a designer is a layout tool
> with a template editor, and we ship neither the editor nor a computed composite
> grade (`S-114`'s two buckets are the furthest this goes).

Two rules ride on every figure here: nothing is pooled across `scale`, and every
average carries its denominator (`core/exams.py`). And P4 holds throughout — a
band never appears on this card, because the card is the surface most likely to
be printed and handed to a parent.
"""

import uuid
from datetime import date

from pydantic import BaseModel

Date = date


class ScaleFigureOut(BaseModel):
    """An average that cannot be rendered without its denominator (`S-118`)."""
    scale: str
    label: str
    purpose: str
    avg_pct: float | None = None
    tests_taken: int = 0
    tests_held: int = 0
    sentence: str = ""


class ReportCardExam(BaseModel):
    cycle_id: uuid.UUID
    name: str
    type_label: str        # the school's own word (D-55)
    scale: str
    date: Date
    score: float
    max_score: float
    pct: float | None = None
    locked: bool = False
    # S-119: the marked paper, one tap away.
    paper_url: str | None = None


class ReportCardSubject(BaseModel):
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    exams: list[ReportCardExam] = []
    figures: list[ScaleFigureOut] = []


class ReportCard(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    admission_no: str | None = None
    class_label: str | None = None
    as_of: Date
    subjects: list[ReportCardSubject] = []
    # Across every subject — still two figures, still never pooled.
    figures: list[ScaleFigureOut] = []


class ClassReportCardColumn(BaseModel):
    cycle_id: uuid.UUID
    name: str
    type_label: str
    scale: str
    date: Date
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    total_marks: float | None = None


class ClassReportCard(BaseModel):
    class_id: uuid.UUID
    class_label: str
    as_of: Date
    columns: list[ClassReportCardColumn] = []
    students: list[ReportCard] = []


# ── level 2 — the analysis ───────────────────────────────────────────────────
class AnalysisTopic(BaseModel):
    title: str
    status: str            # done | in_progress | pending — a word, never a colour
    missed_while_absent: bool = False


class AnalysisSubject(BaseModel):
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    teacher_name: str | None = None
    figures: list[ScaleFigureOut] = []
    coverage_taught: float = 0.0
    coverage_total: int = 0
    coverage_pct: float | None = None
    attendance_pct: float | None = None
    topics: list[AnalysisTopic] = []
    # The per-subject narrative (`D-81` level 2). `source` says who wrote it —
    # 'ai' or 'fixture' — because a reader is owed that.
    summary: str = ""
    summary_source: str = "fixture"


class AnalysisSkill(BaseModel):
    skill_area: str
    score: float
    max_score: float
    pct: float | None = None


class StudentAnalysis(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    as_of: Date
    attendance_pct: float | None = None
    figures: list[ScaleFigureOut] = []
    subjects: list[AnalysisSubject] = []
    skills: list[AnalysisSkill] = []
    strengths: list[str] = []
    growth_areas: list[str] = []
    summary: str = ""
    summary_source: str = "fixture"
