"""Fee domain (M6) — ported from fee_management_system onto org_id + RLS (SPRD §4.6).

workspace_id -> org_id; FKs re-pointed at the unified students / student_categories
/ academic_years. Money is Numeric(12,2) handled through fee_math.q(). `transactions`
is APPEND-ONLY (undo = compensating row, never a delete) — seed law #3.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin
from app.models.students import Student, StudentCategory

_MONEY = Numeric(12, 2)


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _actor_fk() -> Mapped[uuid.UUID | None]:
    # The staffer who performed the action (global users table). SET NULL on delete.
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FeeStructure(Base, UUIDPKMixin, CreatedAtMixin):
    """Per-(class + category + year) template. Creating a new one ARCHIVES any
    active structure for the same key (is_active=False) — history is kept."""

    __tablename__ = "fee_structures"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_name: Mapped[str] = mapped_column(Text, nullable=False)  # class label, across sections
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_categories.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(_MONEY, nullable=False)
    num_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = _actor_fk()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped["StudentCategory | None"] = relationship("StudentCategory")
    templates: Mapped[list["FeeInstallmentTemplate"]] = relationship(
        back_populates="fee_structure", cascade="all, delete-orphan",
        order_by="FeeInstallmentTemplate.installment_number",
    )


class FeeInstallmentTemplate(Base, UUIDPKMixin):
    __tablename__ = "fee_installment_templates"

    org_id: Mapped[uuid.UUID] = _org_fk()
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(_MONEY, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    fee_structure: Mapped["FeeStructure"] = relationship(back_populates="templates")


class StudentFee(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "student_fees"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    total_fee: Mapped[float] = mapped_column(_MONEY, nullable=False)
    discount: Mapped[float] = mapped_column(_MONEY, nullable=False, server_default="0")
    net_fee: Mapped[float] = mapped_column(_MONEY, nullable=False)
    # Arrears carried from the prior year — adds to the outstanding balance but is
    # kept separate from net_fee; status is still driven by installments only.
    opening_dues: Mapped[float] = mapped_column(_MONEY, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_by: Mapped[uuid.UUID | None] = _actor_fk()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship("Student")
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="student_fee", cascade="all, delete-orphan",
        order_by="Installment.installment_number",
    )

    __table_args__ = (
        UniqueConstraint("student_id", "academic_year_id", name="uq_student_fees_student_id"),
    )


class Installment(Base, UUIDPKMixin):
    __tablename__ = "installments"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_fee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fees.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(_MONEY, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_amount: Mapped[float] = mapped_column(_MONEY, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    student_fee: Mapped["StudentFee"] = relationship(back_populates="installments")


class Transaction(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only money/edit ledger: payment | undo | discount | installment_edit.
    Never UPDATE or DELETE — corrections are new compensating rows (seed law #3)."""

    __tablename__ = "fee_transactions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_fee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fees.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    installment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("installments.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[float] = mapped_column(_MONEY, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str | None] = mapped_column(Text, nullable=True)  # cash | cheque | online
    receipt_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = _actor_fk()
    created_by_name: Mapped[str | None] = mapped_column(Text, nullable=True)
