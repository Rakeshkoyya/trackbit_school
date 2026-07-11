"""Classroom capture (M2, SPRD §5.2) — My Day, quick log, homework, compliance.

Every capture is org-scoped and either by the teacher who owns the class-subject
or a coordinator/director. Posting homework notifies guardians immediately (the
teacher's payback, P3) with plain homework text only — never band/tier info (P4).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassPeriod,
    ClassSubject,
    Guardian,
    HomeworkAssignment,
    HomeworkCheck,
    LessonLog,
    LessonObservation,
    Membership,
    PlanEntry,
    SchoolClass,
    Student,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    TimetableSlot,
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
    ObservationConceptOut,
    ObservationSectionIn,
    ObservationSectionOut,
    ObservationsOut,
    ObservationStudentOut,
)
from app.schemas.periods import (
    PeriodCardOut,
    PeriodHomeworkOut,
    PeriodPlanOut,
)
from app.services.attendance import AttendanceService
from app.services.notify_guardian import notify_guardians
from app.services.periods import assert_can_take_class, find_period, get_or_create_period
from app.services.planner import PlannerService
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

        # Today's periods straight from the timetable (V2-P1 §5.4), each resolved on
        # its OWN period row (V2-P6) — two Maths periods on one day are independent
        # cards with independent topics, not two views of one class-subject.
        day_slots = TimetableService(self.db).teacher_day(m, today)
        att_service = AttendanceService(self.db)
        class_ids = list({ts.class_id for ts in day_slots})
        att = att_service.period_states(m.org_id, class_ids, today)
        roster_sizes = att_service.roster_sizes(m.org_id, class_ids)

        period_ids = [s["period_id"] for s in att.values() if s.get("period_id")]
        logs_by_period = {
            log.period_id: log for log in self.db.scalars(
                select(LessonLog).where(
                    LessonLog.org_id == m.org_id, LessonLog.period_id.in_(period_ids)))
        } if period_ids else {}

        hw_cs = set(self.db.scalars(
            select(HomeworkAssignment.class_subject_id).where(
                HomeworkAssignment.org_id == m.org_id, HomeworkAssignment.date == today)))

        assignment = self._assign_topics(
            m.org_id, monday, day_slots,
            {(ts.class_id, ts.period_no): att.get((ts.class_id, ts.period_no), {}).get("period_id")
             for ts in day_slots},
            logs_by_period)

        periods: list[MyDayPeriod] = []
        for ts in day_slots:
            state = att.get((ts.class_id, ts.period_no), {})
            topic_id, topic_title, _unit, logged = assignment[(ts.class_id, ts.period_no)]
            periods.append(MyDayPeriod(
                period_no=ts.period_no, class_subject_id=ts.class_subject_id,
                class_id=ts.class_id, class_label=ts.class_label, subject_name=ts.subject_name,
                planned_topic=topic_title, planned_topic_id=topic_id, logged=logged,
                period_id=state.get("period_id"),
                status=state.get("status", "held"),
                opened=state.get("period_id") is not None,
                closed=state.get("closed", False),
                attendance_marked=state.get("marked", False),
                roster_count=state.get("roster_count", roster_sizes.get(ts.class_id, 0)),
                present_count=state.get("present_count"),
                absent_count=state.get("absent_count"),
                late_count=state.get("late_count"),
                homework_set=ts.class_subject_id in hw_cs))
        periods.sort(key=lambda p: p.period_no)
        return MyDayOut(date=today, classes=classes, periods=periods, homework_pending=pending)

    # ── per-period topic resolution (V2-P6) ──────────────────────────────────
    def _week_topics(self, org_id: uuid.UUID, cs_id: uuid.UUID, monday: date):
        """This week's planned topics for a class-subject, in syllabus order."""
        return self.db.execute(
            select(SyllabusTopic.id, SyllabusTopic.title, SyllabusUnit.title)
            .join(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
            .join(PlanEntry, PlanEntry.topic_id == SyllabusTopic.id)
            .where(PlanEntry.org_id == org_id, PlanEntry.class_subject_id == cs_id,
                   PlanEntry.week_start == monday)
            .order_by(SyllabusUnit.position, SyllabusTopic.position)
        ).all()

    def _assign_topics(self, org_id: uuid.UUID, monday: date, slots, period_ids, logs_by_period):
        """(class_id, period_no) → (topic_id, topic_title, unit_title, logged).

        A period that already has a lesson log shows what was actually taught. The
        rest consume this week's remaining planned topics in period order, so a
        second period of the same subject gets the NEXT topic, not a repeat of the
        first. Topics logged on any earlier date are already excluded."""
        out: dict[tuple[uuid.UUID, int], tuple] = {}
        by_cs: dict[uuid.UUID, list] = {}
        for s in slots:
            by_cs.setdefault(s.class_subject_id, []).append(s)

        for cs_id, cs_slots in by_cs.items():
            logged_ids = set(self.db.scalars(
                select(LessonLog.topic_id).where(
                    LessonLog.org_id == org_id, LessonLog.class_subject_id == cs_id,
                    LessonLog.topic_id.is_not(None))))
            titles = {tid: (title, unit) for tid, title, unit in
                      self._week_topics(org_id, cs_id, monday)}
            remaining = [(tid, t, u) for tid, (t, u) in titles.items() if tid not in logged_ids]
            cursor = 0
            for s in sorted(cs_slots, key=lambda x: x.period_no):
                pid = period_ids.get((s.class_id, s.period_no))
                log = logs_by_period.get(pid) if pid else None
                if log is not None:
                    title, unit = titles.get(log.topic_id, (None, None))
                    if title is None and log.topic_id is not None:
                        title = self.db.scalar(
                            select(SyllabusTopic.title).where(SyllabusTopic.id == log.topic_id))
                    out[(s.class_id, s.period_no)] = (log.topic_id, title, unit, True)
                    continue
                if cursor < len(remaining):
                    tid, title, unit = remaining[cursor]
                    cursor += 1
                    out[(s.class_id, s.period_no)] = (tid, title, unit, False)
                else:
                    # Week's plan exhausted — the card shows no suggestion rather
                    # than re-proposing a topic the class already covered.
                    out[(s.class_id, s.period_no)] = (None, None, None, False)
        return out

    # ── quick log (CL-2) ─────────────────────────────────────────────────────
    def _slots_for_cs(self, org_id: uuid.UUID, cs_id: uuid.UUID, d: date) -> list[TimetableSlot]:
        """That class-subject's timetabled periods on `d`, per the grid effective then."""
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.class_subject_id == cs_id,
                TimetableSlot.weekday == d.weekday(), TimetableSlot.effective_from <= d,
                or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d))
            .order_by(TimetableSlot.period_no)))

    def _resolve_log_period(
        self, m: CurrentMember, cs: ClassSubject, d: date, body: LessonLogIn,
    ) -> ClassPeriod | None:
        """Which period occurrence does this log belong to?

        Explicit `period_id` or `period_no` wins. Otherwise fall back to the grid:
        attach to the earliest of today's slots for this class-subject that has no
        log yet — so a plain quick log still lands on a period, and a teacher
        quick-logging a double period fills period 1 then period 2. With no slot at
        all (nothing timetabled) the log stays period-less, as it did before V2-P6."""
        if body.period_id is not None:
            period = self.db.scalar(select(ClassPeriod).where(
                ClassPeriod.id == body.period_id, ClassPeriod.org_id == m.org_id))
            if period is None:
                raise NotFoundError("Period")
            return period
        if body.period_no is not None:
            return get_or_create_period(self.db, m, cs.class_id, d, body.period_no, cs.id)

        slots = self._slots_for_cs(m.org_id, cs.id, d)
        if not slots:
            return None
        taken = set(self.db.scalars(
            select(ClassPeriod.period_no)
            .join(LessonLog, LessonLog.period_id == ClassPeriod.id)
            .where(ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == cs.class_id,
                   ClassPeriod.date == d)))
        for s in slots:
            if s.period_no not in taken:
                return get_or_create_period(self.db, m, cs.class_id, d, s.period_no, cs.id)
        return get_or_create_period(self.db, m, cs.class_id, d, slots[-1].period_no, cs.id)

    def log(self, m: CurrentMember, body: LessonLogIn) -> LessonLogOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        period = self._resolve_log_period(m, cs, d, body)

        # Dedupe within the period when there is one, else within the day (the
        # pre-V2-P6 key). Mirrors the two partial unique indexes on lesson_logs.
        cond = ([LessonLog.period_id == period.id] if period is not None
                else [LessonLog.class_subject_id == cs.id, LessonLog.date == d,
                      LessonLog.period_id.is_(None)])
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
                        topic_id=body.topic_id, coverage=body.coverage, note=body.note,
                        period_id=period.id if period is not None else None)
        self.db.add(log)
        self.db.flush()
        return LessonLogOut.model_validate(log)

    # ── the period card (V2-P6) ──────────────────────────────────────────────
    def period_card(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
                    on_date: date | None = None) -> PeriodCardOut:
        """Everything the period-detail page needs, in one call. Purely a read —
        the period row is created by "Start attendance", not by opening the page."""
        assert_can_take_class(self.db, m, class_id, None)
        d = on_date or self._today(m)
        monday = d - timedelta(days=d.weekday())
        period = find_period(self.db, m.org_id, class_id, d, period_no)

        cs_id = period.class_subject_id if period else None
        if cs_id is None:
            cs_id = self.db.scalar(
                select(TimetableSlot.class_subject_id).where(
                    TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == class_id,
                    TimetableSlot.weekday == d.weekday(), TimetableSlot.period_no == period_no,
                    TimetableSlot.effective_from <= d,
                    or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d)))

        sheet = AttendanceService(self.db).roster(m, class_id, period_no, d)
        subject_name = self.db.scalar(
            select(Subject.name).join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(ClassSubject.id == cs_id)) if cs_id else None

        plan = PeriodPlanOut()
        homework: list[PeriodHomeworkOut] = []
        if cs_id is not None:
            slots = self._slots_for_cs(m.org_id, cs_id, d)
            period_ids = {
                (p.class_id, p.period_no): p.id for p in self.db.scalars(
                    select(ClassPeriod).where(
                        ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
                        ClassPeriod.date == d))}
            logs_by_period = {
                log.period_id: log for log in self.db.scalars(
                    select(LessonLog).where(
                        LessonLog.org_id == m.org_id, LessonLog.class_subject_id == cs_id,
                        LessonLog.date == d, LessonLog.period_id.is_not(None)))}
            assignment = self._assign_topics(m.org_id, monday, slots, period_ids, logs_by_period)
            topic_id, title, unit, logged = assignment.get(
                (class_id, period_no), (None, None, None, False))
            log = logs_by_period.get(period.id) if period else None
            plan = PeriodPlanOut(
                planned_topic_id=None if logged else topic_id,
                planned_topic_title=None if logged else title,
                planned_unit_title=None if logged else unit,
                logged_topic_id=log.topic_id if log else None,
                logged_coverage=log.coverage if log else None,
                progress=PlannerService(self.db).topic_progress(m, cs_id))
            homework = [
                PeriodHomeworkOut(id=h.id, text=h.text, student_id=h.student_id,
                                  due_date=h.due_date)
                for h in self.db.scalars(
                    select(HomeworkAssignment).where(
                        HomeworkAssignment.org_id == m.org_id,
                        HomeworkAssignment.class_subject_id == cs_id,
                        HomeworkAssignment.date == d).order_by(HomeworkAssignment.created_at))]

        return PeriodCardOut(
            class_id=class_id, class_label=sheet.class_label, period_no=period_no, date=d,
            class_subject_id=cs_id, subject_name=subject_name,
            period_id=period.id if period else None,
            status=period.status if period else "held",
            not_held_reason=period.not_held_reason if period else None,
            opened=period is not None,
            closed=period is not None and period.closed_at is not None,
            attendance_marked=sheet.marked, roster=sheet.roster,
            roster_count=len(sheet.roster),
            present_count=sheet.present_count if sheet.marked else None,
            absent_count=sheet.absent_count if sheet.marked else None,
            late_count=sheet.late_count if sheet.marked else None,
            plan=plan, homework=homework)

    # ── deep log — lesson observations (optional, exception-only) ────────────
    def _observation_scope(self, m: CurrentMember, body: ObservationSectionIn,
                           d: date) -> ClassPeriod | None:
        """Resolve which period occurrence the section belongs to (same rules as
        the lesson log): explicit id, explicit number, else day-scoped."""
        if body.period_id is not None:
            period = self.db.scalar(select(ClassPeriod).where(
                ClassPeriod.id == body.period_id, ClassPeriod.org_id == m.org_id))
            if period is None:
                raise NotFoundError("Period")
            return period
        if body.period_no is not None:
            cs = self._cs(m.org_id, body.class_subject_id)
            return get_or_create_period(self.db, m, cs.class_id, d, body.period_no, cs.id)
        return None

    def save_observation_section(self, m: CurrentMember,
                                 body: ObservationSectionIn) -> ObservationsOut:
        """Full-replace one section's rows — concept rows plus only the tapped
        per-student deviations. An empty `concepts` list keeps just the section
        row ("we did Vocabulary", nothing deeper)."""
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        period = self._observation_scope(m, body, d)
        period_id = period.id if period is not None else None

        # Per-student rows must be students of this class.
        student_ids = {s.student_id for c in body.concepts for s in c.students}
        if student_ids:
            in_class = set(self.db.scalars(select(Student.id).where(
                Student.id.in_(student_ids), Student.org_id == m.org_id,
                Student.class_id == cs.class_id)))
            if in_class != student_ids:
                raise NotFoundError("Student")

        for row in self.db.scalars(select(LessonObservation).where(
                LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d,
                LessonObservation.period_id.is_(None) if period_id is None
                else LessonObservation.period_id == period_id,
                LessonObservation.section == body.section)):
            self.db.delete(row)
        self.db.flush()

        common = {"org_id": m.org_id, "class_subject_id": cs.id, "date": d,
                  "period_id": period_id, "member_id": m.membership.id,
                  "section": body.section}
        if not body.concepts:
            self.db.add(LessonObservation(**common))
        for c in body.concepts:
            self.db.add(LessonObservation(**common, concept=c.concept))
            for s in c.students:
                self.db.add(LessonObservation(**common, concept=c.concept,
                                              student_id=s.student_id, rating=s.rating,
                                              note=s.note))
        self.db.flush()
        return self.observations(m, cs.id, d, period_id)

    def delete_observation_section(self, m: CurrentMember, class_subject_id: uuid.UUID,
                                   section: str, on_date: date | None = None,
                                   period_id: uuid.UUID | None = None) -> None:
        """Remove a named section from the day. Omitting period_id removes it
        wherever it sits (period-scoped or day-scoped) — the teacher is deleting
        "the Vocabulary section", not a storage detail."""
        cs = self._cs(m.org_id, class_subject_id)
        self._can_capture(m, cs)
        d = on_date or self._today(m)
        cond = [LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d,
                LessonObservation.section == section]
        if period_id is not None:
            cond.append(LessonObservation.period_id == period_id)
        for row in self.db.scalars(select(LessonObservation).where(*cond)):
            self.db.delete(row)
        self.db.flush()

    def observations(self, m: CurrentMember, class_subject_id: uuid.UUID,
                     on_date: date | None = None,
                     period_id: uuid.UUID | None = None) -> ObservationsOut:
        """The deep log for one class-subject day (or one period of it), grouped
        section → concept → tapped students."""
        cs = self._cs(m.org_id, class_subject_id)
        assert_can_take_class(self.db, m, cs.class_id, None)
        d = on_date or self._today(m)
        cond = [LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d]
        if period_id is not None:
            cond.append(LessonObservation.period_id == period_id)
        rows = list(self.db.execute(
            select(LessonObservation, Student.full_name)
            .outerjoin(Student, Student.id == LessonObservation.student_id)
            .where(*cond).order_by(LessonObservation.created_at)).all())

        sections: dict[tuple[uuid.UUID | None, str], ObservationSectionOut] = {}
        concepts: dict[tuple[uuid.UUID | None, str, str | None], ObservationConceptOut] = {}
        for obs, student_name in rows:
            skey = (obs.period_id, obs.section)
            if skey not in sections:
                sections[skey] = ObservationSectionOut(
                    section=obs.section, period_id=obs.period_id)
            if obs.concept is None and obs.student_id is None:
                continue  # bare section row — nothing deeper recorded
            ckey = (*skey, obs.concept)
            if ckey not in concepts:
                concepts[ckey] = ObservationConceptOut(concept=obs.concept)
                sections[skey].concepts.append(concepts[ckey])
            if obs.student_id is not None:
                concepts[ckey].students.append(ObservationStudentOut(
                    student_id=obs.student_id, full_name=student_name or "?",
                    rating=obs.rating or "needs_work", note=obs.note))
        return ObservationsOut(class_subject_id=cs.id, date=d,
                               sections=list(sections.values()))

    # ── homework (CL-2) + guardian notify (P3) ───────────────────────────────
    def add_homework(self, m: CurrentMember, body: HomeworkIn) -> HomeworkOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        # A per-student addition must be a student of this class (V2-P3 §5.5).
        if body.student_id is not None:
            in_class = self.db.scalar(
                select(Student.id).where(
                    Student.id == body.student_id, Student.org_id == m.org_id,
                    Student.class_id == cs.class_id))
            if in_class is None:
                raise NotFoundError("Student")
        hw = HomeworkAssignment(org_id=m.org_id, class_subject_id=cs.id, date=d,
                                text=body.text, due_date=body.due_date, student_id=body.student_id)
        self.db.add(hw)
        self.db.flush()

        klass = self.db.get(SchoolClass, cs.class_id)
        subject = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        # Notify the one student's guardians for a per-student note, else the class.
        guardian_q = (
            select(Guardian.phone, Guardian.notify_opt_out)
            .join(Student, Student.id == Guardian.student_id)
            .where(Student.org_id == m.org_id))
        guardian_q = (guardian_q.where(Student.id == body.student_id) if body.student_id
                      else guardian_q.where(Student.class_id == cs.class_id))
        guardians = list(self.db.execute(guardian_q).all())
        due = f" (due {body.due_date})" if body.due_date else ""
        message = f"Homework for {_label(klass)} {subject}: {body.text}{due}"
        count = notify_guardians([(p, o) for p, o in guardians], message)
        hw.notified_at = datetime.now(UTC)
        self.db.flush()
        return HomeworkOut(id=hw.id, class_subject_id=cs.id, date=d, text=hw.text,
                           due_date=hw.due_date, student_id=hw.student_id, notified_count=count)

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
