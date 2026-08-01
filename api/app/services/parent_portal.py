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

from sqlalchemy.orm import Session

from app.core.context import CurrentParent
from app.core.exceptions import ForbiddenError
from app.models import Organization, Student
from app.schemas.parent import (
    ParentHomeworkDay,
    ParentHomeworkItem,
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

        marked = [x for x in t.periods if x.attendance != "unmarked"]
        absents = sum(1 for x in marked if x.attendance == "absent")
        lates = sum(1 for x in marked if x.attendance == "late")
        if not t.periods:
            status = "no_school"
        elif not marked:
            status = "not_marked"
        elif absents == len(marked):
            status = "absent"
        elif absents > 0:
            status = "partial"
        else:
            status = "present"

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
        yesterday, pending = self._homework(p, student_id, t.date)
        return ParentTodayOut(
            date=t.date, status=status, marked_periods=len(marked),
            absent_periods=absents, late_periods=lates,
            taught=taught, homework=homework, sessions=sessions,
            yesterday=yesterday, pending=pending)

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
            yesterday = ParentHomeworkDay(
                date=last_day, items=items,
                done=sum(1 for i in items if i.status == "done"),
                not_done=sum(1 for i in items if i.status == "not_done"),
                partial=sum(1 for i in items if i.status == "partial"),
                not_checked=sum(1 for i in items if i.status == "not_checked"))

        pending = [
            project(i) for i in history.items
            if i.status != "done" and (i.due_date is None or i.due_date >= today)
        ]
        return yesterday, pending

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
                )
                for s in g.subjects
            ],
            strengths=g.strengths,
            growth_areas=g.growth_areas,
        )
