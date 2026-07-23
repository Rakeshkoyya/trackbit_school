"""FastAPI dependencies: DB session, authenticated member, admin guard."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
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
