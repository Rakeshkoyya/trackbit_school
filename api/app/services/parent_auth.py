"""Parent login (parent portal). Two doors into the same account.

**The front door (`D-13`, V1-11):** school code → class → section → child →
the child's date of birth. It is the one a school can actually hand out — a
line in the diary, printed once, works for every parent including the one whose
number the office recorded wrong. `D-08` removed WhatsApp from this version,
which is what made a login that depends on message delivery untenable.

**The recovery door (`Q-29`):** phone OTP, kept and NOT deleted. It is the more
secure credential, it already works, and it is the only way in for a family
whose child has no date of birth on record — the one case the front door cannot
serve. Kept, not default.

Both doors end in the same place: a User row keyed on the guardian's phone,
every guardian row with that phone claimed (`guardians.user_id`), and a
role='parent' token carrying the org, so law 1 holds for parents exactly as for
staff. `Q-27` — the guardian-phone link stays, and stays the notification
target; the login method changing does not rewrite the account model.

A parent is not a Membership. Staff roles and the Members screen stay untouched.
"""

import re
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthError, ConflictError, ForbiddenError, ValidationError
from app.core.security import create_access_token, hash_password, hash_token
from app.models import (
    AcademicYear,
    Guardian,
    Organization,
    OtpCode,
    ParentLoginAttempt,
    SchoolClass,
    Student,
    User,
)
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


def _label(k: SchoolClass | None) -> str | None:
    """"6" + "B" → "6-B". The one place a class name is composed for a parent."""
    if k is None:
        return None
    return k.name + (f"-{k.section}" if k.section else "")


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

    # ── D-13 · the DOB front door ────────────────────────────────────────
    def school_by_code(self, code: str) -> dict:
        """Step 1: the school code names the school and lists its classes.

        `S-57`/`Q-26` — the code is random, handed to parents and never
        published, which is the whole reason step 3 can be a search box rather
        than a wall. The error says *"we don't recognise that code"* and nothing
        else: never "no such school" with a hint, never a near-match.
        """
        norm = (code or "").strip().upper()
        if len(norm) < 4:
            raise ValidationError("Enter the school code from your school.",
                                  code="bad_school_code")
        org = self.db.scalar(select(Organization).where(
            func.upper(Organization.school_code) == norm,
            Organization.parent_portal_enabled.is_(True)))
        if org is None:
            raise ForbiddenError(
                "We don't recognise that code — please check with the school office.",
                code="school_not_found")
        # Classes of the ACTIVE year only. A parent picking last year's 6-B and
        # landing on an empty portal would look like the school lost their child.
        rows = self.db.execute(
            select(SchoolClass)
            .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
            .where(SchoolClass.org_id == org.id, AcademicYear.is_active.is_(True))
            .order_by(SchoolClass.name, SchoolClass.section)
        ).scalars().all()
        return {
            "org_id": org.id, "school_name": org.name, "school_phone": org.phone,
            "classes": [{"class_id": k.id, "name": k.name, "section": k.section,
                         "label": _label(k)} for k in rows],
        }

    def find_children(self, org_id: uuid.UUID, class_id: uuid.UUID,
                      query: str) -> list[dict]:
        """Step 3 (`S-55`): type-to-search, never a browsable list.

        A dropdown of every child in a section hands the school's roster to
        anyone holding a code, *before* any password is entered. Requiring a few
        characters and capping the results costs a parent nothing — they know
        their own child's name — and removes the harvest.
        """
        q = (query or "").strip()
        if len(q) < settings.PARENT_CHILD_SEARCH_MIN_CHARS:
            raise ValidationError(
                f"Type at least {settings.PARENT_CHILD_SEARCH_MIN_CHARS} letters "
                "of your child's name.", code="query_too_short")
        rows = self.db.scalars(
            select(Student)
            .where(Student.org_id == org_id, Student.class_id == class_id,
                   Student.status == "active",
                   or_(Student.full_name.ilike(f"%{q}%"),
                       func.lower(Student.admission_no) == q.lower()))
            .order_by(Student.full_name)
            .limit(settings.PARENT_CHILD_SEARCH_MAX_RESULTS)
        ).all()
        return [{"student_id": s.id, "full_name": s.full_name} for s in rows]

    # ── S-56 · the lock, keyed per student ───────────────────────────────
    def _lock_state(self, student_id: uuid.UUID) -> ParentLoginAttempt | None:
        return self.db.scalar(select(ParentLoginAttempt).where(
            ParentLoginAttempt.student_id == student_id))

    def _assert_not_locked(self, student_id: uuid.UUID, org: Organization) -> None:
        row = self._lock_state(student_id)
        if row is None or row.locked_until is None:
            return
        if row.locked_until <= _now():
            return
        raise AuthError(
            "Too many incorrect attempts. Please try again later, or call the "
            "school office.",
            code="parent_login_locked",
            details={"school_phone": org.phone,
                     "locked_until": row.locked_until.isoformat()})

    def _bump_login_attempts(self, student_id: uuid.UUID) -> int:
        """Record a failed DOB attempt in its OWN committed transaction.

        Same reason as `_bump_attempts`: the request that raises the error rolls
        back, and a lockout counter that rolls back with it is not a lockout —
        brute force would get unlimited tries. Returns attempts remaining.
        """
        from app.core.database import SessionLocal
        window = timedelta(minutes=settings.PARENT_LOGIN_LOCK_MINUTES)
        with SessionLocal() as s:
            row = s.scalar(select(ParentLoginAttempt).where(
                ParentLoginAttempt.student_id == student_id).with_for_update())
            now = _now()
            if row is None:
                row = ParentLoginAttempt(student_id=student_id, attempts=1,
                                         window_started_at=now)
                s.add(row)
            elif row.window_started_at + window <= now and (
                    row.locked_until is None or row.locked_until <= now):
                # The window aged out — a parent who mistyped last month starts
                # clean rather than carrying a grudge.
                row.attempts, row.window_started_at, row.locked_until = 1, now, None
            else:
                row.attempts += 1
            if row.attempts >= settings.PARENT_LOGIN_MAX_ATTEMPTS:
                row.locked_until = now + window
            left = max(0, settings.PARENT_LOGIN_MAX_ATTEMPTS - row.attempts)
            s.commit()
            return left

    def _clear_login_attempts(self, student_id: uuid.UUID) -> None:
        row = self._lock_state(student_id)
        if row is not None:
            self.db.delete(row)
            self.db.flush()

    # ── D-13 · step 4, the date of birth ─────────────────────────────────
    def _student_for_login(self, student_id: uuid.UUID) -> tuple[Student, Organization]:
        student = self.db.get(Student, student_id)
        if student is None or student.status != "active":
            raise ForbiddenError("We couldn't find that student.", code="student_not_found")
        org = self.db.get(Organization, student.org_id)
        if org is None or not org.parent_portal_enabled:
            raise ForbiddenError("This school's parent portal is not open yet.",
                                 code="portal_disabled")
        return student, org

    def _check_dob(self, student: Student, org: Organization, dob: date) -> None:
        """The credential check, with the lock around it. Raises on failure."""
        self._assert_not_locked(student.id, org)
        if student.date_of_birth is None:
            # `Q-24` — no DOB on record is the school's gap, not the parent's
            # mistake, and it must NOT burn an attempt. This is exactly the case
            # `Q-29` keeps phone-OTP alive for.
            # The message no longer offers the mobile door. `/parent/login/otp`
            # exists as a page but nothing links to it, so telling a locked-out
            # parent to "sign in with your mobile number" sent them looking for a
            # screen the product does not show. `otp_available` stays in the
            # details for the day that door is wired up again.
            raise AuthError(
                "We don't have your child's date of birth on record, so there is "
                "nothing here to check your answer against. Please ask the school "
                "office to add it — you can sign in as soon as they do.",
                code="dob_not_on_record",
                details={"school_phone": org.phone, "otp_available": True})
        if student.date_of_birth != dob:
            left = self._bump_login_attempts(student.id)
            raise AuthError(
                "That date of birth doesn't match our records."
                + (f" {left} attempt{'s' if left != 1 else ''} remaining." if left else
                   " This login is now locked — please call the school office."),
                code="dob_incorrect",
                details={"attempts_left": left, "school_phone": org.phone})
        self._clear_login_attempts(student.id)

    def verify_dob(self, student_id: uuid.UUID, dob: date) -> dict:
        """The `D-13` login. Proves ONE child and returns a parent session."""
        student, org = self._student_for_login(student_id)
        self._check_dob(student, org, dob)

        guardians = self._guardians_of(student.id)
        if not guardians:
            # Without a guardian row there is nothing to own the account, and
            # nothing to notify. Say so plainly rather than inventing a contact.
            raise ForbiddenError(
                "We don't have a parent contact for this student yet. Please ask "
                "the school office to add one.",
                code="no_guardian_on_record", details={"school_phone": org.phone})
        user = self._user_for_student(student, guardians)
        self._claim_guardians_for_student(student.id, user)
        self.db.flush()
        return self.build_session(user, org)

    def add_child(self, user: User, org_id: uuid.UUID, student_id: uuid.UUID,
                  dob: date) -> dict:
        """`Q-25` (b) — *"Add another child"*, each proved with their own DOB.

        The alternative was a parent of three logging in three times, which is
        how a portal gets abandoned. Once proved, the child joins this account
        and the sibling switcher that already exists works unchanged.

        Same school only: the org comes from the verified token (law 1), and a
        session spans one school in v1.
        """
        student, org = self._student_for_login(student_id)
        if student.org_id != org_id:
            raise ForbiddenError(
                "That child is at a different school. Please sign in with that "
                "school's code.", code="wrong_school")
        self._check_dob(student, org, dob)
        if not self._guardians_of(student.id):
            raise ForbiddenError(
                "We don't have a parent contact for this student yet. Please ask "
                "the school office to add one.",
                code="no_guardian_on_record", details={"school_phone": org.phone})
        self._claim_guardians_for_student(student.id, user)
        self.db.flush()
        return {"student_id": student.id, "full_name": student.full_name}

    def _guardians_of(self, student_id: uuid.UUID) -> list[Guardian]:
        return list(self.db.scalars(select(Guardian).where(
            Guardian.student_id == student_id).order_by(
            Guardian.is_primary.desc(), Guardian.created_at)))

    def _user_for_student(self, student: Student, guardians: list[Guardian]) -> User:
        """Which account does proving this child belong to?

        In order: an account this family already has (any guardian row already
        claimed) → an existing user with the primary guardian's phone → a new
        user. The first rule is what makes a second DOB login on a new device
        land back in the same account instead of forking the family in two.
        """
        for g in guardians:
            if g.user_id is not None:
                existing = self.db.get(User, g.user_id)
                if existing is not None:
                    return existing
        primary = guardians[0]
        key = phone_key(primary.phone)
        if len(key) == 10:
            user = self.db.scalar(select(User).where(
                func.right(func.regexp_replace(func.coalesce(User.phone, ""),
                                               r"\D", "", "g"), 10) == key))
            if user is not None:
                return user
        user = User(name=primary.name or "Parent",
                    phone=to_e164(primary.phone) if len(key) == 10 else None)
        self.db.add(user)
        self.db.flush()
        return user

    def _claim_guardians_for_student(self, student_id: uuid.UUID, user: User) -> None:
        """Claim ONLY this child's guardian rows.

        Deliberately narrower than the OTP path, which claims every row sharing
        the phone: there the phone *is* the proof, so rolling siblings up is
        what was proved. Here the proof is one child's date of birth, so one
        child is what it buys — `Q-25` (b) makes the others an explicit,
        separately-proved step.
        """
        self.db.execute(
            update(Guardian)
            .where(Guardian.student_id == student_id, Guardian.user_id.is_(None))
            .values(user_id=user.id))

    # ── OTP flows (Q-29: kept as the recovery path, not the default) ─────
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
            label = _label(k)
            out.append({"student_id": s.id, "full_name": s.full_name,
                        "class_label": label, "admission_no": s.admission_no})
        return out
