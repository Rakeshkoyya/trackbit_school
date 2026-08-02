"""The support programme's payloads (V1-9).

Every shape here obeys the same two rules the module lives by:

* **A letter never travels without its sentence** (`S-166`) — the descriptor
  rides along on every surface that renders a tier, because a bare letter is the
  label P4 exists to prevent.
* **Not assessed is a word** — `tier: None` is a real, renderable state, never a
  C and never a zero (ux §5).

And one that never changes: **none of this reaches a parent** (P4). These
schemas serve staff surfaces only.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

Date = date


# ── setup: monitored subjects + descriptors (D-68 / D-69 / D-74) ─────────────
class BandDescriptorOut(BaseModel):
    id: uuid.UUID | None = None
    subject_id: uuid.UUID
    subject_name: str
    tier: str
    text: str
    # The subject's own threshold. None on C — C is "below B" (`D-74`).
    min_pct: int | None = None


class BandSubjectSetup(BaseModel):
    subject_id: uuid.UUID
    subject_name: str
    monitored: bool
    descriptors: list[BandDescriptorOut] = []


class MonitoredIn(BaseModel):
    subject_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class DescriptorUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=400)
    min_pct: int | None = Field(default=None, ge=0, le=100)


# ── assess a class, for one subject (D-70 / Q-79) ────────────────────────────
class AssessRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    current_tier: str | None = None
    # From the chosen test, where there is one. None = did not sit it.
    pct: float | None = None
    suggested_tier: str | None = None


class BandClassBoard(BaseModel):
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    subject_name: str
    term_id: uuid.UUID | None = None
    a_min: int
    b_min: int
    cycle_id: uuid.UUID | None = None
    cycle_name: str | None = None
    # Opened beside the slider, not in a help menu (`S-166`).
    descriptors: list[BandDescriptorOut] = []
    rows: list[AssessRow] = []


class BandFileRow(BaseModel):
    student_id: uuid.UUID
    # None = not assessed. It is skipped, never written as a band.
    tier: str | None = Field(default=None, pattern="^(A|B|C)$")


class BandFileIn(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    term_id: uuid.UUID
    # `D-70`: both routes are first class, and the row records which one.
    source: str = Field(default="test", pattern="^(test|observation)$")
    cycle_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=200)
    rows: list[BandFileRow] = Field(default_factory=list, max_length=500)


# ── movement: promoting a test (D-76 / S-184 / Q-81) ─────────────────────────
class BandMoveRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    from_tier: str | None = None
    to_tier: str
    pct: float
    direction: str            # up | down | new


class BandPromotePreview(BaseModel):
    """The review step (`Q-81`) — shown **before** anything commits, because
    `student_bands` is append-only and a child slipping B → C is the most
    consequential thing this module does."""
    cycle_id: uuid.UUID
    name: str
    date: Date
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    total_marks: float | None = None
    locked: bool = False
    already_promoted: bool = False
    # Set = this test cannot be used, and why, in a sentence.
    blocked: str | None = None
    # `S-184`: warn, never block.
    warnings: list[str] = []
    roster: int = 0
    sat: int = 0
    not_sat: int = 0
    unchanged: int = 0
    moves: list[BandMoveRow] = []
    applied: int = 0
    descriptor: str | None = None


# ── the admin's programme board (D-73 / S-169 / S-188) ───────────────────────
class ProgrammeRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    # `S-188`: never a row about a child without the subject on it.
    subject_id: uuid.UUID
    subject_name: str
    since: Date | None = None
    owner_member_id: uuid.UUID | None = None
    owner_name: str | None = None
    intervention_id: uuid.UUID | None = None
    last_checkin: Date | None = None


class ProgrammeGridCell(BaseModel):
    class_id: uuid.UUID
    class_label: str | None = None
    subject_id: uuid.UUID
    subject_name: str
    c_count: int = 0
    moved_up: int = 0
    slipped: int = 0


class ProgrammeBoard(BaseModel):
    term_id: uuid.UUID | None = None
    term_name: str | None = None
    subjects: list[str] = []
    headline: str = ""
    moved_up: int = 0
    slipped: int = 0
    stuck: list[ProgrammeRow] = []
    grid: list[ProgrammeGridCell] = []
    # A word, never a zero and never red.
    not_assessed: list[str] = []


class AssignOwnerIn(BaseModel):
    student_id: uuid.UUID
    subject_id: uuid.UUID
    member_id: uuid.UUID | None = None    # None = the sensible default (S-168)
    term_id: uuid.UUID | None = None
    goal_text: str | None = Field(default=None, max_length=300)
    exit_criterion: str | None = Field(default=None, max_length=300)


# ── the owner's screens (D-87 / S-164 / S-165) ───────────────────────────────
class SupportDayRow(BaseModel):
    """One line of the pre-filled week — read from capture other teachers
    already did (`S-164`). Nothing here was typed twice."""
    date: Date
    kind: str        # absent | observation | homework | check | session
    text: str


class SupportStudentRow(BaseModel):
    intervention_id: uuid.UUID
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    tier: str | None = None
    since: Date | None = None
    checkins: int = 0
    last_checkin: Date | None = None
    weeks_since_checkin: int | None = None
    checked_in_this_week: bool = False
    ready_to_retest: bool = False
    status: str = "active"


class SupportList(BaseModel):
    as_of: Date
    week_start: Date
    headline: str = ""
    groups: list[dict] = []      # [{subject_name, rows: [...]}]
    moved_on: list[SupportStudentRow] = []


class CheckpointOut(BaseModel):
    id: uuid.UUID
    week_start: Date
    worked_on: str | None = None
    what_changed: str | None = None
    next_step: str | None = None
    ready_to_retest: bool = False
    author_name: str | None = None
    created_at: object


class CheckpointIn(BaseModel):
    worked_on: str | None = Field(default=None, max_length=400)
    what_changed: str | None = Field(default=None, max_length=400)
    next_step: str | None = Field(default=None, max_length=400)
    ready_to_retest: bool = False
    week_start: Date | None = None


class SupportChild(BaseModel):
    intervention_id: uuid.UUID
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    tier: str | None = None
    since: Date | None = None
    source: str | None = None
    owner_name: str | None = None
    goal_text: str = ""
    # `S-167`: on the screen from day one — a goal decided at the end is a
    # judgement, not a target.
    exit_criterion: str | None = None
    status: str = "active"
    headline: str = ""
    descriptors: list[BandDescriptorOut] = []
    week: list[SupportDayRow] = []
    week_start: Date | None = None
    checkpoints: list[CheckpointOut] = []
    # The evidence a "ready to re-test" claim rests on (`S-178`).
    latest_pct: float | None = None
    latest_test: str | None = None


class InterventionCloseIn(BaseModel):
    status: str = Field(pattern="^(achieved|dropped)$")
    outcome_note: str | None = Field(default=None, max_length=300)
