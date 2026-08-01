"""Parent portal reads — a curated PROJECTION over existing computed services.

No new capture tables: today = the student timeline, the report = the growth
report, both already assembled from what teachers capture in the daily flow.
This layer decides what leaves the server for a guardian (founder decision
2026-07-23: curated only):

- kept: attendance, topics taught, homework, syllabus coverage with
  missed-while-absent, verified scores, derived strengths/growth-areas phrases.
- dropped: bands + history (P4), skill profile, raw lesson observations,
  daily-check flags, per-period attendance detail (parents get a DAILY status).

The staff services are reached through a synthetic admin context (the
daily-report precedent) — access control for parents is the guardian link
check in get_current_parent + _assert_child here.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import homework_verdict as verdicts
from app.core.context import CurrentParent
from app.core.exceptions import ForbiddenError
from app.models import Organization, Student
from app.schemas.parent import (
    ParentHomeworkDay,
    ParentHomeworkItem,
    ParentMonthDay,
    ParentReportOut,
    ParentReportSubject,
    ParentSessionItem,
    ParentTaughtItem,
    ParentTodayOut,
)
from app.services.growth import GrowthService
from app.services.homework import HomeworkService
from app.services.timeline import StudentTimelineService


class _AdminView:
    """Synthetic admin read context so the parent service can reuse the
    Growth/Timeline computed joins. Never leaves this module."""

    is_coordinator_up = True

    def __init__(self, org: Organization):
        self.org = org
        self.org_id = org.id


class ParentPortalService:
    def __init__(self, db: Session):
        self.db = db

    def _assert_child(self, p: CurrentParent, student_id: uuid.UUID) -> None:
        if student_id not in p.child_ids():
            raise ForbiddenError("You can view only your own children.",
                                 code="not_your_child")

    def today(self, p: CurrentParent, student_id: uuid.UUID,
              on_date: date | None = None) -> ParentTodayOut:
        self._assert_child(p, student_id)
        t = StudentTimelineService(self.db).timeline(_AdminView(p.org), student_id, on_date)

        # V1-0d: the day status is computed ONCE, in the timeline (`classify_day`)
        # — this projection renders it. The rule used to be re-derived here, which
        # is exactly how a parent and the admin board could come to disagree.
        status = t.day_status

        taught: list[ParentTaughtItem] = []
        seen: set[tuple[str, str]] = set()
        homework: list[ParentHomeworkItem] = []
        for x in t.periods:
            subject = x.subject_name or "—"
            if x.topic and (subject, x.topic) not in seen:
                seen.add((subject, x.topic))
                taught.append(ParentTaughtItem(subject_name=subject, topic=x.topic))
            for hw in x.homework:
                homework.append(ParentHomeworkItem(
                    subject_name=subject, text=hw.text, status=hw.status,
                    due_date=hw.due_date, personal=hw.personal))

        sessions = [
            ParentSessionItem(
                session_name=s.session_name, kind=s.kind, status=s.status,
                homework_done=s.homework_done, log_note=s.log_note)
            for s in t.sessions
        ]
        yesterday, pending, missed = self._homework(p, student_id, t.date)
        month, present_days, marked_days = self._month_pattern(p, student_id, t.date)
        return ParentTodayOut(
            date=t.date, status=status, marked_periods=t.marked_periods,
            absent_periods=t.absent_periods, late_periods=t.late_periods,
            month=month, present_days=present_days, marked_days=marked_days,
            absence_reason=(self._absence_reason(p, student_id, t.date)
                            if status in ("absent", "left_after_lunch") else None),
            school_phone=p.org.phone,
            taught=taught, homework=homework, sessions=sessions,
            yesterday=yesterday, pending=pending, missed=missed)

    def _month_pattern(self, p: CurrentParent, student_id: uuid.UUID, today: date,
                       ) -> tuple[list["ParentMonthDay"], int, int]:
        """S-11: the month strip — DAILY statuses via the same classifier the
        register renders (`classify_marked_day`), never per-period detail."""
        from app.models import AcademicYear, CalendarEvent, SchoolClass  # noqa: PLC0415
        from app.services.attendance import classify_marked_day, day_matrix  # noqa: PLC0415
        from app.services.calendar import event_rows, expand_blocked_dates  # noqa: PLC0415
        from app.services.my_class import PRESENT_STATUSES  # noqa: PLC0415
        from app.services.school_clock import marking_period_nos  # noqa: PLC0415

        student = self.db.get(Student, student_id)
        if student is None or student.class_id is None:
            return [], 0, 0
        klass = self.db.get(SchoolClass, student.class_id)
        year = self.db.get(AcademicYear, klass.academic_year_id) if klass else None
        first = today.replace(day=1)
        working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5]) if year \
            else {0, 1, 2, 3, 4, 5}
        blocked = expand_blocked_dates(event_rows(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == p.org.id,
                CalendarEvent.end_date >= first,
                CalendarEvent.start_date <= today)))) if year else set()
        marking = marking_period_nos(
            year.period_times if year else None, p.org.attendance_mode)
        marked, exc = day_matrix(self.db, p.org.id, [student.class_id], first, today)

        out: list[ParentMonthDay] = []
        present = counted = 0
        start = max(first, student.enrolled_on) if student.enrolled_on else first
        for o in range(start.toordinal(), today.toordinal() + 1):
            d = date.fromordinal(o)
            if d.weekday() not in working or d in blocked:
                continue
            periods = marked.get((student.class_id, d))
            if not periods:
                out.append(ParentMonthDay(date=d, status="not_marked"))
                continue
            per = exc.get((student_id, d), {})
            s, _late = classify_marked_day(
                periods, {pn: st for pn, (st, _r) in per.items()}, marking)
            counted += 1
            if s in PRESENT_STATUSES:
                present += 1
            out.append(ParentMonthDay(date=d, status=s))
        return out, present, counted

    def _absence_reason(self, p: CurrentParent, student_id: uuid.UUID,
                        d: date) -> str | None:
        """The reason the school recorded — projected as one plain string."""
        from app.models import AttendanceException, ClassPeriod, StudentAbsenceNote  # noqa: PLC0415

        row = self.db.execute(
            select(AttendanceException.reason_code, AttendanceException.reason_note)
            .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
            .where(AttendanceException.student_id == student_id,
                   AttendanceException.reason_at.is_not(None),
                   ClassPeriod.date == d).limit(1)).first()
        if row is None:
            row = self.db.execute(
                select(StudentAbsenceNote.reason_code, StudentAbsenceNote.note)
                .where(StudentAbsenceNote.student_id == student_id,
                       StudentAbsenceNote.from_date <= d,
                       StudentAbsenceNote.to_date >= d)
                .order_by(StudentAbsenceNote.created_at.desc()).limit(1)).first()
        if row is None:
            return None
        code, note = row
        return note or (code.replace("_", " ") if code else None)

    # ── homework the parent actually asks about (HW-1) ───────────────────────
    def _homework(self, p: CurrentParent, student_id: uuid.UUID, today: date
                  ) -> tuple[ParentHomeworkDay | None, list[ParentHomeworkItem]]:
        """Yesterday's verdict and what's still outstanding, in one read.

        Deliberately goes through `HomeworkService.history_for` rather than
        calling the timeline once per day: the timeline is ~7 queries a day, so
        walking back a week for "did they do yesterday's homework" would be
        fifty round-trips to a remote database for two small answers.

        The projection stays an allowlist — text, subject, status, due date —
        exactly as the rest of this module (P4: nothing here is band data, but
        the discipline is the point).
        """
        student = self.db.get(Student, student_id)
        if student is None:
            return None, []
        history = HomeworkService(self.db).history_for(p.org.id, student, 8, today)

        def project(i) -> ParentHomeworkItem:
            return ParentHomeworkItem(
                subject_name=i.subject_name or "—", text=i.text, status=i.status,
                due_date=i.due_date, personal=i.personal)

        past = [i for i in history.items if i.date < today]
        yesterday = None
        if past:
            last_day = max(i.date for i in past)
            items = [project(i) for i in past if i.date == last_day]
            counts = verdicts.tally(i.status for i in items)
            yesterday = ParentHomeworkDay(
                date=last_day, items=items,
                done=counts["done"], not_done=counts["not_done"],
                partial=counts["partial"], late=counts["late"],
                carried=counts["carried"], not_checked=counts["not_checked"])

        # S-94 — split what can still be handed in from what was missed.
        # `waived` appears in neither: the teacher decided it is not required,
        # which is precisely how a carried item stops being pending (S-98) and
        # how the parent's yellow finally clears.
        pending: list[ParentHomeworkItem] = []
        missed: list[ParentHomeworkItem] = []
        for i in history.items:
            if i.status in ("done", "late", "waived"):
                continue
            if i.status == "carried":
                # D-35: missed because the child was ABSENT. Yellow, pending,
                # never red — nothing was refused.
                pending.append(project(i))
            elif i.due_date is None or i.due_date >= today:
                pending.append(project(i))
            elif i.status != "not_checked":
                missed.append(project(i))
            # `not_checked` past its due date belongs in neither list: the
            # teacher hasn't looked yet, and that is never the child's miss.
        return yesterday, pending, missed

    def report(self, p: CurrentParent, student_id: uuid.UUID) -> ParentReportOut:
        self._assert_child(p, student_id)
        g = GrowthService(self.db).growth(_AdminView(p.org), student_id)
        # Field-by-field projection — never a dict spread, so a new staff field
        # can't reach parents without being named here deliberately.
        return ParentReportOut(
            student_id=g.student_id,
            full_name=g.full_name,
            class_label=g.class_label,
            attendance=g.attendance,
            subjects=[
                ParentReportSubject(
                    subject_name=s.subject_name,
                    teacher_name=s.teacher_name,
                    attendance=s.attendance,
                    chapters=s.chapters,
                    homework_assigned=s.homework_assigned,
                    homework_personal=s.homework_personal,
                    scores=s.scores,
                    # `S-51`/`S-54`: the coverage figure, computed once in
                    # `core.coverage` and named here deliberately. The basis is
                    # the WHOLE syllabus — the only denominator that cannot
                    # fall when the school sizes next term's chapters, which a
                    # parent would read as the school going backwards.
                    coverage_taught=s.coverage_taught,
                    coverage_total=s.coverage_total,
                    coverage_pct=s.coverage_pct,
                    # `S-48`: the chapter name, which is what a parent can
                    # actually ask their child about. Pace, lag and RAG stay out
                    # of this projection entirely (`D-11`).
                    latest_chapter=s.latest_chapter,
                    latest_topic=s.latest_topic,
                    latest_taught_on=s.latest_taught_on,
                )
                for s in g.subjects
            ],
            strengths=g.strengths,
            growth_areas=g.growth_areas,
        )
