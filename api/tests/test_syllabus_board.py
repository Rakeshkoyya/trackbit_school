"""SY-1 — the syllabus board, the frozen baseline, and set-shaped exam portions.

What each test is defending:

  * **The baseline is frozen at approval.** This is the load-bearing one. Before
    SY-1 `baseline_finish` read the live plan rows, so a teacher moving a chapter
    into next month would have moved the promise with it and every red subject in
    the school could have been cleared by dragging. The test reschedules a
    chapter four weeks later on an approved plan and asserts the pace does NOT
    improve. If this ever fails, rescheduling has to be taken away again.
  * **A portion is a set, and a skipped chapter lands in the next exam.** The
    founder's case: Term 1 examines chapters 1, 2, 3 and 5; chapter 4 goes to
    Term 2. The prefix model could not say it, and the old "everything after the
    previous cut" arithmetic would have made chapter 4 vanish between the two
    exams rather than appear in the second.
  * **The prefix still means exactly what it meant.** Every portion recorded
    before today keeps its arithmetic; it is read as a set, never rewritten into
    one.
  * **Not scheduled is never overdue and never a zero.** A chapter nobody has
    planned has not been missed — the V2-P11 rule, now on a per-chapter row.
  * **Topic detail is optional.** A chapter-only school's row does not expand
    into one topic repeating its own title.
  * **Scope is a block.** A teacher's board contains her own subjects only, and
    editing another teacher's chapter is 403 rather than a silent no-op.
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
        return str(db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id))))
    finally:
        db.close()


# ── the vocabulary, pure ─────────────────────────────────────────────────────
def test_chapter_status_vocabulary():
    """Four words, and the order between them matters. `not_scheduled` outranks
    `not_started` because they call for different responses: one is a planning
    gap, the other is a teaching gap."""
    assert cov.chapter_status(topics=3, taught_full=3, taught_partial=0,
                              planned=3) == cov.CHAPTER_COMPLETED
    assert cov.chapter_status(topics=3, taught_full=1, taught_partial=0,
                              planned=3) == cov.CHAPTER_IN_PROGRESS
    # A single partial log is progress, not silence.
    assert cov.chapter_status(topics=3, taught_full=0, taught_partial=1,
                              planned=3) == cov.CHAPTER_IN_PROGRESS
    assert cov.chapter_status(topics=3, taught_full=0, taught_partial=0,
                              planned=3) == cov.CHAPTER_NOT_STARTED
    # Nothing taught AND nothing promised: a state, never a failure.
    assert cov.chapter_status(topics=3, taught_full=0, taught_partial=0,
                              planned=0) == cov.CHAPTER_NOT_SCHEDULED
    # An empty chapter cannot be "completed" — it would carry coverage upward
    # while containing nothing to teach.
    assert cov.chapter_status(topics=0, taught_full=0, taught_partial=0,
                              planned=0) == cov.CHAPTER_NOT_SCHEDULED
    # The school's own decision beats every derived reading, including a chapter
    # somebody once logged against: the flag is the more recent statement, and a
    # stale "completed" would quietly inflate the school's coverage.
    assert cov.chapter_status(topics=3, taught_full=3, taught_partial=0,
                              planned=3, excluded=True) == cov.CHAPTER_NOT_SCHEDULED
    assert cov.chapter_status(topics=3, taught_full=0, taught_partial=0,
                              planned=3, excluded=True) == cov.CHAPTER_NOT_SCHEDULED


# ── fixtures ─────────────────────────────────────────────────────────────────
def _setup(client, cleanup):
    """A year that started 8 weeks ago, one class, Maths owned by one teacher."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Board Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    today = date.today()
    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=56)).isoformat(),
        "end_date": (today + timedelta(days=240)).isoformat()}).json()

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"},
        {"username": f"o{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    mine, other = bulk.json()["results"]
    for c in (mine, other):
        cleanup["users"].append(uuid.UUID(c["user_id"]))

    def _login(c):
        tok = client.post("/api/v1/auth/login", json={
            "identifier": c["username"], "password": "supersecret1"}).json()
        return {"Authorization": f"Bearer {tok['access_token']}"}

    th, oh = _login(mine), _login(other)
    teacher_mid = _membership_id(mine["user_id"], reg["org"]["id"])
    other_mid = _membership_id(other["user_id"], reg["org"]["id"])

    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": f"Maths {uuid.uuid4().hex[:4]}"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "periods_per_week": 5, "teacher_member_id": teacher_mid}).json()
    return {"h": h, "th": th, "oh": oh, "year": year, "class": klass, "cs": cs,
            "subject": subject, "teacher_mid": teacher_mid, "other_mid": other_mid}


def _chapter(client, h, cs_id, title, topics):
    """topics = [(title, est)] — a chapter and its sized topics."""
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs_id, "title": title}).json()
    for t, est in topics:
        body = {"unit_id": unit["id"], "title": t}
        if est is not None:
            body["est_periods"] = est
        client.post("/api/v1/planner/syllabus/topics", headers=h, json=body)
    return unit


def _board(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items() if v)
    r = client.get(f"/api/v1/planner/syllabus/board{'?' + q if q else ''}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _chapters(board):
    return [ch for g in board["classes"] for s in g["subjects"] for ch in s["chapters"]]


# ── the board ────────────────────────────────────────────────────────────────
def test_board_groups_by_class_and_carries_every_column(client, cleanup):
    """The table the founder asked for: subject, chapter, periods, difficulty,
    planned dates, actual dates, status and remarks — all on one row."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Fractions",
                    [("Adding", 3), ("Multiplying", 2)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])

    r = client.patch(f"/api/v1/planner/syllabus/units/{unit['id']}", headers=s["h"],
                     json={"difficulty": "hard", "remarks": "Needs manipulatives"})
    assert r.status_code == 200, r.text

    board = _board(client, s["h"], year_id=s["year"]["id"])
    assert board["scope"] == "school"
    assert len(board["classes"]) == 1
    group = board["classes"][0]
    assert group["label"] == "6-A"
    subject = group["subjects"][0]
    assert subject["subject_name"] == s["subject"]["name"]
    assert subject["periods_per_week"] == 5

    ch = subject["chapters"][0]
    assert ch["title"] == "Fractions"
    assert ch["est_periods"] == 5          # Σ of its sized topics, not a topic count
    assert ch["difficulty"] == "hard"
    assert ch["remarks"] == "Needs manipulatives"
    assert ch["topics_total"] == 2
    assert ch["has_topic_detail"] is True  # two topics — the row expands
    assert len(ch["topics"]) == 2
    assert ch["planned_start"] and ch["planned_end"]
    # A planned start is a day the school is actually open, never a Monday it
    # happens to be shut.
    assert date.fromisoformat(ch["planned_start"]).weekday() in (
        s["year"].get("working_weekdays") or [0, 1, 2, 3, 4, 5])
    assert ch["actual_start"] is None and ch["actual_end"] is None
    assert ch["status"] == cov.CHAPTER_NOT_STARTED
    assert ch["completion_pct"] == 0.0

    # The headline is a sentence, not a number (ux rule 3).
    assert "chapter" in board["headline"].lower()


def test_board_without_a_year_id_falls_back_to_the_active_year(client, cleanup):
    """Found in a browser, not by this suite (SY-1).

    Every test here passed `year_id`, and so did the page — a moment later. The
    FIRST request a real screen makes arrives with no year at all, because the
    year context has not resolved yet, and that path 500'd on a column name that
    does not exist. The fallback is the common case, not the edge case."""
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Fractions", [("Adding", 3)])
    r = client.get("/api/v1/planner/syllabus/board", headers=s["h"])
    assert r.status_code == 200, r.text
    assert r.json()["academic_year_id"] == s["year"]["id"]
    assert len(_chapters(r.json())) == 1


def test_logging_moves_a_chapter_through_its_states(client, cleanup):
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Fractions",
                    [("Adding", 3), ("Multiplying", 2)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    topics = client.get(f"/api/v1/planner/syllabus?class_subject_id={s['cs']['id']}",
                        headers=s["h"]).json()[0]["topics"]

    client.post("/api/v1/classroom/lesson-logs", headers=s["th"], json={
        "class_subject_id": s["cs"]["id"], "topic_id": topics[0]["id"],
        "coverage": "full"})
    ch = _chapters(_board(client, s["h"], year_id=s["year"]["id"]))[0]
    assert ch["status"] == cov.CHAPTER_IN_PROGRESS
    assert ch["taught_full"] == 1
    assert ch["completion_pct"] == 50.0
    assert ch["actual_start"] == date.today().isoformat()

    client.post("/api/v1/classroom/lesson-logs", headers=s["th"], json={
        "class_subject_id": s["cs"]["id"], "topic_id": topics[1]["id"],
        "coverage": "full"})
    ch = _chapters(_board(client, s["h"], year_id=s["year"]["id"]))[0]
    assert ch["status"] == cov.CHAPTER_COMPLETED
    assert ch["completion_pct"] == 100.0
    assert ch["actual_end"] == date.today().isoformat()
    assert unit["id"] == ch["unit_id"]


def test_an_unscheduled_chapter_is_never_overdue(client, cleanup):
    """Rule 2, per chapter. A school that plans term by term has unsized, unplanned
    chapters all April; reddening them would put it permanently in the wrong."""
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Later term", [("Not sized", None)])
    ch = _chapters(_board(client, s["h"], year_id=s["year"]["id"]))[0]
    assert ch["status"] == cov.CHAPTER_NOT_SCHEDULED
    assert ch["overdue"] is False
    assert ch["est_periods"] is None      # None, never 0 — nothing is estimated
    assert ch["unsized_topics"] == 1
    assert ch["planned_start"] is None


def test_a_chapter_marked_not_planned_leaves_the_denominator(client, cleanup):
    """The founder's call, 2026-08-08. A chapter the school has decided is out of
    scope stops counting — in the numerator AND the denominator. Leaving it in
    is what made a school that teaches 24 of its 30 chapters read as permanently
    20% short, which is rule 2 inverted: a gap in the *record* rendered as a
    failure by a *person*.

    It must also stay VISIBLE with its real topic count, or the decision could
    never be seen or reversed from the row that made it."""
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Fractions",
             [("Adding", 3), ("Multiplying", 2)])
    dropped = _chapter(client, s["h"], s["cs"]["id"], "Optional unit",
                       [("Extra", 2), ("More", 2)])
    # `coverage_pct` is the PLANNED basis (`syllabus_board.py:227`), so it is
    # None until there is a plan to be a fraction of. Draft one over all four
    # topics — which is exactly the case that matters: the excluded chapter has
    # plan entries, and must still leave the denominator.
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    units = client.get(f"/api/v1/planner/syllabus?class_subject_id={s['cs']['id']}",
                       headers=s["h"]).json()
    for t in units[0]["topics"]:
        client.post("/api/v1/classroom/lesson-logs", headers=s["th"], json={
            "class_subject_id": s["cs"]["id"], "topic_id": t["id"],
            "coverage": "full"})

    subject = _board(client, s["h"], year_id=s["year"]["id"])["classes"][0]["subjects"][0]
    assert subject["coverage_pct"] == 50.0     # 2 taught of 4 topics

    r = client.patch(f"/api/v1/planner/syllabus/units/{dropped['id']}",
                     headers=s["h"], json={"not_planned": True})
    assert r.status_code == 200, r.text

    board = _board(client, s["h"], year_id=s["year"]["id"])
    subject = board["classes"][0]["subjects"][0]
    # 2 of 2 — the dropped chapter left BOTH sides of the fraction, so finishing
    # what the school actually planned reads as finished.
    assert subject["coverage_pct"] == 100.0

    by_title = {c["title"]: c for c in _chapters(board)}
    out = by_title["Optional unit"]
    assert out["not_planned"] is True
    assert out["status"] == cov.CHAPTER_NOT_SCHEDULED
    assert out["overdue"] is False
    assert out["topics_total"] == 2            # still shown, still reversible
    assert by_title["Fractions"]["status"] == cov.CHAPTER_COMPLETED

    # And back: the flag is a decision corrected in place, not a one-way door.
    client.patch(f"/api/v1/planner/syllabus/units/{dropped['id']}",
                 headers=s["h"], json={"not_planned": False})
    subject = _board(client, s["h"], year_id=s["year"]["id"])["classes"][0]["subjects"][0]
    assert subject["coverage_pct"] == 50.0


def test_chapter_only_school_does_not_get_a_pointless_expander(client, cleanup):
    """Most schools track a chapter and nothing finer. Their single topic mirrors
    the chapter's own title, and expanding it would show the same words twice."""
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Light", [("Light", 4)])
    _chapter(client, s["h"], s["cs"]["id"], "Sound", [("Waves and pitch", 4)])
    rows = {c["title"]: c for c in _chapters(_board(client, s["h"],
                                                    year_id=s["year"]["id"]))}
    assert rows["Light"]["has_topic_detail"] is False
    assert rows["Sound"]["has_topic_detail"] is True


# ── the frozen baseline — the reason rescheduling is allowed at all ─────────
def test_rescheduling_an_approved_chapter_cannot_improve_the_pace(client, cleanup):
    """THE test of this packet.

    Approve a plan, then drag a chapter four weeks later. The schedule moves;
    the promise does not. If `weeks_behind` fell here, any teacher could clear
    her own slip by moving chapters into December with nothing taught."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Fractions",
                    [("Adding", 5), ("Multiplying", 5)])
    _chapter(client, s["h"], s["cs"]["id"], "Decimals", [("Places", 5)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    approve = client.post(f"/api/v1/planner/plan/{s['cs']['id']}/approve",
                          headers=s["h"])
    assert approve.status_code == 200, approve.text

    before = client.get(f"/api/v1/planner/plan/forecast?class_id={s['class']['id']}",
                        headers=s["h"]).json()[0]
    baseline_before = before["baseline_finish"]

    ch = next(c for c in _chapters(_board(client, s["h"], year_id=s["year"]["id"]))
              if c["unit_id"] == unit["id"])
    start = date.fromisoformat(ch["planned_start"]) + timedelta(days=28)
    r = client.put(f"/api/v1/planner/plan/{s['cs']['id']}/schedule", headers=s["th"],
                   json={"chapters": [{"unit_id": unit["id"],
                                       "start_date": start.isoformat(),
                                       "end_date": (start + timedelta(days=13)).isoformat()}]})
    assert r.status_code == 200, r.text

    after = client.get(f"/api/v1/planner/plan/forecast?class_id={s['class']['id']}",
                       headers=s["h"]).json()[0]
    # The promise is exactly where the admin locked it.
    assert after["baseline_finish"] == baseline_before
    # And the slip did not get forgiven.
    assert after["weeks_behind"] >= before["weeks_behind"]

    # The move IS visible: the live dates changed, the baseline dates did not.
    moved = next(c for c in _chapters(_board(client, s["h"], year_id=s["year"]["id"]))
                 if c["unit_id"] == unit["id"])
    assert moved["planned_start"] != ch["planned_start"]
    assert moved["baseline_start"] == ch["planned_start"]


def test_extending_a_chapter_actually_extends_it(client, cleanup):
    """Found in a browser, not by this suite.

    The first version reused the drafter's greedy `distribute`, which fills from
    the front and stops when the periods are used up. So a teacher who dragged a
    chapter's end out by a fortnight to say *"this needs longer"* saved the
    dates, got the identical plan back, and had no way to tell whether the
    control was broken. The range she draws IS the chapter's span: the last
    topic lands in its final teaching week."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Fractions",
                    [("A", 2), ("B", 2), ("C", 2)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    before = _chapters(_board(client, s["h"], year_id=s["year"]["id"]))[0]

    start = date.fromisoformat(before["planned_start"])
    longer = start + timedelta(days=35)
    r = client.put(f"/api/v1/planner/plan/{s['cs']['id']}/schedule", headers=s["th"],
                   json={"chapters": [{"unit_id": unit["id"],
                                       "start_date": start.isoformat(),
                                       "end_date": longer.isoformat()}]})
    assert r.status_code == 200, r.text
    after = r.json()["chapters"][0]
    # It genuinely moved out — not the same fortnight it was already in.
    assert after["planned_end"] > before["planned_end"]
    # The plan's unit has been a WEEK since P1, so a chapter ends on the last
    # teaching day of the week holding her date, which can be a few days past
    # it. What must not happen is running into the week AFTER that.
    assert date.fromisoformat(after["planned_end"]) <= longer + timedelta(days=6)
    # ...and it still starts where she said, rather than sliding along with it.
    assert after["planned_start"] == before["planned_start"]


def test_reschedule_reports_a_range_too_short_and_still_saves_it(client, cleanup):
    """V2-P5's rule, on the teacher's dialog: over-capacity is surfaced, never
    squeezed. She is the one who knows whether she can go faster."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Big chapter",
                    [("A", 10), ("B", 10)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])

    start = date.today() + timedelta(days=7)
    r = client.put(f"/api/v1/planner/plan/{s['cs']['id']}/schedule", headers=s["th"],
                   json={"chapters": [{"unit_id": unit["id"],
                                       "start_date": start.isoformat(),
                                       "end_date": (start + timedelta(days=2)).isoformat()}]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["fits"] is False
    assert "too_short" in {v["code"] for v in out["violations"]}
    # Saved anyway — the chapter really did move.
    assert out["chapters"] and out["chapters"][0]["planned_start"] is not None


def test_reschedule_refuses_another_teachers_subject(client, cleanup):
    """`S-46`/`D-15` — blocked with a sentence, not filtered to an empty screen."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Fractions", [("Adding", 3)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    start = date.today() + timedelta(days=7)
    r = client.put(f"/api/v1/planner/plan/{s['cs']['id']}/schedule", headers=s["oh"],
                   json={"chapters": [{"unit_id": unit["id"],
                                       "start_date": start.isoformat(),
                                       "end_date": (start + timedelta(days=7)).isoformat()}]})
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "not_your_subject"


def test_teacher_board_is_her_own_subjects_only(client, cleanup):
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Fractions", [("Adding", 3)])
    mine = _board(client, s["th"], year_id=s["year"]["id"])
    assert mine["scope"] == "mine"
    assert len(_chapters(mine)) == 1
    # The other teacher owns nothing — an empty board, and a headline that says so.
    theirs = _board(client, s["oh"], year_id=s["year"]["id"])
    assert theirs["classes"] == []
    assert "not assigned" in theirs["headline"].lower()
    # And she cannot annotate a chapter that is not hers.
    unit_id = _chapters(mine)[0]["unit_id"]
    r = client.patch(f"/api/v1/planner/syllabus/units/{unit_id}", headers=s["oh"],
                     json={"difficulty": "easy"})
    assert r.status_code == 403


# ── exam ↔ syllabus mapping ──────────────────────────────────────────────────
def _exam(client, h, year, title, start, end):
    return client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": title,
        "start_date": start.isoformat(), "end_date": end.isoformat()}).json()


def test_a_skipped_chapter_lands_in_the_next_exam(client, cleanup):
    """The founder's case, and the whole reason the prefix had to go.

    Term 1 examines chapters 1, 2, 3 and 5. Chapter 4 is held over. Under the old
    "everything after the previous cut" arithmetic chapter 4 fell between the two
    exams and was examined by neither."""
    s = _setup(client, cleanup)
    units = [_chapter(client, s["h"], s["cs"]["id"], f"Chapter {i}", [(f"T{i}", 4)])
             for i in range(1, 6)]
    today = date.today()
    e1 = _exam(client, s["h"], s["year"], "Term 1", today + timedelta(days=40),
               today + timedelta(days=44))
    e2 = _exam(client, s["h"], s["year"], "Term 2", today + timedelta(days=120),
               today + timedelta(days=124))

    keep = [units[0]["id"], units[1]["id"], units[2]["id"], units[4]["id"]]
    r = client.put("/api/v1/planner/exam-map/portion", headers=s["h"], json={
        "exam_event_id": e1["id"], "class_subject_id": s["cs"]["id"],
        "unit_ids": keep})
    assert r.status_code == 200, r.text
    client.put("/api/v1/planner/exam-map/portion", headers=s["h"], json={
        "exam_event_id": e2["id"], "class_subject_id": s["cs"]["id"],
        "unit_ids": [u["id"] for u in units]})

    got = client.get(f"/api/v1/planner/exam-map?class_id={s['class']['id']}",
                     headers=s["h"]).json()
    by_exam = {e["title"]: e for e in got["exams"]}

    term1 = by_exam["Term 1"]["subjects"][0]
    assert term1["source"] == "chapters"
    selected = {c["title"] for c in term1["chapters"] if c["selected"]}
    assert selected == {"Chapter 1", "Chapter 2", "Chapter 3", "Chapter 5"}
    assert term1["required_periods"] == 16          # four chapters × 4 periods

    # Term 2 ADDS only chapter 4 — the one Term 1 skipped. Never zero, and never
    # silently dropped.
    term2 = by_exam["Term 2"]["subjects"][0]
    assert term2["required_periods"] == 4
    # And chapter 4 is not marked as already examined, while chapter 5 is.
    marks = {c["title"]: c["covered_earlier"] for c in term2["chapters"]}
    assert marks["Chapter 4"] is False
    assert marks["Chapter 5"] is True


def test_the_legacy_prefix_still_means_what_it_meant(client, cleanup):
    """Every portion recorded before SY-1 keeps its arithmetic. It is read as a
    set, never rewritten into one — converting it would be the server inventing a
    decision the school never made."""
    s = _setup(client, cleanup)
    units = [_chapter(client, s["h"], s["cs"]["id"], f"Chapter {i}", [(f"T{i}", 4)])
             for i in range(1, 4)]
    topics = client.get(f"/api/v1/planner/syllabus?class_subject_id={s['cs']['id']}",
                        headers=s["h"]).json()
    cut = topics[1]["topics"][0]["id"]      # end of chapter 2
    today = date.today()
    exam = _exam(client, s["h"], s["year"], "Half yearly",
                 today + timedelta(days=40), today + timedelta(days=44))
    r = client.post("/api/v1/academics/exam-portions", headers=s["h"], json={
        "exam_event_id": exam["id"], "class_subject_id": s["cs"]["id"],
        "upto_topic_id": cut})
    assert r.status_code == 200, r.text

    got = client.get(f"/api/v1/planner/exam-map?class_id={s['class']['id']}",
                     headers=s["h"]).json()
    sub = got["exams"][0]["subjects"][0]
    assert sub["source"] == "legacy_prefix"
    assert {c["title"] for c in sub["chapters"] if c["selected"]} == {
        "Chapter 1", "Chapter 2"}
    assert sub["required_periods"] == 8
    assert units[2]["id"] not in [c["unit_id"] for c in sub["chapters"] if c["selected"]]

    # Restating it as chapters retires the prefix rather than keeping two answers
    # on one row.
    client.put("/api/v1/planner/exam-map/portion", headers=s["h"], json={
        "exam_event_id": exam["id"], "class_subject_id": s["cs"]["id"],
        "unit_ids": [units[0]["id"]]})
    again = client.get(f"/api/v1/planner/exam-map?class_id={s['class']['id']}",
                       headers=s["h"]).json()
    assert again["exams"][0]["subjects"][0]["source"] == "chapters"
    assert again["exams"][0]["subjects"][0]["required_periods"] == 4


def test_clearing_a_portion_is_expressible(client, cleanup):
    """An empty list means "this exam examines nothing of this subject" — a real
    answer for a languages-only block, which a delete-shaped API cannot give."""
    s = _setup(client, cleanup)
    unit = _chapter(client, s["h"], s["cs"]["id"], "Chapter 1", [("T1", 4)])
    today = date.today()
    exam = _exam(client, s["h"], s["year"], "Term 1", today + timedelta(days=40),
                 today + timedelta(days=44))
    client.put("/api/v1/planner/exam-map/portion", headers=s["h"], json={
        "exam_event_id": exam["id"], "class_subject_id": s["cs"]["id"],
        "unit_ids": [unit["id"]]})
    out = client.put("/api/v1/planner/exam-map/portion", headers=s["h"], json={
        "exam_event_id": exam["id"], "class_subject_id": s["cs"]["id"],
        "unit_ids": []}).json()
    sub = out["exams"][0]["subjects"][0]
    assert sub["source"] == "none"
    assert sub["verdict"] == "no_portion"
    assert not any(c["selected"] for c in sub["chapters"])


def test_timeline_gives_the_dialog_its_chapters_and_fixed_points(client, cleanup):
    s = _setup(client, cleanup)
    _chapter(client, s["h"], s["cs"]["id"], "Fractions", [("Adding", 4)])
    client.post(f"/api/v1/planner/plan/{s['cs']['id']}/draft", headers=s["h"])
    today = date.today()
    _exam(client, s["h"], s["year"], "Term 1", today + timedelta(days=40),
          today + timedelta(days=44))

    r = client.get(f"/api/v1/planner/plan/{s['cs']['id']}/timeline", headers=s["th"])
    assert r.status_code == 200, r.text
    tl = r.json()
    assert tl["subject_name"] == s["subject"]["name"]
    assert tl["periods_per_week"] == 5
    assert tl["locked"] is False
    assert [c["title"] for c in tl["chapters"]] == ["Fractions"]
    kinds = {mk["kind"] for mk in tl["markers"]}
    assert "today" in kinds and "exam" in kinds
    # Another teacher gets a sentence, not an empty timeline.
    assert client.get(f"/api/v1/planner/plan/{s['cs']['id']}/timeline",
                      headers=s["oh"]).status_code == 403
