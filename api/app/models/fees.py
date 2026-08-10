"""Fee domain (M6) — ported from fee_management_system onto org_id + RLS (SPRD §4.6).

workspace_id -> org_id; FKs re-pointed at the unified students / student_categories
/ academic_years. Money is Numeric(12,2) handled through fee_math.q(). `transactions`
is APPEND-ONLY (undo = compensating row, never a delete) — seed law #3.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    # `D-127` — the transfer. A student who leaves mid-year has her record CLOSED,
    # not deleted: the unpaid instalments are voided, the balance comes off the
    # total, and the school stops chasing it. All three columns are NULL for the
    # normal case, and clearing them is how the transfer is undone.
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
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
    # `D-127`. Every OTHER instalment state is derived on read by `fee_math` —
    # this one is stored, because voiding is a decision a person made, and
    # `recompute_student_fee()` runs after every mutation and would un-void it on
    # the next payment. A voided row is excluded from billed, pending, overdue
    # and the schedule's balance check, and still renders (struck through): what
    # was originally scheduled is exactly what somebody will ask about later.
    is_voided: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

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
    # The date the money changed hands, which is NOT `created_at` — a payment
    # taken on Saturday is often entered on Monday. `pay()` accepted this from
    # the start but wrote it only to the instalment, so a second payment
    # overwrote the first one's date and the ledger could not say when either
    # landed. A receipt needs the date on the money.
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = _actor_fk()
    created_by_name: Mapped[str | None] = mapped_column(Text, nullable=True)


FEE_NOTE_KINDS = ("call", "visit", "message", "reminder", "assigned", "note")


class FeeNote(Base, UUIDPKMixin, CreatedAtMixin):
    """The fee conversation history, per student (V1-10, `D-84`) — **append-only**
    (law 3), the `demo_request_notes` shape a sixth time.

    The founder's requirement in his own words: *"I know — conversation history.
    I want you to maintain this in the fee management system for every student."*

    What makes it worth a table rather than a free-text field on the student fee:
    the **next caller**. Without it the same family is rung every week by a
    different person, each of them opening with the same question — and the
    school looks disorganised to exactly the people it is asking for money.

    `said` is the load-bearing column. *"Reminded"* is an event; *"spoke to the
    mother — paying after the 15th"* is what makes a row go away (`S-161`), and
    it is what travels into the follow-up task so the teacher who rings knows
    what was already agreed.

    Nothing here is ever edited or deleted, and `author_member_id` is SET NULL so
    the conversation outlives the account that recorded it."""

    __tablename__ = "fee_notes"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_fee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fees.id", ondelete="CASCADE"),
        nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="call")
    said: Mapped[str | None] = mapped_column(Text, nullable=True)
    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)


# ── FE-1: the fee desk ───────────────────────────────────────────────────────

FEE_EVENT_KINDS = (
    "structure_created", "structure_replaced", "fee_created", "fee_bulk_applied",
    "discount_changed", "schedule_split", "schedule_added", "schedule_removed",
    "due_date_changed", "payment_recorded", "payment_undone", "proof_added",
    "proof_removed", "reminder_sent", "followup_assigned", "note_added",
    "record_closed", "record_reopened",
)


class FeeEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Who did what at the fee desk (`D-124`) — **append-only**, like everything
    else that records a decision (law 3).

    The founder's case, in his own words: *"in case there are 3 admins looking
    into fee collections, then if admin1 changes something and admin2 feel
    something is changed and check the action logs and understand and maybe asks
    in person to get clarity"*. That last clause is the design brief. This table
    exists so one colleague can find the other and ask — which means `actor_name`
    matters as much as the change itself, and it is denormalised so the log
    outlives the account that wrote it.

    **Why not just widen `fee_transactions`?** Two reasons, and the first is
    fatal on its own:

    * a third of what has to be logged — pricing a class, editing a structure —
      has **no student and no fee record at all**, and `fee_transactions.
      student_fee_id` is NOT NULL;
    * `fee_transactions` is a *money* ledger that gets summed. Filling it with
      zero-amount rows to describe non-money actions is how a total quietly
      stops meaning anything.

    So money stays there and is summable; this is the narrative, and the family
    page merges the two into one chronology.

    `summary` is a finished English sentence written at write time. No reader
    ever re-derives the wording, for the same reason `Transaction.created_by_name`
    is denormalised: two screens phrasing the same event differently is the
    defect this codebase keeps re-learning.
    """

    __tablename__ = "fee_events"

    org_id: Mapped[uuid.UUID] = _org_fk()
    # All three are nullable and at least one is always set. A structure edit has
    # no student; a bulk apply has no single student either, and names the year.
    student_fee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fees.id", ondelete="CASCADE"),
        nullable=True)
    fee_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_structures.id", ondelete="SET NULL"),
        nullable=True)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Before/after values, ids, counts — whatever the kind needs to be explained
    # later without a join. Never rendered raw.
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    actor_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)
    actor_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeePaymentProof(Base, UUIDPKMixin, CreatedAtMixin):
    """The photograph or PDF that proves a payment (`D-122`).

    It hangs off the **transaction**, not off the student: a proof is evidence of
    one payment, and a family with four receipts has four of them.
    `student_fee_id` rides along denormalised only so the family page can list
    every proof for a child in one query instead of joining through the ledger.

    Stores the object **key**, never a URL — presigned GETs expire, so fetch URLs
    are minted per read (`services/storage.py::url_for`). This is the same shape
    `session_media` uses; there is no second storage path.

    `D-123`: deletion is soft. Law 3 keeps the fact that something was uploaded,
    but a receipt photographed into the wrong child's record is a real privacy
    problem, so the object itself is purged and the row survives with
    `deleted_at` set.
    """

    __tablename__ = "fee_payment_proofs"

    org_id: Mapped[uuid.UUID] = _org_fk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_transactions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    student_fee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_fees.id", ondelete="CASCADE"),
        nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # photo | pdf
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)


class FeeReceiptCounter(Base):
    """One receipt sequence per (org, academic year) — `D-128`.

    A counter row rather than `MAX(receipt_number) + 1`, because the school has
    two clerks at one counter on the first of the month: `MAX + 1` hands both of
    them the same number, and a duplicate receipt number is the one thing an
    auditor will always find. The service takes this row with `SELECT … FOR
    UPDATE`, so the second clerk waits and gets the next one.

    The number stays editable on the payment form: a school reconciling against
    a pre-printed book has to be able to type the number on the paper in front
    of it.
    """

    __tablename__ = "fee_receipt_counters"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False, server_default="FR")
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        PrimaryKeyConstraint("org_id", "academic_year_id"),
    )
