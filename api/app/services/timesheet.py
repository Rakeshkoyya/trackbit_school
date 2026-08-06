"""The teacher's timesheet — what a non-teaching period was spent on (SF-1).

A teacher's week is already half-written: the timetable knows every period they
teach. The timesheet fills in the rest. Open it in the evening or before the day
starts, tap a free period, say what it is for — notebook checking, exam work, an
event, a student — and the school finally knows what its staff are actually
doing with their time.

Two rules keep it honest:

  * **Teaching periods are never stored here.** They live in `timetable_slots`
    and are rendered read-only. Copying them would create a second source of
    truth that drifts the instant the grid is edited, and "who is free right now"
    would start disagreeing with the timetable.
  * **One entry per period.** A period is free, teaching, or exactly one piece of
    work. Overlapping work would make any workload total meaningless.

Everything is editable all day — a plan that cannot be corrected at 3pm is a plan
nobody writes at 8am.

**V1-4 gave it three altitudes** (`D-18`/`S-64`): month = shape (one cell per
DAY, a navigator), week = edit (the grid, already here), day = do (the vertical
timeline including breaks). Plus `S-75` — the picker's suggestion, computed from
what she has recorded in that slot before and **never written**; `S-68` — the
hostel evenings she runs, reported beside the periods and never inside them; and
`S-70` — the week's counters are HER record, which is the only thing this module
gives back to the person feeding it.

Nothing here ranks anybody, scores completeness, or reaches pay (`D-25`/`S-67`).
A teacher who knows her timesheet cannot cost her money has no reason to write
anything but the truth.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.staff import not_operator
from app.core.work_types import label_for, normalize
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    LeaveRequest,
    Membership,
    SchoolClass,
    Subject,
    TimesheetEntry,
    TimetableSlot,
    User,
)

# Aliased: `Session` here is sqlalchemy's, and the hostel block is a model.
from app.models import Session as HostelSession
from app.schemas.staff import (
    TimesheetBreak,
    TimesheetDay,
    TimesheetEntryIn,
    TimesheetMonth,
    TimesheetMonthDay,
    TimesheetSlot,
    TimesheetWeek,
)
from app.services.calendar import expand_blocked_dates
from app.services.school_clock import breaks_of, day_periods, today_in
from app.services.staff_month import parse_month
from app.services.substitution import SubstitutionService, covers_between


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")




class TimesheetService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(AcademicYear.org_id == org_id,
                                       AcademicYear.is_active.is_(True)))

    def _resolve_member(self, m: CurrentMember, member_id: uuid.UUID | None) -> uuid.UUID:
        """A teacher owns exactly one timesheet — their own. Admins read all."""
        if member_id is None or member_id == m.membership.id:
            return m.membership.id
        if not m.is_admin:
            raise ForbiddenError("You can only open your own timesheet")
        found = self.db.scalar(
            select(Membership.id).where(Membership.id == member_id,
                                        Membership.org_id == m.org_id))
        if found is None:
            raise NotFoundError("Member")
        return found

    def _member_name(self, member_id: uuid.UUID) -> str:
        return self.db.scalar(
            select(User.name).join(Membership, Membership.user_id == User.id)
            .where(Membership.id == member_id)) or "—"

    # ── the teaching half, straight off the grid ─────────────────────────────
    def _teaching(self, org_id: uuid.UUID, member_id: uuid.UUID, start: date, end: date
                  ) -> dict[tuple[int, int], tuple[str, str]]:
        """(weekday, period_no) → (class_label, subject_name) for this teacher.

        One query for the whole week. The effective-dating window is evaluated
        against the week's span, so a grid change mid-week still resolves.
        """
        rows = self.db.execute(
            select(TimetableSlot.weekday, TimetableSlot.period_no,
                   SchoolClass.name, SchoolClass.section, Subject.name)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .join(SchoolClass, SchoolClass.id == TimetableSlot.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(TimetableSlot.org_id == org_id,
                   ClassSubject.teacher_member_id == member_id,
                   TimetableSlot.effective_from <= end,
                   or_(TimetableSlot.effective_to.is_(None),
                       TimetableSlot.effective_to > start))
        ).all()
        return {
            (int(wd), int(pn)): (_label(cname, section), sname)
            for wd, pn, cname, section, sname in rows
        }

    def _entries(self, org_id: uuid.UUID, member_id: uuid.UUID, start: date, end: date
                 ) -> dict[tuple[date, int], TimesheetEntry]:
        rows = self.db.scalars(
            select(TimesheetEntry).where(
                TimesheetEntry.org_id == org_id, TimesheetEntry.member_id == member_id,
                TimesheetEntry.date >= start, TimesheetEntry.date <= end))
        return {(r.date, r.period_no): r for r in rows}

    # ── assembly ─────────────────────────────────────────────────────────────
    def _usual(self, org_id: uuid.UUID, member_id: uuid.UUID, before: date,
               weeks: int = 6) -> dict[tuple[int, int], str]:
        """(weekday, period_no) → the category she usually records there (S-75).

        The picker opens with it highlighted and **writes nothing** — no row
        exists that a human did not put there, which is the property `D-23`
        removed any other way to guarantee. Six weeks back, one query, most
        frequent wins and ties break toward the most recent.
        """
        rows = self.db.execute(
            select(TimesheetEntry.date, TimesheetEntry.period_no, TimesheetEntry.work_type)
            .where(TimesheetEntry.org_id == org_id, TimesheetEntry.member_id == member_id,
                   TimesheetEntry.date >= before - timedelta(weeks=weeks),
                   TimesheetEntry.date < before)
            .order_by(TimesheetEntry.date)).all()
        tally: dict[tuple[int, int], dict[str, int]] = {}
        for on, pno, work_type in rows:
            tally.setdefault((on.weekday(), int(pno)), {})
            counts = tally[(on.weekday(), int(pno))]
            counts[work_type] = counts.get(work_type, 0) + 1
        return {
            key: max(counts.items(), key=lambda kv: kv[1])[0]
            for key, counts in tally.items()
        }

    def _evenings(self, org_id: uuid.UUID, member_id: uuid.UUID) -> dict[int, list[str]]:
        """weekday → the hostel blocks she runs (S-68).

        Read-only, like the timetable — the session grid owns them. A warden
        running evening prep six nights a week was invisible on every load
        surface in the product before this.
        """
        out: dict[int, list[str]] = {}
        for name, weekdays, at in self.db.execute(
            select(HostelSession.name, HostelSession.weekdays, HostelSession.time)
            .where(HostelSession.org_id == org_id, HostelSession.active.is_(True),
                   HostelSession.owner_member_id == member_id)).all():
            for wd in weekdays or []:
                out.setdefault(int(wd), []).append(
                    f"{name}{f' · {at}' if at else ''}")
        return out

    def _build_day(self, on: date, periods, working: set[int], teaching, entries,
                   covers=None, away_reason: str | None = None, org=None,
                   usual=None, breaks=None, evenings=None,
                   away_periods: set[int] | None = None) -> TimesheetDay:
        # S-72: a person who is away has no free periods. Every away cell reads
        # 'away' and nothing counts — the old shape showed an absent teacher as
        # eight free periods on the screen used to find cover.
        #
        # V1-4 (D-04): `away_periods` narrows that to the half they missed. A
        # half-day teacher who taught the morning must not read as a blank day —
        # she took those classes, and the record has to say so.
        evening_labels = (evenings or {}).get(on.weekday(), [])
        if away_reason is not None and away_periods is None:
            return TimesheetDay(
                date=on, weekday=on.weekday(), is_working_day=on.weekday() in working,
                slots=[TimesheetSlot(period_no=p.period_no, start=p.start, end=p.end,
                                     kind="away", note=away_reason) for p in periods],
                teaching_count=0, work_count=0, free_count=0, cover_count=0,
                breaks=breaks or [], evening_labels=evening_labels)
        covers = covers or {}
        usual = usual or {}
        slots: list[TimesheetSlot] = []
        teach = work = free = cover = 0
        for p in periods:
            if away_periods is not None and p.period_no in away_periods:
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="away",
                    note=away_reason))
                continue
            taught = teaching.get((on.weekday(), p.period_no))
            covering = covers.get((on, p.period_no))
            entry = entries.get((on, p.period_no))
            if taught:
                # The grid wins. An entry that somehow exists under a teaching
                # period is ignored rather than deleted — the grid may move back.
                teach += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="class",
                    class_label=taught[0], subject_name=taught[1]))
            elif covering:
                # Q-37: a live substitution outranks a recorded entry — the cover
                # is the actual, and it is read-only here like a teaching period.
                cover += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="cover",
                    class_label=covering[0], subject_name=covering[1]))
            elif entry:
                work += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="work",
                    work_type=entry.work_type,
                    work_label=label_for(entry.work_type, org),
                    note=entry.note))
            else:
                free += 1
                suggested = usual.get((on.weekday(), p.period_no))
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="free",
                    suggested_work_type=suggested,
                    suggested_work_label=label_for(suggested, org) if suggested else None))
        return TimesheetDay(
            date=on, weekday=on.weekday(), is_working_day=on.weekday() in working,
            slots=slots, teaching_count=teach, work_count=work, free_count=free,
            cover_count=cover, breaks=breaks or [], evening_labels=evening_labels)

    def day(self, m: CurrentMember, member_id: uuid.UUID | None = None,
            on: date | None = None) -> TimesheetDay:
        """The day view (D-18): the same cells the week has, plus the breaks, so
        the teacher reads her day as the vertical timeline she actually lives."""
        mid = self._resolve_member(m, member_id)
        on = on or self._today(m)
        year = self._year(m.org_id)
        period_times = year.period_times if year else []
        periods = day_periods(period_times, year.periods_per_day if year else 8)
        working = set(year.working_weekdays) if year else {0, 1, 2, 3, 4, 5}
        return self._build_day(
            on, periods, working,
            self._teaching(m.org_id, mid, on, on),
            self._entries(m.org_id, mid, on, on),
            covers=covers_between(self.db, m.org_id, on, on, mid).get(mid, {}),
            org=m.org, usual=self._usual(m.org_id, mid, on),
            breaks=[TimesheetBreak(**b.model_dump()) for b in breaks_of(period_times)],
            evenings=self._evenings(m.org_id, mid))

    def week(self, m: CurrentMember, member_id: uuid.UUID | None = None,
             week_start: date | None = None) -> TimesheetWeek:
        mid = self._resolve_member(m, member_id)
        anchor = week_start or self._today(m)
        monday = anchor - timedelta(days=anchor.weekday())
        year = self._year(m.org_id)
        periods = day_periods(year.period_times if year else [],
                              year.periods_per_day if year else 8)
        working = set(year.working_weekdays) if year else {0, 1, 2, 3, 4, 5}
        sunday = monday + timedelta(days=6)

        teaching = self._teaching(m.org_id, mid, monday, sunday)
        entries = self._entries(m.org_id, mid, monday, sunday)
        covers = covers_between(self.db, m.org_id, monday, sunday, mid).get(mid, {})
        usual = self._usual(m.org_id, mid, monday)
        evenings = self._evenings(m.org_id, mid)
        # A non-working weekday still appears if something actually happened on
        # it — a sports Sunday, an exam Saturday, a cover assigned out of hours.
        # `week` used to drop them outright, so a period the teacher genuinely
        # worked could not be seen OR recorded (module §4.7). An empty Sunday is
        # still dropped: the grid stays six columns on a normal week.
        def occupied(on: date) -> bool:
            return (any((on.weekday(), p.period_no) in teaching for p in periods)
                    or any(d == on for d, _p in entries)
                    or any(d == on for d, _p in covers))

        days = [
            self._build_day(d, periods, working, teaching, entries,
                            covers=covers, org=m.org, usual=usual, evenings=evenings)
            for d in (monday + timedelta(days=i) for i in range(7))
            if d.weekday() in working or occupied(d)
        ]
        return TimesheetWeek(
            member_id=mid, member_name=self._member_name(mid), week_start=monday, days=days,
            teaching_periods=sum(d.teaching_count for d in days),
            work_periods=sum(d.work_count for d in days),
            free_periods=sum(d.free_count for d in days),
            covered_periods=sum(d.cover_count for d in days),
            evening_sessions=sum(len(d.evening_labels) for d in days))

    # ── the month: shape, not detail (D-18 / S-64) ───────────────────────────
    def month(self, m: CurrentMember, member_id: uuid.UUID | None = None,
              month: str | None = None) -> TimesheetMonth:
        """One cell per DAY, carrying the day's state.

        A month of 8 periods × 25 days is 200 cells and is unfillable on a phone.
        `S-64`'s answer: month = shape, week = edit, day = do. So this is a
        navigator — the counts draw the bar, and holidays, leave and non-working
        days come from the calendar and the leave table rather than being
        inferred from "no entries", which is what would otherwise show gaps on
        Diwali.
        """
        mid = self._resolve_member(m, member_id)
        today = self._today(m)
        month = month or f"{today:%Y-%m}"
        start, end = parse_month(month)
        year = self._year(m.org_id)
        periods = day_periods(year.period_times if year else [],
                              year.periods_per_day if year else 8)
        working = set(year.working_weekdays) if year else {0, 1, 2, 3, 4, 5}

        teaching = self._teaching(m.org_id, mid, start, end)
        entries = self._entries(m.org_id, mid, start, end)
        covers = covers_between(self.db, m.org_id, start, end, mid).get(mid, {})
        evenings = self._evenings(m.org_id, mid)

        # Holidays and leave, so the grid never reads a closed school as a hole.
        holidays: dict[date, str] = {}
        if year is not None:
            for ev in self.db.scalars(
                select(CalendarEvent).where(
                    CalendarEvent.org_id == m.org_id,
                    CalendarEvent.academic_year_id == year.id,
                    CalendarEvent.start_date <= end, CalendarEvent.end_date >= start)):
                if not ev.affects_teaching or ev.blocks_periods:
                    continue
                for d in expand_blocked_dates([(ev.start_date, ev.end_date, True, None)]):
                    if start <= d <= end:
                        holidays[d] = ev.title
        leave: dict[date, str] = {}
        for l_start, l_end, reason, is_half in self.db.execute(
            select(LeaveRequest.start_date, LeaveRequest.end_date, LeaveRequest.reason,
                   LeaveRequest.is_half_day)
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.member_id == mid,
                   LeaveRequest.status == "approved",
                   LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)).all():
            d = max(l_start, start)
            while d <= min(l_end, end):
                leave[d] = f"{'Half-day' if is_half else 'Leave'} — {reason}"
                d += timedelta(days=1)

        days: list[TimesheetMonthDay] = []
        d = start
        while d <= end:
            built = self._build_day(d, periods, working, teaching, entries,
                                    covers=covers, org=m.org, evenings=evenings)
            if d.weekday() not in working:
                state, label = "off", None
            elif d in holidays:
                state, label = "holiday", holidays[d]
            elif d in leave:
                state, label = "leave", leave[d]
            elif d > today:
                state, label = "future", None
            else:
                state, label = "working", None
            # V1-16: a non-working day that was ACTUALLY worked keeps its counts.
            #
            # V1-4 fixed exactly this in `week` — a period genuinely worked on a
            # sports Sunday or an exam Saturday could not be seen OR recorded —
            # and never carried the fix here. So a warden's Sunday evening prep
            # and a Saturday exam duty were both zeroed, and the month's totals
            # disagreed with the entries that were plainly in the table. The
            # STATE is unchanged, so the grid still draws the holiday; only the
            # counts stop lying about it.
            worked = built.teaching_count + built.work_count + built.cover_count
            counts = state in ("working", "future") or worked > 0
            days.append(TimesheetMonthDay(
                date=d, weekday=d.weekday(), state=state, label=label,
                teaching=built.teaching_count if counts else 0,
                work=built.work_count if counts else 0,
                cover=built.cover_count if counts else 0,
                free=built.free_count if state == "working" else 0))
            d += timedelta(days=1)

        return TimesheetMonth(
            member_id=mid, member_name=self._member_name(mid), month=month,
            start_date=start, end_date=end, days=days,
            teaching_periods=sum(x.teaching for x in days),
            work_periods=sum(x.work for x in days),
            covered_periods=sum(x.cover for x in days),
            evening_sessions=sum(
                len(evenings.get(x.weekday, [])) for x in days
                if x.state in ("working", "future")))

    # ── writes ───────────────────────────────────────────────────────────────
    def set_entry(self, m: CurrentMember, body: TimesheetEntryIn) -> TimesheetDay:
        mid = self._resolve_member(m, body.member_id)
        teaching = self._teaching(m.org_id, mid, body.date, body.date)
        if (body.date.weekday(), body.period_no) in teaching:
            klass, subject = teaching[(body.date.weekday(), body.period_no)]
            raise ConflictError(
                f"Period {body.period_no} is already {klass} {subject} on the timetable")

        existing = self.db.scalar(
            select(TimesheetEntry).where(
                TimesheetEntry.org_id == m.org_id, TimesheetEntry.member_id == mid,
                TimesheetEntry.date == body.date, TimesheetEntry.period_no == body.period_no))
        work_type = normalize(body.work_type)
        note = (body.note or "").strip() or None
        if existing:
            existing.work_type = work_type
            existing.note = note
        else:
            self.db.add(TimesheetEntry(
                org_id=m.org_id, member_id=mid, date=body.date, period_no=body.period_no,
                work_type=work_type, note=note))
        self.db.flush()
        return self.day(m, mid, body.date)

    def clear_entry(self, m: CurrentMember, on: date, period_no: int,
                    member_id: uuid.UUID | None = None) -> TimesheetDay:
        mid = self._resolve_member(m, member_id)
        entry = self.db.scalar(
            select(TimesheetEntry).where(
                TimesheetEntry.org_id == m.org_id, TimesheetEntry.member_id == mid,
                TimesheetEntry.date == on, TimesheetEntry.period_no == period_no))
        if entry is not None:
            self.db.delete(entry)
            self.db.flush()
        return self.day(m, mid, on)

    # ── org-wide read (admin) ────────────────────────────────────────────────
    def org_day(self, m: CurrentMember, on: date | None = None) -> list[TimesheetWeek]:
        """Every teacher's day, one row each — the admin's workload view.

        Three queries total regardless of headcount: the grid, the entries and
        the roster are each fetched once and joined in memory. Looping
        `self.day()` per teacher would be one round-trip per person against a
        remote database.
        """
        on = on or self._today(m)
        year = self._year(m.org_id)
        periods = day_periods(year.period_times if year else [],
                              year.periods_per_day if year else 8)
        working = set(year.working_weekdays) if year else {0, 1, 2, 3, 4, 5}

        staff = list(self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == m.org_id, Membership.status == "active",
                   not_operator())
            .order_by(User.name)).all())

        grid = self.db.execute(
            select(ClassSubject.teacher_member_id, TimetableSlot.weekday,
                   TimetableSlot.period_no, SchoolClass.name, SchoolClass.section, Subject.name)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .join(SchoolClass, SchoolClass.id == TimetableSlot.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   TimetableSlot.weekday == on.weekday(),
                   and_(TimetableSlot.effective_from <= on,
                        or_(TimetableSlot.effective_to.is_(None),
                            TimetableSlot.effective_to > on)))
        ).all()
        by_teacher: dict[uuid.UUID, dict] = {}
        for tid, wd, pn, cname, section, sname in grid:
            if tid is None:
                continue
            by_teacher.setdefault(tid, {})[(int(wd), int(pn))] = (_label(cname, section), sname)

        entry_rows = self.db.scalars(
            select(TimesheetEntry).where(TimesheetEntry.org_id == m.org_id,
                                         TimesheetEntry.date == on))
        entries_by: dict[uuid.UUID, dict] = {}
        for e in entry_rows:
            entries_by.setdefault(e.member_id, {})[(e.date, e.period_no)] = e

        # S-72: this grid used to read the timetable and the timesheet and
        # NOTHING else, so an absent teacher showed eight free periods and a
        # teacher covering three showed free in all three — on the screen the
        # admin opens to find cover. Absence/leave come from the same roster the
        # live board reads, covers from the same read My Day unions in (ux §9).
        from app.services.staff_attendance import StaffAttendanceService  # noqa: PLC0415
        presence = StaffAttendanceService(self.db).roster(m, on)
        subs = SubstitutionService(self.db)
        away: dict[uuid.UUID, str] = {}
        # V1-4: a half-day is away for HALF the cells. Blanking the whole row
        # would erase the classes she actually took that morning, and would tell
        # the admin nobody is free in periods she is in fact taking.
        away_halves: dict[uuid.UUID, set[int]] = {}
        for r in presence.roster:
            if r.present:
                continue
            reason = (r.leave_reason or r.note
                      or ("on leave" if r.on_leave else "marked away"))
            away[r.member_id] = reason
            if r.status == "half_day":
                away_halves[r.member_id] = subs.half_periods(m.org_id, on, r.portion)
        covers_all = covers_between(self.db, m.org_id, on, on)

        out: list[TimesheetWeek] = []
        for mid, name in staff:
            day = self._build_day(on, periods, working,
                                  by_teacher.get(mid, {}), entries_by.get(mid, {}),
                                  covers=covers_all.get(mid, {}),
                                  away_reason=away.get(mid),
                                  away_periods=away_halves.get(mid), org=m.org)
            out.append(TimesheetWeek(
                member_id=mid, member_name=name, week_start=on, days=[day],
                teaching_periods=day.teaching_count, work_periods=day.work_count,
                free_periods=day.free_count, covered_periods=day.cover_count,
                away_reason=away.get(mid)))
        return out
