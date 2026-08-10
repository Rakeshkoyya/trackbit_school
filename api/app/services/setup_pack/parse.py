"""Read a filled setup pack back (SETUP-REDESIGN-PLAN §4, phase P1).

Structure only. This module answers *what did the school actually send* — which
sheets, which columns, which rows — and nothing about whether the content makes
sense. Meaning is the validator's job (P2) and writing is the committer's (P3);
keeping them apart is what lets the operator re-upload a corrected file as often
as they like with nothing persisted in between.

What a real school's file looks like, and what that forces:

  * **Banner rows.** The founder's reference sheet puts "CLASS 7 — SYLLABUS
    TRACKER (2026-27, Jul–Nov)" in row 1 and the headers in row 2. So the header
    row is *found* by matching against the spec's hints, not assumed to be row 1.
  * **Renamed headers.** That same file calls a chapter "Chapter Name" and a
    teacher "Mentor". Every column carries a hint list for exactly this.
  * **Numbers where text is meant.** "Ch #" arrives as `1.0`. An integral float
    becomes "1", never "1.0" — a chapter numbered 1.0 reads as a bug to the
    operator reviewing the import.
  * **Real date cells.** openpyxl hands back `datetime`, not the "14/06/2014" the
    school typed. Normalised to ISO, which `parse_dob` already accepts alongside
    day-first text — so both spellings survive without this module having to
    decide what a date means.
"""

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openpyxl import load_workbook

from app.services.setup_pack.specs import READ_ME, SHEETS, SheetSpec

# How many rows to search for the header before giving up and taking the first
# non-empty one. Banner blocks are two or three rows; ten is generous.
HEADER_SEARCH_ROWS = 10


def normalise(text: str) -> str:
    """Fold a sheet title or a column header to something comparable.

    Case, punctuation, and the en/em dashes schools paste from Word all stop
    mattering: "Read Me", "READ-ME" and "Read  me" are one thing.
    """
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def cell_text(value: Any) -> str | None:
    """One cell as text, or None for genuinely empty.

    None is the pack's load-bearing value — it means "not known yet" everywhere
    (a chapter nobody has sized, a subject nobody teaches yet). So a cell that is
    blank, whitespace, or an Excel error must arrive as None and not as a string
    that later reads as data.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if not text or text.upper() in {"#N/A", "#VALUE!", "#REF!", "NA", "-"}:
        return None
    return text


def map_headers(headers: list[str | None], spec: SheetSpec) -> dict[str, str]:
    """Header text → our field keys. Exact matches first, across ALL columns,
    then substrings; a column is claimed by at most one field.

    Deliberately not `ingest.heuristic_mapping`, which scores one field at a time
    and lets two fields claim the same column. On a three-column sheet that never
    showed; on this pack, "Class" and "Class teacher" sit side by side and a
    first-past-the-post pass gives both to the same cell. The existing importers
    keep their mapper — this is an additional one, not a replacement.
    """
    available = {i: normalise(h) for i, h in enumerate(headers) if h}
    taken: dict[str, str] = {}
    claimed: set[int] = set()

    for exact in (True, False):
        for col in spec.columns:
            if col.key in taken:
                continue
            for hint in (normalise(col.header), *(normalise(h) for h in col.hints)):
                hit = next(
                    (i for i, text in available.items()
                     if i not in claimed
                     and (text == hint if exact else hint and hint in text)),
                    None)
                if hit is not None:
                    taken[col.key] = str(headers[hit])
                    claimed.add(hit)
                    break
    return taken


@dataclass
class SheetData:
    """One sheet as read. `present=False` means the school did not send it."""

    key: str
    title: str
    present: bool = False
    columns: list[str] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, str | None]] = field(default_factory=list)
    # The 1-based Excel row each parsed row came from, aligned with `rows`.
    # Blank rows are skipped during parsing, so index+1 is NOT the row number —
    # and a finding that says "row 47" when the school must look at row 61 is
    # worse than one that says nothing.
    row_numbers: list[int] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def excel_row(self, index: int) -> int | None:
        return self.row_numbers[index] if index < len(self.row_numbers) else None


@dataclass
class ParsedPack:
    sheets: dict[str, SheetData] = field(default_factory=dict)
    missing_sheets: list[str] = field(default_factory=list)
    extra_sheets: list[str] = field(default_factory=list)

    def rows(self, key: str) -> list[dict[str, str | None]]:
        data = self.sheets.get(key)
        return data.rows if data else []

    def setting(self, key: str) -> str | None:
        """One value off the School sheet."""
        rows = self.rows("school")
        return rows[0].get(key) if rows else None

    @property
    def total_rows(self) -> int:
        return sum(s.row_count for s in self.sheets.values() if s.key != "school")


def _find_header_row(grid: list[tuple], spec: SheetSpec) -> int | None:
    """The row that looks most like this sheet's headers.

    Scored, not assumed: a banner row scores 0 because none of its cells match a
    hint, so "CLASS 7 — SYLLABUS TRACKER" never gets mistaken for a header.
    """
    best_idx, best_score = None, 0
    for i, row in enumerate(grid[:HEADER_SEARCH_ROWS]):
        headers = [cell_text(c) for c in row]
        if not any(headers):
            continue
        score = len(map_headers(headers, spec))
        if score > best_score:
            best_idx, best_score = i, score
    if best_score >= min(2, len(spec.columns)):
        return best_idx
    return next((i for i, row in enumerate(grid)
                 if any(cell_text(c) for c in row)), None)


def _read_table(grid: list[tuple], spec: SheetSpec) -> SheetData:
    data = SheetData(key=spec.key, title=spec.title, present=True)
    header_idx = _find_header_row(grid, spec)
    if header_idx is None:
        data.missing_columns = spec.required_keys
        return data

    headers = [cell_text(c) for c in grid[header_idx]]
    data.columns = [h for h in headers if h]
    data.mapping = map_headers(headers, spec)
    index = {key: headers.index(header) for key, header in data.mapping.items()}
    data.unmapped_columns = [h for h in data.columns if h not in data.mapping.values()]
    data.missing_columns = [k for k in spec.required_keys if k not in data.mapping]

    for offset, row in enumerate(grid[header_idx + 1:], start=header_idx + 2):
        values = {
            key: (cell_text(row[i]) if i < len(row) else None)
            for key, i in index.items()
        }
        if any(v for v in values.values()):
            data.rows.append(values)
            data.row_numbers.append(offset)
    return data


def _read_key_value(grid: list[tuple], spec: SheetSpec) -> SheetData:
    """The School sheet: match column A against the setting labels, take column B."""
    data = SheetData(key=spec.key, title=spec.title, present=True)
    by_hint: dict[str, str] = {}
    for setting in spec.settings:
        for hint in (setting.label, *setting.hints):
            by_hint.setdefault(normalise(hint), setting.key)

    values: dict[str, str | None] = {s.key: None for s in spec.settings}
    seen: list[str] = []
    unknown: list[str] = []
    for row in grid:
        label = cell_text(row[0]) if row else None
        if not label or normalise(label) == "field":
            continue
        value = cell_text(row[1]) if len(row) > 1 else None
        key = by_hint.get(normalise(label))
        if key is None:
            # A setting we do not know. Only worth reporting when the school
            # actually filled something in beside it — an unmatched label with an
            # empty cell is a spacer or a heading, not a value we are dropping.
            if value is not None:
                unknown.append(label)
            continue
        seen.append(label)
        values[key] = value

    data.columns = seen
    data.unmapped_columns = unknown
    data.mapping = {k: k for k, v in values.items() if v is not None}
    data.rows = [values]
    data.missing_columns = [k for k in spec.required_keys if not values.get(k)]
    return data


def parse_pack(data: bytes) -> ParsedPack:
    """The workbook as structure. Never raises on a messy file — an unreadable
    sheet comes back absent, which the validator reports with its consequence."""
    pack = ParsedPack()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        by_title = {normalise(ws.title): ws for ws in wb.worksheets}
        matched: set[str] = set()
        for spec in SHEETS:
            ws = by_title.get(normalise(spec.title))
            if ws is None:
                pack.sheets[spec.key] = SheetData(key=spec.key, title=spec.title)
                if spec.required:
                    pack.missing_sheets.append(spec.title)
                continue
            matched.add(normalise(spec.title))
            grid = list(ws.iter_rows(values_only=True))
            pack.sheets[spec.key] = (
                _read_key_value(grid, spec) if spec.is_key_value
                else _read_table(grid, spec))
        pack.extra_sheets = [
            ws.title for ws in wb.worksheets
            if normalise(ws.title) not in matched
            and normalise(ws.title) != normalise(READ_ME)
        ]
    finally:
        wb.close()
    return pack


def fill_down(rows: list[dict[str, str | None]], keys: tuple[str, ...],
              ) -> list[dict[str, str | None]]:
    """Carry a blank cell's value down from the row above, for the named keys.

    This is how humans write these sheets: a chapter spanning four topic rows is
    written once and merged, and a merged cell exports as one value followed by
    blanks. `syllabus_import.rows_to_units` already honours it for chapter and
    term; the pack needs it for class and subject too, because one sheet now
    holds every class.

    Returns new dicts — the parsed rows are left alone so a validator can always
    report what the school literally sent.
    """
    out: list[dict[str, str | None]] = []
    carried: dict[str, str | None] = {}
    for row in rows:
        merged = dict(row)
        for key in keys:
            if merged.get(key):
                carried[key] = merged[key]
            elif carried.get(key):
                merged[key] = carried[key]
        out.append(merged)
    return out
