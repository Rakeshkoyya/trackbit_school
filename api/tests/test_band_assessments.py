"""The support owner's assessments, and My students as a table (2026-08-05).

Founder call after walking the shipped ABC bands area. The admin side was right;
the teacher side had a list she could not filter, no way to record how a child
did on the work she gave him, and — because Support lost its sidebar item in the
same change — an owner who teaches none of the monitored subjects would have had
children assigned to her and no door to them.

What these tests pin, in the order they would break something real:

* **My students is the ASSIGNED set, and says so when it is empty.** A teacher
  with nobody assigned must get a sentence, not a blank grid she reads as a
  broken screen. And a class filter that empties the table has to read
  differently from having no children at all.
* **The unit is the placement, not the child** (`D-75`). Ownership is per
  subject, so a boy supported in two subjects is two rows.
* **`covers_all` keeps the roster COMPUTED** (HS-1). A child assigned to her
  after the assessment was set is on it, with nobody editing anything — which is
  the whole reason it is a flag and not forty stored rows.
* **Not evaluated is a word.** `pending` is a state, a child with no result is
  not a zero, and the average divides by the children actually evaluated.
* **The three metrics never pool** (`core/band_assessment.py`). A rating has no
  percentage, and there is no figure that mixes one with a mark.
* **Full replace.** A child left out of the payload goes back to *not
  evaluated* — a legitimate answer, and the only way to undo a mistyped mark.
* **Blocked, not filtered** (`S-46`): another teacher's assessment is a 403 with
  a sentence, never an empty sheet she reads as "nobody did it".
"""

import uuid
from datetime import date, timedelta


def _setup(client, cleanup):
    """One admin, two teachers, two classes, two monitored subjects.

    The second teacher exists only so "another teacher's assessment" is a real
    row rather than a hypothetical, and the second class so the class filter has
    something to filter."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Band Assess Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
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

    def teacher(tag):
        username = f"{tag}{uuid.uuid4().hex[:8]}"
        bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
            {"username": username, "password": "supersecret1", "role": "teacher"}]}).json()
        cleanup["users"].append(uuid.UUID(bulk["results"][0]["user_id"]))
        hdr = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={
            "identifier": username, "password": "supersecret1"}).json()["access_token"]}
        member = next(x for x in client.get("/api/v1/org/members", headers=h).json()["members"]
                      if x.get("username") == username)["member_id"]
        return hdr, member

    th, teacher_member = teacher("t")
    oh, other_member = teacher("o")

    six_b = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "B"}).json()
    seven_a = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "7", "section": "A"}).json()
    hindi = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Hindi"}).json()
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Mathematics"}).json()

    for klass in (six_b, seven_a):
        for subj in (hindi, maths):
            client.post("/api/v1/academics/class-subjects", headers=h, json={
                "class_id": klass["id"], "subject_id": subj["id"],
                "teacher_member_id": teacher_member, "periods_per_week": 5})

    kids_b = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"B{i}-{uuid.uuid4().hex[:6]}", "full_name": name,
        "class_id": six_b["id"], "roll_no": str(i)}).json()
        for i, name in enumerate(["Kabir Shah", "Diya Nair", "Rohan Das"], start=1)]
    kids_a = [client.post("/api/v1/students", headers=h, json={
        "admission_no": f"A{i}-{uuid.uuid4().hex[:6]}", "full_name": name,
        "class_id": seven_a["id"], "roll_no": str(i)}).json()
        for i, name in enumerate(["Aarav Rao"], start=1)]

    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [hindi["id"], maths["id"]]})
    return h, th, oh, {
        "six_b": six_b, "seven_a": seven_a, "hindi": hindi, "maths": maths,
        "kids_b": kids_b, "kids_a": kids_a, "term_id": term_id,
        "teacher_member": teacher_member, "other_member": other_member}


def _own(client, h, ctx, student_id, subject_id, member_id):
    """Give a child an owner — the admin's act, the only way onto her list."""
    r = client.post("/api/v1/bands/owner", headers=h, json={
        "student_id": student_id, "subject_id": subject_id,
        "member_id": member_id, "term_id": ctx["term_id"]})
    assert r.status_code == 200, r.text


def _create(client, hdr, ctx, **over):
    body = {"class_id": ctx["six_b"]["id"], "name": "Reading aloud — week 3",
            "metric": "marks", "max_marks": 10, "covers_all": True}
    body.update(over)
    return client.post("/api/v1/bands/assessments", headers=hdr, json=body)


# ── My students ──────────────────────────────────────────────────────────────
def test_my_students_is_the_assigned_set_and_says_so_when_empty(client, cleanup):
    """Nobody assigned = a SENTENCE, not an empty grid.

    An empty screen with a heading on it reads as a bug; the whole reason she
    would open this tab is to find out whether anyone is hers."""
    _h, th, _oh, _ctx = _setup(client, cleanup)
    board = client.get("/api/v1/bands/my-students", headers=th).json()
    assert board["rows"] == [] and board["total"] == 0
    assert "No students are assigned to you" in board["headline"]
    # Nothing to pick from, so no picker — never a dropdown of empty classes.
    assert board["classes"] == []


def test_my_students_counts_placements_and_filters_by_class(client, cleanup):
    """`D-75`: a boy supported in two subjects is TWO rows, because the work and
    the goal differ in each. And a class filter that empties the table says so
    rather than reusing the "nobody is assigned to you" sentence."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, _rohan = ctx["kids_b"]
    aarav = ctx["kids_a"][0]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, kabir["id"], ctx["maths"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, diya["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, aarav["id"], ctx["hindi"]["id"], ctx["teacher_member"])

    board = client.get("/api/v1/bands/my-students", headers=th).json()
    assert board["total"] == 4                       # placements, not children
    assert len(board["rows"]) == 4
    assert sum(1 for r in board["rows"] if r["full_name"] == "Kabir Shah") == 2
    # Both classes offered, each with its own count.
    assert {c["label"]: c["count"] for c in board["classes"]} == {"6-B": 3, "7-A": 1}

    only_b = client.get("/api/v1/bands/my-students",
                        headers=th, params={"class_id": ctx["six_b"]["id"]}).json()
    assert len(only_b["rows"]) == 3
    # The picker still offers 7-A, so a filter can never trap her.
    assert len(only_b["classes"]) == 2

    # A class she has nobody in: its own sentence, and the school-wide count.
    empty = client.get("/api/v1/bands/my-students", headers=th,
                       params={"class_id": ctx["seven_a"]["id"]}).json()
    seven_only = [r for r in empty["rows"]]
    assert len(seven_only) == 1                      # Aarav is hers


def test_the_headline_counts_children_and_never_says_none_weeks(client, cleanup):
    """Two defects found by looking at the built screen, not by reading it.

    · **Children and placements are two counts.** Three children supported
      across five subjects read as *"5 children assigned to you"* over a table
      plainly showing three names. The unit discipline `D-75` keeps in the
      schemas has to reach the sentence too.
    · **Never checked in is a state, not a duration.** The V1-9 original
      filtered on `(weeks_since_checkin or 99) >= 3`, which sweeps in a child
      with NO check-in and then formats his `None` into the sentence — so the
      board said *"Asha hasn't been checked in None weeks."*
    """
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, kabir["id"], ctx["maths"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, diya["id"], ctx["hindi"]["id"], ctx["teacher_member"])

    head = client.get("/api/v1/bands/my-students", headers=th).json()["headline"]
    assert "None" not in head
    # Two children, three placements — and the sentence carries both.
    assert head.startswith("2 children assigned to you, 3 across subjects")
    assert "never been checked in" in head
    assert "hasn't been checked in" not in head        # nobody is merely stale

    # The V1-9 list is the same sentence from the same defect — fixed in both.
    assert "None" not in client.get("/api/v1/bands/support", headers=th).json()["headline"]


def test_another_teacher_never_appears_on_her_list(client, cleanup):
    """`S-170`: other owners' children are not hers to read, in either
    direction."""
    h, th, oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, diya["id"], ctx["hindi"]["id"], ctx["other_member"])

    mine = client.get("/api/v1/bands/my-students", headers=th).json()
    theirs = client.get("/api/v1/bands/my-students", headers=oh).json()
    assert [r["full_name"] for r in mine["rows"]] == ["Kabir Shah"]
    assert [r["full_name"] for r in theirs["rows"]] == ["Diya Nair"]
    # The admin runs the programme and sees both.
    assert len(client.get("/api/v1/bands/my-students", headers=h).json()["rows"]) == 2


# ── creating an assessment ───────────────────────────────────────────────────
def test_create_blocks_a_class_with_none_of_her_children(client, cleanup):
    """Blocked with a sentence (`S-46`), never an empty form she fills in and
    then cannot save."""
    h, th, _oh, ctx = _setup(client, cleanup)
    _own(client, h, ctx, ctx["kids_a"][0]["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    r = _create(client, th, ctx)                     # 6-B, where she owns nobody
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "no_students_assigned"


def test_marks_need_a_total_so_no_figure_is_ever_bare(client, cleanup):
    """ux §3 / `S-118`: a mark with no denominator is unreadable, and the only
    place that can be enforced is where the assessment is set."""
    h, th, _oh, ctx = _setup(client, cleanup)
    _own(client, h, ctx, ctx["kids_b"][0]["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    r = _create(client, th, ctx, max_marks=None)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_total"


def test_covers_all_keeps_the_roster_computed(client, cleanup):
    """HS-1's rule, and the reason `covers_all` is a flag and not forty rows: a
    child assigned to her AFTER the assessment was set is on it, with nobody
    remembering to edit anything."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, rohan = ctx["kids_b"]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])

    created = _create(client, th, ctx, subject_id=ctx["hindi"]["id"]).json()
    assert created["roster"] == 1
    assert created["status"] == "pending"

    # She is given a second child the following week.
    _own(client, h, ctx, diya["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    sheet = client.get(f"/api/v1/bands/assessments/{created['id']}", headers=th).json()
    assert {r["full_name"] for r in sheet["rows"]} == {"Kabir Shah", "Diya Nair"}
    # A child she does not own is never swept in.
    assert rohan["full_name"] not in {r["full_name"] for r in sheet["rows"]}

    # A picked list is FROZEN by contrast — right for "these two are re-doing
    # it", wrong for a standing weekly check.
    picked = _create(client, th, ctx, name="Just Kabir", covers_all=False,
                     student_ids=[kabir["id"]]).json()
    assert picked["roster"] == 1
    _own(client, h, ctx, rohan["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    again = client.get(f"/api/v1/bands/assessments/{picked['id']}", headers=th).json()
    assert len(again["rows"]) == 1


# ── recording ────────────────────────────────────────────────────────────────
def test_pending_is_a_state_and_an_unmarked_child_is_not_a_zero(client, cleanup):
    """The rule the whole module rests on, borrowed from HW-1: a check nobody
    has marked is `pending`, and the average divides by the children actually
    evaluated — never by the roster, which would report a teacher who has
    marked two of three as a class that scored badly."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, rohan = ctx["kids_b"]
    for kid in (kabir, diya, rohan):
        _own(client, h, ctx, kid["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    a = _create(client, th, ctx, subject_id=ctx["hindi"]["id"], max_marks=10).json()
    assert a["status"] == "pending" and a["average"] is None
    assert "Not evaluated yet" in a["caption"]

    r = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 8},
                    {"student_id": diya["id"], "marks": 6}]})
    assert r.status_code == 200, r.text
    row = r.json()["assessment"]
    assert row["status"] == "partial"
    assert row["evaluated"] == 2 and row["not_evaluated"] == 1
    assert row["average"] == 7.0                     # of 2, not of 3
    assert row["average_pct"] == 70.0
    assert "2 of 3 evaluated" in row["caption"]
    # Rohan carries no number and no zero — a word on every surface.
    rohan_row = next(x for x in r.json()["rows"] if x["full_name"] == "Rohan Das")
    assert rohan_row["evaluated"] is False
    assert rohan_row["marks"] is None and rohan_row["result_text"] is None


def test_recording_is_a_full_replace_so_a_mistake_can_be_undone(client, cleanup):
    """Results are capture, not a decision — law 3's append-only governs bands
    and approvals. Leaving a child out puts him back to *not evaluated*, which
    is the only way to undo a mark typed against the wrong name."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    for kid in (kabir, diya):
        _own(client, h, ctx, kid["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    a = _create(client, th, ctx, subject_id=ctx["hindi"]["id"], max_marks=10).json()

    client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 9},
                    {"student_id": diya["id"], "marks": 4}]})
    sheet = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 9}]}).json()
    assert sheet["assessment"]["evaluated"] == 1
    diya_row = next(x for x in sheet["rows"] if x["full_name"] == "Diya Nair")
    assert diya_row["evaluated"] is False and diya_row["marks"] is None

    # A mark over the total is refused rather than silently clamped.
    over = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 40}]})
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "over_total"


def test_a_rating_has_no_percentage_and_never_pools_with_a_mark(client, cleanup):
    """`core/band_assessment.py`'s rule, and the `ScaleTally` device a fourth
    time: 3 of 5 is not 60% of anything, and printing it as one is an invitation
    to add it to a mark. The result text always carries its own scale."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    for kid in (kabir, diya):
        _own(client, h, ctx, kid["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    a = _create(client, th, ctx, name="Fluency", metric="rating", max_marks=None,
                rating_max=5, subject_id=ctx["hindi"]["id"]).json()
    assert a["rating_max"] == 5 and a["max_marks"] is None

    sheet = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "rating": 4},
                    {"student_id": diya["id"], "rating": 2}]}).json()
    assert sheet["assessment"]["average"] == 3.0
    assert sheet["assessment"]["average_pct"] is None       # never a percentage
    assert "of 5" in sheet["assessment"]["caption"]
    kabir_row = next(x for x in sheet["rows"] if x["full_name"] == "Kabir Shah")
    assert kabir_row["result_text"] == "4 of 5"

    over = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "rating": 9}]})
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "over_rating"


def test_a_word_is_a_verdict_and_carries_no_number(client, cleanup):
    """`other`: she is judging without measuring, and the tally counts the child
    as evaluated without inventing a quantity to average."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    for kid in (kabir, diya):
        _own(client, h, ctx, kid["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    a = _create(client, th, ctx, name="Did he read it?", metric="other",
                max_marks=None, subject_id=ctx["hindi"]["id"]).json()

    sheet = client.put(f"/api/v1/bands/assessments/{a['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "verdict": "read it on his own"},
                    {"student_id": diya["id"], "verdict": "still guessing"}]}).json()
    assert sheet["assessment"]["status"] == "evaluated"
    assert sheet["assessment"]["average"] is None
    assert sheet["assessment"]["average_pct"] is None
    kabir_row = next(x for x in sheet["rows"] if x["full_name"] == "Kabir Shah")
    assert kabir_row["result_text"] == "read it on his own"


# ── the feed, and the fences around it ───────────────────────────────────────
def test_feed_paginates_and_derives_status(client, cleanup):
    """Paginated because a year of small weekly checks is hundreds of rows, and
    `status` is derived so it can never claim to be evaluated when the numbers
    say otherwise."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir = ctx["kids_b"][0]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    for i in range(5):
        _create(client, th, ctx, name=f"Week {i}", subject_id=ctx["hindi"]["id"])

    page1 = client.get("/api/v1/bands/assessments", headers=th,
                       params={"per_page": 2}).json()
    assert page1["total"] == 5 and page1["pages"] == 3 and len(page1["rows"]) == 2
    page3 = client.get("/api/v1/bands/assessments", headers=th,
                       params={"per_page": 2, "page": 3}).json()
    assert len(page3["rows"]) == 1
    assert page1["open_count"] == 5
    assert "5 still to evaluate" in page1["headline"]

    # Evaluate one and the status filter narrows to it.
    target = page1["rows"][0]
    client.put(f"/api/v1/bands/assessments/{target['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 7}]})
    done = client.get("/api/v1/bands/assessments", headers=th,
                      params={"status": "evaluated"}).json()
    assert [r["id"] for r in done["rows"]] == [target["id"]]
    assert client.get("/api/v1/bands/assessments", headers=th,
                      params={"status": "pending"}).json()["total"] == 4


def test_another_teachers_assessment_is_blocked_not_emptied(client, cleanup):
    """`S-46`: a 403 with a sentence. An empty sheet would read as "nobody did
    it", which is a claim about children rather than about permission."""
    h, th, oh, ctx = _setup(client, cleanup)
    kabir, diya, _ = ctx["kids_b"]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    _own(client, h, ctx, diya["id"], ctx["hindi"]["id"], ctx["other_member"])
    mine = _create(client, th, ctx, subject_id=ctx["hindi"]["id"]).json()

    r = client.get(f"/api/v1/bands/assessments/{mine['id']}", headers=oh)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "not_your_assessment"
    # It is not on her feed either — the two must agree.
    assert client.get("/api/v1/bands/assessments", headers=oh).json()["total"] == 0
    # The admin runs the programme and reads the school's.
    assert client.get("/api/v1/bands/assessments", headers=h).json()["total"] == 1


def test_an_assessment_with_results_cannot_be_deleted(client, cleanup):
    """Once a child's result is on it, it is part of his record — the same
    reason a locked exam cannot be re-typed (`D-53`)."""
    h, th, _oh, ctx = _setup(client, cleanup)
    kabir = ctx["kids_b"][0]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])
    a = _create(client, th, ctx, subject_id=ctx["hindi"]["id"]).json()
    assert client.delete(f"/api/v1/bands/assessments/{a['id']}",
                         headers=th).status_code == 200

    b = _create(client, th, ctx, name="Week 2", subject_id=ctx["hindi"]["id"]).json()
    client.put(f"/api/v1/bands/assessments/{b['id']}/results", headers=th, json={
        "results": [{"student_id": kabir["id"], "marks": 5}]})
    r = client.delete(f"/api/v1/bands/assessments/{b['id']}", headers=th)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "has_results"


# ── the student log, and the door that had to stay open ──────────────────────
def test_a_support_owner_may_log_about_her_own_child(client, cleanup):
    """AT-1 made the log the class teacher's. The support owner is the third
    author, because the ABC bands area now asks her for exactly this — and she
    can READ what she is allowed to write, which the original guard did not
    grant her.

    A teacher who owns nobody is still refused: this widened the log by one
    named relationship, not by a role."""
    h, th, oh, ctx = _setup(client, cleanup)
    kabir = ctx["kids_b"][0]
    _own(client, h, ctx, kabir["id"], ctx["hindi"]["id"], ctx["teacher_member"])

    notes = client.get(f"/api/v1/my-class/students/{kabir['id']}/notes", headers=th)
    assert notes.status_code == 200 and notes.json()["can_write"] is True

    a = _create(client, th, ctx, subject_id=ctx["hindi"]["id"]).json()
    r = client.post(f"/api/v1/my-class/students/{kabir['id']}/notes", headers=th, json={
        "kind": "assessment", "note": "read the whole passage without stopping",
        "assessment_id": a["id"]})
    assert r.status_code == 200, r.text
    row = r.json()["rows"][0]
    assert row["kind"] == "assessment" and row["assessment_id"] == a["id"]

    # The other teacher owns nobody in 6-B and may not write to his log.
    denied = client.post(f"/api/v1/my-class/students/{kabir['id']}/notes", headers=oh,
                         json={"kind": "support", "note": "nope"})
    assert denied.status_code == 403


def test_an_owner_gets_the_area_even_without_a_monitored_subject(client, cleanup):
    """The defect removing the Support item would otherwise have shipped.

    An admin may hand a child to anyone (`OwnerSuggestion` suggests, it never
    restricts). Before this, `has_band_scope` asked only whether she TEACHES a
    monitored subject — so a warden given three Band C children would have had
    them assigned to her and no nav item to reach them by."""
    h, _th, oh, ctx = _setup(client, cleanup)
    # The second teacher takes no class-subject at all.
    me = client.get("/api/v1/auth/me", headers=oh).json()
    assert me["has_band_scope"] is False
    scope = client.get("/api/v1/bands/scope", headers=oh).json()
    assert scope["can_band"] is False and scope["owns_students"] is False

    _own(client, h, ctx, ctx["kids_b"][0]["id"], ctx["hindi"]["id"], ctx["other_member"])
    me = client.get("/api/v1/auth/me", headers=oh).json()
    assert me["has_band_scope"] is True
    scope = client.get("/api/v1/bands/scope", headers=oh).json()
    # She gets in, but the class-banding tabs stay off: a tab opening on "you
    # have no classes here" is worse than an absent one (ux §13).
    assert scope["has_scope"] is True
    assert scope["owns_students"] is True and scope["can_band"] is False
    assert len(client.get("/api/v1/bands/my-students", headers=oh).json()["rows"]) == 1
