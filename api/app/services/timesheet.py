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
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.work_types import label_for, normalize
from app.models import (
    AcademicYear,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    TimesheetEntry,
    TimetableSlot,
    User,
)
from app.schemas.staff import (
    TimesheetDay,
    TimesheetEntryIn,
    TimesheetSlot,
    TimesheetWeek,
)
from app.services.school_clock import day_periods, today_in


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
    def _build_day(self, on: date, periods, working: set[int], teaching, entries) -> TimesheetDay:
        slots: list[TimesheetSlot] = []
        teach = work = free = 0
        for p in periods:
            taught = teaching.get((on.weekday(), p.period_no))
            entry = entries.get((on, p.period_no))
            if taught:
                # The grid wins. An entry that somehow exists under a teaching
                # period is ignored rather than deleted — the grid may move back.
                teach += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="class",
                    class_label=taught[0], subject_name=taught[1]))
            elif entry:
                work += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="work",
                    work_type=entry.work_type, work_label=label_for(entry.work_type),
                    note=entry.note))
            else:
                free += 1
                slots.append(TimesheetSlot(
                    period_no=p.period_no, start=p.start, end=p.end, kind="free"))
        return TimesheetDay(
            date=on, weekday=on.weekday(), is_working_day=on.weekday() in working,
            slots=slots, teaching_count=teach, work_count=work, free_count=free)

    def day(self, m: CurrentMember, member_id: uuid.UUID | None = None,
            on: date | None = None) -> TimesheetDay:
        mid = self._resolve_member(m, member_id)
        on = on or self._today(m)
        year = self._year(m.org_id)
        periods = day_periods(year.period_times if year else [],
                              year.periods_per_day if year else 8)
        working = set(year.working_weekdays) if year else {0, 1, 2, 3, 4, 5}
        return self._build_day(
            on, periods, working,
            self._teaching(m.org_id, mid, on, on),
            self._entries(m.org_id, mid, on, on))

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
        days = [
            self._build_day(monday + timedelta(days=i), periods, working, teaching, entries)
            for i in range(7) if (monday + timedelta(days=i)).weekday() in working
        ]
        return TimesheetWeek(
            member_id=mid, member_name=self._member_name(mid), week_start=monday, days=days,
            teaching_periods=sum(d.teaching_count for d in days),
            work_periods=sum(d.work_count for d in days),
            free_periods=sum(d.free_count for d in days))

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
            .where(Membership.org_id == m.org_id, Membership.status == "active")
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

        out: list[TimesheetWeek] = []
        for mid, name in staff:
            day = self._build_day(on, periods, working,
                                  by_teacher.get(mid, {}), entries_by.get(mid, {}))
            out.append(TimesheetWeek(
                member_id=mid, member_name=name, week_start=on, days=[day],
                teaching_periods=day.teaching_count, work_periods=day.work_count,
                free_periods=day.free_count))
        return out
