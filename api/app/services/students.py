"""Students / guardians / categories CRUD (SPRD §4.2).

The single student master shared by fees and academics. Every query is org-scoped
explicitly. Guardians are records only (parents have no login, v1) and carry the
opt-out consent flag honoured by all outbound messaging (SPRD §3.4 / §7).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    Guardian,
    SchoolClass,
    Student,
    StudentCategory,
)
from app.models import (
    Session as SessionModel,
)
from app.schemas.students import (
    CategoryCreate,
    CategoryOut,
    GuardianCreate,
    GuardianOut,
    GuardianUpdate,
    StudentCreate,
    StudentDetailOut,
    StudentOut,
    StudentUpdate,
)

DEFAULT_CATEGORIES = ("Day Scholar", "Hosteller")  # SPRD §4.2 seed


class StudentService:
    def __init__(self, db: Session):
        self.db = db

    def _student(self, org_id: uuid.UUID, student_id: uuid.UUID) -> Student:
        s = self.db.scalar(
            select(Student).where(Student.id == student_id, Student.org_id == org_id)
        )
        if s is None:
            raise NotFoundError("Student")
        return s

    # ── categories ───────────────────────────────────────────────────────────
    def list_categories(self, m: CurrentMember) -> list[CategoryOut]:
        """Every category the school has, with what currently depends on it.

        The counts are not decoration: Settings has to be able to say *"12
        students and 2 blocks use this"* **before** somebody removes it, because
        removing one silently un-assigns every student on it (`D-129`).
        """
        rows = list(self.db.scalars(
            select(StudentCategory).where(StudentCategory.org_id == m.org_id)
            .order_by(StudentCategory.name)
        ))
        ids = [r.id for r in rows]
        students: dict[uuid.UUID, int] = {}
        blocks: dict[uuid.UUID, int] = {}
        if ids:
            # Two grouped queries, never one per row — the DB may be remote.
            for cid, n in self.db.execute(
                    select(Student.category_id, func.count(Student.id))
                    .where(Student.org_id == m.org_id,
                           Student.category_id.in_(ids),
                           Student.status == "active")
                    .group_by(Student.category_id)).all():
                students[cid] = n
            for cid, n in self.db.execute(
                    select(SessionModel.category_id, func.count(SessionModel.id))
                    .where(SessionModel.org_id == m.org_id,
                           SessionModel.category_id.in_(ids))
                    .group_by(SessionModel.category_id)).all():
                blocks[cid] = n
        return [
            CategoryOut(id=r.id, name=r.name,
                        student_count=students.get(r.id, 0),
                        block_count=blocks.get(r.id, 0))
            for r in rows
        ]

    def rename_category(self, m: CurrentMember, category_id: uuid.UUID,
                        name: str) -> CategoryOut:
        """Rename in place — every reference is by id, so nothing breaks.

        This is the whole point of `D-129`. Before it, a block that served
        hostellers found them by matching the category NAME against the literal
        "hosteller", so this rename would have emptied every hostel roster in
        the school without a word.
        """
        cat = self.db.scalar(
            select(StudentCategory).where(
                StudentCategory.id == category_id, StudentCategory.org_id == m.org_id
            )
        )
        if cat is None:
            raise NotFoundError("Category")
        name = name.strip()
        clash = self.db.scalar(
            select(StudentCategory.id).where(
                StudentCategory.org_id == m.org_id, StudentCategory.name == name,
                StudentCategory.id != category_id))
        if clash:
            raise ConflictError(f"“{name}” already exists.", code="duplicate")
        cat.name = name
        self.db.flush()
        return CategoryOut.model_validate(cat)

    def ensure_default_categories(self, m: CurrentMember) -> list[CategoryOut]:
        """Idempotently seed the two default fee categories for a new org."""
        existing = {
            c.name for c in self.db.scalars(
                select(StudentCategory).where(StudentCategory.org_id == m.org_id)
            )
        }
        for name in DEFAULT_CATEGORIES:
            if name not in existing:
                self.db.add(StudentCategory(org_id=m.org_id, name=name))
        self.db.flush()
        return self.list_categories(m)

    def create_category(self, m: CurrentMember, body: CategoryCreate) -> CategoryOut:
        dup = self.db.scalar(
            select(StudentCategory.id).where(
                StudentCategory.org_id == m.org_id, StudentCategory.name == body.name
            )
        )
        if dup:
            raise ConflictError(f"“{body.name}” already exists.", code="duplicate")
        cat = StudentCategory(org_id=m.org_id, name=body.name)
        self.db.add(cat)
        self.db.flush()
        return CategoryOut.model_validate(cat)

    def delete_category(self, m: CurrentMember, category_id: uuid.UUID,
                        force: bool = False) -> None:
        """Remove a category. Refused while it is in use, unless forced.

        The FK is ON DELETE SET NULL, so deleting one quietly un-assigns every
        student on it and reopens every block restricted to it. That is a fine
        thing to allow and a terrible thing to do by accident, so a category
        that is in use needs `force` — and the error carries the counts, which
        is what the confirmation on screen is built from.
        """
        cat = self.db.scalar(
            select(StudentCategory).where(
                StudentCategory.id == category_id, StudentCategory.org_id == m.org_id
            )
        )
        if cat is None:
            raise NotFoundError("Category")
        if not force:
            students = self.db.scalar(
                select(func.count(Student.id)).where(
                    Student.org_id == m.org_id, Student.category_id == category_id,
                    Student.status == "active")) or 0
            blocks = self.db.scalar(
                select(func.count(SessionModel.id)).where(
                    SessionModel.org_id == m.org_id,
                    SessionModel.category_id == category_id)) or 0
            if students or blocks:
                bits = []
                if students:
                    bits.append(f"{students} student{'' if students == 1 else 's'}")
                if blocks:
                    bits.append(f"{blocks} block{'' if blocks == 1 else 's'}")
                raise ConflictError(
                    f"“{cat.name}” is still used by {' and '.join(bits)}. "
                    "Removing it un-assigns them.", code="category_in_use")
        self.db.delete(cat)  # students.category_id -> NULL via FK ON DELETE SET NULL

    # ── students ─────────────────────────────────────────────────────────────
    def list_students(
        self, m: CurrentMember, *, class_id: uuid.UUID | None, query: str | None
    ) -> list[StudentOut]:
        q = select(Student).where(Student.org_id == m.org_id)
        if class_id is not None:
            q = q.where(Student.class_id == class_id)
        if query:
            like = f"%{query.strip()}%"
            q = q.where(Student.full_name.ilike(like) | Student.admission_no.ilike(like))
        q = q.order_by(Student.full_name)
        return [StudentOut.model_validate(r) for r in self.db.scalars(q)]

    def _assert_admission_free(
        self, org_id: uuid.UUID, admission_no: str, *, exclude: uuid.UUID | None = None
    ) -> None:
        """`(org_id, admission_no)` is unique, so both the create and the
        correction have to ask. `exclude` is the student being edited — without
        it, re-saving a record with its own number reads as a clash."""
        q = select(Student.id).where(
            Student.org_id == org_id, Student.admission_no == admission_no
        )
        if exclude is not None:
            q = q.where(Student.id != exclude)
        if self.db.scalar(q):
            raise ConflictError(
                f"Admission no. {admission_no} is already used.", code="duplicate"
            )

    def create_student(self, m: CurrentMember, body: StudentCreate) -> StudentDetailOut:
        self._assert_admission_free(m.org_id, body.admission_no)
        if body.class_id is not None:
            self._scoped_class(m.org_id, body.class_id)
        if body.category_id is not None:
            self._scoped_category(m.org_id, body.category_id)
        student = Student(
            org_id=m.org_id, admission_no=body.admission_no, full_name=body.full_name,
            class_id=body.class_id, roll_no=body.roll_no, category_id=body.category_id,
            date_of_birth=body.date_of_birth,
        )
        self.db.add(student)
        self.db.flush()
        for g in body.guardians:
            self.db.add(self._new_guardian(m.org_id, student.id, g))
        self.db.flush()
        return self.get_student(m, student.id)

    def update_student(
        self, m: CurrentMember, student_id: uuid.UUID, body: StudentUpdate
    ) -> StudentDetailOut:
        student = self._student(m.org_id, student_id)
        data = body.model_dump(exclude_unset=True)
        # A correction, not a rename with consequences: every foreign key in the
        # product points at `students.id`. The one thing that does follow the
        # number is the parent portal sign-in, which looks a child up by it
        # (`services/parent_auth.py`) — hence the warning on the edit form.
        if data.get("admission_no") is not None:
            data["admission_no"] = data["admission_no"].strip()
            if not data["admission_no"]:
                raise ValidationError("An admission number cannot be blank.")
            if data["admission_no"] != student.admission_no:
                self._assert_admission_free(
                    m.org_id, data["admission_no"], exclude=student_id
                )
        if data.get("class_id") is not None:
            self._scoped_class(m.org_id, data["class_id"])
        if data.get("category_id") is not None:
            self._scoped_category(m.org_id, data["category_id"])
        for k, v in data.items():
            setattr(student, k, v)
        self.db.flush()
        return self.get_student(m, student_id)

    def delete_student(self, m: CurrentMember, student_id: uuid.UUID) -> None:
        self.db.delete(self._student(m.org_id, student_id))  # guardians cascade

    def get_student(self, m: CurrentMember, student_id: uuid.UUID) -> StudentDetailOut:
        student = self._student(m.org_id, student_id)
        detail = StudentDetailOut.model_validate(student)
        if student.class_id is not None:
            klass = self.db.get(SchoolClass, student.class_id)
            if klass is not None:
                detail.class_label = klass.name + (f"-{klass.section}" if klass.section else "")
        if student.category_id is not None:
            detail.category_name = self.db.scalar(
                select(StudentCategory.name).where(StudentCategory.id == student.category_id)
            )
        detail.guardians = [
            GuardianOut.model_validate(g)
            for g in self.db.scalars(
                select(Guardian).where(Guardian.student_id == student_id)
                .order_by(Guardian.is_primary.desc(), Guardian.name)
            )
        ]
        return detail

    # ── guardians ────────────────────────────────────────────────────────────
    def _new_guardian(self, org_id: uuid.UUID, student_id: uuid.UUID, g: GuardianCreate) -> Guardian:
        return Guardian(
            org_id=org_id, student_id=student_id, name=g.name, relation=g.relation,
            phone=g.phone, is_primary=g.is_primary, notify_opt_out=g.notify_opt_out,
        )

    def add_guardian(
        self, m: CurrentMember, student_id: uuid.UUID, body: GuardianCreate
    ) -> GuardianOut:
        self._student(m.org_id, student_id)  # same-org guard
        guardian = self._new_guardian(m.org_id, student_id, body)
        self.db.add(guardian)
        self.db.flush()
        return GuardianOut.model_validate(guardian)

    def update_guardian(
        self, m: CurrentMember, guardian_id: uuid.UUID, body: GuardianUpdate
    ) -> GuardianOut:
        guardian = self.db.scalar(
            select(Guardian).where(Guardian.id == guardian_id, Guardian.org_id == m.org_id)
        )
        if guardian is None:
            raise NotFoundError("Guardian")
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(guardian, k, v)
        self.db.flush()
        return GuardianOut.model_validate(guardian)

    def delete_guardian(self, m: CurrentMember, guardian_id: uuid.UUID) -> None:
        guardian = self.db.scalar(
            select(Guardian).where(Guardian.id == guardian_id, Guardian.org_id == m.org_id)
        )
        if guardian is None:
            raise NotFoundError("Guardian")
        self.db.delete(guardian)

    # ── scoped-existence guards ──────────────────────────────────────────────
    def _scoped_class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> None:
        if not self.db.scalar(
            select(SchoolClass.id).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
        ):
            raise NotFoundError("Class")

    def _scoped_category(self, org_id: uuid.UUID, category_id: uuid.UUID) -> None:
        if not self.db.scalar(
            select(StudentCategory.id).where(
                StudentCategory.id == category_id, StudentCategory.org_id == org_id
            )
        ):
            raise NotFoundError("Category")
