"""Computed week/day schedule (V2-P12) — the flexible layer under the locked plan.

The term syllabus is the contract and `plan_entries` the approved weekly baseline
(P2). What actually happens day to day — a teacher absent on Tuesday, a chapter
running a period long — must never mutate either. So the day-level schedule is
COMPUTED on every read: each class-subject's *remaining* syllabus (actual lesson
logs subtracted) is laid onto the class's timetable slots from today forward.
Nothing is stored; falling behind simply shifts what tomorrow suggests, and the
forecast (not this view) is what says whether the drift threatens the exam.

Past periods show what was actually taught (the log), never a back-filled plan.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassPeriod,
    ClassSubject,
    LessonLog,
    Membership,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    TimetableSlot,
    User,
)
from app.schemas.planner import DayScheduleOut, DaySlotOut, WeekScheduleOut
from app.services.calendar import event_rows, expand_blocked_dates, expand_partial_blocks
from app.services.periods import today_for


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class _TopicQueue:
    """One class-subject's remaining syllabus, one period at a time.

    A topic with any full-coverage log is done. An in-progress topic keeps
    max(est − logged periods, 1) periods of life, so a chapter running long
    stays today's topic instead of silently disappearing."""

    def __init__(self, items: list[tuple[uuid.UUID, str, str, int]]):
        self._items = items  # (topic_id, title, unit_title, remaining)
        self._i = 0

    def take(self) -> tuple[uuid.UUID, str, str] | None:
        while self._i < len(self._items) and self._items[self._i][3] <= 0:
            self._i += 1
        if self._i >= len(self._items):
            return None
        tid, title, unit, rem = self._items[self._i]
        self._items[self._i] = (tid, title, unit, rem - 1)
        return tid, title, unit


class WeekScheduleService:
    def __init__(self, db: Session):
        self.db = db

    def _queues(self, org_id: uuid.UUID, cs_ids: list[uuid.UUID],
                ) -> dict[uuid.UUID, _TopicQueue]:
        units = self.db.scalars(
            select(SyllabusUnit)
            .where(SyllabusUnit.org_id == org_id, SyllabusUnit.class_subject_id.in_(cs_ids))
            .options(selectinload(SyllabusUnit.topics))
            .order_by(SyllabusUnit.position))
        by_cs: dict[uuid.UUID, list[tuple[SyllabusUnit, SyllabusTopic]]] = {}
        for u in units:
            for t in sorted(u.topics, key=lambda t: t.position):
                by_cs.setdefault(u.class_subject_id, []).append((u, t))

        log_counts: dict[uuid.UUID, int] = {}
        full: set[uuid.UUID] = set()
        for topic_id, coverage in self.db.execute(
            select(LessonLog.topic_id, LessonLog.coverage).where(
                LessonLog.org_id == org_id, LessonLog.class_subject_id.in_(cs_ids),
                LessonLog.topic_id.is_not(None))
        ).all():
            log_counts[topic_id] = log_counts.get(topic_id, 0) + 1
            if coverage == "full":
                full.add(topic_id)

        out: dict[uuid.UUID, _TopicQueue] = {}
        for cs_id, pairs in by_cs.items():
            items = []
            for u, t in pairs:
                if t.id in full:
                    continue
                # An unsized topic still deserves a day on the board once it is
                # reached — 1 period is the honest minimum, not a schedule.
                remaining = max((t.est_periods or 1) - log_counts.get(t.id, 0), 1)
                items.append((t.id, t.title, u.title, remaining))
            out[cs_id] = _TopicQueue(items)
        return out

    def week(self, m: CurrentMember, class_id: uuid.UUID,
             week_start: date | None = None) -> WeekScheduleOut:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        year = self.db.get(AcademicYear, klass.academic_year_id)
        if year is None:
            raise ValidationError("This class has no academic year.")
        today = today_for(m)
        monday = _monday(week_start or today)
        working = set(year.working_weekdays or [])
        days = [monday + timedelta(days=i) for i in range(7)
                if (monday + timedelta(days=i)).weekday() in working]

        events = list(self.db.scalars(select(CalendarEvent).where(
            CalendarEvent.org_id == m.org_id, CalendarEvent.academic_year_id == year.id)))
        blocked = expand_blocked_dates(event_rows(events))
        partial = expand_partial_blocks(event_rows(events))

        meta = {
            cs_id: (sname, tname) for cs_id, sname, tname in self.db.execute(
                select(ClassSubject.id, Subject.name, User.name)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            ).all()
        }
        queues = self._queues(m.org_id, list(meta.keys())) if meta else {}

        # What actually happened: (date, period_no) → the logged topic.
        actual: dict[tuple[date, int], tuple[uuid.UUID | None, str | None, str | None]] = {}
        if days:
            period_rows = {p.id: p for p in self.db.scalars(select(ClassPeriod).where(
                ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
                ClassPeriod.date.in_(days)))}
            if period_rows:
                for log, ttitle, utitle in self.db.execute(
                    select(LessonLog, SyllabusTopic.title, SyllabusUnit.title)
                    .outerjoin(SyllabusTopic, SyllabusTopic.id == LessonLog.topic_id)
                    .outerjoin(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
                    .where(LessonLog.org_id == m.org_id,
                           LessonLog.period_id.in_(list(period_rows)))
                ).all():
                    p = period_rows[log.period_id]
                    actual[(p.date, p.period_no)] = (log.topic_id, ttitle, utitle)

        out_days: list[DayScheduleOut] = []
        for d in days:
            day_blocked = d in blocked
            lost_periods = partial.get(d, set())
            slots = list(self.db.scalars(select(TimetableSlot).where(
                TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == class_id,
                TimetableSlot.weekday == d.weekday(),
                TimetableSlot.effective_from <= d,
                or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d),
            ).order_by(TimetableSlot.period_no)))

            out_slots: list[DaySlotOut] = []
            for s in slots:
                sname, tname = meta.get(s.class_subject_id, ("?", None))
                base = dict(period_no=s.period_no, class_subject_id=s.class_subject_id,
                            subject_name=sname, teacher_name=tname)
                got = actual.get((d, s.period_no))
                if got is not None:
                    tid, ttitle, utitle = got
                    out_slots.append(DaySlotOut(
                        **base, topic_id=tid, topic_title=ttitle, unit_title=utitle,
                        state="actual"))
                elif day_blocked or s.period_no in lost_periods:
                    out_slots.append(DaySlotOut(**base, state="blocked"))
                elif d < today:
                    out_slots.append(DaySlotOut(**base, state="past"))
                else:
                    nxt = queues.get(s.class_subject_id)
                    took = nxt.take() if nxt else None
                    if took is None:
                        out_slots.append(DaySlotOut(**base, state="planned"))
                    else:
                        tid, ttitle, utitle = took
                        out_slots.append(DaySlotOut(
                            **base, topic_id=tid, topic_title=ttitle, unit_title=utitle,
                            state="planned"))
            out_days.append(DayScheduleOut(
                date=d, weekday=d.weekday(), blocked=day_blocked, slots=out_slots))

        label = klass.name + (f"-{klass.section}" if klass.section else "")
        return WeekScheduleOut(
            class_id=class_id, class_label=label, week_start=monday,
            periods_per_day=year.periods_per_day, days=out_days)

