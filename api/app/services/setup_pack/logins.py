"""Correcting the staff logins the import generated, before handover.

`StaffImporter` builds a username from the person's name — `asha.rao`, plus a
digit when that is taken globally — and a random password. Both are right often
enough to be worth generating and wrong often enough to be worth correcting: a
school that already has its own employee IDs, a name misspelt in the pack, or
two teachers whose slug collided and became `asha.rao` and `asha.rao2`.

This is the one window in which a password can be **chosen**. After it the hash
is all that exists, and the only move is a reset — which is why the import
screen shows the generated ones once and why this screen sits beside it.

Three rules the save enforces, none of them optional:

* **`users.username` is GLOBAL.** It is a `CITEXT UNIQUE` column, so the check
  is case-insensitive and spans every school. `asha.rao` being taken at another
  school is a real clash, and the operator has to pick something else.
* **The operator is not staff.** `core/staff.py::not_operator` keeps the
  vendor's own account off every roster; here it also means the operator cannot
  rename or re-password themselves through a school's setup screen.
* **All or nothing.** A partial rename is worse than a refused one — half the
  staff hold logins from the sheet the operator printed and half do not. One
  failure raises, and the caller's transaction takes the whole batch back.
"""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.core.staff import not_operator
from app.models import Membership, User
from app.schemas.setup_pack import (
    StaffLoginIn,
    StaffLoginRowOut,
    StaffLoginsResult,
    UsernameCheckOut,
)

# The same charset `StaffImporter` slugs down to, stated once as a rule rather
# than twice as a `re.sub`: lowercase letters, digits, dot, underscore, hyphen.
USERNAME_RE = re.compile(r"^[a-z0-9._-]+$")
MIN_USERNAME = 3
MAX_USERNAME = 40
MIN_PASSWORD = 8


def normalise_username(raw: str) -> str:
    """Lowercased and trimmed — never *repaired*.

    The importer silently strips what it cannot use because it is processing a
    spreadsheet nobody is watching. Here a person typed it, so a username with a
    space in it is answered rather than quietly turned into something else they
    did not ask for and would hand to a teacher unaware.
    """
    return (raw or "").strip().lower()


def username_problem(username: str) -> str | None:
    """`None` when the shape is fine. Wording is shown to the operator."""
    if len(username) < MIN_USERNAME:
        return f"Too short — at least {MIN_USERNAME} characters."
    if len(username) > MAX_USERNAME:
        return f"Too long — at most {MAX_USERNAME} characters."
    if not USERNAME_RE.match(username):
        return "Letters, numbers, dot, underscore and hyphen only."
    return None


class StaffLoginService:
    def __init__(self, db: Session):
        self.db = db

    # ── reads ────────────────────────────────────────────────────────────────
    def _staff(self, org_id: uuid.UUID) -> list[tuple[Membership, User]]:
        return list(self.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id,
                   Membership.status == "active",
                   not_operator())
            .order_by(User.name)).all())

    def list_logins(self, org_id: uuid.UUID) -> list[StaffLoginRowOut]:
        """Every staff account this school has, with the username each signs in
        with. Deliberately re-read from the database rather than replayed from
        the import response — the operator reloads the page, and a list that
        only exists in a React state is a list that vanishes."""
        return [
            StaffLoginRowOut(user_id=u.id, name=u.name, username=u.username,
                             org_role=mem.org_role)
            for mem, u in self._staff(org_id)
        ]

    def _taken_by_other(self, username: str, user_id: uuid.UUID) -> bool:
        """`username` is CITEXT, so `==` is already case-insensitive — comparing
        `func.lower()` here would be both redundant and unable to use the
        column's unique index."""
        return self.db.scalar(
            select(User.id).where(User.username == username,
                                  User.id != user_id)) is not None

    def check_username(
        self, username: str, *, for_user_id: uuid.UUID | None = None
    ) -> UsernameCheckOut:
        """What the edit screen calls as the operator types. Answers rather than
        errors: an unavailable username is a normal state of the form, not a
        failed request."""
        name = normalise_username(username)
        problem = username_problem(name)
        if problem:
            return UsernameCheckOut(username=name, available=False, reason=problem)
        # A zero-uuid stand-in keeps one code path for "checking for nobody in
        # particular" — no user has it, so nothing is ever excluded.
        owner = for_user_id or uuid.UUID(int=0)
        if self._taken_by_other(name, owner):
            return UsernameCheckOut(
                username=name, available=False,
                reason="Already taken — usernames are shared across every school.")
        return UsernameCheckOut(username=name, available=True)

    # ── the write ────────────────────────────────────────────────────────────
    def save(
        self, m: CurrentMember, org_id: uuid.UUID, logins: list[StaffLoginIn]
    ) -> StaffLoginsResult:
        """Apply the whole batch or none of it.

        `m` is the operator acting inside the school (`SchoolSetupService._context`
        has already pointed RLS at it). Every id is re-checked against that org's
        own staff, so a user_id from another school is a 404 rather than a
        cross-tenant rename.
        """
        by_id = {u.id: (mem, u) for mem, u in self._staff(org_id)}
        renamed = passwords_set = 0
        seen: dict[str, uuid.UUID] = {}

        for row in logins:
            found = by_id.get(row.user_id)
            if found is None:
                raise NotFoundError("Staff member")
            _, user = found

            name = normalise_username(row.username)
            problem = username_problem(name)
            if problem:
                raise ValidationError(f"{user.name}: {problem}")

            # Two rows claiming one username would otherwise depend on which
            # order they flushed in, and the loser would get a unique-violation
            # 500 rather than a sentence naming both people.
            clash = seen.get(name)
            if clash is not None and clash != row.user_id:
                raise ConflictError(
                    f"Two people were given the username {name}.", code="duplicate")
            seen[name] = row.user_id

            if user.username is None or normalise_username(user.username) != name:
                if self._taken_by_other(name, user.id):
                    raise ConflictError(
                        f"The username {name} is already taken.", code="duplicate")
                user.username = name
                renamed += 1

            if row.password is not None and row.password.strip():
                if len(row.password) < MIN_PASSWORD:
                    raise ValidationError(
                        f"{user.name}: a password needs at least "
                        f"{MIN_PASSWORD} characters.")
                user.password_hash = hash_password(row.password)
                # Still a temp password, exactly like the generated one: the
                # operator is choosing what to write on the handover sheet, not
                # choosing the teacher's own password for her.
                user.must_set_password = True
                passwords_set += 1

        self.db.flush()
        return StaffLoginsResult(
            saved=len(logins), renamed=renamed, passwords_set=passwords_set,
            rows=self.list_logins(org_id))
