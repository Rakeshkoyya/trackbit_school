"""The collection board's payloads (V1-10).

Two rules show up in the shapes themselves:

* **`collected` / `pending` / `overdue` are three fields, never one.** There is
  no `outstanding` anywhere in this file (`S-163`) — pending is a forecast,
  overdue is a phone call.
* **Every class row carries both denominators** (`S-159`): ₹1.4L is one big
  defaulter or fourteen small ones, and those need opposite actions.

And the fence: nothing here is ever served to a teacher except
`FeeFollowupDetail`, which is one student, inside one assigned task (`D-83`).
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

Date = date


class YearCollection(BaseModel):
    """The whole academic year, on one track.

    Nothing exposed this before: `CollectionBoard`'s top-level figures are the
    PICKED quarter's, so "how is the year going" could only be got by summing
    quarter rows in a browser — which the dashboard did, adding pending to
    overdue on the way (the blend `Collection` has no `outstanding` property
    precisely to prevent).

    The three figures the board leads with are `billed`, `due_by_today` and
    `collected`, and they share one denominator, which is why they are drawn as
    one arc against one marker rather than as three rings.
    """
    billed: float = 0            # everything asked for across the year
    due_by_today: float = 0      # of that, what the schedule has already asked for
    collected: float = 0         # of that, what is in
    pending: float = 0
    overdue: float = 0
    pct: float | None = None     # collected / billed
    due_pct: float | None = None # due_by_today / billed — the marker's position
    shortfall: float = 0         # max(0, due_by_today - collected)
    tone: str = "neutral"


class QuarterRow(BaseModel):
    label: str
    start: Date
    end: Date
    billed: float = 0
    collected: float = 0
    pending: float = 0
    overdue: float = 0
    # None when nothing was billed in the window — a quarter with no instalments
    # is **not** 0% collected.
    pct: float | None = None
    # The same pace pair as the year, at quarter scale: one ring per quarter,
    # each on its own denominator, each carrying its own marker.
    due_by_today: float = 0
    due_pct: float | None = None
    shortfall: float = 0
    # Decided server-side. A quarter with nothing due yet is `neutral` and says
    # so in a word — it has not been missed, and painting next January red every
    # August is how a board stops being read.
    tone: str = "neutral"
    # past | current | future — so a renderer never has to compare dates itself
    # and reach a different answer in another timezone.
    state: str = "current"


class ClassCollectionRow(BaseModel):
    class_id: uuid.UUID | None = None
    class_label: str
    # `S-159`: both denominators, always. Sorted by families, because a morning
    # of phone calls is denominated in calls, not rupees.
    families_pending: int = 0
    families_total: int = 0
    billed: float = 0
    collected: float = 0
    pending: float = 0
    overdue: float = 0
    pct: float | None = None


class CollectionPoint(BaseModel):
    day: Date
    collected: float
    # The same day-of-quarter in the previous quarter — the reference line.
    previous: float | None = None


class DefaulterRow(BaseModel):
    """`S-157`: names the **family** beside the child, because the person who
    owes is the person you ring. A full concession never appears here — the list
    is built from what is owed, not from enrolment."""
    student_fee_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_label: str | None = None
    overdue_amount: float
    earliest_due_date: Date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    # `Q-70`: the message goes to the primary only; these ride along so the
    # admin can ring them by hand.
    other_guardians: list[dict] = []
    # ux §7 — the row remembers what already fired, so nobody is chased twice.
    reminded_on: Date | None = None
    assigned_on: Date | None = None
    # `S-161`: what the family SAID, not that a button was pressed.
    last_said: str | None = None
    last_said_on: Date | None = None


class CollectionBoard(BaseModel):
    as_of: Date
    academic_year_id: uuid.UUID | None = None
    academic_year_label: str | None = None
    quarter: str | None = None
    headline: str = ""
    billed: float = 0
    collected: float = 0
    pending: float = 0
    overdue: float = 0
    pct: float | None = None
    # The whole year, beside the picked quarter. Accumulated in the same pass,
    # so the year ring and the quarter rings cannot disagree.
    year: YearCollection = YearCollection()
    quarters: list[QuarterRow] = []
    curve: list[CollectionPoint] = []
    by_class: list[ClassCollectionRow] = []
    defaulters: list[DefaulterRow] = []
    # An instalment with no due date is in no quarter — a word, never silently
    # bucketed into Q1 (ux §10).
    unscheduled_billed: float = 0
    unscheduled_note: str | None = None
    # `D-88`: dues from a previous year, as their own labelled line. Never in the
    # figures above, and never silently omitted either.
    carried: dict | None = None


# ── the conversation history (D-84) ──────────────────────────────────────────
class FeeNoteOut(BaseModel):
    id: uuid.UUID
    kind: str
    said: str | None = None
    promised_date: Date | None = None
    author_name: str | None = None
    created_at: object


class FeeNoteIn(BaseModel):
    kind: str = Field(default="call", pattern="^(call|visit|message|reminder|assigned|note)$")
    said: str | None = Field(default=None, max_length=600)
    promised_date: Date | None = None


class RemindOut(BaseModel):
    sent: int = 0
    # nothing_due | already_reminded | quiet_hours | no_number | opted_out
    skipped: str | None = None
    message: str = ""


class AssignFollowupIn(BaseModel):
    member_id: uuid.UUID
    board_id: uuid.UUID | None = None


class AssignFollowupOut(BaseModel):
    # Returned so the board can link straight to the task it just made — and so
    # the teacher's fee detail has an id to hang off (`D-83`).
    task_id: uuid.UUID
    message: str = ""


class FeeFollowupDetail(BaseModel):
    """`D-83` — the **one** fee payload a teacher may ever receive: this student,
    inside this task. No class list, no collection figure, no other family."""
    task_id: uuid.UUID
    student_id: uuid.UUID
    student_fee_id: uuid.UUID
    student_name: str
    class_label: str | None = None
    pending_amount: float = 0
    due_date: Date | None = None
    paid_so_far: float = 0
    total_fee: float = 0
    guardian_name: str | None = None
    guardian_phone: str | None = None
    notes: list[FeeNoteOut] = []
