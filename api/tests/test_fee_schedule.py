"""FE-1c — the mutable instalment schedule (`D-121`).

One invariant is on trial in every test here: **the instalments always add up to
what is payable**. The founder asked for the ability to add instalments because
some parents want to pay in more pieces; the risk that comes with it is that
re-arranging a schedule quietly changes what a family owes, and nothing raises
at the time.

The unit tests below hammer `fee_math` directly (no DB), and the API tests check
the same promise through the routes a clerk actually uses.
"""

import random
import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError
from app.services.fee_math import assert_balanced, even_split, q, rebalance_unpaid


class _Inst:
    """A stand-in for the ORM row — `fee_math` only ever touches these fields."""

    def __init__(self, amount, paid=0, voided=False, iid=None):
        self.id = iid or uuid.uuid4()
        self.amount = q(amount)
        self.paid_amount = q(paid)
        self.is_voided = voided


# ── the invariant, in the pure layer ─────────────────────────────────────────
def test_assert_balanced_accepts_an_exact_schedule():
    assert_balanced(Decimal("60000"), [_Inst(30000), _Inst(30000)])


def test_assert_balanced_rejects_a_schedule_that_lost_a_rupee():
    with pytest.raises(ValidationError):
        assert_balanced(Decimal("60000"), [_Inst(30000), _Inst(29999)])


def test_voided_installments_are_outside_the_total():
    """`D-127`: a voided instalment is not owed and was not collected, so it
    must not appear in any total — while the row still exists to be un-voided."""
    assert_balanced(Decimal("30000"), [_Inst(30000), _Inst(30000, voided=True)])


@pytest.mark.parametrize("parts", [2, 3, 4, 5, 7, 12])
def test_even_split_always_re_sums(parts):
    """Rounding drift lands on the last part; the parts must re-sum to the
    paisa or every split silently changes the bill."""
    total = q("15500.55")
    pieces = even_split(total, parts)
    assert len(pieces) == parts
    assert q(sum(pieces)) == total


def test_rebalance_never_drops_below_what_was_paid():
    """Money that has landed cannot be un-billed by moving the schedule."""
    rows = [_Inst(30000, paid=25000), _Inst(30000, paid=0)]
    out = rebalance_unpaid(Decimal("40000"), rows)
    for inst in rows:
        if inst.id in out:
            assert out[inst.id] >= inst.paid_amount


def test_rebalance_refuses_to_owe_less_than_was_paid():
    rows = [_Inst(30000, paid=30000), _Inst(30000, paid=25000)]
    with pytest.raises(ValidationError):
        rebalance_unpaid(Decimal("10000"), rows)


def test_property_random_splits_always_balance():
    """The property that matters, over shapes nobody would think to write by
    hand: however a total is cut up, the pieces still add to the total."""
    rng = random.Random(20260811)
    for _ in range(300):
        total = q(rng.randint(1, 500_000) / 100)
        parts = rng.randint(1, 12)
        pieces = even_split(total, parts)
        assert q(sum(pieces)) == total, (total, parts, pieces)
        assert_balanced(total, [_Inst(p) for p in pieces])


# ── through the API ──────────────────────────────────────────────────────────
def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Sched Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = _h(reg["access_token"])
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    student = client.post("/api/v1/students", headers=h,
                          json={"admission_no": "S1", "full_name": "Aarav",
                                "class_id": klass["id"]}).json()
    fs = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "6", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 2,
        "installments": [
            {"installment_number": 1, "amount": "30000", "due_date": "2026-04-10"},
            {"installment_number": 2, "amount": "30000",
             "due_date": "2026-09-10"}]}).json()
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})
    sf = client.get("/api/v1/fees/student-fees", headers=h,
                    params={"year_id": year["id"]}).json()[0]
    detail = client.get(f"/api/v1/fees/student-fees/{sf['id']}", headers=h).json()
    return h, year, student, detail


def _sum_of(detail) -> Decimal:
    return q(sum(q(i["amount"]) for i in detail["installments"]))


def test_split_keeps_the_total_and_adds_parts(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    first = detail["installments"][0]

    r = client.post(f"/api/v1/fees/installments/{first['id']}/split",
                    headers=h, json={"parts": 3})
    assert r.status_code == 200, r.text
    after = r.json()
    assert len(after["installments"]) == 4          # 2 -> (3 + 1)
    assert _sum_of(after) == q("60000")
    assert after["net_fee"] == "60000.00"


def test_split_cannot_change_what_is_owed(client, cleanup):
    """Explicit amounts that do not sum to the original are refused."""
    h, _year, _student, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    r = client.post(f"/api/v1/fees/installments/{first['id']}/split",
                    headers=h, json={"amounts": ["10000", "10000"]})
    assert r.status_code == 422, r.text
    assert "cannot change what is owed" in r.text


def test_split_keeps_a_paid_amount_on_the_first_part(client, cleanup):
    """A family that has paid ₹25,000 of ₹30,000 keeps it where it was — not
    smeared across parts they have not reached."""
    h, _year, _student, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/pay",
                headers=h, json={"amount": "25000", "mode": "cash"})

    r = client.post(f"/api/v1/fees/installments/{first['id']}/split",
                    headers=h, json={"parts": 2})
    assert r.status_code == 200, r.text
    after = r.json()
    assert _sum_of(after) == q("60000")
    part_one = next(i for i in after["installments"] if i["id"] == first["id"])
    assert q(part_one["amount"]) >= q("25000")
    assert q(part_one["paid_amount"]) == q("25000")


def test_a_fully_paid_installment_cannot_be_split(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/mark-paid", headers=h)
    r = client.post(f"/api/v1/fees/installments/{first['id']}/split",
                    headers=h, json={"parts": 2})
    assert r.status_code == 422, r.text


def test_add_installment_is_funded_from_the_unpaid_ones(client, cleanup):
    """The whole point: the family owes exactly what it owed a moment ago."""
    h, _year, _student, detail = _setup(client, cleanup)

    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/installments",
                    headers=h, json={"amount": "10000", "due_date": "2026-12-10",
                                     "label": "Extra"})
    assert r.status_code == 200, r.text
    after = r.json()
    assert len(after["installments"]) == 3
    assert _sum_of(after) == q("60000"), "adding must not increase the bill"
    assert after["net_fee"] == "60000.00"


def test_add_installment_refuses_more_than_is_unpaid(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/installments",
                    headers=h, json={"amount": "99000"})
    assert r.status_code == 422, r.text
    assert "does not add to the bill" in r.text


def test_remove_gives_the_amount_back_to_the_others(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    second = detail["installments"][1]
    r = client.delete(f"/api/v1/fees/installments/{second['id']}", headers=h)
    assert r.status_code == 200, r.text
    after = r.json()
    assert len(after["installments"]) == 1
    assert _sum_of(after) == q("60000")


def test_a_paid_installment_cannot_be_removed(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/pay",
                headers=h, json={"amount": "5000", "mode": "cash"})
    r = client.delete(f"/api/v1/fees/installments/{first['id']}", headers=h)
    assert r.status_code == 422, r.text
    assert "payment against it" in r.text


def test_the_last_installment_cannot_be_removed(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    client.delete(f"/api/v1/fees/installments/{detail['installments'][1]['id']}",
                  headers=h)
    left = client.get(f"/api/v1/fees/student-fees/{detail['id']}", headers=h).json()
    r = client.delete(f"/api/v1/fees/installments/{left['installments'][0]['id']}",
                      headers=h)
    assert r.status_code == 422, r.text


def test_schedule_edits_are_all_logged_with_an_actor(client, cleanup):
    h, _year, _student, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/installments/{detail['installments'][0]['id']}/split",
                headers=h, json={"parts": 2})
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/installments",
                headers=h, json={"amount": "1000"})

    events = client.get(f"/api/v1/fees/student-fees/{detail['id']}/activity",
                        headers=h).json()
    kinds = [e["kind"] for e in events]
    assert "schedule_split" in kinds
    assert "schedule_added" in kinds
    assert all(e["actor_name"] == "Director" for e in events)
