"""FE-1 — the fee desk: structures per class, coverage, bulk apply, the actor log.

The founder's confirmed answers drive most of these:
  Q-1 -> `D-116` a structure prices a CLASS, not a section
  Q-4 -> `D-128` receipt numbers are generated per org + year
  and `D-118`, the one he confirmed first: editing a structure must NEVER
  reprice a student who is already on it.
"""

import uuid


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _register_admin(client, cleanup, *, org="Fee Desk Org", email=None):
    email = email or f"admin-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post("/api/v1/auth/register-org",
                    json={"org_name": org, "name": "Director", "email": email,
                          "password": "supersecret1", "timezone": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    body = r.json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return body


def _school(client, cleanup):
    """A year, class 6 with sections A and B, class 7, and one student in each 6.

    Two sections is the whole point: per-class pricing means ONE structure has
    to reach both of them, and a test with a single section could not tell the
    difference between that and the old per-section behaviour.
    """
    admin = _register_admin(client, cleanup)
    h = _h(admin["access_token"])
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    six_a = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    six_b = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "B"}).json()
    seven = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "7",
                              "section": "A"}).json()
    a1 = client.post("/api/v1/students", headers=h,
                     json={"admission_no": "A1", "full_name": "Aarav",
                           "class_id": six_a["id"]}).json()
    b1 = client.post("/api/v1/students", headers=h,
                     json={"admission_no": "B1", "full_name": "Diya",
                           "class_id": six_b["id"]}).json()
    return admin, h, year, {"6A": six_a, "6B": six_b, "7": seven}, {"a": a1, "b": b1}


def _schedule(total: int, parts: int = 2) -> list[dict]:
    each = total // parts
    rows = []
    for i in range(parts):
        amount = total - each * (parts - 1) if i == parts - 1 else each
        rows.append({"installment_number": i + 1, "label": f"Part {i + 1}",
                     "amount": str(amount), "due_date": f"2026-0{4 + i}-10"})
    return rows


def _price(client, h, year_id, class_name="6", total=60000, parts=2, category_id=None):
    body = {"class_name": class_name, "academic_year_id": year_id,
            "total_amount": str(total), "num_installments": parts,
            "installments": _schedule(total, parts)}
    if category_id:
        body["category_id"] = category_id
    r = client.post("/api/v1/fees/structures", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── D-116: a structure prices the class ──────────────────────────────────────
def test_structure_rejects_a_sectioned_class_name(client, cleanup):
    """The old screen let an admin type "6-B" into a free-text box, and the
    structure then had to accidentally match a label built elsewhere. Naming a
    section is now a validation error with the fix in the message."""
    _admin, h, year, _classes, _students = _school(client, cleanup)
    r = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "6-B", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 2,
        "installments": _schedule(60000, 2)})
    assert r.status_code == 422, r.text
    assert "6-B" in r.text or "whole class" in r.text


def test_structure_rejects_a_class_that_does_not_exist(client, cleanup):
    _admin, h, year, _classes, _students = _school(client, cleanup)
    r = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "99", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 2,
        "installments": _schedule(60000, 2)})
    assert r.status_code == 422, r.text


def test_schedule_must_add_up_to_the_total(client, cleanup):
    _admin, h, year, _classes, _students = _school(client, cleanup)
    r = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "6", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 2,
        "installments": [
            {"installment_number": 1, "amount": "10000"},
            {"installment_number": 2, "amount": "10000"}]})
    assert r.status_code == 422, r.text
    assert "still to allocate" in r.text


# ── D-117: the coverage grid ─────────────────────────────────────────────────
def test_coverage_lists_every_class_priced_or_not(client, cleanup):
    """The founder's completeness check. The class with no structure is the row
    that matters, and a list of existing structures is exactly the shape that
    cannot show it."""
    _admin, h, year, _classes, _students = _school(client, cleanup)
    _price(client, h, year["id"], class_name="6")

    cov = client.get("/api/v1/fees/structures/coverage",
                     headers=h, params={"year_id": year["id"]})
    assert cov.status_code == 200, cov.text
    body = cov.json()
    assert body["classes_total"] == 2      # "6" and "7"
    assert body["classes_priced"] == 1
    rows = {r["class_name"]: r for r in body["rows"]}
    assert set(rows) == {"6", "7"}
    # Class 6 is priced and names both sections it covers.
    assert rows["6"]["structure_id"] is not None
    assert rows["6"]["sections"] == ["A", "B"]
    assert rows["6"]["students_total"] == 2
    # Class 7 is NOT priced — a word, never a zero amount.
    assert rows["7"]["structure_id"] is None
    assert rows["7"]["total_amount"] is None


# ── D-120: one action sets a class up ────────────────────────────────────────
def test_apply_sets_up_every_section_of_the_class(client, cleanup):
    """One structure for "6" must reach the child in 6-A AND the child in 6-B."""
    _admin, h, year, _classes, students = _school(client, cleanup)
    fs = _price(client, h, year["id"], class_name="6", total=60000, parts=2)

    r = client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2, r.text

    listed = client.get("/api/v1/fees/student-fees", headers=h,
                        params={"year_id": year["id"]}).json()
    by_student = {row["student_id"]: row for row in listed}
    assert students["a"]["id"] in by_student
    assert students["b"]["id"] in by_student
    assert by_student[students["a"]["id"]]["net_fee"] == "60000.00"


def test_apply_twice_skips_and_says_so(client, cleanup):
    """A school told "22 set up" after selecting 24 must be able to see why."""
    _admin, h, year, _classes, _students = _school(client, cleanup)
    fs = _price(client, h, year["id"])
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})

    again = client.post(f"/api/v1/fees/structures/{fs['id']}/apply",
                        headers=h, json={}).json()
    assert again["created"] == 0
    assert again["skipped_existing"] == 2
    assert "already had fee record" in again["message"]


# ── D-118: editing never reprices anybody already set up ─────────────────────
def test_editing_a_structure_does_not_reprice_existing_students(client, cleanup):
    """The founder confirmed this one first, and it is the one with money on it:
    a family part-way through paying ₹60,000 must not silently owe ₹80,000
    because somebody corrected the price on the structure screen."""
    _admin, h, year, _classes, _students = _school(client, cleanup)
    fs = _price(client, h, year["id"], total=60000, parts=2)
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})

    before = client.get("/api/v1/fees/student-fees", headers=h,
                        params={"year_id": year["id"]}).json()
    assert all(row["net_fee"] == "60000.00" for row in before)

    edited = client.put(f"/api/v1/fees/structures/{fs['id']}", headers=h, json={
        "total_amount": "80000", "num_installments": 2,
        "installments": _schedule(80000, 2)})
    assert edited.status_code == 200, edited.text
    assert edited.json()["total_amount"] == "80000.00"
    # A NEW row: the edited structure is not the one the students are on.
    assert edited.json()["id"] != fs["id"]

    after = client.get("/api/v1/fees/student-fees", headers=h,
                       params={"year_id": year["id"]}).json()
    assert all(row["net_fee"] == "60000.00" for row in after), (
        "editing a structure must never reprice a student already on it")

    # And only one active structure survives for the key.
    active = client.get("/api/v1/fees/structures", headers=h,
                        params={"year_id": year["id"]}).json()
    assert len([s for s in active if s["class_name"] == "6"]) == 1


def test_a_student_added_after_the_edit_gets_the_new_price(client, cleanup):
    """The other half of `D-118`: the edit is not a no-op, it is the price for
    everybody who comes next."""
    _admin, h, year, classes, _students = _school(client, cleanup)
    fs = _price(client, h, year["id"], total=60000, parts=2)
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})

    new_fs = client.put(f"/api/v1/fees/structures/{fs['id']}", headers=h, json={
        "total_amount": "80000", "num_installments": 2,
        "installments": _schedule(80000, 2)}).json()

    late = client.post("/api/v1/students", headers=h,
                       json={"admission_no": "C1", "full_name": "Kabir",
                             "class_id": classes["6A"]["id"]}).json()
    client.post(f"/api/v1/fees/structures/{new_fs['id']}/apply", headers=h, json={})

    rows = client.get("/api/v1/fees/student-fees", headers=h,
                      params={"year_id": year["id"]}).json()
    by_student = {r["student_id"]: r for r in rows}
    assert by_student[late["id"]]["net_fee"] == "80000.00"


# ── D-124: the actor log ─────────────────────────────────────────────────────
def test_every_structure_action_leaves_a_named_event(client, cleanup):
    """The three-admins case: admin2 must be able to see WHO changed the price.

    This is why `actor_name` is written into the row rather than joined at read
    time — the log has to still name somebody after an account is deactivated.
    """
    _admin, h, year, _classes, _students = _school(client, cleanup)
    fs = _price(client, h, year["id"], total=60000, parts=2)
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})
    client.put(f"/api/v1/fees/structures/{fs['id']}", headers=h, json={
        "total_amount": "80000", "num_installments": 2,
        "installments": _schedule(80000, 2)})

    feed = client.get("/api/v1/fees/activity", headers=h,
                      params={"year_id": year["id"]})
    assert feed.status_code == 200, feed.text
    events = feed.json()
    kinds = [e["kind"] for e in events]
    assert "structure_created" in kinds
    assert "fee_bulk_applied" in kinds
    assert "structure_replaced" in kinds
    assert all(e["actor_name"] == "Director" for e in events), (
        "an action log that cannot name the actor cannot be acted on")
    replaced = next(e for e in events if e["kind"] == "structure_replaced")
    assert "60,000" in replaced["summary"] and "80,000" in replaced["summary"]
