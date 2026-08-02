"""M5 — assigned work, and the duties period capture implies (DASH3 §4.5).

Two halves that look alike and are not.

**Assigned work** is the task module rolled up: open / overdue / completed, by
board and by assignee, with the overdue and critical rows listed by name. Each
red row carries *Reassign* / *Extend* / *Nudge* through the shared rail.

**Daily classroom duties** is the observation that My Day *is* a task list. Four
duties fall out of period capture — attendance marked · lesson logged · homework
set · checks confirmed — and a teacher's completion is those four against the
periods they were **actually due to teach**. That denominator is the whole
honesty of the block:

  * a teacher whose classes were all cancelled cannot read as 0%;
  * a period **covered by a substitute counts toward the substitute**, not the
    absent teacher (§10.3) — the substitute did the work, and charging it to
    someone who was at home is how a compliance number stops meaning anything;
  * homework is **day-scoped per class-subject** (a second period of the same
    subject shows it as already set), so it is counted per class-subject-day, not
    per period, or a teacher with two Maths periods could never reach 100%.

This block is deliberately read-only. The fix for an unlogged period is the
teacher opening My Day, not the admin filing a task about it; *Nudge* is the
right escalation and it lives on the assigned-work half.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.models import (
    AcademicYear,
    Board,
    ClassPeriod,
    ClassSubject,
    DailyCheck,
    HomeworkAssignment,
    LessonLog,
    Membership,
    PeriodSubstitution,
    TaskInstance,
    TimetableSlot,
    User,
)
from app.schemas.insights import (
    DutyRow,
    TaskBoardOut,
    TaskDayPoint,
    TaskRedRow,
    TaskScopeRow,
)
from app.services.school_clock import today_in

WINDOW_DAYS = 14
MAX_RED_ROWS = 25


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


def _headline(out: TaskBoardOut) -> str:
    """§7 rule 3 — *"9 open, 3 overdue, all with Priya."*

    The third clause is the one that changes what the admin does: nine overdue
    tasks spread across nine people is a busy week, and nine sitting with one
    person is a conversation with that person. A bare count cannot tell the two
    apart, so the concentration is named whenever it is real.
    """
    if not out.open and not out.overdue:
        return "Nothing is open." if not out.unassigned else (
            f"Nothing is open, but {out.unassigned} "
            f"{_plural(out.unassigned, 'task')} {'has' if out.unassigned == 1 else 'have'} "
            "nobody assigned.")

    parts = [f"{out.open} open"]
    if out.overdue:
        parts[0] += f", {out.overdue} overdue"
    sentence = parts[0] + "."

    # Who is the overdue work actually sitting with? Only claim concentration
    # when one person genuinely holds most of it.
    if out.overdue:
        holders = sorted((r for r in out.by_assignee if r.overdue),
                         key=lambda r: r.overdue, reverse=True)
        if holders:
            top = holders[0]
            if len(holders) == 1:
                sentence += f" All of it with {top.label}."
            elif top.overdue * 2 >= out.overdue:
                sentence += f" {top.overdue} of them with {top.label}."
    if out.unassigned:
        sentence += (f" {out.unassigned} {_plural(out.unassigned, 'task')} "
                     f"{'has' if out.unassigned == 1 else 'have'} nobody assigned.")
    return sentence


class TaskInsights:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def board(self, m: CurrentMember, window_days: int = WINDOW_DAYS,
              on: date | None = None) -> TaskBoardOut:
        today = on or self._today(m)
        window = max(1, min(window_days, 60))
        since = today - timedelta(days=window - 1)
        now = datetime.now(UTC)
        out = TaskBoardOut(date=today, window_days=window)

        rows = self.db.execute(
            select(TaskInstance, Board.id, Board.name, User.name)
            .join(Board, Board.id == TaskInstance.board_id)
            .outerjoin(User, User.id == TaskInstance.assignee_id)
            .where(TaskInstance.org_id == m.org_id,
                   or_(TaskInstance.status == "open",
                       TaskInstance.completed_at >= datetime.combine(
                           since, datetime.min.time(), tzinfo=UTC)))
        ).all()

        by_board: dict[uuid.UUID, list] = defaultdict(lambda: [0, 0, 0, ""])
        by_user: dict[uuid.UUID | None, list] = defaultdict(lambda: [0, 0, 0, ""])
        per_day: dict[date, list[int]] = defaultdict(lambda: [0, 0])
        red: list[TaskRedRow] = []

        for t, board_id, board_name, assignee_name in rows:
            b = by_board[board_id]
            b[3] = board_name
            u = by_user[t.assignee_id]
            u[3] = assignee_name or "Unassigned"
            overdue = (t.status == "open" and t.due_at is not None and t.due_at < now)
            if t.status == "open":
                out.open += 1
                b[0] += 1
                u[0] += 1
                if t.assignee_id is None:
                    out.unassigned += 1
                if overdue:
                    out.overdue += 1
                    b[1] += 1
                    u[1] += 1
                    if t.is_critical:
                        out.critical_overdue += 1
                    red.append(TaskRedRow(
                        task_id=t.id, title=t.title, board_id=board_id, board_name=board_name,
                        assignee_user_id=t.assignee_id, assignee_name=assignee_name,
                        due_at=t.due_at, is_critical=t.is_critical,
                        days_overdue=max(0, (today - t.due_at.date()).days)))
            elif t.completed_at is not None:
                out.completed_window += 1
                b[2] += 1
                u[2] += 1
                per_day[t.completed_at.date()][0] += 1
            if since <= t.created_at.date() <= today:
                per_day[t.created_at.date()][1] += 1

        out.daily = [
            TaskDayPoint(date=since + timedelta(days=i),
                         completed=per_day.get(since + timedelta(days=i), [0, 0])[0],
                         created=per_day.get(since + timedelta(days=i), [0, 0])[1])
            for i in range(window)
        ]
        out.by_board = self._scope_rows(by_board)
        out.by_assignee = self._scope_rows(by_user)
        red.sort(key=lambda r: (not r.is_critical, -r.days_overdue))
        out.red_rows = red[:MAX_RED_ROWS]
        out.duties = self.duties(m, today)
        rated = [d for d in out.duties if d.due_periods]
        if rated:
            out.duty_completion = round(
                sum(d.completion or 0 for d in rated) / len(rated), 3)
        out.headline = _headline(out)
        return out

    @staticmethod
    def _scope_rows(bucket: dict) -> list[TaskScopeRow]:
        rows = [
            TaskScopeRow(
                key=str(key), id=key if isinstance(key, uuid.UUID) else None, label=v[3],
                open=v[0], overdue=v[1], completed=v[2],
                completion=round(v[2] / (v[0] + v[2]), 3) if (v[0] + v[2]) else None)
            for key, v in bucket.items()
        ]
        rows.sort(key=lambda r: (-r.overdue, -r.open, r.label))
        return rows

    # ── the daily duties ─────────────────────────────────────────────────────
    def duties(self, m: CurrentMember, on: date | None = None) -> list[DutyRow]:
        """Per teacher: the four duties against the periods they were due to take.

        Six queries flat — the grid, today's cover, the period rows, the logs, the
        homework and the checks — joined in memory. A per-teacher loop would be
        one remote round-trip per member of staff.
        """
        on = on or self._today(m)
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))
        if year is None:
            return []
        working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5])
        if on.weekday() not in working:
            return []

        # (class_id, period_no) → (teacher_member_id, class_subject_id)
        due: dict[tuple[uuid.UUID, int], tuple[uuid.UUID | None, uuid.UUID]] = {}
        for cid, pno, cs_id, teacher_id in self.db.execute(
            select(TimetableSlot.class_id, TimetableSlot.period_no,
                   TimetableSlot.class_subject_id, ClassSubject.teacher_member_id)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id, TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on))
        ).all():
            due[(cid, int(pno))] = (teacher_id, cs_id)

        # Cover reassigns the duty with the period (§10.3).
        for s in self.db.scalars(
            select(PeriodSubstitution).where(
                PeriodSubstitution.org_id == m.org_id, PeriodSubstitution.date == on,
                PeriodSubstitution.cancelled_at.is_(None))):
            key = (s.class_id, s.period_no)
            _old, cs_id = due.get(key, (None, s.class_subject_id))
            due[key] = (s.substitute_member_id, cs_id or s.class_subject_id)
        if not due:
            return []

        periods = {
            (p.class_id, p.period_no): p for p in self.db.scalars(
                select(ClassPeriod).where(ClassPeriod.org_id == m.org_id,
                                          ClassPeriod.date == on))
        }
        logged_periods = set(self.db.scalars(
            select(LessonLog.period_id).where(LessonLog.org_id == m.org_id,
                                              LessonLog.date == on,
                                              LessonLog.period_id.is_not(None))))
        hw_cs = set(self.db.scalars(
            select(HomeworkAssignment.class_subject_id).where(
                HomeworkAssignment.org_id == m.org_id, HomeworkAssignment.date == on)))
        confirmed_cs = set(self.db.scalars(
            select(DailyCheck.class_subject_id).where(
                DailyCheck.org_id == m.org_id, DailyCheck.date == on,
                DailyCheck.confirmed_at.is_not(None))))

        acc: dict[uuid.UUID, list] = defaultdict(lambda: [0, 0, 0, set(), set()])
        for (cid, pno), (teacher_id, cs_id) in due.items():
            if teacher_id is None:
                continue
            period = periods.get((cid, pno))
            # A period the teacher marked "not held" is captured, not skipped —
            # it drops out of the denominator rather than counting as a failure.
            if period is not None and period.status == "not_held":
                continue
            row = acc[teacher_id]
            row[0] += 1
            if period is not None and period.attendance_marked_at is not None:
                row[1] += 1
            if period is not None and period.id in logged_periods:
                row[2] += 1
            if cs_id in hw_cs:
                row[3].add(cs_id)
            if cs_id in confirmed_cs:
                row[4].add(cs_id)

        names = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(acc.keys()))).all()
        } if acc else {}
        # Homework and checks are per class-subject-day, so their denominator is
        # the distinct class-subjects due, not the period count.
        cs_due: dict[uuid.UUID, set] = defaultdict(set)
        for _key, (teacher_id, cs_id) in due.items():
            if teacher_id is not None:
                cs_due[teacher_id].add(cs_id)

        out: list[DutyRow] = []
        for teacher_id, v in acc.items():
            n_cs = len(cs_due.get(teacher_id, set())) or 1
            parts = [v[1] / v[0], v[2] / v[0], len(v[3]) / n_cs, len(v[4]) / n_cs] \
                if v[0] else []
            out.append(DutyRow(
                member_id=teacher_id, name=names.get(teacher_id, "—"),
                due_periods=v[0], attendance_marked=v[1], logged=v[2],
                homework_set=len(v[3]), checks_confirmed=len(v[4]),
                completion=round(sum(parts) / len(parts), 3) if parts else None))
        out.sort(key=lambda d: (d.completion if d.completion is not None else 1, d.name))
        return out
