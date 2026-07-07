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
from app.core.exceptions import NotFoundError
from app.models import AcademicYear, CalendarEvent
from app.schemas.calendar import CalendarEventCreate, CalendarEventOut, CalendarSummary

# Default Indian-school working week: Mon–Sat (Python weekday ints, Mon=0).
DEFAULT_WORKING_WEEKDAYS = [0, 1, 2, 3, 4, 5]


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def expand_blocked_dates(events) -> set[date]:
    """Flatten (start_date, end_date, affects_teaching) rows into a set of blocked
    dates. Only events that affect teaching remove days."""
    blocked: set[date] = set()
    for start, end, affects in events:
        if not affects:
            continue
        blocked.update(_daterange(start, end))
    return blocked


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
) -> float:
    """Periods a class-subject can actually teach in the week beginning
    ``week_start`` — periods_per_week scaled by (unblocked working days / working
    days that week within the year). 0 for a fully-blocked (e.g. exam) week."""
    ww = set(working_weekdays)
    week_end = week_start + timedelta(days=6)
    nominal = 0
    available = 0
    for d in _daterange(week_start, week_end):
        if d < year_start or d > year_end or d.weekday() not in ww:
            continue
        nominal += 1
        if d not in blocked:
            available += 1
    if nominal == 0:
        return 0.0
    return round(periods_per_week * available / nominal, 2)


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
            affects_teaching=body.affects_teaching, notes=body.notes,
        )
        self.db.add(event)
        self.db.flush()
        return CalendarEventOut.model_validate(event)

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
        blocked = expand_blocked_dates(
            [(e.start_date, e.end_date, e.affects_teaching) for e in events]
        )
        days = teaching_days(year.start_date, year.end_date, year.working_weekdays, blocked)
        return CalendarSummary(
            academic_year_id=year.id, start_date=year.start_date, end_date=year.end_date,
            working_weekdays=year.working_weekdays, teaching_days=days,
            events=[CalendarEventOut.model_validate(e) for e in events],
        )

