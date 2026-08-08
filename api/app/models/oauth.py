"""OAuth 2.1 authorization-server tables (`D-99`).

Claude's hosted surfaces connect to a remote MCP server over OAuth, so the API
becomes an authorization server. Two tables are enough because **access tokens
are not stored here** — they are `api_tokens` rows (see `models/api_token.py`).
That is deliberate: `ApiTokenService.resolve()` already enforces revocation,
membership liveness and the `agent_access` kill switch, and a second token store
would be a second auth path that forgets one of them.

- `OAuthClient` — a pre-registered client. The founder generates one per
  connector from Setup -> Connections and pastes the id/secret into Claude's
  "Advanced settings". This is the documented non-DCR path for custom
  connectors, and it scopes the OAuth client to one organization.
- `OAuthGrant` — a single-use authorization code, carrying its PKCE challenge
  and the `resource` it was issued for.

Both are org-scoped, so law 2 applies and both carry an org_isolation policy.
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


class OAuthClient(Base, UUIDPKMixin, CreatedAtMixin):
    """A registered OAuth client — one connector configuration."""

    __tablename__ = "oauth_clients"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # The public identifier pasted into Claude. Unguessable rather than
    # sequential: a client_id is not a secret, but it should not be enumerable.
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # NULL = public client (PKCE only). Claude's connector UI makes the secret
    # optional, so both shapes have to work.
    client_secret_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Exact-match allowlist, plus the port-agnostic loopback rule applied in the
    # service (RFC 8252 7.3 — Claude Code binds an ephemeral port).
    redirect_uris: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Toolsets this client may ever request. The consent screen cannot widen it,
    # and the issuing member's own role narrows it again at token time.
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="read")

    created_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("mode IN ('read', 'read_write')",
                        name="oauth_client_mode_valid"),
        Index("ix_oauth_clients_org", "org_id"),
    )


class OAuthGrant(Base, UUIDPKMixin, CreatedAtMixin):
    """A single-use authorization code.

    Short-lived by construction, consumed on first exchange, and bound to the
    PKCE challenge, the redirect URI and the `resource` it was issued for — the
    three things that stop a stolen code being replayed somewhere else.
    """

    __tablename__ = "oauth_grants"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        nullable=False)
    # Whose authority the resulting token acts with.
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False)

    code_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    # RFC 8707 — echoed at token time and burned into the token's audience.
    resource: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False)

    code_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="S256")

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    # Set on exchange. A second attempt is a replay: the grant is refused and
    # every token descended from it is revoked (OAuth 2.1 4.1.3).
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("code_challenge_method = 'S256'",
                        name="oauth_grant_pkce_s256"),
        Index("ix_oauth_grants_org", "org_id"),
        Index("ix_oauth_grants_client", "client_id"),
    )
