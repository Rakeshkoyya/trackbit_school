"""Timetable schemas (V2-M3 §5.3; typed slots and the bell schedule, TT-2)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.core.day_shape import BLOCK_KINDS, DEFAULT_BLOCK_KIND, SLOT_TYPES

_SLOT_TYPE = f"^({'|'.join(SLOT_TYPES)})$"
_BLOCK_KIND = f"^({'|'.join(BLOCK_KINDS)})$"


# ── the bell schedule (one row of the school day) ────────────────────────────
class PeriodTime(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")  # "09:00"
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    # "period" is teachable time and takes a number; anything else is a break and
    # takes none. The kind name is still meaningful — V1-3's twice_daily mode
    # finds the after-lunch marking slot by looking for "lunch" in it — so free
    # text is allowed through rather than pinned to an enum.
    kind: str = Field(default="period", pattern="^[a-z][a-z_ ]{0,23}$")
    # TT-2: what to call it on screen. "Short break" reads better than "Break",
    # and a school with three breaks needs to tell them apart.
    label: str | None = Field(default=None, max_length=40)


class BellScheduleOut(BaseModel):
    academic_year_id: uuid.UUID
    #: None when the school has no schedule row yet and we are reading the
    #: pre-TT-2 columns off the year.
    id: uuid.UUID | None = None
    periods_per_day: int
    entries: list[PeriodTime] = Field(default_factory=list)
    note: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    #: False when the periods are numbered but have no clock — the screens that
    #: draw a time column need to know not to draw an empty one.
    has_timings: bool = False


class BellScheduleIn(BaseModel):
    academic_year_id: uuid.UUID
    entries: list[PeriodTime] = Field(max_length=24)
    #: Defaults to today (org tz). A mid-year restructure closes the running
    #: schedule at this date and opens the new one, so last term still renders
    #: with last term's clock.
    effective_from: date | None = None
    note: str | None = Field(default=None, max_length=200)


class BellHistoryOut(BaseModel):
    academic_year_id: uuid.UUID
    schedules: list[BellScheduleOut] = Field(default_factory=list)


# ── legacy period config (kept: nine test fixtures and the plan page use it) ──
class PeriodConfigOut(BaseModel):
    academic_year_id: uuid.UUID
    periods_per_day: int
    period_times: list[PeriodTime]


class PeriodConfigIn(BaseModel):
    academic_year_id: uuid.UUID
    periods_per_day: int = Field(ge=1, le=16)
    period_times: list[PeriodTime] = Field(default_factory=list)


# ── blocks (a non-subject period — see core/day_shape) ───────────────────────
class BlockOut(BaseModel):
    """A `Session` as the timetable sees it."""

    id: uuid.UUID
    name: str
    kind: str = DEFAULT_BLOCK_KIND
    kind_label: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    active: bool = True
    owner_member_id: uuid.UUID | None = None
    staff_member_ids: list[uuid.UUID] = Field(default_factory=list)
    staff_names: list[str] = Field(default_factory=list)
    class_ids: list[uuid.UUID] = Field(default_factory=list)
    roster_count: int = 0
    #: How many live grid cells point at it. A block on the timetable takes its
    #: schedule from the grid (`D-113`), so the hostel planner must not offer to
    #: edit its weekdays and times.
    slot_count: int = 0


class BlockIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default=DEFAULT_BLOCK_KIND, pattern=_BLOCK_KIND)
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    # Everyone who may run it. Empty = just the owner. Assembly and yoga are
    # taken by whoever is free, which is the whole reason this is a list.
    staff_member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    class_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    owner_member_id: uuid.UUID | None = None


class BlockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = Field(default=None, pattern=_BLOCK_KIND)
    category_id: uuid.UUID | None = None
    staff_member_ids: list[uuid.UUID] | None = Field(default=None, max_length=30)
    class_ids: list[uuid.UUID] | None = Field(default=None, max_length=30)
    owner_member_id: uuid.UUID | None = None
    active: bool | None = None


# ── grid ─────────────────────────────────────────────────────────────────────
class SlotOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    weekday: int
    period_no: int
    slot_type: str = "subject"
    # subject payload
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    teacher_member_id: uuid.UUID | None = None
    teacher_name: str | None = None
    # block payload
    session_id: uuid.UUID | None = None
    block_name: str | None = None
    block_kind: str | None = None
    block_kind_label: str | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    staff_member_ids: list[uuid.UUID] = Field(default_factory=list)
    staff_names: list[str] = Field(default_factory=list)
    # TT-4: this cell is one class's share of a combined meeting.
    combined_id: uuid.UUID | None = None
    #: The OTHER classes sitting in the same lesson — what the grid chip says.
    combined_with: list[str] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None


class Clash(BaseModel):
    """A teacher double-booked at one weekday+period across classes.

    TT-4: `combinable` is the difference between a mistake and an arrangement the
    grid has no words for yet. When every class in the clash runs a subject and
    they share one teacher, the honest fix is usually not to move a period — it
    is to say these classes sit together. The banner offers exactly that, and
    `class_ids` is what it posts.
    """

    weekday: int
    period_no: int
    teacher_member_id: uuid.UUID
    teacher_name: str | None = None
    class_labels: list[str]
    class_ids: list[uuid.UUID] = Field(default_factory=list)
    combinable: bool = False


class GridPeriod(BaseModel):
    """One numbered row of the grid, with the clock beside it."""

    period_no: int
    start: str = ""
    end: str = ""


class GridBreak(BaseModel):
    after_period_no: int
    label: str
    start: str = ""
    end: str = ""


class GridOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    weekdays: list[int]
    periods_per_day: int
    slots: list[SlotOut]
    clashes: list[Clash] = Field(default_factory=list)
    # TT-2: the grid draws the day's real clock down its left edge, so the admin
    # sees "P9 · 15:30" rather than being asked to remember what period 9 is.
    periods: list[GridPeriod] = Field(default_factory=list)
    breaks: list[GridBreak] = Field(default_factory=list)
    has_timings: bool = False


class SlotIn(BaseModel):
    class_id: uuid.UUID
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    slot_type: str = Field(default="subject", pattern=_SLOT_TYPE)
    # Exactly one of these, matching slot_type. The service enforces it before
    # the DB CHECK does, so the admin gets a sentence rather than a 500.
    class_subject_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    # Defaults to today (org tz) in the service. A mid-year edit closes the old
    # row at this date and opens the new one.
    effective_from: date | None = None


class SlotClearIn(BaseModel):
    class_id: uuid.UUID
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    effective_from: date | None = None


class SlotBulkIn(BaseModel):
    """Apply one block to many classes at once.

    The admin's real sentence is "assembly, period 1, every class, Mon–Sat" —
    twenty-four taps as single-cell edits, one as this.
    """

    class_ids: list[uuid.UUID] = Field(min_length=1, max_length=60)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    period_no: int = Field(ge=1, le=16)
    slot_type: str = Field(default="block", pattern=_SLOT_TYPE)
    class_subject_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    effective_from: date | None = None


class SlotBulkOut(BaseModel):
    written: int
    skipped: list[str] = Field(default_factory=list)


# ── combined periods (TT-4) ──────────────────────────────────────────────────
class CombineIn(BaseModel):
    """"These classes sit together in this period."

    Named by the CELL (weekday + period) and the classes in it, never by slot
    ids: the admin is pointing at a column of the grid, and slot ids change every
    time a cell is edited.
    """

    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    class_ids: list[uuid.UUID] = Field(min_length=2, max_length=12)
    note: str | None = Field(default=None, max_length=200)
    effective_from: date | None = None


class UncombineIn(BaseModel):
    """Split a combined meeting back into separate lessons.

    One class id splits just that class out; none splits the whole thing.
    """

    combined_id: uuid.UUID
    class_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)
    effective_from: date | None = None


class CombinedClassOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    class_subject_id: uuid.UUID | None = None
    subject_name: str | None = None


class CombinedOut(BaseModel):
    """One combined meeting as every screen reads it.

    Weekday, period and members are all resolved from the live slots — nothing
    here is stored twice.
    """

    id: uuid.UUID
    weekday: int
    period_no: int
    note: str | None = None
    teacher_member_id: uuid.UUID | None = None
    teacher_name: str | None = None
    classes: list[CombinedClassOut] = Field(default_factory=list)
    label: str = ""


# ── teacher views ────────────────────────────────────────────────────────────
class TeacherSlot(BaseModel):
    """One thing this teacher is doing at one weekday+period.

    TT-4: **one row per MEETING, not per class.** A combined lesson and a block
    placed on twenty classes are each one place the teacher stands, so they
    collapse to a single row here — `class_id`/`class_label` name the one the
    screens key off, and `class_ids`/`class_labels` carry the whole room. Before
    this, a Monday assembly drew twenty identical rows on the admin's week and a
    combined Maths drew two, which is not what a day looks like.
    """

    weekday: int
    period_no: int
    class_id: uuid.UUID
    class_label: str
    slot_type: str = "subject"
    subject_name: str | None = None
    class_subject_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    block_name: str | None = None
    block_kind: str | None = None
    start: str = ""
    end: str = ""
    #: Every class in this meeting, `class_id` first. Length 1 for an ordinary
    #: period — so a caller can always read this one field and be right.
    class_ids: list[uuid.UUID] = Field(default_factory=list)
    class_labels: list[str] = Field(default_factory=list)
    #: Set only when this is a combined SUBJECT meeting (TT-4).
    combined_id: uuid.UUID | None = None


class TeacherWeekOut(BaseModel):
    member_id: uuid.UUID
    weekdays: list[int]
    periods_per_day: int
    slots: list[TeacherSlot]
    periods: list[GridPeriod] = Field(default_factory=list)


# ── import (photo/xlsx → parse → confirm) ─────────────────────────────────────
class ImportCell(BaseModel):
    weekday: int
    period_no: int
    class_subject_id: uuid.UUID | None = None
    subject_name: str
    confidence: float = 1.0


class ImportAnalyzeOut(BaseModel):
    class_id: uuid.UUID
    source: str  # "ai" | "fixture"
    cells: list[ImportCell]
    unmatched: list[str] = Field(default_factory=list)


class ImportCommitCell(BaseModel):
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    class_subject_id: uuid.UUID


class ImportCommitIn(BaseModel):
    class_id: uuid.UUID
    effective_from: date | None = None
    cells: list[ImportCommitCell]


# ── whole-school generation (deterministic — no AI, no flag) ─────────────────
class OrgGenerateIn(BaseModel):
    academic_year_id: uuid.UUID
    effective_from: date | None = None
    # False = preview only. True = replace the live grid of every class in the
    # year with the generated one (append-only: old slots are closed, not deleted).
    apply: bool = False


class OrgDraftCell(BaseModel):
    class_id: uuid.UUID
    class_label: str
    weekday: int
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str


class OrgDraftIssue(BaseModel):
    class_label: str
    subject_name: str
    detail: str


class OrgGenerateOut(BaseModel):
    academic_year_id: uuid.UUID
    classes: int
    cells: list[OrgDraftCell]
    # Demand that could not be placed (teacher already busy / week full) — the
    # generator reports, never squeezes (§5.2 spirit).
    unplaced: list[OrgDraftIssue] = Field(default_factory=list)
    # Subjects skipped because periods_per_week is 0.
    skipped: list[OrgDraftIssue] = Field(default_factory=list)
    applied: bool = False


# ── assisted draft (flag-gated) ──────────────────────────────────────────────
class DraftOut(BaseModel):
    class_id: uuid.UUID
    enabled: bool
    cells: list[ImportCell] = Field(default_factory=list)
    clashes: list[Clash] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    message: str
