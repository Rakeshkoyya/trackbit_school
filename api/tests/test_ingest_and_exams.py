"""V2-P7: document ingestion (staff + syllabus), calendar partial blocks, exam
portions and the V5 exam-coverage validator.

Everything here runs with NO api key — the gaps are found by deterministic
validators and only *phrased* by the AI layer, which is the whole point of that
split (app/services/ingest.py)."""

import io
import uuid
from datetime import date, timedelta

from openpyxl import Workbook

from app.services.calendar import (
    effective_periods,
    expand_blocked_dates,
    expand_partial_blocks,
)
from app.services.plan_validate import validate_exam_coverage


def _xlsx(header: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _setup(client, cleanup, *, year_start: date | None = None):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Ingest Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    start = year_start or date(2026, 4, 1)
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": start.isoformat(),
                             "end_date": (start + timedelta(days=364)).isoformat()}).json()
    return h, year


def _class_subject(client, h, year, *, cname="6", section="A", subject="Science", ppw=5):
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": cname,
                              "section": section}).json()
    subj = client.post("/api/v1/academics/subjects", headers=h, json={"name": subject}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subj["id"],
                           "periods_per_week": ppw}).json()
    return klass, subj, cs


# ── pure engine: partial-day blocks ──────────────────────────────────────────
def test_partial_block_costs_periods_not_the_whole_day():
    d = date(2026, 6, 1)  # a Monday
    whole = [(d, d, True, None)]
    partial = [(d, d, True, [1, 2, 3])]

    assert expand_blocked_dates(whole) == {d}
    assert expand_blocked_dates(partial) == set(), "a partial day is not a blocked day"
    assert expand_partial_blocks(partial) == {d: {1, 2, 3}}

    kw = dict(working_weekdays=[0, 1, 2, 3, 4, 5], year_start=d, year_end=d + timedelta(days=300),
              periods_per_day=8)
    clean = effective_periods(6, d, blocked=set(), **kw)
    holiday = effective_periods(6, d, blocked={d}, **kw)
    exam_am = effective_periods(6, d, blocked=set(), partial={d: {1, 2, 3}}, **kw)

    assert clean == 6.0
    assert holiday == 5.0, "a whole-day holiday costs one of six working days"
    # Monday keeps 5/8 of its periods, so the week keeps 5.625 of 6 days' worth.
    assert holiday < exam_am < clean


def test_overlapping_partial_blocks_do_not_double_count():
    d = date(2026, 6, 1)
    rows = [(d, d, True, [1, 2]), (d, d, True, [2, 3])]
    assert expand_partial_blocks(rows) == {d: {1, 2, 3}}


def test_partial_block_naming_every_period_clamps_to_zero():
    d = date(2026, 6, 1)
    got = effective_periods(
        6, d, working_weekdays=[0], blocked=set(), partial={d: set(range(1, 9))},
        year_start=d, year_end=d, periods_per_day=8)
    assert got == 0.0


# ── V5 exam coverage ─────────────────────────────────────────────────────────
def test_exam_coverage_flags_a_topic_taught_after_the_exam():
    exam_start = date(2026, 11, 10)
    portion = [("Cells", date(2026, 10, 5)), ("Photosynthesis", date(2026, 11, 16))]
    v = validate_exam_coverage("Term 1 Exam", exam_start, portion)
    assert v is not None and v.code == "exam_coverage"
    assert "Photosynthesis" in v.message and "2026-11-10" in v.message


def test_exam_coverage_flags_a_topic_in_the_exam_week():
    """A topic planned for the week the exam starts in has not been taught when
    the paper is written."""
    exam_start = date(2026, 11, 10)  # Tuesday
    portion = [("Cells", date(2026, 11, 9))]  # that same Monday
    assert validate_exam_coverage("Term 1", exam_start, portion) is not None


def test_exam_coverage_passes_when_the_portion_finishes_first():
    exam_start = date(2026, 11, 10)
    portion = [("Cells", date(2026, 10, 5)), ("Photosynthesis", date(2026, 10, 26))]
    assert validate_exam_coverage("Term 1", exam_start, portion) is None


def test_generate_plan_reports_exam_coverage_violation(client, cleanup):
    """End to end: a Term-1 exam two weeks into the year cannot possibly have its
    portion taught — generate_plan must say so."""
    monday = date(2026, 4, 6)
    h, year = _setup(client, cleanup, year_start=monday)
    _klass, _subj, cs = _class_subject(client, h, year, ppw=5)

    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Life"}).json()
    topics = [
        client.post("/api/v1/planner/syllabus/topics", headers=h,
                    json={"unit_id": unit["id"], "title": t, "est_periods": 5}).json()
        for t in ("Cells", "Photosynthesis", "Respiration")
    ]

    exam = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": "Term 1 Exam",
        "start_date": "2026-04-20", "end_date": "2026-04-24"}).json()
    portion = client.post("/api/v1/academics/exam-portions", headers=h, json={
        "exam_event_id": exam["id"], "class_subject_id": cs["id"],
        "upto_topic_id": topics[2]["id"]})
    assert portion.status_code == 200, portion.text

    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).json()
    codes = {v["code"] for v in gen["violations"]}
    assert "exam_coverage" in codes, gen["violations"]
    msg = next(v["message"] for v in gen["violations"] if v["code"] == "exam_coverage")
    assert "Term 1 Exam" in msg

    # Move the cut point to the first topic and the violation clears.
    client.post("/api/v1/academics/exam-portions", headers=h, json={
        "exam_event_id": exam["id"], "class_subject_id": cs["id"],
        "upto_topic_id": topics[0]["id"]})
    gen2 = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).json()
    assert "exam_coverage" not in {v["code"] for v in gen2["violations"]}


def test_exam_portion_rejects_a_non_exam_event(client, cleanup):
    h, year = _setup(client, cleanup)
    _k, _s, cs = _class_subject(client, h, year)
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "U"}).json()
    topic = client.post("/api/v1/planner/syllabus/topics", headers=h,
                        json={"unit_id": unit["id"], "title": "T", "est_periods": 1}).json()
    holiday = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "holiday", "title": "Diwali",
        "start_date": "2026-11-01", "end_date": "2026-11-03"}).json()
    r = client.post("/api/v1/academics/exam-portions", headers=h, json={
        "exam_event_id": holiday["id"], "class_subject_id": cs["id"],
        "upto_topic_id": topic["id"]})
    assert r.status_code == 422  # ValidationError


# ── calendar bulk + partial blocks over HTTP ─────────────────────────────────
def test_calendar_bulk_create_and_blocks_periods(client, cleanup):
    h, year = _setup(client, cleanup)
    events = [
        {"academic_year_id": year["id"], "type": "holiday", "title": f"Day {i}",
         "start_date": f"2026-08-{10 + i:02d}", "end_date": f"2026-08-{10 + i:02d}"}
        for i in range(3)
    ]
    events.append({"academic_year_id": year["id"], "type": "exam_block",
                   "title": "Morning test", "start_date": "2026-08-20",
                   "end_date": "2026-08-20", "blocks_periods": [1, 2]})
    r = client.post("/api/v1/academics/calendar/events/bulk", headers=h, json={"events": events})
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out) == 4
    assert out[-1]["blocks_periods"] == [1, 2]
    assert out[0]["blocks_periods"] is None

    # The partial-day event must NOT remove a teaching day from the summary.
    summary = client.get(
        f"/api/v1/academics/calendar/summary?year_id={year['id']}", headers=h).json()
    assert summary["teaching_days"] > 0
    assert len(summary["events"]) == 4


def test_blocks_periods_must_be_null_or_non_empty(client, cleanup):
    h, year = _setup(client, cleanup)
    r = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "event", "title": "Bad",
        "start_date": "2026-08-10", "end_date": "2026-08-10", "blocks_periods": []})
    assert r.status_code == 422


# ── staff import ─────────────────────────────────────────────────────────────
def test_staff_import_analyze_finds_gaps_and_phrases_questions(client, cleanup):
    h, _year = _setup(client, cleanup)
    # No name column at all — the required field is missing, and the two unknown
    # columns become the options for the question.
    data = _xlsx(["Mobile", "Weird Column"], [["9999999999", "x"]])
    r = client.post("/api/v1/org/members/import/analyze", headers=h,
                    files={"file": ("staff.xlsx", data)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["missing_required"] == ["full_name"]
    q = body["questions"][0]
    assert q["field"] == "full_name" and q["skippable"] is True
    assert "Weird Column" in q["options"]
    assert q["source"] == "fixture", "no API key configured -> deterministic phrasing"


def test_staff_import_creates_teachers_and_resolves_assignments(client, cleanup):
    h, year = _setup(client, cleanup)
    _klass, _subj, _cs = _class_subject(client, h, year, cname="6", section="A",
                                        subject="Mathematics")
    data = _xlsx(
        ["Teacher Name", "Email", "Assignments"],
        [["Ramesh Kumar", "ramesh@example.com", "6-A Mathematics"],
         ["Anil Rao", "", "9-Z Astrophysics"]])
    analyze = client.post("/api/v1/org/members/import/analyze", headers=h,
                          files={"file": ("staff.xlsx", data)}).json()
    assert analyze["missing_required"] == []
    assert analyze["mapping"]["full_name"] == "Teacher Name"

    r = client.post("/api/v1/org/members/import/commit", headers=h, json={
        "mapping": analyze["mapping"], "rows": analyze["rows"],
        "academic_year_id": year["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_count"] == 2
    assert body["assigned"] == 1, "only the assignment we can resolve is applied"
    # The unknown class/subject is reported, never guessed at.
    assert body["unresolved"] == [{"teacher": "Anil Rao", "tokens": ["9-Z Astrophysics"]}]

    # Usernames are derived from the name, but are globally unique — a suffix is
    # appended when another school already holds the plain form.
    usernames = sorted(c["username"] for c in body["created"])
    assert len(usernames) == 2
    assert usernames[0].startswith("anil.rao") and usernames[1].startswith("ramesh.kumar")
    # The imported teacher can actually log in with the echoed password.
    cred = next(c for c in body["created"] if c["username"].startswith("ramesh.kumar"))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": cred["password"]})
    assert login.status_code == 200


def test_staff_import_skips_a_teacher_already_in_this_org(client, cleanup):
    """The same person twice in one sheet: create once, skip the duplicate."""
    h, year = _setup(client, cleanup)
    data = _xlsx(["Teacher Name"], [["Ramesh Kumar"], ["Ramesh Kumar"]])
    analyze = client.post("/api/v1/org/members/import/analyze", headers=h,
                          files={"file": ("staff.xlsx", data)}).json()
    body = client.post("/api/v1/org/members/import/commit", headers=h, json={
        "mapping": analyze["mapping"], "rows": analyze["rows"],
        "academic_year_id": year["id"]}).json()
    assert body["created_count"] == 1 and body["skipped"] == 1


def test_staff_import_does_not_skip_a_name_held_by_another_school(client, cleanup):
    """usernames are global. A teacher whose derived username is taken by ANOTHER
    org must still get an account here — she is a different person."""
    name = f"Shared {uuid.uuid4().hex[:6]}"
    data = _xlsx(["Teacher Name"], [[name]])

    h1, y1 = _setup(client, cleanup)
    a1 = client.post("/api/v1/org/members/import/analyze", headers=h1,
                     files={"file": ("staff.xlsx", data)}).json()
    b1 = client.post("/api/v1/org/members/import/commit", headers=h1, json={
        "mapping": a1["mapping"], "rows": a1["rows"], "academic_year_id": y1["id"]}).json()

    h2, y2 = _setup(client, cleanup)
    a2 = client.post("/api/v1/org/members/import/analyze", headers=h2,
                     files={"file": ("staff.xlsx", data)}).json()
    b2 = client.post("/api/v1/org/members/import/commit", headers=h2, json={
        "mapping": a2["mapping"], "rows": a2["rows"], "academic_year_id": y2["id"]}).json()

    assert b1["created_count"] == 1 and b2["created_count"] == 1
    assert b2["skipped"] == 0
    u1 = b1["created"][0]["username"]
    u2 = b2["created"][0]["username"]
    assert u1 != u2, "the second school's teacher gets her own username"


# ── syllabus import ──────────────────────────────────────────────────────────
def test_syllabus_import_from_text(client, cleanup):
    h, year = _setup(client, cleanup)
    _k, _s, cs = _class_subject(client, h, year)
    text = """Chapter 1: Food
Sources of food (3)
Components of food - 2 periods
Chapter 2: Materials
Sorting materials (4)
"""
    r = client.post("/api/v1/planner/syllabus/import/text", headers=h, json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "text"
    assert [u["title"] for u in body["units"]] == ["Food", "Materials"]
    assert body["units"][0]["topics"][0] == {"title": "Sources of food", "est_periods": 3}
    assert body["units"][0]["topics"][1]["est_periods"] == 2
    assert body["topic_count"] == 3

    commit = client.post("/api/v1/planner/syllabus/import/commit", headers=h, json={
        "class_subject_id": cs["id"], "units": body["units"]})
    assert commit.status_code == 200, commit.text
    assert commit.json() == {"units_created": 2, "topics_created": 3, "replaced": False,
                             "unsized_topics": 0, "unresolved_terms": []}

    syllabus = client.get(
        f"/api/v1/planner/syllabus?class_subject_id={cs['id']}", headers=h).json()
    assert [u["title"] for u in syllabus] == ["Food", "Materials"]


def test_syllabus_import_from_grid_with_merged_chapter_cells(client, cleanup):
    """Merged chapter cells export as blanks — a blank continues the chapter above."""
    h, year = _setup(client, cleanup)
    _k, _s, cs = _class_subject(client, h, year)
    data = _xlsx(["Chapter", "Topic", "Periods"],
                 [["Food", "Sources of food", 3],
                  [None, "Components of food", 2],
                  ["Materials", "Sorting materials", None]])
    body = client.post("/api/v1/planner/syllabus/import/analyze", headers=h,
                       files={"file": ("syl.xlsx", data)}).json()
    assert body["mode"] == "grid"
    assert body["missing_required"] == []
    assert [u["title"] for u in body["units"]] == ["Food", "Materials"]
    assert len(body["units"][0]["topics"]) == 2
    # A missing period estimate stays unsized rather than being invented as 1 — an
    # unplanned chapter must not be indistinguishable from a one-period chapter.
    assert body["units"][1]["topics"][0]["est_periods"] is None

    client.post("/api/v1/planner/syllabus/import/commit", headers=h, json={
        "class_subject_id": cs["id"], "units": body["units"]})
    # Re-import with replace wipes rather than duplicates.
    again = client.post("/api/v1/planner/syllabus/import/commit", headers=h, json={
        "class_subject_id": cs["id"], "units": body["units"], "replace": True}).json()
    assert again["replaced"] is True
    syllabus = client.get(
        f"/api/v1/planner/syllabus?class_subject_id={cs['id']}", headers=h).json()
    assert len(syllabus) == 2, "replace must not leave the old chapters behind"


def test_syllabus_grid_without_a_topic_column_falls_back_to_text(client, cleanup):
    h, _year = _setup(client, cleanup)
    data = _xlsx(["Syllabus"], [["Chapter 1: Food"], ["Sources of food (3)"]])
    body = client.post("/api/v1/planner/syllabus/import/analyze", headers=h,
                       files={"file": ("syl.xlsx", data)}).json()
    assert body["source"] == "heuristic-text-fallback"
    assert body["units"][0]["title"] == "Food"


# ── wizard ───────────────────────────────────────────────────────────────────
def test_wizard_steps_are_derived_from_real_data(client, cleanup):
    h, year = _setup(client, cleanup)
    state = client.get("/api/v1/wizard/state", headers=h).json()
    assert state["total_steps"] == 10
    keys = [s["key"] for s in state["steps"]]
    assert keys == ["year", "timings", "classes", "subjects", "staff", "syllabus",
                    "calendar", "students", "timetable", "generate"]
    by_key = {s["key"]: s["complete"] for s in state["steps"]}
    assert by_key["year"] is True and by_key["classes"] is False

    _class_subject(client, h, year)
    state2 = client.get("/api/v1/wizard/state", headers=h).json()
    by_key2 = {s["key"]: s["complete"] for s in state2["steps"]}
    assert by_key2["classes"] is True and by_key2["subjects"] is True
    assert by_key2["syllabus"] is False
    # The class-subject exists but no teacher does, so the staff step is not done.
    assert by_key2["staff"] is False
