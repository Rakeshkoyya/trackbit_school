"""Platform (super-admin) schemas — the layer above orgs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PlatformOrgOut(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    plan: str
    created_at: datetime
    member_count: int
    student_count: int
    class_count: int
    active_year: str | None = None
    last_active_at: datetime | None = None
    # V1-2: the parent-login code (S-57) and the handover state (§6 ⑤).
    school_code: str | None = None
    handed_over_at: datetime | None = None


class CreateSchoolRequest(BaseModel):
    """Create a school + its first admin. The dev collects the school's data,
    runs setup inside the org, then hands these credentials to the owner."""

    org_name: str = Field(min_length=1, max_length=120)
    timezone: str = "Asia/Kolkata"
    # V1-2 §6 ①: address (→ state) and board scope the observance catalogue —
    # the school is never asked to declare a region or a religion (D-61).
    address: str | None = Field(default=None, max_length=300)
    state: str | None = Field(default=None, max_length=60)
    board: str | None = Field(default=None, max_length=60)
    admin_name: str = Field(min_length=1, max_length=120)
    admin_email: EmailStr
    # Temp password chosen by the operator; the admin is forced to change it on
    # first login (must_set_password).
    admin_password: str = Field(min_length=8, max_length=128)


class CreateSchoolResult(BaseModel):
    org: PlatformOrgOut
    admin_email: str
    admin_name: str
    school_code: str | None = None


# ── the readiness report (V1-2, §6 ⑤) ────────────────────────────────────────
class ReadinessCheck(BaseModel):
    """One line of the handover page. `status` is ok | warn — never a blocker:
    the report informs the operator, the operator decides. Every warn names its
    CONSEQUENCE ("45 parents cannot log in"), not the missing field, and links
    to the screen that clears it."""

    key: str
    title: str
    status: str  # ok | warn
    summary: str
    count: int | None = None
    total: int | None = None
    link: str | None = None  # web route that clears it
    items: list[str] = Field(default_factory=list)  # e.g. the missing-DOB names


class ReadinessOut(BaseModel):
    org_id: uuid.UUID
    org_name: str
    school_code: str | None = None
    ready_count: int
    total: int
    handed_over_at: datetime | None = None
    checks: list[ReadinessCheck]
