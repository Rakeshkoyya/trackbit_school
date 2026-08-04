"""The shipped observance corpus, resolved to a year (V1-19).

`build(year)` is the one entry point. It answers *"what dates exist for this
year"* and nothing else — it does not touch the database, does not know what a
school is, and has no idea which state anybody is in. That keeps it testable as
pure data and keeps the loader (`scripts/load_observances.py`) a thin thing that
only writes.

**Coverage:** `FIXED` + `FIXED_INTERNATIONAL` generate for any year at all;
`MOVABLE` is populated for the years a human has curated. `available_years()`
says which those are, so a caller asking for 2029 gets an honest partial answer
plus a warning rather than a corpus that has quietly lost every festival.
"""

from __future__ import annotations

from datetime import timedelta

from app.core.indian_states import normalise_all

from .india import FIXED, MOVABLE
from .international import FIXED_INTERNATIONAL
from .types import BuiltRow, Entry

__all__ = ["available_years", "build", "collisions", "summarise"]


def available_years() -> list[int]:
    """The years `MOVABLE` has been curated for. `FIXED` covers everything."""
    return sorted(MOVABLE)


def _row(entry: Entry, on, source_year: int) -> BuiltRow:
    end = on + timedelta(days=entry.span_days - 1) if entry.span_days > 1 else None
    # Normalised here rather than trusted from the data files: the corpus is
    # hand-written, and a typo like "Tamilnadu" would otherwise import cleanly
    # and then match no school for a year. The loader reports what it drops.
    states = normalise_all(list(entry.states)) if entry.states else None
    return BuiltRow(
        key=entry.key,
        name=entry.name,
        date=on,
        end_date=end,
        kind=entry.kind,
        tier=entry.tier,
        prep_days=entry.prep_days,
        states=states or None,
        board=entry.board,
        tradition=entry.tradition,
        source=entry.source or f"TrackBit corpus {source_year}",
        note=entry.note,
    )


def build(year: int) -> list[BuiltRow]:
    """Every corpus row for `year`, date-ordered.

    Fixed rows are generated; movable rows are taken from the curated block if
    one exists for the year. A year with no `MOVABLE` block still returns the
    ~230 fixed rows, which is a real and useful answer — it just has no
    festivals in it, and `available_years()` is how a caller knows that.
    """
    rows: list[BuiltRow] = []
    for f in (*FIXED, *FIXED_INTERNATIONAL):
        rows.append(_row(f.entry, f.on(year), year))
    for m in MOVABLE.get(year, []):
        on = m.on(year)
        if on.year != year:
            # A curated block filed under the wrong year is a data bug, not a
            # runtime condition — but silently importing it would put a 2027
            # date in the 2026 import and be very hard to spot afterwards.
            raise ValueError(
                f"MOVABLE[{year}] contains {m.entry.key} dated {on.isoformat()}")
        rows.append(_row(m.entry, on, year))
    rows.sort(key=lambda r: (r.date, r.name))
    return rows


def collisions(year: int) -> list[tuple[str, str]]:
    """(key, iso-date) pairs that appear more than once.

    `observances` carries `UNIQUE(key, date)`, so a duplicate does not raise on
    import — `bulk()` upserts, and the second row silently overwrites the first.
    That is precisely the failure mode this corpus was written to fix, so the
    corpus checks itself for it. Called by the loader before it writes and by
    the test suite; a non-empty result is a bug in the data files.
    """
    seen: dict[tuple[str, str], int] = {}
    for r in build(year):
        pair = (r.key, r.date.isoformat())
        seen[pair] = seen.get(pair, 0) + 1
    return [pair for pair, n in seen.items() if n > 1]


def summarise(year: int) -> dict:
    """What was built, for the loader's report and for a human reading it."""
    rows = build(year)
    by_kind: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    states: set[str] = set()
    for r in rows:
        by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
        by_tier[r.tier] = by_tier.get(r.tier, 0) + 1
        states.update(r.states or ())
    return {
        "year": year,
        "total": len(rows),
        "all_india": sum(1 for r in rows if not r.states),
        "state_scoped": sum(1 for r in rows if r.states),
        "states_covered": len(states),
        "by_kind": by_kind,
        "by_tier": by_tier,
        "movable_curated": year in MOVABLE,
    }
