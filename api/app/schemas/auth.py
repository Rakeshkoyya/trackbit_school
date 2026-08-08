"""Auth request/response schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterOrgRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = "Asia/Kolkata"


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)  # email or username
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    # Optional: first-login name capture (bulk/username staff start with a
    # placeholder name = their username and can set a real one here).
    name: str | None = Field(default=None, max_length=120)


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # V1-7 `D-56`: staff DOB is **self-entered from the profile screen and never
    # imported**. `S-127` — an admin who wishes a teacher by name on the morning
    # of costs nothing and is felt for a year, and staff turnover is a school's
    # most expensive problem. Fence (`Q-57`): it must never reach a parent
    # surface, and must never sit next to anything payroll-shaped.
    # An explicit null clears it; omitting the field leaves it alone.
    date_of_birth: date | None = None
    set_date_of_birth: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class VerifyTokenRequest(BaseModel):
    token: str


class SwitchOrgRequest(BaseModel):
    org_id: uuid.UUID


class CreateOrgRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=120)
    timezone: str = "Asia/Kolkata"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    email: str | None = None
    username: str | None = None
    phone: str | None = None


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    timezone: str
    plan: str
    # SETUP-REDESIGN-PLAN §6: once we have handed the school over, its structure
    # is ours to change (`require_operator`). The UI reads this to render the
    # setup screens read-only rather than offering buttons that 403 — a disabled
    # affordance that explains itself beats a permission error.
    handed_over_at: datetime | None = None


class OrgMembershipOut(BaseModel):
    """One org the signed-in user is an active member of — drives the switcher."""
    id: uuid.UUID
    name: str
    plan: str
    org_role: str


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    org_role: str
    must_set_password: bool = False
    is_super_admin: bool = False
    user: UserOut
    org: OrgOut
    # Every org this user can switch into (includes the current one).
    orgs: list[OrgMembershipOut] = []


class MeResponse(BaseModel):
    org_role: str
    # V1-7 (`D-56`): the signed-in member's own DOB, for the profile screen that
    # sets it. Never rendered on a class list (`S-133`) and never sent to a
    # parent surface (`Q-57`).
    date_of_birth: date | None = None
    must_set_password: bool = False
    is_super_admin: bool = False
    # V1-3 (D-03): this member is class teacher of at least one class — the nav
    # shows "My Class" from this alone.
    is_class_teacher: bool = False
    # Founder 2026-08-04: this member takes at least one monitored subject (or is
    # an admin) — the one signal the nav needs to show/hide "ABC bands".
    has_band_scope: bool = False
    user: UserOut
    org: OrgOut
    orgs: list[OrgMembershipOut] = []
