"""Director Dashboard (M4, SPRD §5.4).

Every problem on the screen has an 'assign action' button. The dashboard is pure
composition — it re-reads the module services (planner forecast, fees summary,
session records, classroom compliance/homework) and derives the alert feed. No
new capture; nothing here is stored.
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    SchoolClass,
)
from app.schemas.dashboard import (
    Alert,
    DashboardOverview,
    DigestOut,
    HomeworkClassHealth,
    HomeworkHealth,
)
from app.schemas.task import TaskCreateRequest
from app.services.classroom import ClassroomService
from app.services.fees import FeeService
from app.services.planner import PlannerService
from app.services.sessions import SessionService
from app.services.task import TaskService

HOMEWORK_WINDOW_DAYS = 14
LOW_COMPLETION = 0.6  # below this a class is flagged


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id is not None:
            return self.db.scalar(
                select(AcademicYear).where(AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(
            select(AcademicYear).where(AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    def _rag_rows(self, m: CurrentMember, year_id: uuid.UUID):
        classes = self.db.scalars(
            select(SchoolClass.id).where(
                SchoolClass.org_id == m.org_id, SchoolClass.academic_year_id == year_id))
        rows = []
        planner = PlannerService(self.db)
        for cid in classes:
            rows.extend(planner.forecast(m, cid))
        return rows

    def _homework_health(self, m: CurrentMember, year_id: uuid.UUID) -> HomeworkHealth:
        since = self._today(m) - timedelta(days=HOMEWORK_WINDOW_DAYS)
        # class label per class-subject, with homework counts + completion.
        rows = self.db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section,
                   func.count(func.distinct(HomeworkAssignment.id)),
                   func.coalesce(func.sum(HomeworkCheck.done_count), 0),
                   func.coalesce(func.sum(HomeworkCheck.total_count), 0))
            .join(ClassSubject, ClassSubject.class_id == SchoolClass.id)
            .join(HomeworkAssignment, (HomeworkAssignment.class_subject_id == ClassSubject.id)
                  & (HomeworkAssignment.date >= since), isouter=True)
            .join(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id, isouter=True)
            .where(SchoolClass.org_id == m.org_id, SchoolClass.academic_year_id == year_id)
            .group_by(SchoolClass.id, SchoolClass.name, SchoolClass.section)
            .order_by(SchoolClass.name, SchoolClass.section)
        ).all()
        classes: list[HomeworkClassHealth] = []
        tot_done = tot_total = 0
        for _cid, name, section, assignments, done, total in rows:
            label = name + (f"-{section}" if section else "")
            completion = round(done / total, 2) if total else None
            tot_done += int(done)
            tot_total += int(total)
            classes.append(HomeworkClassHealth(class_label=label, assignments=int(assignments),
                                               completion=completion))
        overall = round(tot_done / tot_total, 2) if tot_total else None
        return HomeworkHealth(window_days=HOMEWORK_WINDOW_DAYS, overall_completion=overall,
                              classes=classes)

    def _alerts(self, m: CurrentMember, rag_rows, homework: HomeworkHealth) -> list[Alert]:
        alerts: list[Alert] = []
        for r in rag_rows:
            if r.status in ("amber", "red"):
                alerts.append(Alert(
                    id=f"pace:{r.class_subject_id}", type="pace",
                    severity=r.status, class_subject_id=r.class_subject_id,
                    title=f"{r.class_label} {r.subject_name} is {r.weeks_behind}w behind plan",
                    detail=(f"Projected finish {r.projected_finish} vs baseline {r.baseline_finish}. "
                            f"Plan a catch-up before the next test.")))
        # today's logging compliance
        comp = ClassroomService(self.db).compliance(m)
        unlogged = comp.total - comp.logged_count
        if comp.total and unlogged:
            alerts.append(Alert(
                id="compliance:today", type="compliance",
                severity="red" if unlogged > comp.total / 2 else "amber",
                title=f"{unlogged} of {comp.total} classes not logged today",
                detail="Nudge the teachers who haven't logged."))
        # low homework completion
        for c in homework.classes:
            if c.completion is not None and c.completion < LOW_COMPLETION:
                alerts.append(Alert(
                    id=f"homework:{c.class_label}", type="homework", severity="amber",
                    title=f"{c.class_label} homework completion at {int(c.completion * 100)}%",
                    detail="Follow up on homework completion with the class teacher."))
        return alerts

    def overview(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> DashboardOverview:
        year = self._year(m, year_id)
        # Fee card is director-only (coordinators never read fees, §3.3).
        fees = FeeService(self.db).summary(m, year.id if year else None) if m.is_admin else None
        if year is None:
            return DashboardOverview(
                academic_year_id=None, rag_green=0, rag_amber=0, rag_red=0, rag=[], fees=fees,
                sessions=SessionService(self.db).records(m),
                homework=HomeworkHealth(window_days=HOMEWORK_WINDOW_DAYS, overall_completion=None, classes=[]),
                alerts=[])
        rag_rows = self._rag_rows(m, year.id)
        homework = self._homework_health(m, year.id)
        greens = sum(1 for r in rag_rows if r.status == "green")
        ambers = sum(1 for r in rag_rows if r.status == "amber")
        reds = sum(1 for r in rag_rows if r.status == "red")
        return DashboardOverview(
            academic_year_id=year.id, rag_green=greens, rag_amber=ambers, rag_red=reds,
            rag=[r for r in rag_rows if r.status in ("amber", "red")], fees=fees,
            sessions=SessionService(self.db).records(m),
            homework=homework,
            alerts=self._alerts(m, rag_rows, homework))

    # ── Monday digest (M4, DB-4) ─────────────────────────────────────────────
    def digest(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> DigestOut:
        ov = self.overview(m, year_id)
        issues = [a.title for a in ov.alerts[:3]]  # top 3 issues
        wins: list[str] = []
        if ov.fees and ov.fees.total_fee and float(ov.fees.total_fee) > 0:
            pct = round(float(ov.fees.collected_fee) / float(ov.fees.total_fee) * 100)
            wins.append(f"Fees {pct}% collected")
        attended = sum(s.present + s.late for s in ov.sessions)
        if ov.sessions:
            wins.append(f"{len(ov.sessions)} session(s) run · {attended} attended")
        if ov.rag_green:
            wins.append(f"{ov.rag_green} class-subjects on track")
        lines = [f"TrackBit · {m.org.name}", ""]
        lines.append("Needs attention:" if issues else "All on track this week ✅")
        lines += [f"• {i}" for i in issues]
        if wins:
            lines += ["", "Wins:"] + [f"• {w}" for w in wins]
        return DigestOut(text="\n".join(lines), issues=issues, wins=wins)

    # ── one-tap alert -> task (into the existing task module) ────────────────
    def create_task_from_alert(self, m: CurrentMember, board_id: uuid.UUID,
                               title: str, description: str | None):
        from app.models import Board
        board = self.db.scalar(
            select(Board).where(Board.id == board_id, Board.org_id == m.org_id))
        if board is None:
            raise NotFoundError("Board")
        return TaskService(self.db).create(
            m, TaskCreateRequest(board_id=board_id, title=title, description=description))
