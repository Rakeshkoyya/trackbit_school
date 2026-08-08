"""Machine credentials for agent connectors (`D-97`, MCP-SERVER-PLAN §4.1).

**Why not a JWT.** The app already pays statelessness' price and takes none of
its benefit — `get_current_member` hits the database on every request anyway
(membership + `token_version`). So an opaque token costs exactly the same and
buys the one thing a JWT cannot give: **revocation**. It is also nameable,
scopeable per connector, and greppable — `tbk_live_...` can be caught by secret
scanning and recognised in a log, where a JWT looks like every other JWT.

Human sessions keep their 15-minute JWT unchanged. This is the machine half.

Two invariants worth stating out loud:

- **The raw token is never stored.** Only its SHA-256, and a 12-char prefix so a
  human can tell two rows apart in the list.
- **A token never exceeds its issuer.** `membership_id` is the authority it acts
  with; `scopes` may only narrow that member's toolsets, never widen them. That
  check lives in the service — this table only records the grant.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class ApiToken(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "api_tokens"

    # Law 1: org_id is the token's own, and every request it authenticates reads
    # org context from here — never from a param or a body.
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False)
    # The authority this token acts with. Deleting the membership kills the
    # token, which is the correct behaviour when someone leaves the school.
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False)

    # "Rakesh's Claude Desktop" — the thing that makes revocation possible in
    # practice. Without a name, a list of hashes is not a list anyone can act on.
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False)

    # Toolset names from services/lucy/domains.py. A JSONB array rather than a
    # join table: it is a short, whole-value list that is always read at once and
    # never queried across.
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Orthogonal to scopes, and the default is the safe one.
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="read")

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    # Throttled writes, like `_touch_last_active` — a per-request UPDATE on every
    # authenticated call is write amplification nobody asked for.
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- OAuth linkage (`D-99`) ------------------------------------------
    # An OAuth access token IS an api_tokens row. Keeping one token store means
    # `resolve()` is the only resolver, so revocation, membership liveness and
    # the `agent_access` kill switch apply to connector tokens for free.
    # All of these are NULL for a hand-issued PAT.
    oauth_client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        nullable=True)
    # The authorization code this token descends from. A replayed code revokes
    # every token that came from it (OAuth 2.1 4.1.3).
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(
        Text, unique=True, nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    # RFC 8707: what this token is valid *for*. Checked against the MCP
    # endpoint on every call, so a token minted for another resource is refused.
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    revoked_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)

    __table_args__ = (
        CheckConstraint("mode IN ('read', 'read_write')", name="api_token_mode_valid"),
        Index("ix_api_tokens_org", "org_id"),
        Index("ix_api_tokens_membership", "membership_id"),
    )
