"""Events & dates — the what's-on feed, the approval sheet, the catalogue (V1-7).

One shape (`FeedItem`) carries all three sources — a birthday, the school's own
calendar row, and an approved observance — because they are one computation with
many renderings (ux §9). A consumer that needs to tell them apart reads `source`;
none of them needs a second endpoint.
"""

import uuid
from datetime import date as date_

from pydantic import BaseModel, ConfigDict, Field, model_validator

FEED_SOURCES = "^(birthday|calendar|staff_birthday)$"
LOCK_LEVELS = "^(closed|periods|open)$"


# ── the feed (the read side `calendar_events` has never had) ─────────────────
class FeedItem(BaseModel):
    """One dated thing, in the plainest form every surface can render.

    `on_date` is the date it *shows* on, which for a birthday landing in a
    vacation is the nearest working day (`S-128`) — `actual_date` is then the
    real one, and the copy says so rather than quietly moving a child's birthday.
    """
    source: str                       # birthday | staff_birthday | calendar
    on_date: date_
    actual_date: date_ | None = None  # set only when it differs from on_date
    title: str
    detail: str | None = None
    # calendar rows only
    event_id: uuid.UUID | None = None
    event_type: str | None = None     # holiday | exam_block | event | celebration
    affects_teaching: bool | None = None
    blocks_periods: list[int] | None = None
    # birthdays only
    student_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None
    class_label: str | None = None
    # `S-126` — a big date surfaces early, a birthday the morning of. Days until
    # `on_date`; negative never happens (the feed starts today).
    days_away: int = 0


class WhatsOn(BaseModel):
    """Today, the rest of the horizon, and the coverage sentence.

    `dob_known` / `dob_total` exist so an empty card can say *why* it is empty
    with its denominator (`S-124`, ux §4) — *"Birthdays known for 41 of 486
    students"* — rather than looking broken.
    """
    date: date_
    today: list[FeedItem] = []
    upcoming: list[FeedItem] = []
    dob_known: int = 0
    dob_total: int = 0
    # Admin only: how many catalogue suggestions are waiting on a decision.
    pending_suggestions: int = 0


# ── the catalogue, as the school sees it ────────────────────────────────────
class SuggestionOut(BaseModel):
    """A catalogue entry this school has not yet decided on.

    It is a **prompt to pick a date, never a date** (`D-79`) — which is why the
    approval sheet's date field is editable and pre-filled from `date`, and why
    one suggested row can produce two approvals (Christmas the holiday on the
    25th, the Christmas celebration on the 22nd).
    """
    id: uuid.UUID
    key: str
    name: str
    date: date_
    end_date: date_ | None = None
    kind: str
    tier: str
    prep_days: int
    tradition: str | None = None
    # `S-150` — the provenance line, rendered on the row.
    source: str
    note: str | None = None
    days_away: int
    # Already approved once (the second approval is legitimate, so this is a
    # label on the row, never a block).
    approved_count: int = 0


class ApproveIn(BaseModel):
    """`D-58`'s three lock levels, with the date the admin actually picked.

    `closed` = the whole day leaves every plan. `periods` = only these periods
    go (`blocks_periods`). `open` = marked on the calendar, nothing lost. Both
    map onto `affects_teaching` + `blocks_periods`, which the effective-days
    engine has prorated since V2-P7 — there is no new engine here.
    """
    title: str | None = Field(default=None, max_length=200)
    start_date: date_
    end_date: date_ | None = None
    lock: str = Field(pattern=LOCK_LEVELS)
    blocks_periods: list[int] | None = None
    event_type: str = Field(default="holiday",
                            pattern="^(holiday|exam_block|event|celebration)$")
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self) -> "ApproveIn":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        if self.lock == "periods" and not self.blocks_periods:
            raise ValueError("Say which periods this takes.")
        if self.lock != "periods":
            self.blocks_periods = None
        return self


class DismissIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    observance_key: str
    action: str
    calendar_event_id: uuid.UUID | None = None
    note: str | None = None


# ── `S-143` the cost, before they commit ────────────────────────────────────
class CostMove(BaseModel):
    class_label: str
    subject_name: str
    from_status: str
    to_status: str


class LockCost(BaseModel):
    """What locking these dates removes, in periods and in RAG moves.

    Without this a principal locks three days for Diwali and watches six
    subjects turn amber with no idea why — `effective_periods` is computed live,
    so the colours move the instant the row is written.
    """
    days_lost: float = 0            # working days removed (a partial day is a fraction)
    periods_lost: int = 0
    working_days: int = 0           # how many of the picked days the school works
    already_blocked: int = 0        # days that were closed anyway — cost nothing
    moves: list[CostMove] = []
    unaffected: int = 0
    sentence: str = ""


class CostIn(BaseModel):
    academic_year_id: uuid.UUID
    start_date: date_
    end_date: date_ | None = None
    lock: str = Field(pattern=LOCK_LEVELS)
    blocks_periods: list[int] | None = None


# ── the platform catalogue (super-admin) ────────────────────────────────────
class ObservanceIn(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    date: date_
    end_date: date_ | None = None
    kind: str = Field(default="festival", pattern="^(holiday|festival|observance)$")
    tier: str = Field(default="major", pattern="^(major|minor)$")
    prep_days: int = Field(default=7, ge=0, le=120)
    # V1-19 — the set of states that observe this, canonical tokens from
    # `core/indian_states.py`. Empty/None = all India. The service normalises
    # on write and REPORTS what it could not place rather than dropping it
    # silently, so a typo in a bulk import is visible instead of producing a
    # state no school will ever match.
    states: list[str] | None = Field(default=None, max_length=40)
    board: str | None = Field(default=None, max_length=80)
    tradition: str | None = Field(default=None, max_length=80)
    source: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @model_validator(mode="after")
    def _order(self) -> "ObservanceIn":
        if self.end_date and self.end_date < self.date:
            raise ValueError("end_date must be on or after date.")
        return self


class ObservanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    name: str
    date: date_
    end_date: date_ | None = None
    kind: str
    tier: str
    prep_days: int
    states: list[str] | None = None
    board: str | None = None
    tradition: str | None = None
    source: str
    note: str | None = None
    is_active: bool
    # How many schools have already decided on this entry — the operator's one
    # signal that correcting a date is now a correction, not an edit.
    decided_count: int = 0


class ObservanceBulkIn(BaseModel):
    """A year's import from one source. Upserts on (key, date) so re-running a
    corrected file fixes every school rather than double-suggesting."""
    source: str = Field(min_length=1, max_length=200)
    entries: list[ObservanceIn] = Field(min_length=1, max_length=1000)


# ── the annual xlsx import (V1-20) ──────────────────────────────────────────
class ObservanceImportRow(BaseModel):
    """One spreadsheet row, resolved to what would be stored.

    Carries its own `problems`, and broken rows are returned rather than
    dropped: an importer that silently discards what it cannot read reports
    "142 imported" over a file of 150 and nobody ever finds the eight. For a
    calendar each missing row is a day the school stays open for.
    """
    index: int
    name: str
    key: str
    date: date_ | None = None
    end_date: date_ | None = None
    kind: str = "festival"
    tier: str = "major"
    states: list[str] | None = None
    tradition: str | None = None
    prep_days: int = 7
    note: str | None = None
    source: str = ""
    problems: list[str] = []
    importable: bool = True


class ObservanceImportPreview(BaseModel):
    columns: list[str] = []
    mapping: dict[str, str] = {}
    unmapped_columns: list[str] = []
    missing_required: list[str] = []
    # Fields the keyword heuristic could not place and the model proposed —
    # always worth the operator's glance before saving (`ingest.py`).
    low_confidence: list[str] = []
    source: str = "heuristic"   # heuristic | ai — how the mapping was reached
    rows: list[ObservanceImportRow] = []
    ready: int = 0
    blocked: int = 0


class ObservanceImportCommitIn(BaseModel):
    mapping: dict[str, str]
    rows: list[dict] = Field(min_length=1, max_length=4000)
    source: str = Field(min_length=1, max_length=200)
    # A sheet whose title carries the year and whose rows say only "15 August".
    year_hint: int | None = Field(default=None, ge=2000, le=2100)


class ObservanceImportCommitOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: list[str] = []
    duplicates: list[str] = []
    unresolved_states: list[str] = []


# ── the school-side read of the catalogue (V1-20) ───────────────────────────
class CatalogueRow(BaseModel):
    """A catalogue entry as a school sees it in the browser.

    Deliberately NOT `ObservanceOut`: that carries `decided_count` (how many
    OTHER schools acted on this row), which is platform telemetry and none of a
    school's business. What a school gets instead is `decided`/`approved` —
    what **it** did about this row.
    """
    id: uuid.UUID
    key: str
    name: str
    date: date_
    end_date: date_ | None = None
    kind: str
    tier: str
    states: list[str] | None = None
    tradition: str | None = None
    source: str
    note: str | None = None
    applies_here: bool = False   # matches this school's own state
    decided: bool = False
    approved: bool = False


class CatalogueBrowse(BaseModel):
    """The "Show events" table. `states` is the dropdown's options, served with
    the rows so the filter can never offer a state the corpus cannot answer."""
    org_state: str | None = None
    filter_state: str | None = None
    years: list[int] = []
    states: list[str] = []
    rows: list[CatalogueRow] = []
    total: int = 0


class ObservanceBulkOut(BaseModel):
    created: int = 0
    updated: int = 0
    # V1-19 — state names the import could not resolve to a canonical token,
    # de-duplicated. Reported, never silently dropped: an unresolvable state is
    # the one failure here with no symptom (the row imports fine and then
    # matches no school forever), so the importer has to say it out loud. Same
    # rule as the syllabus importer's `unresolved` (V2-P11).
    unresolved_states: list[str] = []
