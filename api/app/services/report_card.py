"""Report card + analysis (V1-8, `D-81`) — two levels over one computation.

Level 1 is the card a school recognises: **numbers only**, per student and per
class. Level 2 is the analysis: per topic, skill abilities, and a per-subject
narrative written over figures the product already computed.

Neither level computes anything new. The marks come from `exam_marks`, the
never-pool arithmetic and the denominators from `core/exams.py`, and the
analysis's coverage, chapters and attendance from `GrowthService` — the same
call `/students/[id]` renders. That is the point: a report card that disagreed
with the growth report would be the `S-51` defect wearing a gown.

Access is `GrowthService`'s: an admin sees any student, a teacher only students
in a class they teach. Bands never appear on either level (P4) — this is the
surface most likely to be printed and handed to a family.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exams import SCALE_LABELS, SCALE_PURPOSE, type_label
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import AssessmentCycle, ClassSubject, SchoolClass, Student
from app.schemas.report_card import (
    AnalysisSkill,
    AnalysisSubject,
    AnalysisTopic,
    ClassReportCard,
    ClassReportCardColumn,
    ReportCard,
    ReportCardExam,
    ReportCardSubject,
    ScaleFigureOut,
    StudentAnalysis,
)
from app.services.ai.exam_analysis import subject_summary
from app.services.exam_marks import ClassMarks, load_class_marks
from app.services.growth import GrowthService
from app.services.school_clock import today_in

_MAX_ANALYSIS_TOPICS = 40


def _figure_out(f) -> ScaleFigureOut:
    return ScaleFigureOut(
        scale=f.scale, label=SCALE_LABELS[f.scale], purpose=SCALE_PURPOSE[f.scale],
        avg_pct=f.pct, tests_taken=f.tests_taken, tests_held=f.tests_held,
        sentence=f.sentence())


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


class ReportCardService:
    def __init__(self, db: Session):
        self.db = db

    # ── level 1: the report card ─────────────────────────────────────────────
    def for_student(self, m: CurrentMember, student_id: uuid.UUID) -> ReportCard:
        student = self._student(m, student_id)
        marks = (load_class_marks(self.db, m.org_id, student.class_id, [student.id])
                 if student.class_id else ClassMarks())
        return self._card(m, student, marks)

    def for_class(self, m: CurrentMember, class_id: uuid.UUID) -> ClassReportCard:
        """*"The class version is the same thing for everybody"* (`D-81`) — so it
        is literally the same builder, over one batched read rather than N."""
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        self._assert_class(m, class_id)
        students = list(self.db.scalars(select(Student).where(
            Student.org_id == m.org_id, Student.class_id == class_id,
            Student.status == "active").order_by(Student.full_name)))
        marks = load_class_marks(self.db, m.org_id, class_id)

        # One pass over the marks for the label/subject of each column, rather
        # than a scan per cycle — the remote DB is not the only thing that gets
        # slow at forty exams × forty children.
        seen: dict[uuid.UUID, tuple[str, str | None]] = {}
        for rows in marks.rows.values():
            for r in rows:
                seen.setdefault(r.cycle_id, (r.type_label, r.subject_name))
        columns = [ClassReportCardColumn(
            cycle_id=c.id, name=c.name,
            type_label=seen.get(c.id, (type_label(c.type), None))[0],
            scale=c.scale, date=c.date, subject_id=c.subject_id,
            subject_name=seen.get(c.id, ("", None))[1],
            total_marks=float(c.total_marks) if c.total_marks is not None else None)
            for c in self.db.scalars(
                select(AssessmentCycle)
                .where(AssessmentCycle.org_id == m.org_id,
                       AssessmentCycle.class_id == class_id,
                       AssessmentCycle.subject_id.is_not(None))
                .order_by(AssessmentCycle.date))]

        return ClassReportCard(
            class_id=class_id, class_label=_label(klass),
            as_of=today_in(m.org.timezone), columns=columns,
            students=[self._card(m, s, marks, klass) for s in students])

    def _card(self, m: CurrentMember, student: Student, marks: ClassMarks,
              klass: SchoolClass | None = None) -> ReportCard:
        klass = klass or (self.db.get(SchoolClass, student.class_id)
                          if student.class_id else None)
        rows = marks.for_student(student.id)
        by_subject: dict[uuid.UUID | None, list] = {}
        for r in rows:
            by_subject.setdefault(r.subject_id, []).append(r)

        subjects = [ReportCardSubject(
            subject_id=sid,
            subject_name=next((r.subject_name for r in srows), None),
            exams=[ReportCardExam(
                cycle_id=r.cycle_id, name=r.cycle_name, type_label=r.type_label,
                scale=r.scale, date=r.date, score=r.score, max_score=r.max_score,
                pct=r.pct, locked=r.locked, paper_url=r.paper_url) for r in srows],
            figures=[_figure_out(f) for f in marks.figures(student.id, sid)])
            for sid, srows in sorted(
                by_subject.items(), key=lambda kv: (next(
                    (r.subject_name for r in kv[1]), "") or ""))]

        return ReportCard(
            student_id=student.id, full_name=student.full_name,
            roll_no=student.roll_no, admission_no=student.admission_no,
            class_label=_label(klass) if klass else None,
            as_of=today_in(m.org.timezone), subjects=subjects,
            figures=[_figure_out(f) for f in marks.figures(student.id)])

    # ── level 2: the analysis ────────────────────────────────────────────────
    def analysis(self, m: CurrentMember, student_id: uuid.UUID) -> StudentAnalysis:
        """Per topic, skill abilities and a per-subject narrative — over the
        growth report's own figures, never a second computation of them."""
        student = self._student(m, student_id)
        growth = GrowthService(self.db).growth(m, student_id)
        marks = (load_class_marks(self.db, m.org_id, student.class_id, [student.id])
                 if student.class_id else ClassMarks())
        # class_subject → subject, in one query rather than one per subject.
        cs_subject = dict(self.db.execute(
            select(ClassSubject.id, ClassSubject.subject_id).where(
                ClassSubject.id.in_([g.class_subject_id for g in growth.subjects]))
            ).all()) if growth.subjects else {}

        subjects: list[AnalysisSubject] = []
        for g in growth.subjects:
            topics: list[AnalysisTopic] = []
            for ch in g.chapters:
                for t in ch.topics:
                    if len(topics) >= _MAX_ANALYSIS_TOPICS:
                        break
                    topics.append(AnalysisTopic(
                        title=t.title, status=t.status,
                        missed_while_absent=t.student_attendance == "absent"))
            subject_id = cs_subject.get(g.class_subject_id)
            figures = [_figure_out(f) for f in marks.figures(student.id, subject_id)]
            recent = "; ".join(
                f"{s.cycle_name} {s.score:g}/{s.max_score:g}" for s in g.scores[-3:])
            source, text = subject_summary({
                "student": student.full_name, "subject": g.subject_name,
                "figures": [f.sentence for f in figures if f.tests_taken],
                "recent": recent,
                "coverage": (f"{g.coverage_taught:g} of {g.coverage_total} topics"
                             if g.coverage_total else None),
                "attendance_pct": g.attendance.pct,
                "missed": sum(1 for ch in g.chapters for t in ch.topics
                              if t.student_attendance == "absent"),
            })
            subjects.append(AnalysisSubject(
                subject_id=subject_id,
                subject_name=g.subject_name, teacher_name=g.teacher_name,
                figures=figures,
                coverage_taught=g.coverage_taught, coverage_total=g.coverage_total,
                coverage_pct=g.coverage_pct, attendance_pct=g.attendance.pct,
                topics=topics, summary=text, summary_source=source))

        return StudentAnalysis(
            student_id=student.id, full_name=student.full_name,
            class_label=growth.class_label, as_of=today_in(m.org.timezone),
            attendance_pct=growth.attendance.pct,
            figures=[_figure_out(f) for f in marks.figures(student.id)],
            subjects=subjects,
            skills=[AnalysisSkill(
                skill_area=s.skill_area, score=s.score, max_score=s.max_score,
                pct=round(s.score / s.max_score * 100, 1) if s.max_score else None)
                for s in growth.skills],
            strengths=growth.strengths, growth_areas=growth.growth_areas,
            summary=" ".join(s.summary for s in subjects[:2]).strip(),
            summary_source=subjects[0].summary_source if subjects else "fixture")

    # ── helpers ──────────────────────────────────────────────────────────────
    def _student(self, m: CurrentMember, student_id: uuid.UUID) -> Student:
        student = self.db.scalar(select(Student).where(
            Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        # One access rule for every student-level report, and it is the growth
        # report's — a second implementation here would be a leak or a blackout.
        GrowthService(self.db)._assert_can_view(m, student)  # noqa: SLF001
        return student

    def _assert_class(self, m: CurrentMember, class_id: uuid.UUID) -> None:
        if m.is_coordinator_up:
            return
        teaches = self.db.scalar(select(ClassSubject.id).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
            ClassSubject.teacher_member_id == m.membership.id).limit(1))
        if teaches is None:
            raise ForbiddenError("You can open report cards only for classes you teach.",
                                 code="not_your_class")
