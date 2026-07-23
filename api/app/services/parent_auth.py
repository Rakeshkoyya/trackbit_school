"""Parent login: phone OTP → guardian match → parent session (parent portal).

A parent is not a Membership — staff roles and the Members screen stay
untouched. Identity is the phone number: at verify time every guardian row
with that number is linked to one User (guardians.user_id), and the session
token carries role='parent' + the org, so law 1 (org from the verified token)
holds for parents exactly as for staff. Optional username/email+password can
be added later from the profile; OTP remains available forever.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthError, ConflictError, ForbiddenError, ValidationError
from app.core.security import create_access_token, hash_password, hash_token
from app.models import Guardian, Organization, OtpCode, SchoolClass, Student, User
from app.services.otp_delivery import send_otp


def _now() -> datetime:
    return datetime.now(UTC)


def phone_key(raw: str | None) -> str:
    """Normalized matching key: the last 10 digits (Indian mobiles). Ignores
    +91 / 0-prefix / spacing differences between the roster and the login form."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else digits


def to_e164(raw: str) -> str:
    """Best-effort E.164 for storage/delivery; bare 10-digit numbers are +91."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}"


def _guardian_phone_key_sql():
    return func.right(func.regexp_replace(Guardian.phone, r"\D", "", "g"), 10)


class ParentAuthService:
    def __init__(self, db: Session):
        self.db = db

    # ── guardian lookup ──────────────────────────────────────────────────
    def _matching_links(self, key: str) -> list[tuple[Guardian, Student, Organization]]:
        """Guardian rows for this phone with an active student in a
        portal-enabled org. Runs unauthenticated (like login), so no RLS scope
        is engaged — matching deliberately spans orgs."""
        rows = self.db.execute(
            select(Guardian, Student, Organization)
            .join(Student, Student.id == Guardian.student_id)
            .join(Organization, Organization.id == Guardian.org_id)
            .where(
                _guardian_phone_key_sql() == key,
                Student.status == "active",
                Organization.parent_portal_enabled.is_(True),
            )
            .order_by(Guardian.created_at.desc())
        ).all()
        return [(g, s, o) for g, s, o in rows]

    def parent_org_for(self, user_id: uuid.UUID) -> Organization | None:
        """The org a credentialed parent lands in at password login — their most
        recently linked school with an active student and the portal on."""
        return self.db.scalars(
            select(Organization)
            .join(Guardian, Guardian.org_id == Organization.id)
            .join(Student, Student.id == Guardian.student_id)
            .where(Guardian.user_id == user_id, Student.status == "active",
                   Organization.parent_portal_enabled.is_(True))
            .order_by(Guardian.created_at.desc())
        ).first()

    def has_links(self, user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
        """Does this user still have an active-student guardian link in the org?
        Used by refresh + the parent dependency — revocation is live."""
        return self.db.scalar(
            select(Guardian.id)
            .join(Student, Student.id == Guardian.student_id)
            .join(Organization, Organization.id == Guardian.org_id)
            .where(
                Guardian.user_id == user_id, Guardian.org_id == org_id,
                Student.status == "active",
                Organization.parent_portal_enabled.is_(True),
            ).limit(1)
        ) is not None

    # ── OTP flows ────────────────────────────────────────────────────────
    def request_otp(self, phone: str) -> dict:
        key = phone_key(phone)
        if len(key) < 10:
            raise ValidationError("Enter a valid 10-digit mobile number.", code="bad_phone")
        links = self._matching_links(key)
        if not links:
            raise ForbiddenError(
                "This number isn't registered with a school. "
                "Please contact your school office to update your number.",
                code="phone_not_registered",
            )

        hour_ago = _now() - timedelta(hours=1)
        recent = self.db.scalar(
            select(func.count(OtpCode.id)).where(
                OtpCode.phone_key == key, OtpCode.created_at >= hour_ago)
        )
        if recent >= settings.OTP_MAX_SENDS_PER_HOUR:
            raise ValidationError(
                "Too many codes requested. Please try again in an hour.",
                code="otp_throttled",
            )

        # A new code supersedes any outstanding one — exactly one live code per phone.
        self.db.execute(
            update(OtpCode)
            .where(OtpCode.phone_key == key, OtpCode.consumed_at.is_(None))
            .values(consumed_at=_now())
        )
        code = f"{secrets.randbelow(10**6):06d}"
        self.db.add(OtpCode(
            phone_key=key,
            code_hash=hash_token(f"{key}:{code}"),
            expires_at=_now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        ))
        self.db.flush()
        channel = send_otp(to_e164(phone), code)
        out = {"message": "Code sent.", "channel": channel}
        if settings.OTP_ECHO_IN_RESPONSE:  # dev only — see config
            out["debug_code"] = code
        return out

    def _bump_attempts(self, otp_id: uuid.UUID) -> None:
        """Record a failed attempt in its OWN committed transaction — the
        request that raised the error rolls back, and the lockout counter must
        survive that rollback or brute force gets unlimited tries."""
        from app.core.database import SessionLocal
        with SessionLocal() as s:
            s.execute(update(OtpCode).where(OtpCode.id == otp_id)
                      .values(attempts=OtpCode.attempts + 1))
            s.commit()

    def verify_otp(self, phone: str, code: str) -> dict:
        key = phone_key(phone)
        row = self.db.scalar(
            select(OtpCode)
            .where(OtpCode.phone_key == key, OtpCode.consumed_at.is_(None))
            .order_by(OtpCode.created_at.desc()).limit(1)
        )
        if row is None or row.expires_at <= _now():
            raise AuthError("Code expired or not requested. Request a new one.",
                            code="otp_expired")
        if row.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise AuthError("Too many wrong attempts. Request a new code.",
                            code="otp_locked")
        if row.code_hash != hash_token(f"{key}:{code.strip()}"):
            self._bump_attempts(row.id)
            raise AuthError("Incorrect code. Please check and try again.",
                            code="otp_incorrect")
        row.consumed_at = _now()

        links = self._matching_links(key)
        if not links:
            raise ForbiddenError(
                "This number is no longer linked to an active student.",
                code="phone_not_registered",
            )
        user = self._find_or_create_user(key, links)
        # Claim every guardian row with this phone (across orgs) for this user.
        self.db.execute(
            update(Guardian)
            .where(_guardian_phone_key_sql() == key, Guardian.user_id.is_(None))
            .values(user_id=user.id)
        )
        self.db.flush()
        org = links[0][2]  # most recent link's org; v1 = one school per session
        return self.build_session(user, org)

    def _find_or_create_user(
        self, key: str, links: list[tuple[Guardian, Student, Organization]]
    ) -> User:
        e164 = to_e164(key)
        user = self.db.scalar(select(User).where(
            func.right(func.regexp_replace(func.coalesce(User.phone, ""),
                                           r"\D", "", "g"), 10) == key))
        if user is not None:
            return user
        primary = next((g for g, _, _ in links if g.is_primary), links[0][0])
        user = User(name=primary.name or "Parent", phone=e164)
        self.db.add(user)
        self.db.flush()
        return user

    # ── session ──────────────────────────────────────────────────────────
    def build_session(self, user: User, org: Organization) -> dict:
        # Parents have no membership, hence no token_version; revocation is the
        # live guardian-link check on every request instead.
        access = create_access_token(
            user_id=user.id, org_id=org.id, org_role="parent", token_version=0)
        from app.services.auth import AuthService  # local import — no cycle at module load
        refresh = AuthService(self.db)._issue_refresh_token(user.id, org.id)
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "org_role": "parent",
            "must_set_password": False,
            "is_super_admin": False,
            "user": user,
            "org": org,
            "orgs": [],
        }

    # ── optional credentials (the "techy parent") ────────────────────────
    def set_credentials(self, user: User, *, username: str | None,
                        email: str | None, password: str) -> None:
        if not username and not email:
            raise ValidationError("Choose a username or add an email.",
                                  code="identifier_required")
        if username:
            uname = username.strip().lower()
            if not re.fullmatch(r"[a-z0-9_.]{3,32}", uname):
                raise ValidationError(
                    "Username must be 3–32 characters: letters, numbers, _ or .",
                    code="bad_username")
            taken = self.db.scalar(select(User.id).where(
                User.username == uname, User.id != user.id))
            if taken:
                raise ConflictError("That username is taken.", code="username_taken")
            user.username = uname
        if email:
            taken = self.db.scalar(select(User.id).where(
                User.email == email, User.id != user.id))
            if taken:
                raise ConflictError("An account with this email already exists.",
                                    code="email_taken")
            user.email = email
        user.password_hash = hash_password(password)
        user.must_set_password = False
        self.db.flush()

    # ── children for the signed-in parent ────────────────────────────────
    def children(self, user_id: uuid.UUID, org_id: uuid.UUID) -> list[dict]:
        rows = self.db.execute(
            select(Student, SchoolClass)
            .join(Guardian, Guardian.student_id == Student.id)
            .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
            .where(Guardian.user_id == user_id, Guardian.org_id == org_id,
                   Student.status == "active")
            .order_by(Student.full_name)
        ).unique().all()
        seen: set[uuid.UUID] = set()
        out = []
        for s, k in rows:
            if s.id in seen:
                continue
            seen.add(s.id)
            label = (k.name + (f"-{k.section}" if k.section else "")) if k else None
            out.append({"student_id": s.id, "full_name": s.full_name,
                        "class_label": label, "admission_no": s.admission_no})
        return out
