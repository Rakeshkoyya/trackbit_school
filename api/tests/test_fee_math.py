"""P0-D: fee money math (SPRD §4.6 invariants). Pure — no DB needed."""

from datetime import date
from decimal import Decimal

from app.models.fees import Installment, StudentFee
from app.services import fee_math as fm

D = lambda s: Decimal(s)  # noqa: E731


def test_q_rounds_to_2dp():
    assert fm.q("100") == D("100.00")
    assert fm.q(33.333) == D("33.33")
    assert fm.q(None) == D("0.00")


def test_even_split_sums_and_puts_remainder_last():
    parts = fm.even_split(D("100.00"), 3)
    assert parts == [D("33.33"), D("33.33"), D("33.34")]
    assert sum(parts) == D("100.00")


def test_proportional_installments_sum_exactly_to_net():
    # Scale a 30k structure down to a 20k net; parts must re-sum to the paisa.
    scaled = fm.proportional_installments(D("20000.00"), [D("10000"), D("10000"), D("10000")])
    assert sum(scaled) == D("20000.00")
    # zero-gross falls back to an even split
    assert sum(fm.proportional_installments(D("500.00"), [D("0"), D("0")])) == D("500.00")


def test_waterfall_fills_in_order_without_overpaying():
    dues = [D("100"), D("100"), D("100")]
    assert fm.waterfall(dues, D("150")) == [D("100.00"), D("50.00"), D("0.00")]
    assert fm.waterfall(dues, D("500")) == [D("100.00"), D("100.00"), D("100.00")]  # capped at dues
    assert fm.waterfall(dues, D("0")) == [D("0.00"), D("0.00"), D("0.00")]


def _inst(amount, paid, due):
    return Installment(amount=D(amount), paid_amount=D(paid), due_date=due)


def test_installment_status_transitions():
    today = date(2026, 6, 1)
    assert fm.installment_status(_inst("100", "100", date(2026, 5, 1)), today) == "paid"
    assert fm.installment_status(_inst("100", "40", date(2026, 5, 1)), today) == "overdue"
    assert fm.installment_status(_inst("100", "40", date(2026, 7, 1)), today) == "partial"
    assert fm.installment_status(_inst("100", "0", date(2026, 7, 1)), today) == "pending"


def test_student_fee_status_and_overdue_amount():
    today = date(2026, 6, 1)
    sf = StudentFee(net_fee=D("200"))
    sf.installments = [_inst("100", "100", date(2026, 5, 1)), _inst("100", "0", date(2026, 5, 1))]
    # one paid, one overdue -> overdue wins over partial
    assert fm.student_fee_status(sf, sf.installments, today) == "overdue"
    assert fm.overdue_amount(sf.installments, today) == D("100.00")
    # fully paid
    sf.installments[1].paid_amount = D("100")
    assert fm.student_fee_status(sf, sf.installments, today) == "paid"


def test_default_due_dates_start_from_april():
    dates = fm.default_due_dates(4, date(2026, 4, 1))
    assert dates[0] == date(2026, 4, 1)
    assert len(dates) == 4
