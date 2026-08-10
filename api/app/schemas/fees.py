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
    receipt_number: str | None = Field(default=None, max_length=60)
    paid_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


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


class StudentFeeUpdate(BaseModel):
    discount: Decimal | None = None
    opening_dues: Decimal | None = None


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


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    installment_id: uuid.UUID | None
    amount: Decimal
    type: str
    note: str | None
    mode: str | None
    receipt_number: str | None
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
