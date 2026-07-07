"""P0-D: fee port end-to-end (SPRD §5.6) — structures, enrol, pay/undo/discount,
append-only ledger, role gates (admin-only in v2), org isolation."""

import uuid


def _register_admin(client, cleanup, *, org="Fee Org", email=None):
    email = email or f"admin-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post("/api/v1/auth/register-org",
                    json={"org_name": org, "name": "Director", "email": email,
                          "password": "supersecret1", "timezone": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    body = r.json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return body


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _setup(client, cleanup):
    """Director + a year + a class-6 student, ready to enrol into fees."""
    admin = _register_admin(client, cleanup)
    h = _h(admin["access_token"])
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "B"}).json()
    student = client.post("/api/v1/students", headers=h,
                          json={"admission_no": "F1", "full_name": "Meera", "class_id": klass["id"]}).json()
    return admin, h, year, klass, student


def _structure(client, h, year_id):
    body = {
        "class_name": "6-B", "academic_year_id": year_id, "total_amount": "30000",
        "num_installments": 3,
        "installments": [
            {"installment_number": 1, "amount": "10000", "due_date": "2026-04-15"},
            {"installment_number": 2, "amount": "10000", "due_date": "2026-08-15"},
            {"installment_number": 3, "amount": "10000", "due_date": "2026-12-15"},
        ],
    }
    r = client.post("/api/v1/fees/structures", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_full_fee_lifecycle(client, cleanup):
    _admin, h, year, _klass, student = _setup(client, cleanup)

    # structure with a bad sum -> 422
    bad = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "6-B", "academic_year_id": year["id"], "total_amount": "30000",
        "num_installments": 1, "installments": [{"installment_number": 1, "amount": "25000"}]})
    assert bad.status_code == 422

    fs = _structure(client, h, year["id"])
    assert len(fs["templates"]) == 3

    # enrol from the structure -> 3 installments scaled to net 30000
    detail = client.post("/api/v1/fees/student-fees", headers=h, json={
        "student_id": student["id"], "academic_year_id": year["id"],
        "total_fee": "30000", "fee_structure_id": fs["id"]}).json()
    assert detail["net_fee"] == "30000.00"
    assert detail["balance"] == "30000.00"
    assert len(detail["installments"]) == 3
    inst1 = detail["installments"][0]["id"]

    # duplicate enrolment same year -> 409
    dup = client.post("/api/v1/fees/student-fees", headers=h, json={
        "student_id": student["id"], "academic_year_id": year["id"], "total_fee": "30000"})
    assert dup.status_code == 409

    # pay installment 1 fully -> partial, balance 20000
    paid = client.post(f"/api/v1/fees/installments/{inst1}/pay", headers=h,
                       json={"amount": "10000", "mode": "cash"}).json()
    assert paid["paid"] == "10000.00" and paid["balance"] == "20000.00"
    assert paid["status"] == "partial"

    # overpay -> 422
    over = client.post(f"/api/v1/fees/installments/{inst1}/pay", headers=h, json={"amount": "5000"})
    assert over.status_code == 422  # installment already full

    # undo the payment -> back to 0 paid, ledger keeps BOTH rows (append-only)
    undone = client.post(f"/api/v1/fees/installments/{inst1}/undo", headers=h).json()
    assert undone["paid"] == "0.00"
    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions", headers=h).json()
    assert {t["type"] for t in txns} == {"payment", "undo"}

    # discount 5000 -> net 25000, unpaid installments rescale to sum 25000
    disc = client.patch(f"/api/v1/fees/student-fees/{detail['id']}", headers=h,
                        json={"discount": "5000"}).json()
    assert disc["net_fee"] == "25000.00"
    assert sum(float(i["amount"]) for i in disc["installments"]) == 25000.0

    # dashboard summary reflects the net + nothing collected
    summ = client.get(f"/api/v1/fees/summary?year_id={year['id']}", headers=h).json()
    assert summ["total_fee"] == "25000.00" and summ["collected_fee"] == "0.00"


def test_custom_schedule_must_sum_to_net(client, cleanup):
    _admin, h, year, _klass, student = _setup(client, cleanup)
    r = client.post("/api/v1/fees/student-fees", headers=h, json={
        "student_id": student["id"], "academic_year_id": year["id"], "total_fee": "10000",
        "use_custom_schedule": True,
        "installments": [{"installment_number": 1, "amount": "9000"}]})  # 9000 != 10000
    assert r.status_code == 422


def test_only_admins_see_fees(client, cleanup):
    admin, h, year, _klass, _student = _setup(client, cleanup)

    def _invite(role, phone):
        inv = client.post("/api/v1/org/members/invite", headers=h,
                          json={"name": role.title(), "phone": phone, "role": role})
        cleanup["users"].append(uuid.UUID(inv.json()["user_id"]))
        tok = inv.json()["invite_url"].rsplit("/join/", 1)[1]
        return _h(client.post("/api/v1/auth/verify", json={"token": tok}).json()["access_token"])

    teacher_h = _invite("teacher", "+919800000011")
    admin2_h = _invite("admin", "+919800000022")

    # v2: teachers are blocked from fees entirely; any admin can read them
    assert client.get("/api/v1/fees/summary", headers=teacher_h).status_code == 403
    assert client.get("/api/v1/fees/summary", headers=admin2_h).status_code == 200


def test_fees_are_org_isolated(client, cleanup):
    _a, ha, year_a, _k, _s = _setup(client, cleanup)
    fs = _structure(client, ha, year_a["id"])
    assert fs["id"]
    # a second org sees none of org A's structures
    b = _register_admin(client, cleanup, org="Fee Org B")
    hb = _h(b["access_token"])
    assert client.get("/api/v1/fees/structures", headers=hb).json() == []
    assert client.get(f"/api/v1/fees/structures/{fs['id']}", headers=hb).status_code == 404
