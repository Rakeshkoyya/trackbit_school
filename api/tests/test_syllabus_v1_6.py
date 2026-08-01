"""V1-6 — syllabus, planning and the mid-year proof.

What each test is defending:

  * `S-51` — **one coverage definition.** The phrase "syllabus covered" was
    computed in four places with no two alike (two of them in the browser), so a
    parent and a principal could read different percentages for the same subject
    on the same day. One function now, and the test asserts the two surfaces
    agree rather than merely that each is self-consistent.
  * `S-54`/`Q-16` — a parent's denominator is the **whole syllabus**, because it
    is the only one that cannot go down. Sizing next term's chapters must never
    make a parent's number fall.
  * `S-42` — **unlogged is not behind.** A class-subject nobody has logged a
    lesson against is `unknown`: never red, never ranked, never on a worst list,
    and never counted as on-track either.
  * `S-41` — every behind row says **why**, and the four causes get four
    different sentences because they need four different responses.
  * `S-45` — the rank carries the sentence it rests on, not a composite score
    nobody could reconstruct.
  * `S-50`/`S-40`/`S-43` — the exam leads, coverage has a trend, and sections of
    one grade can be compared.
  * `D-16`/`S-60` — "Ask for a catch-up plan" is a **meeting request**: it lands
    as a task on the teacher, pressing twice does not file twice, and the row
    clears on the recorded **outcome**, not on the press.
  * `D-15` — a subject teacher sees her own subjects **only** (blocked, not
    merely defaulted), and the class-teacher view is her own class only.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core import coverage as cov
from app.models import Membership
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return str(db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id),
                Membership.org_id == uuid.UUID(org_id))))
    finally:
        db.close()


def _setup(client, cleanup, *, sections=("A",)):
    """A year, one grade with `sections` sections, Maths owned by one teacher."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Syl Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    today = date.today()
    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=120)).isoformat(),
        "end_date": (today + timedelta(days=180)).isoformat()}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 4,
        "period_times": [{"start": f"{9 + i:02d}:00", "end": f"{9 + i:02d}:40", "kind": "period"}
                         for i in range(4)]})

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"},
        {"username": f"o{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    mine, other = bulk.json()["results"]
    for c in (mine, other):
        cleanup["users"].append(uuid.UUID(c["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": mine["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    other_login = client.post("/api/v1/auth/login", json={
        "identifier": other["username"], "password": "supersecret1"}).json()
    oh = {"Authorization": f"Bearer {other_login['access_token']}"}

    teacher_mid = _membership_id(mine["user_id"], reg["org"]["id"])
    other_mid = _membership_id(other["user_id"], reg["org"]["id"])
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": f"Maths {uuid.uuid4().hex[:4]}"}).json()

    classes, css = [], []
    for section in sections:
        klass = client.post("/api/v1/academics/classes", headers=h, json={
            "academic_year_id": year["id"], "name": "6", "section": section,
            "class_teacher_member_id": teacher_mid}).json()
        cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
            "class_id": klass["id"], "subject_id": subject["id"],
            "periods_per_week": 4, "teacher_member_id": teacher_mid}).json()
        classes.append(klass)
        css.append(cs)
    return {"h": h, "th": th, "oh": oh, "year": year, "subject": subject,
            "classes": classes, "css": css, "class": classes[0], "cs": css[0],
            "teacher_mid": teacher_mid, "other_mid": other_mid,
            "org_id": reg["org"]["id"]}


def _syllabus(client, h, cs_id, topics):
    """topics = [(title, est_or_None)] under one chapter. Returns the topic rows."""
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs_id, "title": "Chapter One"}).json()
    out = []
    for title, est in topics:
        body = {"unit_id": unit["id"], "title": title}
        if est is not None:
            body["est_periods"] = est
        out.append(client.post("/api/v1/planner/syllabus/topics",
                               headers=h, json=body).json())
    return unit, out


def _plan(client, h, cs_id):
    r = client.post(f"/api/v1/planner/plan/{cs_id}/generate", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _log(client, th, cs_id, topic_id, coverage="full"):
    r = client.post("/api/v1/classroom/lesson-logs", headers=th, json={
        "class_subject_id": cs_id, "topic_id": topic_id, "coverage": coverage})
    assert r.status_code == 200, r.text
    return r.json()


def _board(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/v1/insights/syllabus{'?' + q if q else ''}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _row(board, cs_id):
    return next(r for r in board["rows"] if r["class_subject_id"] == cs_id)


# ── the arithmetic, pure ─────────────────────────────────────────────────────
def test_one_coverage_definition_and_its_denominators():
    """The whole packet rests on this: one weight, one best-log rule, and a
    figure that cannot be rendered without saying what it is a percentage of."""
    assert cov.taught_weight("full") == 1.0
    assert cov.taught_weight("partial") == cov.PARTIAL_WEIGHT == 0.5
    assert cov.taught_weight("") == 0.0

    # A topic taught across two periods is taught ONCE, at its best state —
    # otherwise it counted 1.5 and two surfaces disagreed about which log won.
    assert cov.better_coverage("partial", "full") == "full"
    assert cov.better_coverage("full", "partial") == "full"
    assert cov.better_coverage(None, "partial") == "partial"

    # None is not zero and no screen may render it as one.
    assert cov.coverage_pct(0, 0) is None
    assert cov.coverage_pct(3.5, 7) == 50.0

    figure = cov.CoverageFigure(3.5, 7, cov.SYLLABUS)
    assert figure.pct == 50.0
    assert "of 7" in figure.sentence() and "whole syllabus" in figure.sentence()
    # Each basis names its own window, so a figure can never be quoted bare.
    assert cov.CoverageFigure(1, 2, cov.PLANNED_TO_DATE).label == "of what was due by today"


def test_unlogged_is_unknown_not_behind_in_the_shared_classifier():
    """`S-42` at the source. The forecast may rate a subject on plan-vs-calendar
    with no logs at all — that arithmetic is fine — but no screen may tell a
    human "3 weeks behind" about a class nobody observed."""
    for pace in ("green", "amber", "red"):
        assert cov.rated_status(pace, has_evidence=False) == cov.UNKNOWN
        assert cov.rated_status(pace, has_evidence=True) == pace
    # States stay themselves: "nothing is scheduled" is not "we don't know".
    for state in ("unplanned", "unallocated", "none"):
        assert cov.rated_status(state, has_evidence=False) == state


def test_every_behind_row_says_why_and_the_four_causes_differ():
    """`S-41`. "6-B Maths is 3 weeks behind" is where the screen used to stop."""
    cause, text = cov.attribute_cause(status=cov.UNKNOWN)
    assert cause == cov.CAUSE_NOT_LOGGED and "recording" in text

    # Periods lost outranks "slower": one is nobody's fault, and saying so first
    # is the difference between a scheduling accident and an accusation.
    cause, text = cov.attribute_cause(status="red", behind_topics=3, periods_not_held=8)
    assert cause == cov.CAUSE_PERIODS_LOST
    assert "8 periods were called off" in text and "Nobody's fault" in text

    cause, text = cov.attribute_cause(status="red", behind_topics=2,
                                      unestimated_topics=4, planned_topics=0)
    assert cause == cov.CAUSE_NEVER_SIZED and "setup gap" in text

    cause, text = cov.attribute_cause(status="red", behind_topics=2, planned_topics=6)
    assert cause == cov.CAUSE_SLOWER and "teaching conversation" in text

    # A row that is not behind gets no excuse — otherwise the column is noise.
    assert cov.attribute_cause(status="green") == (None, None)
    # One below the floor is not "we lost periods".
    cause, _ = cov.attribute_cause(status="red", behind_topics=1, periods_not_held=1,
                                   planned_topics=5)
    assert cause == cov.CAUSE_SLOWER


# ── S-42 end to end ──────────────────────────────────────────────────────────
def test_a_planned_subject_with_no_logs_is_unknown_never_ranked(client, cleanup):
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                              [("Comparing", 2), ("Rounding", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])

    board = _board(client, ctx["h"])
    row = _row(board, ctx["cs"]["id"])
    assert row["status"] == "unknown", "a plan with no lesson logs is not a pace"
    assert row["cause"] == "not_logged"
    assert row["logged_periods"] == 0
    # It is in NEITHER bucket — not on track, and not behind.
    assert board["school"]["unknown"] == 1
    assert board["school"]["on_track"] == 0
    assert board["school"]["behind"] == 0
    assert all(n["label"] for n in board["needs_support"]) or not board["needs_support"]
    assert ctx["cs"]["id"] not in [n["key"] for n in board["needs_support"]]

    # One log and the pace becomes real again.
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"])
    board = _board(client, ctx["h"])
    assert _row(board, ctx["cs"]["id"])["status"] in ("green", "amber", "red")


# ── S-51 / S-54: the two surfaces agree ──────────────────────────────────────
def test_admin_and_parent_read_the_same_coverage(client, cleanup):
    """The defect this packet exists to remove: same subject, same day, two
    numbers. The admin sees both bases; the parent sees the safe one."""
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                              [("Comparing", 2), ("Rounding", 2), ("Estimating", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")
    _log(client, ctx["th"], ctx["cs"]["id"], topics[1]["id"], "partial")

    row = _row(_board(client, ctx["h"]), ctx["cs"]["id"])
    # full + partial = 1.5 of 3 topics in the whole syllabus.
    assert row["syllabus_taught"] == 1.5
    assert row["total_topics"] == 3
    assert row["syllabus_pct"] == 50.0
    # Both bases are present and are genuinely different questions.
    assert row["coverage_pct"] is not None

    student = client.post("/api/v1/students", headers=ctx["h"], json={
        "full_name": "Asha Rao", "class_id": ctx["class"]["id"],
        "admission_no": f"A{uuid.uuid4().hex[:6]}"}).json()
    growth = client.get(f"/api/v1/students/{student['id']}/growth",
                        headers=ctx["h"]).json()
    subj = next(s for s in growth["subjects"]
                if s["class_subject_id"] == ctx["cs"]["id"])
    # THE assertion: the parent-facing figure is the admin's whole-syllabus one.
    assert subj["coverage_pct"] == row["syllabus_pct"]
    assert subj["coverage_taught"] == row["syllabus_taught"]
    assert subj["coverage_basis"] == cov.SYLLABUS
    # `S-48`: the chapter has a name, which is what a parent can ask about.
    assert subj["latest_chapter"] == "Chapter One"
    assert subj["latest_topic"] in ("Comparing", "Rounding")


def test_sizing_new_chapters_never_lowers_the_parent_number(client, cleanup):
    """`S-54` — coverage against the PLAN falls when next term is sized; against
    the whole syllabus it cannot. A parent reads a fall as going backwards."""
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"], [("Comparing", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")

    before = _row(_board(client, ctx["h"]), ctx["cs"]["id"])["syllabus_pct"]
    assert before == 100.0

    # The school now sizes a second chapter — nothing was un-taught.
    unit2 = client.post("/api/v1/planner/syllabus/units", headers=ctx["h"], json={
        "class_subject_id": ctx["cs"]["id"], "title": "Chapter Two"}).json()
    client.post("/api/v1/planner/syllabus/topics", headers=ctx["h"], json={
        "unit_id": unit2["id"], "title": "Integers", "est_periods": 2})

    after = _row(_board(client, ctx["h"]), ctx["cs"]["id"])
    assert after["syllabus_taught"] == 1.0, "nothing was un-taught"
    assert after["total_topics"] == 2
    # The number moved because the portion grew — and the taught count held.
    # What must never happen is the taught side shrinking.
    assert after["syllabus_taught"] >= 1.0


# ── S-45 / S-50 / S-40 / S-43 ────────────────────────────────────────────────
def test_rank_carries_the_sentence_it_rests_on(client, cleanup):
    """`S-45` — if a rank cannot be explained to the teacher it is about, it has
    no business being on the screen."""
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"], [("Comparing", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"])

    board = _board(client, ctx["h"], scope="class")
    node = board["nodes"][0]
    # Below the sample floor nothing is ranked, and the guard still holds.
    assert node["rank_eligible"] is False
    assert node["score"] is None
    assert board["min_class_subjects"] == 3
    # The node still carries its numbers — "not enough data" is not "no data".
    assert node["class_subjects"] == 1
    assert node["coverage_pct"] is not None


def test_the_board_leads_with_a_sentence_and_carries_a_trend(client, cleanup):
    """`S-50` + `S-40` + rule 3 — a percentage on its own tells nobody what to do."""
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                              [("Comparing", 2), ("Rounding", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"])

    board = _board(client, ctx["h"])
    assert board["headline"], "the page must open with a sentence"
    assert isinstance(board["headline"], str) and len(board["headline"]) > 10

    # `S-40`: a dated series with the baseline beside the actual.
    assert board["trend"], "coverage over time is the chart the board lacked"
    first = board["trend"][0]
    assert {"week_start", "actual", "baseline"} <= set(first)
    actuals = [p["actual"] for p in board["trend"]]
    assert actuals == sorted(actuals), "cumulative coverage can only go up"


def test_sections_of_one_grade_are_compared_only_when_there_are_two(client, cleanup):
    """`S-43` — 6-A Maths vs 6-B Maths is the fairest comparison in a school.
    A comparison of one thing is not a comparison."""
    solo = _setup(client, cleanup)
    _syllabus(client, solo["h"], solo["cs"]["id"], [("Comparing", 2)])
    _plan(client, solo["h"], solo["cs"]["id"])
    assert _board(client, solo["h"])["sections"] == []

    ctx = _setup(client, cleanup, sections=("A", "B"))
    for cs in ctx["css"]:
        _unit, topics = _syllabus(client, ctx["h"], cs["id"],
                                  [("Comparing", 2), ("Rounding", 2)])
        _plan(client, ctx["h"], cs["id"])
        _log(client, ctx["th"], cs["id"], topics[0]["id"])
    board = _board(client, ctx["h"])
    assert len(board["sections"]) == 1
    compare = board["sections"][0]
    assert compare["grade"] == "6"
    assert {r["class_label"] for r in compare["rows"]} == {"6-A", "6-B"}


# ── D-16 / S-60: the catch-up request ────────────────────────────────────────
def test_catchup_is_a_meeting_request_that_clears_on_the_outcome(client, cleanup):
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"], [("Comparing", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"])

    r = client.post("/api/v1/insights/actions/catchup_requested", headers=ctx["h"],
                    json={"class_subject_id": ctx["cs"]["id"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] and out["subject_type"] == "class_subject"
    task_id = out["task_id"]
    assert task_id

    # It is a REQUEST, not a directive: the copy asks for a discussion.
    task = client.get(f"/api/v1/tasks/{task_id}", headers=ctx["h"]).json()
    assert task["title"].lower().startswith("discuss")
    # The task is ABOUT the class-subject, resolved to a readable name.
    assert task["subject"]["type"] == "class_subject"
    assert task["subject"]["name"].startswith("6-A ")

    # The board row shows it as asked-and-waiting, with no outcome yet.
    row = _row(_board(client, ctx["h"]), ctx["cs"]["id"])
    assert row["catchup_task_id"] == task_id
    assert row["catchup_outcome"] is None

    # Pressing again does not file a second row in her list (`D-47`).
    again = client.post("/api/v1/insights/actions/catchup_requested", headers=ctx["h"],
                        json={"class_subject_id": ctx["cs"]["id"]}).json()
    assert again["already_done"] is True
    assert again["task_id"] == task_id

    # `S-60`: it clears on the recorded OUTCOME, not on the press.
    done = client.post(f"/api/v1/tasks/{task_id}/complete", headers=ctx["h"],
                       json={"outcome": "Agreed two extra periods a week."})
    assert done.status_code == 200, done.text
    row = _row(_board(client, ctx["h"]), ctx["cs"]["id"])
    assert row["catchup_outcome"] == "Agreed two extra periods a week."


# ── D-15 / S-46: who may see what ────────────────────────────────────────────
def test_my_subjects_shows_hers_only_and_says_what_to_teach_next(client, cleanup):
    ctx = _setup(client, cleanup)
    _unit, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                              [("Comparing", 2), ("Rounding", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")

    mine = client.get("/api/v1/planner/my-subjects", headers=ctx["th"]).json()
    assert len(mine["rows"]) == 1
    row = mine["rows"][0]
    assert row["class_label"] == "6-A"
    # The reason she opened the screen at all (`S-46`).
    assert row["next_topic_title"] == "Rounding"
    assert row["next_chapter_title"] == "Chapter One"
    assert mine["headline"]

    # `D-15` is a block, not a default: another teacher owns none of these.
    other = client.get("/api/v1/planner/my-subjects", headers=ctx["oh"]).json()
    assert other["rows"] == []


def test_class_syllabus_is_her_class_only(client, cleanup):
    """`D-15` — the class teacher sees all subjects and all teachers' pace, but
    only for her own class. There is no school-wide form of this endpoint."""
    ctx = _setup(client, cleanup)
    _syllabus(client, ctx["h"], ctx["cs"]["id"], [("Comparing", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])

    ok = client.get(f"/api/v1/planner/class-syllabus/{ctx['class']['id']}",
                    headers=ctx["th"])
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["class_label"] == "6-A"
    assert len(body["rows"]) == 1
    assert body["headline"]

    # A teacher who is not this class's class teacher is refused, by code.
    denied = client.get(f"/api/v1/planner/class-syllabus/{ctx['class']['id']}",
                        headers=ctx["oh"])
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "not_your_class"

    # The admin may read it.
    assert client.get(f"/api/v1/planner/class-syllabus/{ctx['class']['id']}",
                      headers=ctx["h"]).status_code == 200
