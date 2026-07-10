"""Effective-teaching-days engine (M1, SPRD §5.1).

The baseline for the whole planner: how many teaching days/periods actually
remain once weekends, holidays, exam blocks, and events are removed. Pure
functions (no session) so they're unit-testable; the service loads the org's
working weekdays + affects_teaching events and feeds them in.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import AcademicYear, CalendarEvent, ClassSubject, ExamPortion, SyllabusTopic
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventOut,
    CalendarSummary,
    ExamPortionIn,
    ExamPortionOut,
)

# Default Indian-school working week: Mon–Sat (Python weekday ints, Mon=0).
DEFAULT_WORKING_WEEKDAYS = [0, 1, 2, 3, 4, 5]


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def expand_blocked_dates(events) -> set[date]:
    """Flatten (start_date, end_date, affects_teaching[, blocks_periods]) rows into
    a set of FULLY blocked dates. Only events that affect teaching remove days, and
    an event that names specific periods is a partial day, not a blocked one — see
    `expand_partial_blocks` (V2-P7)."""
    blocked: set[date] = set()
    for row in events:
        start, end, affects = row[0], row[1], row[2]
        blocks_periods = row[3] if len(row) > 3 else None
        if not affects or blocks_periods:
            continue
        blocked.update(_daterange(start, end))
    return blocked


def expand_partial_blocks(events) -> dict[date, set[int]]:
    """date → the set of period numbers lost to partial-day events (V2-P7).

    A morning exam over periods 1-3 costs three periods, not the whole day. Rows
    are (start, end, affects_teaching, blocks_periods); only rows naming periods
    contribute. Overlapping events union their periods, so a date can't lose the
    same period twice."""
    partial: dict[date, set[int]] = {}
    for row in events:
        start, end, affects = row[0], row[1], row[2]
        blocks_periods = row[3] if len(row) > 3 else None
        if not affects or not blocks_periods:
            continue
        for d in _daterange(start, end):
            partial.setdefault(d, set()).update(int(p) for p in blocks_periods)
    return partial


def event_rows(events) -> list[tuple]:
    """CalendarEvent ORM rows → the tuples the pure engine above consumes."""
    return [(e.start_date, e.end_date, e.affects_teaching, e.blocks_periods) for e in events]


def is_teaching_day(d: date, working_weekdays: set[int], blocked: set[date]) -> bool:
    return d.weekday() in working_weekdays and d not in blocked


def teaching_days(start: date, end: date, working_weekdays, blocked: set[date]) -> int:
    ww = set(working_weekdays)
    return sum(1 for d in _daterange(start, end) if is_teaching_day(d, ww, blocked))


def effective_periods(
    periods_per_week: int,
    week_start: date,
    *,
    working_weekdays,
    blocked: set[date],
    year_start: date,
    year_end: date,
    partial: dict[date, set[int]] | None = None,
    periods_per_day: int = 8,
) -> float:
    """Periods a class-subject can actually teach in the week beginning
    ``week_start`` — periods_per_week scaled by (available working days / working
    days in the week). 0 for a fully-blocked (e.g. exam) week.

    A partial day contributes a fraction: an event eating 3 of 8 periods leaves
    5/8 of that day (V2-P7). A partial block that somehow names every period is
    clamped to 0, never negative.

    The denominator is the week's working days, NOT just the ones inside
    [year_start, year_end]. Those differ only for a week straddling a window edge,
    and there the distinction decides the answer: the week Term 2 opens on a
    Thursday has 3 teaching days, not 6, so it must yield half a week's periods.
    Normalising by the in-window days instead returns a full week and lets the
    planner cram six periods of topics into three days. For every week that lies
    wholly inside the window — which is every week the whole-year planner sees
    except the year's first and last — the two denominators are equal."""
    ww = set(working_weekdays)
    week_end = week_start + timedelta(days=6)
    partial = partial or {}
    week_working = 0
    in_window = 0
    available = 0.0
    for d in _daterange(week_start, week_end):
        if d.weekday() not in ww:
            continue
        week_working += 1
        if d < year_start or d > year_end:
            continue
        in_window += 1
        if d in blocked:
            continue
        lost = len(partial.get(d, ()))
        available += max(0.0, 1.0 - lost / max(periods_per_day, 1))
    if in_window == 0 or week_working == 0:
        return 0.0
    return round(periods_per_week * available / week_working, 2)


class CalendarService:
    """DB-facing wrapper around the pure engine above (M1)."""

    def __init__(self, db: Session):
        self.db = db

    def _year(self, org_id: uuid.UUID, year_id: uuid.UUID) -> AcademicYear:
        y = self.db.scalar(
            select(AcademicYear).where(AcademicYear.id == year_id, AcademicYear.org_id == org_id)
        )
        if y is None:
            raise NotFoundError("Academic year")
        return y

    def _events(self, org_id: uuid.UUID, year_id: uuid.UUID) -> list[CalendarEvent]:
        return list(self.db.scalars(
            select(CalendarEvent)
            .where(CalendarEvent.org_id == org_id, CalendarEvent.academic_year_id == year_id)
            .order_by(CalendarEvent.start_date)
        ))

    def list_events(self, m: CurrentMember, year_id: uuid.UUID) -> list[CalendarEventOut]:
        return [CalendarEventOut.model_validate(e) for e in self._events(m.org_id, year_id)]

    def create_event(self, m: CurrentMember, body: CalendarEventCreate) -> CalendarEventOut:
        self._year(m.org_id, body.academic_year_id)  # same-org guard
        event = CalendarEvent(
            org_id=m.org_id, academic_year_id=body.academic_year_id, type=body.type,
            title=body.title, start_date=body.start_date, end_date=body.end_date,
            affects_teaching=body.affects_teaching, blocks_periods=body.blocks_periods,
            notes=body.notes,
        )
        self.db.add(event)
        self.db.flush()
        return CalendarEventOut.model_validate(event)

    def create_events(self, m: CurrentMember, bodies: list[CalendarEventCreate],
                      ) -> list[CalendarEventOut]:
        """Bulk create in one transaction — the drag-select grid's commit."""
        return [self.create_event(m, b) for b in bodies]

    def delete_event(self, m: CurrentMember, event_id: uuid.UUID) -> None:
        event = self.db.scalar(
            select(CalendarEvent).where(
                CalendarEvent.id == event_id, CalendarEvent.org_id == m.org_id
            )
        )
        if event is None:
            raise NotFoundError("Event")
        self.db.delete(event)

    def summary(self, m: CurrentMember, year_id: uuid.UUID) -> CalendarSummary:
        year = self._year(m.org_id, year_id)
        events = self._events(m.org_id, year_id)
        blocked = expand_blocked_dates(event_rows(events))
        days = teaching_days(year.start_date, year.end_date, year.working_weekdays, blocked)
        return CalendarSummary(
            academic_year_id=year.id, start_date=year.start_date, end_date=year.end_date,
            working_weekdays=year.working_weekdays, teaching_days=days,
            events=[CalendarEventOut.model_validate(e) for e in events],
        )



class ExamPortionService:
    """Which syllabus each exam examines (V2-P7). Feeds the planner's V5 validator."""

    def __init__(self, db: Session):
        self.db = db

    def list(self, m: CurrentMember, class_subject_id: uuid.UUID | None = None,
             ) -> list[ExamPortionOut]:
        q = select(ExamPortion).where(ExamPortion.org_id == m.org_id)
        if class_subject_id is not None:
            q = q.where(ExamPortion.class_subject_id == class_subject_id)
        return [ExamPortionOut.model_validate(p) for p in self.db.scalars(q)]

    def set(self, m: CurrentMember, body: ExamPortionIn) -> ExamPortionOut:
        """Idempotent per (exam, class-subject) — re-setting moves the cut point."""
        event = self.db.scalar(select(CalendarEvent).where(
            CalendarEvent.id == body.exam_event_id, CalendarEvent.org_id == m.org_id))
        if event is None:
            raise NotFoundError("Exam")
        if event.type != "exam_block":
            raise ValidationError("Only an exam block can have a portion.")
        if not self.db.scalar(select(ClassSubject.id).where(
                ClassSubject.id == body.class_subject_id, ClassSubject.org_id == m.org_id)):
            raise NotFoundError("Class-subject")
        if not self.db.scalar(select(SyllabusTopic.id).where(
                SyllabusTopic.id == body.upto_topic_id, SyllabusTopic.org_id == m.org_id)):
            raise NotFoundError("Topic")

        existing = self.db.scalar(select(ExamPortion).where(
            ExamPortion.org_id == m.org_id, ExamPortion.exam_event_id == body.exam_event_id,
            ExamPortion.class_subject_id == body.class_subject_id))
        if existing is None:
            existing = ExamPortion(
                org_id=m.org_id, exam_event_id=body.exam_event_id,
                class_subject_id=body.class_subject_id, upto_topic_id=body.upto_topic_id)
            self.db.add(existing)
        else:
            existing.upto_topic_id = body.upto_topic_id
        self.db.flush()
        return ExamPortionOut.model_validate(existing)

    def delete(self, m: CurrentMember, portion_id: uuid.UUID) -> None:
        p = self.db.scalar(select(ExamPortion).where(
            ExamPortion.id == portion_id, ExamPortion.org_id == m.org_id))
        if p is None:
            raise NotFoundError("Exam portion")
        self.db.delete(p)
