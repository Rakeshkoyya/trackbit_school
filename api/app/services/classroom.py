"""Classroom capture (M2, SPRD §5.2) — My Day, quick log, homework, compliance.

Every capture is org-scoped and either by the teacher who owns the class-subject
or a coordinator/director. Posting homework notifies guardians immediately (the
teacher's payback, P3) with plain homework text only — never band/tier info (P4).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    Guardian,
    HomeworkAssignment,
    HomeworkCheck,
    LessonLog,
    Membership,
    PlanEntry,
    SchoolClass,
    Student,
    Subject,
    SyllabusTopic,
    User,
)
from app.schemas.classroom import (
    ComplianceOut,
    ComplianceRow,
    HomeworkCheckIn,
    HomeworkIn,
    HomeworkOut,
    HomeworkPending,
    LessonLogIn,
    LessonLogOut,
    MyDayClass,
    MyDayOut,
    MyDayPeriod,
)
from app.services.notify_guardian import notify_guardians
from app.services.timetable import TimetableService


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class ClassroomService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _cs(self, org_id: uuid.UUID, cs_id: uuid.UUID) -> ClassSubject:
        cs = self.db.scalar(
            select(ClassSubject).where(ClassSubject.id == cs_id, ClassSubject.org_id == org_id)
        )
        if cs is None:
            raise NotFoundError("Class-subject")
        return cs

    def _can_capture(self, m: CurrentMember, cs: ClassSubject) -> None:
        if not (m.is_coordinator_up or cs.teacher_member_id == m.membership.id):
            raise ForbiddenError("You don't teach this class.", code="not_your_class")

    def _active_year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)
            )
        )

    # ── My Day (CL-1) ────────────────────────────────────────────────────────
    def my_day(self, m: CurrentMember, on_date: date | None = None) -> MyDayOut:
        today = on_date or self._today(m)
        monday = today - timedelta(days=today.weekday())
        year = self._active_year(m.org_id)
        if year is None:
            return MyDayOut(date=today, classes=[], periods=[], homework_pending=[])

        rows = self.db.execute(
            select(ClassSubject, Subject.name, SchoolClass)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.teacher_member_id == m.membership.id,
                   SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, Subject.name)
        ).all()

        classes: list[MyDayClass] = []
        for cs, subject_name, klass in rows:
            logged_ids = set(self.db.scalars(
                select(LessonLog.topic_id).where(LessonLog.class_subject_id == cs.id)))
            planned = self.db.execute(
                select(PlanEntry.topic_id, SyllabusTopic.title)
                .join(SyllabusTopic, SyllabusTopic.id == PlanEntry.topic_id)
                .where(PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs.id,
                       PlanEntry.week_start == monday)
            ).all()
            topic, topic_id = None, None
            for tid, title in planned:
                if tid not in logged_ids:
                    topic, topic_id = title, tid
                    break
            if topic is None and planned:
                topic_id, topic = planned[0]
            logged_today = self.db.scalar(
                select(LessonLog.id).where(
                    LessonLog.class_subject_id == cs.id, LessonLog.date == today).limit(1)
            ) is not None
            hw_today = self.db.scalar(
                select(HomeworkAssignment.id).where(
                    HomeworkAssignment.class_subject_id == cs.id,
                    HomeworkAssignment.date == today).limit(1)
            ) is not None
            classes.append(MyDayClass(
                class_subject_id=cs.id, class_label=_label(klass), subject_name=subject_name,
                planned_topic=topic, planned_topic_id=topic_id,
                logged=logged_today, homework_set=hw_today))

        pending: list[HomeworkPending] = []
        cs_ids = [cs.id for cs, _, _ in rows]
        if cs_ids:
            yest = today - timedelta(days=1)
            hw_rows = self.db.execute(
                select(HomeworkAssignment, Subject.name, SchoolClass)
                .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
                .where(HomeworkAssignment.org_id == m.org_id,
                       HomeworkAssignment.class_subject_id.in_(cs_ids),
                       HomeworkAssignment.date == yest)
            ).all()
            for hw, sname, klass in hw_rows:
                if not self.db.scalar(
                    select(HomeworkCheck.id).where(HomeworkCheck.assignment_id == hw.id).limit(1)
                ):
                    pending.append(HomeworkPending(
                        assignment_id=hw.id, class_label=_label(klass),
                        subject_name=sname, text=hw.text))

        # Today's periods straight from the timetable (V2-P1 §5.4): the teacher's
        # slots for today, enriched with the planned topic / logged state we already
        # computed per class-subject above.
        by_cs = {c.class_subject_id: c for c in classes}
        periods: list[MyDayPeriod] = []
        for ts in TimetableService(self.db).teacher_day(m, today):
            c = by_cs.get(ts.class_subject_id)
            periods.append(MyDayPeriod(
                period_no=ts.period_no, class_subject_id=ts.class_subject_id,
                class_label=ts.class_label, subject_name=ts.subject_name,
                planned_topic=c.planned_topic if c else None,
                planned_topic_id=c.planned_topic_id if c else None,
                logged=c.logged if c else False))
        periods.sort(key=lambda p: p.period_no)
        return MyDayOut(date=today, classes=classes, periods=periods, homework_pending=pending)

    # ── quick log (CL-2) ─────────────────────────────────────────────────────
    def log(self, m: CurrentMember, body: LessonLogIn) -> LessonLogOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        cond = [LessonLog.class_subject_id == cs.id, LessonLog.date == d]
        cond.append(LessonLog.topic_id.is_(None) if body.topic_id is None
                    else LessonLog.topic_id == body.topic_id)
        existing = self.db.scalar(select(LessonLog).where(*cond))
        if existing:
            existing.coverage = body.coverage
            existing.note = body.note
            existing.member_id = m.membership.id
            self.db.flush()
            return LessonLogOut.model_validate(existing)
        log = LessonLog(org_id=m.org_id, class_subject_id=cs.id, date=d, member_id=m.membership.id,
                        topic_id=body.topic_id, coverage=body.coverage, note=body.note)
        self.db.add(log)
        self.db.flush()
        return LessonLogOut.model_validate(log)

    # ── homework (CL-2) + guardian notify (P3) ───────────────────────────────
    def add_homework(self, m: CurrentMember, body: HomeworkIn) -> HomeworkOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        hw = HomeworkAssignment(org_id=m.org_id, class_subject_id=cs.id, date=d,
                                text=body.text, due_date=body.due_date)
        self.db.add(hw)
        self.db.flush()

        klass = self.db.get(SchoolClass, cs.class_id)
        subject = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        guardians = list(self.db.execute(
            select(Guardian.phone, Guardian.notify_opt_out)
            .join(Student, Student.id == Guardian.student_id)
            .where(Student.org_id == m.org_id, Student.class_id == cs.class_id)
        ).all())
        due = f" (due {body.due_date})" if body.due_date else ""
        message = f"Homework for {_label(klass)} {subject}: {body.text}{due}"
        count = notify_guardians([(p, o) for p, o in guardians], message)
        hw.notified_at = datetime.now(UTC)
        self.db.flush()
        return HomeworkOut(id=hw.id, class_subject_id=cs.id, date=d, text=hw.text,
                           due_date=hw.due_date, notified_count=count)

    def check_homework(self, m: CurrentMember, assignment_id: uuid.UUID,
                       body: HomeworkCheckIn) -> HomeworkOut:
        hw = self.db.scalar(
            select(HomeworkAssignment).where(
                HomeworkAssignment.id == assignment_id, HomeworkAssignment.org_id == m.org_id)
        )
        if hw is None:
            raise NotFoundError("Homework")
        self._can_capture(m, self._cs(m.org_id, hw.class_subject_id))
        check = self.db.scalar(
            select(HomeworkCheck).where(HomeworkCheck.assignment_id == assignment_id))
        if check is None:
            check = HomeworkCheck(org_id=m.org_id, assignment_id=assignment_id)
            self.db.add(check)
        check.done_count = body.done_count
        check.total_count = body.total_count
        check.checked_at = datetime.now(UTC)
        self.db.flush()
        return HomeworkOut(id=hw.id, class_subject_id=hw.class_subject_id, date=hw.date,
                           text=hw.text, due_date=hw.due_date, notified_count=0)

    # ── compliance (CL-4) — coordinator/director ─────────────────────────────
    def compliance(self, m: CurrentMember, on_date: date | None = None) -> ComplianceOut:
        today = on_date or self._today(m)
        year = self._active_year(m.org_id)
        rows: list[ComplianceRow] = []
        if year is not None:
            data = self.db.execute(
                select(ClassSubject, Subject.name, SchoolClass, User.name)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
                .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .where(ClassSubject.org_id == m.org_id, SchoolClass.academic_year_id == year.id)
                .order_by(SchoolClass.name, Subject.name)
            ).all()
            for cs, sname, klass, teacher in data:
                logged = self.db.scalar(
                    select(LessonLog.id).where(
                        LessonLog.class_subject_id == cs.id, LessonLog.date == today).limit(1)
                ) is not None
                rows.append(ComplianceRow(
                    class_subject_id=cs.id, class_label=_label(klass), subject_name=sname,
                    teacher_name=teacher, logged=logged))
        return ComplianceOut(date=today, logged_count=sum(1 for r in rows if r.logged),
                             total=len(rows), rows=rows)
