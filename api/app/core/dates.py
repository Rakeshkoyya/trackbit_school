"""Reading a date a human typed. One vocabulary, three importers.

Indian school sheets spell the same day a dozen ways — `14/06/2014`, `14-06-14`,
`14.06.2014`, `14 Jun 2014`, `15th Aug 2027`, a bare Excel serial, or a real date
cell openpyxl hands back as a `datetime`. Three importers grew three overlapping
answers to that: `roster_import.parse_dob` (regex, numeric only),
`setup_pack.validate.to_date` (five `strptime` formats, numeric only) and
`observance_import._parse_date` (fifteen formats including month names). A school
could therefore write `21-Aug-2026` on the Calendar sheet and have it read, write
the same thing on the Terms sheet and have it refused. This module ends that.

**Day-first, always.** `%m/%d/%Y` is deliberately absent and must stay absent: on
the rows where both readings parse, accepting it silently turns 3 April into
4 March, and a calendar that is wrong is worse than one that refused to load.
`08/21/2026` therefore returns None — correctly — because 21 is not a month.
A month *name* carries no such ambiguity, which is why `21-Aug-2026` is safe to
accept and numeric US order is not.

**Two-digit years need a policy, not a default.** `21/08/27` on a Terms sheet is
2027; `14/06/60` in a date-of-birth column is 1960. Python's own pivot (1969—2068)
is right for the first and wrong for the second, so the caller says which world it
is in via `prefer_past`. Getting this wrong is not cosmetic: a birthday read as
2060 is discarded as implausible, and that child's parent cannot log in.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any

# Day-first, then unambiguous month-name forms, then ISO. `%m/%d/%Y` is absent on
# purpose; see the module docstring.
_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y",
    "%d %b, %Y", "%d %B, %Y", "%d/%b/%Y", "%d/%B/%Y",
    "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y",
    "%d %b %y", "%d-%b-%y", "%d %B %y", "%d-%B-%y",
)

# Numeric day-first with a two-digit year, handled apart from `_FORMATS` because
# the century it belongs to is the caller's decision (see `prefer_past`).
_SHORT_NUMERIC = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})$")

# "15th Aug 2027" → "15 Aug 2027". Schools write ordinals; strptime does not read them.
_ORDINAL = re.compile(r"(\d+)(st|nd|rd|th)\b", re.IGNORECASE)

# ISO with an optional time riding along: `read_first_sheet` stringifies a real
# Excel date cell to "2015-06-03 00:00:00", and that string reaches us verbatim.
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$")

# Excel's epoch, its 1900 leap-year bug included. openpyxl normally hands back a
# real datetime, so this only fires on a serial sitting in a text-formatted column.
_EXCEL_EPOCH = date(1899, 12, 30)
# ≈1927—2064. Wide enough for any birthday or school date, narrow enough that a
# roll number or an amount typed into a date column is not silently read as one.
_SERIAL_MIN, _SERIAL_MAX = 10_000, 60_000


def _century(two_digit: int, *, prefer_past: bool, today: date) -> int:
    """Which century a two-digit year belongs to.

    `prefer_past` is the birthday reading, carried over verbatim from
    `roster_import.parse_dob`: anything at or below the current two-digit year is
    this century, anything above it is the last one, so `14` is 2014 and `80` is
    1980. Without it we use Python's own pivot, which is what a term or exam date
    wants — those run into the future.
    """
    if prefer_past:
        return two_digit + (2000 if two_digit <= today.year % 100 else 1900)
    return two_digit + (2000 if two_digit < 69 else 1900)


def read_date(value: Any, *, prefer_past: bool = False,
              year_hint: int | None = None, today: date | None = None) -> date | None:
    """One calendar date, or None when it cannot be read *safely*.

    None is a real answer here, not a failure to try: every caller treats an
    unreadable date as "not known", which is a state the pack is allowed to be in.
    Guessing would be the bug.

    `prefer_past` decides the century for a two-digit year — pass True for dates
    of birth. `year_hint` accepts a day and month with no year at all ("15 August"),
    which happens on sheets whose title carries the year and whose rows do not.
    """
    if value is None:
        return None
    # A real date cell. openpyxl gives these back for anything Excel itself
    # recognised as a date, which is the common case and needs no parsing.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None
    today = today or date.today()

    # A bare number in a text column is an Excel serial.
    if re.fullmatch(r"\d{5}(\.\d+)?", raw):
        try:
            return _EXCEL_EPOCH + timedelta(days=int(float(raw)))
        except (ValueError, OverflowError):
            return None

    text = _ORDINAL.sub(r"\1", raw.replace(",", ", ").replace("  ", " ")).strip()

    iso = _ISO.match(text)
    if iso:
        try:
            return date(*(int(g) for g in iso.groups()))
        except ValueError:
            return None

    short = _SHORT_NUMERIC.match(text)
    if short:
        day, month, year = (int(g) for g in short.groups())
        try:
            return date(_century(year, prefer_past=prefer_past, today=today),
                        month, day)
        except ValueError:
            return None

    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    if year_hint:
        for fmt in ("%d %b", "%d %B", "%b %d", "%B %d", "%d/%m", "%d-%m"):
            try:
                return datetime.strptime(text, fmt).date().replace(year=year_hint)
            except ValueError:
                continue
    return None


def read_excel_serial(raw: str) -> date | None:
    """A bare Excel serial, range-checked. Split out because `parse_dob` accepts
    one from a column that has already failed every textual reading."""
    if not raw.isdigit():
        return None
    serial = int(raw)
    if _SERIAL_MIN <= serial <= _SERIAL_MAX:
        return _EXCEL_EPOCH + timedelta(days=serial)
    return None
