"""The mutable instalment schedule (FE-1, `D-121`).

The founder's requirement was one line — *"we can add installments as well (some
cases some parent wants more installments to pay)"* — and it is the thing the fee
module could not do at all: nothing in the API could add, split or remove an
instalment after enrolment.

**One invariant governs all three operations: `sum(instalments) == net payable`.**
It is asserted after every mutation by `fee_math.assert_balanced`, in one place,
because the failure is silent. A split that loses a rupee raises nothing at the
time; it just makes the school's books quietly wrong until a parent adds up their
receipts and finds a number nobody can explain.

So the three operations are shaped to preserve it rather than to trust the caller:

* **split** divides one instalment into parts that sum to the original. The
  total cannot move, whatever the caller sends. This is the one to reach for.
* **add** takes the new instalment's amount *out of* the unpaid ones,
  proportionally. The family owes the same money on a different calendar.
* **remove** gives an unpaid instalment's amount back to the others.

Changing what is owed is a **discount**, and lives in `services/fees.py`. A
schedule edit that could change the total would be a discount nobody logged.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import Installment, Student, StudentFee, Transaction
from app.schemas.fees import AddInstallmentIn, SplitInstallmentIn, StudentFeeDetail
from app.services import fee_events
from app.services.fee_math import (
    assert_balanced,
    even_split,
    live_installments,
    q,
    rebalance_unpaid,
    recompute_student_fee,
)


class FeeScheduleService:
    def __init__(self, db: Session):
        self.db = db

    # ── loading ──────────────────────────────────────────────────────────────
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

    def _load_inst(
        self, org_id: uuid.UUID, inst_id: uuid.UUID
    ) -> tuple[Installment, StudentFee]:
        inst = self.db.scalar(
            select(Installment).where(
                Installment.id == inst_id, Installment.org_id == org_id
            )
        )
        if inst is None:
            raise NotFoundError("Instalment")
        sf = self._load_sf(org_id, inst.student_fee_id)
        return next(i for i in sf.installments if i.id == inst_id), sf

    def _guard_open(self, sf: StudentFee) -> None:
        """A closed record's schedule is history (`D-127`). Reopen it first."""
        if sf.closed_at is not None:
            raise ValidationError(
                "This fee record is closed. Reopen it before changing the "
                "instalment schedule."
            )

    # ── numbering ────────────────────────────────────────────────────────────
    def _renumber(self, sf: StudentFee) -> None:
        """1..n in the order the school will actually be paid.

        Ordered by due date, with undated instalments last: a schedule numbered
        by insertion order reads "1, 2, 5, 3, 4" on the family page the moment
        anything is split, and the number is the only handle a parent has when
        they ring up about "the third instalment".
        """
        rows = sorted(
            sf.installments,
            key=lambda i: (i.due_date or date.max, i.installment_number or 0),
        )
        for idx, inst in enumerate(rows, start=1):
            inst.installment_number = idx

    def _finish(self, sf: StudentFee) -> StudentFeeDetail:
        """Renumber, prove the invariant, re-derive status, hand back the detail.

        `assert_balanced` runs BEFORE the flush that would persist a bad
        schedule — the point is to refuse, not to record and apologise.
        """
        self._renumber(sf)
        assert_balanced(sf.net_fee, sf.installments)
        recompute_student_fee(sf)
        self.db.flush()
        from app.services.fees import FeeService  # noqa: PLC0415 — one detail shape

        return FeeService(self.db)._detail(sf)

    def _ledger(self, m: CurrentMember, sf: StudentFee,
                inst_id: uuid.UUID | None, note: str) -> None:
        """A schedule edit moves no money, so it writes a zero-amount
        `installment_edit` row — the same shape `update_due_date` already uses."""
        self.db.add(Transaction(
            org_id=m.org_id, student_fee_id=sf.id, installment_id=inst_id,
            amount=q(0), type="installment_edit", note=note,
            created_by=m.user_id, created_by_name=m.user.name,
        ))

    def _who(self, sf: StudentFee) -> str:
        return sf.student.full_name if sf.student else "This student"

    # ── split ────────────────────────────────────────────────────────────────
    def split(
        self, m: CurrentMember, inst_id: uuid.UUID, body: SplitInstallmentIn
    ) -> StudentFeeDetail:
        """Divide one instalment into several. The sum cannot change.

        Anything already paid stays on the **first** part. A family that has paid
        ₹5,000 of a ₹15,500 instalment and asks to spread the rest keeps its
        ₹5,000 exactly where it was; the alternative — spreading the paid amount
        across the new parts — would show money against instalments the family
        has not paid yet.
        """
        inst, sf = self._load_inst(m.org_id, inst_id)
        self._guard_open(sf)
        if inst.is_voided:
            raise ValidationError("That instalment was voided and cannot be split.")

        total = q(inst.amount)
        paid = q(inst.paid_amount)
        if paid >= total:
            raise ValidationError(
                "That instalment is fully paid, so there is nothing left to "
                "split. Add an instalment instead if the family needs more time "
                "on what remains."
            )

        if body.amounts:
            amounts = [q(a) for a in body.amounts]
            if q(sum(amounts)) != total:
                raise ValidationError(
                    f"The parts add up to ₹{q(sum(amounts))}, but the instalment "
                    f"is ₹{total}. Splitting cannot change what is owed."
                )
            if any(a <= 0 for a in amounts):
                raise ValidationError("Every part must be more than zero.")
        else:
            amounts = even_split(total, body.parts or 2)

        # The paid amount has to fit inside part one, or it would appear against
        # a part the family has not reached yet.
        if paid > amounts[0]:
            rest = q(total - paid)
            tail = even_split(rest, len(amounts) - 1) if len(amounts) > 1 else []
            amounts = [paid, *tail]

        label = inst.label or f"Instalment {inst.installment_number}"
        inst.amount = amounts[0]
        inst.label = f"{label} (1)"

        made: list[Installment] = []
        for idx, amount in enumerate(amounts[1:], start=2):
            made.append(Installment(
                org_id=m.org_id, student_fee_id=sf.id,
                installment_number=inst.installment_number + idx - 1,
                label=f"{label} ({idx})", amount=amount,
                # Undated on purpose: the school has not yet said when it wants
                # the new part, and `unscheduled` is a real state the collection
                # board already names rather than a bug. Inventing a date here
                # would make the board report money as due that nobody agreed.
                due_date=None,
            ))
        sf.installments.extend(made)
        self.db.add_all(made)
        self.db.flush()

        self._ledger(m, sf, inst.id, f"Split ₹{total} into {len(amounts)} parts")
        fee_events.record(
            self.db, m, "schedule_split",
            f"{self._who(sf)}: {label} of ₹{total:,.0f} split into "
            f"{len(amounts)} parts ({', '.join(f'₹{a:,.0f}' for a in amounts)}). "
            "The total owed is unchanged.",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"installment_id": str(inst.id), "parts": len(amounts),
                  "amounts": [str(a) for a in amounts]},
        )
        return self._finish(sf)

    # ── add ──────────────────────────────────────────────────────────────────
    def add(
        self, m: CurrentMember, sf_id: uuid.UUID, body: AddInstallmentIn
    ) -> StudentFeeDetail:
        """Append an instalment, funded from the unpaid ones.

        The dialog says where the money comes from before it commits, and this
        is the half that makes that sentence true: the new row's amount is taken
        proportionally out of what is still unpaid, so the family owes exactly
        what it owed a moment ago.
        """
        sf = self._load_sf(m.org_id, sf_id)
        self._guard_open(sf)
        amount = q(body.amount)
        if amount <= 0:
            raise ValidationError("An instalment has to be more than zero.")

        live = live_installments(sf.installments)
        unpaid_room = q(sum(q(i.amount) - q(i.paid_amount) for i in live))
        if amount > unpaid_room:
            raise ValidationError(
                f"₹{amount} is more than the ₹{unpaid_room} still unpaid on this "
                "schedule. A new instalment is funded out of what is still "
                "owed — it does not add to the bill."
            )

        added = Installment(
            org_id=m.org_id, student_fee_id=sf.id,
            installment_number=len(sf.installments) + 1,
            label=body.label, amount=amount, due_date=body.due_date,
        )
        sf.installments.append(added)
        self.db.add(added)
        self.db.flush()

        # Fund it: everything EXCEPT the new row shares the reduced remainder.
        others = [i for i in live_installments(sf.installments) if i.id != added.id]
        target = q(q(sf.net_fee) - amount)
        for inst_id, new_amount in rebalance_unpaid(target, others).items():
            match = next(i for i in others if i.id == inst_id)
            match.amount = new_amount

        self._ledger(m, sf, added.id, f"Added an instalment of ₹{amount}")
        fee_events.record(
            self.db, m, "schedule_added",
            f"{self._who(sf)}: an instalment of ₹{amount:,.0f} added"
            + (f", due {body.due_date:%d %b %Y}" if body.due_date
               else " with no due date yet")
            + ". Taken out of the unpaid instalments — the total owed is "
              "unchanged.",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"amount": str(amount),
                  "due_date": body.due_date.isoformat() if body.due_date else None},
        )
        return self._finish(sf)

    # ── remove ───────────────────────────────────────────────────────────────
    def remove(self, m: CurrentMember, inst_id: uuid.UUID) -> StudentFeeDetail:
        """Delete an unpaid instalment; its amount goes back to the others.

        Refused the moment anything has been paid against it. A row that carries
        a payment is part of the ledger's story, and removing it would leave a
        transaction pointing at nothing.
        """
        inst, sf = self._load_inst(m.org_id, inst_id)
        self._guard_open(sf)
        if q(inst.paid_amount) > 0:
            raise ValidationError(
                "That instalment has a payment against it, so it cannot be "
                "removed. Undo the payment first, or move its due date."
            )
        live = live_installments(sf.installments)
        if len(live) <= 1:
            raise ValidationError(
                "A fee record needs at least one instalment. Change what is owed "
                "with a discount instead."
            )

        amount = q(inst.amount)
        label = inst.label or f"Instalment {inst.installment_number}"
        sf.installments.remove(inst)
        self.db.delete(inst)
        self.db.flush()

        for iid, new_amount in rebalance_unpaid(sf.net_fee, sf.installments).items():
            match = next(i for i in sf.installments if i.id == iid)
            match.amount = new_amount

        self._ledger(m, sf, None, f"Removed {label} of ₹{amount}")
        fee_events.record(
            self.db, m, "schedule_removed",
            f"{self._who(sf)}: {label} of ₹{amount:,.0f} removed and shared "
            "across the remaining unpaid instalments. The total owed is "
            "unchanged.",
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={"amount": str(amount), "label": label},
        )
        return self._finish(sf)
