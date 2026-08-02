"""The exam's **Report** tab (V1-8, `D-80`).

An exam now opens on two tabs: **Score** — the roster and their marks, nothing
else — and **Report**, which is this. What a teacher and an admin arrive asking:

    "How did they actually do, and where was the difficulty?"

So the report says, in this order: a sentence, then the shape (distribution),
then **named rows** — who did not sit it, who is well below the class, who is
well above — then the question detail where a photo gave us it, then what the
class had actually been taught.

Four rules it is built against:

* **Participation rides beside every average** (the module's own honesty rule):
  an 88% average from 9 of 42 papers is not an 88% class.
* **No ranking.** A position in a class is the one number that changes a child's
  year and tells a teacher nothing they can act on. Rows are named with their
  mark and a stated criterion — *"more than 15 points below the class"* — never
  a rank, and never on a parent surface.
* **Question-level analysis is absent, not zero, for a hand-typed exam.** The
  marks exist only where somebody photographed a marked script (§4's
  reconciliation), and the screen says so in a word.
* **Coverage comes from `services/coverage.py`**, the one syllabus computation
  (`S-51`) — never re-derived here.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import PLANNED_TO_DATE
from app.core.exams import SCALE_LABELS, type_label
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    CalendarEvent,
    ClassSubject,
    ExamType,
    SchoolClass,
    Student,
    Subject,
)
from app.schemas.exam_report import (
    ExamReport,
    ExamReportQuestion,
    ExamReportRow,
)
from app.services.ai.exam_analysis import exam_summary
from app.services.coverage import coverage_rows
from app.services.insights.exams import BANDS
from app.services.periods import assert_can_take_class

# How far from the class average a mark has to be before the row is worth
# naming. A stated criterion, shown on screen — not a hidden threshold, and not
# a rank.
_GAP_POINTS = 15.0
_MAX_NAMED = 8


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


class ExamReportService:
    def __init__(self, db: Session):
        self.db = db

    def report(self, m: CurrentMember, cycle_id: uuid.UUID) -> ExamReport:
        c = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == cycle_id, AssessmentCycle.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Exam")
        if c.class_id is None or c.subject_id is None:
            raise ValidationError("That cycle has no single class-subject to report on.",
                                  code="use_grid")
        assert_can_take_class(self.db, m, c.class_id, None)

        klass = self.db.get(SchoolClass, c.class_id)
        subject = self.db.get(Subject, c.subject_id)
        own_type = self.db.scalar(select(ExamType.name).where(
            ExamType.id == c.exam_type_id)) if c.exam_type_id else None

        roster = list(self.db.scalars(
            select(Student).where(
                Student.org_id == m.org_id, Student.class_id == c.class_id,
                Student.status == "active").order_by(Student.full_name)))
        if c.student_ids:
            picked = {str(s) for s in c.student_ids}
            roster = [s for s in roster if str(s.id) in picked]
        scores = {sc.student_id: sc for sc in self.db.scalars(select(AssessmentScore).where(
            AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == c.id,
            AssessmentScore.subject_id == c.subject_id))}

        rows: list[ExamReportRow] = []
        tot_s = tot_x = 0.0
        for st in roster:
            sc = scores.get(st.id)
            if sc is None:
                continue
            tot_s += float(sc.score)
            tot_x += float(sc.max_score)
            rows.append(ExamReportRow(
                student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                score=float(sc.score), max_score=float(sc.max_score),
                pct=round(float(sc.score) / float(sc.max_score) * 100, 1)
                if sc.max_score else None))
        avg = round(tot_s / tot_x * 100, 1) if tot_x else None
        not_sat = [ExamReportRow(student_id=st.id, full_name=st.full_name,
                                 roll_no=st.roll_no, score=None, max_score=None, pct=None)
                   for st in roster if st.id not in scores]

        scored_rows = [r for r in rows if r.pct is not None]
        struggling = sorted(
            [r for r in scored_rows if avg is not None and r.pct < avg - _GAP_POINTS],
            key=lambda r: r.pct)[:_MAX_NAMED]
        strong = sorted(
            [r for r in scored_rows if avg is not None and r.pct > avg + _GAP_POINTS],
            key=lambda r: -r.pct)[:_MAX_NAMED]

        out = ExamReport(
            cycle_id=c.id, name=c.name, date=c.date,
            type_label=own_type or type_label(c.type), scale=c.scale,
            scale_label=SCALE_LABELS.get(c.scale, ""),
            class_id=c.class_id, class_label=_label(klass),
            subject_id=c.subject_id, subject_name=subject.name, topic=c.topic,
            total_marks=float(c.total_marks) if c.total_marks is not None else None,
            locked=c.locked_at is not None,
            roster=len(roster), scored=len(rows), avg_pct=avg,
            participation=round(len(rows) / len(roster), 3) if roster else None,
            rows=sorted(scored_rows, key=lambda r: -(r.pct or 0)),
            not_sat=not_sat, struggling=struggling, strong=strong,
            gap_points=_GAP_POINTS,
            distribution=self._distribution(scored_rows))

        out.questions, out.question_note = self._questions(scores.values())
        self._coverage(m, out, c)
        out.summary_source, out.summary = exam_summary({
            "exam": c.name, "class_label": out.class_label, "subject": subject.name,
            "type_label": out.type_label, "scale": c.scale, "topic": c.topic,
            "avg_pct": avg, "scored": len(rows), "roster": len(roster),
            "distribution": ", ".join(f"{b.label}: {b.count}" for b in out.distribution),
            "not_sat": [r.full_name for r in not_sat],
            "struggling": [f"{r.full_name} {r.pct:g}%" for r in struggling],
            "strong": [f"{r.full_name} {r.pct:g}%" for r in strong],
            "coverage": out.coverage_note,
            "has_questions": bool(out.questions),
            "hardest_question": out.questions[0].q if out.questions else None,
            "questions": ", ".join(
                f"Q{q.q} {q.avg_pct:g}%" for q in out.questions if q.avg_pct is not None),
        })
        return out

    # ── the shape ────────────────────────────────────────────────────────────
    @staticmethod
    def _distribution(rows: list[ExamReportRow]) -> list:
        from app.schemas.insights import ExamBand  # noqa: PLC0415

        counts = dict.fromkeys((name for _lo, _hi, name in BANDS), 0)
        for r in rows:
            for lo, hi, name in BANDS:
                if lo <= (r.pct or 0) < hi:
                    counts[name] += 1
                    break
        return [ExamBand(label=name, count=counts[name]) for _lo, _hi, name in BANDS]

    @staticmethod
    def _questions(scores) -> tuple[list[ExamReportQuestion], str | None]:
        """*"Which questions were most often wrong"* — from the marks the
        teacher wrote beside each question, transcribed off the photographed
        script. Sorted worst-first, because that is the order a teacher acts in.

        **Absent is a word, never a zero**: an exam typed in by hand has no
        question detail and the screen says exactly why."""
        totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
        order: list[str] = []
        for sc in scores:
            qs = sc.question_marks if isinstance(sc.question_marks, list) else None
            if not qs:
                continue
            for q in qs:
                if not isinstance(q, dict):
                    continue
                label = str(q.get("q") or "")
                mx = q.get("max")
                try:
                    got = float(q.get("score"))
                except (TypeError, ValueError):
                    continue
                if label not in totals:
                    order.append(label)
                acc = totals[label]
                acc[0] += got
                acc[1] += float(mx) if mx else 0.0
                acc[2] += 1
        if not totals:
            return [], "Question-level analysis needs a photo of the marked paper."
        out = [ExamReportQuestion(
            q=label, attempted=acc[2], avg_score=round(acc[0] / acc[2], 2) if acc[2] else None,
            max=round(acc[1] / acc[2], 2) if acc[2] and acc[1] else None,
            avg_pct=round(acc[0] / acc[1] * 100, 1) if acc[1] else None)
            for label, acc in ((k, totals[k]) for k in order)]
        # Worst first, and questions with no printed maximum (so no percentage)
        # sink to the bottom rather than being invented a denominator.
        out.sort(key=lambda q: (q.avg_pct is None, q.avg_pct if q.avg_pct is not None else 0))
        return out, None

    def _coverage(self, m: CurrentMember, out: ExamReport, c: AssessmentCycle) -> None:
        """What the class had actually been taught by the time they sat it —
        from `services/coverage.py`, the one syllabus computation (`S-51`).

        `S-115`'s `exam_event_id` is what makes the sharper question answerable:
        when the exam is linked to its planned block, the report names the block
        so *"we covered 70% of the portion — did the marks show it?"* is one
        screen, not two."""
        cs_id = self.db.scalar(select(ClassSubject.id).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == c.class_id,
            ClassSubject.subject_id == c.subject_id))
        if cs_id is None:
            return
        rows = coverage_rows(self.db, m.org_id, [cs_id])
        cov = rows.get(cs_id)
        if cov is None:
            return
        figure = cov.figure(PLANNED_TO_DATE)
        out.coverage_taught = figure.taught
        out.coverage_total = figure.total
        out.coverage_pct = figure.pct
        out.coverage_note = (f"{figure.taught:g} of {figure.total} planned topics taught"
                             if figure.total else "nothing planned for this subject yet")
        out.latest_topic = cov.last_topic_title
        if c.exam_event_id:
            out.exam_event_name = self.db.scalar(select(CalendarEvent.name).where(
                CalendarEvent.id == c.exam_event_id))
