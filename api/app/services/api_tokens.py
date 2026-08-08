"""Agent connector credentials — issue, list, revoke, resolve (`D-97`).

The whole security argument for this module is one sentence: **a token never
exceeds the member who issued it.** `membership_id` is the authority it acts
with, and `scopes` may only narrow that member's toolsets. Everything else here
serves that, or serves revocation.

`resolve()` deliberately repeats the liveness checks `get_current_member` makes
— membership still active, RLS engaged by the caller, the org still permitting
agent access — because a second auth path that forgets one of them is exactly
how a revoked member keeps working. It is written once and called from the
dependency.

**One deliberate deviation from MCP-SERVER-PLAN §4.1, which lists `token_version`
among the checks to repeat.** It is not checked here, and there is no snapshot of
it on the row. `token_version` exists because a **JWT embeds** the role and org,
so a stale one carries stale claims; a connector token embeds nothing — every
fact is read live from the membership on each call. The practical consequence is
the right way round: an admin demoted to teacher loses her connector's admin
tools **immediately**, because `visible_tools()` reads the current role.

What that costs: bumping `token_version` ("sign everyone out") does **not** kill
connectors — only `revoke`, removing the membership, or `agent_access = off` do.
If connectors should die with human sessions, that is a column and a second
migration, and it should be a recorded decision rather than a default.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.exceptions import AuthError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import generate_raw_token, hash_token
from app.models import ApiToken, Membership, Organization, User
from app.services.lucy import domains
from app.services.lucy.registry import visible_tools

# How long a `last_used_at` write is skipped for. Same reasoning as
# `_touch_last_active`: an UPDATE on every authenticated call is write
# amplification, and nobody needs minute-accurate "last used".
LAST_USED_THROTTLE_SECONDS = 300

MODES = ("read", "read_write")
EXPIRY_CHOICES = (30, 90, 365)


def _token_prefix() -> str:
    """`tbk_live_` in a real deployment, `tbk_test_` otherwise. The point of a
    prefix is that a leaked token is greppable in a repo, catchable by secret
    scanning, and recognisable in a log — a JWT looks like every other JWT."""
    return "tbk_test_" if settings.DEBUG else "tbk_live_"


class ApiTokenService:
    def __init__(self, db: Session):
        self.db = db

    # -- issuing ---------------------------------------------------------

    def _assert_may_issue(self, m: CurrentMember) -> None:
        """`D-103`. `off` for a school still being set up, `admins` once live,
        `all_staff` if the school wants teachers to have their own."""
        access = m.org.agent_access
        if access == "off":
            raise ForbiddenError(
                "Agent access is switched off for this school. An admin can "
                "turn it on in Setup → Connections.")
        if access == "admins" and not m.is_admin:
            raise ForbiddenError(
                "Only admins may create an agent connection in this school.")
        if access not in ("admins", "all_staff"):
            raise ForbiddenError("Agent access is not configured.")

    def _narrow_scopes(self, m: CurrentMember, requested: list[str]) -> list[str]:
        """A connector can be narrower than its issuer, never wider.

        A domain the member cannot reach any tool in is refused rather than
        silently dropped: a teacher who thinks she granted `fees` and got
        nothing has been told something false about her own connector.
        """
        unknown = [s for s in requested if s not in domains.DOMAIN_NAMES]
        if unknown:
            raise ValidationError(
                f"Unknown toolset(s): {', '.join(sorted(unknown))}.")
        for name in requested:
            if name in domains.ALWAYS_ON:
                continue
            reachable = [s for s in visible_tools(m, scope={name})
                         if s.domain == name]
            if not reachable:
                raise ForbiddenError(
                    f"You cannot grant the '{name}' toolset — it holds nothing "
                    "you can do yourself. A connector never exceeds the person "
                    "who issued it.")
        return sorted(set(requested) | domains.ALWAYS_ON)

    def issue(self, m: CurrentMember, *, name: str, scopes: list[str],
              mode: str = "read",
              expires_days: int | None = None) -> tuple[ApiToken, str]:
        """Returns the row and **the raw token, which is never stored and never
        recoverable** — the caller shows it once and then it is gone."""
        self._assert_may_issue(m)
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValidationError(
                "Give the connection a name — it is what makes revoking the "
                "right one possible later.")
        if mode not in MODES:
            raise ValidationError(f"mode must be one of {', '.join(MODES)}.")
        if expires_days is not None and expires_days not in EXPIRY_CHOICES:
            raise ValidationError(
                f"expires_days must be one of {EXPIRY_CHOICES}, or omitted "
                "for a token that does not expire.")

        granted = self._narrow_scopes(m, scopes)
        raw = _token_prefix() + generate_raw_token(32)
        row = ApiToken(
            org_id=m.org_id,
            membership_id=m.membership.id,
            name=clean_name,
            token_hash=hash_token(raw),
            prefix=raw[:12],
            scopes=granted,
            mode=mode,
            expires_at=(datetime.now(UTC) + timedelta(days=expires_days)
                        if expires_days else None),
            created_by_membership_id=m.membership.id,
        )
        self.db.add(row)
        self.db.flush()
        return row, raw

    # -- listing and revoking --------------------------------------------

    def list_for(self, m: CurrentMember) -> list[ApiToken]:
        """An admin sees the school's connectors; a teacher sees her own. Law 1:
        org_id comes from the token, never from a param."""
        stmt = select(ApiToken).where(ApiToken.org_id == m.org_id)
        if not m.is_admin:
            stmt = stmt.where(ApiToken.membership_id == m.membership.id)
        return list(self.db.scalars(stmt.order_by(ApiToken.created_at.desc())))

    def revoke(self, m: CurrentMember, token_id: uuid.UUID) -> ApiToken:
        row = self.db.scalar(select(ApiToken).where(
            ApiToken.id == token_id, ApiToken.org_id == m.org_id))
        if row is None:
            raise NotFoundError("Connection", str(token_id))
        if not m.is_admin and row.membership_id != m.membership.id:
            raise ForbiddenError("You can only revoke your own connections.")
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            row.revoked_by_membership_id = m.membership.id
        return row

    # -- resolving -------------------------------------------------------

    def resolve(self, raw: str, *, ip: str | None = None
                ) -> tuple[CurrentMember, ApiToken]:
        """Authenticate a raw connector token.

        Every refusal is the same `AuthError` on purpose: a caller must not be
        able to tell "revoked" from "expired" from "never existed".
        """
        if not raw or not raw.startswith(("tbk_live_", "tbk_test_")):
            raise AuthError("Invalid API token.", code="bad_token")
        row = self.db.scalar(
            select(ApiToken).where(ApiToken.token_hash == hash_token(raw)))
        if row is None:
            raise AuthError("Invalid API token.", code="bad_token")
        if row.revoked_at is not None:
            raise AuthError("Invalid API token.", code="bad_token")
        if row.expires_at is not None and row.expires_at <= datetime.now(UTC):
            raise AuthError("Invalid API token.", code="bad_token")

        membership = self.db.get(Membership, row.membership_id)
        # The same liveness checks a human session makes. A token outliving the
        # membership it was issued against is the failure this prevents.
        if membership is None or membership.status != "active":
            raise AuthError("Invalid API token.", code="bad_token")
        if membership.org_id != row.org_id:
            raise AuthError("Invalid API token.", code="bad_token")

        user = self.db.get(User, membership.user_id)
        org = self.db.get(Organization, row.org_id)
        if user is None or org is None:
            raise AuthError("Invalid API token.", code="bad_token")
        # A school that switched agent access off has switched it off for the
        # tokens already issued, not just for new ones.
        if org.agent_access == "off":
            raise AuthError("Invalid API token.", code="bad_token")

        self._touch(row, ip)
        return CurrentMember(user=user, org=org, membership=membership), row

    def _touch(self, row: ApiToken, ip: str | None) -> None:
        now = datetime.now(UTC)
        last = row.last_used_at
        if last is None or (now - last) > timedelta(
                seconds=LAST_USED_THROTTLE_SECONDS):
            row.last_used_at = now
            if ip:
                row.last_used_ip = ip
