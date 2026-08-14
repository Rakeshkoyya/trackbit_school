"""Fee schemas (SPRD §5.6). Money is Decimal end-to-end."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── fee structures ───────────────────────────────────────────────────────────
class TemplateIn(BaseModel):
    installment_number: int = Field(ge=1)
    label: str | None = Field(default=None, max_length=60)
    amount: Decimal
    due_date: date | None = None


class FeeStructureCreate(BaseModel):
    # `D-116`: the CLASS ("6"), never the sectioned label ("6-B"). One structure
    # prices the whole grade. The service rejects a value that is not one of the
    # year's class names, so this can no longer be free text typed by hand.
    class_name: str = Field(min_length=1, max_length=120)
    category_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID
    total_amount: Decimal
    num_installments: int = Field(ge=1, le=24)
    installments: list[TemplateIn] = Field(min_length=1, max_length=24)


class FeeStructureUpdate(BaseModel):
    """`D-118`: saving an edit archives the old row and writes a new one, so the
    school's pricing history survives and **students already on the old amount
    are not repriced**. The class and year cannot move — that would be a
    different structure, not an edit of this one."""

    total_amount: Decimal
    num_installments: int = Field(ge=1, le=24)
    installments: list[TemplateIn] = Field(min_length=1, max_length=24)
    category_id: uuid.UUID | None = None


# ── the coverage grid (`D-117`) ──────────────────────────────────────────────
class ClassCoverageRow(BaseModel):
    """One class of the year, priced or not.

    `structure_id is None` is the **"not priced"** row. It is a state and it
    renders as a word — never ₹0, which would read as "this class is free"."""

    class_name: str
    # What the price covers. Per-class pricing has to make this obvious, or
    # nobody can tell whether 6-C was included.
    sections: list[str] = Field(default_factory=list)
    students_total: int = 0
    structure_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    total_amount: Decimal | None = None
    num_installments: int | None = None
    # How many students are on THIS structure — the fact that says whether
    # editing is safe (`D-118`).
    students_on: int = 0
    # Students in the class with no fee record at all for this year.
    students_unset: int = 0


class StructureCoverage(BaseModel):
    academic_year_id: uuid.UUID
    classes_total: int = 0
    classes_priced: int = 0
    rows: list[ClassCoverageRow] = Field(default_factory=list)


class ApplyStructureIn(BaseModel):
    """`D-120`: set a class up in one action instead of one sheet per child.

    `student_ids` empty means *every student in the class* — the common case,
    and the one the class-level button sends."""

    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2000)
    skip_existing: bool = True


class FeeEventOut(BaseModel):
    """One line of the actor log (`D-124`).

    `summary` is already a finished sentence — the client renders it, never
    re-composes it from `kind` and `meta`. `actor_name` is never null in
    practice and is what makes the log actionable: the founder's case is one
    admin going to ask another what they changed."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    summary: str
    meta: dict = Field(default_factory=dict)
    actor_name: str | None = None
    student_fee_id: uuid.UUID | None = None
    fee_structure_id: uuid.UUID | None = None
    created_at: datetime


class ApplyStructureOut(BaseModel):
    created: int = 0
    # Never silent: a school that selected 24 children and got 22 records must
    # be told about the other two, or it will assume they were billed.
    skipped_existing: int = 0
    skipped_no_class: int = 0
    message: str = ""


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    installment_number: int
    label: str | None
    amount: Decimal
    due_date: date | None


class FeeStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_name: str
    category_id: uuid.UUID | None
    category_name: str | None = None
    academic_year_id: uuid.UUID
    total_amount: Decimal
    num_installments: int
    is_active: bool
    templates: list[TemplateOut] = Field(default_factory=list)


# ── enrolment / student fee ──────────────────────────────────────────────────
class PaymentIn(BaseModel):
    amount: Decimal
    installment_number: int | None = None  # only used by the enrolment first-payment
    mode: str | None = Field(default=None, max_length=20)
    # `D-128`: left empty, the server generates `FR/2026-27/001` from a locked
    # counter. Still writable, because a school reconciling against a
    # pre-printed book has to type the number on the paper in front of it.
    receipt_number: str | None = Field(default=None, max_length=60)
    paid_on: date | None = None
    note: str | None = Field(default=None, max_length=500)
    # `D-122`: an already-uploaded object key, so a payment and its proof land
    # in one round trip instead of two. Optional, always — making proof
    # mandatory would stop a cash payment being recorded at the counter, which
    # is the one thing this screen must never do.
    proof_key: str | None = Field(default=None, max_length=400)


# ── proof of payment (`D-122`, `D-123`) ──────────────────────────────────────
class PresignProofIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=3, max_length=100)


class PresignProofOut(BaseModel):
    """`url is None` means R2 is not configured, so the client should POST the
    bytes to the pass-through upload route instead. Same two-step shape HS-1
    uses for session media — there is no second storage path."""

    key: str
    url: str | None = None


class ConfirmProofIn(BaseModel):
    key: str = Field(min_length=1, max_length=400)
    caption: str | None = Field(default=None, max_length=200)


class ProofOut(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    kind: str
    # Minted per read: presigned GETs expire, so a stored URL would rot.
    url: str
    content_type: str
    size_bytes: int
    caption: str | None = None
    uploaded_by_name: str | None = None
    created_at: datetime


class InstallmentIn(BaseModel):
    installment_number: int = Field(ge=1)
    label: str | None = Field(default=None, max_length=60)
    amount: Decimal
    due_date: date | None = None


class StudentFeeCreate(BaseModel):
    student_id: uuid.UUID
    academic_year_id: uuid.UUID
    total_fee: Decimal
    discount: Decimal = Decimal("0")
    opening_dues: Decimal = Decimal("0")
    fee_structure_id: uuid.UUID | None = None
    use_custom_schedule: bool = False
    installments: list[InstallmentIn] = Field(default_factory=list)
    first_payment: PaymentIn | None = None
    # FE-2: "the class's price, this family's discount, but six payments instead
    # of four". Unset (or equal to the structure's own count) keeps the school's
    # real terms and due dates; a different number re-plans evenly. The split is
    # `fee_math.plan_installments` either way — never the browser's arithmetic.
    num_installments: int | None = Field(default=None, ge=1, le=24)


# ── FE-2: locking one student's fee, with the discount agreed at the counter ──
class PlannedInstallmentOut(BaseModel):
    """A proposed row. Nothing is written until the office confirms."""

    installment_number: int
    label: str | None = None
    amount: Decimal
    due_date: date | None = None


class FeeSetupStructure(BaseModel):
    id: uuid.UUID
    class_name: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    total_amount: Decimal
    num_installments: int


class FeeSetupOut(BaseModel):
    """What the "set this student up" screen opens on.

    It answers the question the office actually has — *what would this child be
    billed if I do nothing?* — before offering to change it. `structure` is null
    when the class has no price yet, and that is a state with a sentence, never
    a zero.
    """

    student_id: uuid.UUID
    student_name: str
    class_label: str | None = None
    category_name: str | None = None
    academic_year_id: uuid.UUID
    #: Already locked. The screen becomes a link to her record rather than a form.
    already_locked: bool = False
    student_fee_id: uuid.UUID | None = None
    structure: FeeSetupStructure | None = None
    #: The default mapping, priced and dated — what "use the class structure" means.
    default_plan: list[PlannedInstallmentOut] = Field(default_factory=list)


class FeeSetupPreviewIn(BaseModel):
    student_id: uuid.UUID
    academic_year_id: uuid.UUID
    #: Defaults to the structure that prices this student. Sent explicitly only
    #: when the office deliberately picks another one.
    fee_structure_id: uuid.UUID | None = None
    #: Overrides the structure's price. Left unset the structure's total stands.
    total_fee: Decimal | None = None
    discount: Decimal = Decimal("0")
    opening_dues: Decimal = Decimal("0")
    num_installments: int | None = Field(default=None, ge=1, le=24)


class FeeSetupPreview(BaseModel):
    """The arithmetic, done server-side and shown before it is committed."""

    total_fee: Decimal
    discount: Decimal
    net_fee: Decimal
    opening_dues: Decimal
    total_payable: Decimal
    installments: list[PlannedInstallmentOut] = Field(default_factory=list)
    #: A sentence when something is off — a discount larger than the fee, a class
    #: with no structure. Never a silent zero.
    warning: str | None = None


class StudentFeeUpdate(BaseModel):
    discount: Decimal | None = None
    opening_dues: Decimal | None = None


class CloseFeeIn(BaseModel):
    """`D-127`, founder Q-2 — the student transferred out.

    Closing voids the unpaid instalments, drops the payable to what was actually
    billed and paid, and marks the record `closed`. It is reversible."""

    reason: str | None = Field(default=None, max_length=300)


class InstallmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    installment_number: int
    label: str | None
    amount: Decimal
    due_date: date | None
    paid_amount: Decimal
    status: str
    paid_date: date | None
    # `D-127`: voided by a transfer. Still rendered — struck through — because
    # what was originally scheduled is exactly what somebody asks about later.
    is_voided: bool = False


class StudentFeeListItem(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_label: str | None
    category_name: str | None
    academic_year_id: uuid.UUID
    total_fee: Decimal
    discount: Decimal
    net_fee: Decimal
    opening_dues: Decimal
    paid: Decimal
    pending: Decimal
    status: str


class StudentFeeDetail(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_label: str | None
    category_name: str | None
    academic_year_id: uuid.UUID
    total_fee: Decimal
    discount: Decimal
    net_fee: Decimal
    opening_dues: Decimal
    total_payable: Decimal
    paid: Decimal
    balance: Decimal
    status: str
    installments: list[InstallmentOut]


class DueDateUpdate(BaseModel):
    due_date: date | None = None


# ── the mutable schedule (`D-121`) ───────────────────────────────────────────
class SplitInstallmentIn(BaseModel):
    """Divide one instalment into several — the founder's *"some parent wants
    more installments to pay"* case.

    Splitting is the operation to reach for first because **the total is
    preserved by construction**: `parts` equal shares, or explicit `amounts`
    that must sum to the original. Anything already paid stays on the first
    part, so money that has landed is never re-billed."""

    parts: int | None = Field(default=None, ge=2, le=12)
    amounts: list[Decimal] | None = Field(default=None, max_length=12)


class AddInstallmentIn(BaseModel):
    """Append an instalment, taking its amount out of the UNPAID ones.

    The total payable does not move: this re-arranges the schedule, it does not
    change what the family owes. Changing that is a discount."""

    amount: Decimal
    due_date: date | None = None
    label: str | None = Field(default=None, max_length=60)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    installment_id: uuid.UUID | None
    amount: Decimal
    type: str
    note: str | None
    mode: str | None
    receipt_number: str | None
    # The date the money changed hands — NOT `created_at`. A payment taken on
    # Saturday is often entered on Monday, and the receipt has to say Saturday.
    paid_on: date | None = None
    created_at: datetime
    created_by_name: str | None


# ── dashboard card (M4 read-only) ────────────────────────────────────────────
class FeeSummary(BaseModel):
    total_fee: Decimal
    collected_fee: Decimal
    pending_installments: int
    overdue_amount: Decimal


class OverdueStudent(BaseModel):
    student_fee_id: uuid.UUID
    student_name: str
    class_label: str | None
    overdue_amount: Decimal
    earliest_due_date: date | None
