"""Parent portal schemas — the ONLY shapes that reach a guardian.

P4 is enforced here by construction: no band, no band_history, no skills, no
raw observations, no check-flag counts anywhere in this module. The projection
service builds these from staff payloads; tests assert the fields never leak.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.growth import GrowthAttendance, GrowthChapter


class RequestOtpIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class RequestOtpOut(BaseModel):
    message: str
    channel: str  # whatsapp | sms | stub
    debug_code: str | None = None  # OTP_ECHO_IN_RESPONSE dev convenience only


class VerifyOtpIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class SetCredentialsIn(BaseModel):
    username: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)


# ── D-13 · the login, one step per screen ───────────────────────────────────
class SchoolCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class ParentClassOut(BaseModel):
    class_id: uuid.UUID
    name: str
    section: str | None = None
    label: str | None = None


class SchoolLookupOut(BaseModel):
    """Step 1's answer. Deliberately thin: the school's name so the parent knows
    they typed the right code, its phone so a stuck parent has somewhere to go,
    and the class list. Nothing about the school's size, its staff or its year."""

    org_id: uuid.UUID
    school_name: str
    school_phone: str | None = None
    classes: list[ParentClassOut] = []


class FindChildIn(BaseModel):
    org_id: uuid.UUID
    class_id: uuid.UUID
    # `S-55`: the minimum is enforced in the service (one config, one message),
    # not duplicated as a validator here.
    query: str = Field(max_length=60)


class ParentChildMatch(BaseModel):
    """A search hit, before any credential is entered. The name and nothing
    else — no admission number, no class teacher, no date of birth hint."""

    student_id: uuid.UUID
    full_name: str


class VerifyDobIn(BaseModel):
    student_id: uuid.UUID
    date_of_birth: date


class AddChildOut(BaseModel):
    student_id: uuid.UUID
    full_name: str


# ── D-08/D-14 · the notifications archive ───────────────────────────────────
class ParentNotification(BaseModel):
    """One message the school sent this family.

    `S-61`: the Today tab is the delivery surface and this is the archive, so a
    parent who opens the app once a day has already seen everything and never
    has to check two places. `delivered` is shown to nobody — it exists so the
    school can tell whether its own alert arrived (`S-62`)."""

    id: uuid.UUID
    kind: str
    title: str
    body: str
    url: str | None = None
    student_id: uuid.UUID
    student_name: str
    created_at: datetime
    read: bool = False


class ParentNotificationsOut(BaseModel):
    items: list[ParentNotification] = []
    unread: int = 0


# ── Q-56 · the school calendar, read-only ───────────────────────────────────
class ParentCalendarItem(BaseModel):
    """*"Is school open on Monday?"* — the most-asked question in a school
    office, answered from rows the school already maintains.

    `closed` is the answer; `title` is the reason. A birthday item is only ever
    this family's own child (a list of classmates' birthdays is a roster leak
    wearing a party hat)."""

    date: date
    end_date: date | None = None
    title: str
    kind: str          # holiday | exam_block | celebration | event | birthday
    closed: bool = False
    detail: str | None = None


class ParentCalendarOut(BaseModel):
    items: list[ParentCalendarItem] = []


class ParentChildOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    admission_no: str


class ParentMeOut(BaseModel):
    name: str
    phone: str | None = None
    username: str | None = None
    email: str | None = None
    has_password: bool = False
    org_name: str
    children: list[ParentChildOut] = []


class ParentTaughtItem(BaseModel):
    subject_name: str
    topic: str


class ParentHomeworkItem(BaseModel):
    subject_name: str
    text: str
    # done | late | partial | not_done | carried | waived | not_checked.
    # `not_checked` means the teacher hasn't gone through it — the UI must say
    # "not checked yet", never imply the child missed it. `carried` (D-35) is
    # work missed because the child was ABSENT: shown **yellow**, pending, never
    # red — nothing was refused.
    status: str = "not_checked"
    due_date: date | None = None
    personal: bool = False


class ParentHomeworkDay(BaseModel):
    """A day's homework for one child, with the day's verdict rolled up."""
    date: date
    items: list[ParentHomeworkItem] = []
    done: int = 0
    not_done: int = 0
    partial: int = 0
    late: int = 0
    carried: int = 0
    not_checked: int = 0


class ParentSessionItem(BaseModel):
    session_name: str
    kind: str
    status: str  # present | late | absent
    homework_done: bool | None = None
    log_note: str | None = None


class ParentMonthDay(BaseModel):
    """One school day of the month strip (V1-3, S-11) — a DAILY status only,
    never per-period detail. `not_marked` renders neutral, never as absence."""

    date: date
    # present | partial | absent | left_after_lunch | not_marked
    status: str


class ParentTodayOut(BaseModel):
    date: date
    # no_school | not_marked | present | partial | absent | left_after_lunch
    status: str
    marked_periods: int = 0
    absent_periods: int = 0
    late_periods: int = 0
    # V1-3 (S-11): the pattern — this month's school days and the sentence's
    # figures: "present 18 of 21 marked school days".
    month: list[ParentMonthDay] = []
    present_days: int = 0
    marked_days: int = 0
    # V1-3 (D-02/D-86): the reason the school recorded for TODAY's absence, if
    # any — plain text, never a band, never who recorded it.
    absence_reason: str | None = None
    # V1-3 (S-25): the school's number for the "tell the school why" tel: link.
    # Zero parent writes — the phone call is the write path (D-86).
    school_phone: str | None = None
    taught: list[ParentTaughtItem] = []
    homework: list[ParentHomeworkItem] = []
    sessions: list[ParentSessionItem] = []
    # Yesterday's homework, so the first question a parent asks — "did they do
    # it?" — is answered without navigating anywhere (HW-1).
    yesterday: ParentHomeworkDay | None = None
    # S-94 — two lists, because they are two different things and one of them
    # is not actionable. `pending` is work that can still be handed in: not yet
    # due, or CARRIED because the child was away (D-35 — yellow, never red).
    # `missed` is work whose deadline has passed and was not done: a fact, and
    # it carries **no red** either, because the child may well have finished it
    # since. Before this split, a missed item sat in "still to do" for eight
    # days looking like something that could still be handed in.
    pending: list[ParentHomeworkItem] = []
    missed: list[ParentHomeworkItem] = []
    # V1-10 (`D-66`/`Q-69`/`S-160`): the fee reminder — **one line**, and only
    # when something is actually due. Two questions, "how much" and "by when",
    # and both fit on it. Not a ledger: a fee tab invites "why was I charged
    # this", which is a counter conversation, not a screen. Neutral tone, never
    # red, never the word defaulter — it is read by a family that may be having
    # a hard year.
    fee: "ParentFeeLine | None" = None


class ParentFeeLine(BaseModel):
    """What a parent may see about money. Field by field, like everything in
    this projection — and deliberately no transaction history, no instalment
    list, no status word."""
    amount_due: float
    due_date: date | None = None
    paid_so_far: float = 0
    line: str = ""
    # The office's number, so "I need to discuss it" has somewhere to go. The
    # portal stays read-only (`D-86`): the phone call is the write path.
    school_phone: str | None = None


class ParentScore(BaseModel):
    """A mark, as a parent may see it — named field by field, deliberately.

    It does **not** reuse `GrowthScore`. V1-8 added `paper_url` (a link to the
    child's photographed script) to that staff schema, and because this
    projection referenced the type rather than the fields, the link would have
    reached the portal without anybody deciding it should. That is the exact
    accident PC-1's allowlist exists to prevent — *"a new staff field cannot
    reach a parent by accident"* — so the shape is spelled out here instead.

    `type_label` and `scale` ARE included, and deliberately: a parent reading
    one line through a 5-mark slip test and an 80-mark final is the same
    conflation `S-114` removed everywhere else."""

    cycle_name: str
    date: date
    score: float
    max_score: float
    type_label: str | None = None
    scale: str = "minor"


class ParentReportSubject(BaseModel):
    """Per-subject progress — the curated cut of GrowthSubject: coverage,
    attendance, homework counts and scores; never observations or check flags."""

    subject_name: str
    teacher_name: str | None = None
    attendance: GrowthAttendance
    chapters: list[GrowthChapter] = []
    homework_assigned: int = 0
    homework_personal: int = 0
    scores: list[ParentScore] = []

    # V1-6 — the coverage figure, computed server-side by `core.coverage` and
    # measured against the WHOLE syllabus (`S-54`, `Q-16`). Both parent pages
    # used to sum this in the browser, which is how the product ended up with
    # four different answers to "how much of the syllabus is covered".
    coverage_taught: float = 0
    coverage_total: int = 0
    coverage_pct: float | None = None
    # `S-48` — the chapter and topic most recently taught. Still no pace, no
    # lag, no RAG and no "missed": `D-11` is unchanged by this.
    latest_chapter: str | None = None
    latest_topic: str | None = None
    latest_taught_on: date | None = None


class ParentReportOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    attendance: GrowthAttendance
    subjects: list[ParentReportSubject] = []
    # Derived phrases (never tiers): the same curated lists staff see.
    strengths: list[str] = []
    growth_areas: list[str] = []
