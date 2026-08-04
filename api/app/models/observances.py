"""The observance catalogue and the school's decision on each suggestion (V1-7).

Two tables, and they sit on opposite sides of the tenancy line on purpose.

**`observances` is platform data** (`D-60`, `S-149`) — no `org_id`, no RLS
policy, `require_super_admin` on every write, exactly the `demo_requests` shape
from EN-1. One curation serves every school and one correction fixes every
school, without a deploy. A school never owns a row here and can never write one.

**`event_decisions` is the school's record of what it did about a suggestion**
(`S-148`) — org-scoped, RLS'd, and **append-only** (law 3), the
`plan_approvals` / `demo_request_notes` shape the codebase already uses three
times. Approving also creates a `calendar_events` row; that row is the *effect*,
this one is the *record of the decision*, and the two are deliberately separate
so a deleted holiday does not resurrect the suggestion that produced it.

What is NOT here, and must not arrive later: a birthday. A birthday is derived
from `students.date_of_birth`, never stored as an event (`S-121`). If this file
grows a third table, the module was designed wrong.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

# What kind of date this is, in the school's language. `holiday` is a day
# schools commonly close for, `festival` a date they commonly mark, `observance`
# an international/awareness day. It is a HINT for the admin's default, never a
# decision: the lock level is chosen in the approval sheet, every time.
OBSERVANCE_KINDS = ("holiday", "festival", "observance")

# `S-125` — an international day exists for almost everything. A card with
# something on it every single day stops being read inside a week, so the
# catalogue carries the tier and the feed defaults to `major` only.
OBSERVANCE_TIERS = ("major", "minor")

DECISION_ACTIONS = ("approved", "dismissed")


class Observance(Base, UUIDPKMixin, CreatedAtMixin):
    """One dated entry in the platform catalogue, for one year.

    `key` is the stable slug the same observance carries every year
    (`diwali`, `independence-day`) — dismissal keys on it, so *"we don't observe
    this"* survives into next year's catalogue (`S-148`). `date` is that year's
    actual date, which for a lunisolar festival moves.
    """

    __tablename__ = "observances"

    key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Some dates genuinely span two days by region ("observed 12–13 Oct").
    # NULL = a single day. An honest range beats a confidently wrong single date.
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="festival")
    tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="major")
    # `S-126` — lead time by kind. Independence Day needs three weeks of
    # rehearsal; a birthday needs the morning of.
    prep_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    # `D-61` — scoping falls out of what setup already collects. NULL/empty
    # means "everybody"; a value narrows to schools whose org matches. A school
    # is never asked to declare a region or a religion.
    #
    # V1-19: this was a single `state` column, and it could not express the
    # corpus. `UNIQUE(key, date)` is load-bearing (it is what makes re-importing
    # a corrected file *fix* every school rather than double-suggest), so one
    # row per state was never available: "Onam is a holiday in Kerala" and
    # "Onam is a holiday in Karnataka" are the same (key, date), and the second
    # import silently OVERWROTE the first. Almost every real Indian holiday is
    # observed by a set of states, not one — so the column is the set.
    #
    # Tokens are the canonical spellings in `core/indian_states.py`; nothing
    # else may be written here, or a school will match no row and see an empty
    # feed with no error to explain it.
    states: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    board: Mapped[str | None] = mapped_column(Text, nullable=True)
    tradition: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `S-150` — provenance, and it is NOT NULL. The admin approving a date is the
    # last human in the chain; an unattributed date is one they either approve
    # blindly or ignore entirely, and both are bad.
    source: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Retire an entry rather than delete it — a school may already have approved
    # against it, and the decision row points here.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        CheckConstraint("kind IN ('holiday', 'festival', 'observance')",
                        name="ck_observances_kind_valid"),
        CheckConstraint("tier IN ('major', 'minor')", name="ck_observances_tier_valid"),
        CheckConstraint("end_date IS NULL OR end_date >= date",
                        name="ck_observances_range_ordered"),
        Index("ix_observances_key_date", "key", "date", unique=True),
    )


class EventDecision(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only: what this school decided about one suggestion (`S-148`).

    Never updated, never deleted. Re-approving the same suggestion on a second
    date (Christmas the holiday and the Christmas celebration — the packet's own
    Done-when) appends a second `approved` row, which is exactly right: two
    decisions were made.

    A `dismissed` row is permanent and keys on `observance_key`, not the row id,
    so next year's Diwali entry does not come back to a school that said no.
    """

    __tablename__ = "event_decisions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    # SET NULL: a retired catalogue entry must not erase the school's history.
    observance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("observances.id", ondelete="SET NULL"), nullable=True,
    )
    observance_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # The effect of an approval. SET NULL, because deleting the holiday off the
    # year calendar must not resurrect the suggestion — the decision was still
    # made, and re-suggesting it would be the feed nagging.
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True,
    )
    decided_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("action IN ('approved', 'dismissed')",
                        name="ck_event_decisions_action_valid"),
        Index("ix_event_decisions_org_key", "org_id", "observance_key"),
    )
