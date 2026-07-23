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


class CreateSchoolRequest(BaseModel):
    """Create a school + its first admin. The dev collects the school's data,
    runs setup inside the org, then hands these credentials to the owner."""

    org_name: str = Field(min_length=1, max_length=120)
    timezone: str = "Asia/Kolkata"
    admin_name: str = Field(min_length=1, max_length=120)
    admin_email: EmailStr
    # Temp password chosen by the operator; the admin is forced to change it on
    # first login (must_set_password).
    admin_password: str = Field(min_length=8, max_length=128)


class CreateSchoolResult(BaseModel):
    org: PlatformOrgOut
    admin_email: str
    admin_name: str
