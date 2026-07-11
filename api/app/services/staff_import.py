"""Staff/teacher document importer (V2-P7, SPRD2 §5.1).

Mirrors the roster importer's stateless analyze → confirm → commit flow. Creates
teacher accounts, then resolves any assignment hints ("6-A Mathematics; 6-B
Mathematics") against classes and subjects that already exist.

Assignment resolution is deterministic and **never guesses**: a hint that names a
class or subject we don't have comes back in `unresolved` for the admin to fix on
the class-subject screen. Half-assigning a teacher is worse than not assigning her,
because nobody notices.
"""

import re
import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.security import hash_password
from app.models import ClassSubject, Membership, SchoolClass, Subject, User
from app.services.ingest import FieldSpec, build_analysis
from app.services.roster_import import read_first_sheet

SPECS = [
    FieldSpec("full_name", ["teacher name", "name", "staff name", "full name", "teacher"],
              required=True, label="name"),
    FieldSpec("username", ["username", "user name", "login", "user id", "employee id", "emp id"],
              label="username / employee id"),
    FieldSpec("email", ["email", "e-mail", "mail"], label="email"),
    FieldSpec("phone", ["mobile", "phone", "contact", "mobile no"], label="phone number"),
    FieldSpec("assignments", ["assignments", "classes", "class & subject", "subjects taught",
                              "class subject", "teaches"],
              label="classes and subjects they teach"),
]

_ASSIGN_SPLIT = re.compile(r"[;,/|\n]+")
# "6-A Mathematics", "6A Maths", "Class 6 - A : Science"
_ASSIGN_ROW = re.compile(r"^\s*(?:class\s*)?([0-9]{1,2}|[ivxIVX]+|[A-Za-z]+)\s*[-–:\s]?\s*([A-Za-z])?\s+(.+?)\s*$")
# Optional trailing periods/week: "6-A Mathematics x6", "6-A Maths (6)", "… *6"
_ASSIGN_PPW = re.compile(r"\s*(?:[x×*]\s*(\d{1,2})|\((\d{1,2})\))\s*$")


def analyze(data: bytes) -> dict[str, Any]:
    columns, rows = read_first_sheet(data)
    return build_analysis("staff", columns, rows, SPECS).as_dict()


def _slugify_username(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".")
    return base[:40] or "teacher"


class StaffImporter:
    def __init__(self, db: Session):
        self.db = db

    def _class_map(self, org_id: uuid.UUID, year_id: uuid.UUID | None) -> dict[tuple, uuid.UUID]:
        if year_id is None:
            return {}
        rows = self.db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == org_id, SchoolClass.academic_year_id == year_id))
        return {(c.name.strip().lower(), (c.section or "").strip().lower()): c.id for c in rows}

    def _subject_map(self, org_id: uuid.UUID) -> dict[str, uuid.UUID]:
        return {s.name.strip().lower(): s.id
                for s in self.db.scalars(select(Subject).where(Subject.org_id == org_id))}

    def _unique_username(self, base: str, taken: set[str]) -> str:
        uname, n = base, 1
        while uname in taken or self.db.scalar(select(User.id).where(User.username == uname)):
            n += 1
            uname = f"{base}{n}"
        taken.add(uname)
        return uname

    def _resolve(self, raw: str, classes: dict, subjects: dict,
                 ) -> tuple[list[tuple[uuid.UUID, uuid.UUID, int | None]], list[str]]:
        """"6-A Mathematics x6; 6-B Maths" → [(class_id, subject_id, periods_per_week
        or None)], plus what failed. The x6/(6) suffix is how a staff sheet carries
        each subject's weekly period budget in the same cell as the assignment."""
        ok: list[tuple[uuid.UUID, uuid.UUID, int | None]] = []
        bad: list[str] = []
        for chunk in _ASSIGN_SPLIT.split(raw):
            token = chunk.strip()
            if not token:
                continue
            ppw: int | None = None
            suffix = _ASSIGN_PPW.search(token)
            if suffix:
                ppw = int(suffix.group(1) or suffix.group(2))
                token = token[: suffix.start()].strip()
            m = _ASSIGN_ROW.match(token)
            if not m:
                bad.append(token)
                continue
            cname, section, subject = m.group(1), (m.group(2) or ""), m.group(3)
            class_id = classes.get((cname.lower(), section.lower()))
            subject_id = subjects.get(subject.strip().lower())
            if class_id is None or subject_id is None:
                bad.append(token)
                continue
            ok.append((class_id, subject_id, ppw))
        return ok, bad

    def commit(self, m: CurrentMember, *, mapping: dict[str, str], rows: list[dict],
               academic_year_id: uuid.UUID | None, default_password: str | None = None,
               ) -> dict[str, Any]:
        classes = self._class_map(m.org_id, academic_year_id)
        subjects = self._subject_map(m.org_id)
        taken: set[str] = set()
        created: list[dict] = []
        skipped = 0
        errors: list[dict] = []
        unresolved: list[dict] = []
        assigned = 0

        def val(row: dict, field: str) -> str | None:
            col = mapping.get(field)
            v = row.get(col) if col else None
            return v.strip() if isinstance(v, str) and v.strip() else None

        # Identity for a staff sheet is the person's name *within this org*, not the
        # username: `users.username` is GLOBAL, so "ramesh.kumar" being taken tells
        # us nothing about whether this school already has a Ramesh Kumar. Keying
        # the skip on the username would silently deny an account to a real teacher
        # whose name happens to be used at another school.
        # Consequence, accepted: two genuinely different teachers with identical
        # names in one school import as one, and the admin adds the second by hand.
        # That beats silently creating two accounts nobody can tell apart.
        existing_names = {
            (n or "").strip().lower() for n in self.db.scalars(
                select(User.name).join(Membership, Membership.user_id == User.id)
                .where(Membership.org_id == m.org_id))}

        for idx, row in enumerate(rows):
            name = val(row, "full_name")
            if not name:
                errors.append({"row": idx + 1, "reason": "missing name"})
                continue
            if name.strip().lower() in existing_names:
                skipped += 1
                continue
            existing_names.add(name.strip().lower())

            uname = (val(row, "username") or _slugify_username(name)).lower()
            uname = re.sub(r"[^a-z0-9._-]+", "", uname) or _slugify_username(name)
            uname = self._unique_username(uname, taken)

            password = default_password or secrets.token_urlsafe(9)
            # `users.email` is globally unique. A duplicate here means the address is
            # already in use (often the same teacher in a second school), so drop it
            # rather than fail the row — the username is the login that matters.
            email = val(row, "email")
            if email and self.db.scalar(select(User.id).where(User.email == email)):
                email = None
            user = User(name=name, username=uname, email=email,
                        password_hash=hash_password(password), must_set_password=True)
            self.db.add(user)
            self.db.flush()
            membership = Membership(org_id=m.org_id, user_id=user.id, org_role="teacher",
                                    status="active")
            self.db.add(membership)
            self.db.flush()
            created.append({"name": name, "username": uname, "password": password,
                            "user_id": str(user.id)})

            raw = val(row, "assignments")
            if raw:
                pairs, bad = self._resolve(raw, classes, subjects)
                for class_id, subject_id, ppw in pairs:
                    cs = self.db.scalar(select(ClassSubject).where(
                        ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
                        ClassSubject.subject_id == subject_id))
                    if cs is None:
                        cs = ClassSubject(org_id=m.org_id, class_id=class_id,
                                          subject_id=subject_id, periods_per_week=ppw or 0)
                        self.db.add(cs)
                    elif ppw:
                        cs.periods_per_week = ppw
                    cs.teacher_member_id = membership.id
                    assigned += 1
                if bad:
                    unresolved.append({"teacher": name, "tokens": bad})
            self.db.flush()

        return {"created": created, "created_count": len(created), "skipped": skipped,
                "assigned": assigned, "errors": errors, "unresolved": unresolved}
