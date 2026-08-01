"""Parent portal schemas — the ONLY shapes that reach a guardian.

P4 is enforced here by construction: no band, no band_history, no skills, no
raw observations, no check-flag counts anywhere in this module. The projection
service builds these from staff payloads; tests assert the fields never leak.
"""

import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.schemas.growth import GrowthAttendance, GrowthChapter, GrowthScore


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


class ParentReportSubject(BaseModel):
    """Per-subject progress — the curated cut of GrowthSubject: coverage,
    attendance, homework counts and scores; never observations or check flags."""

    subject_name: str
    teacher_name: str | None = None
    attendance: GrowthAttendance
    chapters: list[GrowthChapter] = []
    homework_assigned: int = 0
    homework_personal: int = 0
    scores: list[GrowthScore] = []


class ParentReportOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    attendance: GrowthAttendance
    subjects: list[ParentReportSubject] = []
    # Derived phrases (never tiers): the same curated lists staff see.
    strengths: list[str] = []
    growth_areas: list[str] = []
