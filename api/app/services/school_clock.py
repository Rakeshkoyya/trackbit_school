"""The school day as a list of periods, and where "now" falls in it (SF-1).

`bell_schedules.entries` is a JSON list of `{start, end, kind, label}` that INCLUDES
breaks, in wall-clock order. Everything else in the app addresses a period by its
1-based `period_no` — the timetable grid, `class_periods`, the period card. The
mapping between the two lives here and nowhere else:

    period_no = the 1-based index among entries whose kind == 'period'

so a lunch break between periods 4 and 5 shifts no period number. Getting this
wrong would silently misalign a teacher's timesheet with their timetable, which
is why it is one pure function with tests rather than an inline enumerate() in
three services.

Pure and I/O-free — it takes the JSON it is given. `services/bell.py` is what
decides *which* list applies to a date, because that needs the database.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.core.day_shape import PERIOD_KIND

__all__ = [
    "PERIOD_KIND", "DayPeriod", "DayBreak", "periods_of", "breaks_of",
    "fallback_periods", "day_periods", "periods_before_lunch", "half_day_periods",
    "marking_period_nos", "current_period_no", "phase", "today_in", "month_bounds",
]


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
        # TT-2: the admin may name a break ("Short break", "Games") in the
        # timings editor. Falling back to the title-cased kind keeps every
        # pre-TT-2 entry rendering exactly as it did.
        out.append(DayBreak(
            after_period_no=seen,
            label=str(entry.get("label") or "").strip()
            or str(kind).replace("_", " ").capitalize(),
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


def periods_before_lunch(period_times: list[dict] | None) -> int | None:
    """How many teaching periods fall before the midday break, or None.

    The one place the school day is cut in half. Two features need the same cut
    and must not disagree: `twice_daily` attendance (V1-3, Q-03) asks for the
    first period *after* lunch, and a half-day (V1-4, `D-04`/`S-31`) needs to
    know which periods an AM absence actually costs.

    "Lunch" is computable with no extra config — `period_times` already carries
    breaks as their own entries. Prefer a break whose kind mentions lunch; else
    the break nearest the middle of the day. No break at all → None, and both
    callers degrade rather than inventing a boundary.
    """
    entries = period_times or []
    break_idxs = [i for i, e in enumerate(entries)
                  if (e.get("kind") or PERIOD_KIND) != PERIOD_KIND]
    if not break_idxs:
        return None
    lunch_idx = next(
        (i for i in break_idxs if "lunch" in str(entries[i].get("kind", "")).lower()), None)
    if lunch_idx is None:
        mid = len(entries) / 2
        lunch_idx = min(break_idxs, key=lambda i: abs(i - mid))
    return sum(1 for e in entries[:lunch_idx]
               if (e.get("kind") or PERIOD_KIND) == PERIOD_KIND)


def half_day_periods(period_times: list[dict] | None, portion: str,
                     periods_per_day: int = 8) -> list[int]:
    """Which period numbers a half-day absence covers (V1-4, `S-31`).

    ``portion='am'`` = away for the morning, so the periods before lunch are the
    ones that need covering; ``'pm'`` = the ones after. With no break in the
    timings the day cannot be halved honestly, so it falls back to splitting the
    period list down the middle — a rounded guess is better than telling the
    admin nobody needs covering, and the sheet shows which periods it picked.
    """
    periods = day_periods(period_times, periods_per_day)
    if not periods:
        return []
    cut = periods_before_lunch(period_times)
    if cut is None or cut <= 0 or cut >= len(periods):
        cut = (len(periods) + 1) // 2
    return [p.period_no for p in periods[:cut]] if portion == "am" \
        else [p.period_no for p in periods[cut:]]


def marking_period_nos(period_times: list[dict] | None, mode: str) -> list[int]:
    """Which period numbers take attendance under the org's mode (V1-3, D-01).

    * every_period  → all of them (the only behaviour until now);
    * first_period  → just the day's first period;
    * twice_daily   → the first period AND the first period after lunch — the
      mode a school picks precisely to see who left at midday (Q-03/S-05).

    "After lunch" comes from `periods_before_lunch` — the one place the day is
    cut in half, shared with V1-4's half-day (`S-31`) so the two can never
    disagree. With no break at all twice_daily degrades to first_period rather
    than inventing a slot.
    """
    periods = periods_of(period_times)
    if not periods:
        # No timings set: first_period/twice_daily still mean "period 1".
        return [] if mode == "every_period" else [1]
    if mode == "first_period":
        return [periods[0].period_no]
    if mode == "twice_daily":
        periods_before = periods_before_lunch(period_times)
        if periods_before is None:
            return [periods[0].period_no]
        after = [p.period_no for p in periods if p.period_no > periods_before]
        return [periods[0].period_no] + after[:1]
    return [p.period_no for p in periods]  # every_period


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


def month_bounds(month: str) -> tuple[date, date]:
    """"2026-08" → (2026-08-01, 2026-08-31).

    One parser for both month surfaces (the teacher's grid and the admin's
    summary) so a bad string fails the same way on each, and so neither invents
    its own idea of where a month ends. Raises `ValueError` on anything else;
    the services turn that into a `ValidationError`.
    """
    year_s, month_s = str(month).split("-")[:2]
    first = date(int(year_s), int(month_s), 1)
    next_first = (date(first.year + 1, 1, 1) if first.month == 12
                  else date(first.year, first.month + 1, 1))
    return first, next_first - timedelta(days=1)
