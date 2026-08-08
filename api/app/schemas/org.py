"""Org/member schemas (P0 invite slice; P1-BE-08 expands the Members API)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.roles import ROLE_PATTERN, TEACHER


class InviteMemberRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    role: str = Field(default=TEACHER, pattern=ROLE_PATTERN)
    # invite_link -> return shareable URL the admin sends themselves (plan B4)
    # email_invite -> also "send" it via the email channel (dev stub logs it)
    mode: str = Field(default="invite_link", pattern="^(invite_link|email_invite)$")

    @model_validator(mode="after")
    def _need_a_contact(self) -> "InviteMemberRequest":
        if not self.email and not self.phone:
            raise ValueError("Provide an email or a phone number.")
        if self.mode == "email_invite" and not self.email:
            raise ValueError("Email invite needs an email address.")
        return self


class InvitedMemberResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    role: str
    invite_url: str
    pending: bool = False  # brand-new account that still needs to set a password


class MemberOut(BaseModel):
    user_id: uuid.UUID
    member_id: uuid.UUID | None = None  # membership id (for class/subject teacher assignment)
    name: str
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    role: str
    status: str
    last_active_at: datetime | None = None
    has_email: bool = False
    has_phone: bool = False
    pending: bool = False  # invited/created but hasn't set their own password yet


class MembersListResponse(BaseModel):
    members: list[MemberOut] = []


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern=ROLE_PATTERN)


class RemoveMemberResponse(BaseModel):
    orphaned_tasks: int = 0


class BulkMemberRow(BaseModel):
    # Name is optional: staff set their own on first login. When omitted, the
    # account's display name defaults to the username until then.
    name: str | None = Field(default=None, max_length=120)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default=TEACHER, pattern=ROLE_PATTERN)


class BulkMembersRequest(BaseModel):
    members: list[BulkMemberRow] = Field(min_length=1, max_length=100)


class BulkMemberResult(BaseModel):
    name: str
    username: str
    role: str
    ok: bool
    user_id: uuid.UUID | None = None
    password: str | None = None  # echoed back for the copyable summary on success
    error: str | None = None  # code on failure (username_taken / invalid_username)


class BulkMembersResponse(BaseModel):
    results: list[BulkMemberResult]
    created: int


class UsernameAvailabilityResponse(BaseModel):
    username: str  # normalized form (lowercased/trimmed) the server would store
    available: bool
    error: str | None = None  # "username_taken" | "invalid_username" when not available


class AdminResetPasswordRequest(BaseModel):
    # Present => username user: set this as the new temp password (forces change).
    # Absent  => email user: send a reset link.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminResetPasswordResponse(BaseModel):
    mode: str  # "link_sent" | "password_set"
    password: str | None = None  # echoed temp password when mode == password_set


# ---- org settings + usage (S9) ----------------------------------------
class OrgUsageOut(BaseModel):
    boards: int
    members: int


class WorkCategoryOut(BaseModel):
    """One timesheet category (D-19): stable key, mutable label, retire never
    delete. `other` is always present and always active."""

    key: str
    label: str
    active: bool = True
    #: V1-16 — the day-book cell colour. Always resolved server-side, so a client
    #: never has to know the assignment rules (`core/work_types.py`).
    color: str = ""


class WorkCategoryIn(BaseModel):
    # key absent/blank = a NEW category: the server mints a stable key from the
    # label, once, and never regenerates it on rename.
    key: str | None = Field(default=None, max_length=40)
    label: str = Field(min_length=1, max_length=60)
    active: bool = True
    #: One of `CATEGORY_COLORS` or "slate". Omit to keep whatever is set (or to
    #: take the next free slot). Anything else is rejected — see the note on
    #: `CATEGORY_COLORS` for why this is not a free-form hex.
    color: str | None = Field(default=None, max_length=20)


class OrgSettingsOut(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    report_card_hour: int
    plan: str
    plan_status: str
    plan_renews_at: datetime | None = None
    # V1-2 — setup & onboarding
    school_code: str | None = None  # read-only: minted at creation (S-57)
    address: str | None = None
    state: str | None = None
    board: str | None = None
    # V1-3 (S-25): the number behind the parent's "tell the school why" link.
    phone: str | None = None
    attendance_mode: str = "every_period"  # D-01
    min_attendance_pct: int = 75
    homework_gap_days: int = 3
    agent_access: str = "off"  # D-103 — off for a school still being set up
    # V1-8 (`D-54`/`S-138`, A-4): keep the model-read-vs-human-locked diff on
    # locked exam captures, for training a marks reader later. Default OFF and
    # asked for — it is the only data here that does not serve the school that
    # entered it. No export path exists in v1.
    training_data_opt_in: bool = False
    work_categories: list[WorkCategoryOut] = []
    #: Every feature this school's plan includes (`core/features.py`), computed
    #: server-side so no client re-derives the tier map. `D-106`: the map and
    #: the price move on different clocks, so this list carries neither.
    features: list[str] = []
    usage: OrgUsageOut


class OrgSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = None
    report_card_hour: int | None = Field(default=None, ge=0, le=23)
    address: str | None = Field(default=None, max_length=300)
    state: str | None = Field(default=None, max_length=60)
    board: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=20)
    attendance_mode: str | None = Field(
        default=None, pattern="^(every_period|first_period|twice_daily)$")
    min_attendance_pct: int | None = Field(default=None, ge=0, le=100)
    homework_gap_days: int | None = Field(default=None, ge=1, le=30)
    # `D-103`: who may issue an agent connector. Switching this to `off`
    # disables tokens already issued, not only new ones.
    agent_access: str | None = Field(
        default=None, pattern="^(off|admins|all_staff)$")
    training_data_opt_in: bool | None = None
    # Full replace of the visible list; the service applies the D-19 rules
    # (missing keys are retired, never deleted).
    work_categories: list[WorkCategoryIn] | None = None
