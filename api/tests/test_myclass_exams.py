"""My Class + the exam module, reworked (founder, 2026-08-05).

What each test defends — every one is a rule that is easy to "fix" back into a
defect, and three of them pin a scope in BOTH directions because a scope test
that only checks what is present cannot tell a block from an empty screen:

  * **Plan → Syllabus is her own teaching; My Class → Syllabus is her class.**
    The board used to fold the homeroom in, so a class teacher opened her
    planning screen to five subjects that were somebody else's plan. Removing it
    is only safe because the other door exists, so the two are tested together.
  * **The homework day book shows what was GIVEN**, and an unchecked homework
    still reports no completion figure at all (HW-1) — the day book must not
    become the one surface where `not_checked` reads as 0%.
  * **The band tab names children per subject** and orders them A → B → C by
    name, never by their percentage: a band is a teaching group, and sorting
    children by marks turns it into a ranking (`S-170`). `not_assessed` stays a
    denominator and never a tier (`D-75`).
  * **A teacher may record only her OWN subject.** `assert_can_take_class` is
    true for every subject of a class she teaches one subject of, which let the
    Science teacher overwrite the Hindi paper. Pinned in both directions.
  * **The main exam list is the admin's**, and an exam that has been sat cannot
    be deleted out from under its marks.
  * **The feed paginates**, so the 31st test of a term is reachable.
"""

import uuid
from datetime import date, timedelta

from tests.test_insights import _setup


def _second_subject(client, ctx, name="Hindi"):
    """A subject of the SAME class taught by the OTHER teacher — the whole point
    of every scope test below."""
    h = ctx["h"]
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": name}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": ctx["class"]["id"], "subject_id": subject["id"],
                           "teacher_member_id": ctx["teacher2_mid"],
                           "periods_per_week": 2}).json()
    return subject, cs


def _make_class_teacher(client, ctx):
    res = client.patch(f"/api/v1/staff/directory/{ctx['teacher_mid']}",
                       headers=ctx["h"],
                       json={"class_teacher_of": [ctx["class"]["id"]]})
    assert res.status_code == 200, res.text


def _subject_names(board) -> set[str]:
    return {s["subject_name"] for g in board["classes"] for s in g["subjects"]}


# ── the syllabus scope, both directions ──────────────────────────────────────
def test_plan_syllabus_is_her_own_subjects_and_my_class_is_the_whole_class(
        client, cleanup):
    """The two halves of the founder's change, and they only make sense together.

    Plan → Syllabus stops folding in the homeroom (there it is HER teaching, and
    her class's other subjects drowned her own rows), and in exchange My Class →
    Syllabus becomes the full board for every subject the class takes.
    """
    ctx = _setup(client, cleanup)
    _second_subject(client, ctx)
    _make_class_teacher(client, ctx)          # she owns 6-A as well
    th = ctx["th"]

    plan = client.get("/api/v1/planner/syllabus/board", headers=th)
    assert plan.status_code == 200, plan.text
    plan = plan.json()
    assert plan["scope"] == "mine"
    # Present: her own. Absent: the colleague's — and the absence is the test.
    assert _subject_names(plan) == {"Science"}, (
        "her homeroom's other subjects are somebody else's plan")

    mine = client.get(f"/api/v1/my-class/{ctx['class']['id']}/syllabus", headers=th)
    assert mine.status_code == 200, mine.text
    mine = mine.json()
    assert mine["scope"] == "class"
    assert _subject_names(mine) == {"Science", "Hindi"}

    # The admin's board is unchanged by any of this.
    admin = client.get("/api/v1/planner/syllabus/board", headers=ctx["h"]).json()
    assert admin["scope"] == "school"
    assert _subject_names(admin) == {"Science", "Hindi"}


def test_another_teachers_class_is_refused_not_filtered(client, cleanup):
    """`S-46`: a block, with a sentence. Filtering to an empty board would read
    as a class with no syllabus rather than one that is not hers."""
    ctx = _setup(client, cleanup)
    res = client.get(f"/api/v1/my-class/{ctx['class']['id']}/syllabus",
                     headers=ctx["th2"])
    assert res.status_code == 403, res.text
    assert res.json()["error"]["code"] == "not_your_class"


# ── the homework day book ────────────────────────────────────────────────────
def _homework(client, h, cs_id, text, on=None, student_id=None):
    body = {"class_subject_id": cs_id,
            "date": (on or date.today()).isoformat(), "text": text}
    if student_id:
        body["student_id"] = student_id
    return client.post("/api/v1/classroom/homework", headers=h, json=body).json()


def test_the_day_book_shows_what_was_given_and_never_invents_a_figure(
        client, cleanup):
    """The tab existed and could not answer the question it is opened with:
    *what was the homework?* It now carries the text — and an unchecked one
    still reports no completion figure at all (HW-1)."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _homework(client, h, ctx["cs"]["id"], "Read chapter 4 and answer Q1-Q5")

    days = client.get(f"/api/v1/my-class/{ctx['class']['id']}/homework/days",
                      headers=h)
    assert days.status_code == 200, days.text
    days = days.json()

    assert len(days["today_items"]) == 1
    item = days["today_items"][0]
    assert item["text"] == "Read chapter 4 and answer Q1-Q5"
    assert item["subject_name"] == "Science"
    assert item["given"] == len(ctx["students"])
    assert item["checked"] is False
    assert item["completion_pct"] is None, "never 0% — nobody has looked yet"
    assert item["misses"] == []
    # Today is shown in full and is deliberately NOT also a row in the table.
    assert all(r["date"] != days["today"] for r in days["rows"])


def test_an_opened_day_names_who_did_not_do_it(client, cleanup):
    """Doing it on time writes no row (P1v2), so the exception list IS the
    record — and `carried` appears on it while leaving the denominator."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    yesterday = date.today() - timedelta(days=1)
    hw = _homework(client, h, ctx["cs"]["id"], "Sums 1-10", on=yesterday)
    students = ctx["students"]
    client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h,
                json={"results": [
                    {"student_id": students[0]["id"], "status": "not_done"},
                    {"student_id": students[1]["id"], "status": "carried"},
                ]})

    day = client.get(f"/api/v1/my-class/{ctx['class']['id']}/homework/day",
                     headers=h, params={"on": yesterday.isoformat()})
    assert day.status_code == 200, day.text
    day = day.json()
    item = day["items"][0]
    assert item["checked"] is True
    assert {m["full_name"] for m in item["misses"]} == {
        students[0]["full_name"], students[1]["full_name"]}
    assert item["carried"] == 1
    # carried leaves the denominator entirely (`D-34`).
    assert item["graded"] == len(students) - 1
    assert item["not_done"] == 1
    assert item["completion_pct"] == 0.0

    # ...and it is a row in the paginated table, with the same arithmetic.
    days = client.get(f"/api/v1/my-class/{ctx['class']['id']}/homework/days",
                      headers=h).json()
    row = next(r for r in days["rows"] if r["date"] == yesterday.isoformat())
    assert row["graded"] == item["graded"] and row["missed"] == 1
    assert days["total_days"] >= 1


# ── the band tab names its children ──────────────────────────────────────────
def test_band_subject_expands_to_named_children_never_ranked(client, cleanup):
    """`D-75`/`S-170`. The tier list is A → B → C then by NAME — ordering it by
    the percentage would make a teaching group a ranking of children — and
    `not_assessed` is a denominator, never a fourth tier."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _make_class_teacher(client, ctx)
    term = _term(client, ctx)
    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [ctx["subject"]["id"]]})

    students = ctx["students"]
    res = client.post("/api/v1/bands/class/file", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": ctx["subject"]["id"],
        "term_id": term["id"], "source": "observation",
        "rows": [{"student_id": students[0]["id"], "tier": "C"}]})
    assert res.status_code == 200, res.text

    board = client.get(f"/api/v1/my-class/{ctx['class']['id']}/bands", headers=h)
    assert board.status_code == 200, board.text
    row = board.json()["subjects"][0]

    assert row["c"] == 1 and row["assessed"] == 1
    # The child who never sat it is not a C — he is simply not on the list.
    assert row["not_assessed"] == len(students) - 1
    assert [s["full_name"] for s in row["students"]] == [students[0]["full_name"]]
    assert row["students"][0]["tier"] == "C"
    # Nothing recorded is null, never 0 — this child has sat no exam.
    assert row["students"][0]["pct"] is None

    # The Overview's block is counts only: it must not pay for the roster read.
    overview = client.get(f"/api/v1/my-class/{ctx['class']['id']}/overview",
                          headers=h).json()
    assert overview["bands"]["subjects"][0]["students"] == []


# ── a teacher records only her own subject ───────────────────────────────────
def _exam_body(ctx, cs_subject_id, name="Unit test"):
    return {
        "class_id": ctx["class"]["id"], "subject_id": cs_subject_id,
        "type": "class_test", "name": name, "date": date.today().isoformat(),
        "total_marks": 20,
        "rows": [{"student_id": ctx["students"][0]["id"], "score": 15}],
    }


def _term(client, ctx):
    """Saving an exam needs a term covering its date."""
    today = date.today()
    return client.post("/api/v1/academics/terms", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "name": "Term 1",
        "start_date": (today - timedelta(days=120)).isoformat(),
        "end_date": (today + timedelta(days=120)).isoformat()}).json()


def test_a_teacher_records_her_own_subject_and_is_refused_a_colleagues(
        client, cleanup):
    """`assert_can_take_class` answers *may she stand in front of this class*,
    which is true for every subject of a class she teaches one subject of. That
    is the right rule for attendance and the wrong one for a mark."""
    ctx = _setup(client, cleanup)
    _term(client, ctx)
    hindi, _cs = _second_subject(client, ctx)
    th = ctx["th"]                      # teaches Science in 6-A, not Hindi

    ok = client.post("/api/v1/assessments/exams", headers=th,
                     json=_exam_body(ctx, ctx["subject"]["id"]))
    assert ok.status_code == 200, ok.text

    refused = client.post("/api/v1/assessments/exams", headers=th,
                          json=_exam_body(ctx, hindi["id"], name="Hindi test"))
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "not_your_subject"

    # The admin is refused nothing.
    admin = client.post("/api/v1/assessments/exams", headers=ctx["h"],
                        json=_exam_body(ctx, hindi["id"], name="Hindi test"))
    assert admin.status_code == 200, admin.text


# ── the main exam calendar ───────────────────────────────────────────────────
def _main_exam(client, ctx, title="Half-yearly", days_ahead=10):
    start = date.today() + timedelta(days=days_ahead)
    return client.post("/api/v1/main-exams", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "title": title,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=4)).isoformat()})


def test_the_exam_list_is_the_admins_and_a_teacher_reads_it_locked(client, cleanup):
    ctx = _setup(client, cleanup)
    _second_subject(client, ctx)
    created = _main_exam(client, ctx)
    assert created.status_code == 200, created.text

    admin = client.get("/api/v1/main-exams", headers=ctx["h"]).json()
    assert admin["can_edit"] is True and admin["scope"] == "school"
    row = admin["rows"][0]
    assert row["title"] == "Half-yearly"
    assert row["state"] == "upcoming"
    assert row["subjects_total"] == 2
    assert row["recorded_subjects"] == 0
    # Nothing recorded is a WORD, never a bold 0%.
    assert row["avg_pct"] is None
    assert "Nothing recorded yet" in row["caption"]

    teacher = client.get("/api/v1/main-exams", headers=ctx["th"]).json()
    assert teacher["can_edit"] is False, "she reads the same list, locked"
    assert [r["title"] for r in teacher["rows"]] == ["Half-yearly"]

    # ...and the write routes refuse her outright, not just the pencils.
    assert client.post("/api/v1/main-exams", headers=ctx["th"], json={
        "academic_year_id": ctx["year"]["id"], "title": "Mine",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat()}).status_code == 403


def test_a_papers_grid_marks_only_her_own_subject_editable(client, cleanup):
    """The asymmetry that is the design: she READS every subject of a class she
    is assigned to, and WRITES only her own."""
    ctx = _setup(client, cleanup)
    hindi, _cs = _second_subject(client, ctx)
    event_id = _main_exam(client, ctx).json()["exam_event_id"]

    detail = client.get(f"/api/v1/main-exams/{event_id}", headers=ctx["th"])
    assert detail.status_code == 200, detail.text
    detail = detail.json()
    assert detail["can_edit_exam"] is False
    rows = {r["subject_name"]: r for g in detail["classes"] for r in g["subjects"]}
    assert set(rows) == {"Science", "Hindi"}, "she can read the whole class's card"
    assert rows["Science"]["can_edit"] is True
    assert rows["Hindi"]["can_edit"] is False

    admin = client.get(f"/api/v1/main-exams/{event_id}", headers=ctx["h"]).json()
    assert all(r["can_edit"] for g in admin["classes"] for r in g["subjects"])

    # `can_edit` must say exactly what the WRITE will accept — a greyed cell the
    # server would have taken is a screen lying about permission. The class
    # teacher is the person who enters a paper for a colleague who has left, so
    # the flag and the guard have to widen together.
    _term(client, ctx)
    _make_class_teacher(client, ctx)
    ct = client.get(f"/api/v1/main-exams/{event_id}", headers=ctx["th"]).json()
    ct_rows = {r["subject_name"]: r for g in ct["classes"] for r in g["subjects"]}
    assert ct_rows["Hindi"]["can_edit"] is True
    body = _exam_body(ctx, hindi["id"], name="Hindi, entered by the class teacher")
    body["exam_event_id"] = event_id
    assert client.post("/api/v1/assessments/exams", headers=ctx["th"],
                       json=body).status_code == 200


def test_an_exam_that_has_been_sat_cannot_be_deleted(client, cleanup):
    """Deleting the block that owns a term's marks would orphan them with
    nothing on screen to say it happened (`D-53`'s reason)."""
    ctx = _setup(client, cleanup)
    _term(client, ctx)
    event_id = _main_exam(client, ctx, days_ahead=-5).json()["exam_event_id"]

    body = _exam_body(ctx, ctx["subject"]["id"], name="Half-yearly · Science")
    body["exam_event_id"] = event_id
    saved = client.post("/api/v1/assessments/exams", headers=ctx["h"], json=body)
    assert saved.status_code == 200, saved.text

    # The paper now shows on the exam's own grid — the `S-115` link finally
    # populated from a screen.
    detail = client.get(f"/api/v1/main-exams/{event_id}", headers=ctx["h"]).json()
    row = next(r for g in detail["classes"] for r in g["subjects"]
               if r["subject_name"] == "Science")
    assert row["cycle_id"] == saved.json()["id"]
    assert row["scored"] == 1

    res = client.delete(f"/api/v1/main-exams/{event_id}", headers=ctx["h"])
    assert res.status_code == 422, res.text
    assert res.json()["error"]["code"] == "exam_has_marks"


def test_an_empty_exam_deletes_and_dates_stay_inside_the_year(client, cleanup):
    ctx = _setup(client, cleanup)
    event_id = _main_exam(client, ctx).json()["exam_event_id"]
    assert client.delete(f"/api/v1/main-exams/{event_id}",
                         headers=ctx["h"]).status_code == 200

    outside = client.post("/api/v1/main-exams", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "title": "Next year's",
        "start_date": "2030-01-01", "end_date": "2030-01-05"})
    assert outside.status_code == 422, outside.text
    assert outside.json()["error"]["code"] == "outside_year"


# ── the feed paginates ───────────────────────────────────────────────────────
def test_the_exam_feed_pages_and_carries_its_total(client, cleanup):
    """Without a total the pager is a Next button that may or may not do
    anything; without pagination the 31st test of a term is unreachable."""
    ctx = _setup(client, cleanup)
    _term(client, ctx)
    for i in range(3):
        body = _exam_body(ctx, ctx["subject"]["id"], name=f"Test {i}")
        body["date"] = (date.today() - timedelta(days=i)).isoformat()
        assert client.post("/api/v1/assessments/exams", headers=ctx["h"],
                           json=body).status_code == 200

    first = client.get("/api/v1/assessments/exams/page", headers=ctx["h"],
                       params={"size": 2, "page": 1})
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["total"] == 3 and len(first["rows"]) == 2

    second = client.get("/api/v1/assessments/exams/page", headers=ctx["h"],
                        params={"size": 2, "page": 2}).json()
    assert len(second["rows"]) == 1
    ids = {r["id"] for r in first["rows"]} | {r["id"] for r in second["rows"]}
    assert len(ids) == 3, "the pages do not overlap"

    # Narrowing by subject is what makes "how did 6-A do in Science" askable.
    scoped = client.get("/api/v1/assessments/exams/page", headers=ctx["h"],
                        params={"class_id": ctx["class"]["id"],
                                "subject_id": ctx["subject"]["id"]}).json()
    assert scoped["total"] == 3
    empty = client.get("/api/v1/assessments/exams/page", headers=ctx["h"],
                       params={"subject_id": str(uuid.uuid4())}).json()
    assert empty["total"] == 0 and empty["rows"] == []
