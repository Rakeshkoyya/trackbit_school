"""Academic master-data CRUD (SPRD §4.2 / §5.1).

Thin endpoints call these; every query is scoped by member.org_id explicitly
(seed law #2 — app-layer scoping is the primary tenant guard). Cross-references
(a term's year, a class-subject's class/subject) are resolved through the same
org filter so nothing can point across tenants.
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    User,
)
from app.schemas.academics import (
    AllocationRow,
    AllocationSetIn,
    ClassAllocationOut,
    ClassCreate,
    ClassOut,
    ClassSubjectCreate,
    ClassSubjectOut,
    ClassSubjectUpdate,
    ClassUpdate,
    CopySubjectsIn,
    CopySubjectsOut,
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
    def list_classes(self, m: CurrentMember, year_id: uuid.UUID | None,
                     mine: bool = False) -> list[ClassOut]:
        q = select(SchoolClass).where(SchoolClass.org_id == m.org_id).order_by(
            SchoolClass.name, SchoolClass.section
        )
        if year_id is not None:
            q = q.where(SchoolClass.academic_year_id == year_id)
        if mine and not m.is_coordinator_up:
            q = q.where(SchoolClass.id.in_(select(ClassSubject.class_id).where(
                ClassSubject.org_id == m.org_id,
                ClassSubject.teacher_member_id == m.membership.id)))
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

    # ── copy a class's setup onto a sibling section ───────────────────────────
    def copy_class_subjects(self, m: CurrentMember, class_id: uuid.UUID,
                            body: CopySubjectsIn) -> CopySubjectsOut:
        """Copy 6-A's subjects (teacher + periods/week) — and optionally each
        subject's syllabus — onto 6-B. Additive and idempotent: a subject the
        target already has is left untouched, and syllabus is only copied onto a
        subject whose syllabus is still empty (never merged, never overwritten)."""
        target = self._scoped(SchoolClass, m.org_id, class_id)
        source = self._scoped(SchoolClass, m.org_id, body.from_class_id)
        if target.id == source.id:
            raise ValidationError("Pick a different class to copy from.")

        src_rows = list(self.db.scalars(select(ClassSubject).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == source.id)))
        existing = {cs.subject_id: cs for cs in self.db.scalars(select(ClassSubject).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == target.id))}

        subjects_added = units_copied = topics_copied = 0
        for src in src_rows:
            dst = existing.get(src.subject_id)
            if dst is None:
                dst = ClassSubject(
                    org_id=m.org_id, class_id=target.id, subject_id=src.subject_id,
                    teacher_member_id=src.teacher_member_id,
                    periods_per_week=src.periods_per_week)
                self.db.add(dst)
                self.db.flush()
                subjects_added += 1
            if not body.include_syllabus:
                continue
            has_units = self.db.scalar(select(SyllabusUnit.id).where(
                SyllabusUnit.org_id == m.org_id,
                SyllabusUnit.class_subject_id == dst.id).limit(1))
            if has_units:
                continue
            src_units = self.db.scalars(
                select(SyllabusUnit)
                .where(SyllabusUnit.org_id == m.org_id,
                       SyllabusUnit.class_subject_id == src.id)
                .options(selectinload(SyllabusUnit.topics))
                .order_by(SyllabusUnit.position))
            for u in src_units:
                nu = SyllabusUnit(org_id=m.org_id, class_subject_id=dst.id, title=u.title,
                                  position=u.position, term_id=u.term_id)
                self.db.add(nu)
                self.db.flush()
                units_copied += 1
                for t in sorted(u.topics, key=lambda t: t.position):
                    self.db.add(SyllabusTopic(
                        org_id=m.org_id, unit_id=nu.id, title=t.title,
                        position=t.position, est_periods=t.est_periods))
                    topics_copied += 1
        self.db.flush()
        return CopySubjectsOut(subjects_added=subjects_added, units_copied=units_copied,
                               topics_copied=topics_copied)

    # ── class allocation (the week's period budget) ──────────────────────────
    # periods_per_week stays *entered, never generated* (§11 fence): `suggested`
    # is a proposal the admin confirms with an explicit save, exactly like every
    # other draft surface.
    def class_allocation(self, m: CurrentMember, class_id: uuid.UUID) -> ClassAllocationOut:
        klass = self._scoped(SchoolClass, m.org_id, class_id)
        year = self.db.get(AcademicYear, klass.academic_year_id)
        capacity = (len(year.working_weekdays or []) * (year.periods_per_day or 0)) if year else 0

        rows = self.db.execute(
            select(ClassSubject, Subject.name, User.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)
        ).all()

        syl: dict[uuid.UUID, int] = dict(self.db.execute(
            select(SyllabusUnit.class_subject_id,
                   func.coalesce(func.sum(SyllabusTopic.est_periods), 0))
            .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id)
            .where(SyllabusUnit.org_id == m.org_id,
                   SyllabusUnit.class_subject_id.in_([cs.id for cs, _s, _t in rows]))
            .group_by(SyllabusUnit.class_subject_id)
        ).all()) if rows else {}

        suggested = self._suggest(
            [(cs.id, syl.get(cs.id, 0)) for cs, _s, _t in rows], capacity)
        out_rows = [
            AllocationRow(
                class_subject_id=cs.id, subject_name=sname, teacher_name=tname,
                periods_per_week=cs.periods_per_week, syllabus_periods=syl.get(cs.id, 0),
                suggested=suggested.get(cs.id, 0))
            for cs, sname, tname in rows
        ]
        label = klass.name + (f"-{klass.section}" if klass.section else "")
        return ClassAllocationOut(
            class_id=class_id, class_label=label, capacity=capacity,
            allocated=sum(r.periods_per_week for r in out_rows), rows=out_rows)

    @staticmethod
    def _suggest(sizes: list[tuple[uuid.UUID, int]], capacity: int) -> dict[uuid.UUID, int]:
        """Split the week's capacity across subjects in proportion to syllabus size
        (largest-remainder rounding; a subject with any syllabus gets at least 1)."""
        total = sum(n for _id, n in sizes)
        if capacity <= 0 or total <= 0:
            return {cs_id: 0 for cs_id, _n in sizes}
        raw = {cs_id: capacity * n / total for cs_id, n in sizes}
        base = {cs_id: max(1, int(r)) if r > 0 else 0 for cs_id, r in raw.items()}
        leftover = capacity - sum(base.values())
        for cs_id, _frac in sorted(
                ((cs_id, raw[cs_id] - int(raw[cs_id])) for cs_id, _n in sizes),
                key=lambda x: -x[1]):
            if leftover <= 0:
                break
            base[cs_id] += 1
            leftover -= 1
        return base

    def set_allocation(self, m: CurrentMember, class_id: uuid.UUID,
                       body: AllocationSetIn) -> ClassAllocationOut:
        self._scoped(SchoolClass, m.org_id, class_id)
        for item in body.items:
            cs = self._scoped(ClassSubject, m.org_id, item.class_subject_id)
            if cs.class_id != class_id:
                raise ValidationError("That subject belongs to a different class.")
            cs.periods_per_week = item.periods_per_week
        self.db.flush()
        return self.class_allocation(m, class_id)
