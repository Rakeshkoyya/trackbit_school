"""Syllabus + academic plan (M1, SPRD §4.3).

The approved set of plan_entries is the **baseline** (P2). Re-forecast is computed
from baseline + effective periods — never stored as mutated plan rows.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class SyllabusUnit(Base, UUIDPKMixin, CreatedAtMixin):
    """A chapter within a class-subject's syllabus.

    `term_id` is how a school says "this chapter belongs to Term 2". It is NULLABLE
    on purpose: a school that plans the whole year in one go never sets it, and
    every pre-term-planning row keeps working untouched. NULL means "not scoped to
    a term", never "Term 1"."""

    __tablename__ = "syllabus_units"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Dropping a term must not delete the chapter — it un-scopes it (SET NULL).
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(Text, nullable=False)

    topics: Mapped[list["SyllabusTopic"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", order_by="SyllabusTopic.position",
    )


class SyllabusTopic(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "syllabus_topics"

    org_id: Mapped[uuid.UUID] = _org_fk()
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_units.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL = "nobody has sized this chapter yet", which is the normal state of a
    # later term's syllabus in April. It is NOT the same as 1, and the difference
    # is load-bearing: `distribute` refuses to place an unsized topic and the
    # forecast refuses to go green while any remain. A NOT NULL DEFAULT 1 here
    # made an unplanned year look finished.
    est_periods: Mapped[int | None] = mapped_column(Integer, nullable=True)

    unit: Mapped["SyllabusUnit"] = relationship(back_populates="topics")


class Plan(Base, UUIDPKMixin, CreatedAtMixin):
    """One plan per class-subject. Approving it locks the baseline (P2).

    `status` / `approved_at` are a DERIVED CACHE of `plan_approvals`, recomputed on
    every approve/unapprove. The append-only table is the record of who did what
    (law 3); these columns exist so `overview.py` and `wizard.py` can ask "is this
    plan locked?" without replaying events. Never write them outside
    `PlannerService._recompute_plan_status`.

    status: none | draft | partial | approved
      partial = some terms approved, others still open for planning.
    """

    __tablename__ = "plans"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("class_subject_id", name="uq_plans_class_subject_id"),
    )


class PlanApproval(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only log of baseline locks and unlocks, per (class-subject, term).

    Law 3: undo is a compensating row, never an UPDATE or a DELETE. Un-approving
    Term 1 appends `action='revoke'`; the current state of a term is the action on
    its most recent row. That history is the answer to "who unlocked the plan the
    week before the exam", which a mutable `revoked_at` column would erase.

    `term_id IS NULL` is the whole-year approval — what a school that never uses
    terms gets, and what `approve_plan(term_id=None)` writes.
    """

    __tablename__ = "plan_approvals"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)  # approve | revoke
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("action IN ('approve', 'revoke')", name="plan_approval_action_valid"),
    )


class PlanEntry(Base, UUIDPKMixin, CreatedAtMixin):
    """A topic scheduled into a week (Monday date). The approved set is the baseline.

    An unsized topic (`est_periods IS NULL`) has NO row here — you cannot schedule
    what nobody has estimated. Re-planning a term deletes and rebuilds only the
    entries whose topic sits in that term, so an approved Term 1 is never touched
    by a Term 2 re-draft (P2)."""

    __tablename__ = "plan_entries"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=False,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_subject_id", "topic_id", name="uq_plan_entries_class_subject_id"),
    )


class PlanComment(Base, UUIDPKMixin, CreatedAtMixin):
    """A teacher change-request on a plan (V2-M2, SPRD2 §5.2) — "chapter 4 needs
    more days". Threaded per class-subject, optionally anchored to a topic. The
    admin applies the change (re-draft / drag) and resolves it, then re-approves."""

    __tablename__ = "plan_comments"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True
    )
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")

    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="plan_comment_status_valid"),
    )
