"""V1-9 — bands / the support programme.

The module's own §10 says step 0 is four fixes and *"nothing below is honest
until these land"*. The tests are in that order.

* **The core loop** — an intervention could never be finished, so a goal met in
  July kept injecting a targeted daily check into the period card in March.
* **The owner** — every intervention in every real school was created
  unassigned, because the assignee came from a field no screen set.
* **The deletions** (`S-183`) — `apply_band_suggestions` re-banded a class off
  *each child's most recent cycle, whatever it was*: a Tuesday slip test could
  move eleven children between support tiers.
* **Per subject, no overall letter** (`D-75`) — one letter for a child who reads
  two years below grade and is fine at arithmetic described neither, and the
  check generator then handed him easier *maths*.
* **Movement is a test** (`D-76`/`S-184`/`Q-81`) — locked only, one subject,
  size shown, and the moves reviewed before they commit.
* **The weekly check-in opens already written** (`S-164`/`D-87`).
"""

import uuid
from datetime import date, timedelta

from app.core.bands import Placement, chip, movement, size_warnings, starter_descriptors


def _setup(client, cleanup):
    """A school with two monitored subjects, one teacher who owns Hindi, and
    three children — the smallest world where "per subject" means anything."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Band Org", "name": "Director", "email": email,
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

    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "B"}).json()
    hindi = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Hindi"}).json()
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Mathematics"}).json()
    for subj in (hindi, maths):
        client.post("/api/v1/academics/class-subjects", headers=h, json={
            "class_id": klass["id"], "subject_id": subj["id"],
            "teacher_member_id": teacher_member, "periods_per_week": 5})
    kids = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"S{i}", "full_name": name, "class_id": klass["id"],
        "roll_no": str(i)}).json()
        for i, name in enumerate(["Kabir Shah", "Diya Nair", "Aarav Rao"], start=1)]

    # Two monitored subjects — the third stays off, so "not monitored" is real.
    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [hindi["id"], maths["id"]]})
    return h, th, {"class": klass, "hindi": hindi, "maths": maths, "kids": kids,
                   "term_id": term_id, "teacher_member": teacher_member,
                   "year": year}


def _cs_id(client, h, ctx, subject):
    rows = client.get(f"/api/v1/academics/classes/{ctx['class']['id']}/subjects",
                      headers=h).json()
    return next(cs["id"] for cs in rows if cs["subject_id"] == subject["id"])


def _file(client, h, ctx, subject, tiers, source="observation"):
    return client.post("/api/v1/bands/class/file", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": subject["id"],
        "term_id": ctx["term_id"], "source": source,
        "rows": [{"student_id": k["id"], "tier": t}
                 for k, t in zip(ctx["kids"], tiers, strict=False)]})


# ── the pure vocabulary ──────────────────────────────────────────────────────
def test_core_bands_never_averages_a_child_across_subjects():
    """`S-186`: one chip reads **"C · Hindi"** — the lowest band with the subject
    that earned it. There is no overall letter to compute, and computing one is
    what `D-75` retires."""
    places = [
        Placement(subject_id="m", subject_name="Mathematics", tier="A"),
        Placement(subject_id="h", subject_name="Hindi", tier="C"),
    ]
    assert chip(places) == "C · Hindi"
    assert chip([]) is None                       # not assessed is its own state

    assert movement("C", "B") == "up"
    assert movement("B", "C") == "down"
    assert movement(None, "C") == "new"
    assert movement("C", None) == "same"          # didn't sit it → keeps his band

    # `S-184`: warn, never block.
    assert size_warnings(10, 24, 38)              # small test AND thin room
    assert size_warnings(80, 38, 38) == []
    # `S-175`: never an empty box for a teacher to invent a standard against.
    assert set(starter_descriptors("Hindi")) == {"A", "B", "C"}
    assert starter_descriptors("Mathematics")["C"] != starter_descriptors("Hindi")["C"]
    assert starter_descriptors("Woodwork")["B"]   # a subject nobody anticipated


# ── step 0: the four fixes (S-180) ───────────────────────────────────────────
def test_the_deleted_routes_are_gone(client, cleanup):
    """`S-183`: two implicit paths that re-banded children off whatever test
    happened last. Deleted, not deprecated — the unchosen route was the
    dangerous one."""
    h, _th, _ctx = _setup(client, cleanup)
    for path, body in (("/api/v1/assessments/bands/apply-suggestions", {}),
                       ("/api/v1/assessments/bands/categorize", {"cycle_id": str(uuid.uuid4())})):
        assert client.post(path, headers=h, json=body).status_code == 404


def test_an_intervention_can_finally_be_finished_and_the_daily_check_stops(client, cleanup):
    """The loop the module exists to close. `RecommendationsService` filters on
    `status == 'active'`, so before V1-9 a goal achieved in July kept injecting a
    targeted check into the period card in March."""
    h, _th, ctx = _setup(client, cleanup)
    kabir = ctx["kids"][0]
    _file(client, h, ctx, ctx["hindi"], ["C", "B", "A"])
    assert client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "term_id": ctx["term_id"], "exit_criterion": "reads a passage at 60 wpm",
    }).status_code == 200

    cs_id = _cs_id(client, h, ctx, ctx["hindi"])
    checks = client.get(f"/api/v1/checks?class_subject_id={cs_id}", headers=h).json()
    assert any(c.get("student_id") == kabir["id"] for c in checks["checks"]), \
        "the C child should be getting a targeted check"

    # The admin can close it too — the owner's list is the TEACHER's, since the
    # plan defaulted to the subject teacher (`S-168`).
    plan = client.get(f"/api/v1/assessments/students/{kabir['id']}/interventions",
                      headers=h).json()[0]
    closed = client.post(f"/api/v1/bands/support/{plan['id']}/close",
                         headers=h, json={"status": "achieved",
                                          "outcome_note": "reads a full paragraph unaided"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "achieved"

    # Tomorrow's checks are generated fresh — and no longer name him.
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    after = client.get(f"/api/v1/checks?class_subject_id={cs_id}&on_date={tomorrow}",
                       headers=h).json()
    assert not any(c.get("student_id") == kabir["id"] for c in after["checks"])


def test_the_owner_defaults_to_the_subject_teacher_never_unassigned(client, cleanup):
    """`S-168`/§4.3: the assignee used to come from
    `school_classes.class_teacher_member_id`, which no screen set — so every
    intervention in every real school was created unassigned."""
    h, th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "C", "A"])
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": ctx["kids"][0]["id"], "subject_id": ctx["hindi"]["id"],
        "term_id": ctx["term_id"]})
    ivs = client.get(f"/api/v1/assessments/students/{ctx['kids'][0]['id']}/interventions",
                     headers=h).json()
    assert ivs and ivs[0]["owner_member_id"] == ctx["teacher_member"]
    assert ivs[0]["subject_name"] == "Hindi"

    # ...and it lands on HER list the same afternoon (`D-71`).
    mine = client.get("/api/v1/bands/support", headers=th).json()
    assert [g["subject_name"] for g in mine["groups"]] == ["Hindi"]
    assert mine["groups"][0]["rows"][0]["full_name"] == "Kabir Shah"
    # No compliance score anywhere on it (`S-170`).
    assert "%" not in mine["headline"]


# ── D-75: per subject, and no overall letter ─────────────────────────────────
def test_a_child_is_banded_per_subject_and_the_chip_names_the_subject(client, cleanup):
    h, _th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "B", "A"])
    _file(client, h, ctx, ctx["maths"], ["A", "B", "A"])
    kabir = ctx["kids"][0]

    growth = client.get(f"/api/v1/students/{kabir['id']}/growth", headers=h).json()
    # He reads two years below grade and is fine at arithmetic. One letter
    # described neither; the chip names the subject that earned it (`S-186`).
    assert growth["band"] == "C · Hindi"
    subjects_in_history = {e["subject_name"] for e in growth["band_history"]}
    assert subjects_in_history == {"Hindi", "Mathematics"}

    chips = client.get("/api/v1/assessments/bands/current", headers=h).json()
    assert chips[kabir["id"]] == "C · Hindi"
    assert chips[ctx["kids"][2]["id"]] == "A · Hindi"   # A in both → still named

    # And the class board is per subject — never a blend of the two.
    board = client.get("/api/v1/bands/class", headers=h, params={
        "class_id": ctx["class"]["id"], "subject_id": ctx["maths"]["id"]}).json()
    assert board["subject_name"] == "Mathematics"
    assert next(r for r in board["rows"]
                if r["student_id"] == kabir["id"])["current_tier"] == "A"
    # `S-166`: the letter never travels without its sentence.
    assert all(d["text"] for d in board["descriptors"])


def test_the_daily_check_now_targets_the_subject_the_child_is_weak_in(client, cleanup):
    """The thing `D-75` buys for free: the generator already runs per
    class-subject, so the Hindi period hands the easier route to the children
    who cannot read — instead of to whoever the blended letter caught."""
    h, _th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "A", "A"])
    _file(client, h, ctx, ctx["maths"], ["A", "A", "A"])
    cs = {"hindi": _cs_id(client, h, ctx, ctx["hindi"]),
          "maths": _cs_id(client, h, ctx, ctx["maths"])}

    hindi = client.get(f"/api/v1/checks?class_subject_id={cs['hindi']}", headers=h).json()
    maths = client.get(f"/api/v1/checks?class_subject_id={cs['maths']}", headers=h).json()
    assert any(c["band_scope"] == "C" for c in hindi["checks"]), \
        "Hindi has a C child — it should get the richer C-band check"
    assert not any(c["band_scope"] == "C" for c in maths["checks"]), \
        "nobody is C in Maths — the old blended letter would have added one anyway"


# ── D-76 / S-184 / Q-81: movement is an evidenced test ───────────────────────
def _locked_exam(client, h, ctx, subject, scores, total=10, name="Slip test 3"):
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": subject["id"], "type": "slip_test",
        "name": name, "date": date.today().isoformat(), "total_marks": total,
        "rows": [{"student_id": k["id"], "score": s}
                 for k, s in zip(ctx["kids"], scores, strict=False) if s is not None]}).json()
    return exam


def test_promotion_needs_a_lock_shows_its_moves_and_touches_one_subject(client, cleanup):
    h, th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "B", "A"])
    _file(client, h, ctx, ctx["maths"], ["C", "C", "C"])
    kabir, diya, aarav = ctx["kids"]
    # Kabir 9/10 = 90% → A; Diya 4/10 = 40% → C; Aarav did not sit it.
    exam = _locked_exam(client, h, ctx, ctx["hindi"], [9, 4, None])

    # `S-184`/`D-53`: an unverified transcription must not move a child.
    unlocked = client.get(f"/api/v1/bands/promote/{exam['id']}", headers=th).json()
    assert unlocked["blocked"] and "lock" in unlocked["blocked"].lower()
    assert unlocked["moves"] == []

    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=th)
    preview = client.get(f"/api/v1/bands/promote/{exam['id']}", headers=th).json()
    assert preview["blocked"] is None
    assert preview["subject_name"] == "Hindi" and preview["roster"] == 3
    assert preview["sat"] == 2 and preview["not_sat"] == 1
    # The size is shown and a small test WARNS (`S-184`).
    assert any("small basis" in w for w in preview["warnings"])
    moves = {r["full_name"]: r for r in preview["moves"]}
    assert moves["Kabir Shah"]["from_tier"] == "C" and moves["Kabir Shah"]["to_tier"] == "A"
    # The down-move is what the review step exists to make somebody read.
    assert moves["Diya Nair"]["direction"] == "down"
    assert preview["moves"][0]["direction"] == "down"     # down-moves first
    assert "Aarav" not in moves                            # didn't sit it → unchanged

    # `Q-81`: the preview commits NOTHING.
    assert client.get(f"/api/v1/students/{kabir['id']}/growth",
                      headers=h).json()["band"] == "C · Hindi"

    done = client.post(f"/api/v1/bands/promote/{exam['id']}", headers=th).json()
    assert done["applied"] == 2 and done["already_promoted"] is True
    after = {sid: c for sid, c in client.get(
        "/api/v1/assessments/bands/current", headers=h).json().items()}
    # `S-187`: one subject. Hindi moved; Maths did not.
    assert after[kabir["id"]] == "C · Mathematics"     # Hindi A now, Maths still C
    assert after[diya["id"]] == "C · Hindi"            # slipped, and it shows
    assert after[aarav["id"]] == "C · Mathematics"     # untouched by this test

    # `S-182`: a flag, never a type change — it is still a slip test everywhere.
    assert client.get(f"/api/v1/assessments/exams/{exam['id']}",
                      headers=h).json()["type"] == "slip_test"


def test_an_unmonitored_subject_has_no_programme(client, cleanup):
    h, th, ctx = _setup(client, cleanup)
    science = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": science["id"], "periods_per_week": 3})
    exam = _locked_exam(client, h, ctx, science, [9, 4, 2])
    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=th)
    preview = client.get(f"/api/v1/bands/promote/{exam['id']}", headers=th).json()
    assert preview["blocked"] and "not part of the support programme" in preview["blocked"]


# ── D-87 / S-164: the weekly check-in, opening already written ───────────────
def test_the_child_page_opens_already_written_and_the_check_in_appends(client, cleanup):
    h, th, ctx = _setup(client, cleanup)
    kabir = ctx["kids"][0]
    _file(client, h, ctx, ctx["hindi"], ["C", "A", "A"])
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "term_id": ctx["term_id"],
        "exit_criterion": "reads a grade-level passage at 60 wpm, twice running"})
    plan = client.get("/api/v1/bands/support", headers=th).json()["groups"][0]["rows"][0]

    # Something another teacher recorded this week, with nobody typing it twice.
    cs_id = _cs_id(client, h, ctx, ctx["hindi"])
    hw = client.post("/api/v1/classroom/homework", headers=th, json={
        "class_subject_id": cs_id, "date": date.today().isoformat(),
        "text": "Ex 4.2"}).json()
    client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=th, json={
        "results": [{"student_id": kabir["id"], "status": "not_done"}]})

    child = client.get(f"/api/v1/bands/support/{plan['intervention_id']}", headers=th)
    assert child.status_code == 200, child.text
    child = child.json()
    # `S-167`: the exit criterion is on the screen from day one.
    assert "60 wpm" in child["headline"]
    assert "Band C in Hindi" in child["headline"]
    # `S-164`: his week, already recorded.
    assert any("Ex 4.2" in row["text"] for row in child["week"])
    assert child["checkpoints"] == []
    # `S-166`: the descriptors ride along, so the letter is never alone.
    assert {d["tier"] for d in child["descriptors"]} == {"A", "B", "C"}

    saved = client.post(f"/api/v1/bands/support/{plan['intervention_id']}/check-in",
                        headers=th, json={
                            "worked_on": "flashcards, 10 min daily",
                            "what_changed": "read a full paragraph unaided",
                            "next_step": "move to the Ch 5 passage",
                            "ready_to_retest": True}).json()
    assert len(saved["checkpoints"]) == 1
    assert saved["checkpoints"][0]["ready_to_retest"] is True

    mine = client.get("/api/v1/bands/support", headers=th).json()
    row = mine["groups"][0]["rows"][0]
    assert row["checked_in_this_week"] is True and row["ready_to_retest"] is True
    assert "All 1 checked in" in mine["headline"] or "checked in this week" in mine["headline"]
    # She proposes readiness; the band still moves on a test (`D-76`).
    assert client.get(f"/api/v1/students/{kabir['id']}/growth",
                      headers=h).json()["band"] == "C · Hindi"


def test_another_teachers_child_is_not_hers(client, cleanup):
    h, th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "A", "A"])
    # Owned by the admin, not the teacher.
    admin_member = next(x for x in client.get("/api/v1/org/members", headers=h).json()["members"]
                        if x["member_id"] != ctx["teacher_member"])["member_id"]
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": ctx["kids"][0]["id"], "subject_id": ctx["hindi"]["id"],
        "term_id": ctx["term_id"], "member_id": admin_member})
    iv = client.get(f"/api/v1/assessments/students/{ctx['kids'][0]['id']}/interventions",
                    headers=h).json()[0]
    assert client.get(f"/api/v1/bands/support/{iv['id']}", headers=th).status_code == 403
    assert client.get("/api/v1/bands/support", headers=th).json()["groups"] == []


# ── D-73 / S-169 / S-188: the admin's board ──────────────────────────────────
def test_the_programme_board_leads_with_movement_and_names_the_subject(client, cleanup):
    h, th, ctx = _setup(client, cleanup)
    _file(client, h, ctx, ctx["hindi"], ["C", "C", "B"])
    _file(client, h, ctx, ctx["maths"], ["B", "B", "B"])
    kabir = ctx["kids"][0]
    client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": kabir["id"], "subject_id": ctx["hindi"]["id"],
        "term_id": ctx["term_id"]})

    board = client.get("/api/v1/bands/programme", headers=h)
    assert board.status_code == 200, board.text
    board = board.json()
    assert "Band C" in board["headline"] or "moved up" in board["headline"]
    # `S-188`: every row about a child names the subject, because a child can
    # have two owners and each would otherwise assume the other is on it.
    stuck = {(r["full_name"], r["subject_name"]) for r in board["stuck"]}
    assert ("Kabir Shah", "Hindi") in stuck
    assert all(r["subject_name"] for r in board["stuck"])
    kabir_row = next(r for r in board["stuck"] if r["student_id"] == kabir["id"])
    assert kabir_row["owner_name"]                  # named, not "—"
    diya_row = next(r for r in board["stuck"] if r["student_id"] == ctx["kids"][1]["id"])
    assert diya_row["owner_name"] is None           # the row that needs an admin

    # Now move one child up on a locked test and the headline changes.
    exam = _locked_exam(client, h, ctx, ctx["hindi"], [9, None, None])
    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=th)
    client.post(f"/api/v1/bands/promote/{exam['id']}", headers=th)
    after = client.get("/api/v1/bands/programme", headers=h).json()
    assert after["moved_up"] == 1
    assert "1 child moved up this term" in after["headline"]
    cell = next(c for c in after["grid"] if c["subject_name"] == "Hindi")
    assert cell["moved_up"] == 1 and cell["class_label"] == "6-B"
    # A subject nobody assessed is a WORD, never a zero and never red.
    assert isinstance(after["not_assessed"], list)
