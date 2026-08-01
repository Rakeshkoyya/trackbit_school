"""The school day as a list of periods, and where "now" falls in it (SF-1).

`academic_years.period_times` is a JSON list of `{start, end, kind}` that INCLUDES
breaks, in wall-clock order. Everything else in the app addresses a period by its
1-based `period_no` — the timetable grid, `class_periods`, the period card. The
mapping between the two lives here and nowhere else:

    period_no = the 1-based index among entries whose kind == 'period'

so a lunch break between periods 4 and 5 shifts no period number. Getting this
wrong would silently misalign a teacher's timesheet with their timetable, which
is why it is one pure function with tests rather than an inline enumerate() in
three services.

Pure and I/O-free — it takes the JSON it is given. The caller loads the year.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel

PERIOD_KIND = "period"


class DayPeriod(BaseModel):
    """One teachable slot in the school day."""
    period_no: int
    start: str  # "09:00"
    end: str    # "09:40"


class DayBreak(BaseModel):
    """A non-teaching interval — rendered on the timesheet, never markable."""
    after_period_no: int  # 0 = before the first period
    label: str
    start: str
    end: str


def _parse(hhmm: str) -> time | None:
    try:
        h, m = hhmm.strip().split(":")[:2]
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def periods_of(period_times: list[dict] | None) -> list[DayPeriod]:
    """The teachable periods, numbered the way the rest of the app numbers them."""
    out: list[DayPeriod] = []
    for entry in period_times or []:
        if (entry.get("kind") or PERIOD_KIND) != PERIOD_KIND:
            continue
        out.append(DayPeriod(
            period_no=len(out) + 1,
            start=str(entry.get("start") or ""),
            end=str(entry.get("end") or ""),
        ))
    return out


def breaks_of(period_times: list[dict] | None) -> list[DayBreak]:
    """Non-teaching intervals, tagged with the period they follow."""
    out: list[DayBreak] = []
    seen = 0
    for entry in period_times or []:
        kind = entry.get("kind") or PERIOD_KIND
        if kind == PERIOD_KIND:
            seen += 1
            continue
        out.append(DayBreak(
            after_period_no=seen,
            label=str(kind).replace("_", " ").capitalize(),
            start=str(entry.get("start") or ""),
            end=str(entry.get("end") or ""),
        ))
    return out


def fallback_periods(periods_per_day: int) -> list[DayPeriod]:
    """Numbered periods with no clock, for a school that never set its timings.

    The timesheet still has to render — a teacher whose admin skipped the timings
    step should see eight rows they can fill, not an empty screen.
    """
    return [DayPeriod(period_no=n, start="", end="") for n in range(1, max(0, periods_per_day) + 1)]


def day_periods(period_times: list[dict] | None, periods_per_day: int) -> list[DayPeriod]:
    return periods_of(period_times) or fallback_periods(periods_per_day)


def current_period_no(
    period_times: list[dict] | None, now: datetime | None = None, tz: str = "Asia/Kolkata",
) -> int | None:
    """Which period is running at `now`, or None outside teaching time.

    A break returns None: nobody is teaching during lunch, and reporting the
    period on either side of it would put teachers in classrooms they are not in.
    """
    moment = (now or datetime.now(ZoneInfo(tz))).timetz()
    for p in periods_of(period_times):
        start, end = _parse(p.start), _parse(p.end)
        if start is None or end is None:
            continue
        if start <= moment.replace(tzinfo=None) < end:
            return p.period_no
    return None


def phase(
    period_times: list[dict] | None, now: datetime | None = None, tz: str = "Asia/Kolkata",
) -> tuple[str, int | None]:
    """(phase, period_no) — 'before' | 'period' | 'break' | 'after' | 'unset'."""
    periods = periods_of(period_times)
    if not periods:
        return ("unset", None)
    moment = (now or datetime.now(ZoneInfo(tz))).replace(tzinfo=None).time()
    first, last = _parse(periods[0].start), _parse(periods[-1].end)
    if first is None or last is None:
        return ("unset", None)
    if moment < first:
        return ("before", None)
    if moment >= last:
        return ("after", None)
    running = current_period_no(period_times, now, tz)
    return ("period", running) if running else ("break", None)


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()
