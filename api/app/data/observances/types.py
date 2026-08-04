"""The two shapes the corpus is written in, and the line between them (V1-19).

Every date in the Indian school calendar is one of two kinds, and the
distinction is not cosmetic — it decides how much work next year costs.

**`Fixed`** recurs on the same (month, day) every year: Republic Day, every
state formation day, every UN international day, Ambedkar Jayanti. These are
generated for ANY year by arithmetic. Nobody re-researches them, ever.

**`Movable`** is tied to a lunisolar or Hijri calendar and must be looked up per
year: Diwali, Eid, Onam, Holi, Easter. These are the only rows a human touches
when the corpus is extended — which is the point of splitting the file this way.
Extending to 2028 is "add one `MOVABLE[2028]` block", not "re-key 700 rows".

⚠️ **`source` is required on every row and is never decorative** (`S-150`).
The admin approving a date is the last human in the chain; an unattributed date
is one they either approve blindly or ignore entirely. Where two authorities
genuinely disagree — and for movable dates they routinely do, because almanacs
differ regionally and a tithi that ends near midnight lands on different days in
different states — the disagreement goes in `note`, naming both. It is never
averaged, never silently resolved, and never hidden: the approval sheet's date
field is editable (`D-79`), so the admin resolves it against their own state's
gazette in one tap. That editable field is the structural answer to the fact
that no single national calendar is correct for every school.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# `states=ALL_INDIA` reads better at 300 call sites than `states=None`, and it
# makes "we deliberately did not scope this" visible rather than implied.
ALL_INDIA: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Entry:
    """The fields every corpus row carries, independent of how its date is got."""

    key: str
    name: str
    kind: str = "festival"          # holiday | festival | observance
    tier: str = "major"             # major | minor  (`S-125` — the feed shows major)
    prep_days: int = 7              # `S-126` — lead time, by what the date needs
    states: tuple[str, ...] | None = None   # None = all India
    board: str | None = None
    tradition: str | None = None
    source: str = ""
    note: str | None = None
    # Multi-day observances (Onam, Durga Puja, Bohag Bihu) carry a span. Stored
    # as a day count so a Fixed row can generate it for any year.
    span_days: int = 1


@dataclass(frozen=True)
class Fixed:
    """Same month and day every year."""

    month: int
    day: int
    entry: Entry

    def on(self, year: int) -> date:
        return date(year, self.month, self.day)


@dataclass(frozen=True)
class Movable:
    """A date that has to be looked up for the specific year."""

    iso: str
    entry: Entry

    def on(self, _year: int) -> date:
        return date.fromisoformat(self.iso)


@dataclass
class BuiltRow:
    """One corpus row resolved to a concrete year, ready for `ObservanceIn`."""

    key: str
    name: str
    date: date
    end_date: date | None
    kind: str
    tier: str
    prep_days: int
    states: list[str] | None
    board: str | None
    tradition: str | None
    source: str
    note: str | None
    is_active: bool = True

    def as_payload(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "date": self.date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "kind": self.kind,
            "tier": self.tier,
            "prep_days": self.prep_days,
            "states": self.states,
            "board": self.board,
            "tradition": self.tradition,
            "source": self.source,
            "note": self.note,
            "is_active": self.is_active,
        }


def group(*names: str) -> tuple[str, ...]:
    """Readability helper — a named set of states at the point of use."""
    return tuple(names)


# Frequently reused state sets. Named for the thing they have in common, not
# for a region, because "South India" is not why these five observe Ugadi.
UGADI_STATES = group("Karnataka", "Andhra Pradesh", "Telangana")
TAMIL_STATES = group("Tamil Nadu", "Puducherry")
BENGALI_STATES = group("West Bengal", "Tripura", "Assam", "Jharkhand", "Odisha", "Bihar")
CHHATH_STATES = group("Bihar", "Jharkhand", "Uttar Pradesh", "Delhi")
MAY_DAY_STATES = group(
    "Tamil Nadu", "Kerala", "Karnataka", "West Bengal", "Assam", "Bihar",
    "Maharashtra", "Telangana", "Andhra Pradesh", "Manipur", "Tripura",
    "Puducherry", "Goa",
)
PUNJAB_HARYANA = group("Punjab", "Haryana", "Chandigarh", "Himachal Pradesh", "Delhi")
NORTH_EAST = group(
    "Assam", "Arunachal Pradesh", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Tripura", "Sikkim",
)

__all__ = [
    "ALL_INDIA",
    "BENGALI_STATES",
    "BuiltRow",
    "CHHATH_STATES",
    "Entry",
    "Fixed",
    "MAY_DAY_STATES",
    "Movable",
    "NORTH_EAST",
    "PUNJAB_HARYANA",
    "TAMIL_STATES",
    "UGADI_STATES",
    "field",
    "group",
]
