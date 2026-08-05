"""My Class, expanded (founder, 2026-08-05) — the class teacher's whole desk.

What each test defends. Every one is a way a class teacher's screen would start
telling her something different from what her principal is reading, or a way an
unopened register would be mistaken for news about a child:

  * the overview's attendance block is about TODAY when the school is open,
    marked or not, and `roster` is the class's strength either way — the same
    correction the admin board got on the same day;
  * an unmarked register is neutral and carries a WORD, never a 0% and never a
    tone of red (ux §5);
  * the homework funnel counts **student-homeworks** so `given ⊇ checked ⊇
    graded` nests, `not_checked` stays out of `completion_pct` (HW-1's rule),
    and `carried`/`waived` leave the denominator entirely (`D-34`/`S-98`);
  * a class where nothing has been checked reports NO completion figure at all
    rather than 0% — that is the difference between a teacher who has not opened
    the books and a class that did nothing;
  * the band block counts PLACEMENTS, not children (`D-75`): a child who is A in
    one subject and C in another is in both columns, and `not_assessed` is its
    own number and never a tier;
  * the student log is append-only, staff-only, and writable only by the
    homeroom's own teacher;
  * a teacher who is not this class's class teacher gets 403 on every route.
"""

from datetime import date

import pytest

from tests.test_insights import _recent_working_days, _setup, _slot


def _ct(client, ctx):
    """Give the fixture's teacher the homeroom through the REAL endpoint — so
    this suite also pins that the staff directory is how a class teacher is set,
    and that it writes the column My Class reads."""
    res = client.patch(f"/api/v1/staff/directory/{ctx['teacher_mid']}",
                       headers=ctx["h"],
                       json={"class_teacher_of": [ctx["class"]["id"]]})
    assert res.status_code == 200, res.text
    return res.json()["row"]


def _mark(client, h, ctx, period_no, absent_ids=(), on=None):
    body = {
        "class_id": ctx["class"]["id"], "period_no": period_no,
        "class_subject_id": ctx["cs"]["id"],
        "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids],
    }
    if on is not None:
        body["date"] = on.isoformat()
    return client.post("/api/v1/attendance/mark", headers=h, json=body)


# ── the overview ─────────────────────────────────────────────────────────────
def test_unmarked_register_is_a_word_not_a_zero(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    board = client.get(f"/api/v1/my-class/{ctx['class']['id']}/overview",
                       headers=h).json()
    att = board["attendance"]

    assert att["marked"] is False
    # The strength is known even when the register is not open — the founder's
    # 2026-08-05 rule, applied to the class teacher's own screen.
    assert att["roster"] == len(ctx["students"])
    assert att["pct"] is None
    assert att["tone"] == "neutral", "an unopened register is never red"
    assert att["present"] == 0 and att["absent"] == 0
    assert "not taken" in att["headline"].lower()
    assert att["absentees"] == []
    # ...and the page's own headline leads with it.
    assert "register" in board["headline"].lower()


def test_overview_names_todays_absentees_with_the_number_to_ring(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    today = _recent_working_days(1)[0]
    if today != date.today():
        pytest.skip("today is not a working day")
    _slot(client, h, ctx, today.weekday(), 1)
    away = ctx["students"][0]
    client.post(f"/api/v1/students/{away['id']}/guardians", headers=h,
                json={"name": "Meera Rao", "phone": "+919000000123",
                      "is_primary": True})
    _mark(client, h, ctx, 1, absent_ids=[away["id"]], on=today)

    board = client.get(f"/api/v1/my-class/{ctx['class']['id']}/overview",
                       headers=h).json()
    att = board["attendance"]
    assert att["marked"] is True
    assert att["roster"] == len(ctx["students"])
    assert att["absent"] == 1
    assert att["present"] == len(ctx["students"]) - 1
    row = att["absentees"][0]
    assert row["full_name"] == away["full_name"]
    assert row["explained"] is False and row["tone"] == "red"
    assert row["guardian_phone"] == "+919000000123"
    assert row["reminded_today"] is False


def test_a_recorded_reason_turns_the_row_amber_never_red(client, cleanup):
    """`D-86`: an explained absence is somebody having dealt with it. Painting
    it red is how a board trains its reader to ignore the colour."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    today = _recent_working_days(1)[0]
    if today != date.today():
        pytest.skip("today is not a working day")
    _slot(client, h, ctx, today.weekday(), 1)
    away = ctx["students"][0]
    _mark(client, h, ctx, 1, absent_ids=[away["id"]], on=today)
    client.put("/api/v1/attendance/absences/reason", headers=h,
               json={"student_id": away["id"], "date": today.isoformat(),
                     "reason_code": "sick", "note": "fever, back Monday"})

    att = client.get(f"/api/v1/my-class/{ctx['class']['id']}/overview",
                     headers=h).json()["attendance"]
    row = att["absentees"][0]
    assert row["explained"] is True
    assert row["tone"] == "amber"
    assert row["reason_note"] == "fever, back Monday"
    assert att["tone"] == "amber"


# ── homework ─────────────────────────────────────────────────────────────────
def _homework(client, h, ctx, text="Sums 1-10"):
    return client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": ctx["cs"]["id"], "date": date.today().isoformat(),
        "text": text}).json()


def test_unchecked_homework_reports_no_completion_figure(client, cleanup):
    """HW-1's load-bearing rule. A percentage over an unchecked set blames
    children for a teacher who has not opened the notebooks — so there is no
    percentage at all until somebody checks."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _homework(client, h, ctx)

    hw = client.get(f"/api/v1/my-class/{ctx['class']['id']}/homework",
                    headers=h).json()
    n = len(ctx["students"])
    assert hw["assignments"] == 1
    assert hw["given"] == n                 # student-homeworks, not sets
    assert hw["checked"] == 0
    assert hw["not_checked"] == n
    assert hw["completion_pct"] is None, "never 0% — nobody has looked yet"
    assert hw["unchecked_assignments"] == 1
    assert hw["tone"] == "neutral"
    assert "nothing to report" in hw["headline"]


def test_the_funnel_nests_and_carried_leaves_the_denominator(client, cleanup):
    """`given ⊇ checked ⊇ graded`, and `carried` (absent when it was set) is not
    a miss — otherwise a child off sick tops the "keeps missing it" list."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    assignment = _homework(client, h, ctx)
    students = ctx["students"]
    client.post(f"/api/v1/classroom/homework/{assignment['id']}/check", headers=h,
                json={"results": [
                    {"student_id": students[0]["id"], "status": "not_done"},
                    {"student_id": students[1]["id"], "status": "carried"},
                ]})

    hw = client.get(f"/api/v1/my-class/{ctx['class']['id']}/homework",
                    headers=h).json()
    n = len(students)
    assert hw["given"] == n and hw["checked"] == n
    assert hw["carried"] == 1
    # carried leaves the denominator entirely.
    assert hw["graded"] == n - 1
    assert hw["missed"] == 1
    assert hw["completion_pct"] is not None
    # The stages nest — this is the property the unit change exists to give.
    assert hw["given"] >= hw["checked"] >= hw["graded"]


# ── bands ────────────────────────────────────────────────────────────────────
def test_band_block_counts_placements_and_names_the_unassessed(client, cleanup):
    """`D-75`: there is no overall letter. A child is counted once per SUBJECT,
    and a child who has not been assessed is not a C."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    subject_id = ctx["subject"]["id"]
    client.put("/api/v1/bands/setup/monitored", headers=h,
               json={"subject_ids": [subject_id]})
    term = client.post("/api/v1/academics/terms", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "Term 1",
        "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()
    filed = client.post("/api/v1/bands/class/file", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": subject_id,
        "term_id": term["id"], "source": "observation",
        "rows": [{"student_id": ctx["students"][0]["id"], "tier": "C"}]})
    assert filed.status_code == 200, filed.text

    board = client.get(f"/api/v1/my-class/{ctx['class']['id']}/bands",
                       headers=h).json()
    assert board["monitored"] == 1
    row = board["subjects"][0]
    assert row["subject_id"] == subject_id
    assert row["c"] == 1
    assert row["assessed"] == 1
    assert row["not_assessed"] == len(ctx["students"]) - 1


# ── the students table ───────────────────────────────────────────────────────
def test_student_rows_carry_denominators_not_bare_percentages(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    out = client.get(f"/api/v1/my-class/{ctx['class']['id']}/students",
                     headers=h).json()
    assert len(out["rows"]) == len(ctx["students"])
    for row in out["rows"]:
        # Nothing marked, nothing checked — so both figures are absent rather
        # than zero, and the row is neutral rather than a concern.
        assert row["attendance_pct"] is None
        assert row["marked_days"] == 0
        assert row["homework_pct"] is None
        assert row["tone"] == "neutral"
    assert "no attendance figure" in out["headline"]


# ── the class teacher's log ──────────────────────────────────────────────────
def test_student_log_is_append_only_and_the_homerooms_own(client, cleanup):
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    student_id = ctx["students"][0]["id"]

    # Before she owns the homeroom she may read (she teaches the class) but not
    # write — the log is the class teacher's running account, with one author.
    before = client.get(f"/api/v1/my-class/students/{student_id}/notes", headers=th)
    assert before.status_code == 200
    assert before.json()["can_write"] is False
    denied = client.post(f"/api/v1/my-class/students/{student_id}/notes", headers=th,
                         json={"kind": "wellbeing", "note": "gone quiet this week"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "not_your_student"

    # Give her the homeroom through the staff directory — the only way it is set.
    _ct(client, ctx)

    res = client.post(f"/api/v1/my-class/students/{student_id}/notes", headers=th,
                      json={"kind": "wellbeing", "note": "gone quiet this week"})
    assert res.status_code == 200
    body = res.json()
    assert body["can_write"] is True
    assert body["rows"][0]["note"] == "gone quiet this week"
    assert body["rows"][0]["kind"] == "wellbeing"
    assert body["rows"][0]["author_name"]

    # Append-only: a second thought is a second row, and the newest leads.
    client.post(f"/api/v1/my-class/students/{student_id}/notes", headers=th,
                json={"kind": "achievement", "note": "read aloud in assembly"})
    rows = client.get(f"/api/v1/my-class/students/{student_id}/notes",
                      headers=th).json()["rows"]
    assert len(rows) == 2
    assert rows[0]["note"] == "read aloud in assembly"
    # There is deliberately no edit and no delete route.
    assert client.delete(
        f"/api/v1/my-class/students/{student_id}/notes").status_code in (404, 405)

    # And the count reaches her class table, so the log is discoverable.
    out = client.get(f"/api/v1/my-class/{ctx['class']['id']}/students",
                     headers=th).json()
    row = next(r for r in out["rows"] if r["student_id"] == student_id)
    assert row["note_count"] == 2


def test_another_teacher_is_refused_the_whole_area(client, cleanup):
    """The homeroom is the point of the assignment. A teacher who takes a
    subject in the class still does not get her class-teacher screens."""
    ctx = _setup(client, cleanup)
    class_id = ctx["class"]["id"]
    th = ctx["th"]
    for path in ("overview", "students", "homework", "bands", "register"):
        res = client.get(f"/api/v1/my-class/{class_id}/{path}", headers=th)
        assert res.status_code == 403, f"{path} let a non-class-teacher in"
        assert res.json()["error"]["code"] == "not_your_class"
