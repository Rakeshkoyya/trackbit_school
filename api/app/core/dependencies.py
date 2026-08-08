"""FastAPI dependencies: DB session, authenticated member, admin guard."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember, CurrentParent
from app.core.database import get_db
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.models import Guardian, Membership, Organization, Student, User

_bearer = HTTPBearer(auto_error=False)


def _engage_rls(db: Session, org_id: uuid.UUID) -> None:
    """Scope this transaction to the org so the RLS safety net applies."""
    db.execute(
        text("SELECT set_config('app.current_org_id', :oid, true)"),
        {"oid": str(org_id)},
    )


def _touch_last_active(db: Session, membership: Membership) -> None:
    """Throttled heartbeat — write at most once per LAST_ACTIVE_THROTTLE_SECONDS."""
    now = datetime.now(UTC)
    last = membership.last_active_at
    if last is None or (now - last) > timedelta(seconds=settings.LAST_ACTIVE_THROTTLE_SECONDS):
        membership.last_active_at = now


def get_current_member(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentMember:
    if creds is None or not creds.credentials:
        raise AuthError("Authentication required.", code="missing_token")

    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.", code="bad_token") from exc

    try:
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
        token_version = int(payload["tv"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthError("Malformed authentication token.", code="bad_token") from exc

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org_id,
            Membership.status == "active",
        )
    )
    if membership is None:
        raise AuthError("You are no longer a member of this organization.", code="revoked")
    # token_version bumps on removal/role change — invalidates old access tokens (G11).
    if membership.token_version != token_version:
        raise AuthError("Session is no longer valid. Please sign in again.", code="revoked")

    _engage_rls(db, org_id)
    user = db.get(User, user_id)
    org = db.get(Organization, org_id)
    _touch_last_active(db, membership)

    return CurrentMember(user=user, org=org, membership=membership)


def _decode_payload(creds: HTTPAuthorizationCredentials | None) -> dict:
    if creds is None or not creds.credentials:
        raise AuthError("Authentication required.", code="missing_token")
    try:
        return decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.", code="bad_token") from exc


def get_current_parent(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentParent:
    """Parent-portal principal. Only tokens minted with role='parent' pass —
    staff sessions never reach parent endpoints (and parent sessions fail
    get_current_member because parents have no membership).

    Revocation is live: no active-student guardian link in this org => 401,
    so an admin deleting/re-phoning a guardian ends the session at once."""
    payload = _decode_payload(creds)
    if payload.get("role") != "parent":
        raise AuthError("This action needs a parent login.", code="not_parent")
    try:
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthError("Malformed authentication token.", code="bad_token") from exc

    _engage_rls(db, org_id)
    org = db.get(Organization, org_id)
    user = db.get(User, user_id)
    if org is None or user is None or not org.parent_portal_enabled:
        raise AuthError("Session is no longer valid.", code="revoked")
    students = list(db.scalars(
        select(Student)
        .join(Guardian, Guardian.student_id == Student.id)
        .where(Guardian.org_id == org_id, Guardian.user_id == user_id,
               Student.status == "active")
        .distinct()
    ))
    if not students:
        raise AuthError("Session is no longer valid.", code="revoked")
    return CurrentParent(user=user, org=org, students=students)


def get_current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentMember | CurrentParent:
    """Member OR parent, decided by the token's role claim. Only for surfaces
    genuinely shared by both (e.g. /auth/me); feature endpoints keep the
    specific guard."""
    payload = _decode_payload(creds)
    if payload.get("role") == "parent":
        return get_current_parent(creds, db)
    return get_current_member(creds, db)


def require_super_admin(
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> CurrentMember:
    """Platform operator (users.is_super_admin) — the layer ABOVE orgs.

    Platform endpoints read/write across organizations by design, so this lifts
    the request's RLS org scope after verifying the flag. The platform service
    is then responsible for its own explicit org handling."""
    if not member.user.is_super_admin:
        raise ForbiddenError("This action requires the platform operator.",
                             code="super_admin_only")
    db.execute(text("SELECT set_config('app.current_org_id', '', true)"))
    return member


def require_operator(
    member: CurrentMember = Depends(get_current_member),
) -> CurrentMember:
    """Platform operator, acting INSIDE one school (SETUP-REDESIGN-PLAN §6, G4).

    The school's *structure* — its year and terms, classes, subjects, who teaches
    what, the syllabus, the timetable, the plan lock — is set up by us and changed
    by us (D-1, founder 2026-08-07). The school keeps everything about *people*
    and every daily action: admitting a student, adding a staff member, marking
    attendance, logging homework, collecting fees.

    **Handover is the gate**, quoting the founder exactly: *"there will be no
    setup screen or anything like that for the school admin once we handed over;
    only we super admin can edit to change the data."* So:

      * the operator may always change structure, in any school;
      * the school's own admin may, until `handed_over_at` is stamped. That
        window is the build, and it is how fifty existing suites — which create
        classes and subjects to have something to test against — keep working
        without pretending to be the platform operator;
      * after handover the school is live, and structure freezes.

    Freezing on handover rather than on role is also the honest reading of what
    the flag is for. An org nobody has handed over is a half-built thing; an org
    that has been handed over has teachers logging against its plan, and a
    deleted class or a renamed subject there is a data-loss event, not an edit.

    Deliberately NOT `require_super_admin`, which blanks `app.current_org_id`.
    That is right for platform endpoints reading across every school and wrong
    here: these are ordinary org-scoped writes, and with the GUC blanked every
    `WITH CHECK` policy would reject them. This keeps the scope
    `get_current_member` already engaged, so law 2 applies to the operator
    exactly as it does to anyone else.
    """
    if member.user.is_super_admin:
        return member
    if member.is_admin and member.org.handed_over_at is None:
        return member
    raise ForbiddenError(
        "Setup is handled by TrackBit. Send us the change and we will make it.",
        code="operator_only")


@dataclass
class AgentPrincipal:
    """A connector acting with a member's authority (`D-97`).

    Not a `CurrentMember` on purpose: an agent call carries two extra facts a
    human session does not have — which toolsets the credential grants, and
    whether it may write at all — and those must be passed explicitly into
    `visible_tools()` rather than inferred from the member.
    """

    member: CurrentMember
    token_id: uuid.UUID
    scopes: frozenset[str]
    mode: str  # "read" | "read_write"

    @property
    def can_write(self) -> bool:
        return self.mode == "read_write"


def get_agent_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AgentPrincipal:
    """Authenticate an agent connector token (`tbk_live_...` / `tbk_test_...`).

    A separate door from `get_current_member`, deliberately: this one accepts
    *only* an opaque connector token, never a human's JWT, so a stolen browser
    session cannot be replayed against the agent surface and a connector token
    cannot be used to drive the web app.
    """
    from app.services.api_tokens import ApiTokenService  # noqa: PLC0415 (cycle)

    if creds is None or not creds.credentials:
        raise AuthError("Authentication required.", code="missing_token")
    ip = request.client.host if request.client else None
    member, token = ApiTokenService(db).resolve(creds.credentials, ip=ip)
    # The same safety net the human path engages, from the token's own org_id —
    # which came from the database, never from the request (law 1).
    _engage_rls(db, member.org_id)
    return AgentPrincipal(
        member=member,
        token_id=token.id,
        scopes=frozenset(token.scopes or []),
        mode=token.mode,
    )


def require_admin(member: CurrentMember = Depends(get_current_member)) -> CurrentMember:
    if not member.is_admin:
        raise ForbiddenError("This action requires an admin.", code="admin_only")
    return member


def require_coordinator_up(
    member: CurrentMember = Depends(get_current_member),
) -> CurrentMember:
    """Admin-only in v2 (SPRD v2 §2) — plan upkeep, approvals, marks verification."""
    if not member.is_coordinator_up:
        raise ForbiddenError("This action requires an admin.", code="admin_only")
    return member


def require_academic(
    member: CurrentMember = Depends(get_current_member),
) -> CurrentMember:
    """admin | teacher — academic capture/read (every v2 member is academic staff)."""
    if not member.is_academic:
        raise ForbiddenError("This is an academic-staff action.", code="academic_only")
    return member


def require_office_up(
    member: CurrentMember = Depends(get_current_member),
) -> CurrentMember:
    """Admin-only in v2 (SPRD v2 §2) — fees. Teachers never reach this."""
    if not member.is_office_up:
        raise ForbiddenError("This action requires an admin.", code="admin_only")
    return member
