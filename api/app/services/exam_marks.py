"""The one batched read of a class's marks (V1-8).

Rule 1 of the v1 plan — *one computation, many renderings* — is why this module
exists rather than three score queries. Four surfaces ask the same question in
different shapes:

    the student's report card      subjects × exams, numbers only (`D-81` L1)
    the growth report              the same marks beside attendance and coverage
    the class report card          the same thing for everybody
    the analysis                   the same marks with a narrative over them

Before V1-8 each had its own query and its own arithmetic, and none of them
carried the type — so a slip test and a term exam were pooled (`S-114`) and an
average never said how many tests it was over (`S-118`). Both rules live in
`core/exams.py`; the reading of them lives here, **once**, batched: four queries
for a whole class, not four per student.

Nothing in this module renders. It returns rows and figures; the screens decide
what to say about them.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exams import SCALES, ScaleTally, normalise_scale, type_label
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    ExamType,
    ScoreCapture,
    ScoreCapturePage,
    Subject,
)
from app.services import storage


@dataclass(frozen=True)
class MarkRow:
    """One student's mark in one exam, carrying everything a screen needs to
    render it honestly: its scale, the school's word for its type, and the
    paper it came off."""

    cycle_id: uuid.UUID
    cycle_name: str
    date: date_
    system_type: str
    type_label: str
    scale: str
    subject_id: uuid.UUID | None
    subject_name: str | None
    score: float
    max_score: float
    locked: bool = False
    question_marks: list | None = None
    paper_url: str | None = None

    @property
    def pct(self) -> float | None:
        return round(self.score / self.max_score * 100, 1) if self.max_score else None


@dataclass
class ClassMarks:
    """Every mark a class has, indexed for the readers above."""

    rows: dict[uuid.UUID, list[MarkRow]] = field(default_factory=lambda: defaultdict(list))
    # cycle → (subject_id, scale, the subset who sat it or None for everybody)
    cycles: dict[uuid.UUID, tuple] = field(default_factory=dict)

    def for_student(self, student_id: uuid.UUID) -> list[MarkRow]:
        return sorted(self.rows.get(student_id, []), key=lambda r: r.date)

    def held(self, student_id: uuid.UUID) -> dict[uuid.UUID | None, dict[str, int]]:
        """subject → {scale: tests this student could have sat} (`S-118`).

        A few-students test the child was never part of is not in their
        denominator — otherwise the figure would say they missed something
        nobody asked them to sit."""
        out: dict[uuid.UUID | None, dict[str, int]] = defaultdict(
            lambda: dict.fromkeys(SCALES, 0))
        for subject_id, scale, subset in self.cycles.values():
            if subset and str(student_id) not in subset:
                continue
            out[subject_id][scale] += 1
        return out

    def figures(self, student_id: uuid.UUID, subject_id: uuid.UUID | None = None) -> list:
        """The student's two never-pooled figures, each with its denominator.
        `subject_id=None` = across every subject."""
        tally = ScaleTally()
        for r in self.for_student(student_id):
            if subject_id is not None and r.subject_id != subject_id:
                continue
            tally.add(r.scale, r.score, r.max_score, cycle_id=r.cycle_id)
        held = self.held(student_id)
        if subject_id is not None:
            counts = held.get(subject_id)
        else:
            counts = {s: sum(v[s] for v in held.values()) for s in SCALES}
        return tally.figures(counts)


def load_class_marks(db: Session, org_id: uuid.UUID, class_id: uuid.UUID,
                     student_ids: list[uuid.UUID] | None = None) -> ClassMarks:
    """Four queries for a whole class, whatever its size.

    `student_ids` narrows the *scores* fetched (one student's report card) but
    never the cycles — the denominator has to know about tests this student
    missed, which is the whole point of `S-118`."""
    out = ClassMarks()
    cycle_rows = db.execute(
        select(AssessmentCycle.id, AssessmentCycle.name, AssessmentCycle.date,
               AssessmentCycle.type, AssessmentCycle.scale, AssessmentCycle.subject_id,
               AssessmentCycle.student_ids, AssessmentCycle.locked_at, ExamType.name)
        .outerjoin(ExamType, ExamType.id == AssessmentCycle.exam_type_id)
        .where(AssessmentCycle.org_id == org_id,
               AssessmentCycle.class_id == class_id)).all()
    if not cycle_rows:
        return out

    subjects = dict(db.execute(
        select(Subject.id, Subject.name).where(Subject.org_id == org_id)).all())
    meta: dict[uuid.UUID, tuple] = {}
    for cid, name, d, sys_type, scale, subject_id, subset, locked_at, own_name in cycle_rows:
        norm = normalise_scale(scale, sys_type)
        out.cycles[cid] = (subject_id, norm,
                           {str(s) for s in subset} if subset else None)
        meta[cid] = (name, d, sys_type, own_name or type_label(sys_type), norm,
                     subject_id, subjects.get(subject_id), locked_at is not None)

    cids = list(meta)
    q = select(AssessmentScore).where(
        AssessmentScore.org_id == org_id, AssessmentScore.cycle_id.in_(cids),
        AssessmentScore.subject_id.is_not(None))
    if student_ids:
        q = q.where(AssessmentScore.student_id.in_(student_ids))
    scores = list(db.scalars(q))

    # `S-119`: this student's own script, per exam. One query for the class.
    paper_q = select(ScoreCapture.cycle_id, ScoreCapturePage.student_id,
                     ScoreCapturePage.object_key).join(
        ScoreCapturePage, ScoreCapturePage.capture_id == ScoreCapture.id).where(
        ScoreCapture.org_id == org_id, ScoreCapture.cycle_id.in_(cids),
        ScoreCapture.status != "discarded",
        ScoreCapturePage.student_id.is_not(None))
    papers = {(cid, sid): key for cid, sid, key in db.execute(paper_q).all()}

    for sc in scores:
        name, d, sys_type, label, scale, subject_id, subject_name, locked = meta[sc.cycle_id]
        key = papers.get((sc.cycle_id, sc.student_id))
        out.rows[sc.student_id].append(MarkRow(
            cycle_id=sc.cycle_id, cycle_name=name, date=d, system_type=sys_type,
            type_label=label, scale=scale, subject_id=subject_id,
            subject_name=subject_name, score=float(sc.score),
            max_score=float(sc.max_score), locked=locked,
            question_marks=sc.question_marks,
            paper_url=storage.url_for(key) if key else None))
    return out
