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


class ParentSessionItem(BaseModel):
    session_name: str
    kind: str
    status: str  # present | late | absent
    homework_done: bool | None = None
    log_note: str | None = None


class ParentTodayOut(BaseModel):
    date: date
    # no_school | not_marked | present | partial | absent
    status: str
    marked_periods: int = 0
    absent_periods: int = 0
    late_periods: int = 0
    taught: list[ParentTaughtItem] = []
    homework: list[ParentHomeworkItem] = []
    sessions: list[ParentSessionItem] = []


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
