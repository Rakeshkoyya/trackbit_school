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
from app.schemas.fees import (
    AddInstallmentIn,
    FeeReviseIn,
    SplitInstallmentIn,
    StudentFeeDetail,
)
from app.services import fee_events
from app.services.fee_math import (
    assert_balanced,
    even_split,
    live_installments,
    plan_installments,
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

    # ── revise ───────────────────────────────────────────────────────────────
    def _label(self, inst: Installment) -> str:
        return inst.label or f"Instalment {inst.installment_number}"

    def _plan_rows(
        self, sf: StudentFee, net, num_installments: int | None
    ) -> list[dict]:
        """Re-plan `net` into N rows through the one splitter.

        Keeps the class's own labels and due dates when the count still matches
        the structure's — the same mapping `enroll` writes, because a record
        being corrected should land exactly where it would have landed had the
        right numbers been typed the first time.
        """
        from app.models import FeeStructure  # noqa: PLC0415 — avoids a cycle

        templates: list = []
        if sf.fee_structure_id is not None:
            fs = self.db.scalar(
                select(FeeStructure)
                .where(FeeStructure.id == sf.fee_structure_id,
                       FeeStructure.org_id == sf.org_id)
                .options(selectinload(FeeStructure.templates))
            )
            if fs is not None:
                templates = list(fs.templates)
        return [
            {"id": None, "label": p.label, "amount": p.amount,
             "due_date": p.due_date}
            for p in plan_installments(net, templates, num_installments)
        ]

    def _apply_schedule(
        self, m: CurrentMember, sf: StudentFee, rows: list[dict], net
    ) -> None:
        """Make the live schedule be exactly `rows`.

        Rows carrying an `id` are existing instalments kept in place; the rest
        are new; live instalments nobody listed are deleted. Everything is
        checked BEFORE anything is written, so a schedule the server is going to
        refuse never half-lands.
        """
        live = live_installments(sf.installments)
        by_id = {i.id: i for i in live}

        if not rows:
            raise ValidationError("A fee record needs at least one instalment.")

        kept = [r["id"] for r in rows if r.get("id") is not None]
        if len(set(kept)) != len(kept):
            raise ValidationError("An instalment is listed twice.")
        for inst_id in kept:
            if inst_id not in by_id:
                raise ValidationError(
                    "One of those instalments is not on this fee record any "
                    "more. Close the sheet and open it again."
                )
        keep = set(kept)

        amounts = [q(r["amount"]) for r in rows]
        if any(a <= 0 for a in amounts):
            raise ValidationError("Every instalment has to be more than zero.")
        if q(sum(amounts)) != q(net):
            raise ValidationError(
                f"The instalments add up to ₹{q(sum(amounts)):,.2f}, but "
                f"₹{q(net):,.2f} is payable. Adjust the rows, or change the "
                "total or the discount to match."
            )

        # Money that has landed decides what may be deleted. A row carrying a
        # payment is the other half of a receipt the family is holding, and
        # dropping it would leave that transaction pointing at nothing.
        for inst in live:
            if q(inst.paid_amount) > 0 and inst.id not in keep:
                raise ValidationError(
                    f"{self._label(inst)} has ₹{q(inst.paid_amount):,.0f} paid "
                    "against it, so it cannot be deleted. Undo that payment "
                    "first, or keep the instalment and change its amount."
                )
        for idx, row in enumerate(rows):
            inst_id = row.get("id")
            if inst_id is None:
                continue
            paid = q(by_id[inst_id].paid_amount)
            if amounts[idx] < paid:
                raise ValidationError(
                    f"{self._label(by_id[inst_id])} already has ₹{paid:,.0f} "
                    f"paid against it, so it cannot be set to "
                    f"₹{amounts[idx]:,.0f}."
                )

        # ── every check has passed; only now does anything change ──
        for inst in [i for i in live if i.id not in keep]:
            sf.installments.remove(inst)
            self.db.delete(inst)

        made: list[Installment] = []
        for idx, row in enumerate(rows, start=1):
            inst_id = row.get("id")
            label = row.get("label") or None
            if inst_id is not None:
                inst = by_id[inst_id]
                inst.installment_number = idx
                inst.label = label
                inst.amount = amounts[idx - 1]
                inst.due_date = row.get("due_date")
            else:
                made.append(Installment(
                    org_id=m.org_id, student_fee_id=sf.id, installment_number=idx,
                    label=label, amount=amounts[idx - 1],
                    due_date=row.get("due_date"),
                ))
        sf.installments.extend(made)
        self.db.add_all(made)
        self.db.flush()

    def revise(
        self, m: CurrentMember, sf_id: uuid.UUID, body: FeeReviseIn
    ) -> StudentFeeDetail:
        """Correct a record that was set up wrong (FE-3).

        Everything the office typed at enrolment — the total, the discount, the
        previous dues and the whole schedule — becomes editable again here, in
        **one** operation. That matters more than it looks: as a sequence of
        small edits every intermediate state would have to balance, so
        *"₹60,000 in 4 should have been ₹45,000 in 6"* is not expressible at
        all — the first step alone is refused. As one revision it is a single
        decision, checked once and logged once.

        The fences are the three the rest of the module already holds:

        * **collected money is never un-billed.** The new net cannot fall below
          what has been paid, no row may be set below its own paid amount, and a
          row carrying a payment cannot be deleted;
        * **the schedule always sums to the net** — proved by `assert_balanced`
          inside `_finish`, on every path through here;
        * **a closed record is history.** Reopen it first.

        This is a correction, not a discount, and the log says so. Six months
        later those are different conversations: one is *"what did we agree to
        give this family"*, the other is *"what did we get wrong"*.
        """
        sf = self._load_sf(m.org_id, sf_id)
        self._guard_open(sf)

        before = {
            "total_fee": str(q(sf.total_fee)),
            "discount": str(q(sf.discount)),
            "net_fee": str(q(sf.net_fee)),
            "opening_dues": str(q(sf.opening_dues)),
            "installments": [
                {"id": str(i.id), "label": i.label, "amount": str(q(i.amount)),
                 "due_date": i.due_date.isoformat() if i.due_date else None,
                 "paid_amount": str(q(i.paid_amount)),
                 "is_voided": bool(i.is_voided)}
                for i in sorted(sf.installments,
                                key=lambda i: i.installment_number)
            ],
        }

        total = q(body.total_fee) if body.total_fee is not None else q(sf.total_fee)
        discount = (q(body.discount) if body.discount is not None
                    else q(sf.discount))
        opening = (q(body.opening_dues) if body.opening_dues is not None
                   else q(sf.opening_dues))
        if total < 0 or discount < 0 or opening < 0:
            raise ValidationError("Fees, discounts and dues cannot be negative.")
        net = q(total - discount)
        if net < 0:
            raise ValidationError(
                f"A discount of ₹{discount:,.0f} is more than the fee of "
                f"₹{total:,.0f}."
            )

        live = live_installments(sf.installments)
        paid = q(sum(q(i.paid_amount) for i in live))
        if net < paid:
            raise ValidationError(
                f"₹{paid:,.0f} has already been collected from this family, so "
                f"the payable cannot be set to ₹{net:,.0f}. Undo a payment "
                "first."
            )

        if body.installments is not None and body.num_installments is not None:
            raise ValidationError(
                "Send either the instalment rows or a number of instalments, "
                "not both."
            )

        # The three ways to land on a schedule, most explicit first.
        if body.installments is not None:
            rows = [
                {"id": r.id, "label": r.label, "amount": r.amount,
                 "due_date": r.due_date}
                for r in body.installments
            ]
            self._apply_schedule(m, sf, rows, net)
            n = len(rows)
            how = f"re-entered as {n} instalment{'' if n == 1 else 's'}"
        elif body.num_installments is not None:
            # A re-plan discards the old rows, so it only runs on a record
            # nothing has been paid on. `_apply_schedule` is what refuses
            # otherwise, and it names the instalment and the amount.
            rows = self._plan_rows(sf, net, body.num_installments)
            self._apply_schedule(m, sf, rows, net)
            n = len(rows)
            how = f"re-planned into {n} instalment{'' if n == 1 else 's'}"
        else:
            # Money only. The unpaid rows re-scale to the new net, which is what
            # changing the discount has always meant.
            moved = rebalance_unpaid(net, sf.installments)
            for inst_id, amount in moved.items():
                match = next(i for i in sf.installments if i.id == inst_id)
                match.amount = amount
            if not moved and net != q(sum(q(i.amount) for i in live)):
                # Everything is fully paid, so nothing can absorb the change.
                # Accepting it quietly is how a schedule stops adding up to the
                # net with nobody told — the exact silent failure `D-121` names.
                raise ValidationError(
                    "Every instalment on this record is fully paid, so there is "
                    "nothing left to re-scale. Change the schedule too — "
                    "re-enter the rows, or add an instalment for the difference."
                )
            how = "re-priced"

        sf.total_fee = total
        sf.discount = discount
        sf.opening_dues = opening
        sf.net_fee = net

        # `_finish` renumbers, PROVES the schedule sums to the net, and
        # re-derives every status. If the revision does not balance it raises
        # here, before the flush that would have persisted it.
        detail = self._finish(sf)

        old_net = q(before["net_fee"])
        delta = q(net - old_net)
        self._ledger(m, sf, None,
                     f"Record revised — payable ₹{old_net} → ₹{net}")
        if delta != 0:
            # The money ledger carries the change in what is owed, so a sum over
            # `fee_transactions` still reconciles with the record.
            self.db.add(Transaction(
                org_id=m.org_id, student_fee_id=sf.id, installment_id=None,
                amount=delta, type="discount",
                note=f"Fee revised — payable ₹{old_net} → ₹{net}",
                created_by=m.user_id, created_by_name=m.user.name,
            ))

        parts: list[str] = []
        if q(before["total_fee"]) != total:
            parts.append(f"total ₹{q(before['total_fee']):,.0f} → ₹{total:,.0f}")
        if q(before["discount"]) != discount:
            parts.append(
                f"discount ₹{q(before['discount']):,.0f} → ₹{discount:,.0f}")
        if q(before["opening_dues"]) != opening:
            parts.append(
                f"previous dues ₹{q(before['opening_dues']):,.0f} → "
                f"₹{opening:,.0f}")
        n_live = len(live_installments(sf.installments))
        summary = (
            f"{self._who(sf)}'s fee record was revised: "
            + (", ".join(parts) + ". " if parts else "")
            + f"The schedule was {how} and now stands at ₹{net:,.0f} payable "
            f"across {n_live} instalment{'' if n_live == 1 else 's'}."
            + (f" Reason: {body.reason}" if body.reason else "")
        )
        fee_events.record(
            self.db, m, "fee_revised", summary,
            student_fee_id=sf.id, academic_year_id=sf.academic_year_id,
            meta={
                "before": before,
                "after": {
                    "total_fee": str(total), "discount": str(discount),
                    "net_fee": str(net), "opening_dues": str(opening),
                    "installments": [
                        {"id": str(i.id), "label": i.label,
                         "amount": str(q(i.amount)),
                         "due_date": i.due_date.isoformat() if i.due_date
                         else None}
                        for i in sorted(sf.installments,
                                        key=lambda i: i.installment_number)
                    ],
                },
                "reason": body.reason,
            },
        )
        return detail
