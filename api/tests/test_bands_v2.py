"""ABC bands, v2 — distribution, allocation and the teacher's way in.

Founder call, 2026-08-04. Three things V1-9 left undone, and each has a rule the
tests exist to pin:

* **The distribution board.** `S-169` rejected the distribution as the admin's
  *headline*, and that still holds — so `headline` here is the movement sentence
  and the tiers render beneath it. What the packet adds is the shape of the
  school, which movement genuinely cannot answer.
* **The unit is the placement, not the child** (`D-75`). There is no overall
  letter, so a child who is A in Maths and C in Hindi is counted in both — and a
  test asserts exactly that, because the obvious "fix" is to collapse him to one
  row and it would quietly reinstate the letter the module deleted.
* **The teacher can finally set a band.** V1-9 made every write admin-only, so
  the person who knows whether the child can read the passage could see a band
  and never file one. She gets her own class-subjects, **blocked** rather than
  filtered for anyone else's.
"""

import uuid
from datetime import date, timedelta


def _setup(client, cleanup):
    """Two classes, two monitored subjects, one teacher who takes 6-B only.

    The second class is what makes the by-class chart mean anything, and the
    teacher's narrow scope is what the guard tests need."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Band V2 Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    today = date.today()
    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=60)).isoformat(),
        "end_date": (today + timedelta(days=240)).isoformat()}).json()
    client.post("/api/v1/academics/terms", headers=h, json={
        "academic_year_id": year["id"], "name": "Term 1",
        "start_date": (today - timedelta(days=60)).isoformat(),
        "end_date": (today + timedelta(days=240)).isoformat()})
    term_id = client.get("/api/v1/academics/terms", headers=h).json()[0]["id"]

    username = f"t{uuid.uuid4().hex[:8]}"
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": username, "password": "supersecret1", "role": "teacher"}]}).json()
    cleanup["users"].append(uuid.UUID(bulk["results"][0]["user_id"]))
    th = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={
        "identifier": username, "password": "supersecret1"}).json()["access_token"]}
    members = client.get("/api/v1/org/members", headers=h).json()["members"]
    teacher_member = next(x for x in members if x.get("username") == username)["member_id"]

    six_b = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "B"}).json()
    seven_a = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "7", "section": "A"}).json()
    hindi = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Hindi"}).json()
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Mathematics"}).json()
    telugu = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Telugu"}).json()

    # The teacher takes both monitored subjects in 6-B and nothing in 7-A.
    for subj in (hindi, maths):
        client.post("/api/v1/academics/class-subjects", headers=h, json={
            "class_id": six_b["id"], "subject_id": subj["id"],
            "teacher_member_id": teacher_member, "periods_per_week": 5})
        client.post("/api/v1/academics/class-subjects", headers=h, json={
            "class_id": seven_a["id"], "subject_id": subj["id"], "periods_per_week": 5})
    # Telugu is taught but NOT monitored — it must never reach a denominator.
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": six_b["id"], "subject_id": telugu["id"],
        "teacher_member_id": teacher_member, "periods_per_week": 3})

    kids_b = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"B{i}", "full_name": name, "class_id": six_b["id"],
        "roll_no": str(i)}).json()
        for i, name in enumerate(["Kabir Shah", "Diya Nair"], start=1)]
    kids_a = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"A{i}", "full_name": name, "class_id": seven_a["id"],
        "roll_no": str(i)}).json()
        for i, name in enumerate(["Aarav Rao"], start=1)]

    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [hindi["id"], maths["id"]]})
    return h, th, {"six_b": six_b, "seven_a": seven_a, "hindi": hindi, "maths": maths,
                   "telugu": telugu, "kids_b": kids_b, "kids_a": kids_a,
                   "term_id": term_id, "teacher_member": teacher_member}


def _file(client, h, ctx, class_id, subject_id, rows):
    return client.post("/api/v1/bands/class/file", headers=h, json={
        "class_id": class_id, "subject_id": subject_id, "term_id": ctx["term_id"],
        "source": "observation", "rows": rows})


# ── the three charts ─────────────────────────────────────────────────────────
def test_distribution_counts_placements_not_children(client, cleanup):
    """`D-75`: a child who is A in Maths and C in Hindi is in BOTH columns.

    Collapsing him to one row is the overall letter coming back through the
    chart, so this is asserted as arithmetic and not left to a comment."""
    h, _, ctx = _setup(client, cleanup)
    kabir, diya = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"},
           {"student_id": diya["id"], "tier": "B"}])
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["maths"]["id"],
          [{"student_id": kabir["id"], "tier": "A"},
           {"student_id": diya["id"], "tier": "B"}])

    d = client.get("/api/v1/bands/distribution", headers=h).json()
    school = d["school"]
    # Four placements from two children — not two.
    assert school["assessed"] == 4
    assert (school["a"], school["b"], school["c"]) == (1, 2, 1)
    assert school["a_pct"] == 25.0 and school["c_pct"] == 25.0
    # The caption carries both units, so no screen can quote a bare number.
    assert "4 placements" in d["caption"]
    assert "2 of 3 children assessed" in d["caption"]

    # Movement leads (`S-169`) — the headline is the programme's own sentence.
    assert d["headline"]
    assert "distribution" not in d["headline"].lower()


def test_distribution_by_class_and_subject_carry_denominators(client, cleanup):
    """Every row states what it was divided by, and an unbanded class is a
    `not_assessed` count — never a zero and never folded into C (ux §4/§5)."""
    h, _, ctx = _setup(client, cleanup)
    kabir, diya = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"},
           {"student_id": diya["id"], "tier": "C"}])

    d = client.get("/api/v1/bands/distribution", headers=h).json()
    six_b = next(r for r in d["by_class"] if r["label"] == "6-B")
    seven_a = next(r for r in d["by_class"] if r["label"] == "7-A")
    # 2 children × 2 monitored subjects = 4 possible placements; 2 exist.
    assert six_b["eligible"] == 4 and six_b["assessed"] == 2
    assert six_b["not_assessed"] == 2
    assert six_b["c_pct"] == 100.0     # of what was assessed, not of the roster
    # Nobody has looked at 7-A: a gap in the record, not a class of A students.
    assert seven_a["assessed"] == 0 and seven_a["not_assessed"] == 2
    assert seven_a["a_pct"] == seven_a["c_pct"] == 0.0

    # Telugu is taught but not monitored — it is in no denominator anywhere.
    assert {r["label"] for r in d["by_subject"]} == {"Hindi", "Mathematics"}
    hindi = next(r for r in d["by_subject"] if r["label"] == "Hindi")
    assert hindi["assessed"] == 2 and hindi["eligible"] == 3   # 6-B(2) + 7-A(1)


def test_distribution_is_scoped_for_a_teacher(client, cleanup):
    """Her board is her class-subjects — the same computation, narrower input,
    so her figures and the admin's can never disagree about 6-B."""
    h, th, ctx = _setup(client, cleanup)
    kabir, diya = ctx["kids_b"]
    aarav = ctx["kids_a"][0]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"},
           {"student_id": diya["id"], "tier": "B"}])
    _file(client, h, ctx, ctx["seven_a"]["id"], ctx["hindi"]["id"],
          [{"student_id": aarav["id"], "tier": "C"}])

    admin = client.get("/api/v1/bands/distribution", headers=h).json()
    mine = client.get("/api/v1/bands/distribution", headers=th).json()
    assert admin["school"]["assessed"] == 3
    assert mine["school"]["assessed"] == 2          # 7-A is not hers
    assert {r["label"] for r in mine["by_class"]} == {"6-B"}
    # And the class they share reads identically on both boards.
    a_six = next(r for r in admin["by_class"] if r["label"] == "6-B")
    m_six = next(r for r in mine["by_class"] if r["label"] == "6-B")
    assert (a_six["a"], a_six["b"], a_six["c"]) == (m_six["a"], m_six["b"], m_six["c"])


# ── the teacher's way in ─────────────────────────────────────────────────────
def test_teacher_files_her_own_class_and_is_blocked_elsewhere(client, cleanup):
    """V1-9 made every band write admin-only. She now files 6-B Hindi, and 7-A
    is a **403 with a sentence**, not an empty table she would read as
    "nobody is banded here" (`S-46`'s blocked-not-filtered rule)."""
    h, th, ctx = _setup(client, cleanup)
    kabir, _ = ctx["kids_b"]
    aarav = ctx["kids_a"][0]

    ok = _file(client, th, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
               [{"student_id": kabir["id"], "tier": "C"}])
    assert ok.status_code == 200, ok.text

    blocked = _file(client, th, ctx, ctx["seven_a"]["id"], ctx["hindi"]["id"],
                    [{"student_id": aarav["id"], "tier": "C"}])
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "not_your_class_subject"

    # Reading is the same permission as writing.
    assert client.get("/api/v1/bands/class", headers=th, params={
        "class_id": ctx["six_b"]["id"], "subject_id": ctx["hindi"]["id"]}).status_code == 200
    assert client.get("/api/v1/bands/class", headers=th, params={
        "class_id": ctx["seven_a"]["id"], "subject_id": ctx["hindi"]["id"]}).status_code == 403


def test_scope_gates_the_nav(client, cleanup):
    """A teacher who takes none of the monitored subjects gets `has_scope=False`
    and therefore no ABC Bands nav item — an area that opens on "nothing here
    for you" is worse than one that was never offered (ux §13)."""
    h, th, ctx = _setup(client, cleanup)
    mine = client.get("/api/v1/bands/scope", headers=th).json()
    assert mine["enabled"] and mine["has_scope"] and not mine["is_admin"]
    assert [c["class_label"] for c in mine["classes"]] == ["6-B"]
    assert {s["label"] for s in mine["classes"][0]["subjects"]} == {"Hindi", "Mathematics"}
    assert {s["label"] for s in mine["subjects"]} == {"Hindi", "Mathematics"}

    # Turn the monitored set down to a subject she does not teach.
    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [ctx["telugu"]["id"]]})
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": ctx["seven_a"]["id"], "subject_id": ctx["telugu"]["id"],
        "periods_per_week": 3})
    # She teaches Telugu in 6-B, so she still has scope; the admin always does.
    assert client.get("/api/v1/bands/scope", headers=h).json()["has_scope"] is True

    # A school monitoring nothing offers the area to nobody.
    client.put("/api/v1/bands/setup/monitored", headers=h, json={"subject_ids": []})
    off = client.get("/api/v1/bands/scope", headers=th).json()
    assert off["enabled"] is False and off["has_scope"] is False


# ── allocation ───────────────────────────────────────────────────────────────
def test_allocation_lists_c_placements_unassigned_first(client, cleanup):
    """The screen exists for the empty column, so unassigned sorts to the top and
    the headline counts it. `S-188`: every row names its subject."""
    h, _, ctx = _setup(client, cleanup)
    kabir, diya = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"},
           {"student_id": diya["id"], "tier": "A"}])
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["maths"]["id"],
          [{"student_id": kabir["id"], "tier": "C"}])

    board = client.get("/api/v1/bands/allocation", headers=h).json()
    assert len(board["rows"]) == 2            # Kabir twice — one row per subject
    assert {r["subject_name"] for r in board["rows"]} == {"Hindi", "Mathematics"}
    assert all(r["full_name"] == "Kabir Shah" for r in board["rows"])
    assert board["unassigned"] == 2 and board["assigned"] == 0
    assert "2 of 2" in board["headline"]

    # Assign one, and the board moves it — and the sort puts the open one first.
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "member_id": ctx["teacher_member"], "term_id": ctx["term_id"]})
    board = client.get("/api/v1/bands/allocation", headers=h).json()
    assert board["assigned"] == 1 and board["unassigned"] == 1
    assert board["rows"][0]["owner_member_id"] is None
    hindi_row = next(r for r in board["rows"] if r["subject_name"] == "Hindi")
    assert hindi_row["owner_name"] and hindi_row["intervention_id"]

    # Filters narrow the rows AND the sentence, so the two can't disagree.
    only_maths = client.get("/api/v1/bands/allocation", headers=h,
                            params={"subject_id": ctx["maths"]["id"]}).json()
    assert len(only_maths["rows"]) == 1 and only_maths["unassigned"] == 1
    assert len(client.get("/api/v1/bands/allocation", headers=h, params={
        "class_id": ctx["seven_a"]["id"]}).json()["rows"]) == 0


def test_owner_suggestions_suggest_without_restricting(client, cleanup):
    """The founder's rule: the teachers already in front of this child come
    first, and **everyone else is still on the list**. `load` rides along as
    capacity, never as a score (`S-170`)."""
    h, _, ctx = _setup(client, cleanup)
    kabir, _ = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"}])

    rows = client.get("/api/v1/bands/allocation/suggestions", headers=h, params={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"]}).json()
    assert len(rows) >= 2                       # the teacher AND the admin
    top = rows[0]
    assert top["member_id"] == ctx["teacher_member"]
    assert top["suggested"] is True
    assert "Hindi" in top["reason"]             # says WHY, never just a name
    # Not restricted: the admin, who teaches nothing, is still assignable.
    assert any(not r["suggested"] for r in rows)
    assert all(r["load"] == 0 for r in rows)

    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "member_id": ctx["teacher_member"], "term_id": ctx["term_id"]})
    rows = client.get("/api/v1/bands/allocation/suggestions", headers=h, params={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"]}).json()
    owner = next(r for r in rows if r["member_id"] == ctx["teacher_member"])
    assert owner["current"] is True and owner["load"] == 1
    assert rows[0]["current"] is True           # the incumbent sorts first


def test_allocation_is_admin_only(client, cleanup):
    """Who owns whom is a decision about how the school runs (`D-73`)."""
    _, th, _ = _setup(client, cleanup)
    assert client.get("/api/v1/bands/allocation", headers=th).status_code == 403


# ── the written summary ──────────────────────────────────────────────────────
def test_summary_is_never_blank_and_never_a_diagnosis(client, cleanup):
    """AI-off — which is dev, tests, and every school without a key — the
    deterministic sentences render, so the owner's page always says something.

    The forbidden register is asserted rather than trusted to the prompt. A band
    is a teaching group; the moment this text calls a child weak or slow it has
    become the label `D-67` and P4 exist to prevent, and it is the one surface
    where a model is most tempted to."""
    h, th, ctx = _setup(client, cleanup)
    kabir, _ = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"}])
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "member_id": ctx["teacher_member"], "term_id": ctx["term_id"],
        "exit_criterion": "reads a grade-level passage at 60 wpm, twice running"})
    plan = client.get("/api/v1/bands/support", headers=th).json()["groups"][0]["rows"][0]
    iv = plan["intervention_id"]

    r = client.get(f"/api/v1/bands/support/{iv}/summary", headers=th)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["source"] == "computed"        # no key in the suite
    assert out["summary"].strip()             # never blank
    assert out["insights"]
    # It says what it was written from, so a reader can check it.
    assert any("check-in" in b for b in out["based_on"])

    blob = " ".join([out["summary"], *out["insights"]]).lower()
    for word in ("weak", "slow", "poor", "lazy", "unmotivated", "low-ability",
                 "learning difficulty", "disorder", "stupid", "dull"):
        assert word not in blob, f"the summary called a child {word!r}"
    # A week nobody recorded is a statement about the RECORD (`S-164`).
    assert "gap in the record" in out["summary"] or "record shows" in out["summary"]


def test_summary_is_the_owners_and_the_admins_only(client, cleanup):
    """Never another owner's children (`S-170`), on this surface as on the rest."""
    h, th, ctx = _setup(client, cleanup)
    kabir, _ = ctx["kids_b"]
    _file(client, h, ctx, ctx["six_b"]["id"], ctx["hindi"]["id"],
          [{"student_id": kabir["id"], "tier": "C"}])
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "member_id": ctx["teacher_member"], "term_id": ctx["term_id"]})
    iv = client.get("/api/v1/bands/support", headers=th).json()[
        "groups"][0]["rows"][0]["intervention_id"]

    # The admin may read it; a teacher who owns nobody may not.
    assert client.get(f"/api/v1/bands/support/{iv}/summary", headers=h).status_code == 200

    other = f"o{uuid.uuid4().hex[:8]}"
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": other, "password": "supersecret1", "role": "teacher"}]}).json()
    cleanup["users"].append(uuid.UUID(bulk["results"][0]["user_id"]))
    oh = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={
        "identifier": other, "password": "supersecret1"}).json()["access_token"]}
    blocked = client.get(f"/api/v1/bands/support/{iv}/summary", headers=oh)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "not_your_student"
