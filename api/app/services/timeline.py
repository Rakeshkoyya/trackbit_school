"""Student timeline (V2-M7, SPRD2 §5.7) — period-by-period, assembled from the §4
join with ZERO new capture tables:

    timetable_slots × attendance × lesson_logs × checks × homework × sessions

For a given student+day: the class's timetable for that weekday, each period joined
to what actually happened — subject, topic (from the lesson log), the student's
attendance (present/late/absent/unmarked), checks they were flagged on, homework set
for them, plus any after-school sessions. Absent periods surface as gaps.
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    CheckResult,
    ClassPeriod,
    ClassSubject,
    DailyCheck,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    LessonLog,
    SchoolClass,
    SessionAttendance,
    SessionMeeting,
    SessionStudentLog,
    Student,
    Subject,
    SyllabusTopic,
    TimetableSlot,
)
from app.models import (
    Session as SessionModel,
)
from app.schemas.timeline import (
    StudentTimelineOut,
    TimelineFollowup,
    TimelineHomework,
    TimelinePeriod,
    TimelineSession,
)
from app.services.attendance import classify_day


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class StudentTimelineService:
    def __init__(self, db: Session):
        self.db = db

    def timeline(self, m: CurrentMember, student_id: uuid.UUID,
                 on_date: date | None = None) -> StudentTimelineOut:
        student = self.db.scalar(
            select(Student).where(Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        d = on_date or datetime.now(ZoneInfo(m.org.timezone)).date()
        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        class_label = _label(klass.name, klass.section) if klass else None

        periods: list[TimelinePeriod] = []
        if student.class_id is not None:
            periods = self._periods(m.org_id, student, d)
        sessions = self._sessions(m.org_id, student_id, d)
        marked = [p for p in periods if p.attendance != "unmarked"]
        absents = sum(1 for p in marked if p.attendance == "absent")
        return StudentTimelineOut(
            student_id=student.id, full_name=student.full_name, class_label=class_label,
            date=d, periods=periods, sessions=sessions,
            followups=self._followups(m, student.id, d),
            day_status=classify_day(len(periods), len(marked), absents),
            marked_periods=len(marked), absent_periods=absents,
            late_periods=sum(1 for p in marked if p.attendance == "late"))

    def _periods(self, org_id: uuid.UUID, student: Student, d: date) -> list[TimelinePeriod]:
        slots = list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.class_id == student.class_id,
                TimetableSlot.weekday == d.weekday(), TimetableSlot.effective_from <= d,
                or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d))
            .order_by(TimetableSlot.period_no)))
        if not slots:
            return []
        cs_ids = {s.class_subject_id for s in slots}
        subjects = dict(self.db.execute(
            select(ClassSubject.id, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.id.in_(cs_ids))).all())
        # topics from today's lesson logs
        topics = dict(self.db.execute(
            select(LessonLog.class_subject_id, SyllabusTopic.title)
            .join(SyllabusTopic, SyllabusTopic.id == LessonLog.topic_id)
            .where(LessonLog.org_id == org_id, LessonLog.date == d,
                   LessonLog.class_subject_id.in_(cs_ids))).all())
        # attendance marks for the class today, keyed by period
        marks = {p.period_no: p for p in self.db.scalars(
            select(ClassPeriod).where(
                ClassPeriod.org_id == org_id, ClassPeriod.class_id == student.class_id,
                ClassPeriod.date == d,
                ClassPeriod.attendance_marked_at.is_not(None))
            .options(selectinload(ClassPeriod.exceptions)))}
        # checks this student was flagged not-done on
        flagged: dict[uuid.UUID, list[str]] = {}
        for csid, desc in self.db.execute(
            select(DailyCheck.class_subject_id, DailyCheck.description)
            .join(CheckResult, CheckResult.check_id == DailyCheck.id)
            .where(DailyCheck.org_id == org_id, DailyCheck.date == d,
                   DailyCheck.class_subject_id.in_(cs_ids),
                   CheckResult.student_id == student.id, CheckResult.status == "not_done")
        ).all():
            flagged.setdefault(csid, []).append(desc)
        # Homework for the student (class-wide or targeted), each carrying THIS
        # student's verdict (HW-1). Three queries, never one per assignment.
        hw_rows = list(self.db.execute(
            select(HomeworkAssignment.class_subject_id, HomeworkAssignment.id,
                   HomeworkAssignment.text, HomeworkAssignment.due_date,
                   HomeworkAssignment.student_id)
            .where(HomeworkAssignment.org_id == org_id, HomeworkAssignment.date == d,
                   HomeworkAssignment.class_subject_id.in_(cs_ids),
                   or_(HomeworkAssignment.student_id.is_(None),
                       HomeworkAssignment.student_id == student.id))
        ).all())
        hw_ids = [r[1] for r in hw_rows]
        checked = set(self.db.scalars(
            select(HomeworkCheck.assignment_id)
            .where(HomeworkCheck.assignment_id.in_(hw_ids)))) if hw_ids else set()
        mine = {
            r.assignment_id: r.status for r in self.db.scalars(
                select(HomeworkResult).where(HomeworkResult.assignment_id.in_(hw_ids),
                                             HomeworkResult.student_id == student.id))
        } if hw_ids else {}
        homework: dict[uuid.UUID, list[TimelineHomework]] = {}
        for csid, hw_id, text, due, target in hw_rows:
            status = ("not_checked" if hw_id not in checked
                      else mine.get(hw_id, "done"))
            homework.setdefault(csid, []).append(TimelineHomework(
                assignment_id=hw_id, text=text, status=status, due_date=due,
                personal=target is not None))

        out: list[TimelinePeriod] = []
        for s in slots:
            mk = marks.get(s.period_no)
            status, late = "unmarked", None
            if mk is not None:
                exc = next((e for e in mk.exceptions if e.student_id == student.id), None)
                if exc is None:
                    status = "present"
                else:
                    status = exc.status
                    late = exc.late_minutes
            out.append(TimelinePeriod(
                period_no=s.period_no, class_subject_id=s.class_subject_id,
                subject_name=subjects.get(s.class_subject_id), topic=topics.get(s.class_subject_id),
                attendance=status, late_minutes=late,
                checks_flagged=flagged.get(s.class_subject_id, []),
                homework=homework.get(s.class_subject_id, []), gap=status == "absent"))
        return out

    def _followups(self, m: CurrentMember, student_id: uuid.UUID,
                   d: date) -> list[TimelineFollowup]:
        """Follow-ups raised ABOUT this student on this org-local day (D-46) —
        raised or resolved that day, so "was anything done about Kabir?" is
        answerable from the same screen that shows the absence."""
        from app.models import TaskInstance  # noqa: PLC0415
        from app.services import events as task_events  # noqa: PLC0415

        tz = ZoneInfo(m.org.timezone)
        start = datetime.combine(d, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=1)
        rows = list(self.db.scalars(select(TaskInstance).where(
            TaskInstance.org_id == m.org_id,
            TaskInstance.subject_type == "student",
            TaskInstance.subject_id == student_id,
            TaskInstance.status.notin_(("cancelled",)),
            or_(and_(TaskInstance.created_at >= start, TaskInstance.created_at < end),
                and_(TaskInstance.completed_at >= start, TaskInstance.completed_at < end)))
            .order_by(TaskInstance.created_at)))
        names = task_events.resolve_user_names(
            self.db, {r.assignee_id for r in rows if r.assignee_id})
        return [TimelineFollowup(
            task_id=r.id, title=r.title, status=r.status,
            assignee_name=names.get(r.assignee_id) if r.assignee_id else None,
            outcome=r.outcome) for r in rows]

    def _sessions(self, org_id: uuid.UUID, student_id: uuid.UUID, d: date) -> list[TimelineSession]:
        rows = self.db.execute(
            select(SessionMeeting.id, SessionModel.name, SessionModel.kind,
                   SessionAttendance.status, SessionAttendance.homework_done)
            .join(SessionMeeting, SessionMeeting.session_id == SessionModel.id)
            .join(SessionAttendance, SessionAttendance.meeting_id == SessionMeeting.id)
            .where(SessionModel.org_id == org_id, SessionMeeting.date == d,
                   SessionAttendance.student_id == student_id)
            .order_by(SessionModel.time, SessionModel.name)
        ).all()
        meeting_ids = [mid for mid, *_ in rows]
        # HS-2: a student's log is sectioned rows — fold them into one line here.
        notes: dict[uuid.UUID, list[str]] = {}
        if meeting_ids:
            for log in self.db.scalars(
                    select(SessionStudentLog).where(
                        SessionStudentLog.meeting_id.in_(meeting_ids),
                        SessionStudentLog.student_id == student_id)
                    .order_by(SessionStudentLog.created_at)):
                notes.setdefault(log.meeting_id, []).append(
                    f"{log.section}: {log.note}" if log.section else log.note)
        return [TimelineSession(session_name=name, kind=kind, status=status, homework_done=hw,
                                log_note=" · ".join(notes[mid]) if mid in notes else None)
                for mid, name, kind, status, hw in rows]
