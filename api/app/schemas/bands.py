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


# ── who may band what (founder 2026-08-04) ───────────────────────────────────
class BandScopeClass(BaseModel):
    class_id: uuid.UUID
    class_label: str
    # The monitored subjects this member takes in this class — the class × subject
    # tab rows the manage screen is built from.
    subjects: list[dict] = []


class BandScopeOut(BaseModel):
    """What this member may do in the programme, and therefore whether the ABC
    Bands nav item exists for them at all.

    A teacher who takes none of the monitored subjects gets `has_scope=False` and
    no nav item — an area that opens on "nothing here for you" is worse than one
    that was never offered (ux §13)."""
    # Any subject monitored in the school at all.
    enabled: bool = False
    # This member gets the area at all — `can_band` or `owns_students`.
    has_scope: bool = False
    # This member has at least one monitored class-subject, so the class-banding
    # tabs mean something for them.
    can_band: bool = False
    # Founder 2026-08-05: they own at least one active support plan. Kept apart
    # from `can_band` because they answer different questions — an owner who
    # teaches none of the monitored subjects still needs My students, and would
    # read an empty Manage-bands screen as a broken one.
    owns_students: bool = False
    is_admin: bool = False
    classes: list[BandScopeClass] = []
    subjects: list[dict] = []


# ── the distribution board (founder 2026-08-04) ──────────────────────────────
# `S-169` rejected the distribution as the admin's HEADLINE, and that still
# holds: `BandDistribution.headline` is the movement sentence, and these counts
# render underneath it. What the founder asked for is the shape of the school —
# which class is carrying the support load, and which subject — and that is a
# question movement cannot answer.
#
# The unit is deliberate. `D-75` retired the overall letter, so a *student*
# cannot be counted into one tier at school or class level: a child who is A in
# Maths and C in Hindi belongs to both. The unit here is therefore the
# **placement** (one child in one subject), and `caption` says so on every
# surface that renders it. Per subject the unit collapses back to children,
# because inside one subject a child holds exactly one band.
class BandScopeRow(BaseModel):
    """One class, or one subject, tallied A/B/C."""
    key: str
    label: str
    a: int = 0
    b: int = 0
    c: int = 0
    # a + b + c. The denominator every percentage on this row is taken over.
    assessed: int = 0
    # How many placements COULD exist here — roster × the monitored subjects
    # actually taught. `eligible - assessed` is the gap in the record, and it is
    # reported as its own number rather than folded into C (ux §5).
    eligible: int = 0
    a_pct: float = 0.0
    b_pct: float = 0.0
    c_pct: float = 0.0
    not_assessed: int = 0
    # Children, not placements — the honest count for a subject row, and useful
    # context on a class row.
    students: int = 0


class BandDistribution(BaseModel):
    term_id: uuid.UUID | None = None
    term_name: str | None = None
    subjects: list[str] = []
    # `S-169`: movement leads, the distribution explains. This is the same
    # sentence `ProgrammeBoard.headline` carries, from the same computation —
    # the two boards can never describe the same term differently.
    headline: str = ""
    moved_up: int = 0
    slipped: int = 0
    school: BandScopeRow = Field(default_factory=lambda: BandScopeRow(key="school", label="School"))
    # "418 placements across 3 subjects · 142 children assessed of 156"
    caption: str = ""
    by_class: list[BandScopeRow] = []
    by_subject: list[BandScopeRow] = []


# ── teacher allocation (D-71 / D-77 / S-168) ─────────────────────────────────
class AllocationRow(BaseModel):
    """One C-band placement and the teacher who owns moving it to B.

    `S-188`: never a row about a child without the subject on it — with one
    owner per subject (`D-77`), "Kabir Shah — owner Priya" is ambiguous until
    you know whether that is Priya-for-Hindi or Priya-for-Maths."""
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID
    subject_name: str
    tier: str = "C"
    since: Date | None = None
    owner_member_id: uuid.UUID | None = None
    owner_name: str | None = None
    intervention_id: uuid.UUID | None = None
    last_checkin: Date | None = None
    checkins: int = 0
    status: str = "active"


class AllocationBoard(BaseModel):
    term_id: uuid.UUID | None = None
    term_name: str | None = None
    headline: str = ""
    rows: list[AllocationRow] = []
    assigned: int = 0
    unassigned: int = 0
    # The filter vocabulary, so the screen never has to guess what exists.
    classes: list[dict] = []
    subjects: list[dict] = []


class OwnerSuggestion(BaseModel):
    """A teacher who could own this child, and **why** — never a ranking.

    `S-170` is a fence: teachers are not scored by children moved, so `load` is
    here as *capacity* (how many they already carry), never as performance. The
    list is not filtered to the suggested set — the founder's call: suggest the
    class's own teachers first, allow anyone."""
    member_id: uuid.UUID
    name: str
    # `suggested` = one of the teachers already in front of this child.
    suggested: bool = False
    reason: str = ""
    # Support children this member already owns, across every subject.
    load: int = 0
    # True when this member already owns THIS child in THIS subject.
    current: bool = False


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
    # The (class, subject) this child sits in — what an assignment given from
    # this page has to be filed against. Per-student homework already exists
    # (`homework_assignments.student_id`, V2-P3) and the support programme
    # deliberately reuses it rather than growing a second "did he do the work"
    # store, which would be `S-51` for the seventh time.
    class_subject_id: uuid.UUID | None = None
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


class SupportSummary(BaseModel):
    """The written summary and key insights for one support child.

    `source` is `ai` only when a model actually answered — with no key, a
    timeout or bad JSON it is `computed` and the deterministic sentences are
    what render. The page is never blank, and the reader can always tell which
    they are looking at."""
    source: str = "computed"
    summary: str = ""
    insights: list[str] = []
    # What the summary was written from, so a reader can check it rather than
    # trust it — and so an empty summary is explicable rather than mysterious.
    based_on: list[str] = []


class InterventionCloseIn(BaseModel):
    status: str = Field(pattern="^(achieved|dropped)$")
    outcome_note: str | None = Field(default=None, max_length=300)


# ── the owner's own assessments (founder 2026-08-05) ─────────────────────────
# Not `assessment_cycles`. That table is the school's academic record and moves
# a child's band (`D-76`); this is a support owner's own small check on the
# children she owns, and its figures never leave the programme. The vocabulary
# and every average live in `core/band_assessment.py`.
class MyStudentRow(BaseModel):
    """One child she owns — the row My students renders.

    It carries `intervention_id` because the child page is keyed on the support
    plan, not the student: a child who is C in Hindi and C in Maths is two rows
    on two teachers' lists, and collapsing him to one would reinstate the
    overall letter `D-75` retired."""
    intervention_id: uuid.UUID
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    tier: str | None = None
    # `S-166`: the letter never travels without its sentence.
    descriptor: str | None = None
    since: Date | None = None
    checkins: int = 0
    last_checkin: Date | None = None
    weeks_since_checkin: int | None = None
    checked_in_this_week: bool = False
    ready_to_retest: bool = False
    # Per-student homework given to him and not yet checked by anyone. The
    # teacher's gap, counted as the teacher's gap — never his miss (HW-1).
    open_assignments: int = 0
    notes: int = 0
    status: str = "active"


class MyStudentsBoard(BaseModel):
    """`headline` states the record, never grades her (`S-170`).

    `classes` is the picker's vocabulary, so the screen never guesses what
    exists — and `total` is the unfiltered count, so a class filter that empties
    the table can be told apart from having no children at all."""
    headline: str = ""
    as_of: Date
    week_start: Date
    class_id: uuid.UUID | None = None
    classes: list[dict] = []
    rows: list[MyStudentRow] = []
    total: int = 0
    moved_on: list[MyStudentRow] = []


class AssessmentResultRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    class_label: str | None = None
    tier: str | None = None
    marks: float | None = None
    rating: int | None = None
    verdict: str | None = None
    note: str | None = None
    # `core/band_assessment.py::result_text` — the figure WITH its denominator.
    # None is a real state and every surface renders it as a word.
    result_text: str | None = None
    evaluated: bool = False
    # His running log, so the sheet can say whether anyone has written about him
    # without a second round trip per child.
    notes: int = 0


class BandAssessmentRow(BaseModel):
    id: uuid.UUID
    name: str
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    instructions: str | None = None
    description: str | None = None
    metric: str = "marks"
    max_marks: float | None = None
    rating_max: int | None = None
    covers_all: bool = True
    given_on: Date
    due_date: Date | None = None
    author_name: str | None = None
    # pending | partial | evaluated — `pending` is a state, never an empty score.
    status: str = "pending"
    roster: int = 0
    evaluated: int = 0
    not_evaluated: int = 0
    average: float | None = None
    average_pct: float | None = None
    # The figure with its denominator, in this metric's own words.
    caption: str = ""


class BandAssessmentList(BaseModel):
    """Paginated on purpose (founder): a year of small weekly checks is
    hundreds of rows, and a screen that loads all of them stops opening.

    Grouped by class in the rendering, so `rows` arrives sorted by class then
    newest-first and a page never interleaves two classes at random."""
    headline: str = ""
    rows: list[BandAssessmentRow] = []
    page: int = 1
    per_page: int = 20
    total: int = 0
    pages: int = 1
    classes: list[dict] = []
    open_count: int = 0


class BandAssessmentCreate(BaseModel):
    class_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    subject_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    metric: str = Field(default="marks", pattern="^(marks|rating|other)$")
    max_marks: float | None = Field(default=None, gt=0, le=1000)
    rating_max: int | None = Field(default=None, ge=2, le=10)
    given_on: Date | None = None
    due_date: Date | None = None
    # True = every support child she owns in this class, and the roster stays
    # computed so a child assigned next week is on it (HS-1). False = the
    # explicit ids below — the founder's "or a single student".
    covers_all: bool = True
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class BandAssessmentSheet(BaseModel):
    """The evaluation surface: the assessment, its roster, and what is recorded.

    Deliberately NOT capture-by-exception. P1v2's budget rule is about *daily*
    capture across a whole class; this is a handful of support children and the
    number for each one IS the point — the same reasoning that lets
    `file_bands` touch every row of a class."""
    assessment: BandAssessmentRow
    rows: list[AssessmentResultRow] = []
    can_record: bool = False


class AssessmentResultIn(BaseModel):
    student_id: uuid.UUID
    marks: float | None = Field(default=None, ge=0, le=1000)
    rating: int | None = Field(default=None, ge=0, le=10)
    verdict: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class AssessmentRecordIn(BaseModel):
    """Full replace, like `check_homework` and `mark`. Results are capture, and
    law 3's append-only governs decisions — a mistyped 7 for 17 is corrected in
    place, exactly as a mis-tapped absence is. A row omitted here is **cleared
    back to not-evaluated**, which is a legitimate answer."""
    results: list[AssessmentResultIn] = Field(default_factory=list, max_length=200)
