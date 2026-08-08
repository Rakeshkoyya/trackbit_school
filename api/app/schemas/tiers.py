"""Package tiers — request/response shapes (`D-106`…`D-111`).

Money is **integer paise** on the wire, never rupees and never a float. The
client divides by 100 to render; nothing here ever ships a pre-formatted
currency string, because the same figure appears on the wall, the operator's
list and the marketing page and they must not drift.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- prices (platform data, operator-editable) -------------------------
class PlanPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    amount_paise_per_student: int
    currency: str
    effective_from: datetime


class SetPriceIn(BaseModel):
    plan: str
    #: Paise per student per month. 0 is legal — that is what `free` costs.
    amount_paise_per_student: int = Field(ge=0, le=10_000_000)
    note: str | None = Field(default=None, max_length=500)


# ---- the quote a school sees on the wall -------------------------------
class TierQuoteOut(BaseModel):
    plan: str
    label: str
    unit_paise_per_student: int
    #: This school's own active-student count — the multiplier. Carried beside
    #: the total so the wall can show its working ("₹10 × 480 students"), never
    #: a bare number the school has to trust.
    students: int
    monthly_paise: int
    features: list[str]
    is_current: bool
    #: False for anything at or below the current plan — there is nothing to buy.
    is_upgrade: bool


class PlanQuoteOut(BaseModel):
    current_plan: str
    students: int
    currency: str
    tiers: list[TierQuoteOut]


# ---- the plan history (append-only, law 3) -----------------------------
class PlanChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_plan: str | None
    to_plan: str
    reason: str | None
    student_count_at_change: int | None
    unit_amount_snapshot: int | None
    monthly_amount_snapshot: int | None
    effective_from: datetime
    expires_at: datetime | None
    created_at: datetime
    changed_by_name: str | None = None


class AssignPlanIn(BaseModel):
    plan: str
    reason: str | None = Field(default=None, max_length=1000)
    #: NULL = no end date. Nothing downgrades on this automatically; the
    #: operator's "expiring soon" list reads it.
    expires_at: datetime | None = None


# ---- the upgrade queue -------------------------------------------------
class UpgradeRequestIn(BaseModel):
    plan: str
    #: Which wall they hit, if they came from one — a `core/features.Feature`
    #: id. The single most useful column in the table: it says which paywall
    #: actually converts, without anyone being surveyed.
    feature_id: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=2000)


class UpgradeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    requested_plan: str
    feature_id: str | None
    message: str | None
    status: str
    created_at: datetime
    requested_by_name: str | None = None
    #: Operator-list context. Absent on the school's own view of its request.
    org_name: str | None = None
    current_plan: str | None = None
    students: int | None = None
    monthly_paise: int | None = None


class UpgradeRequestNoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=4000)
    status_to: str | None = None


class UpgradeRequestNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    note: str | None
    status_from: str | None
    status_to: str | None
    created_at: datetime
    author_name: str | None = None


class OrgPlanOut(BaseModel):
    """Everything the school's own plan screen and every upgrade wall need, in
    one call: what each tier costs THIS school, whether an ask is already in
    flight, and whether this member is allowed to make one (`D-110`)."""

    quote: PlanQuoteOut
    open_request: UpgradeRequestOut | None = None
    #: False for a teacher — the wall then says "contact your admin" and offers
    #: no form at all, rather than a button that 403s.
    can_request: bool = False


class UpgradeRequestDetailOut(BaseModel):
    request: UpgradeRequestOut
    #: Operator-only. Never rendered on an org-scoped surface — these are our
    #: notes about the school, not for the school (`models/tiers.py`).
    notes: list[UpgradeRequestNoteOut] = []
