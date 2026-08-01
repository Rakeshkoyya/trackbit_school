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
with a free period and no entry simply reads as free — `D-23` decided an unfilled
period *is* free, and V1-4 deleted the tile that counted them (`S-76`): it was
the school's adoption rate wearing the costume of a workload figure, and it was
at its reddest at 8:30am when nothing could have been logged yet.

**The week** is teaching periods per teacher against the org mean, with over/under
flags, plus the hostel evenings each one runs — reported beside the periods and
never added to them (`S-68`). `TimetableService.teacher_week` does one teacher;
this is the batched org-wide version — the whole staff in three queries, because
the alternative is one remote round-trip per person.

**The slack profile** (`D-21`/`S-66`) is the one genuinely new chart: teaching /
working / free per (weekday, period) across people who teach at all, so the admin
can find the one slot where the whole staff could meet. Its job is finding slack,
not watching people — there is no ranking here and there never will be (`S-67`).
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
    SchoolClass,
    Subject,
    TaskInstance,
    TimesheetEntry,
    TimetableSlot,
    User,
)

# Aliased: `Session` here is sqlalchemy's, and the hostel block is a model.
from app.models import Session as HostelSession
from app.schemas.insights import (
    LeavePulse,
    LeaveQueueRow,
    LoadStripCell,
    NowBoard,
    NowPerson,
    SlackProfile,
    SlackSlot,
    StaffBoard,
    TeacherLoad,
    UpcomingCover,
    WorkBucket,
    WorkloadWeek,
)
from app.services.calendar import event_rows, expand_blocked_dates, org_working_days
from app.services.insights.attendance import AttendanceInsights
from app.services.leave import LeaveService
from app.services.school_clock import day_periods, phase, today_in
from app.services.staff_attendance import StaffAttendanceService
from app.services.substitution import SubstitutionService, covers_between

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
        # One computation (ux §9): the same read the timesheet unions in (Q-37).
        return {
            mid: {pno: pair for (_d, pno), pair in cells.items()}
            for mid, cells in covers_between(self.db, org_id, on, on).items()
        }

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
        # float, not int: `days` is numeric since V1-4 and int() would round
        # every half-day in the month away to nothing.
        approved_this_month = float(self.db.scalar(
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
            upcoming=self.upcoming_cover(m, today),
            queue=[
                LeaveQueueRow(
                    request_id=r.id, member_id=r.member_id, member_name=r.member_name,
                    start_date=r.start_date, end_date=r.end_date, days=r.days,
                    is_half_day=r.is_half_day, portion=r.portion,
                    reason=r.reason, warnings=r.warnings, created_at=r.created_at,
                    cover_dates=r.cover_dates)
                for r in listing.requests[:15]
            ])

    # ── approved leave that still needs cover (D-27 / S-81) ──────────────────
    def upcoming_cover(self, m: CurrentMember, today: date,
                       horizon_days: int = 14) -> list[UpcomingCover]:
        """Future days someone is already approved away and periods are open.

        Four queries for the whole horizon, whatever the headcount: the approved
        leaves, the working days, the timetable rows for those teachers, and the
        substitutions already assigned. The alternative — asking per leave, per
        day — is a round-trip per row against a remote database, on a payload the
        admin loads every morning.

        Today is deliberately excluded: today's uncovered periods already have
        their own rail item off staff attendance, and two rows for one problem is
        how a rail becomes a list nobody reads.
        """
        horizon = today + timedelta(days=horizon_days)
        leaves = self.db.execute(
            select(LeaveRequest.id, LeaveRequest.member_id, LeaveRequest.start_date,
                   LeaveRequest.end_date, LeaveRequest.is_half_day, LeaveRequest.portion,
                   User.name)
            .join(Membership, Membership.id == LeaveRequest.member_id)
            .join(User, User.id == Membership.user_id)
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.status == "approved",
                   LeaveRequest.end_date > today, LeaveRequest.start_date <= horizon)).all()
        if not leaves:
            return []

        working = set(org_working_days(self.db, m.org_id, today + timedelta(days=1), horizon))
        member_ids = {row[1] for row in leaves}
        by_weekday: dict[uuid.UUID, dict[int, list[int]]] = defaultdict(
            lambda: defaultdict(list))
        for tid, weekday, pno in self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.weekday,
                   TimetableSlot.period_no)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   TimetableSlot.effective_from <= horizon,
                   or_(TimetableSlot.effective_to.is_(None),
                       TimetableSlot.effective_to > today),
                   ClassSubject.teacher_member_id.in_(member_ids))).all():
            by_weekday[tid][int(weekday)].append(int(pno))

        covered: dict[tuple[uuid.UUID, date], int] = defaultdict(int)
        from app.models import PeriodSubstitution  # noqa: PLC0415

        for absent_id, on in self.db.execute(
            select(PeriodSubstitution.absent_member_id, PeriodSubstitution.date)
            .where(PeriodSubstitution.org_id == m.org_id,
                   PeriodSubstitution.date > today, PeriodSubstitution.date <= horizon,
                   PeriodSubstitution.cancelled_at.is_(None),
                   PeriodSubstitution.absent_member_id.is_not(None))).all():
            covered[(absent_id, on)] += 1

        subs = SubstitutionService(self.db)
        out: list[UpcomingCover] = []
        for req_id, member_id, start, end, is_half, portion, name in leaves:
            d = max(start, today + timedelta(days=1))
            while d <= min(end, horizon):
                if d in working:
                    periods = by_weekday.get(member_id, {}).get(d.weekday(), [])
                    if is_half:
                        half = subs.half_periods(m.org_id, d, portion)
                        periods = [p for p in periods if p in half]
                    done = covered.get((member_id, d), 0)
                    if len(periods) > done:
                        out.append(UpcomingCover(
                            date=d, member_id=member_id, member_name=name,
                            request_id=req_id, periods_due=len(periods),
                            periods_covered=done))
                d += timedelta(days=1)
        out.sort(key=lambda r: (r.date, r.member_name))
        return out[:20]

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
                    work_label=label_for(entry.work_type, m.org), note=entry.note,
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

        # S-68 — the warden's evening. `sessions` is a staffed, recurring,
        # timetabled block (owner + weekdays + time) that no load surface has
        # ever read, so a teacher running prep six nights a week appeared on
        # every board as somebody with a light load. Counted separately, never
        # summed into teaching periods.
        evenings: dict[uuid.UUID, int] = defaultdict(int)
        for owner, weekdays in self.db.execute(
            select(HostelSession.owner_member_id, HostelSession.weekdays)
            .where(HostelSession.org_id == m.org_id, HostelSession.active.is_(True),
                   HostelSession.owner_member_id.is_not(None))).all():
            evenings[owner] += sum(1 for d in (weekdays or []) if int(d) in working)

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
            (WorkBucket(key=k, label=label_for(k, m.org), periods=v)
             for k, v in buckets.items()),
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
                                               label=label_for(entry.work_type, m.org)))
                    continue
                strip.append(LoadStripCell(period_no=p.period_no, kind="free"))

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
                evening_sessions=evenings.get(mid, 0),
                delta_vs_mean=round(teach - mean, 1), load_flag=flag,
                open_tasks=tasks.get(uid, 0), today=strip))
        out.teachers.sort(key=lambda t: (-t.teaching_periods, t.name))
        out.slack = self._slack(m, monday, working, periods, week_teaching)
        return out

    # ── the slack profile (D-21 / S-66) ──────────────────────────────────────
    def _slack(self, m: CurrentMember, monday: date, working: list[int],
               periods, week_teaching: dict[uuid.UUID, int]) -> SlackProfile:
        """Where the week's slack is — for finding a meeting slot, not for
        watching people.

        The denominator is **people who teach at all**, the same population the
        load mean uses: including the office clerk's eight free periods would
        make every slot look wide open and the answer would be wrong.

        Two more queries on top of what `week` already read — the grid pivoted by
        (weekday, period) and the week's timesheet entries by (weekday, period).
        `free` here means "free or unrecorded" (`D-23`/`S-76`); the screen says so
        once, which is the honest way to keep this chart rather than delete it.
        """
        teachers = {mid for mid, n in week_teaching.items() if n > 0}
        profile = SlackProfile(
            week_start=monday, teacher_count=len(teachers),
            periods_per_day=len(periods), working_weekdays=working)
        if not teachers or not periods:
            return profile

        busy: dict[tuple[int, int], set[uuid.UUID]] = defaultdict(set)
        for tid, weekday, pno in self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.weekday,
                   TimetableSlot.period_no)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   TimetableSlot.effective_from <= monday + timedelta(days=6),
                   or_(TimetableSlot.effective_to.is_(None),
                       TimetableSlot.effective_to > monday),
                   ClassSubject.teacher_member_id.in_(teachers))).all():
            busy[(int(weekday), int(pno))].add(tid)

        recorded: dict[tuple[int, int], set[uuid.UUID]] = defaultdict(set)
        for mid, on, pno in self.db.execute(
            select(TimesheetEntry.member_id, TimesheetEntry.date, TimesheetEntry.period_no)
            .where(TimesheetEntry.org_id == m.org_id, TimesheetEntry.date >= monday,
                   TimesheetEntry.date <= monday + timedelta(days=6),
                   TimesheetEntry.member_id.in_(teachers))).all():
            recorded[(on.weekday(), int(pno))].add(mid)

        best: tuple[int, int, int] | None = None
        for weekday in working:
            for p in periods:
                key = (weekday, p.period_no)
                teaching = len(busy[key])
                # A period she is teaching outranks anything she wrote down for
                # it — one source of truth per period, the timesheet's own rule.
                doing = len(recorded[key] - busy[key])
                free = max(0, len(teachers) - teaching - doing)
                profile.slots.append(SlackSlot(
                    weekday=weekday, period_no=p.period_no,
                    teaching=teaching, working=doing, free=free))
                if best is None or free > best[2]:
                    best = (weekday, p.period_no, free)
        if best is not None and best[2] > 0:
            profile.best_weekday, profile.best_period_no, profile.best_free = best
        return profile
