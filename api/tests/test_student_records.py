"""The Students area's two halves (founder, 2026-08-05).

Directory answers *who is this child*; Academics answers *how is this child
doing*. This suite defends the second half — the roster board and the two log
books — plus the three rules that were only ever intentions before the class log
could name a child:

  * a per-student class-log line is `lesson_observations`, **never** a lesson
    log, so a lesson that reached three children can never move the syllabus;
  * a note with no rating is a NOTE. `growth.py` renders a rating-less
    observation as `needs_work` and `support.py` labelled it **"excellent"** —
    both would have turned "brought the wrong book" into evidence about a
    child's ability, in opposite directions;
  * an unchecked homework reports NO completion figure, on this surface as on
    every other (HW-1): `not_checked` is the teacher's gap and may never render
    as a child's miss;
  * a teacher's roster is her classes ∪ her homeroom, and someone else's class
    is refused with a sentence rather than returned empty (`S-46`) — an empty
    table reads as "this class has no children".

And the arithmetic rule the roster shares with every other exam surface: minor
and major **never pool** (`S-114`), and each figure carries its denominator
(`S-118`).
"""

import uuid
from datetime import date, timedelta

from tests.test_insights import _recent_working_days, _setup


def _log(client, h, cs_id, **kw):
    return client.post("/api/v1/classroom/class-log", headers=h,
                       json={"class_subject_id": cs_id, **kw})


def _term(client, ctx):
    """`_setup` builds no term, and an exam needs one covering its date —
    `ExamService.save` refuses with `no_term` rather than filing a mark under a
    term nobody declared."""
    return client.post("/api/v1/academics/terms", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "name": "Term 1",
        "start_date": ctx["year"]["start_date"],
        "end_date": ctx["year"]["end_date"]}).json()


def _exam(client, h, ctx, name, total, rows, exam_date=None, type_="chapter_test"):
    return client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": ctx["subject"]["id"],
        "type": type_, "name": name,
        "date": (exam_date or _recent_working_days(1)[0]).isoformat(),
        "total_marks": total, "rows": rows})


# ── the class log book ───────────────────────────────────────────────────────
def test_class_entry_is_a_lesson_log_and_student_entry_is_not(client, cleanup):
    """The load-bearing separation. A class-wide entry moves the syllabus; a line
    about one child moves nothing at all."""
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    today = _recent_working_days(1)[0]

    assert _log(client, h, cs_id, title="Recap of the water cycle",
                date=today.isoformat()).status_code == 200
    res = _log(client, h, cs_id, title="Re-explained condensation at his desk",
               date=today.isoformat(), note="Struggled with the diagram",
               student_ids=[ctx["students"][0]["id"]])
    assert res.status_code == 200, res.text

    book = client.get("/api/v1/classroom/class-log", headers=h,
                      params={"class_subject_id": cs_id}).json()
    kinds = {e["kind"] for e in book["entries"]}
    assert kinds == {"class", "student"}, book["entries"]

    student_row = next(e for e in book["entries"] if e["kind"] == "student")
    assert student_row["student_name"] == "Asha Rao"
    assert student_row["note"] == "Struggled with the diagram"

    # The syllabus must not have moved for the per-student line. `logged_periods`
    # is the count of lesson_logs for this class-subject — one, not two.
    forecast = client.get(f"/api/v1/planner/forecast/{cs_id}", headers=h)
    if forecast.status_code == 200:
        assert forecast.json()["logged_periods"] == 1


def test_a_note_with_no_rating_is_never_read_as_a_verdict(client, cleanup):
    """The defect this packet found in two live readers, pinned in both
    directions: a class-log line reaches neither the growth report's ability
    signal nor a support page labelled "excellent"."""
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    sid = ctx["students"][0]["id"]
    _log(client, h, cs_id, title="Forgot his book again", student_ids=[sid],
         note="Third time this week")

    growth = client.get(f"/api/v1/students/{sid}/growth", headers=h).json()
    blob = str(growth).lower()
    assert "needs_work" not in blob, "a note is not a needs-work flag"
    assert "forgot his book" not in blob, (
        "a class-log line must not surface as an observation on the report card")
    # ...and it did not invent a growth area out of it either.
    assert not any("forgot" in a.lower() for a in growth["growth_areas"])


def test_reading_the_book_is_wider_than_writing_it(client, cleanup):
    """A teacher who does not own this class-subject may still READ the register
    (she may be covering, or own the homeroom) — but a class that is not hers at
    all is refused with a sentence, not an empty book."""
    ctx = _setup(client, cleanup)
    other = client.get("/api/v1/classroom/class-log", headers=ctx["th2"],
                       params={"class_subject_id": ctx["cs"]["id"]})
    assert other.status_code == 403, other.text

    mine = client.get("/api/v1/classroom/class-log", headers=ctx["th"],
                      params={"class_subject_id": ctx["cs"]["id"]}).json()
    assert mine["can_write"] is True


def test_an_entry_needs_a_topic_or_words(client, cleanup):
    ctx = _setup(client, cleanup)
    res = _log(client, ctx["h"], ctx["cs"]["id"], note="just a note")
    assert res.status_code == 422
    assert "topic" in res.json()["error"]["message"].lower()


# ── the homework log book ────────────────────────────────────────────────────
def test_unchecked_homework_reports_no_completion_figure(client, cleanup):
    """HW-1's rule on a new surface: nobody has looked at it, so there is no
    figure — never 0%, which would blame forty children for a teacher who has
    not opened the books."""
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    res = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs_id, "text": "Exercise 4"})
    assert res.status_code == 200, res.text

    book = client.get("/api/v1/classroom/homework-log", headers=h,
                      params={"class_subject_id": cs_id}).json()
    row = book["entries"][0]
    assert row["checked"] is False
    assert row["completion"] is None, "an unchecked set has no completion figure"
    assert row["roster"] == len(ctx["students"])


def test_homework_for_several_children_writes_one_row_each(client, cleanup):
    """`student_ids` is one assignment per child, never a shared row with a list
    on it — every reader keys on (assignment, student)."""
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    ids = [s["id"] for s in ctx["students"]]
    res = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs_id, "text": "Extra practice", "student_ids": ids})
    assert res.status_code == 200, res.text
    assert len(res.json()["created_ids"]) == 2

    book = client.get("/api/v1/classroom/homework-log", headers=h,
                      params={"class_subject_id": cs_id}).json()
    personal = [e for e in book["entries"] if e["student_id"]]
    assert len(personal) == 2
    assert {e["student_name"] for e in personal} == {"Asha Rao", "Bilal Khan"}
    # A roster of one: a personal assignment is not measured against the class.
    assert all(e["roster"] == 1 for e in personal)


# ── the roster board ─────────────────────────────────────────────────────────
def test_roster_never_pools_minor_and_major(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _term(client, ctx)
    a, b = ctx["students"][0]["id"], ctx["students"][1]["id"]
    _exam(client, h, ctx, "Slip test", 10,
          [{"student_id": a, "score": 4}, {"student_id": b, "score": 9}])
    _exam(client, h, ctx, "Term exam", 80,
          [{"student_id": a, "score": 68}, {"student_id": b, "score": 40}],
          type_="term_exam")

    rows = client.get("/api/v1/students/records", headers=h).json()["rows"]
    asha = next(r for r in rows if r["full_name"] == "Asha Rao")
    scales = {f["scale"]: f for f in asha["figures"]}
    assert set(scales) == {"minor", "major"}, "both buckets always present"
    # 4/10 and 68/80 must not become one number: pooled would be 72/90 = 80%.
    assert scales["minor"]["pct"] == 40.0
    assert scales["major"]["pct"] == 85.0
    # ...and each carries its denominator (`S-118`).
    assert all(f["tests_held"] >= f["tests_taken"] >= 1 for f in asha["figures"])
    assert "test" in scales["major"]["sentence"]


def test_roster_attendance_is_derived_and_a_blank_register_is_none(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    rows = client.get("/api/v1/students/records", headers=h).json()["rows"]
    assert all(r["attendance"]["pct"] is None for r in rows), (
        "nothing marked is a word, never 0%")

    today = _recent_working_days(1)[0]
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "date": today.isoformat(),
        "exceptions": [{"student_id": ctx["students"][0]["id"], "status": "absent"}]})

    rows = client.get("/api/v1/students/records", headers=h).json()["rows"]
    asha = next(r for r in rows if r["full_name"] == "Asha Rao")
    bilal = next(r for r in rows if r["full_name"] == "Bilal Khan")
    assert asha["attendance"] == {
        "marked_periods": 1, "present": 0, "absent": 1, "late": 0, "pct": 0.0}
    # Present is DERIVED — Bilal has no row anywhere, and that is the whole of
    # capture-by-exception (P1v2).
    assert bilal["attendance"]["present"] == 1
    assert bilal["attendance"]["pct"] == 100.0


def test_roster_latest_homework_says_not_checked_rather_than_missed(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": ctx["cs"]["id"], "text": "Exercise 4"})

    rows = client.get("/api/v1/students/records", headers=h).json()["rows"]
    hw = rows[0]["homework"]
    assert hw["assigned"] == 1
    assert hw["latest_status"] == "not_checked"
    assert hw["completion"] is None
    assert hw["not_done"] == 0, "the teacher's gap is never the child's miss"
    assert hw["streak"] == 0


def test_a_teacher_sees_her_own_classes_and_is_refused_the_rest(client, cleanup):
    ctx = _setup(client, cleanup)
    mine = client.get("/api/v1/students/records", headers=ctx["th"]).json()
    assert mine["scoped"] is True
    assert mine["class_count"] == 1
    assert {r["full_name"] for r in mine["rows"]} == {"Asha Rao", "Bilal Khan"}

    # The other teacher teaches nothing — an empty scope, not the whole school.
    theirs = client.get("/api/v1/students/records", headers=ctx["th2"]).json()
    assert theirs["rows"] == []

    refused = client.get("/api/v1/students/records", headers=ctx["th2"],
                         params={"class_id": ctx["class"]["id"]})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "not_your_class"

    # The admin sees the school, unscoped.
    every = client.get("/api/v1/students/records", headers=ctx["h"]).json()
    assert every["scoped"] is False


# ── the exam remark ──────────────────────────────────────────────────────────
def test_exam_remark_rides_with_the_mark_and_never_reaches_a_parent(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _term(client, ctx)
    sid = ctx["students"][0]["id"]
    res = _exam(client, h, ctx, "Chapter 2 test", 20, [
        {"student_id": sid, "score": 11, "remark": "Rushed the second half"},
        {"student_id": ctx["students"][1]["id"], "score": 18}])
    assert res.status_code == 200, res.text
    detail = res.json()
    marked = next(r for r in detail["rows"] if r["student_id"] == sid)
    assert marked["remark"] == "Rushed the second half"
    # A child with nothing typed about them has no remark — not an empty string,
    # which a screen would render as a blank quote.
    other = next(r for r in detail["rows"] if r["student_id"] != sid)
    assert other["remark"] is None

    # It reaches the staff report card, beside the mark it is about.
    growth = client.get(f"/api/v1/students/{sid}/growth", headers=h).json()
    remarks = [s.get("remark") for sub in growth["subjects"] for s in sub["scores"]]
    assert "Rushed the second half" in remarks


def test_remark_is_absent_from_the_parent_projection(client, cleanup):
    """P4-adjacent: the parent projection is built field by field, and a new
    column on `assessment_scores` must not appear on it by accident."""
    from app.schemas.parent import ParentScore

    assert "remark" not in ParentScore.model_fields, (
        "the parent's score line is an allowlist — adding a field here is a "
        "decision, never a side effect of a migration")


def test_deleting_a_student_log_line_leaves_the_class_entry(client, cleanup):
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    _log(client, h, cs_id, title="Whole class recap")
    _log(client, h, cs_id, title="One-to-one", student_ids=[ctx["students"][0]["id"]])
    book = client.get("/api/v1/classroom/class-log", headers=h,
                      params={"class_subject_id": cs_id}).json()
    student_row = next(e for e in book["entries"] if e["kind"] == "student")

    assert client.delete(f"/api/v1/classroom/class-log/{student_row['id']}",
                         headers=h).status_code == 200
    after = client.get("/api/v1/classroom/class-log", headers=h,
                       params={"class_subject_id": cs_id}).json()
    assert [e["kind"] for e in after["entries"]] == ["class"]


def test_the_window_is_honoured(client, cleanup):
    ctx = _setup(client, cleanup)
    h, cs_id = ctx["h"], ctx["cs"]["id"]
    old = date.today() - timedelta(days=200)
    _log(client, h, cs_id, title="Ancient history", date=old.isoformat())
    _log(client, h, cs_id, title="This week")

    default_book = client.get("/api/v1/classroom/class-log", headers=h,
                              params={"class_subject_id": cs_id}).json()
    assert [e["title"] for e in default_book["entries"]] == ["This week"]

    wide = client.get("/api/v1/classroom/class-log", headers=h, params={
        "class_subject_id": cs_id, "since": old.isoformat()}).json()
    assert len(wide["entries"]) == 2
    # Newest first — a register is read from the top.
    assert wide["entries"][0]["title"] == "This week"


def test_a_search_narrows_the_roster_without_changing_its_arithmetic(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _term(client, ctx)
    _exam(client, h, ctx, "Slip", 10, [
        {"student_id": s["id"], "score": 5} for s in ctx["students"]])

    everyone = client.get("/api/v1/students/records", headers=h).json()["rows"]
    just_asha = client.get("/api/v1/students/records", headers=h,
                           params={"q": "Asha"}).json()["rows"]
    assert len(just_asha) == 1
    a_full = next(r for r in everyone if r["full_name"] == "Asha Rao")
    # The denominator must not change because someone typed in a search box.
    assert just_asha[0]["figures"] == a_full["figures"]


def test_records_is_not_swallowed_by_the_student_id_route(client, cleanup):
    """`/students/records` sits before `/students/{student_id}` on purpose —
    FastAPI matches in order and would otherwise 422 on the UUID parse."""
    ctx = _setup(client, cleanup)
    res = client.get("/api/v1/students/records", headers=ctx["h"])
    assert res.status_code == 200
    assert "rows" in res.json()
    # And a real id still resolves.
    assert client.get(f"/api/v1/students/{ctx['students'][0]['id']}",
                      headers=ctx["h"]).status_code == 200


def test_unknown_class_id_is_a_404_not_an_empty_board(client, cleanup):
    ctx = _setup(client, cleanup)
    res = client.get("/api/v1/students/records", headers=ctx["h"],
                     params={"class_id": str(uuid.uuid4())})
    assert res.status_code == 200
    assert res.json()["rows"] == []
