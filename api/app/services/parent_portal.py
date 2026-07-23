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
from app.models import Organization
from app.schemas.parent import (
    ParentHomeworkItem,
    ParentReportOut,
    ParentReportSubject,
    ParentSessionItem,
    ParentTaughtItem,
    ParentTodayOut,
)
from app.services.growth import GrowthService
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
                homework.append(ParentHomeworkItem(subject_name=subject, text=hw))

        sessions = [
            ParentSessionItem(
                session_name=s.session_name, kind=s.kind, status=s.status,
                homework_done=s.homework_done, log_note=s.log_note)
            for s in t.sessions
        ]
        return ParentTodayOut(
            date=t.date, status=status, marked_periods=len(marked),
            absent_periods=absents, late_periods=lates,
            taught=taught, homework=homework, sessions=sessions)

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
