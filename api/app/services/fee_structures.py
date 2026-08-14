"""Fee structures — the year's backbone (FE-1, `D-116`…`D-120`).

Split out of `services/fees.py`, which was already at ~520 lines and is about to
carry the schedule and proof work as well.

Three rules from the founder shape everything here:

* **A structure prices a CLASS, not a section** (`D-116`). One row for "6" covers
  6-A, 6-B and 6-C. `class_name` therefore holds the bare class name, and it is
  validated against the year's real classes rather than typed — the old screen
  let an admin type "6-B" into a free-text box and hope it matched a label the
  student list would build later.
* **Editing never reprices a student already on the old amount** (`D-118`). Save
  archives and re-creates; existing `student_fees` rows are untouched. A family
  that has paid two instalments against ₹62,000 does not silently owe ₹68,000
  because somebody corrected the price on the wrong screen.
* **Setting a class up is one action, not N** (`D-120`). Typing a fee per child
  for a whole class is what P1v2 calls a mis-designed feature.
"""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    FeeInstallmentTemplate,
    FeeStructure,
    Installment,
    SchoolClass,
    Student,
    StudentCategory,
    StudentFee,
)
from app.schemas.fees import (
    ApplyStructureIn,
    ApplyStructureOut,
    ClassCoverageRow,
    FeeStructureCreate,
    FeeStructureOut,
    FeeStructureUpdate,
    StructureCoverage,
    TemplateOut,
)
from app.services import fee_events
from app.services.fee_math import proportional_installments, q


def _school_order(name: str) -> tuple:
    """`10` after `9`, and "Nursery" after the numbered classes rather than
    wherever ASCII would put it. The web picker sorts the same way; a class list
    that reads 11, 12, 3, 5 is the defect this exists to prevent."""
    digits = "".join(ch for ch in name if ch.isdigit())
    return (0, int(digits), name) if digits else (1, 0, name.lower())


class FeeStructureService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _year(self, org_id: uuid.UUID, year_id: uuid.UUID) -> AcademicYear:
        year = self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == org_id
            )
        )
        if year is None:
            raise NotFoundError("Academic year")
        return year

    def _classes(self, org_id: uuid.UUID, year_id: uuid.UUID) -> list[SchoolClass]:
        return list(
            self.db.scalars(
                select(SchoolClass).where(
                    SchoolClass.org_id == org_id,
                    SchoolClass.academic_year_id == year_id,
                )
            )
        )

    def _class_ids_for(
        self, org_id: uuid.UUID, year_id: uuid.UUID, class_name: str
    ) -> list[uuid.UUID]:
        """Every section of one class. This is what "per class" means in queries."""
        return list(
            self.db.scalars(
                select(SchoolClass.id).where(
                    SchoolClass.org_id == org_id,
                    SchoolClass.academic_year_id == year_id,
                    SchoolClass.name == class_name,
                )
            )
        )

    def structure_for_student(
        self, org_id: uuid.UUID, year_id: uuid.UUID, student: Student,
    ) -> FeeStructure | None:
        """Which structure prices THIS child (FE-2).

        The exact mirror of `apply()`'s rule, read from the student's end instead
        of the structure's: **her own category's price for her class if one
        exists, otherwise the class's general price.** `apply()` says the same
        thing by having the general structure skip children whose category is
        spoken for; said from here it has to be a preference, and the two must
        agree or a staff ward would be quoted one fee by the per-student screen
        and billed another by the bulk button.

        Returns None when the class is not priced at all — which is a real answer
        the setup screen renders as "not priced yet", never as ₹0.
        """
        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        if klass is None:
            return None
        actives = list(
            self.db.scalars(
                select(FeeStructure)
                .where(
                    FeeStructure.org_id == org_id,
                    FeeStructure.academic_year_id == year_id,
                    FeeStructure.class_name == klass.name,
                    FeeStructure.is_active.is_(True),
                )
                .options(selectinload(FeeStructure.templates),
                         selectinload(FeeStructure.category))
            )
        )
        if not actives:
            return None
        if student.category_id is not None:
            mine = next((s for s in actives if s.category_id == student.category_id), None)
            if mine is not None:
                return mine
        return next((s for s in actives if s.category_id is None), None)

    def _require_real_class(
        self, org_id: uuid.UUID, year_id: uuid.UUID, class_name: str
    ) -> None:
        """`D-116`. The one guard that stops a structure orphaning itself the day
        it is written — the failure the free-text box made routine."""
        if not self._class_ids_for(org_id, year_id, class_name):
            raise ValidationError(
                f"There is no class named “{class_name}” in this academic year. "
                "A fee structure prices the whole class, so name it “6”, not “6-B”."
            )

    def _validate_category(
        self, org_id: uuid.UUID, category_id: uuid.UUID | None
    ) -> StudentCategory | None:
        if category_id is None:
            return None
        cat = self.db.scalar(
            select(StudentCategory).where(
                StudentCategory.id == category_id, StudentCategory.org_id == org_id
            )
        )
        if cat is None:
            raise ValidationError("Selected category does not exist.")
        return cat

    def _validate_schedule(self, total, rows, num_installments: int) -> None:
        """The rule the editor's reconciliation bar draws, enforced server-side.

        Both halves matter: a mismatched sum silently changes what the school
        charges, and a row count that disagrees with `num_installments` means the
        two are describing different schedules.
        """
        total = q(total)
        rows_sum = q(sum(q(r.amount) for r in rows))
        if rows_sum != total:
            short = q(total - rows_sum)
            raise ValidationError(
                f"The instalments add up to ₹{rows_sum}, but the total fee is "
                f"₹{total} — ₹{abs(short)} "
                f"{'still to allocate' if short > 0 else 'over-allocated'}."
            )
        if len(rows) != num_installments:
            raise ValidationError(
                f"{num_installments} instalments were asked for but "
                f"{len(rows)} rows were sent."
            )

    def _out(self, fs: FeeStructure) -> FeeStructureOut:
        return FeeStructureOut(
            id=fs.id, class_name=fs.class_name, category_id=fs.category_id,
            category_name=fs.category.name if fs.category else None,
            academic_year_id=fs.academic_year_id, total_amount=q(fs.total_amount),
            num_installments=fs.num_installments, is_active=fs.is_active,
            templates=[
                TemplateOut.model_validate(t)
                for t in sorted(fs.templates, key=lambda t: t.installment_number)
            ],
        )

    def _load(self, org_id: uuid.UUID, fs_id: uuid.UUID) -> FeeStructure:
        fs = self.db.scalar(
            select(FeeStructure)
            .where(FeeStructure.id == fs_id, FeeStructure.org_id == org_id)
            .options(
                selectinload(FeeStructure.templates),
                selectinload(FeeStructure.category),
            )
        )
        if fs is None:
            raise NotFoundError("Fee structure")
        return fs

    def _archive_active(
        self, org_id: uuid.UUID, year_id: uuid.UUID, class_name: str,
        category_id: uuid.UUID | None,
    ) -> list[FeeStructure]:
        """Retire whatever currently prices this key. Never a DELETE — the
        school's pricing history is exactly what somebody will ask about."""
        rows = list(
            self.db.scalars(
                select(FeeStructure).where(
                    FeeStructure.org_id == org_id,
                    FeeStructure.academic_year_id == year_id,
                    FeeStructure.class_name == class_name,
                    FeeStructure.category_id.is_(None)
                    if category_id is None
                    else FeeStructure.category_id == category_id,
                    FeeStructure.is_active.is_(True),
                )
            )
        )
        for row in rows:
            row.is_active = False
        # The partial unique index is checked at statement end, so the archive
        # has to reach the database before the replacement is inserted.
        if rows:
            self.db.flush()
        return rows

    def _build(
        self, m: CurrentMember, *, class_name: str, category_id: uuid.UUID | None,
        year_id: uuid.UUID, total, num_installments: int, rows,
    ) -> FeeStructure:
        fs = FeeStructure(
            org_id=m.org_id, class_name=class_name, category_id=category_id,
            academic_year_id=year_id, total_amount=q(total),
            num_installments=num_installments, created_by=m.user_id,
            templates=[
                FeeInstallmentTemplate(
                    org_id=m.org_id, installment_number=r.installment_number,
                    label=r.label, amount=q(r.amount), due_date=r.due_date,
                )
                for r in rows
            ],
        )
        self.db.add(fs)
        self.db.flush()
        return fs

    # ── reads ────────────────────────────────────────────────────────────────
    def coverage(self, m: CurrentMember, year_id: uuid.UUID) -> StructureCoverage:
        """Every class of the year, priced or not (`D-117`).

        The founder's phrase was *"once all the classes and fee structure is
        done"* — a completeness check. A screen that lists only the structures
        that exist cannot answer it, because the missing class is precisely the
        row it does not draw.
        """
        self._year(m.org_id, year_id)
        classes = self._classes(m.org_id, year_id)
        sections: dict[str, list[str]] = defaultdict(list)
        class_id_to_name: dict[uuid.UUID, str] = {}
        for klass in classes:
            class_id_to_name[klass.id] = klass.name
            if klass.section:
                sections[klass.name].append(klass.section)

        class_ids = list(class_id_to_name)
        # Active students only — a struck-off child is not a family anybody is
        # going to bill. One grouped query, never one per class row.
        head: dict[str, int] = defaultdict(int)
        unset: dict[str, int] = defaultdict(int)
        if class_ids:
            with_fee = set(
                self.db.scalars(
                    select(StudentFee.student_id).where(
                        StudentFee.org_id == m.org_id,
                        StudentFee.academic_year_id == year_id,
                    )
                )
            )
            for student_id, class_id in self.db.execute(
                select(Student.id, Student.class_id).where(
                    Student.org_id == m.org_id,
                    Student.status == "active",
                    Student.class_id.in_(class_ids),
                )
            ).all():
                name = class_id_to_name[class_id]
                head[name] += 1
                if student_id not in with_fee:
                    unset[name] += 1

        structures = list(
            self.db.scalars(
                select(FeeStructure)
                .where(
                    FeeStructure.org_id == m.org_id,
                    FeeStructure.academic_year_id == year_id,
                    FeeStructure.is_active.is_(True),
                )
                .options(selectinload(FeeStructure.category))
            )
        )
        on_structure: dict[uuid.UUID, int] = defaultdict(int)
        if structures:
            for fs_id, count in self.db.execute(
                select(StudentFee.fee_structure_id, func.count(StudentFee.id))
                .where(
                    StudentFee.org_id == m.org_id,
                    StudentFee.academic_year_id == year_id,
                    StudentFee.fee_structure_id.in_([s.id for s in structures]),
                )
                .group_by(StudentFee.fee_structure_id)
            ).all():
                on_structure[fs_id] = count

        by_class: dict[str, list[FeeStructure]] = defaultdict(list)
        for fs in structures:
            by_class[fs.class_name].append(fs)

        out: list[ClassCoverageRow] = []
        names = sorted({k.name for k in classes}, key=_school_order)
        for name in names:
            secs = sorted(sections.get(name, []))
            found = by_class.get(name, [])
            if not found:
                # The "not priced" row. Drawn, never omitted (`D-117`).
                out.append(ClassCoverageRow(
                    class_name=name, sections=secs,
                    students_total=head.get(name, 0),
                    students_unset=unset.get(name, 0),
                ))
                continue
            for fs in sorted(found,
                             key=lambda s: (s.category.name if s.category else "")):
                out.append(ClassCoverageRow(
                    class_name=name, sections=secs,
                    students_total=head.get(name, 0),
                    structure_id=fs.id, category_id=fs.category_id,
                    category_name=fs.category.name if fs.category else None,
                    total_amount=q(fs.total_amount),
                    num_installments=fs.num_installments,
                    students_on=on_structure.get(fs.id, 0),
                    students_unset=unset.get(name, 0),
                ))
        return StructureCoverage(
            academic_year_id=year_id,
            classes_total=len(names),
            classes_priced=len([n for n in names if by_class.get(n)]),
            rows=out,
        )

    # ── writes ───────────────────────────────────────────────────────────────
    def create(self, m: CurrentMember, body: FeeStructureCreate) -> FeeStructureOut:
        self._year(m.org_id, body.academic_year_id)
        self._require_real_class(m.org_id, body.academic_year_id, body.class_name)
        cat = self._validate_category(m.org_id, body.category_id)
        self._validate_schedule(body.total_amount, body.installments,
                                body.num_installments)

        replaced = self._archive_active(
            m.org_id, body.academic_year_id, body.class_name, body.category_id)
        fs = self._build(
            m, class_name=body.class_name, category_id=body.category_id,
            year_id=body.academic_year_id, total=body.total_amount,
            num_installments=body.num_installments, rows=body.installments,
        )

        who = f"Class {body.class_name}" + (f" · {cat.name}" if cat else "")
        if replaced:
            old = replaced[0]
            fee_events.record(
                self.db, m, "structure_replaced",
                f"{who} repriced from ₹{q(old.total_amount):,.0f} to "
                f"₹{q(fs.total_amount):,.0f} ({fs.num_installments} instalments). "
                "Students already set up keep the old amount.",
                fee_structure_id=fs.id, academic_year_id=fs.academic_year_id,
                meta={"previous_structure_id": str(old.id),
                      "previous_total": str(q(old.total_amount)),
                      "total": str(q(fs.total_amount))},
            )
        else:
            fee_events.record(
                self.db, m, "structure_created",
                f"{who} priced at ₹{q(fs.total_amount):,.0f} in "
                f"{fs.num_installments} instalments.",
                fee_structure_id=fs.id, academic_year_id=fs.academic_year_id,
                meta={"total": str(q(fs.total_amount))},
            )
        return self._out(fs)

    def update(
        self, m: CurrentMember, fs_id: uuid.UUID, body: FeeStructureUpdate
    ) -> FeeStructureOut:
        """`D-118`. Presented to the admin as an edit; underneath it archives and
        re-creates, so the previous price stays readable and — the part that
        matters — **no existing student fee record is touched**."""
        current = self._load(m.org_id, fs_id)
        category_id = (
            body.category_id if body.category_id is not None else current.category_id
        )
        return self.create(
            m,
            FeeStructureCreate(
                class_name=current.class_name,
                category_id=category_id,
                academic_year_id=current.academic_year_id,
                total_amount=body.total_amount,
                num_installments=body.num_installments,
                installments=body.installments,
            ),
        )

    def apply(
        self, m: CurrentMember, fs_id: uuid.UUID, body: ApplyStructureIn
    ) -> ApplyStructureOut:
        """Create a fee record per student from this structure (`D-120`).

        **Order does not matter.** Applying the general ("all categories")
        structure skips students whose own category has its own active structure
        for the class, so a school can set the staff-ward price up before or
        after the ordinary one and get the same answer either way. Getting this
        wrong means quietly billing a staff ward the full fee.
        """
        fs = self._load(m.org_id, fs_id)
        class_ids = self._class_ids_for(m.org_id, fs.academic_year_id, fs.class_name)
        if not class_ids:
            raise ValidationError(
                f"No class named “{fs.class_name}” exists in this year any more, "
                "so there is nobody to apply this structure to."
            )

        stmt = select(Student).where(
            Student.org_id == m.org_id,
            Student.class_id.in_(class_ids),
            Student.status == "active",
        )
        if body.student_ids:
            stmt = stmt.where(Student.id.in_(body.student_ids))
        if fs.category_id is not None:
            stmt = stmt.where(Student.category_id == fs.category_id)
        students = list(self.db.scalars(stmt))

        if fs.category_id is None:
            # Categories that have their own price for this class: their children
            # are not ours to bill.
            spoken_for = set(
                self.db.scalars(
                    select(FeeStructure.category_id).where(
                        FeeStructure.org_id == m.org_id,
                        FeeStructure.academic_year_id == fs.academic_year_id,
                        FeeStructure.class_name == fs.class_name,
                        FeeStructure.category_id.isnot(None),
                        FeeStructure.is_active.is_(True),
                    )
                )
            )
            if spoken_for:
                students = [s for s in students if s.category_id not in spoken_for]

        existing = set(
            self.db.scalars(
                select(StudentFee.student_id).where(
                    StudentFee.org_id == m.org_id,
                    StudentFee.academic_year_id == fs.academic_year_id,
                    StudentFee.student_id.in_(
                        [s.id for s in students] or [uuid.uuid4()]
                    ),
                )
            )
        )

        templates = sorted(fs.templates, key=lambda t: t.installment_number)
        total = q(fs.total_amount)
        amounts = proportional_installments(total, [t.amount for t in templates])

        created = 0
        skipped_existing = 0
        for student in students:
            if student.id in existing:
                # Skipped whatever `skip_existing` says. Overwriting a record
                # that may already carry payments is not something a bulk button
                # gets to do — the per-student screen is where that conversation
                # happens. The flag stays in the schema so the count can be
                # reported, and so a future "re-apply" has somewhere to live.
                skipped_existing += 1
                continue
            self.db.add(StudentFee(
                org_id=m.org_id, student_id=student.id, fee_structure_id=fs.id,
                academic_year_id=fs.academic_year_id, total_fee=total,
                discount=q(0), net_fee=total, opening_dues=q(0),
                created_by=m.user_id,
                installments=[
                    Installment(
                        org_id=m.org_id, installment_number=t.installment_number,
                        label=t.label, amount=amounts[i], due_date=t.due_date,
                    )
                    for i, t in enumerate(templates)
                ],
            ))
            created += 1
        self.db.flush()

        message = f"Set up {created} student{'' if created == 1 else 's'}."
        if skipped_existing:
            message += (
                f" {skipped_existing} already had fee "
                f"record{'' if skipped_existing == 1 else 's'}."
            )
        who = f"Class {fs.class_name}" + (
            f" · {fs.category.name}" if fs.category else ""
        )
        fee_events.record(
            self.db, m, "fee_bulk_applied",
            f"{who} structure applied. {message}",
            fee_structure_id=fs.id, academic_year_id=fs.academic_year_id,
            meta={"created": created, "skipped_existing": skipped_existing},
        )
        return ApplyStructureOut(
            created=created, skipped_existing=skipped_existing, message=message,
        )
