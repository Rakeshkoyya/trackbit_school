"""FE-1k — the transfer (`D-127`, founder Q-2).

*"prompt to transfer then the amount will be closed and remaining balance will
be detected from total and the student status will be closed and we can open the
stundent and undo the transfer as well"*

The two things worth guarding: a closed record must stop appearing as money the
school is owed, and the undo has to put back exactly what was there.
"""

import uuid


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Transfer Org", "name": "Director",
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
    client.post("/api/v1/students", headers=h,
                json={"admission_no": "T1", "full_name": "Aarav",
                      "class_id": klass["id"]})
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
    return h, year, detail


def test_closing_writes_off_the_unpaid_balance(client, cleanup):
    """Paid ₹30,000 of ₹60,000, then transferred: the school is owed nothing,
    and the ₹30,000 it did collect still stands as billed."""
    h, _year, detail = _setup(client, cleanup)
    client.post(
        f"/api/v1/fees/installments/{detail['installments'][0]['id']}/mark-paid",
        headers=h)

    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h,
                    json={"reason": "Moved to Pune"})
    assert r.status_code == 200, r.text
    closed = r.json()
    assert closed["status"] == "closed"
    assert closed["net_fee"] == "30000.00"
    assert closed["balance"] == "0.00"
    # The unpaid instalment is VOIDED, not deleted — it is still on the page.
    assert len(closed["installments"]) == 2
    assert any(i["is_voided"] for i in closed["installments"])


def test_a_closed_record_leaves_the_collection_board_alone(client, cleanup):
    """A transferred child must stop being chased. The voided instalment had a
    due date in the past, so if it were still counted it would show as overdue
    money for ever."""
    h, year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h,
                json={"reason": "Transferred"})

    board = client.get("/api/v1/fees/collection", headers=h,
                       params={"year_id": year["id"]}).json()
    assert board["overdue"] == 0, board
    assert board["year"]["billed"] == 0, board


def test_a_closed_record_refuses_new_payments(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h, json={})
    r = client.post(
        f"/api/v1/fees/installments/{detail['installments'][0]['id']}/pay",
        headers=h, json={"amount": "100", "mode": "cash"})
    assert r.status_code == 422, r.text
    assert "closed" in r.text


def test_reopening_restores_exactly_what_was_there(client, cleanup):
    """The undo the founder asked for, in the same breath as the transfer."""
    h, _year, detail = _setup(client, cleanup)
    before = client.get(f"/api/v1/fees/student-fees/{detail['id']}",
                        headers=h).json()

    client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h,
                json={"reason": "Left"})
    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/reopen", headers=h)
    assert r.status_code == 200, r.text
    after = r.json()

    assert after["status"] != "closed"
    assert after["net_fee"] == before["net_fee"]
    assert after["balance"] == before["balance"]
    assert not any(i["is_voided"] for i in after["installments"])
    assert (sorted(i["amount"] for i in after["installments"])
            == sorted(i["amount"] for i in before["installments"]))


def test_closing_twice_is_refused(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h, json={})
    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h,
                    json={})
    assert r.status_code == 422, r.text


def test_reopening_a_record_that_is_not_closed_is_refused(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    r = client.post(f"/api/v1/fees/student-fees/{detail['id']}/reopen", headers=h)
    assert r.status_code == 422, r.text


def test_both_halves_of_the_transfer_are_logged(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/close", headers=h,
                json={"reason": "Moved to Pune"})
    client.post(f"/api/v1/fees/student-fees/{detail['id']}/reopen", headers=h)

    events = client.get(f"/api/v1/fees/student-fees/{detail['id']}/activity",
                        headers=h).json()
    kinds = [e["kind"] for e in events]
    assert "record_closed" in kinds and "record_reopened" in kinds
    closed = next(e for e in events if e["kind"] == "record_closed")
    assert "Moved to Pune" in closed["summary"]
    assert closed["actor_name"] == "Director"
