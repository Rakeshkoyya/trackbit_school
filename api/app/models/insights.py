"""The two tables the operating board needs that capture did not already have
(DASH3 §3, PR-2 + PR-5).

Everything else on the board is a computed join over existing capture (P5) —
attendance, timetable, plans, homework, tasks, staff presence and leave are all
already recorded. Two things are not, and both are *decisions an admin makes on
the board*, which is exactly the kind of thing that has to be written down:

**`period_substitutions`** — who is covering an absent teacher's period. This is
the P2 shape: the substitution is the PLAN, `class_periods.teacher_member_id`
stays the ACTUAL. Assigning a substitute never rewrites what happened; it puts
the period in someone's My Day so it can happen at all. Cancelling appends a
`cancelled_at` rather than deleting, so "we moved the cover twice this morning"
is still readable at 4pm.

**`followup_actions`** — append-only (law 3), one row per button pressed on any
action rail. It exists for one reason above all others: **so the same parent is
not reminded three times in one morning** by three people looking at the same red
row. Each rail row reads today's history for its own subject and renders "already
reminded" instead of firing again — the same discipline
`class_periods.alerted_at` uses for the automatic absence alert.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

# The rail's verbs. Kept here rather than in a CHECK constraint's shadow so the
# service, the schema and the UI all name them from one place.
FOLLOWUP_KINDS = (
    "guardian_reminded",
    "followup_assigned",
    "substitute_assigned",
    "task_reassigned",
    "task_extended",
    "nudged",
)


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class PeriodSubstitution(Base, UUIDPKMixin, CreatedAtMixin):
    """One period of one day, covered by someone other than its usual teacher.

    Uniqueness is enforced on the *live* rows only (a partial index where
    `cancelled_at IS NULL`), so a period can be re-covered after a cancellation
    without the history being thrown away.
    """

    __tablename__ = "period_substitutions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # The subject being covered. Nullable because a class can be sat with rather
    # than taught — "keep 7B occupied for period 3" is a real instruction.
    class_subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=True,
    )
    absent_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    substitute_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_period_substitutions_org_date", "org_id", "date"),
        Index("uq_period_substitutions_live", "org_id", "date", "class_id", "period_no",
              unique=True, postgresql_where=text("cancelled_at IS NULL")),
        CheckConstraint("period_no >= 1", name="substitution_period_no_valid"),
    )


class FollowupAction(Base, CreatedAtMixin):
    """An action fired from an action rail. Append-only — nothing here is updated.

    `subject_type` / `subject_id` name what the action was ABOUT (a student, a
    member, a task), which is what the idempotence read keys on. `detail` carries
    whatever the rail needs to render "already done" honestly — the message that
    went out, the task that was created.

    Both member references are SET NULL so the history outlives a departing
    member, the same choice `demo_request_notes.author_user_id` makes.
    """

    __tablename__ = "followup_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = _org_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    target_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_followup_actions_org_created", "org_id", "created_at"),
        Index("ix_followup_actions_subject", "org_id", "subject_type", "subject_id"),
    )
