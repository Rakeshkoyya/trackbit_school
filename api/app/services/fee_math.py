"""Fee money math — ported nearly verbatim from fee_management_system (SPRD §4.6).

Behavioural invariants carried over (do not "improve" these — they match the
school's real registers): 2-dp Decimal via q(); status is COMPUTED, never stored
as truth; proportional discount rescaling of the unpaid portion; waterfall spread
of a lump payment; monthly default due dates from the April year-start.
"""

from datetime import date
from decimal import Decimal

from app.models.fees import Installment, StudentFee


def q(value) -> Decimal:
    """Coerce to a 2dp Decimal (the only way fee amounts are ever rounded)."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def installment_status(inst: "Installment", today: date | None = None) -> str:
    today = today or date.today()
    paid = q(inst.paid_amount)
    amount = q(inst.amount)
    if paid >= amount and amount > 0:
        return "paid"
    if inst.due_date and inst.due_date < today and paid < amount:
        return "overdue"
    if paid > 0:
        return "partial"
    return "pending"


def recompute_installment(inst: "Installment", today: date | None = None) -> None:
    inst.status = installment_status(inst, today)
    if q(inst.paid_amount) >= q(inst.amount) and q(inst.amount) > 0:
        inst.paid_date = inst.paid_date or (today or date.today())


def aggregate_paid(installments: list["Installment"]) -> Decimal:
    return q(sum(q(i.paid_amount) for i in installments))


def overdue_amount(installments: list["Installment"], today: date | None = None) -> Decimal:
    today = today or date.today()
    total = Decimal("0")
    for i in installments:
        if i.due_date and i.due_date < today and q(i.paid_amount) < q(i.amount):
            total += q(i.amount) - q(i.paid_amount)
    return q(total)


def student_fee_status(
    sf: "StudentFee", installments: list["Installment"], today: date | None = None
) -> str:
    today = today or date.today()
    # `D-127`: closed is a DECISION somebody made, not a derivation, so it
    # outranks everything below. Without this, `recompute_student_fee` — which
    # runs after every mutation — would quietly relabel a transferred student's
    # record `paid`, and the transfer would vanish from every screen.
    if getattr(sf, "closed_at", None) is not None:
        return "closed"
    net = q(sf.net_fee)
    paid = aggregate_paid(installments)
    if net > 0 and paid >= net:
        return "paid"
    if overdue_amount(installments, today) > 0:
        return "overdue"
    if paid > 0:
        return "partial"
    return "pending"


def recompute_student_fee(sf: "StudentFee", today: date | None = None) -> None:
    """Call after ANY mutation: derives per-installment + rollup status. Overdue is
    never persisted as truth — it's this query-time comparison."""
    for inst in sf.installments:
        recompute_installment(inst, today)
    sf.status = student_fee_status(sf, sf.installments, today)


def even_split(total, n: int) -> list[Decimal]:
    """Split ``total`` into ``n`` parts; remainder lands on the last part."""
    total = q(total)
    if n <= 0:
        return []
    base = (total / n).quantize(Decimal("0.01"))
    parts = [base] * (n - 1)
    parts.append(q(total - base * (n - 1)))
    return parts


def default_due_dates(n: int, start: date | None = None) -> list[date]:
    """Monthly due dates from the academic-year start (April by default)."""
    if start is None:
        today = date.today()
        year = today.year if today.month >= 4 else today.year - 1
        start = date(year, 4, 1)
    out: list[date] = []
    for i in range(n):
        month_index = start.month - 1 + i * (12 // max(n, 1) if n <= 12 else 1)
        y = start.year + month_index // 12
        m = month_index % 12 + 1
        out.append(date(y, m, 1))
    return out


def proportional_installments(net_fee, template_amounts: list) -> list[Decimal]:
    """Scale template amounts so they sum exactly to net_fee (after discount).

    Rounding drift is absorbed by the last element so the parts always re-sum to
    net_fee to the paisa."""
    net_fee = q(net_fee)
    gross = q(sum(q(a) for a in template_amounts))
    if gross <= 0:
        return even_split(net_fee, len(template_amounts) or 1)
    scaled = [q(q(a) * net_fee / gross) for a in template_amounts]
    drift = net_fee - q(sum(scaled))
    if scaled:
        scaled[-1] = q(scaled[-1] + drift)
    return scaled


def live_installments(installments: list["Installment"]) -> list["Installment"]:
    """The instalments that still count.

    A voided one (`D-127`, the transfer) is not owed, was not collected, and must
    not appear in any total — but the row survives so the transfer can be undone
    and so the family page can still show what was originally scheduled."""
    return [i for i in installments if not getattr(i, "is_voided", False)]


def assert_balanced(net_fee, installments: list["Installment"]) -> None:
    """`D-121` — the schedule always adds up to what is owed.

    Called after EVERY schedule mutation, from one place, because the failure it
    prevents is silent: a split that loses ₹1 or an add that quietly increases
    the total does not raise anything at the time, it just makes the school's
    books wrong in a way nobody notices until a parent adds up their receipts.

    Voided instalments are excluded — see `live_installments`.
    """
    from app.core.exceptions import ValidationError  # noqa: PLC0415 — avoids a cycle

    total = q(sum(q(i.amount) for i in live_installments(installments)))
    net = q(net_fee)
    if total != net:
        raise ValidationError(
            f"The instalments would add up to ₹{total}, but ₹{net} is payable. "
            "The schedule may be re-arranged, but the total cannot change here — "
            "use the discount to change what is owed."
        )


def rebalance_unpaid(net_fee, installments: list["Installment"]) -> dict:
    """New amounts for the UNPAID portion so the schedule re-sums to `net_fee`.

    Returns `{installment_id: new_amount}`, and never drops an instalment below
    what has already been paid on it — money that has landed cannot be
    un-billed by moving the schedule around. Rounding drift lands on the last
    adjustable row so the parts always re-sum to the paisa.
    """
    from app.core.exceptions import ValidationError  # noqa: PLC0415 — avoids a cycle

    live = live_installments(installments)
    net = q(net_fee)
    paid_total = q(sum(q(i.paid_amount) for i in live))
    adjustable = [i for i in live if q(i.paid_amount) < q(i.amount)]
    if not adjustable:
        return {}
    room = q(net - paid_total)          # what is left to spread over the unpaid
    if room < 0:
        raise ValidationError(
            f"₹{paid_total} has already been paid, which is more than the "
            f"₹{net} that would be payable."
        )
    current = [q(q(i.amount) - q(i.paid_amount)) for i in adjustable]
    shares = proportional_installments(room, current)
    return {
        i.id: q(q(i.paid_amount) + shares[idx]) for idx, i in enumerate(adjustable)
    }


def waterfall(dues: list, amount) -> list[Decimal]:
    """Spread a lump ``amount`` across ordered installment dues, filling each up to
    its remaining balance (SPRD §4.6 — lump-payment spread on import)."""
    amount = q(amount)
    out: list[Decimal] = []
    for due in dues:
        take = q(min(q(due), amount)) if amount > 0 else q(0)
        if take < 0:
            take = q(0)
        out.append(take)
        amount = q(amount - take)
    return out
