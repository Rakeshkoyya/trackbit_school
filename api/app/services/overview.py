"""Post-setup read models (V2-P10) — what the admin sees once ingestion is done.

Everything here is a **computed join over data the wizard already stored**. No new
tables, no denormalised cache: the numbers are derived on read, so an edit made
anywhere (a teacher reassigned, a chapter deleted, a holiday added) shows up
immediately and can never go stale. That is the same rule the forecast follows (P2).

Two read models:

  `school_overview`  the board: is this year sound? Every class, its roster, how
                     much of its timetable is filled, how many plans are approved,
                     and the worst forecast among its subjects.
  `class_overview`   one class in full: per subject, who teaches it, the weekly
                     period budget the admin *entered* versus the one the timetable
                     actually gives, syllabus size, and the plan's health.

The entered-vs-timetabled comparison is the point of the class screen. They are two
independent sources of truth today (`class_subjects.periods_per_week` is typed by
hand; the grid is drawn separately), and when they disagree every plan date for that
subject is wrong. Nothing surfaced that before.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    LessonLog,
    Membership,
    Plan,
    SchoolClass,
    Student,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    TimetableSlot,
    User,
)
from app.schemas.overview import (
    ClassOverviewOut,
    ClassRow,
    SchoolOverviewOut,
    SubjectRow,
    TeacherLoadRow,
    YearFacts,
)
from app.services.planner import PlannerService

# Severity, worst last. "none" (no plan drafted) outranks green — an unplanned
# subject is a real gap — but a red one is louder still, because it has a date on it.
_RAG_ORDER = {"green": 0, "none": 1, "amber": 2, "red": 3}


def _label(k: SchoolClass) -> str:
    return k.name + (f"-{k.section}" if k.section else "")


class OverviewService:
    def __init__(self, db: Session):
        self.db = db

    # ── shared loaders ───────────────────────────────────────────────────────
    def _year(self, org_id: uuid.UUID, year_id: uuid.UUID | None) -> AcademicYear | None:
        q = select(AcademicYear).where(AcademicYear.org_id == org_id)
        q = q.where(AcademicYear.id == year_id) if year_id else q.where(
            AcademicYear.is_active.is_(True))
        return self.db.scalar(q)

    def _roster_sizes(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        return dict(self.db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.org_id == org_id, Student.status == "active",
                   Student.class_id.is_not(None))
            .group_by(Student.class_id)).all())

    def _timetabled(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """class_subject_id → periods currently on the grid, per week."""
        return dict(self.db.execute(
            select(TimetableSlot.class_subject_id, func.count(TimetableSlot.id))
            .where(TimetableSlot.org_id == org_id, TimetableSlot.effective_to.is_(None))
            .group_by(TimetableSlot.class_subject_id)).all())

    def _syllabus_sizes(self, org_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, int, int]]:
        """class_subject_id → (chapters, topics, total est_periods)."""
        rows = self.db.execute(
            select(SyllabusUnit.class_subject_id,
                   func.count(func.distinct(SyllabusUnit.id)),
                   func.count(SyllabusTopic.id),
                   func.coalesce(func.sum(SyllabusTopic.est_periods), 0))
            .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id, isouter=True)
            .where(SyllabusUnit.org_id == org_id)
            .group_by(SyllabusUnit.class_subject_id)).all()
        return {r[0]: (r[1], r[2], int(r[3])) for r in rows}

    def _taught_topics(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """class_subject_id → distinct topics with at least one full-coverage log."""
        return dict(self.db.execute(
            select(LessonLog.class_subject_id, func.count(func.distinct(LessonLog.topic_id)))
            .where(LessonLog.org_id == org_id, LessonLog.coverage == "full",
                   LessonLog.topic_id.is_not(None))
            .group_by(LessonLog.class_subject_id)).all())

    def _plans(self, org_id: uuid.UUID) -> dict[uuid.UUID, Plan]:
        return {p.class_subject_id: p for p in self.db.scalars(
            select(Plan).where(Plan.org_id == org_id))}

    def _teacher_names(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        return dict(self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id)).all())

    # ── the board ────────────────────────────────────────────────────────────
    def school_overview(self, m: CurrentMember, year_id: uuid.UUID | None = None,
                        ) -> SchoolOverviewOut:
        year = self._year(m.org_id, year_id)
        if year is None:
            raise NotFoundError("Academic year")

        classes = list(self.db.scalars(
            select(SchoolClass).where(
                SchoolClass.org_id == m.org_id, SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, SchoolClass.section)))
        rosters = self._roster_sizes(m.org_id)
        timetabled = self._timetabled(m.org_id)
        plans = self._plans(m.org_id)
        syllabus = self._syllabus_sizes(m.org_id)

        cs_by_class: dict[uuid.UUID, list[ClassSubject]] = {}
        for cs in self.db.scalars(select(ClassSubject).where(ClassSubject.org_id == m.org_id)):
            cs_by_class.setdefault(cs.class_id, []).append(cs)

        rows: list[ClassRow] = []
        for k in classes:
            css = cs_by_class.get(k.id, [])
            forecasts = PlannerService(self.db).forecast(m, k.id)
            # The class inherits its most alarming subject: one red subject makes the
            # row red, however many greens sit beside it.
            statuses = [f.status for f in forecasts] or ["none"]
            worst = max(statuses, key=lambda s: _RAG_ORDER.get(s, 3))

            approved = sum(1 for cs in css
                           if (p := plans.get(cs.id)) and p.status == "approved")
            rows.append(ClassRow(
                class_id=k.id, label=_label(k),
                students=rosters.get(k.id, 0),
                subjects=len(css),
                subjects_without_teacher=sum(1 for cs in css if cs.teacher_member_id is None),
                subjects_without_syllabus=sum(1 for cs in css if cs.id not in syllabus),
                timetable_slots=sum(timetabled.get(cs.id, 0) for cs in css),
                plans_approved=approved, plans_total=len(css),
                worst_forecast=worst))

        exams = list(self.db.scalars(select(CalendarEvent).where(
            CalendarEvent.org_id == m.org_id, CalendarEvent.academic_year_id == year.id,
            CalendarEvent.type == "exam_block")))
        portions = self.db.scalar(select(func.count(ExamPortion.id)).where(
            ExamPortion.org_id == m.org_id)) or 0
        teachers = self.db.scalar(select(func.count(Membership.id)).where(
            Membership.org_id == m.org_id, Membership.org_role == "teacher")) or 0

        return SchoolOverviewOut(
            year=YearFacts(
                academic_year_id=year.id, label=year.label,
                start_date=year.start_date, end_date=year.end_date,
                periods_per_day=year.periods_per_day,
                terms=self.db.scalar(select(func.count(Term.id)).where(
                    Term.org_id == m.org_id, Term.academic_year_id == year.id)) or 0,
                exams=len(exams),
                exam_portions=portions,
                # An exam nobody mapped to a syllabus portion can never trigger the
                # "won't finish in time" warning. Worth showing on the board.
                exams_without_portions=sum(
                    1 for e in exams
                    if not self.db.scalar(select(func.count(ExamPortion.id)).where(
                        ExamPortion.exam_event_id == e.id))),
            ),
            teachers=teachers,
            students=sum(rosters.values()),
            classes=rows)

    # ── one class ────────────────────────────────────────────────────────────
    def class_overview(self, m: CurrentMember, class_id: uuid.UUID) -> ClassOverviewOut:
        k = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if k is None:
            raise NotFoundError("Class")

        year = self.db.get(AcademicYear, k.academic_year_id)
        timetabled = self._timetabled(m.org_id)
        syllabus = self._syllabus_sizes(m.org_id)
        taught = self._taught_topics(m.org_id)
        plans = self._plans(m.org_id)
        names = self._teacher_names(m.org_id)
        forecasts = {f.class_subject_id: f for f in PlannerService(self.db).forecast(m, class_id)}

        rows = self.db.execute(
            select(ClassSubject, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)).all()

        subjects: list[SubjectRow] = []
        for cs, subject_name in rows:
            chapters, topics, est = syllabus.get(cs.id, (0, 0, 0))
            plan = plans.get(cs.id)
            f = forecasts.get(cs.id)
            grid = timetabled.get(cs.id, 0)
            subjects.append(SubjectRow(
                class_subject_id=cs.id, subject_name=subject_name,
                teacher_member_id=cs.teacher_member_id,
                teacher_name=names.get(cs.teacher_member_id) if cs.teacher_member_id else None,
                periods_per_week=cs.periods_per_week,
                timetabled_periods=grid,
                # The disagreement that silently corrupts every plan date.
                periods_mismatch=bool(grid) and grid != cs.periods_per_week,
                chapters=chapters, topics=topics, est_periods=est,
                topics_taught=taught.get(cs.id, 0),
                plan_status=plan.status if plan else "none",
                plan_approved_at=plan.approved_at if plan else None,
                forecast=f.status if f else "none",
                weeks_behind=f.weeks_behind if f else None,
                baseline_finish=f.baseline_finish if f else None,
                projected_finish=f.projected_finish if f else None))

        return ClassOverviewOut(
            class_id=k.id, label=_label(k),
            academic_year_id=k.academic_year_id,
            year_label=year.label if year else "",
            students=self._roster_sizes(m.org_id).get(k.id, 0),
            class_teacher_name=names.get(k.class_teacher_member_id)
            if k.class_teacher_member_id else None,
            subjects=subjects)

    # ── teacher load ─────────────────────────────────────────────────────────
    def teacher_load(self, m: CurrentMember) -> list[TeacherLoadRow]:
        """Periods per week each teacher is actually timetabled for, from the grid.

        Not from `periods_per_week` — that's the intent; this is the commitment.
        A teacher at 40 periods across 6 classes is the kind of thing nobody
        notices until she burns out or a clash appears."""
        names = self._teacher_names(m.org_id)
        rows = self.db.execute(
            select(ClassSubject.teacher_member_id,
                   func.count(TimetableSlot.id),
                   func.count(func.distinct(ClassSubject.class_id)),
                   func.count(func.distinct(ClassSubject.subject_id)))
            .join(TimetableSlot, TimetableSlot.class_subject_id == ClassSubject.id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.teacher_member_id.is_not(None),
                   TimetableSlot.effective_to.is_(None))
            .group_by(ClassSubject.teacher_member_id)).all()
        loaded = {r[0]: r for r in rows}

        out: list[TeacherLoadRow] = []
        for mid in self.db.scalars(select(Membership.id).where(
                Membership.org_id == m.org_id, Membership.org_role == "teacher")):
            r = loaded.get(mid)
            out.append(TeacherLoadRow(
                member_id=mid, name=names.get(mid, "—"),
                periods_per_week=r[1] if r else 0,
                classes=r[2] if r else 0,
                subjects=r[3] if r else 0))
        out.sort(key=lambda t: (-t.periods_per_week, t.name))
        return out
