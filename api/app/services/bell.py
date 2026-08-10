"""Which shape the school day had on a given date (TT-2, `D-115`).

`school_clock` is pure: hand it a list of entries and it tells you the periods,
the breaks, where lunch falls and which period is running now. It cannot know
*which* list applies to a date, because that is a database question. This module
is the answer, and it is the only place that loads a `BellSchedule`.

Why a date at all: a school may restructure its day mid-year — the founder's
case is "after the Term 1 exams, introduce new classes and change the timetable
structure". If the timings were a single value, September's timesheet, day-book
and daily report would all silently re-render with October's clock, and nobody
would notice because every number would still look plausible. So schedules are
effective-dated `[effective_from, effective_to)` like `timetable_slots`, and
every read is *as of a date*.

Editing is append-only (Law 3): `set_schedule` closes the current row and opens
a new one. The old shape stays readable forever, which is the entire point.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import NamedTuple

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.day_shape import PERIOD_KIND
from app.core.exceptions import ValidationError
from app.models import AcademicYear, BellSchedule
from app.services import school_clock


class DayShape(NamedTuple):
    """The school day as it stood on one date."""

    entries: list[dict]
    periods_per_day: int
    #: None for the legacy fallback (a year with no bell_schedules row).
    schedule_id: uuid.UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    note: str | None = None

    @property
    def periods(self) -> list[school_clock.DayPeriod]:
        return school_clock.day_periods(self.entries, self.periods_per_day)

    @property
    def breaks(self) -> list[school_clock.DayBreak]:
        return school_clock.breaks_of(self.entries)

    @property
    def has_timings(self) -> bool:
        """True when the school actually set clock times.

        A school that never did still gets numbered periods from
        `fallback_periods`, so "there are 8 periods" and "we know when they run"
        are different questions and callers that render a clock must ask this one.
        """
        return any(e.get("start") for e in self.entries)


def count_periods(entries: list[dict] | None) -> int:
    """How many teachable periods a set of entries describes."""
    return sum(1 for e in (entries or []) if (e.get("kind") or PERIOD_KIND) == PERIOD_KIND)


def _current_at(on_date: date):
    return and_(
        BellSchedule.effective_from <= on_date,
        or_(BellSchedule.effective_to.is_(None), BellSchedule.effective_to > on_date),
    )


def resolve(db: Session, year: AcademicYear | None, on_date: date) -> DayShape:
    """The shape of the day for `year` on `on_date`.

    Falls back to the year's own legacy `period_times` / `periods_per_day` when
    no schedule row exists. That is the bridge for a year created before TT-2 and
    not yet backfilled, and for one created by a code path that has not learned
    to open a schedule — a school seeing its real timings beats a school seeing
    an empty day. It is a read-side floor only; nothing writes those columns.
    """
    if year is None:
        return DayShape(entries=[], periods_per_day=0)
    row = db.scalar(
        select(BellSchedule)
        .where(BellSchedule.academic_year_id == year.id, _current_at(on_date))
        .order_by(BellSchedule.effective_from.desc())
    )
    if row is None:
        return DayShape(
            entries=list(year.period_times or []),
            periods_per_day=year.periods_per_day or 0,
        )
    return DayShape(
        entries=list(row.entries or []), periods_per_day=row.periods_per_day,
        schedule_id=row.id, effective_from=row.effective_from,
        effective_to=row.effective_to, note=row.note,
    )


def resolve_for_org(db: Session, org_id: uuid.UUID, on_date: date) -> DayShape:
    """The active year's shape — for callers that have an org but no year."""
    year = db.scalar(select(AcademicYear).where(
        AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))
    return resolve(db, year, on_date)


def history(db: Session, academic_year_id: uuid.UUID) -> list[BellSchedule]:
    """Every shape this year has had, newest first."""
    return list(db.scalars(
        select(BellSchedule)
        .where(BellSchedule.academic_year_id == academic_year_id)
        .order_by(BellSchedule.effective_from.desc(), BellSchedule.created_at.desc())))


def _minutes(hhmm: str) -> int | None:
    try:
        h, m = hhmm.strip().split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def validate_entries(entries: list[dict]) -> None:
    """Reject a day that cannot happen.

    Deliberately strict about order and overlap and deliberately silent about
    everything else: a school may run a 25-minute period, start at 06:00, or put
    three breaks in a row, and none of those is our business. What we refuse is a
    day whose entries contradict each other, because `current_period_no` walks
    them in order and would answer wrongly rather than fail.
    """
    last_end: int | None = None
    for i, e in enumerate(entries, start=1):
        start = _minutes(str(e.get("start") or ""))
        end = _minutes(str(e.get("end") or ""))
        if start is None or end is None:
            raise ValidationError(f"Row {i}: give both a start and an end time.")
        if end <= start:
            raise ValidationError(f"Row {i} ends at or before it starts.")
        if last_end is not None and start < last_end:
            raise ValidationError(
                f"Row {i} starts before the row above it ends — put the day in order.")
        last_end = end


def set_schedule(
    db: Session, org_id: uuid.UUID, year: AcademicYear, entries: list[dict],
    effective_from: date, note: str | None = None,
    periods_per_day: int | None = None, today: date | None = None,
) -> BellSchedule:
    """Open a new shape from `effective_from`, closing whatever was current.

    Append-only. Editing a schedule that has not started yet replaces it in place
    (it never applied to a real day, so there is no history to keep) — the same
    rule `clear_slot` uses, and for the same reason.

    `periods_per_day` exists for the legacy `/timetable/period-config` contract,
    where a school could declare eight periods while listing the times of only
    two — or none at all. The timings editor passes None and the count is derived
    from the entries, which is what makes "add a row" mean "add a period".
    """
    validate_entries(entries)
    ppd = count_periods(entries) if periods_per_day is None else periods_per_day
    if ppd < 1:
        raise ValidationError("A school day needs at least one period.")

    current = db.scalar(
        select(BellSchedule).where(
            BellSchedule.academic_year_id == year.id,
            BellSchedule.effective_to.is_(None))
        .order_by(BellSchedule.effective_from.desc()))
    if current is not None:
        if current.effective_from >= effective_from:
            current.entries = entries
            current.periods_per_day = ppd
            current.effective_from = effective_from
            current.note = note
            db.flush()
            sync_year_cache(db, year, today or effective_from)
            return current
        current.effective_to = effective_from

    row = BellSchedule(
        org_id=org_id, academic_year_id=year.id, periods_per_day=ppd,
        entries=entries, note=note, effective_from=effective_from, effective_to=None)
    db.add(row)
    db.flush()
    sync_year_cache(db, year, today or effective_from)
    return row


def sync_year_cache(db: Session, year: AcademicYear, today: date) -> None:
    """Mirror **today's** shape onto `academic_years.period_times`/`periods_per_day`.

    Those two columns were the whole story before TT-2, and about twenty-five
    call sites still read them — the timesheet, the now-board, the day's marking
    periods, the workload grid. Nearly all of them render *today*, for which the
    current shape is exactly the right answer.

    So the columns stay, as a materialized view of the current row, and this is
    the only function that writes them. That is not two sources of truth: the
    table is the truth, this is a cache of one row of it, maintained in one
    place. The rule for anyone reading:

        **`bell.resolve(db, year, on_date)` is the only correct read for a
        date.** The year columns answer "now" and nothing else — a screen that
        renders a past month must use the resolver or it will draw September
        with October's clock, which is the bug this packet exists to fix.

    A schedule that starts in the future does not touch the cache, because it is
    not the shape of today.
    """
    shape = resolve(db, year, today)
    year.periods_per_day = shape.periods_per_day
    year.period_times = list(shape.entries)
    db.flush()


def ensure(db: Session, org_id: uuid.UUID, year: AcademicYear,
           entries: list[dict], effective_from: date) -> BellSchedule | None:
    """Open the year's first schedule if it has none. Used by setup commit.

    Idempotent: a year that already has any schedule row is left exactly alone,
    so re-running an import cannot quietly rewrite a day the school has since
    edited.
    """
    existing = db.scalar(select(BellSchedule.id).where(
        BellSchedule.academic_year_id == year.id))
    if existing is not None:
        return None
    ppd = count_periods(entries)
    row = BellSchedule(
        org_id=org_id, academic_year_id=year.id, periods_per_day=ppd or 0,
        entries=entries, note="Set during school setup",
        effective_from=effective_from, effective_to=None)
    db.add(row)
    db.flush()
    sync_year_cache(db, year, effective_from)
    return row
