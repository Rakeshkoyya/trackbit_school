"""Fee operations (M6) — ported from fee_management_system to sync + org scoping.

Every query is org-scoped explicitly. Money goes through fee_math.q(); status is
recomputed after every mutation and never trusted as stored truth. The transactions
ledger is append-only — undo writes a compensating row (SPRD §4.6 invariants).
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    FeeEvent,
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
    CloseFeeIn,
    DueDateUpdate,
    FeeSetupOut,
    FeeSetupPreview,
    FeeSetupPreviewIn,
    FeeSetupStructure,
    FeeStructureCreate,
    FeeStructureOut,
    FeeSummary,
    InstallmentOut,
    OverdueStudent,
    PaymentIn,
    PlannedInstallmentOut,
    StudentFeeCreate,
    StudentFeeDetail,
    StudentFeeListItem,
    StudentFeeUpdate,
    TemplateOut,
    TransactionOut,
)
from app.services import fee_events
from app.services.fee_math import (
    aggregate_paid,
    assert_balanced,
    installment_status,
    live_installments,
    plan_installments,
    proportional_installments,
    q,
    recompute_student_fee,
)
from app.services.fee_proofs import FeeProofService, next_receipt_number


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
            fee_structure_id=sf.fee_structure_id,
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

    # ── FE-2: locking one student, with the discount agreed at the counter ────
    def _student(self, org_id: uuid.UUID, student_id: uuid.UUID) -> Student:
        student = self.db.scalar(
            select(Student)
            .where(Student.id == student_id, Student.org_id == org_id)
            .options(selectinload(Student.category))
        )
        if student is None:
            raise NotFoundError("Student")
        return student

    def _setup_context(self, m: CurrentMember, student_id: uuid.UUID,
                       year_id: uuid.UUID, fee_structure_id: uuid.UUID | None = None):
        """(student, the structure that prices her, her existing record if any)."""
        from app.services.fee_structures import FeeStructureService  # noqa: PLC0415

        student = self._student(m.org_id, student_id)
        self._year(m.org_id, year_id)
        if fee_structure_id is not None:
            fs = self.db.scalar(
                select(FeeStructure)
                .where(FeeStructure.id == fee_structure_id, FeeStructure.org_id == m.org_id)
                .options(selectinload(FeeStructure.templates),
                         selectinload(FeeStructure.category))
            )
            if fs is None:
                raise NotFoundError("Fee structure")
        else:
            fs = FeeStructureService(self.db).structure_for_student(
                m.org_id, year_id, student)
        existing = self.db.scalar(
            select(StudentFee).where(
                StudentFee.org_id == m.org_id, StudentFee.student_id == student_id,
                StudentFee.academic_year_id == year_id)
        )
        return student, fs, existing

    def setup(self, m: CurrentMember, student_id: uuid.UUID,
              year_id: uuid.UUID) -> FeeSetupOut:
        """What the "set this student up" screen opens on (FE-2).

        The office's real question is *what would she be billed if I do
        nothing?* — so the default mapping is priced and dated here, before any
        offer to change it. A class with no structure yet is a sentence on the
        screen, never a ₹0 form the school could accidentally lock in.
        """
        from app.services.fee_structures import FeeStructureService  # noqa: PLC0415

        student, fs, existing = self._setup_context(m, student_id, year_id)
        plan = plan_installments(q(fs.total_amount), list(fs.templates)) if fs else []
        # Everything pricing her class, whichever category. With `structure`
        # null and this non-empty the class IS priced — just not for a child in
        # her category — and the screen has to say so. That is the exact case
        # that made FE-2 look broken on a live school: class 5 priced for
        # Hostellers only, and the three day scholars in it were told the class
        # had no structure at all.
        siblings = FeeStructureService(self.db).structures_for_class_of(
            m.org_id, year_id, student)
        return FeeSetupOut(
            student_id=student.id, student_name=student.full_name,
            class_label=self._class_label(student.class_id),
            category_name=student.category.name if student.category else None,
            academic_year_id=year_id,
            already_locked=existing is not None,
            student_fee_id=existing.id if existing else None,
            structure=FeeSetupStructure(
                id=fs.id, class_name=fs.class_name, category_id=fs.category_id,
                category_name=fs.category.name if fs.category else None,
                total_amount=q(fs.total_amount),
                num_installments=fs.num_installments,
            ) if fs else None,
            class_structures=[
                FeeSetupStructure(
                    id=s.id, class_name=s.class_name, category_id=s.category_id,
                    category_name=s.category.name if s.category else None,
                    total_amount=q(s.total_amount),
                    num_installments=s.num_installments,
                )
                for s in siblings
            ],
            default_plan=[PlannedInstallmentOut(**p._asdict()) for p in plan],
        )

    def setup_preview(self, m: CurrentMember, body: FeeSetupPreviewIn) -> FeeSetupPreview:
        """The arithmetic, done here and shown before it is committed.

        Deliberately the same call the write makes: `plan_installments` over the
        same net. A browser that divided the money itself would disagree with the
        server on the first rounding remainder, and the family would be shown one
        schedule and handed another.
        """
        _student, fs, _existing = self._setup_context(
            m, body.student_id, body.academic_year_id, body.fee_structure_id)
        total = q(body.total_fee) if body.total_fee is not None else (
            q(fs.total_amount) if fs else q(0))
        discount = q(body.discount)
        opening = q(body.opening_dues)
        net = q(total - discount)
        warning: str | None = None
        if fs is None and body.total_fee is None:
            # Not a refusal — a prompt. FE-2 first shipped with this as a dead
            # end, and a school with an unpriced class (or a student not yet in
            # one) could not set that child up at all, which is exactly the
            # family standing at the counter with cash.
            #
            # The wording stays neutral about WHY there is no default, because
            # there are two reasons and the screen knows which from
            # `class_structures` — a class priced for one category only is not an
            # unpriced class, and saying so here would contradict the sheet.
            warning = ("There is no default price for this student — type the "
                       "total, or pick one of the class's structures.")
        elif net < 0:
            warning = (f"A discount of ₹{discount:,.0f} is more than the fee of "
                       f"₹{total:,.0f}.")
        plan = plan_installments(
            max(net, q(0)), list(fs.templates) if fs else [], body.num_installments)
        return FeeSetupPreview(
            total_fee=total, discount=discount, net_fee=net, opening_dues=opening,
            total_payable=q(net + opening),
            installments=[PlannedInstallmentOut(**p._asdict()) for p in plan],
            warning=warning,
        )

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

        if net < 0:
            raise ValidationError(
                f"A discount of ₹{discount} is more than the fee of ₹{total}.")

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
        elif body.fee_structure_id or body.num_installments:
            templates: list = []
            if body.fee_structure_id:
                fs = self.db.scalar(
                    select(FeeStructure)
                    .where(FeeStructure.id == body.fee_structure_id,
                           FeeStructure.org_id == m.org_id)
                    .options(selectinload(FeeStructure.templates))
                )
                if fs is None:
                    raise NotFoundError("Fee structure")
                templates = list(fs.templates)
            # FE-2 — one splitter, so the schedule written here is the one the
            # office was shown in the preview, to the paisa.
            inst_rows = [
                Installment(
                    org_id=m.org_id, installment_number=p.installment_number,
                    label=p.label, amount=p.amount, due_date=p.due_date,
                )
                for p in plan_installments(net, templates, body.num_installments)
            ]
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
        # `D-124` — the actor log. A fee agreed at the counter is a DECISION
        # somebody made, and "why is this child paying ₹8,000 less" is the
        # question that gets asked six months later, by a different person. The
        # bulk apply already records itself; a single lock has to as well, or the
        # discounted ones are exactly the records with no trail.
        if q(sf.discount) > 0:
            fee_events.record(
                self.db, m, "fee_created",
                f"{self._who(sf)} locked at ₹{q(sf.net_fee):,.0f} — "
                f"₹{q(sf.total_fee):,.0f} less a ₹{q(sf.discount):,.0f} discount, "
                f"in {len(inst_rows)} instalment{'' if len(inst_rows) == 1 else 's'}.",
                student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
                meta={"total_fee": str(q(sf.total_fee)),
                      "discount": str(q(sf.discount)),
                      "net_fee": str(q(sf.net_fee)),
                      "installments": len(inst_rows)},
            )
        else:
            fee_events.record(
                self.db, m, "fee_created",
                f"{self._who(sf)} set up at ₹{q(sf.net_fee):,.0f} in "
                f"{len(inst_rows)} instalment{'' if len(inst_rows) == 1 else 's'}.",
                student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
                meta={"net_fee": str(q(sf.net_fee)), "installments": len(inst_rows)},
            )
        return self._detail(sf)

    def update_discount(self, m: CurrentMember, sf_id: uuid.UUID, body: StudentFeeUpdate) -> StudentFeeDetail:
        """Change what this family owes, and re-scale the unpaid instalments.

        Three fences were missing here until FE-3, and each let the schedule
        stop adding up to the net **silently** — the one failure `D-121` exists
        to prevent:

        * a **closed** record was editable, and its voided rows re-scaled with
          the live ones, so a transfer could be quietly un-done by arithmetic;
        * `live_installments` was not applied, so a voided row absorbed money
          that nobody was being billed for;
        * nothing proved the result balanced. With every instalment fully paid
          there is no unpaid row to absorb a reduced discount, so the extra
          landed nowhere and the record simply stopped reconciling.
        """
        sf = self._load_sf(m.org_id, sf_id)
        if sf.closed_at is not None:
            raise ValidationError(
                "This fee record is closed. Reopen it before changing what is "
                "owed.")
        if body.opening_dues is not None:
            sf.opening_dues = q(body.opening_dues)
        if body.discount is not None:
            old_net = q(sf.net_fee)
            sf.discount = q(body.discount)
            sf.net_fee = q(q(sf.total_fee) - sf.discount)
            if sf.net_fee < 0:
                raise ValidationError(
                    f"A discount of ₹{q(sf.discount):,.0f} is more than the fee "
                    f"of ₹{q(sf.total_fee):,.0f}.")
            live = live_installments(sf.installments)
            paid = aggregate_paid(live)
            remaining = q(sf.net_fee - paid)
            if remaining < 0:
                raise ValidationError(
                    "Discount makes net payable lower than the amount already paid.")
            unpaid = [i for i in live if q(i.paid_amount) < q(i.amount)]
            if unpaid:
                current_unpaid_total = q(sum(q(i.amount) - q(i.paid_amount) for i in unpaid))
                scaled = (
                    proportional_installments(remaining, [q(i.amount) - q(i.paid_amount) for i in unpaid])
                    if current_unpaid_total > 0 else [remaining]
                )
                for idx, i in enumerate(unpaid):
                    i.amount = q(q(i.paid_amount) + scaled[idx])
            elif q(sum(q(i.amount) for i in live)) != q(sf.net_fee):
                raise ValidationError(
                    "Every instalment on this record is fully paid, so there is "
                    "nothing left to re-scale. Use Edit fee to re-enter the "
                    "schedule as well.")
            # Refuse rather than record and apologise (`D-121`).
            assert_balanced(sf.net_fee, sf.installments)
            self.db.add(self._txn(m, sf.id, None, q(sf.net_fee - old_net), "discount",
                                  f"Discount updated to ₹{sf.discount}"))
            fee_events.record(
                self.db, m, "discount_changed",
                f"{self._who(sf)}'s discount set to ₹{q(sf.discount):,.0f} — "
                f"net payable is now ₹{q(sf.net_fee):,.0f}. The unpaid "
                "instalments were re-scaled to match.",
                student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
                meta={"discount": str(q(sf.discount)),
                      "net_fee": str(q(sf.net_fee))},
            )
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    # ── D-127: the transfer ──────────────────────────────────────────────────
    def close_record(self, m: CurrentMember, sf_id: uuid.UUID,
                     body: CloseFeeIn) -> StudentFeeDetail:
        """The student has transferred out (founder Q-2).

        What happens, in his words: *"the amount will be closed and remaining
        balance will be detected from total and the student status will be
        closed"*. Concretely:

        * an instalment with nothing paid against it is **voided** — not
          deleted (law 3), so the transfer can be undone and so the family page
          can still show what was originally scheduled;
        * a part-paid instalment is trimmed to what was actually paid, so the
          unpaid remainder comes off the bill rather than being chased;
        * `net_fee` drops to the sum of what survives, which zeroes the balance;
        * the record goes `closed` and leaves the collection board alone.

        The undo buffer is the event's own `meta` snapshot. That is deliberate:
        the log is append-only and already the thing nobody may rewrite, so
        putting the restore data there means an undo cannot outlive its record.
        """
        sf = self._load_sf(m.org_id, sf_id)
        if sf.closed_at is not None:
            raise ValidationError("This fee record is already closed.")

        snapshot = [
            {"id": str(i.id), "amount": str(q(i.amount)),
             "is_voided": bool(i.is_voided)}
            for i in sf.installments
        ]
        released = q(0)
        for inst in sf.installments:
            if inst.is_voided:
                continue
            paid = q(inst.paid_amount)
            amount = q(inst.amount)
            if paid <= 0:
                inst.is_voided = True
                released = q(released + amount)
            elif paid < amount:
                released = q(released + (amount - paid))
                inst.amount = paid
        kept = q(sum(q(i.amount) for i in sf.installments if not i.is_voided))

        sf.net_fee = kept
        sf.closed_at = datetime.now(UTC)
        sf.closed_reason = body.reason
        sf.closed_by_member_id = m.membership.id
        sf.status = "closed"

        self.db.add(self._txn(
            m, sf.id, None, q(-released), "installment_edit",
            f"Record closed on transfer — ₹{released} written off"))
        fee_events.record(
            self.db, m, "record_closed",
            f"{self._who(sf)}'s fee record was closed on transfer. "
            f"₹{released:,.0f} of unpaid instalments came off the bill; "
            f"₹{kept:,.0f} stands as billed."
            + (f" Reason: {body.reason}" if body.reason else ""),
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"released": str(released), "previous_net_fee": str(kept + released),
                  "installments": snapshot},
        )
        self.db.flush()
        return self._detail(sf)

    def reopen_record(self, m: CurrentMember, sf_id: uuid.UUID) -> StudentFeeDetail:
        """Undo the transfer — the founder asked for this in the same breath:
        *"we can open the stundent and undo the transfer as well"*.

        Restores from the snapshot the close wrote into the log. If there is no
        snapshot to restore from we refuse rather than guess: silently
        re-inventing a schedule would put amounts in front of a family that
        nobody ever agreed.
        """
        sf = self._load_sf(m.org_id, sf_id)
        if sf.closed_at is None:
            raise ValidationError("This fee record is not closed.")

        last = self.db.scalar(
            select(FeeEvent)
            .where(FeeEvent.org_id == m.org_id, FeeEvent.student_fee_id == sf.id,
                   FeeEvent.kind == "record_closed")
            .order_by(FeeEvent.created_at.desc()).limit(1)
        )
        if last is None or not last.meta.get("installments"):
            raise ValidationError(
                "There is no record of how this fee looked before it was "
                "closed, so it cannot be restored automatically.")

        by_id = {row["id"]: row for row in last.meta["installments"]}
        for inst in sf.installments:
            row = by_id.get(str(inst.id))
            if row is None:
                continue
            inst.amount = q(row["amount"])
            inst.is_voided = bool(row["is_voided"])
        sf.net_fee = q(last.meta.get("previous_net_fee", sf.net_fee))
        sf.closed_at = None
        sf.closed_reason = None
        sf.closed_by_member_id = None

        assert_balanced(sf.net_fee, sf.installments)
        self.db.add(self._txn(
            m, sf.id, None, q(last.meta.get("released", 0)), "installment_edit",
            "Record reopened — the transfer was undone"))
        fee_events.record(
            self.db, m, "record_reopened",
            f"{self._who(sf)}'s fee record was reopened and the transfer undone. "
            f"₹{q(sf.net_fee):,.0f} is payable again.",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"restored_net_fee": str(q(sf.net_fee))},
        )
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
    def _who(self, sf: StudentFee) -> str:
        return sf.student.full_name if sf.student else "this student"

    def pay(self, m: CurrentMember, inst_id: uuid.UUID, body: PaymentIn) -> StudentFeeDetail:
        inst, sf = self._load_installment(m.org_id, inst_id)
        if sf.closed_at is not None:
            raise ValidationError(
                "This fee record is closed. Reopen it before recording a payment.")
        if inst.is_voided:
            raise ValidationError("That instalment was voided.")
        amount = q(body.amount)
        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")
        remaining = q(q(inst.amount) - q(inst.paid_amount))
        if amount > remaining:
            raise ValidationError(
                f"Payment ₹{amount} exceeds remaining balance ₹{remaining} on this installment.")
        paid_on = body.paid_on or date.today()
        inst.paid_amount = q(q(inst.paid_amount) + amount)
        inst.paid_date = paid_on
        # `D-128`: the school gets a receipt number without typing one, but a
        # number it DID type always wins — reconciling against a pre-printed
        # book is the case that breaks if we overwrite it.
        receipt = body.receipt_number or next_receipt_number(
            self.db, m.org_id, sf.academic_year_id)
        txn = self._txn(m, sf.id, inst.id, amount, "payment", body.note,
                        body.mode, receipt)
        txn.paid_on = paid_on
        self.db.add(txn)
        self.db.flush()
        if body.proof_key:
            # One round trip for the payment and its evidence. Deliberately
            # after the transaction is flushed, so the proof has a real id to
            # hang off and a failed attach cannot lose the payment.
            FeeProofService(self.db).confirm(m, txn.id, body.proof_key)
        fee_events.record(
            self.db, m, "payment_recorded",
            f"₹{amount:,.0f} received from {self._who(sf)}"
            + (f" by {body.mode}" if body.mode else "")
            + (f" · receipt {receipt}" if receipt else "") + ".",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"amount": str(amount), "mode": body.mode, "receipt": receipt,
                  "installment_id": str(inst.id)},
        )
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def mark_paid(self, m: CurrentMember, inst_id: uuid.UUID) -> StudentFeeDetail:
        inst, sf = self._load_installment(m.org_id, inst_id)
        if sf.closed_at is not None:
            raise ValidationError(
                "This fee record is closed. Reopen it before recording a payment.")
        if inst.is_voided:
            raise ValidationError("That instalment was voided.")
        remaining = q(q(inst.amount) - q(inst.paid_amount))
        if remaining <= 0:
            raise ValidationError("Installment is already fully paid.")
        inst.paid_amount = q(inst.amount)
        inst.paid_date = date.today()
        receipt = next_receipt_number(self.db, m.org_id, sf.academic_year_id)
        txn = self._txn(m, sf.id, inst.id, remaining, "payment",
                        "Marked fully paid", "cash", receipt)
        txn.paid_on = inst.paid_date
        self.db.add(txn)
        fee_events.record(
            self.db, m, "payment_recorded",
            f"₹{remaining:,.0f} received from {self._who(sf)} — marked fully paid"
            + (f" · receipt {receipt}" if receipt else "") + ".",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"amount": str(remaining), "receipt": receipt,
                  "installment_id": str(inst.id)},
        )
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
        fee_events.record(
            self.db, m, "payment_undone",
            f"A payment of ₹{q(last.amount):,.0f} from {self._who(sf)} was "
            "reverted. The original payment stays in the ledger — the undo is a "
            "compensating entry.",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"amount": str(q(last.amount)), "installment_id": str(inst.id)},
        )
        recompute_student_fee(sf)
        self.db.flush()
        return self._detail(sf)

    def update_due_date(self, m: CurrentMember, inst_id: uuid.UUID,
                        body: DueDateUpdate) -> StudentFeeDetail:
        """Move (or clear) the date the school is asking for this instalment by.

        **This method did not exist.** `PATCH /fees/installments/{id}/due-date`
        has been routed to it since P0-D and raised `AttributeError` — a 500 —
        on every call. Nothing in the web client called the route, so nothing
        ever surfaced it; the V1-13 no-dead-ends sweep looked for orphaned
        *client methods* and for GET routes with no caller, and this is neither.

        It matters now because the collection board reports an instalment with
        no due date as **`unscheduled`** — in no quarter, in `billed` but never
        in `due_by_today` — and this route is the only way to resolve that
        state. A board that names a problem whose only fix is a 500 has made
        the admin's day worse (ux §7).

        The due date is a plan, not money: it changes no amount, no
        `paid_amount` and no status, so it writes an `installment_edit` row to
        the append-only ledger rather than a payment. Clearing it back to NULL
        is allowed — a school that set a date by mistake has to be able to take
        it off, and `unscheduled` is a legitimate state, not an error.
        """
        inst, sf = self._load_installment(m.org_id, inst_id)
        was = inst.due_date
        if was == body.due_date:
            return self._detail(sf)
        inst.due_date = body.due_date
        # Status is derived from the date, so re-derive it: an instalment that
        # was overdue and has been given a later date is not overdue any more.
        inst.status = installment_status(inst, date.today())
        self.db.add(self._txn(
            m, sf.id, inst.id, q(0), "installment_edit",
            f"Due date {was.isoformat() if was else 'none'} → "
            f"{body.due_date.isoformat() if body.due_date else 'none'}"))
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
            for i in live_installments(sf.installments):
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
        # V1-0e/S-162: one query for every class label — this used to run
        # `db.get(SchoolClass, …)` per student, so 200 overdue students was 200
        # round trips for one list.
        class_ids = {sf.student.class_id for sf in rows
                     if sf.student and sf.student.class_id}
        labels = {
            cid: name + (f"-{sec}" if sec else "")
            for cid, name, sec in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.id.in_(class_ids))).all()
        } if class_ids else {}
        out: list[OverdueStudent] = []
        for sf in rows:
            overdue_total = q(0)
            earliest: date | None = None
            for i in live_installments(sf.installments):
                unpaid = q(i.amount) - q(i.paid_amount)
                if unpaid > 0 and i.due_date and i.due_date < today:
                    overdue_total = q(overdue_total + unpaid)
                    if earliest is None or i.due_date < earliest:
                        earliest = i.due_date
            if overdue_total > 0:
                out.append(OverdueStudent(
                    student_fee_id=sf.id,
                    student_name=sf.student.full_name if sf.student else "",
                    class_label=(labels.get(sf.student.class_id)
                                 if sf.student else None),
                    overdue_amount=overdue_total, earliest_due_date=earliest,
                ))
        out.sort(key=lambda o: (o.earliest_due_date or date.max))
        return out[offset : offset + limit]
