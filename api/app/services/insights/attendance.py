"""M1 — attendance, students and staff (DASH3 §4.1).

Three layers, and the middle one is the reason the tab exists.

**The picture.** The 14-day pulse and per-class today already existed on the
overview; what is new here is the **period capture heatmap** — class × period for
today, showing which periods were never marked at all. It separates "attendance
is bad" from "attendance was never taken", which no percentage can do, and which
is usually the actual finding at 11am.

**The red list.** Students absent for every marked period of N consecutive school
days. Stated precisely because it decides who gets a phone call:

  * A student is **day-absent** only when they were absent in *every* marked
    period of that day. Absent in some but not all is **partial** (came late,
    left early) and never counts toward a streak — the same rule
    `services/timeline.py` and the parent portal use, so a parent and this board
    can never disagree about whether a child was "absent".
  * A streak counts consecutive **school days**. Days with nothing marked are
    skipped rather than breaking the run: the school's failure to capture is not
    evidence the child came in. Non-working days and holidays are skipped through
    the calendar, so Friday→Monday is a 2-day streak, not 4.

**The blast radius.** For each absent staff member, the periods they were due to
teach and who could cover each one — ranked by who actually knows the subject.
For an absent admin the equivalent is their open tasks.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    AttendanceException,
    Board,
    CalendarEvent,
    ClassPeriod,
    ClassSubject,
    Guardian,
    Membership,
    PeriodSubstitution,
    SchoolClass,
    Student,
    Subject,
    TaskInstance,
    TimetableSlot,
    User,
)
from app.schemas.insights import (
    AbsenceStreak,
    AttendanceBoard,
    CaptureCell,
    CaptureRow,
    ImpactPeriod,
    ImpactTask,
    PeriodCaptureGrid,
    StaffAbsentee,
    StaffImpact,
    StaffPresence,
    StreakBoard,
    SubstituteCandidate,
)
from app.services.calendar import event_rows, expand_blocked_dates
from app.services.dashboard import DashboardService
from app.services.insights.actions import ActionService
from app.services.school_clock import day_periods, today_in
from app.services.staff_attendance import StaffAttendanceService
from app.services.substitution import SubstitutionService

# Constants, not settings (DASH3 §10.4): the school has no basis to tune these
# yet, and a threshold nobody understands is worse than one nobody can change.
STREAK_ALERT_DAYS = 3
STREAK_WINDOW_DAYS = 30
MAX_STREAK_ROWS = 40


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class AttendanceInsights:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id is not None:
            return self.db.scalar(select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    # ── layer 1: the picture ─────────────────────────────────────────────────
    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> AttendanceBoard:
        today = self._today(m)
        year = self._year(m, year_id)
        pulse = (DashboardService(self.db).attendance_pulse(m, year.id) if year
                 else None)
        capture = self._capture_grid(m, today, year)
        staff = self.staff_presence(m, today)
        streaks = self.streaks(m, year_id=year.id if year else None)
        from app.schemas.dashboard import AttendancePulse  # noqa: PLC0415

        return AttendanceBoard(
            date=today, students=pulse or AttendancePulse(window_days=14),
            capture=capture, staff=staff, streak_count=len(streaks.rows))

    def capture_grid(self, m: CurrentMember, on: date | None = None,
                     year_id: uuid.UUID | None = None) -> PeriodCaptureGrid:
        """The heatmap on its own, for any day — Lucy and the daily report ask
        for it without pulling the whole board."""
        return self._capture_grid(m, on or self._today(m), self._year(m, year_id))

    def _capture_grid(self, m: CurrentMember, on: date,
                      year: AcademicYear | None) -> PeriodCaptureGrid:
        """Class × period for one day: what was scheduled, and what was captured.

        Four queries flat — the grid, the periods, the exception counts and the
        rosters — never one per class.
        """
        ppd = year.periods_per_day if year else 8
        periods = day_periods(year.period_times if year else [], ppd)
        grid = PeriodCaptureGrid(
            date=on, periods_per_day=len(periods) or ppd,
            period_times=[p.model_dump() for p in periods])
        if year is None:
            return grid

        classes = {
            cid: _label(name, section) for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.org_id == m.org_id,
                       SchoolClass.academic_year_id == year.id)
                .order_by(SchoolClass.name, SchoolClass.section)).all()
        }
        if not classes:
            return grid

        scheduled: dict[tuple[uuid.UUID, int], tuple[uuid.UUID, str]] = {}
        for cid, pno, cs_id, sname in self.db.execute(
            select(TimetableSlot.class_id, TimetableSlot.period_no,
                   TimetableSlot.class_subject_id, Subject.name)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   TimetableSlot.class_id.in_(classes.keys()),
                   TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None),
                       TimetableSlot.effective_to > on))
        ).all():
            scheduled[(cid, int(pno))] = (cs_id, sname)

        captured: dict[tuple[uuid.UUID, int], tuple[str, int, int]] = {}
        for cid, pno, status, marked, absent, late in self.db.execute(
            select(ClassPeriod.class_id, ClassPeriod.period_no, ClassPeriod.status,
                   ClassPeriod.attendance_marked_at,
                   func.count(func.distinct(
                       case((AttendanceException.status == "absent", AttendanceException.id)))),
                   func.count(func.distinct(
                       case((AttendanceException.status == "late", AttendanceException.id)))))
            .outerjoin(AttendanceException, AttendanceException.period_id == ClassPeriod.id)
            .where(ClassPeriod.org_id == m.org_id, ClassPeriod.date == on,
                   ClassPeriod.class_id.in_(classes.keys()))
            .group_by(ClassPeriod.class_id, ClassPeriod.period_no, ClassPeriod.status,
                      ClassPeriod.attendance_marked_at)
        ).all():
            state = ("not_held" if status == "not_held"
                     else "marked" if marked is not None else "pending")
            captured[(cid, int(pno))] = (state, int(absent), int(late))

        rosters = {
            cid: int(n) for cid, n in self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_(classes.keys()))
                .group_by(Student.class_id)).all()
        }

        total_marked = total_expected = 0
        for cid, label in classes.items():
            cells: list[CaptureCell] = []
            marked = expected = 0
            for p in periods:
                key = (cid, p.period_no)
                sched = scheduled.get(key)
                cap = captured.get(key)
                if sched is None and cap is None:
                    cells.append(CaptureCell(period_no=p.period_no, state="free"))
                    continue
                expected += 1
                state, absent, late = cap or ("pending", 0, 0)
                if state == "marked":
                    marked += 1
                cells.append(CaptureCell(
                    period_no=p.period_no, state=state,
                    class_subject_id=sched[0] if sched else None,
                    subject_name=sched[1] if sched else None,
                    absent=absent, late=late))
            total_marked += marked
            total_expected += expected
            grid.rows.append(CaptureRow(
                class_id=cid, class_label=label, roster=rosters.get(cid, 0),
                cells=cells, marked=marked, expected=expected))
        grid.marked = total_marked
        grid.expected = total_expected
        return grid

    # ── staff presence ───────────────────────────────────────────────────────
    def staff_presence(self, m: CurrentMember, on: date | None = None) -> StaffPresence:
        on = on or self._today(m)
        roster = StaffAttendanceService(self.db).roster(m, on)
        absentees = [r for r in roster.roster if not r.present]
        due = self._periods_due(m.org_id, [r.member_id for r in absentees], on)
        covered = defaultdict(int)
        for s in SubstitutionService(self.db).live(m.org_id, on):
            if s.absent_member_id:
                covered[s.absent_member_id] += 1
        return StaffPresence(
            date=on, marked=roster.marked, total=roster.total,
            present=roster.present_count, absent=roster.absent_count,
            on_leave=sum(1 for r in absentees if r.on_leave),
            absentees=[
                StaffAbsentee(
                    member_id=r.member_id, name=r.name, role=r.role, on_leave=r.on_leave,
                    reason=r.leave_reason or r.note,
                    periods_due=due.get(r.member_id, 0),
                    periods_covered=covered.get(r.member_id, 0))
                for r in absentees
            ])

    def _periods_due(self, org_id: uuid.UUID, member_ids: list[uuid.UUID],
                     on: date) -> dict[uuid.UUID, int]:
        if not member_ids:
            return {}
        rows = self.db.execute(
            select(ClassSubject.teacher_member_id, func.count(TimetableSlot.id))
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == org_id, TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on),
                   ClassSubject.teacher_member_id.in_(member_ids))
            .group_by(ClassSubject.teacher_member_id)).all()
        return {mid: int(n) for mid, n in rows}

    # ── layer 2: the red list ────────────────────────────────────────────────
    def streaks(self, m: CurrentMember, min_days: int = STREAK_ALERT_DAYS,
                year_id: uuid.UUID | None = None) -> StreakBoard:
        today = self._today(m)
        since = today - timedelta(days=STREAK_WINDOW_DAYS)
        year = self._year(m, year_id)
        board = StreakBoard(as_of=today, min_days=min_days, window_days=STREAK_WINDOW_DAYS)
        if year is None:
            return board

        # Marked periods per class-day — the denominator for "absent in EVERY
        # marked period". One row per (class, date).
        marked = {
            (cid, d): int(n) for cid, d, n in self.db.execute(
                select(ClassPeriod.class_id, ClassPeriod.date, func.count(ClassPeriod.id))
                .where(ClassPeriod.org_id == m.org_id, ClassPeriod.date >= since,
                       ClassPeriod.date <= today,
                       ClassPeriod.attendance_marked_at.is_not(None))
                .group_by(ClassPeriod.class_id, ClassPeriod.date)).all()
        }
        if not marked:
            return board

        # Absences per student-day, in one grouped query over the same window.
        absent_rows = self.db.execute(
            select(AttendanceException.student_id, ClassPeriod.date,
                   func.count(AttendanceException.id))
            .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
            .where(AttendanceException.org_id == m.org_id,
                   AttendanceException.status == "absent",
                   ClassPeriod.date >= since, ClassPeriod.date <= today,
                   ClassPeriod.attendance_marked_at.is_not(None))
            .group_by(AttendanceException.student_id, ClassPeriod.date)
        ).all()
        if not absent_rows:
            return board

        by_student: dict[uuid.UUID, dict[date, int]] = defaultdict(dict)
        for sid, d, n in absent_rows:
            by_student[sid][d] = int(n)

        # Which class each of those students sits in — the streak is walked over
        # THEIR class's marked days, because a period marked in 6B says nothing
        # about a child in 7A.
        student_class = {
            sid: cid for sid, cid in self.db.execute(
                select(Student.id, Student.class_id)
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.id.in_(by_student.keys()))).all()
        }
        blocked = expand_blocked_dates(event_rows(self.db.scalars(
            select(CalendarEvent).where(CalendarEvent.org_id == m.org_id,
                                        CalendarEvent.academic_year_id == year.id))))
        working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5])
        # Per class: the school days it actually captured, newest first. Days
        # nobody marked are skipped, not counted as present — the school's gap in
        # capture is not evidence the child came in.
        class_days: dict[uuid.UUID, list[date]] = defaultdict(list)
        for (cid, d), n in sorted(marked.items(), key=lambda kv: kv[0][1], reverse=True):
            if n and d.weekday() in working and d not in blocked:
                class_days[cid].append(d)

        rows: list[AbsenceStreak] = []
        for sid, days in by_student.items():
            cid = student_class.get(sid)
            if cid is None:
                continue
            streak = 0
            last_present: date | None = None
            partial = 0
            for d in class_days.get(cid, []):
                n_absent = days.get(d, 0)
                n_marked = marked.get((cid, d), 0)
                if n_marked and n_absent >= n_marked:
                    streak += 1
                    continue
                # Present for at least one marked period — the run ends here.
                if n_absent:
                    partial += 1
                last_present = d
                break
            if streak >= min_days:
                rows.append(AbsenceStreak(
                    student_id=sid, full_name="", streak=streak,
                    last_present=last_present, days_partial=partial))
        if not rows:
            return board

        board.rows = self._decorate(m, rows, today)[:MAX_STREAK_ROWS]
        return board

    def _decorate(self, m: CurrentMember, rows: list[AbsenceStreak],
                  today: date) -> list[AbsenceStreak]:
        """Names, classes, class teachers, guardian counts and today's rail
        history — five queries for the whole list, never one per row."""
        ids = [r.student_id for r in rows]
        students = {
            sid: (name, roll, cid) for sid, name, roll, cid in self.db.execute(
                select(Student.id, Student.full_name, Student.roll_no, Student.class_id)
                .where(Student.id.in_(ids))).all()
        }
        class_ids = {cid for _n, _r, cid in students.values() if cid}
        classes = {
            cid: (_label(name, section), teacher) for cid, name, section, teacher
            in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section,
                       SchoolClass.class_teacher_member_id)
                .where(SchoolClass.id.in_(class_ids))).all()
        } if class_ids else {}
        teacher_ids = {t for _l, t in classes.values() if t}
        teachers = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(teacher_ids))).all()
        } if teacher_ids else {}
        guardians = {
            sid: int(n) for sid, n in self.db.execute(
                select(Guardian.student_id, func.count(Guardian.id))
                .where(Guardian.student_id.in_(ids))
                .group_by(Guardian.student_id)).all()
        }
        done = ActionService(self.db).done_today(m.org_id, "student", today, m.org.timezone)

        for r in rows:
            name, roll, cid = students.get(r.student_id, ("Unknown", None, None))
            label, teacher_member_id = classes.get(cid, (None, None)) if cid else (None, None)
            r.full_name = name
            r.roll_no = roll
            r.class_id = cid
            r.class_label = label
            r.class_teacher_member_id = teacher_member_id
            r.class_teacher_name = teachers.get(teacher_member_id)
            r.guardian_count = guardians.get(r.student_id, 0)
            r.reminded_today = ("guardian_reminded", r.student_id) in done
            r.followup_assigned_today = ("followup_assigned", r.student_id) in done
        rows.sort(key=lambda r: (-r.streak, r.class_label or "", r.full_name))
        return rows

    # ── layer 3: what one absence breaks ─────────────────────────────────────
    def staff_impact(self, m: CurrentMember, member_id: uuid.UUID,
                     on: date | None = None) -> StaffImpact:
        on = on or self._today(m)
        row = self.db.execute(
            select(Membership, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id == member_id, Membership.org_id == m.org_id)).first()
        if row is None:
            raise NotFoundError("Member")
        membership, name = row

        presence = self.staff_presence(m, on)
        mine = next((a for a in presence.absentees if a.member_id == member_id), None)
        year = self._year(m, None)
        periods = {p.period_no: p for p in day_periods(
            year.period_times if year else [], year.periods_per_day if year else 8)}

        due = self.db.execute(
            select(TimetableSlot.period_no, TimetableSlot.class_id, TimetableSlot.class_subject_id,
                   SchoolClass.name, SchoolClass.section, Subject.name)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .join(SchoolClass, SchoolClass.id == TimetableSlot.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(TimetableSlot.org_id == m.org_id, TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on),
                   ClassSubject.teacher_member_id == member_id)
            .order_by(TimetableSlot.period_no)).all()

        subs = {(s.class_id, s.period_no): s
                for s in SubstitutionService(self.db).live(m.org_id, on)}
        sub_names = {
            mid: nm for mid, nm in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_([s.substitute_member_id for s in subs.values()]))).all()
        } if subs else {}

        out_periods: list[ImpactPeriod] = []
        if due:
            candidates = self._candidates(m, on, [int(p) for p, *_ in due],
                                          {cs_id for _p, _c, cs_id, *_ in due}, member_id)
            for pno, cid, cs_id, cname, section, sname in due:
                clock = periods.get(int(pno))
                sub = subs.get((cid, int(pno)))
                out_periods.append(ImpactPeriod(
                    period_no=int(pno), start=clock.start if clock else None,
                    end=clock.end if clock else None,
                    class_id=cid, class_label=_label(cname, section),
                    class_subject_id=cs_id, subject_name=sname,
                    substitution_id=sub.id if sub else None,
                    covered_by_member_id=sub.substitute_member_id if sub else None,
                    covered_by_name=sub_names.get(sub.substitute_member_id) if sub else None,
                    candidates=[] if sub else candidates.get((int(pno), cs_id), [])))

        tasks = self._open_tasks(m, membership.user_id, on)
        return StaffImpact(
            member_id=member_id, name=name, role=membership.org_role, date=on,
            on_leave=bool(mine and mine.on_leave), reason=mine.reason if mine else None,
            periods=out_periods, tasks=tasks)

    def _candidates(self, m: CurrentMember, on: date, period_nos: list[int],
                    cs_ids: set[uuid.UUID], absent_member_id: uuid.UUID,
                    ) -> dict[tuple[int, uuid.UUID], list[SubstituteCandidate]]:
        """Who could take each affected period, ranked by who actually knows it.

        Ranking (DASH3 §4.1): teaches the same subject elsewhere > teaches this
        class for another subject > lightest teaching load today. The rank is a
        suggestion — the admin still chooses, which is why the reason is shown.
        """
        staff = list(self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == m.org_id, Membership.status == "active",
                   Membership.id != absent_member_id,
                   Membership.org_role.in_(("teacher", "admin")))
            .order_by(User.name)).all())
        if not staff or not cs_ids:
            return {}

        wanted = {
            cs_id: (subject_id, class_id) for cs_id, subject_id, class_id in self.db.execute(
                select(ClassSubject.id, ClassSubject.subject_id, ClassSubject.class_id)
                .where(ClassSubject.id.in_(cs_ids))).all()
        }
        # Everyone's whole teaching profile, in one query: which subjects and
        # classes they take, and which periods they are busy in today.
        teaches_subject: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        teaches_class: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for tid, subject_id, class_id in self.db.execute(
            select(ClassSubject.teacher_member_id, ClassSubject.subject_id,
                   ClassSubject.class_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.teacher_member_id.is_not(None))).all():
            teaches_subject[tid].add(subject_id)
            teaches_class[tid].add(class_id)

        busy: dict[uuid.UUID, set[int]] = defaultdict(set)
        load: dict[uuid.UUID, int] = defaultdict(int)
        for tid, pno in self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.period_no)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id, TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on),
                   ClassSubject.teacher_member_id.is_not(None))).all():
            busy[tid].add(int(pno))
            load[tid] += 1
        for s in self.db.scalars(
            select(PeriodSubstitution).where(
                PeriodSubstitution.org_id == m.org_id, PeriodSubstitution.date == on,
                PeriodSubstitution.cancelled_at.is_(None))):
            busy[s.substitute_member_id].add(s.period_no)
        away = {a.member_id for a in self.staff_presence(m, on).absentees}

        out: dict[tuple[int, uuid.UUID], list[SubstituteCandidate]] = {}
        for pno in period_nos:
            for cs_id in cs_ids:
                subject_id, class_id = wanted.get(cs_id, (None, None))
                ranked: list[tuple[int, SubstituteCandidate]] = []
                for mid, name in staff:
                    if pno in busy[mid] or mid in away:
                        continue
                    same_subject = subject_id in teaches_subject.get(mid, set())
                    same_class = class_id in teaches_class.get(mid, set())
                    if same_subject:
                        tier, reason = 0, "teaches this subject elsewhere"
                    elif same_class:
                        tier, reason = 1, "teaches this class"
                    else:
                        tier, reason = 2, f"free · {load.get(mid, 0)} periods today"
                    ranked.append((tier * 100 + load.get(mid, 0), SubstituteCandidate(
                        member_id=mid, name=name, reason=reason, rank=0,
                        teaches_subject_elsewhere=same_subject,
                        teaches_this_class=same_class,
                        teaching_periods_today=load.get(mid, 0))))
                ranked.sort(key=lambda t: (t[0], t[1].name))
                picked = []
                for i, (_score, c) in enumerate(ranked[:6], start=1):
                    c.rank = i
                    picked.append(c)
                out[(pno, cs_id)] = picked
        return out

    def _open_tasks(self, m: CurrentMember, user_id: uuid.UUID, on: date) -> list[ImpactTask]:
        """An absent admin's blast radius is their work, not their periods.

        Due today or already overdue, criticals first — the rows a colleague
        would have to pick up. The date cut is applied in Python against the
        org-local day, because `due_at` is a timestamp and "due today" is a
        question about the school's calendar, not UTC's.
        """
        rows = self.db.execute(
            select(TaskInstance, Board.name)
            .join(Board, Board.id == TaskInstance.board_id)
            .where(TaskInstance.org_id == m.org_id, TaskInstance.assignee_id == user_id,
                   TaskInstance.status == "open", TaskInstance.due_at.is_not(None),
                   TaskInstance.due_at < datetime.combine(
                       on + timedelta(days=1), datetime.min.time(), tzinfo=UTC))
            .order_by(TaskInstance.is_critical.desc(), TaskInstance.due_at)
            .limit(20)).all()
        return [
            ImpactTask(
                task_id=t.id, title=t.title, board_name=board_name, due_at=t.due_at,
                is_critical=t.is_critical,
                days_overdue=max(0, (on - t.due_at.date()).days))
            for t, board_name in rows
        ]
