"""V1-10 — fees: the collection board, the conversation, and the fence.

What each test pins:

* **The read service** (`Q-67`/`S-163`/`S-158`/`S-159`) — quarters are due-date
  windows, `collected`/`pending`/`overdue` never merge, a full concession is
  never a defaulter, and every class row carries both denominators.
* **`D-88`** — years never pool; dues carried from before are their own labelled
  line and never enter this year's totals.
* **`D-84`** — the conversation history: what the family *said*, append-only.
* **`S-156`** — the reminder's manners: one per week however many staff press
  it, and it **stops the moment the payment lands**.
* **`D-83` and the fence, which is the most important test in the file** — a
  teacher sees fee detail for a student she has been assigned, **and for nobody
  else**, and no academic surface carries a fee field at all.
"""

import uuid
from datetime import date, timedelta

from app.core.collection import (
    Collection,
    collection_sentence,
    current_quarter,
    quarter_of,
    quarter_windows,
    reminder_line,
)


def _setup(client, cleanup):
    """A year, two classes, three families — one paid, one behind, one on a
    full concession (the row that must never appear on a chase list)."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Fee Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    today = date.today()
    start = today - timedelta(days=120)
    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=364)).isoformat()}).json()
    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "8", "section": "B"}).json()
    kids = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"S{i}", "full_name": name, "class_id": klass["id"]}).json()
        for i, name in enumerate(["Kabir Shah", "Diya Nair", "Aarav Rao"], start=1)]
    for kid in kids[:2]:
        client.post(f"/api/v1/students/{kid['id']}/guardians", headers=h, json={
            "name": f"Parent of {kid['full_name'].split()[0]}",
            "phone": f"+9198{uuid.uuid4().int % 100000000:08d}", "is_primary": True})

    structure = client.post("/api/v1/fees/structures", headers=h, json={
        "academic_year_id": year["id"], "class_name": "8", "total_amount": 40000,
        "num_installments": 2,
        "installments": [
            {"installment_number": 1, "label": "Q1", "amount": 20000,
             "due_date": (start + timedelta(days=30)).isoformat()},
            {"installment_number": 2, "label": "Q2", "amount": 20000,
             "due_date": (start + timedelta(days=200)).isoformat()},
        ]}).json()
    fees = {}
    for kid, discount in zip(kids, [0, 0, 40000], strict=False):
        created = client.post("/api/v1/fees/student-fees", headers=h, json={
            "student_id": kid["id"], "fee_structure_id": structure["id"],
            "academic_year_id": year["id"], "total_fee": 40000,
            "discount": discount})
        assert created.status_code == 200, created.text
        sf = created.json()
        fees[kid["full_name"]] = sf
    # Kabir pays the first instalment; Diya does not (it is overdue).
    paid_inst = fees["Kabir Shah"]["installments"][0]
    client.post(f"/api/v1/fees/installments/{paid_inst['id']}/mark-paid", headers=h)
    return h, {"year": year, "class": klass, "kids": kids, "fees": fees}


# ── the pure vocabulary ──────────────────────────────────────────────────────
def test_core_collection_keeps_three_states_apart_and_buckets_by_due_date():
    """`Q-67`: a quarter is a **due-date window** — `installment_number` breaks
    when structures differ and `label` is free text. `S-163`: pending is a
    forecast and overdue is a phone call, so there is deliberately no
    `outstanding` to render."""
    start, end = date(2026, 4, 1), date(2027, 3, 31)
    ws = quarter_windows(start, end)
    assert [w.label for w in ws] == ["Q1", "Q2", "Q3", "Q4"]
    assert ws[0].start == start and ws[-1].end == end
    assert quarter_of(date(2026, 5, 10), ws) == "Q1"
    assert quarter_of(date(2026, 11, 2), ws) == "Q3"
    # An instalment with no due date is a WORD, never silently bucketed into Q1.
    assert quarter_of(None, ws) == "unscheduled"
    assert current_quarter(ws, date(2026, 8, 1)).label == "Q2"

    c = Collection()
    c.add(collected=1000, billed=3000)
    c.add(overdue=1500, billed=0)
    c.add(pending=500)
    assert (c.collected, c.overdue, c.pending) == (1000, 1500, 500)
    assert not hasattr(c, "outstanding")     # the blend has no name here
    assert c.pct == round(1000 / 3000 * 100, 1)
    # Nothing billed is NOT 0% collected.
    assert Collection().pct is None

    # `S-155`: the sentence names the shape, not the total.
    said = collection_sentence(ws[1], c, 4, prev_pct=50.0)
    assert "Q2 is 33.3% collected" in said and "behind" in said
    assert "4 families past a due date" in said
    # ...and a quarter whose money is not due yet is **not 0% collected**. That
    # is a quarter that has not started, and reading it as a failure is the same
    # invented-red the unmarked register rule forbids (ux §5).
    ahead = Collection()
    ahead.add(pending=100000, billed=100000)
    early = collection_sentence(ws[1], ahead, 0)
    assert "0%" not in early and "behind" not in early
    assert "falls due through" in early and "none of it is overdue yet" in early
    # The parent's line is neutral, and it says how much and by when.
    assert reminder_line(20000, date(2026, 7, 15), 20000).startswith("₹20,000 due by 15 Jul")
    assert "defaulter" not in reminder_line(1, None, 0).lower()


# ── the board ────────────────────────────────────────────────────────────────
def test_the_board_names_the_quarter_the_class_and_the_family(client, cleanup):
    h, ctx = _setup(client, cleanup)
    # Ask for Q1 explicitly: the fixture's instalments fall in Q1 and Q3, so the
    # quarter today sits in has nothing billed — which the board reports as
    # `pct: null`, **not** 0% collected.
    board = client.get("/api/v1/fees/collection?quarter=Q1", headers=h)
    assert board.status_code == 200, board.text
    board = board.json()
    empty = client.get("/api/v1/fees/collection?quarter=Q2", headers=h).json()
    assert empty["pct"] is None, "a quarter with no instalments is not 0% collected"

    assert [q["label"] for q in board["quarters"]] == ["Q1", "Q2", "Q3", "Q4"]
    q1 = board["quarters"][0]
    # Kabir paid 20k of the 60k billed in Q1 (two full fees + one concession at 0).
    assert q1["collected"] == 20000
    assert q1["overdue"] == 20000        # Diya's, past its due date
    assert q1["pending"] == 0            # nothing in Q1 is still ahead of its date
    assert q1["pct"] == round(20000 / 40000 * 100, 1)

    # `S-159`: both denominators on the class row.
    row = next(r for r in board["by_class"] if r["class_label"] == "8-B")
    assert row["families_pending"] == 1 and row["families_total"] == 3

    # `S-157`/`S-158`: the family is named, and the full concession is absent.
    names = {d["student_name"] for d in board["defaulters"]}
    assert names == {"Diya Nair"}, "a 100% concession owes ₹0 and is not a defaulter"
    diya = board["defaulters"][0]
    assert diya["guardian_name"] and diya["guardian_phone"]
    assert diya["overdue_amount"] == 20000
    assert diya["reminded_on"] is None
    assert "Q1" in board["headline"] and "%" in board["headline"]


def test_years_never_pool_and_carried_dues_are_their_own_line(client, cleanup):
    """`D-88`: `opening_dues` used to be silently missing from every roll-up, so
    a child carrying ₹20,000 from last year with this year paid read as `paid`.
    It is now a labelled line, and still never inside this year's totals."""
    h, ctx = _setup(client, cleanup)
    sf_id = ctx["fees"]["Kabir Shah"]["id"]
    client.patch(f"/api/v1/fees/student-fees/{sf_id}", headers=h,
                 json={"opening_dues": 15000})

    board = client.get("/api/v1/fees/collection", headers=h).json()
    assert board["carried"]["amount"] == 15000
    assert board["carried"]["families"] == 1
    assert "not counted in the figures above" in board["carried"]["note"]
    # ...and it did NOT move this year's arithmetic.
    q1 = board["quarters"][0]
    assert q1["collected"] == 20000 and q1["overdue"] == 20000


# ── D-84: the conversation ───────────────────────────────────────────────────
def test_the_conversation_history_records_what_the_family_said(client, cleanup):
    h, ctx = _setup(client, cleanup)
    sf_id = ctx["fees"]["Diya Nair"]["id"]
    first = client.post(f"/api/v1/fees/student-fees/{sf_id}/notes", headers=h, json={
        "kind": "call", "said": "spoke to the mother — paying after the 15th",
        "promised_date": (date.today() + timedelta(days=10)).isoformat()})
    assert first.status_code == 200, first.text
    client.post(f"/api/v1/fees/student-fees/{sf_id}/notes", headers=h, json={
        "kind": "visit", "said": "father came in, asked for two weeks"})

    notes = client.get(f"/api/v1/fees/student-fees/{sf_id}/notes", headers=h).json()
    assert [n["said"] for n in notes] == [
        "father came in, asked for two weeks",
        "spoke to the mother — paying after the 15th"]   # newest first, both kept
    assert notes[0]["author_name"] == "Director"

    # `S-161`: the board shows what was SAID, not that a button was pressed.
    board = client.get("/api/v1/fees/collection", headers=h).json()
    diya = next(d for d in board["defaulters"] if d["student_name"] == "Diya Nair")
    assert diya["last_said"] == "father came in, asked for two weeks"


# ── S-156: the reminder's manners ────────────────────────────────────────────
def test_the_reminder_fires_once_a_week_and_stops_when_the_money_lands(client, cleanup):
    h, ctx = _setup(client, cleanup)
    diya = ctx["fees"]["Diya Nair"]["id"]

    first = client.post(f"/api/v1/fees/student-fees/{diya}/remind", headers=h).json()
    # Quiet hours may legitimately block it — both outcomes are correct, and
    # neither is an error the screen has to hide.
    assert first["sent"] == 1 or first["skipped"] == "quiet_hours"
    if first["sent"]:
        again = client.post(f"/api/v1/fees/student-fees/{diya}/remind", headers=h).json()
        assert again["sent"] == 0 and again["skipped"] == "already_reminded"
        board = client.get("/api/v1/fees/collection", headers=h).json()
        row = next(d for d in board["defaulters"] if d["student_name"] == "Diya Nair")
        assert row["reminded_on"] is not None, "the row remembers, so nobody is chased twice"

    # It stops the moment the payment lands — including at the counter.
    kabir = ctx["fees"]["Kabir Shah"]
    for inst in kabir["installments"]:
        client.post(f"/api/v1/fees/installments/{inst['id']}/mark-paid", headers=h)
    done = client.post(f"/api/v1/fees/student-fees/{kabir['id']}/remind", headers=h).json()
    assert done["sent"] == 0 and done["skipped"] == "nothing_due"


# ── D-83 + the fence ─────────────────────────────────────────────────────────
def _teacher(client, cleanup, h):
    username = f"t{uuid.uuid4().hex[:8]}"
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": username, "password": "supersecret1", "role": "teacher"}]}).json()
    cleanup["users"].append(uuid.UUID(bulk["results"][0]["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": username, "password": "supersecret1"}).json()
    members = client.get("/api/v1/org/members", headers=h).json()["members"]
    member_id = next(x for x in members if x.get("username") == username)["member_id"]
    return {"Authorization": f"Bearer {login['access_token']}"}, member_id


def test_an_assigned_teacher_sees_that_one_family_and_no_other(client, cleanup):
    """`D-83` narrows a fence stated in three documents, so the narrowing is
    asserted rather than reviewed: the assigned teacher gets the full detail —
    amount, date, and the conversation log — for **that student**, and a 403 for
    anybody else's."""
    h, ctx = _setup(client, cleanup)
    th, member_id = _teacher(client, cleanup, h)
    diya = ctx["fees"]["Diya Nair"]["id"]
    kabir = ctx["fees"]["Kabir Shah"]["id"]
    client.post(f"/api/v1/fees/student-fees/{diya}/notes", headers=h, json={
        "kind": "call", "said": "spoke to the mother — paying after the 15th"})

    assigned = client.post(f"/api/v1/fees/student-fees/{diya}/assign", headers=h,
                           json={"member_id": member_id})
    assert assigned.status_code == 200, assigned.text
    task_id = assigned.json()["task_id"]

    task = client.get(f"/api/v1/tasks/{task_id}", headers=th)
    assert task.status_code == 200, "the assignee can open her own task"
    task = task.json()
    # The detail travels in the task itself (`D-83`), conversation included.
    assert "Fee follow-up" in task["title"]
    # The whole outstanding balance, not just the overdue slice — the person
    # making the call needs the number the family will quote back at her.
    assert "₹40,000" in task["description"]
    assert "paying after the 15th" in task["description"]

    detail = client.get(f"/api/v1/fees/followup/{task_id}", headers=th)
    assert detail.status_code == 200, detail.text
    detail = detail.json()
    assert detail["student_name"] == "Diya Nair"
    assert detail["pending_amount"] == 40000
    assert detail["guardian_phone"]
    assert any("15th" in (n["said"] or "") for n in detail["notes"])

    # ...and nothing else. No board, no other family, no fee list.
    assert client.get("/api/v1/fees/collection", headers=th).status_code == 403
    assert client.get(f"/api/v1/fees/student-fees/{kabir}", headers=th).status_code == 403
    assert client.get(f"/api/v1/fees/student-fees/{kabir}/notes",
                      headers=th).status_code == 403
    # A task she was not assigned is not hers to read.
    th2, _ = _teacher(client, cleanup, h)
    assert client.get(f"/api/v1/fees/followup/{task_id}",
                      headers=th2).status_code == 403,         "a task she was not assigned is not hers to read"


def test_no_fee_field_reaches_an_academic_surface(client, cleanup):
    """The rule that outranks the screen. It is one join away at all times, and
    a "fees pending" chip on a child's report card is the single most damaging
    thing this module could do (`S-157`)."""
    h, ctx = _setup(client, cleanup)
    kid = ctx["kids"][1]["id"]
    for path in (f"/api/v1/students/{kid}/growth",
                 f"/api/v1/students/{kid}/report-card",
                 f"/api/v1/students/{kid}/timeline",
                 f"/api/v1/students/{kid}/analysis"):
        body = str(client.get(path, headers=h).json()).lower()
        for word in ("fee", "overdue_amount", "installment", "defaulter"):
            assert word not in body, f"{path} leaked '{word}' onto an academic surface"
