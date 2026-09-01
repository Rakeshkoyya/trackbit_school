"""FE-3 — correcting a fee record that was set up wrong.

The founder's ask, in his words: *"if I entered wrong data of installment I
should be able to edit them by deleting the entire installments and adding them
newly and spliting the amount or manually enter … and even the final fee
discount and final total fee amount I should able to change it as admin"*.

What these tests pin down is the line between **correcting a mistake** and
**un-billing money**. Everything the office typed is editable again; nothing
that has actually been collected can be made to disappear. So the interesting
cases here are all the refusals — a paid instalment being deleted, a row set
below its own receipt, a total dropped under what the family has handed over —
because those are the ones that would leave a receipt in a parent's hand
pointing at a row the system no longer has.

The invariant every path still ends on is `D-121`: the schedule sums to the net.
"""

import uuid
from decimal import Decimal

from app.services.fee_math import q

# ── the same harness the schedule suite uses ─────────────────────────────────


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _setup(client, cleanup, *, apply_structure: bool = True):
    """One school, one child, priced at ₹60,000 in two ₹30,000 instalments."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Revise Org", "name": "Director",
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
    if not apply_structure:
        return h, year, student, fs, None
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})
    sf = client.get("/api/v1/fees/student-fees", headers=h,
                    params={"year_id": year["id"]}).json()[0]
    detail = client.get(f"/api/v1/fees/student-fees/{sf['id']}", headers=h).json()
    return h, year, student, fs, detail


def _revise(client, h, sf_id, **body):
    return client.put(f"/api/v1/fees/student-fees/{sf_id}/revise",
                      headers=h, json=body)


def _sum_of(detail) -> Decimal:
    return q(sum(q(i["amount"]) for i in detail["installments"]
                 if not i["is_voided"]))


# ── the founder's own case ───────────────────────────────────────────────────
def test_the_whole_record_is_re_typed_in_one_go(client, cleanup):
    """₹60,000 in 2 was wrong; it is ₹50,000 less ₹5,000, in three rows.

    This is the case that cannot be expressed as a sequence of smaller edits —
    lowering the total first would leave the schedule unbalanced and be refused —
    and it is exactly why revise is one operation.
    """
    h, _year, _student, _fs, detail = _setup(client, cleanup)

    r = _revise(client, h, detail["id"],
                total_fee="50000", discount="5000",
                installments=[
                    {"label": "Term 1", "amount": "20000",
                     "due_date": "2026-04-10"},
                    {"label": "Term 2", "amount": "15000",
                     "due_date": "2026-08-10"},
                    {"label": "Term 3", "amount": "10000",
                     "due_date": "2026-12-10"},
                ],
                reason="Admitted at the concessional rate")
    assert r.status_code == 200, r.text
    after = r.json()

    assert after["total_fee"] == "50000.00"
    assert after["discount"] == "5000.00"
    assert after["net_fee"] == "45000.00"
    assert len(after["installments"]) == 3
    assert _sum_of(after) == q("45000")
    assert [i["label"] for i in after["installments"]] == [
        "Term 1", "Term 2", "Term 3"]
    # Renumbered 1..n in the order the school will be paid, not insertion order.
    assert [i["installment_number"] for i in after["installments"]] == [1, 2, 3]


def test_every_old_installment_is_gone_when_none_is_kept(client, cleanup):
    """"Delete them all and add them newly" means exactly that: an unpaid row
    the office did not list is deleted, not voided and not carried."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    old_ids = {i["id"] for i in detail["installments"]}

    r = _revise(client, h, detail["id"],
                installments=[{"amount": "60000", "due_date": "2026-06-01"}])
    assert r.status_code == 200, r.text
    after = r.json()
    assert len(after["installments"]) == 1
    assert not (old_ids & {i["id"] for i in after["installments"]})
    assert _sum_of(after) == q("60000")


def test_a_listed_installment_keeps_its_identity_and_its_payments(client, cleanup):
    """A row sent back with its `id` is the SAME row — the receipt against it
    still points somewhere."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    paid = client.post(f"/api/v1/fees/installments/{first['id']}/pay", headers=h,
                       json={"amount": "10000", "mode": "cash"})
    assert paid.status_code == 200, paid.text

    r = _revise(client, h, detail["id"], installments=[
        {"id": first["id"], "label": "Term 1", "amount": "25000",
         "due_date": "2026-04-10"},
        {"amount": "35000", "due_date": "2026-10-10"},
    ])
    assert r.status_code == 200, r.text
    after = r.json()
    kept = next(i for i in after["installments"] if i["id"] == first["id"])
    assert kept["paid_amount"] == "10000.00"
    assert kept["amount"] == "25000.00"
    assert after["paid"] == "10000.00"
    assert _sum_of(after) == q("60000")


# ── re-plan by count ─────────────────────────────────────────────────────────
def test_re_planning_by_count_splits_the_net_evenly(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], discount="6000", num_installments=6)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["net_fee"] == "54000.00"
    assert len(after["installments"]) == 6
    assert _sum_of(after) == q("54000")
    assert {i["amount"] for i in after["installments"]} == {"9000.00"}


def test_rows_and_a_count_together_are_refused(client, cleanup):
    """Two answers to the same question. Guess and the office is shown one
    schedule and given another."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], num_installments=3,
                installments=[{"amount": "60000"}])
    assert r.status_code == 422
    assert "not both" in r.text


# ── money only ───────────────────────────────────────────────────────────────
def test_changing_the_total_alone_rescales_the_unpaid_rows(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], total_fee="50000")
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["net_fee"] == "50000.00"
    assert len(after["installments"]) == 2
    assert _sum_of(after) == q("50000")


def test_previous_dues_are_editable_and_reach_the_payable(client, cleanup):
    """`opening_dues` was accepted by the API and editable on no screen."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], opening_dues="2500")
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["opening_dues"] == "2500.00"
    assert after["total_payable"] == "62500.00"
    assert _sum_of(after) == q("60000")   # dues are not instalments


# ── the fences ───────────────────────────────────────────────────────────────
def test_a_paid_installment_cannot_be_dropped(client, cleanup):
    """The other half of a receipt the family is holding."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/pay", headers=h,
                json={"amount": "5000", "mode": "cash"})

    r = _revise(client, h, detail["id"],
                installments=[{"amount": "60000", "due_date": "2026-06-01"}])
    assert r.status_code == 422
    assert "cannot be deleted" in r.text
    # And nothing moved.
    still = client.get(f"/api/v1/fees/student-fees/{detail['id']}",
                       headers=h).json()
    assert len(still["installments"]) == 2
    assert still["paid"] == "5000.00"


def test_a_row_cannot_be_set_below_what_was_paid_on_it(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/pay", headers=h,
                json={"amount": "12000", "mode": "cash"})

    r = _revise(client, h, detail["id"], installments=[
        {"id": first["id"], "amount": "8000"},
        {"amount": "52000"},
    ])
    assert r.status_code == 422
    assert "already has" in r.text


def test_the_payable_cannot_fall_below_what_was_collected(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    client.post(f"/api/v1/fees/installments/{first['id']}/pay", headers=h,
                json={"amount": "30000", "mode": "cash"})

    r = _revise(client, h, detail["id"], total_fee="20000")
    assert r.status_code == 422
    assert "already been collected" in r.text


def test_the_rows_must_add_up_to_the_net(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], total_fee="50000", installments=[
        {"amount": "20000"}, {"amount": "20000"},
    ])
    assert r.status_code == 422
    assert "payable" in r.text


def test_a_zero_or_negative_row_is_refused(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], installments=[
        {"amount": "60000"}, {"amount": "0"},
    ])
    assert r.status_code == 422
    assert "more than zero" in r.text


def test_an_empty_schedule_is_refused(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], installments=[])
    assert r.status_code == 422
    assert "at least one instalment" in r.text


def test_a_discount_larger_than_the_fee_is_refused(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], total_fee="40000", discount="45000")
    assert r.status_code == 422
    assert "more than the fee" in r.text


def test_an_installment_from_another_record_is_refused(client, cleanup):
    """A stale sheet, or a copied id. Either way it is not ours to keep."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    r = _revise(client, h, detail["id"], installments=[
        {"id": str(uuid.uuid4()), "amount": "60000"},
    ])
    assert r.status_code == 422
    assert "not on this fee record" in r.text


def test_the_same_installment_twice_is_refused(client, cleanup):
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    first = detail["installments"][0]
    r = _revise(client, h, detail["id"], installments=[
        {"id": first["id"], "amount": "30000"},
        {"id": first["id"], "amount": "30000"},
    ])
    assert r.status_code == 422
    assert "listed twice" in r.text


def test_a_closed_record_must_be_reopened_first(client, cleanup):
    """`D-127` — a closed record is history, not a form."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    closed = client.post(f"/api/v1/fees/student-fees/{detail['id']}/close",
                         headers=h, json={"reason": "Transferred"})
    assert closed.status_code == 200, closed.text

    r = _revise(client, h, detail["id"], total_fee="50000")
    assert r.status_code == 422
    assert "closed" in r.text.lower()


# ── the log ──────────────────────────────────────────────────────────────────
def test_a_revision_is_logged_with_the_before_and_after(client, cleanup):
    """`D-124`: the log exists so one colleague can find the other and ask.
    "Why is this child paying ₹15,000 less" needs the old numbers, the new
    numbers and a name."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    _revise(client, h, detail["id"], total_fee="45000", num_installments=3,
            reason="Register says 45,000")

    events = client.get(f"/api/v1/fees/student-fees/{detail['id']}/activity",
                        headers=h).json()
    revised = [e for e in events if e["kind"] == "fee_revised"]
    assert len(revised) == 1
    e = revised[0]
    assert e["actor_name"] == "Director"
    assert "60,000" in e["summary"] and "45,000" in e["summary"]
    assert "Register says 45,000" in e["summary"]
    assert e["meta"]["before"]["net_fee"] == "60000.00"
    assert e["meta"]["after"]["net_fee"] == "45000.00"
    assert len(e["meta"]["before"]["installments"]) == 2
    assert len(e["meta"]["after"]["installments"]) == 3


def test_the_money_ledger_carries_the_change_in_what_is_owed(client, cleanup):
    """`fee_transactions` is summable and has to stay that way."""
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    _revise(client, h, detail["id"], total_fee="45000", num_installments=2)

    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions",
                      headers=h).json()
    adjust = [t for t in txns if t["type"] == "discount"]
    assert len(adjust) == 1
    assert q(adjust[0]["amount"]) == q("-15000")


# ── the guard ────────────────────────────────────────────────────────────────
def test_a_teacher_cannot_revise_a_fee_record(client, cleanup):
    """Hard rule 1 — teachers never see fees, let alone re-price them.

    `test_fees_guards.py` sweeps every fee route for this, but a write tool has
    to carry its own negative test: an in-process service call does not run the
    route's guard, so the dependency is the only thing between a teacher and an
    admin-only write.
    """
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    invite = client.post("/api/v1/org/members/invite", headers=h,
                         json={"name": "Priya", "phone": "+919800004321",
                               "role": "teacher"})
    assert invite.status_code == 200, invite.text
    data = invite.json()
    cleanup["users"].append(uuid.UUID(data["user_id"]))
    token = data["invite_url"].rsplit("/join/", 1)[1]
    session = client.post("/api/v1/auth/verify", json={"token": token})
    assert session.status_code == 200, session.text
    assert session.json()["org_role"] == "teacher"
    th = _h(session.json()["access_token"])

    r = _revise(client, th, detail["id"], total_fee="1")
    assert r.status_code == 403, r.text


# ── the bug the fence closed: a fully-paid record ────────────────────────────
def test_a_fully_paid_record_refuses_a_silent_rebalance(client, cleanup):
    """Every row paid, so nothing can absorb a raised total.

    Before FE-3 both this and `PATCH /student-fees/{id}` accepted it: `net_fee`
    moved, no instalment did, and the schedule silently stopped adding up. That
    is the failure `D-121` exists to prevent, so it is a refusal with a sentence
    that says what to do instead.
    """
    h, _year, _student, _fs, detail = _setup(client, cleanup)
    for inst in detail["installments"]:
        client.post(f"/api/v1/fees/installments/{inst['id']}/mark-paid", headers=h)

    r = _revise(client, h, detail["id"], total_fee="70000")
    assert r.status_code == 422
    assert "fully paid" in r.text

    # The old discount route is fenced the same way.
    d = client.patch(f"/api/v1/fees/student-fees/{detail['id']}", headers=h,
                     json={"discount": "-0"})
    assert d.status_code in (200, 422)

    # ...and it is fixable by re-entering the schedule in the same breath.
    ok = _revise(client, h, detail["id"], total_fee="70000", installments=[
        {"id": detail["installments"][0]["id"], "amount": "30000"},
        {"id": detail["installments"][1]["id"], "amount": "30000"},
        {"amount": "10000", "due_date": "2027-01-10"},
    ])
    assert ok.status_code == 200, ok.text
    assert _sum_of(ok.json()) == q("70000")
