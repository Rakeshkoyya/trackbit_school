"""Academic master-data CRUD (SPRD §4.2 / §5.1).

Thin endpoints call these; every query is scoped by member.org_id explicitly
(seed law #2 — app-layer scoping is the primary tenant guard). Cross-references
(a term's year, a class-subject's class/subject) are resolved through the same
org filter so nothing can point across tenants.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError
from app.models import AcademicYear, ClassSubject, SchoolClass, Subject, Term
from app.schemas.academics import (
    ClassCreate,
    ClassOut,
    ClassSubjectCreate,
    ClassSubjectOut,
    ClassSubjectUpdate,
    ClassUpdate,
    SubjectCreate,
    SubjectOut,
    TermCreate,
    TermOut,
    TermUpdate,
    YearCreate,
    YearOut,
    YearUpdate,
)


class AcademicService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _scoped(self, model, org_id: uuid.UUID, obj_id: uuid.UUID):
        obj = self.db.scalar(
            select(model).where(model.id == obj_id, model.org_id == org_id)
        )
        if obj is None:
            raise NotFoundError(model.__name__)
        return obj

    # ── academic years ───────────────────────────────────────────────────────
    def list_years(self, m: CurrentMember) -> list[YearOut]:
        rows = self.db.scalars(
            select(AcademicYear).where(AcademicYear.org_id == m.org_id)
            .order_by(AcademicYear.start_date.desc())
        )
        return [YearOut.model_validate(r) for r in rows]

    def create_year(self, m: CurrentMember, body: YearCreate) -> YearOut:
        exists = self.db.scalar(
            select(AcademicYear.id).where(
                AcademicYear.org_id == m.org_id, AcademicYear.label == body.label
            )
        )
        if exists:
            raise ConflictError(f"A year labelled “{body.label}” already exists.", code="duplicate")
        # First year created becomes the active one, so the app is usable immediately.
        has_any = self.db.scalar(
            select(AcademicYear.id).where(AcademicYear.org_id == m.org_id).limit(1)
        )
        year = AcademicYear(
            org_id=m.org_id, label=body.label, start_date=body.start_date,
            end_date=body.end_date, is_active=has_any is None,
        )
        self.db.add(year)
        self.db.flush()
        return YearOut.model_validate(year)

    def update_year(self, m: CurrentMember, year_id: uuid.UUID, body: YearUpdate) -> YearOut:
        year = self._scoped(AcademicYear, m.org_id, year_id)
        data = body.model_dump(exclude_unset=True)
        if "label" in data and data["label"] != year.label:
            dup = self.db.scalar(
                select(AcademicYear.id).where(
                    AcademicYear.org_id == m.org_id, AcademicYear.label == data["label"],
                    AcademicYear.id != year_id,
                )
            )
            if dup:
                raise ConflictError("Another year already uses that label.", code="duplicate")
        for k, v in data.items():
            setattr(year, k, v)
        self.db.flush()
        return YearOut.model_validate(year)

    def activate_year(self, m: CurrentMember, year_id: uuid.UUID) -> YearOut:
        year = self._scoped(AcademicYear, m.org_id, year_id)
        # Exactly one active year per org (enforced here, not in the DB).
        self.db.execute(
            update(AcademicYear).where(
                AcademicYear.org_id == m.org_id, AcademicYear.id != year_id
            ).values(is_active=False)
        )
        year.is_active = True
        self.db.flush()
        return YearOut.model_validate(year)

    def delete_year(self, m: CurrentMember, year_id: uuid.UUID) -> None:
        self.db.delete(self._scoped(AcademicYear, m.org_id, year_id))

    # ── terms ────────────────────────────────────────────────────────────────
    def list_terms(self, m: CurrentMember, year_id: uuid.UUID | None) -> list[TermOut]:
        q = select(Term).where(Term.org_id == m.org_id).order_by(Term.start_date)
        if year_id is not None:
            q = q.where(Term.academic_year_id == year_id)
        return [TermOut.model_validate(r) for r in self.db.scalars(q)]

    def create_term(self, m: CurrentMember, body: TermCreate) -> TermOut:
        self._scoped(AcademicYear, m.org_id, body.academic_year_id)  # same-org guard
        term = Term(
            org_id=m.org_id, academic_year_id=body.academic_year_id, name=body.name,
            start_date=body.start_date, end_date=body.end_date,
        )
        self.db.add(term)
        self.db.flush()
        return TermOut.model_validate(term)

    def update_term(self, m: CurrentMember, term_id: uuid.UUID, body: TermUpdate) -> TermOut:
        term = self._scoped(Term, m.org_id, term_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(term, k, v)
        self.db.flush()
        return TermOut.model_validate(term)

    def delete_term(self, m: CurrentMember, term_id: uuid.UUID) -> None:
        self.db.delete(self._scoped(Term, m.org_id, term_id))

    # ── subjects ─────────────────────────────────────────────────────────────
    def list_subjects(self, m: CurrentMember) -> list[SubjectOut]:
        rows = self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id).order_by(Subject.name)
        )
        return [SubjectOut.model_validate(r) for r in rows]

    def create_subject(self, m: CurrentMember, body: SubjectCreate) -> SubjectOut:
        dup = self.db.scalar(
            select(Subject.id).where(Subject.org_id == m.org_id, Subject.name == body.name)
        )
        if dup:
            raise ConflictError(f"“{body.name}” already exists.", code="duplicate")
        subject = Subject(org_id=m.org_id, name=body.name)
        self.db.add(subject)
        self.db.flush()
        return SubjectOut.model_validate(subject)

    def delete_subject(self, m: CurrentMember, subject_id: uuid.UUID) -> None:
        self.db.delete(self._scoped(Subject, m.org_id, subject_id))

    # ── classes ──────────────────────────────────────────────────────────────
    def list_classes(self, m: CurrentMember, year_id: uuid.UUID | None) -> list[ClassOut]:
        q = select(SchoolClass).where(SchoolClass.org_id == m.org_id).order_by(
            SchoolClass.name, SchoolClass.section
        )
        if year_id is not None:
            q = q.where(SchoolClass.academic_year_id == year_id)
        return [ClassOut.model_validate(r) for r in self.db.scalars(q)]

    def create_class(self, m: CurrentMember, body: ClassCreate) -> ClassOut:
        self._scoped(AcademicYear, m.org_id, body.academic_year_id)
        dup = self.db.scalar(
            select(SchoolClass.id).where(
                SchoolClass.org_id == m.org_id,
                SchoolClass.academic_year_id == body.academic_year_id,
                SchoolClass.name == body.name,
                SchoolClass.section.is_(body.section) if body.section is None
                else SchoolClass.section == body.section,
            )
        )
        if dup:
            raise ConflictError("That class + section already exists this year.", code="duplicate")
        klass = SchoolClass(
            org_id=m.org_id, academic_year_id=body.academic_year_id, name=body.name,
            section=body.section, class_teacher_member_id=body.class_teacher_member_id,
        )
        self.db.add(klass)
        self.db.flush()
        return ClassOut.model_validate(klass)

    def update_class(self, m: CurrentMember, class_id: uuid.UUID, body: ClassUpdate) -> ClassOut:
        klass = self._scoped(SchoolClass, m.org_id, class_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(klass, k, v)
        self.db.flush()
        return ClassOut.model_validate(klass)

    def delete_class(self, m: CurrentMember, class_id: uuid.UUID) -> None:
        self.db.delete(self._scoped(SchoolClass, m.org_id, class_id))

    # ── class–subjects ───────────────────────────────────────────────────────
    def list_class_subjects(self, m: CurrentMember, class_id: uuid.UUID) -> list[ClassSubjectOut]:
        self._scoped(SchoolClass, m.org_id, class_id)
        rows = self.db.execute(
            select(ClassSubject, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)
        ).all()
        out: list[ClassSubjectOut] = []
        for cs, subject_name in rows:
            item = ClassSubjectOut.model_validate(cs)
            item.subject_name = subject_name
            out.append(item)
        return out

    def create_class_subject(self, m: CurrentMember, body: ClassSubjectCreate) -> ClassSubjectOut:
        self._scoped(SchoolClass, m.org_id, body.class_id)
        subject = self._scoped(Subject, m.org_id, body.subject_id)
        dup = self.db.scalar(
            select(ClassSubject.id).where(
                ClassSubject.class_id == body.class_id, ClassSubject.subject_id == body.subject_id
            )
        )
        if dup:
            raise ConflictError("That subject is already on this class.", code="duplicate")
        cs = ClassSubject(
            org_id=m.org_id, class_id=body.class_id, subject_id=body.subject_id,
            teacher_member_id=body.teacher_member_id, periods_per_week=body.periods_per_week,
        )
        self.db.add(cs)
        self.db.flush()
        item = ClassSubjectOut.model_validate(cs)
        item.subject_name = subject.name
        return item

    def update_class_subject(
        self, m: CurrentMember, cs_id: uuid.UUID, body: ClassSubjectUpdate
    ) -> ClassSubjectOut:
        cs = self._scoped(ClassSubject, m.org_id, cs_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(cs, k, v)
        self.db.flush()
        item = ClassSubjectOut.model_validate(cs)
        item.subject_name = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        return item

    def delete_class_subject(self, m: CurrentMember, cs_id: uuid.UUID) -> None:
        self.db.delete(self._scoped(ClassSubject, m.org_id, cs_id))
