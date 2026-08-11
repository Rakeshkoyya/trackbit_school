"""`D-129` — one student-category vocabulary, referenced by id.

The founder's ask was that categories stop being three unrelated things:
*"make all these category occurance bind to same thing so if I add in fee it
will reflect everywhere and if I added from student page it reflect here"*, and
that a block choose one from a dropdown instead of a hostellers-only checkbox.

The test that matters is `test_renaming_a_category_does_not_break_its_blocks`.
Before this change the roster query resolved a hosteller block by matching the
category NAME against the literal "hosteller", so renaming it in Settings
emptied every hostel roster in the school — silently, with nothing to see.
"""

import uuid


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _school(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Category Org", "name": "Director",
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
    cats = client.post("/api/v1/students/categories/seed-defaults", headers=h).json()
    hosteller = next(c["id"] for c in cats if c["name"] == "Hosteller")
    day = next(c["id"] for c in cats if c["name"] == "Day Scholar")
    for name, cat in [("Asha", hosteller), ("Bina", hosteller), ("Chetan", day)]:
        client.post("/api/v1/students", headers=h,
                    json={"admission_no": f"{name[0]}1", "full_name": name,
                          "class_id": klass["id"], "category_id": cat})
    return h, year, klass, hosteller, day


# ── the vocabulary is one thing, everywhere ──────────────────────────────────
def test_a_category_added_anywhere_is_visible_everywhere(client, cleanup):
    """One list, one endpoint. The fee structure editor, the student directory
    and the block dropdown all read this — there is no second store to drift."""
    h, _year, _klass, _hosteller, _day = _school(client, cleanup)
    made = client.post("/api/v1/students/categories", headers=h,
                       json={"name": "Transport"})
    assert made.status_code == 200, made.text

    names = {c["name"] for c in
             client.get("/api/v1/students/categories", headers=h).json()}
    assert {"Hosteller", "Day Scholar", "Transport"} <= names


def test_categories_report_what_depends_on_them(client, cleanup):
    """Settings has to say "2 students use this" BEFORE offering to remove it."""
    h, _year, _klass, hosteller, _day = _school(client, cleanup)
    cats = {c["id"]: c for c in
            client.get("/api/v1/students/categories", headers=h).json()}
    assert cats[hosteller]["student_count"] == 2
    assert cats[hosteller]["block_count"] == 0


def test_duplicate_names_are_refused(client, cleanup):
    h, _year, _klass, _hosteller, _day = _school(client, cleanup)
    r = client.post("/api/v1/students/categories", headers=h,
                    json={"name": "Hosteller"})
    assert r.status_code == 409, r.text


# ── the regression this change exists to prevent ─────────────────────────────
def test_renaming_a_category_does_not_break_its_blocks(client, cleanup):
    """The whole point of `D-129`.

    A block restricted to hostellers used to find them by comparing the category
    name to "hosteller". Rename it to "Hostel" — an ordinary thing to do in
    Settings — and the roster silently went to zero.
    """
    h, _year, klass, hosteller, _day = _school(client, cleanup)
    block = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Evening prep", "kind": "study",
        "class_ids": [klass["id"]], "category_id": hosteller}).json()
    assert block["roster_count"] == 2, block
    assert block["category_name"] == "Hosteller"

    renamed = client.patch(f"/api/v1/students/categories/{hosteller}", headers=h,
                           json={"name": "Hostel"})
    assert renamed.status_code == 200, renamed.text

    blocks = client.get("/api/v1/timetable/blocks", headers=h).json()
    after = next(b for b in blocks if b["id"] == block["id"])
    assert after["roster_count"] == 2, (
        "renaming a category must not change who is in a block")
    assert after["category_name"] == "Hostel"


def test_a_block_can_use_any_category_not_just_hostellers(client, cleanup):
    """The old boolean could only ask one question. A school with a Transport
    or Staff-ward category could not restrict a block to it at all."""
    h, _year, klass, _hosteller, day = _school(client, cleanup)
    block = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Bus duty", "kind": "study",
        "class_ids": [klass["id"]], "category_id": day}).json()
    assert block["roster_count"] == 1, block
    assert block["category_name"] == "Day Scholar"


def test_clearing_a_blocks_category_reopens_it_to_the_class(client, cleanup):
    """NULL is a meaningful value here, so the update has to be able to send it —
    a plain `if v is not None` could never clear the field."""
    h, _year, klass, hosteller, _day = _school(client, cleanup)
    block = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Evening prep", "kind": "study",
        "class_ids": [klass["id"]], "category_id": hosteller}).json()
    assert block["roster_count"] == 2

    opened = client.patch(f"/api/v1/timetable/blocks/{block['id']}", headers=h,
                          json={"category_id": None})
    assert opened.status_code == 200, opened.text
    assert opened.json()["roster_count"] == 3, "clearing it should include everyone"
    assert opened.json()["category_id"] is None


# ── removal is allowed, but never by accident ────────────────────────────────
def test_removing_a_category_in_use_is_refused_with_the_counts(client, cleanup):
    h, _year, _klass, hosteller, _day = _school(client, cleanup)
    r = client.delete(f"/api/v1/students/categories/{hosteller}", headers=h)
    assert r.status_code == 409, r.text
    assert "2 students" in r.text


def test_forcing_the_removal_unassigns_and_succeeds(client, cleanup):
    """The FK is ON DELETE SET NULL, so this un-assigns rather than deleting
    anybody — which is right, and is exactly why it needs confirming first."""
    h, _year, _klass, hosteller, _day = _school(client, cleanup)
    r = client.delete(f"/api/v1/students/categories/{hosteller}?force=true",
                      headers=h)
    assert r.status_code == 200, r.text

    names = {c["name"] for c in
             client.get("/api/v1/students/categories", headers=h).json()}
    assert "Hosteller" not in names
    # The students survive; they simply have no category any more.
    students = client.get("/api/v1/students", headers=h).json()
    assert len(students) == 3
    assert all(s["category_id"] is None for s in students
               if s["full_name"] in {"Asha", "Bina"})


def test_an_unused_category_removes_without_a_fight(client, cleanup):
    h, _year, _klass, _hosteller, _day = _school(client, cleanup)
    made = client.post("/api/v1/students/categories", headers=h,
                       json={"name": "Transport"}).json()
    r = client.delete(f"/api/v1/students/categories/{made['id']}", headers=h)
    assert r.status_code == 200, r.text
