"""FE-2 — locking ONE student's fee, with the discount agreed at the counter.

The gap this closes: every door into "set this child up" billed the class's full
price in the class's number of instalments. The real conversation is *"the
structure says ₹60,000; we have agreed ₹52,000 in six payments"* — and there was
nowhere to say it before the record existed.

What each test is defending:

  * the setup screen opens on **what she would be billed if nobody did
    anything** — the class's structure, priced AND dated, so "use the default"
    is something the office can see rather than a promise;
  * `structure_for_student` agrees with the bulk `apply()` about which structure
    prices a child. A staff ward quoted one fee here and billed another there is
    the failure this pair exists to prevent;
  * the preview is the write. The rows the office reads before confirming are
    the rows that get stored, to the paisa — because a browser dividing the
    money itself would drift on the first rounding remainder;
  * a discount larger than the fee is refused, and an unpriced class is a
    sentence rather than a ₹0 form somebody could lock in;
  * locking writes the actor log (`D-124`) — "why is this child paying ₹8,000
    less" is asked months later by a different person.
"""

import uuid


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _schedule(total: int, parts: int) -> list[dict]:
    each = total // parts
    return [
        {"installment_number": i + 1, "label": f"Term {i + 1}",
         "amount": str(total - each * (parts - 1) if i == parts - 1 else each),
         "due_date": f"2026-0{4 + i}-10"}
        for i in range(parts)
    ]


def _school(client, cleanup):
    """Class 5 priced at ₹60,000 in 4 terms, with two children in it — one of
    them in a category that has its own cheaper price."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Fee Setup Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = _h(reg["access_token"])
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "5",
                              "section": "A"}).json()
    cat = client.post("/api/v1/students/categories", headers=h,
                      json={"name": "Staff ward"}).json()
    ordinary = client.post("/api/v1/students", headers=h,
                           json={"admission_no": "S1", "full_name": "Aarav Rao",
                                 "class_id": klass["id"]}).json()
    ward = client.post("/api/v1/students", headers=h,
                       json={"admission_no": "S2", "full_name": "Meera Nair",
                             "class_id": klass["id"], "category_id": cat["id"]}).json()
    fs = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "5", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 4,
        "installments": _schedule(60000, 4)}).json()
    return {"h": h, "year": year, "class": klass, "category": cat,
            "student": ordinary, "ward": ward, "structure": fs}


def _setup(client, ctx, student=None):
    s = student or ctx["student"]
    return client.get(
        f"/api/v1/fees/setup/{s['id']}?year_id={ctx['year']['id']}", headers=ctx["h"])


# ── the screen opens on the default mapping ──────────────────────────────────
def test_setup_shows_the_class_structure_priced_and_dated(client, cleanup):
    ctx = _school(client, cleanup)
    r = _setup(client, ctx)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_locked"] is False
    assert body["class_label"] == "5-A"
    assert body["structure"]["total_amount"] == "60000.00"
    assert body["structure"]["num_installments"] == 4
    # Priced AND dated — the school's own terms, not four anonymous quarters.
    assert [p["label"] for p in body["default_plan"]] == [
        "Term 1", "Term 2", "Term 3", "Term 4"]
    assert sum(float(p["amount"]) for p in body["default_plan"]) == 60000
    assert body["default_plan"][0]["due_date"] == "2026-04-10"


def test_an_unpriced_class_is_a_sentence_not_a_zero(client, cleanup):
    ctx = _school(client, cleanup)
    six = client.post("/api/v1/academics/classes", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "name": "6", "section": "A"}).json()
    orphan = client.post("/api/v1/students", headers=ctx["h"], json={
        "admission_no": "S9", "full_name": "Unpriced Child",
        "class_id": six["id"]}).json()
    body = _setup(client, ctx, orphan).json()
    assert body["structure"] is None
    assert body["default_plan"] == []

    preview = client.post("/api/v1/fees/setup/preview", headers=ctx["h"], json={
        "student_id": orphan["id"], "academic_year_id": ctx["year"]["id"]}).json()
    assert preview["warning"] is not None
    assert "no fee structure" in preview["warning"]


def test_the_setup_screen_and_the_bulk_apply_pick_the_same_structure(client, cleanup):
    """`structure_for_student` is the mirror of `apply()`'s category rule. If the
    two ever disagree, a staff ward is quoted one fee and billed another."""
    ctx = _school(client, cleanup)
    cheap = client.post("/api/v1/fees/structures", headers=ctx["h"], json={
        "class_name": "5", "academic_year_id": ctx["year"]["id"],
        "category_id": ctx["category"]["id"],
        "total_amount": "20000", "num_installments": 2,
        "installments": _schedule(20000, 2)}).json()

    # The per-student screen prefers her category's price…
    assert _setup(client, ctx, ctx["ward"]).json()["structure"]["id"] == cheap["id"]
    # …and her classmate still gets the general one.
    assert _setup(client, ctx).json()["structure"]["id"] == ctx["structure"]["id"]

    # …which is exactly what the bulk apply does with the general structure: it
    # skips the ward, because her category is spoken for.
    applied = client.post(
        f"/api/v1/fees/structures/{ctx['structure']['id']}/apply",
        headers=ctx["h"], json={}).json()
    assert applied["created"] == 1
    fees = client.get(
        f"/api/v1/fees/student-fees?year_id={ctx['year']['id']}",
        headers=ctx["h"]).json()
    assert [f["student_id"] for f in fees] == [ctx["student"]["id"]]


# ── the preview IS the write ─────────────────────────────────────────────────
def test_a_custom_discount_and_instalment_count_preview_then_lock(client, cleanup):
    """The founder's case: the structure says ₹60,000, the school agreed
    ₹52,000 in six payments."""
    ctx = _school(client, cleanup)
    payload = {
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "discount": "8000", "num_installments": 6,
    }
    preview = client.post("/api/v1/fees/setup/preview",
                          headers=ctx["h"], json=payload)
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["total_fee"] == "60000.00"
    assert p["net_fee"] == "52000.00"
    assert p["warning"] is None
    assert len(p["installments"]) == 6
    assert sum(float(i["amount"]) for i in p["installments"]) == 52000

    locked = client.post("/api/v1/fees/student-fees", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "fee_structure_id": ctx["structure"]["id"],
        "total_fee": "60000", "discount": "8000", "num_installments": 6})
    assert locked.status_code == 200, locked.text
    detail = locked.json()
    assert detail["net_fee"] == "52000.00"
    assert detail["discount"] == "8000.00"
    # What she was shown is what was stored — row for row, to the paisa.
    assert [i["amount"] for i in detail["installments"]] == [
        i["amount"] for i in p["installments"]]
    assert [i["due_date"] for i in detail["installments"]] == [
        i["due_date"] for i in p["installments"]]


def test_the_default_mapping_keeps_the_schools_own_terms(client, cleanup):
    """Locking with no overrides must be byte-identical to the bulk apply — the
    same labels, the same dates, the same amounts."""
    ctx = _school(client, cleanup)
    detail = client.post("/api/v1/fees/student-fees", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "fee_structure_id": ctx["structure"]["id"],
        "total_fee": "60000"}).json()
    assert [i["label"] for i in detail["installments"]] == [
        "Term 1", "Term 2", "Term 3", "Term 4"]
    assert detail["installments"][0]["due_date"] == "2026-04-10"
    assert detail["net_fee"] == "60000.00"


def test_a_discount_larger_than_the_fee_is_refused(client, cleanup):
    ctx = _school(client, cleanup)
    warned = client.post("/api/v1/fees/setup/preview", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"], "discount": "70000"}).json()
    assert warned["warning"] is not None

    r = client.post("/api/v1/fees/student-fees", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "fee_structure_id": ctx["structure"]["id"],
        "total_fee": "60000", "discount": "70000"})
    assert r.status_code == 422, r.text
    assert "more than the fee" in r.json()["error"]["message"]


def test_previous_dues_ride_into_the_payable(client, cleanup):
    ctx = _school(client, cleanup)
    p = client.post("/api/v1/fees/setup/preview", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "discount": "5000", "opening_dues": "3000"}).json()
    assert p["net_fee"] == "55000.00"
    # Arrears add to what the family owes but never to the instalments — status
    # is still driven by the schedule alone.
    assert p["total_payable"] == "58000.00"
    assert sum(float(i["amount"]) for i in p["installments"]) == 55000


# ── the trail ────────────────────────────────────────────────────────────────
def test_locking_a_discount_is_recorded_in_the_actor_log(client, cleanup):
    ctx = _school(client, cleanup)
    detail = client.post("/api/v1/fees/student-fees", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "fee_structure_id": ctx["structure"]["id"],
        "total_fee": "60000", "discount": "8000", "num_installments": 6}).json()
    events = client.get(
        f"/api/v1/fees/student-fees/{detail['id']}/activity",
        headers=ctx["h"]).json()
    assert any(e["kind"] == "fee_created" for e in events), events
    said = " ".join(e["summary"] for e in events)
    assert "8,000" in said and "52,000" in said


def test_setup_says_when_she_is_already_locked(client, cleanup):
    ctx = _school(client, cleanup)
    locked = client.post("/api/v1/fees/student-fees", headers=ctx["h"], json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"],
        "fee_structure_id": ctx["structure"]["id"],
        "total_fee": "60000"}).json()
    body = _setup(client, ctx).json()
    assert body["already_locked"] is True
    assert body["student_fee_id"] == locked["id"]


def test_a_teacher_cannot_read_or_lock_a_fee(client, cleanup):
    """The first hard rule: teachers never see fees, on every surface."""
    ctx = _school(client, cleanup)
    inv = client.post("/api/v1/org/members/invite", headers=ctx["h"], json={
        "name": "Teach", "phone": "+9198" + str(uuid.uuid4().int)[:8],
        "role": "teacher"}).json()
    cleanup["users"].append(uuid.UUID(inv["user_id"]))
    token = inv["invite_url"].rsplit("/join/", 1)[1]
    th = _h(client.post("/api/v1/auth/verify",
                        json={"token": token}).json()["access_token"])
    assert client.get(
        f"/api/v1/fees/setup/{ctx['student']['id']}?year_id={ctx['year']['id']}",
        headers=th).status_code == 403
    assert client.post("/api/v1/fees/setup/preview", headers=th, json={
        "student_id": ctx["student"]["id"],
        "academic_year_id": ctx["year"]["id"]}).status_code == 403
