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
    class_name: str = Field(min_length=1, max_length=120)
    category_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID
    total_amount: Decimal
    num_installments: int = Field(ge=1, le=24)
    installments: list[TemplateIn] = Field(min_length=1, max_length=24)


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
