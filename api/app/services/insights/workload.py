"""M3 — who is teaching, working or free (DASH3 §4.3).

**Right now.** The school clock (`services/school_clock.py`) says which period is
running; the timetable says who is in a classroom; the timesheet says what the
rest are doing; staff attendance says who is not in the building. Four facts, one
board:

    Period 4 · 11:20–12:00 — 9 teaching · 4 free · 2 absent

with every list named. Outside teaching hours it says so rather than inventing a
period, and a school that never entered its timings gets `unset` — not a guess.

**What the free ones are doing** comes from `timesheet_entries` (SF-1), which is
capture rather than inference. The original plan derived this from task
categories; a real timesheet is better data and it is what shipped. A teacher
with a free period and no entry shows as exactly that, which is itself the
finding — `unfilled_free_periods` counts them.

**The week** is teaching periods per teacher against the org mean, with over/under
flags. `TimetableService.teacher_week` does one teacher; this is the batched
org-wide version — the whole staff in three queries, because the alternative is
one remote round-trip per person.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.work_types import label_for
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    LeaveRequest,
    Membership,
    PeriodSubstitution,
    SchoolClass,
    Subject,
    TaskInstance,
    TimesheetEntry,
    TimetableSlot,
    User,
)
from app.schemas.insights import (
    LeavePulse,
    LeaveQueueRow,
    LoadStripCell,
    NowBoard,
    NowPerson,
    StaffBoard,
    TeacherLoad,
    WorkBucket,
    WorkloadWeek,
)
from app.services.calendar import event_rows, expand_blocked_dates
from app.services.insights.attendance import AttendanceInsights
from app.services.leave import LeaveService
from app.services.school_clock import day_periods, phase, today_in
from app.services.staff_attendance import StaffAttendanceService

# Over/under-load is a share of the org mean, not an absolute count: a school
# with 5 periods a day and one with 9 cannot share a threshold.
OVERLOAD_RATIO = 1.2
UNDERLOAD_RATIO = 0.8


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class WorkloadInsights:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))

    def _staff(self, org_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, str, str]]:
        return [
            (mid, uid, name, role) for mid, uid, name, role in self.db.execute(
                select(Membership.id, Membership.user_id, User.name, Membership.org_role)
                .join(User, User.id == Membership.user_id)
                .where(Membership.org_id == org_id, Membership.status == "active")
                .order_by(User.name)).all()
        ]

    def _grid_day(self, org_id: uuid.UUID, on: date
                  ) -> dict[uuid.UUID, dict[int, tuple[str, str]]]:
        """teacher → period_no → (class_label, subject). One query for the day."""
        out: dict[uuid.UUID, dict[int, tuple[str, str]]] = defaultdict(dict)
        for tid, pno, cname, section, sname in self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.period_no,
                   SchoolClass.name, SchoolClass.section, Subject.name)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .join(SchoolClass, SchoolClass.id == TimetableSlot.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(TimetableSlot.org_id == org_id, TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on),
                   ClassSubject.teacher_member_id.is_not(None))).all():
            out[tid][int(pno)] = (_label(cname, section), sname)
        return out

    def _subs_day(self, org_id: uuid.UUID, on: date
                  ) -> dict[uuid.UUID, dict[int, tuple[str, str | None]]]:
        rows = list(self.db.scalars(
            select(PeriodSubstitution).where(
                PeriodSubstitution.org_id == org_id, PeriodSubstitution.date == on,
                PeriodSubstitution.cancelled_at.is_(None))))
        if not rows:
            return {}
        labels = {
            cid: _label(name, section) for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.id.in_([r.class_id for r in rows]))).all()
        }
        subjects = {
            cs_id: name for cs_id, name in self.db.execute(
                select(ClassSubject.id, Subject.name)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .where(ClassSubject.id.in_([r.class_subject_id for r in rows
                                            if r.class_subject_id]))).all()
        }
        out: dict[uuid.UUID, dict[int, tuple[str, str | None]]] = defaultdict(dict)
        for r in rows:
            out[r.substitute_member_id][r.period_no] = (
                labels.get(r.class_id, "?"), subjects.get(r.class_subject_id))
        return out

    def _timesheet_day(self, org_id: uuid.UUID, on: date
                       ) -> dict[uuid.UUID, dict[int, TimesheetEntry]]:
        out: dict[uuid.UUID, dict[int, TimesheetEntry]] = defaultdict(dict)
        for e in self.db.scalars(
            select(TimesheetEntry).where(TimesheetEntry.org_id == org_id,
                                         TimesheetEntry.date == on)):
            out[e.member_id][e.period_no] = e
        return out

    def _open_tasks(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        return {
            uid: int(n) for uid, n in self.db.execute(
                select(TaskInstance.assignee_id, func.count(TaskInstance.id))
                .where(TaskInstance.org_id == org_id, TaskInstance.status == "open",
                       TaskInstance.assignee_id.is_not(None))
                .group_by(TaskInstance.assignee_id)).all()
        }

    # ── the whole people tab, in one payload ─────────────────────────────────
    def staff_board(self, m: CurrentMember, week_start: date | None = None) -> StaffBoard:
        today = self._today(m)
        presence = AttendanceInsights(self.db).staff_presence(m, today)
        board = StaffBoard(
            date=today, presence=presence, leave=self._leave_pulse(m, today),
            now=self.now(m), week=self.week(m, week_start),
            uncovered_periods=sum(max(0, a.periods_due - a.periods_covered)
                                  for a in presence.absentees))
        return board

    def _leave_pulse(self, m: CurrentMember, today: date) -> LeavePulse:
        """Leave as the admin meets it in the morning: what is waiting, who is
        out, and how much of the month's allowance the school has already spent.

        `LeaveService.list_requests` carries the policy warnings SF-1 computes —
        over-policy is flagged, never blocked — so the queue arrives ready to
        decide on rather than needing a second call per row.
        """
        service = LeaveService(self.db)
        listing = service.list_requests(m, status="pending")
        policy = listing.policy
        month_start = today.replace(day=1)
        approved_this_month = int(self.db.scalar(
            select(func.coalesce(func.sum(LeaveRequest.days), 0))
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.status == "approved",
                   LeaveRequest.start_date >= month_start,
                   LeaveRequest.start_date <= today)) or 0)
        on_leave_today = int(self.db.scalar(
            select(func.count(LeaveRequest.id))
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.status == "approved",
                   LeaveRequest.start_date <= today, LeaveRequest.end_date >= today)) or 0)
        return LeavePulse(
            pending=listing.pending_count, on_leave_today=on_leave_today,
            approved_days_this_month=approved_this_month,
            allowed_per_year=policy.leaves_per_year,
            allowed_per_month=policy.leaves_per_month,
            queue=[
                LeaveQueueRow(
                    request_id=r.id, member_id=r.member_id, member_name=r.member_name,
                    start_date=r.start_date, end_date=r.end_date, days=r.days,
                    reason=r.reason, warnings=r.warnings, created_at=r.created_at)
                for r in listing.requests[:15]
            ])

    # ── the live board ───────────────────────────────────────────────────────
    def now(self, m: CurrentMember, at: datetime | None = None) -> NowBoard:
        tz = ZoneInfo(m.org.timezone)
        moment = at or datetime.now(tz)
        on = moment.date()
        year = self._year(m.org_id)
        period_times = year.period_times if year else []
        state, period_no = phase(period_times, moment, m.org.timezone)
        periods = {p.period_no: p for p in day_periods(
            period_times, year.periods_per_day if year else 8)}
        clock = periods.get(period_no) if period_no else None

        board = NowBoard(
            now=time(moment.hour, moment.minute), date=on, phase=state, period_no=period_no,
            period_start=clock.start if clock else None,
            period_end=clock.end if clock else None)

        # A holiday or a non-working weekday outranks the clock — the timings say
        # "period 4" every Sunday, and reporting that would be nonsense.
        if year is not None:
            blocked = expand_blocked_dates(event_rows(self.db.scalars(
                select(CalendarEvent).where(CalendarEvent.org_id == m.org_id,
                                            CalendarEvent.academic_year_id == year.id))))
            working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5])
            if on in blocked or on.weekday() not in working:
                board.phase = "holiday"
                board.period_no = None
                return board

        presence = StaffAttendanceService(self.db).roster(m, on)
        board.staff_marked = presence.marked
        away = {r.member_id: r for r in presence.roster if not r.present}

        teaching = self._grid_day(m.org_id, on)
        subs = self._subs_day(m.org_id, on)
        entries = self._timesheet_day(m.org_id, on)
        tasks = self._open_tasks(m.org_id)

        for mid, uid, name, role in self._staff(m.org_id):
            if mid in away:
                r = away[mid]
                board.absent.append(NowPerson(
                    member_id=mid, name=name, role=role,
                    reason=r.leave_reason or r.note or ("on leave" if r.on_leave else None)))
                continue
            if board.phase != "period" or period_no is None:
                continue
            slot = teaching.get(mid, {}).get(period_no)
            sub = subs.get(mid, {}).get(period_no)
            if slot or sub:
                label, subject = slot or sub
                board.teaching.append(NowPerson(
                    member_id=mid, name=name, role=role, class_label=label,
                    subject_name=subject, substituting=slot is None))
                continue
            entry = entries.get(mid, {}).get(period_no)
            if entry is not None:
                board.working.append(NowPerson(
                    member_id=mid, name=name, role=role, work_type=entry.work_type,
                    work_label=label_for(entry.work_type), note=entry.note,
                    open_tasks=tasks.get(uid, 0)))
                continue
            board.free.append(NowPerson(
                member_id=mid, name=name, role=role, open_tasks=tasks.get(uid, 0)))
        return board

    # ── the week ─────────────────────────────────────────────────────────────
    def week(self, m: CurrentMember, week_start: date | None = None) -> WorkloadWeek:
        today = self._today(m)
        anchor = week_start or today
        monday = anchor - timedelta(days=anchor.weekday())
        sunday = monday + timedelta(days=6)
        year = self._year(m.org_id)
        ppd = year.periods_per_day if year else 8
        periods = day_periods(year.period_times if year else [], ppd)
        working = list(year.working_weekdays or [0, 1, 2, 3, 4, 5]) if year \
            else [0, 1, 2, 3, 4, 5]

        out = WorkloadWeek(
            week_start=monday, date=today, working_weekdays=working,
            periods_per_day=len(periods) or ppd)

        # Teaching periods for the WEEK, one query: the grid is weekday-shaped, so
        # a slot counts once for each working weekday it falls on.
        week_teaching: dict[uuid.UUID, int] = defaultdict(int)
        for tid, weekday, n in self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.weekday,
                   func.count(TimetableSlot.id))
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   TimetableSlot.effective_from <= sunday,
                   or_(TimetableSlot.effective_to.is_(None),
                       TimetableSlot.effective_to > monday),
                   ClassSubject.teacher_member_id.is_not(None))
            .group_by(ClassSubject.teacher_member_id, TimetableSlot.weekday)).all():
            if int(weekday) in working:
                week_teaching[tid] += int(n)

        week_work: dict[uuid.UUID, int] = defaultdict(int)
        buckets: dict[str, int] = defaultdict(int)
        for mid, work_type, n in self.db.execute(
            select(TimesheetEntry.member_id, TimesheetEntry.work_type,
                   func.count(TimesheetEntry.id))
            .where(TimesheetEntry.org_id == m.org_id, TimesheetEntry.date >= monday,
                   TimesheetEntry.date <= sunday)
            .group_by(TimesheetEntry.member_id, TimesheetEntry.work_type)).all():
            week_work[mid] += int(n)
            buckets[work_type] += int(n)
        out.buckets = sorted(
            (WorkBucket(key=k, label=label_for(k), periods=v) for k, v in buckets.items()),
            key=lambda b: -b.periods)

        # Today's strip — the same three reads the live board uses, reused.
        teaching_today = self._grid_day(m.org_id, today)
        subs_today = self._subs_day(m.org_id, today)
        entries_today = self._timesheet_day(m.org_id, today)
        presence = StaffAttendanceService(self.db).roster(m, today)
        away = {r.member_id for r in presence.roster if not r.present}
        tasks = self._open_tasks(m.org_id)

        staff = self._staff(m.org_id)
        teaching_counts = [week_teaching.get(mid, 0) for mid, *_ in staff]
        # The mean is over people who teach at all — including office staff who
        # never take a class would drag it toward zero and flag every teacher as
        # overloaded.
        teachers_only = [c for c in teaching_counts if c > 0]
        mean = round(sum(teachers_only) / len(teachers_only), 1) if teachers_only else 0.0
        out.mean_teaching = mean

        unfilled = 0
        for mid, uid, name, role in staff:
            strip: list[LoadStripCell] = []
            for p in periods:
                if mid in away:
                    strip.append(LoadStripCell(period_no=p.period_no, kind="absent"))
                    continue
                slot = teaching_today.get(mid, {}).get(p.period_no)
                if slot:
                    strip.append(LoadStripCell(period_no=p.period_no, kind="class",
                                               label=f"{slot[0]} {slot[1]}"))
                    continue
                sub = subs_today.get(mid, {}).get(p.period_no)
                if sub:
                    strip.append(LoadStripCell(period_no=p.period_no, kind="substituting",
                                               label=f"{sub[0]} {sub[1] or ''}".strip()))
                    continue
                entry = entries_today.get(mid, {}).get(p.period_no)
                if entry is not None:
                    strip.append(LoadStripCell(period_no=p.period_no, kind="work",
                                               label=label_for(entry.work_type)))
                    continue
                strip.append(LoadStripCell(period_no=p.period_no, kind="free"))
                if today.weekday() in working:
                    unfilled += 1

            teach = week_teaching.get(mid, 0)
            work = week_work.get(mid, 0)
            slots = (len(periods) or ppd) * len(working)
            flag = "balanced"
            if mean and teach:
                if teach >= mean * OVERLOAD_RATIO:
                    flag = "over"
                elif teach <= mean * UNDERLOAD_RATIO:
                    flag = "under"
            out.teachers.append(TeacherLoad(
                member_id=mid, name=name, role=role, teaching_periods=teach,
                work_periods=work, free_periods=max(0, slots - teach - work),
                delta_vs_mean=round(teach - mean, 1), load_flag=flag,
                open_tasks=tasks.get(uid, 0), today=strip))
        out.teachers.sort(key=lambda t: (-t.teaching_periods, t.name))
        out.unfilled_free_periods = unfilled
        return out
