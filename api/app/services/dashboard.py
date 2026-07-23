"""Director Dashboard (M4, SPRD §5.4).

Every problem on the screen has an 'assign action' button. The dashboard is pure
composition — it re-reads the module services (planner forecast, fees summary,
session records, classroom compliance/homework) and derives the alert feed. No
new capture; nothing here is stored.
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    AttendanceException,
    ClassPeriod,
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    SchoolClass,
    Student,
    TimetableSlot,
)
from app.schemas.dashboard import (
    Alert,
    AttendanceClassToday,
    AttendanceDay,
    AttendancePulse,
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
ATTENDANCE_WINDOW_DAYS = 14
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

    # ── attendance pulse (the charts read this; nothing here is stored) ──────
    def _attendance_pulse(self, m: CurrentMember, year_id: uuid.UUID) -> AttendancePulse:
        """Roll the exception rows up per day and per class.

        Capture-by-exception means a marked period IS a full roster minus its
        exceptions (P1v2) — so present = roster − absent, and a day with no marked
        period is a no-data day, never a 0% day. Three grouped queries, no
        per-class loop: every read here is a round-trip to a remote database.
        """
        today = self._today(m)
        since = today - timedelta(days=ATTENDANCE_WINDOW_DAYS - 1)

        labels = {
            cid: name + (f"-{section}" if section else "")
            for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.org_id == m.org_id, SchoolClass.academic_year_id == year_id)
                .order_by(SchoolClass.name, SchoolClass.section)).all()
        }
        if not labels:
            return AttendancePulse(window_days=ATTENDANCE_WINDOW_DAYS)

        roster = {
            cid: int(n) for cid, n in self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_(labels.keys()))
                .group_by(Student.class_id)).all()
        }
        rows = self.db.execute(
            select(
                ClassPeriod.date, ClassPeriod.class_id,
                func.count(func.distinct(ClassPeriod.id)),
                func.count(func.distinct(
                    case((AttendanceException.status == "absent", AttendanceException.id)))),
                func.count(func.distinct(
                    case((AttendanceException.status == "late", AttendanceException.id)))),
            )
            .join(AttendanceException, AttendanceException.period_id == ClassPeriod.id, isouter=True)
            .where(ClassPeriod.org_id == m.org_id, ClassPeriod.class_id.in_(labels.keys()),
                   ClassPeriod.date >= since, ClassPeriod.date <= today,
                   ClassPeriod.attendance_marked_at.is_not(None))
            .group_by(ClassPeriod.date, ClassPeriod.class_id)
        ).all()
        # Periods scheduled TODAY per class — the denominator for "how much of
        # today has been captured", read off the effective-dated grid.
        expected_today = {
            cid: int(n) for cid, n in self.db.execute(
                select(TimetableSlot.class_id, func.count(TimetableSlot.id))
                .where(TimetableSlot.org_id == m.org_id, TimetableSlot.weekday == today.weekday(),
                       TimetableSlot.effective_from <= today,
                       or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > today))
                .group_by(TimetableSlot.class_id)).all()
        }

        per_day: dict[date, list[int]] = {}       # date → [periods, student-periods, absent, late]
        per_class_today: dict[uuid.UUID, list[int]] = {}
        for d, cid, periods, absent, late in rows:
            size = roster.get(cid, 0)
            for acc in (per_day.setdefault(d, [0, 0, 0, 0]),
                        *([per_class_today.setdefault(cid, [0, 0, 0, 0])] if d == today else [])):
                acc[0] += int(periods)
                acc[1] += int(periods) * size
                acc[2] += int(absent)
                acc[3] += int(late)

        def pct(student_periods: int, absent: int) -> float | None:
            if not student_periods:
                return None
            return round((student_periods - absent) / student_periods * 100, 1)

        days = [
            AttendanceDay(date=d, periods_marked=v[0], roster=v[1], absent=v[2], late=v[3],
                          present_pct=pct(v[1], v[2]))
            for d, v in sorted(per_day.items())
        ]
        classes_today = [
            AttendanceClassToday(
                class_label=labels.get(cid, "?"), periods_marked=v[0],
                periods_expected=expected_today.get(cid, 0), absent=v[2], late=v[3],
                present_pct=pct(v[1], v[2]))
            for cid, v in sorted(per_class_today.items(), key=lambda kv: labels.get(kv[0], ""))
        ]
        return AttendancePulse(
            window_days=ATTENDANCE_WINDOW_DAYS,
            today=next((x for x in days if x.date == today), None),
            days=days, classes_today=classes_today)

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
            elif r.status == "unplanned":
                # Nothing is scheduled for this subject at all. Chapters that are
                # merely unsized in a LATER term are deliberately not alerted (the
                # school plans term by term — that's normal); a wholly unscheduled
                # subject is what the director needs told.
                alerts.append(Alert(
                    id=f"unplanned:{r.class_subject_id}", type="pace", severity="amber",
                    class_subject_id=r.class_subject_id,
                    title=f"{r.class_label} {r.subject_name} has no plan yet",
                    detail=("No chapter is scheduled, so there is no finish date. "
                            "Size the current term's chapters and generate its plan.")))
            elif r.current_term_unplanned:
                # Paced fine on what's planned, but the term running TODAY has
                # nothing scheduled — the plan ran out under the teacher's feet.
                alerts.append(Alert(
                    id=f"term-unplanned:{r.class_subject_id}", type="pace", severity="amber",
                    class_subject_id=r.class_subject_id,
                    title=f"{r.class_label} {r.subject_name}: current term has no plan",
                    detail=("The running term's chapters are not scheduled yet. "
                            "Size them and generate that term's plan.")))
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
        # weak-subject early warning (class average falling across cycles, M3)
        from app.services.assessments import AssessmentService
        for t in AssessmentService(self.db).weak_subjects(m):
            latest = t.points[-1]["avg_pct"] if t.points else 0
            alerts.append(Alert(
                id=f"weak:{t.subject_id}", type="homework", severity="amber",
                title=f"{t.subject_name} average dropped to {latest}%",
                detail="Class average is falling across test cycles — review with the teacher."))
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
                attendance=AttendancePulse(window_days=ATTENDANCE_WINDOW_DAYS),
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
            attendance=self._attendance_pulse(m, year.id),
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
