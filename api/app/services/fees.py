"""Fee operations (M6) — ported from fee_management_system to sync + org scoping.

Every query is org-scoped explicitly. Money goes through fee_math.q(); status is
recomputed after every mutation and never trusted as stored truth. The transactions
ledger is append-only — undo writes a compensating row (SPRD §4.6 invariants).
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    FeeInstallmentTemplate,
    FeeStructure,
    Installment,
    SchoolClass,
    Student,
    StudentCategory,
    StudentFee,
    Transaction,
)
from app.schemas.fees import (
    FeeStructureCreate,
    FeeStructureOut,
    FeeSummary,
    InstallmentOut,
    OverdueStudent,
    PaymentIn,
    StudentFeeCreate,
    StudentFeeDetail,
    StudentFeeListItem,
    StudentFeeUpdate,
    TemplateOut,
    TransactionOut,
)
from app.services.fee_math import (
    aggregate_paid,
    proportional_installments,
    q,
    recompute_student_fee,
)


class FeeService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _year(self, org_id: uuid.UUID, year_id: uuid.UUID) -> AcademicYear:
        y = self.db.scalar(
            select(AcademicYear).where(AcademicYear.id == year_id, AcademicYear.org_id == org_id)
        )
        if y is None:
            raise NotFoundError("Academic year")
        return y

    def _validate_category(self, org_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
        if category_id is None:
            return
        if not self.db.scalar(
            select(StudentCategory.id).where(
                StudentCategory.id == category_id, StudentCategory.org_id == org_id
            )
        ):
            raise ValidationError("Selected category does not exist.")

    def _class_label(self, class_id: uuid.UUID | None) -> str | None:
        if class_id is None:
            return None
        klass = self.db.get(SchoolClass, class_id)
        if klass is None:
            return None
        return klass.name + (f"-{klass.section}" if klass.section else "")

    def _load_sf(self, org_id: uuid.UUID, sf_id: uuid.UUID) -> StudentFee:
        sf = self.db.scalar(
            select(StudentFee)
            .where(StudentFee.id == sf_id, StudentFee.org_id == org_id)
            .options(
                selectinload(StudentFee.installments),
                selectinload(StudentFee.student).selectinload(Student.category),
            )
        )
        if sf is None:
            raise NotFoundError("Fee record")
        return sf

    def _load_installment(self, org_id: uuid.UUID, inst_id: uuid.UUID) -> tuple[Installment, StudentFee]:
        inst = self.db.scalar(
            select(Installment).where(Installment.id == inst_id, Installment.org_id == org_id)
        )
        if inst is None:
            raise NotFoundError("Installment")
        sf = self._load_sf(org_id, inst.student_fee_id)
        inst = next(i for i in sf.installments if i.id == inst_id)
        return inst, sf

    def _detail(self, sf: StudentFee) -> StudentFeeDetail:
        recompute_student_fee(sf)
        paid = aggregate_paid(sf.installments)
        opening = q(sf.opening_dues)
        total_payable = q(q(sf.net_fee) + opening)
        cat = sf.student.category.name if sf.student and sf.student.category else None
        return StudentFeeDetail(
            id=sf.id, student_id=sf.student_id,
            student_name=sf.student.full_name if sf.student else "",
            class_label=self._class_label(sf.student.class_id) if sf.student else None,
            category_name=cat, academic_year_id=sf.academic_year_id,
            total_fee=q(sf.total_fee), discount=q(sf.discount), net_fee=q(sf.net_fee),
            opening_dues=opening, total_payable=total_payable, paid=paid,
            balance=q(total_payable - paid), status=sf.status,
            installments=[
                InstallmentOut.model_validate(i)
                for i in sorted(sf.installments, key=lambda i: i.installment_number)
            ],
        )

    def _txn(self, m: CurrentMember, sf_id: uuid.UUID, inst_id: uuid.UUID | None,
             amount, ttype: str, note: str | None, mode: str | None = None,
             receipt: str | None = None) -> Transaction:
        return Transaction(
            org_id=m.org_id, student_fee_id=sf_id, installment_id=inst_id, amount=q(amount),
            type=ttype, note=note, mode=mode, receipt_number=receipt,
            created_by=m.user_id, created_by_name=m.user.name,
        )

    # ── fee structures ───────────────────────────────────────────────────────
    def _structure_out(self, fs: FeeStructure) -> FeeStructureOut:
        out = FeeStructureOut(
            id=fs.id, class_name=fs.class_name, category_id=fs.category_id,
            category_name=fs.category.name if fs.category else None,
            academic_year_id=fs.academic_year_id, total_amount=q(fs.total_amount),
            num_installments=fs.num_installments, is_active=fs.is_active,
            templates=[TemplateOut.model_validate(t) for t in fs.templates],
        )
        return out

    def list_structures(self, m: CurrentMember, *, class_name=None, year_id=None) -> list[FeeStructureOut]:
        q_ = (
            select(FeeStructure)
            .where(FeeStructure.org_id == m.org_id, FeeStructure.is_active.is_(True))
            .options(selectinload(FeeStructure.templates), selectinload(FeeStructure.category))
            .order_by(FeeStructure.class_name)
        )
        if class_name:
            q_ = q_.where(FeeStructure.class_name == class_name)
        if year_id:
            q_ = q_.where(FeeStructure.academic_year_id == year_id)
        return [self._structure_out(fs) for fs in self.db.scalars(q_)]

    def get_structure(self, m: CurrentMember, fs_id: uuid.UUID) -> FeeStructureOut:
        fs = self.db.scalar(
            select(FeeStructure)
            .where(FeeStructure.id == fs_id, FeeStructure.org_id == m.org_id)
            .options(selectinload(FeeStructure.templates), selectinload(FeeStructure.category))
        )
        if fs is None:
            raise NotFoundError("Fee structure")
        return self._structure_out(fs)

    def create_structure(self, m: CurrentMember, body: FeeStructureCreate) -> FeeStructureOut:
        total = q(body.total_amount)
        inst_sum = q(sum(q(i.amount) for i in body.installments))
        if inst_sum != total:
            raise ValidationError(
                f"Installment amounts (₹{inst_sum}) must equal the total fee (₹{total}).")
        if len(body.installments) != body.num_installments:
            raise ValidationError("Number of installment rows must match num_installments.")
        self._year(m.org_id, body.academic_year_id)
        self._validate_category(m.org_id, body.category_id)

        # Archive any existing active structure for the same class+category+year.
        existing = self.db.scalars(
            select(FeeStructure).where(
                FeeStructure.org_id == m.org_id,
                FeeStructure.class_name == body.class_name,
                FeeStructure.category_id.is_(None) if body.category_id is None
                else FeeStructure.category_id == body.category_id,
                FeeStructure.academic_year_id == body.academic_year_id,
                FeeStructure.is_active.is_(True),
            )
        )
        for e in existing:
            e.is_active = False

        fs = FeeStructure(
            org_id=m.org_id, class_name=body.class_name, category_id=body.category_id,
            academic_year_id=body.academic_year_id, total_amount=total,
            num_installments=body.num_installments, created_by=m.user_id,
            templates=[
                FeeInstallmentTemplate(
                    org_id=m.org_id, installment_number=i.installment_number, label=i.label,
                    amount=q(i.amount), due_date=i.due_date,
                )
                for i in body.installments
            ],
        )
        self.db.add(fs)
        self.db.flush()
        return self._structure_out(fs)

    # ── student fees ─────────────────────────────────────────────────────────
    def get_student_fee(self, m: CurrentMember, sf_id: uuid.UUID) -> StudentFeeDetail:
        return self._detail(self._load_sf(m.org_id, sf_id))

    def list_student_fees(
        self, m: CurrentMember, *, year_id=None, class_name=None, status=None, search=None
    ) -> list[StudentFeeListItem]:
        q_ = (
            select(StudentFee)
            .where(StudentFee.org_id == m.org_id)
            .options(
                selectinload(StudentFee.installments),
                selectinload(StudentFee.student).selectinload(Student.category),
            )
            .order_by(StudentFee.created_at.desc())
        )
        if year_id:
            q_ = q_.where(StudentFee.academic_year_id == year_id)
        rows = list(self.db.scalars(q_))
        items: list[StudentFeeListItem] = []
        for sf in rows:
            recompute_student_fee(sf)
            student = sf.student
            label = self._class_label(student.class_id) if student else None
            if class_name and label != class_name:
                continue
            if status and sf.status != status:
                continue
            if search and (not student or search.lower() not in student.full_name.lower()):
                continue
            paid = aggregate_paid(sf.installments)
            opening = q(sf.opening_dues)
            total_payable = q(q(sf.net_fee) + opening)
            items.append(StudentFeeListItem(
                id=sf.id, student_id=sf.student_id,
                student_name=student.full_name if student else "",
                class_label=label,
                category_name=student.category.name if student and student.category else None,
                academic_year_id=sf.academic_year_id, total_fee=q(sf.total_fee),
                discount=q(sf.discount), net_fee=q(sf.net_fee), opening_dues=opening,
                paid=paid, pending=q(total_payable - paid), status=sf.status,
            ))
        return items

    def enroll(self, m: CurrentMember, body: StudentFeeCreate) -> StudentFeeDetail:
        student = self.db.scalar(
            select(Student).where(Student.id == body.student_id, Student.org_id == m.org_id)
        )
        if student is None:
            raise NotFoundError("Student")
        self._year(m.org_id, body.academic_year_id)
        dup = self.db.scalar(
            select(StudentFee.id).where(
                StudentFee.org_id == m.org_id, StudentFee.student_id == body.student_id,
                StudentFee.academic_year_id == body.academic_year_id,
            )
        )
        if dup:
            raise ConflictError("This student is already enrolled for this academic year.")

        total = q(body.total_fee)
        discount = q(body.discount)
        net = q(total - discount)
        opening = q(body.opening_dues)

        inst_rows: list[Installment] = []
        if body.use_custom_schedule and body.installments:
            inst_sum = q(sum(q(i.amount) for i in body.installments))
            if inst_sum != net:
                raise ValidationError(
                    f"Installment amounts (₹{inst_sum}) must equal net payable (₹{net}).")
            for i in body.installments:
                inst_rows.append(Installment(
                    org_id=m.org_id, installment_number=i.installment_number, label=i.label,
                    amount=q(i.amount), due_date=i.due_date,
                ))
        elif body.fee_structure_id:
            fs = self.db.scalar(
                select(FeeStructure)
                .where(FeeStructure.id == body.fee_structure_id, FeeStructure.org_id == m.org_id)
                .options(selectinload(FeeStructure.templates))
            )
            if fs is None:
                raise NotFoundError("Fee structure")
            templates = sorted(fs.templates, key=lambda t: t.installment_number)
            scaled = proportional_installments(net, [t.amount for t in templates])
            for idx, t in enumerate(templates):
                inst_rows.append(Installment(
                    org_id=m.org_id, installment_number=t.installment_number, label=t.label,
                    amount=scaled[idx], due_date=t.due_date,
                ))
        else:
            inst_rows.append(Installment(
                org_id=m.org_id, installment_number=1, amount=net, due_date=None))

        sf = StudentFee(
            org_id=m.org_id, student_id=body.student_id, fee_structure_id=body.fee_structure_id,
            academic_year_id=body.academic_year_id, total_fee=total, discount=discount,
            net_fee=net, opening_dues=opening, created_by=m.user_id, installments=inst_rows,
        )
        self.db.add(sf)
        self.db.flush()

        if body.first_payment and q(body.first_payment.amount) > 0:
            fp = body.first_payment
            target = next(
                (i for i in sf.installments if i.installment_number == fp.installment_number),
                sf.installments[0],
            )
            pay = q(fp.amount)
            target.paid_amount = q(q(target.paid_amount) + pay)
            target.paid_date = fp.paid_on or date.today()
            self.db.add(self._txn(m, sf.id, target.id, pay, "payment",
                                  "Initial payment at enrolment", fp.mode, fp.receipt_number))

        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def update_discount(self, m: CurrentMember, sf_id: uuid.UUID, body: StudentFeeUpdate) -> StudentFeeDetail:
        sf = self._load_sf(m.org_id, sf_id)
        if body.opening_dues is not None:
            sf.opening_dues = q(body.opening_dues)
        if body.discount is not None:
            old_net = q(sf.net_fee)
            sf.discount = q(body.discount)
            sf.net_fee = q(q(sf.total_fee) - sf.discount)
            paid = aggregate_paid(sf.installments)
            remaining = q(sf.net_fee - paid)
            if remaining < 0:
                raise ValidationError(
                    "Discount makes net payable lower than the amount already paid.")
            unpaid = [i for i in sf.installments if q(i.paid_amount) < q(i.amount)]
            if unpaid:
                current_unpaid_total = q(sum(q(i.amount) - q(i.paid_amount) for i in unpaid))
                scaled = (
                    proportional_installments(remaining, [q(i.amount) - q(i.paid_amount) for i in unpaid])
                    if current_unpaid_total > 0 else [remaining]
                )
                for idx, i in enumerate(unpaid):
                    i.amount = q(q(i.paid_amount) + scaled[idx])
            self.db.add(self._txn(m, sf.id, None, q(sf.net_fee - old_net), "discount",
                                  f"Discount updated to ₹{sf.discount}"))
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def list_transactions(self, m: CurrentMember, sf_id: uuid.UUID) -> list[TransactionOut]:
        self._load_sf(m.org_id, sf_id)  # same-org guard
        rows = self.db.scalars(
            select(Transaction)
            .where(Transaction.student_fee_id == sf_id, Transaction.org_id == m.org_id)
            .order_by(Transaction.created_at.desc())
        )
        return [TransactionOut.model_validate(t) for t in rows]

    # ── installment actions ──────────────────────────────────────────────────
    def pay(self, m: CurrentMember, inst_id: uuid.UUID, body: PaymentIn) -> StudentFeeDetail:
        inst, sf = self._load_installment(m.org_id, inst_id)
        amount = q(body.amount)
        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")
        remaining = q(q(inst.amount) - q(inst.paid_amount))
        if amount > remaining:
            raise ValidationError(
                f"Payment ₹{amount} exceeds remaining balance ₹{remaining} on this installment.")
        inst.paid_amount = q(q(inst.paid_amount) + amount)
        inst.paid_date = body.paid_on or date.today()
        self.db.add(self._txn(m, sf.id, inst.id, amount, "payment", body.note,
                              body.mode, body.receipt_number))
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def mark_paid(self, m: CurrentMember, inst_id: uuid.UUID) -> StudentFeeDetail:
        inst, sf = self._load_installment(m.org_id, inst_id)
        remaining = q(q(inst.amount) - q(inst.paid_amount))
        if remaining <= 0:
            raise ValidationError("Installment is already fully paid.")
        inst.paid_amount = q(inst.amount)
        inst.paid_date = date.today()
        self.db.add(self._txn(m, sf.id, inst.id, remaining, "payment", "Marked fully paid", "cash"))
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def undo(self, m: CurrentMember, inst_id: uuid.UUID) -> StudentFeeDetail:
        inst, sf = self._load_installment(m.org_id, inst_id)
        last = self.db.scalar(
            select(Transaction)
            .where(Transaction.installment_id == inst.id, Transaction.type == "payment",
                   Transaction.org_id == m.org_id)
            .order_by(Transaction.created_at.desc()).limit(1)
        )
        if last is None:
            raise ValidationError("No payment to undo on this installment.")
        inst.paid_amount = q(max(q(inst.paid_amount) - q(last.amount), q(0)))
        if q(inst.paid_amount) <= 0:
            inst.paid_date = None
        # Compensating row — the original payment is preserved (append-only ledger).
        self.db.add(self._txn(m, sf.id, inst.id, q(-last.amount), "undo",
                              f"Reverted payment of ₹{q(last.amount)}"))
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    # ── dashboard card (M4 read-only) ────────────────────────────────────────
    def _year_rows(self, org_id: uuid.UUID, year_id: uuid.UUID | None) -> list[StudentFee]:
        q_ = (
            select(StudentFee).where(StudentFee.org_id == org_id)
            .options(selectinload(StudentFee.installments), selectinload(StudentFee.student))
        )
        if year_id:
            q_ = q_.where(StudentFee.academic_year_id == year_id)
        rows = list(self.db.scalars(q_))
        for sf in rows:
            recompute_student_fee(sf)
        return rows

    def summary(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> FeeSummary:
        today = date.today()
        rows = self._year_rows(m.org_id, year_id)
        total_fee = q(sum(q(sf.net_fee) for sf in rows))
        collected = q(sum(aggregate_paid(sf.installments) for sf in rows))
        pending_count = 0
        overdue_amt = q(0)
        for sf in rows:
            for i in sf.installments:
                unpaid = q(i.amount) - q(i.paid_amount)
                if unpaid <= 0:
                    continue
                if i.due_date and i.due_date < today:
                    overdue_amt = q(overdue_amt + unpaid)
                else:
                    pending_count += 1
        return FeeSummary(
            total_fee=total_fee, collected_fee=collected,
            pending_installments=pending_count, overdue_amount=overdue_amt,
        )

    def overdue_students(
        self, m: CurrentMember, *, year_id=None, limit=20, offset=0
    ) -> list[OverdueStudent]:
        today = date.today()
        rows = self._year_rows(m.org_id, year_id)
        out: list[OverdueStudent] = []
        for sf in rows:
            overdue_total = q(0)
            earliest: date | None = None
            for i in sf.installments:
                unpaid = q(i.amount) - q(i.paid_amount)
                if unpaid > 0 and i.due_date and i.due_date < today:
                    overdue_total = q(overdue_total + unpaid)
                    if earliest is None or i.due_date < earliest:
                        earliest = i.due_date
            if overdue_total > 0:
                out.append(OverdueStudent(
                    student_fee_id=sf.id,
                    student_name=sf.student.full_name if sf.student else "",
                    class_label=self._class_label(sf.student.class_id) if sf.student else None,
                    overdue_amount=overdue_total, earliest_due_date=earliest,
                ))
        out.sort(key=lambda o: (o.earliest_due_date or date.max))
        return out[offset : offset + limit]
