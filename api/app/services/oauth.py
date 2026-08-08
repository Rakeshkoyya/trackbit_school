"""The OAuth 2.1 authorization server behind the MCP connector (`D-99`).

Claude's hosted surfaces will not accept a bare header token for a custom
connector — they run an OAuth authorization-code flow with PKCE. This module is
that server. It is deliberately small: the *only* grant types are
`authorization_code` and `refresh_token`, because every other grant either has
no user in the loop or has no place here.

Three rules shape the whole file, each checked against the current MCP
authorization spec and Claude's connector documentation rather than recalled:

1. **PKCE S256 is mandatory.** Claude sends `code_challenge` with
   `code_challenge_method=S256` on every authorization request, whatever the
   registration mechanism, so the server never accepts `plain` or a missing
   challenge.
2. **The token is bound to a resource** (RFC 8707). `resource` rides the
   authorization and token requests and is burned into the token's `audience`;
   the MCP endpoint refuses a token minted for anything else. That is what stops
   a token issued for a different server being replayed at ours.
3. **A replayed authorization code revokes its descendants.** Codes are
   single-use; a second exchange is treated as theft, not as a retry
   (OAuth 2.1 4.1.3).

The access token it issues is an ordinary `api_tokens` row, so
`ApiTokenService.resolve()` stays the single resolver — revocation, membership
liveness and the org's `agent_access` switch apply to connector tokens without
being reimplemented here.
"""

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import AppError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import generate_raw_token, hash_token
from app.models import ApiToken, Membership, OAuthClient, OAuthGrant, Organization
from app.services.api_tokens import ApiTokenService, _token_prefix
from app.services.lucy import domains
from app.services.lucy.registry import visible_tools

# Claude's hosted surfaces (web, Desktop, mobile, Cowork) all use this one
# callback. Verified against Claude's connector docs — do not "tidy" it.
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"

# Claude Code is a native client and binds an ephemeral loopback port per
# session, declaring these in its Client ID Metadata Document. RFC 8252 7.3
# requires the port to be ignored when matching.
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")

DEFAULT_REDIRECT_URIS = (
    CLAUDE_CALLBACK,
    "http://localhost/callback",
    "http://127.0.0.1/callback",
)

# Short enough that a leaked code is near-useless, long enough for a browser
# redirect chain. The exchange is machine-to-machine and immediate.
CODE_TTL_SECONDS = 60
ACCESS_TOKEN_TTL_HOURS = 8
REFRESH_TOKEN_TTL_DAYS = 60

GRANT_TYPES = ("authorization_code", "refresh_token")


class OAuthError(AppError):
    """An OAuth-shaped error: the wire format is `{error, error_description}`,
    not this codebase's usual envelope, so the endpoint renders it specially.

    `error` must be an RFC 6749 code — Claude keys its refresh handling on
    `invalid_grant` specifically, and a custom code there breaks token refresh
    quietly rather than loudly.
    """

    def __init__(self, error: str, description: str = "", status_code: int = 400):
        super().__init__(description or error, code=error)
        self.oauth_error = error
        self.status_code = status_code


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def redirect_uri_allowed(requested: str, allowed: list[str]) -> bool:
    """Exact match, except that loopback redirects ignore the port.

    Claude Code picks a fresh port every session, so `http://localhost:3118/callback`
    has to match a registered `http://localhost/callback`. RFC 8252 7.3 requires
    this for `127.0.0.1`; Claude's docs ask for the same treatment of `localhost`.
    Everything else — including any https redirect — is compared exactly, because
    a loose match on a public redirect is an open-redirect hole.
    """
    if requested in allowed:
        return True
    got = urlsplit(requested)
    if got.hostname not in LOOPBACK_HOSTS or got.scheme != "http":
        return False
    for candidate in allowed:
        want = urlsplit(candidate)
        if (want.scheme == "http"
                and want.hostname == got.hostname
                and want.path == got.path):
            return True
    return False


class OAuthService:
    def __init__(self, db: Session):
        self.db = db

    # -- client registration (the Connections screen) ---------------------

    def create_client(self, m: CurrentMember, *, name: str,
                      scopes: list[str], mode: str = "read",
                      redirect_uris: list[str] | None = None,
                      confidential: bool = True) -> tuple[OAuthClient, str | None]:
        """Register a connector. Returns the row and the raw secret, which is
        shown once and is never recoverable."""
        tokens = ApiTokenService(self.db)
        tokens._assert_may_issue(m)
        clean = (name or "").strip()
        if not clean:
            raise ValidationError("Give the connection a name.")
        if mode not in ("read", "read_write"):
            raise ValidationError("mode must be 'read' or 'read_write'.")
        granted = tokens._narrow_scopes(m, scopes)

        uris = list(redirect_uris or DEFAULT_REDIRECT_URIS)
        for uri in uris:
            parts = urlsplit(uri)
            if parts.scheme == "https":
                continue
            if parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS:
                continue
            raise ValidationError(
                f"Redirect URI must be https, or http on loopback: {uri}")

        secret = generate_raw_token(32) if confidential else None
        row = OAuthClient(
            org_id=m.org_id,
            name=clean,
            # Prefixed like the PAT so a leaked id is recognisable in a log.
            client_id="tbk_client_" + secrets.token_urlsafe(18),
            client_secret_hash=_sha256(secret) if secret else None,
            redirect_uris=uris,
            scopes=granted,
            mode=mode,
            created_by_membership_id=m.membership.id,
        )
        self.db.add(row)
        self.db.flush()
        return row, secret

    def list_clients(self, m: CurrentMember) -> list[OAuthClient]:
        stmt = select(OAuthClient).where(OAuthClient.org_id == m.org_id)
        if not m.is_admin:
            stmt = stmt.where(
                OAuthClient.created_by_membership_id == m.membership.id)
        return list(self.db.scalars(stmt.order_by(OAuthClient.created_at.desc())))

    def revoke_client(self, m: CurrentMember, client_pk: uuid.UUID) -> OAuthClient:
        """Revoking a connector also kills every token it ever issued — the
        point of the button is that access stops, not that new logins stop."""
        row = self.db.scalar(select(OAuthClient).where(
            OAuthClient.id == client_pk, OAuthClient.org_id == m.org_id))
        if row is None:
            raise NotFoundError("Connection", str(client_pk))
        if not m.is_admin and row.created_by_membership_id != m.membership.id:
            raise ForbiddenError("You can only revoke your own connections.")
        now = datetime.now(UTC)
        if row.revoked_at is None:
            row.revoked_at = now
        for tok in self.db.scalars(select(ApiToken).where(
                ApiToken.oauth_client_id == row.id,
                ApiToken.revoked_at.is_(None))):
            tok.revoked_at = now
            tok.revoked_by_membership_id = m.membership.id
        return row

    # -- the authorization endpoint ---------------------------------------

    def load_client(self, client_id: str) -> OAuthClient:
        row = self.db.scalar(select(OAuthClient).where(
            OAuthClient.client_id == client_id))
        if row is None or row.revoked_at is not None:
            raise OAuthError("invalid_client", "Unknown or revoked client.", 401)
        return row

    def begin_authorization(self, *, client_id: str, redirect_uri: str,
                            response_type: str, code_challenge: str,
                            code_challenge_method: str,
                            scope: str | None,
                            resource: str | None) -> OAuthClient:
        """Validate an authorization request *before* any user interaction.

        Errors here must NOT redirect — an unvalidated `redirect_uri` is exactly
        what an attacker would supply, so a bad client or redirect renders an
        error instead of bouncing the browser (OAuth 2.1 4.1.2.1).
        """
        client = self.load_client(client_id)
        if not redirect_uri_allowed(redirect_uri, client.redirect_uris or []):
            raise OAuthError("invalid_request",
                             "redirect_uri is not registered for this client.")
        if response_type != "code":
            raise OAuthError("unsupported_response_type",
                             "Only the authorization code flow is supported.")
        if code_challenge_method != "S256":
            raise OAuthError("invalid_request",
                             "PKCE with code_challenge_method=S256 is required.")
        if not code_challenge:
            raise OAuthError("invalid_request", "code_challenge is required.")
        if scope:
            unknown = (set(scope.split()) - set(client.scopes or [])
                       - {"offline_access"})
            if unknown:
                raise OAuthError(
                    "invalid_scope",
                    f"Not granted to this connector: {', '.join(sorted(unknown))}")
        return client

    def issue_code(self, m: CurrentMember, client: OAuthClient, *,
                   redirect_uri: str, code_challenge: str,
                   scope: str | None, resource: str | None) -> str:
        """The user has consented. Mint a single-use code bound to them."""
        if client.org_id != m.org_id:
            raise ForbiddenError("This connector belongs to a different school.")
        ApiTokenService(self.db)._assert_may_issue(m)
        requested = [s for s in (scope or "").split() if s != "offline_access"]
        granted = sorted(set(requested or list(client.scopes)) & set(client.scopes))
        raw = secrets.token_urlsafe(32)
        self.db.add(OAuthGrant(
            org_id=m.org_id,
            client_id=client.id,
            membership_id=m.membership.id,
            code_hash=_sha256(raw),
            redirect_uri=redirect_uri,
            resource=resource,
            scopes=granted or sorted(domains.ALWAYS_ON),
            code_challenge=code_challenge,
            code_challenge_method="S256",
            expires_at=datetime.now(UTC) + timedelta(seconds=CODE_TTL_SECONDS),
        ))
        self.db.flush()
        return raw

    # -- the token endpoint -----------------------------------------------

    def _authenticate_client(self, client: OAuthClient,
                             client_secret: str | None) -> None:
        """A confidential client must prove itself; a public client has nothing
        to prove. Claude makes the secret optional in its connector UI, so both
        shapes are legitimate — what is not legitimate is accepting a missing
        secret for a client that registered one."""
        if client.client_secret_hash is None:
            return
        if not client_secret:
            raise OAuthError("invalid_client",
                             "This client requires a client_secret.", 401)
        if not secrets.compare_digest(_sha256(client_secret),
                                      client.client_secret_hash):
            raise OAuthError("invalid_client", "Bad client credentials.", 401)

    def _mint(self, grant_scopes: list[str], *, org_id, membership_id,
              client: OAuthClient, grant_id, audience: str | None,
              name: str) -> tuple[ApiToken, str, str]:
        raw_access = _token_prefix() + generate_raw_token(32)
        raw_refresh = _token_prefix() + generate_raw_token(32)
        now = datetime.now(UTC)
        row = ApiToken(
            org_id=org_id,
            membership_id=membership_id,
            name=name,
            token_hash=hash_token(raw_access),
            prefix=raw_access[:12],
            scopes=grant_scopes,
            mode=client.mode,
            expires_at=now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
            oauth_client_id=client.id,
            grant_id=grant_id,
            refresh_token_hash=hash_token(raw_refresh),
            refresh_expires_at=now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            audience=audience,
            created_by_membership_id=membership_id,
        )
        self.db.add(row)
        self.db.flush()
        return row, raw_access, raw_refresh

    def exchange_code(self, *, code: str, client_id: str,
                      client_secret: str | None, code_verifier: str,
                      redirect_uri: str, resource: str | None) -> dict:
        client = self.load_client(client_id)
        self._authenticate_client(client, client_secret)

        grant = self.db.scalar(select(OAuthGrant).where(
            OAuthGrant.code_hash == _sha256(code)))
        if grant is None or grant.client_id != client.id:
            raise OAuthError("invalid_grant", "Unknown authorization code.")

        if grant.consumed_at is not None:
            # Replay. The legitimate holder already exchanged this code, so the
            # copy in flight is stolen — kill everything descended from it.
            for tok in self.db.scalars(select(ApiToken).where(
                    ApiToken.grant_id == grant.id,
                    ApiToken.revoked_at.is_(None))):
                tok.revoked_at = datetime.now(UTC)
            raise OAuthError("invalid_grant",
                             "Authorization code has already been used.")
        if grant.expires_at <= datetime.now(UTC):
            raise OAuthError("invalid_grant", "Authorization code has expired.")
        if grant.redirect_uri != redirect_uri:
            raise OAuthError("invalid_grant", "redirect_uri does not match.")

        # PKCE: BASE64URL(SHA256(verifier)) == stored challenge, unpadded.
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        if not secrets.compare_digest(computed, grant.code_challenge):
            raise OAuthError("invalid_grant", "PKCE verification failed.")

        # RFC 8707: a token request may repeat the resource but never change it.
        if resource and grant.resource and resource != grant.resource:
            raise OAuthError("invalid_target",
                             "resource does not match the authorization request.")

        grant.consumed_at = datetime.now(UTC)
        row, access, refresh = self._mint(
            list(grant.scopes), org_id=grant.org_id,
            membership_id=grant.membership_id, client=client,
            grant_id=grant.id, audience=grant.resource or resource,
            name=client.name)
        client.last_used_at = datetime.now(UTC)
        return self._token_response(row, access, refresh)

    def refresh(self, *, refresh_token: str, client_id: str,
                client_secret: str | None, scope: str | None = None) -> dict:
        """Rotating refresh: the old token dies in the same transaction that
        mints the new one. OAuth 2.1 requires rotation for public clients, and
        Claude registers as one."""
        client = self.load_client(client_id)
        self._authenticate_client(client, client_secret)

        old = self.db.scalar(select(ApiToken).where(
            ApiToken.refresh_token_hash == hash_token(refresh_token)))
        if old is None or old.oauth_client_id != client.id:
            raise OAuthError("invalid_grant", "Unknown refresh token.")
        if old.revoked_at is not None:
            raise OAuthError("invalid_grant", "Refresh token has been revoked.")
        if old.refresh_expires_at and old.refresh_expires_at <= datetime.now(UTC):
            raise OAuthError("invalid_grant", "Refresh token has expired.")

        membership = self.db.get(Membership, old.membership_id)
        if membership is None or membership.status != "active":
            raise OAuthError("invalid_grant", "The member is no longer active.")
        org = self.db.get(Organization, old.org_id)
        if org is None or org.agent_access == "off":
            raise OAuthError("invalid_grant",
                             "Agent access is switched off for this school.")

        now = datetime.now(UTC)
        old.revoked_at = now
        old.refresh_token_hash = None  # free the unique index
        row, access, refresh_raw = self._mint(
            list(old.scopes), org_id=old.org_id, membership_id=old.membership_id,
            client=client, grant_id=old.grant_id, audience=old.audience,
            name=old.name)
        client.last_used_at = now
        return self._token_response(row, access, refresh_raw)

    def _token_response(self, row: ApiToken, access: str, refresh: str) -> dict:
        body = {
            "access_token": access,
            "token_type": "Bearer",
            "refresh_token": refresh,
            "scope": " ".join(row.scopes or []),
        }
        if row.expires_at:
            secs = int((row.expires_at - datetime.now(UTC)).total_seconds())
            body["expires_in"] = max(secs, 1)
        return body

    # -- what the consent screen shows ------------------------------------

    def consent_summary(self, m: CurrentMember, client: OAuthClient,
                        scope: str | None) -> dict:
        """The tools this connection would actually reach, so consent is
        informed rather than a checkbox. Computed through `visible_tools`, so it
        reflects the member's real authority, not the client's wish list."""
        requested = [s for s in (scope or "").split() if s != "offline_access"]
        granted = sorted(set(requested or list(client.scopes)) & set(client.scopes))
        specs = visible_tools(m, scope=set(granted) or None, transport="mcp")
        return {
            "client_name": client.name,
            "org_name": m.org.name,
            "member_name": m.user.name,
            "mode": client.mode,
            "scopes": granted,
            "tool_count": len(specs),
            "domains": sorted({s.domain for s in specs}),
            "writes": sorted({s.name for s in specs if s.kind == "write"}),
        }
