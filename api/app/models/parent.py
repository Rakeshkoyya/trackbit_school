"""V1-11 parent access: the DOB-login lockout, and the family's inbox.

Two tables, two very different lives.

**`parent_login_attempts` (`S-56`)** is platform-level like `otp_codes`: the
login runs *before* any session exists, so no RLS GUC is engaged and an
org-scoped policy would be inert at exactly the moment it mattered. It is keyed
per student because that is what `D-13` puts at risk — a date of birth is about
5,500 guesses and the child picker names the target, so the counter has to sit
on the thing being guessed, not on the guesser.

**`guardian_messages` (`D-08`/`D-14`)** is the destination `notify_guardian.py`
never had. Until now every guardian message — the absence alert, homework set,
the Saturday note — ended its life as a line in a log file. `D-08` removes
WhatsApp from this version, so these rows *are* the delivery: the parent reads
them in the portal, web push wakes them up, and `push_sent_at` records honestly
whether that wake-up worked.

That last column is `S-62`. Push is best-effort — iOS needs the site installed
to the home screen, permission can be denied, a phone can be off — and the
absence alert is not best-effort. So an undelivered message is not swallowed:
`unreachable_reason` names why, and the admin's board lists those few families
for the office to phone. *The reach problem doesn't disappear when WhatsApp
goes; it becomes visible.*

Deliberately NOT `notifications`: that table is the staff task outbox, its
`user_id` is NOT NULL, and most guardians have never logged in and so have no
User row at all. Those are precisely the families the office most needs to
know about, and a table that cannot represent them would have hidden them.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

# What a message is about. Free-text column on purpose (the `exam_types` /
# work-types precedent): a new kind of school note must never need a migration.
GUARDIAN_MESSAGE_KINDS = (
    "absence",           # V2-P2 absence alert — the one that matters most (S-62)
    "left_after_lunch",  # V1-3 twice-daily: went home at midday
    "homework_set",      # P3 — teachers get value before they give data
    "homework_pattern",  # S-90/Q-39 — two consecutive homework days missed, never one
    "week_note",         # the Saturday summary
    "fee_reminder",      # V1-10 D-66 — primary guardian only (Q-70)
    "general",
)

# Why a message did not reach the phone. Ordered by what the office can do
# about it: the first two are fixable at the desk, the third is the parent's
# own choice and must never be "fixed" behind their back.
UNREACHABLE_REASONS = (
    "no_login",    # guardian has never claimed a portal account
    "no_device",   # logged in, never allowed push (or never on a browser that can)
    "push_failed", # we tried and the browser refused it
    "opted_out",   # guardians.notify_opt_out — deliberate, and it stays deliberate
)


class ParentLoginAttempt(Base, UUIDPKMixin, CreatedAtMixin):
    """One row per student, holding the current failure window (`S-56`).

    The counter is bumped in its OWN committed session (see
    `ParentAuthService._bump_login_attempts`) — the request that raises the
    error rolls back, and a lockout that rolls back with it is not a lockout.
    That is the same trick `otp_codes` already relies on.
    """

    __tablename__ = "parent_login_attempts"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # When the current window opened. Failures older than the lock period are
    # not held against a parent who simply mistyped last month.
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", name="uq_parent_login_attempts_student"),
    )


class GuardianMessage(Base, UUIDPKMixin, CreatedAtMixin):
    """One message to one guardian about one child.

    Org-scoped and RLS-policied like every other school table (law 2). The
    parent reads their own rows through the curated projection; nothing here is
    ever rendered to a family without passing that allowlist, and nothing about
    a band, a skill or an observation is ever written into `body` (P4).
    """

    __tablename__ = "guardian_messages"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guardians.id", ondelete="CASCADE"),
        nullable=False, index=True)
    # Which child this is about — with siblings rolled into one login, a message
    # without the name is unreadable.
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Where tapping it should land inside the portal. Always a portal-relative
    # path — a guardian message never links off to a staff screen.
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # `D-14` reach, recorded honestly. Both NULL = we have not tried yet.
    push_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    unreachable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The one thing a parent may write (see `ParentPortalService.mark_read`):
    # session bookkeeping, never content. The read-only fence is about a family
    # contributing data about the school; an unread badge that cannot clear is
    # just a broken archive.
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # At-most-once per (thing, day, guardian) — the same discipline
    # `notifications.dedupe_key` uses. A parent chased twice for one absence
    # stops reading the channel.
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)

    __table_args__ = (
        Index("ix_guardian_messages_feed", "guardian_id", "created_at"),
        # The office's morning question: who did we fail to reach today?
        Index("ix_guardian_messages_reach", "org_id", "created_at", "unreachable_reason"),
    )
