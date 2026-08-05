"""The staff directory (founder, 2026-08-05).

Setup → Members answers *"who can log in"*. This answers *"who works here and
what do they carry"* — the join nobody had ever written, across three tables that
each hold a third of the answer:

  * `memberships` / `users` — the person and their role;
  * `school_classes.class_teacher_member_id` — whose homeroom it is;
  * `class_subjects` — what they teach, where, and for how many periods.

**The class teacher is derived, not stored twice.** `org_role` stays the two-value
column every guard in the app is built on (SPRD2 §2); the directory renders
`role_key = class_teacher` when a person owns a homeroom, and writing that back
assigns the CLASS, never the membership. A `class_teacher` value in `org_role`
would be the same fact in two places, which is the drift V1-0 exists to remove —
and the two would disagree the first time a class was reassigned.

Four queries for the whole screen, however many staff: people, classes,
class-subjects, and the subject names. Never one query per person — the load
figures are exactly the sort of column that grows a loop.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.validators import normalize_username
from app.models import (
    AcademicYear,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    User,
)
from app.schemas.staff_directory import (
    ClassRef,
    StaffDetailOut,
    StaffDirectoryOut,
    StaffRow,
    StaffUpdateIn,
    SubjectRef,
)
from app.services.member import MemberService


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _role_view(org_role: str, homerooms: list[ClassRef]) -> tuple[str, str]:
    """(role_key, role_label) — the pair the Role column renders and writes.

    An admin is shown as an admin even when they also hold a homeroom: the org
    role is the one that decides what they can *do*, and a label that hid it
    would be the more dangerous of the two to get wrong.
    """
    if org_role == "admin":
        if homerooms:
            return "admin", "Admin · class teacher " + ", ".join(
                c.class_label for c in homerooms)
        return "admin", "Admin"
    if homerooms:
        return "class_teacher", "Class teacher · " + ", ".join(
            c.class_label for c in homerooms)
    return "teacher", "Teacher"


class StaffDirectoryService:
    def __init__(self, db: Session):
        self.db = db

    def _year(self, m: CurrentMember) -> AcademicYear | None:
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    # ── the list ─────────────────────────────────────────────────────────────
    def list_staff(self, m: CurrentMember) -> StaffDirectoryOut:
        year = self._year(m)
        people = self.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == m.org_id, Membership.status == "active")
            .order_by(User.name)).all()

        klasses = list(self.db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section,
                   SchoolClass.class_teacher_member_id)
            .where(SchoolClass.org_id == m.org_id,
                   *( [SchoolClass.academic_year_id == year.id] if year else []))
            .order_by(SchoolClass.name, SchoolClass.section)).all())
        class_refs = {
            cid: ClassRef(class_id=cid, class_label=_label(name, section))
            for cid, name, section, _t in klasses
        }
        homerooms: dict[uuid.UUID, list[ClassRef]] = {}
        unowned: list[ClassRef] = []
        for cid, _n, _s, teacher in klasses:
            if teacher:
                homerooms.setdefault(teacher, []).append(class_refs[cid])
            else:
                unowned.append(class_refs[cid])

        taught: dict[uuid.UUID, list[SubjectRef]] = {}
        if class_refs:
            for cs_id, cls_id, sub_id, sub_name, ppw, teacher in self.db.execute(
                select(ClassSubject.id, ClassSubject.class_id, Subject.id, Subject.name,
                       ClassSubject.periods_per_week, ClassSubject.teacher_member_id)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .where(ClassSubject.org_id == m.org_id,
                       ClassSubject.class_id.in_(class_refs.keys()),
                       ClassSubject.teacher_member_id.is_not(None))
                .order_by(Subject.name)
            ).all():
                taught.setdefault(teacher, []).append(SubjectRef(
                    class_subject_id=cs_id, class_id=cls_id,
                    class_label=class_refs[cls_id].class_label,
                    subject_id=sub_id, subject_name=sub_name,
                    periods_per_week=int(ppw or 0)))

        rows = [self._row(mem, user, homerooms.get(mem.id, []),
                          taught.get(mem.id, []), class_refs)
                for mem, user in people]
        return StaffDirectoryOut(
            rows=rows, classes=list(class_refs.values()), total=len(rows),
            admins=sum(1 for r in rows if r.org_role == "admin"),
            teachers=sum(1 for r in rows if r.org_role == "teacher"),
            class_teachers=sum(1 for r in rows if r.class_teacher_of),
            classes_without_teacher=unowned)

    def _row(self, mem: Membership, user: User, homerooms: list[ClassRef],
             subjects: list[SubjectRef], class_refs: dict) -> StaffRow:
        role_key, role_label = _role_view(mem.org_role, homerooms)
        # Every class they are in front of, homeroom or subject — de-duplicated
        # in insertion order so the filter reads the way the row does.
        seen: dict[uuid.UUID, ClassRef] = {c.class_id: c for c in homerooms}
        for s in subjects:
            if s.class_id not in seen and s.class_id in class_refs:
                seen[s.class_id] = class_refs[s.class_id]
        return StaffRow(
            member_id=mem.id, user_id=user.id, name=user.name, email=user.email,
            username=user.username, phone=user.phone,
            date_of_birth=mem.date_of_birth,
            org_role=mem.org_role, role_key=role_key, role_label=role_label,
            status=mem.status,
            pending=bool(user.must_set_password and mem.last_active_at is None),
            last_active_at=mem.last_active_at,
            class_teacher_of=homerooms, classes=list(seen.values()),
            subjects=subjects, subject_count=len(subjects),
            periods_per_week=sum(s.periods_per_week for s in subjects))

    # ── one person ───────────────────────────────────────────────────────────
    def _member(self, m: CurrentMember, member_id: uuid.UUID) -> Membership:
        mem = self.db.scalar(select(Membership).where(
            Membership.id == member_id, Membership.org_id == m.org_id))
        if mem is None:
            raise NotFoundError("Member")
        return mem

    def detail(self, m: CurrentMember, member_id: uuid.UUID) -> StaffDetailOut:
        """An admin reads anyone; a teacher reads only themselves.

        Same rule as the V1-16 record and `/staff/month`: a person whose file is
        being kept must be able to read it, and nobody else's.
        """
        mem = self._member(m, member_id)
        if not m.is_admin and mem.id != m.membership.id:
            raise ForbiddenError("That is not your record.", code="not_your_record")
        board = self.list_staff(m)
        row = next((r for r in board.rows if r.member_id == member_id), None)
        if row is None:
            raise NotFoundError("Member")
        return StaffDetailOut(
            row=row, classes=board.classes, can_edit=m.is_admin,
            is_last_admin=row.org_role == "admin" and board.admins <= 1)

    # ── the one write ────────────────────────────────────────────────────────
    def update(self, m: CurrentMember, member_id: uuid.UUID,
               body: StaffUpdateIn) -> StaffDetailOut:
        """Profile, role and homeroom in one call, because they are one form.

        The role change goes through `MemberService.change_role` rather than
        touching `org_role` here: that is where the last-admin guard and the
        `token_version` bump live, and a second path to the same column would
        eventually skip one of them.
        """
        mem = self._member(m, member_id)
        user = self.db.get(User, mem.user_id)
        if user is None:
            raise NotFoundError("Member")

        if body.name is not None:
            user.name = body.name.strip()
        if body.clear_email:
            user.email = None
        elif body.email is not None:
            email = body.email.strip().lower()
            if email and email != (user.email or "").lower():
                self._assert_free(User.email, email, user.id,
                                  "Another account already uses that email.",
                                  "email_taken")
            user.email = email or None
        if body.clear_phone:
            user.phone = None
        elif body.phone is not None:
            phone = body.phone.strip()
            if phone and phone != (user.phone or ""):
                self._assert_free(User.phone, phone, user.id,
                                  "Another account already uses that number.",
                                  "phone_taken")
            user.phone = phone or None
        if body.username is not None:
            uname = normalize_username(body.username)
            if uname != (user.username or ""):
                self._assert_free(User.username, uname, user.id,
                                  "That username is taken.", "username_taken")
            user.username = uname
        if body.clear_date_of_birth:
            mem.date_of_birth = None
        elif body.date_of_birth is not None:
            mem.date_of_birth = body.date_of_birth

        if body.org_role is not None and body.org_role != mem.org_role:
            MemberService(self.db).change_role(m, mem.user_id, body.org_role)

        if body.class_teacher_of is not None:
            self._set_homerooms(m, mem, body.class_teacher_of)

        self.db.flush()
        return self.detail(m, member_id)

    def _assert_free(self, column, value: str, user_id: uuid.UUID,
                     message: str, code: str) -> None:
        clash = self.db.scalar(select(User.id).where(column == value, User.id != user_id))
        if clash is not None:
            raise ConflictError(message, code=code)

    def _set_homerooms(self, m: CurrentMember, mem: Membership,
                       class_ids: list[uuid.UUID]) -> None:
        """Full replace: after this, they are class teacher of exactly these.

        Assigning a class that already has a different class teacher REPLACES
        them, and that is deliberate — a homeroom has exactly one owner, and a
        screen that silently refused would leave the admin unable to hand a class
        over without first knowing to go and unassign the previous teacher.
        """
        year = self._year(m)
        wanted = set(class_ids)
        if wanted:
            found = list(self.db.scalars(select(SchoolClass).where(
                SchoolClass.org_id == m.org_id, SchoolClass.id.in_(wanted),
                *([SchoolClass.academic_year_id == year.id] if year else []))))
            if len(found) != len(wanted):
                raise ValidationError("One of those classes is not in this year.",
                                      code="unknown_class")
            for klass in found:
                klass.class_teacher_member_id = mem.id
        # Anything they held and no longer should.
        for klass in self.db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == m.org_id,
            SchoolClass.class_teacher_member_id == mem.id,
        )):
            if klass.id not in wanted:
                klass.class_teacher_member_id = None
        self.db.flush()
