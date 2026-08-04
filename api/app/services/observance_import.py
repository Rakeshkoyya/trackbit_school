"""The annual catalogue import — next year's dates, from a spreadsheet (V1-20).

`D-60` chose *fetch and store* over a checked-in file, and `S-151` named the
realistic shape: **a small importer per source plus one annual human review**.
V1-19 shipped the corpus for 2026–27 as code; this is how the super-admin adds
2028 without a deploy — collect the year's dates however they like (a panchang,
the state notifications, a colleague's spreadsheet), drop the file in, check the
preview, save.

**The division of labour is the codebase's standing rule and it is what keeps
this testable offline** (`ingest.py`): deterministic parsers decide what a value
IS, the model only proposes which COLUMN means what, and only for columns the
keyword heuristic could not place. So:

  * `_parse_date` reads Excel serials, real datetimes and eleven written
    formats, and is **day-first** — this is an Indian product and `03/04/2028`
    is 3 April, not 4 March. A date it cannot read becomes a **reported error on
    that row**, never a guess and never a silently dropped row.
  * `_parse_states` resolves against `core/indian_states.py` and reports what it
    could not place, because an unresolvable state imports perfectly and then
    matches no school for a year.
  * The model never sees a date and never decides one. Asking it "when is Diwali
    in 2028" is `S-123`'s rejected row; asking it "which of these columns is the
    date column" is a mapping problem it is good at and a human confirms.

Nothing here writes. `analyze` returns rows and problems; `commit` takes back
what the human approved and hands it to `ObservanceService.bulk`, which upserts
on (key, date) — so re-importing a corrected file FIXES every school rather than
double-suggesting to all of them.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.indian_states import normalise, normalise_all
from app.schemas.events import (
    ObservanceBulkIn,
    ObservanceImportCommitOut,
    ObservanceImportRow,
    ObservanceIn,
)
from app.services.ingest import FieldSpec, build_analysis
from app.services.observances import ObservanceService, slugify
from app.services.roster_import import read_first_sheet

SPECS = [
    FieldSpec("name", ["name", "festival", "holiday", "event", "occasion", "title",
                       "observance", "description"],
              required=True, label="the name of the day"),
    FieldSpec("date", ["date", "on", "day", "from", "start date", "start"],
              required=True, label="the date"),
    FieldSpec("end_date", ["end date", "end", "to", "until", "till", "last day"],
              label="the last day, for a multi-day festival"),
    FieldSpec("states", ["state", "states", "region", "applicable", "applicable states",
                         "observed in", "where"],
              label="the states that observe it (blank = all India)"),
    FieldSpec("kind", ["kind", "type", "category"], label="holiday / festival / observance"),
    FieldSpec("tier", ["tier", "importance", "priority", "major"], label="major or minor"),
    FieldSpec("tradition", ["tradition", "religion", "community", "faith"],
              label="tradition"),
    FieldSpec("prep_days", ["prep days", "prep", "lead time", "notice", "prep_days"],
              label="how many days' notice it needs"),
    FieldSpec("note", ["note", "notes", "remark", "remarks", "comment"], label="note"),
    FieldSpec("source", ["source", "reference", "authority", "published by"],
              label="where the date came from"),
]

# `S-125` / the model's vocabulary. Anything unrecognised falls back to the
# safest default rather than failing the row: a wrong `kind` is a label the
# admin fixes at approval, a lost row is a date the school never hears about.
_KINDS = {"holiday", "festival", "observance"}
_TIERS = {"major", "minor"}
_KIND_ALIASES = {
    "public holiday": "holiday", "gazetted": "holiday", "gazetted holiday": "holiday",
    "closed": "holiday", "restricted": "festival", "restricted holiday": "festival",
    "optional": "festival", "celebration": "festival", "national day": "observance",
    "international day": "observance", "awareness day": "observance", "day": "observance",
}
_TIER_ALIASES = {
    "high": "major", "important": "major", "primary": "major", "1": "major", "yes": "major",
    "low": "minor", "secondary": "minor", "optional": "minor", "2": "minor", "no": "minor",
}

# Written formats seen in real state notifications and panchang exports.
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
    "%b %d %Y", "%B %d %Y", "%d-%b-%Y", "%d-%B-%Y", "%d %b, %Y", "%d %B, %Y",
    "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y",
)
# Excel's epoch. 1900 is deliberate (Excel's own off-by-one leap bug included):
# openpyxl usually hands back a datetime, so this only fires on a raw serial in
# a text-formatted column.
_EXCEL_EPOCH = date(1899, 12, 30)

_ALL_INDIA_WORDS = {
    "", "all", "all india", "all-india", "india", "all states", "national",
    "nationwide", "everywhere", "pan india", "pan-india", "any", "-", "na", "n/a",
}

_SPLIT = re.compile(r"[;,|/\n]+")


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value: Any, *, year_hint: int | None = None) -> date | None:
    """Read a date cell, day-first, or return None.

    Day-first is not a preference — it is the correct reading for every source
    this importer exists to consume. `%m/%d/%Y` is deliberately absent: silently
    accepting it would turn 3 April into 4 March on exactly the rows where both
    parse, which is the worst possible failure for a calendar.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _clean(value)
    if not raw:
        return None

    # A bare number in a text column is an Excel serial.
    if re.fullmatch(r"\d{5}(\.\d+)?", raw):
        try:
            return _EXCEL_EPOCH + timedelta(days=int(float(raw)))
        except (ValueError, OverflowError):
            return None

    normalised = raw.replace(",", ", ").replace("  ", " ").strip()
    # "15th Aug 2027" → "15 Aug 2027"
    normalised = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", normalised, flags=re.I)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(normalised, fmt).date()
        except ValueError:
            continue
    # "15 August" with the year known from the import — common in a sheet whose
    # title carries the year and whose rows do not repeat it.
    if year_hint:
        for fmt in ("%d %b", "%d %B", "%b %d", "%B %d", "%d/%m", "%d-%m"):
            try:
                parsed = datetime.strptime(normalised, fmt).date()
                return parsed.replace(year=year_hint)
            except ValueError:
                continue
    return None


def _parse_states(value: Any) -> tuple[list[str] | None, list[str]]:
    """(canonical states, unresolvable names).

    Blank, or any of the all-India words, means None — every school. That
    default matters: a row scoped to nothing is invisible, and the commonest
    thing a spreadsheet says in this column is nothing at all.
    """
    raw = _clean(value)
    if raw.lower() in _ALL_INDIA_WORDS:
        return None, []
    parts = [p.strip() for p in _SPLIT.split(raw) if p.strip()]
    if not parts:
        return None, []
    resolved = normalise_all(parts)
    bad = [p for p in parts if normalise(p) is None]
    return (resolved or None), bad


def _parse_choice(value: Any, allowed: set[str], aliases: dict[str, str],
                  default: str) -> str:
    raw = _clean(value).lower()
    if raw in allowed:
        return raw
    return aliases.get(raw, default)


def _parse_int(value: Any, default: int) -> int:
    raw = _clean(value)
    if not raw:
        return default
    try:
        return max(0, min(120, int(float(raw))))
    except ValueError:
        return default


def analyze(data: bytes) -> dict[str, Any]:
    """Columns, a proposed mapping and the raw rows — the shared envelope."""
    columns, rows = read_first_sheet(data)
    return build_analysis("observances", columns, rows, SPECS).as_dict()


def preview(*, mapping: dict[str, str], rows: list[dict[str, Any]],
            default_source: str, year_hint: int | None = None,
            ) -> list[ObservanceImportRow]:
    """Resolve every row to what would be stored, with its problems attached.

    Deliberately returns **every** row including the broken ones. An importer
    that silently drops what it cannot read reports "142 imported" over a file
    of 150 and nobody ever finds the eight — the roster importer learned this
    (V2-P11's `unresolved`), and a calendar has the same failure with worse
    consequences, because the missing row is a day a school stays open for.
    """
    out: list[ObservanceImportRow] = []

    def cell(row: dict, field: str) -> Any:
        column = mapping.get(field)
        return row.get(column) if column else None

    for index, row in enumerate(rows):
        problems: list[str] = []
        name = _clean(cell(row, "name"))
        on = _parse_date(cell(row, "date"), year_hint=year_hint)
        end = _parse_date(cell(row, "end_date"), year_hint=year_hint)
        states, bad_states = _parse_states(cell(row, "states"))

        if not name:
            problems.append("No name.")
        if on is None:
            raw = _clean(cell(row, "date"))
            problems.append(
                f'Could not read "{raw}" as a date.' if raw else "No date.")
        if end and on and end < on:
            problems.append("The end date is before the start date.")
            end = None
        for bad in bad_states:
            problems.append(f'"{bad}" is not a state we recognise.')

        source = _clean(cell(row, "source")) or default_source
        out.append(ObservanceImportRow(
            index=index,
            name=name or _clean(cell(row, "date")) or f"Row {index + 1}",
            key=slugify(name) if name else "",
            date=on,
            end_date=end,
            kind=_parse_choice(cell(row, "kind"), _KINDS, _KIND_ALIASES, "festival"),
            tier=_parse_choice(cell(row, "tier"), _TIERS, _TIER_ALIASES, "major"),
            states=states,
            tradition=_clean(cell(row, "tradition")) or None,
            prep_days=_parse_int(cell(row, "prep_days"), 7),
            note=_clean(cell(row, "note")) or None,
            source=source,
            problems=problems,
            importable=not problems,
        ))
    return out


class ObservanceImportService:
    def __init__(self, db: Session):
        self.db = db

    def commit(self, *, mapping: dict[str, str], rows: list[dict[str, Any]],
               default_source: str, year_hint: int | None,
               user_id: uuid.UUID | None) -> ObservanceImportCommitOut:
        """Import the rows that parsed; report the rest by name.

        Only `importable` rows are written. The rest come back with their
        problems so the operator fixes the sheet and re-runs — which is safe,
        because `bulk()` upserts on (key, date).
        """
        resolved = preview(mapping=mapping, rows=rows, default_source=default_source,
                           year_hint=year_hint)
        good = [r for r in resolved if r.importable and r.date]
        skipped = [r for r in resolved if not r.importable]

        # (key, date) is unique. Two rows colliding inside ONE file would not
        # error — the second would overwrite the first — so it is caught here
        # and reported, exactly as `collisions()` does for the shipped corpus.
        seen: dict[tuple[str, str], int] = {}
        duplicates: list[str] = []
        entries: list[ObservanceIn] = []
        for r in good:
            pair = (r.key, r.date.isoformat())
            if pair in seen:
                duplicates.append(f"{r.name} on {r.date.isoformat()}")
                continue
            seen[pair] = r.index
            entries.append(ObservanceIn(
                key=r.key, name=r.name, date=r.date, end_date=r.end_date,
                kind=r.kind, tier=r.tier, prep_days=r.prep_days, states=r.states,
                tradition=r.tradition, source=r.source, note=r.note))

        out = ObservanceImportCommitOut(
            skipped=[f"{r.name}: {' '.join(r.problems)}" for r in skipped],
            duplicates=duplicates)
        if not entries:
            return out

        svc = ObservanceService(self.db)
        for i in range(0, len(entries), 500):
            result = svc.bulk(ObservanceBulkIn(
                source=default_source, entries=entries[i:i + 500]), user_id)
            out.created += result.created
            out.updated += result.updated
            for bad in result.unresolved_states:
                if bad not in out.unresolved_states:
                    out.unresolved_states.append(bad)
        return out
