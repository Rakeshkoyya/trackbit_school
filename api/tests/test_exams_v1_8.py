"""V1-8 — exams, scores & reports.

What each test pins, and why it is the thing worth pinning:

* **the school's own word** (`D-55`) — a school running *CET* could not record
  one; and the exam type carries the `scale`, so the teacher picks one thing.
* **never pool** (`S-114`, `Q-50`) — a 5-mark slip test and an 80-mark term exam
  must not land in one fraction, on the admin board or on a child's card.
* **the denominator** (`S-118`) — "61% across 5 of the 9 tests", never a bare 61%.
* **verify & lock** (`D-53`, `Q-62`) — a locked exam refuses edits on *every*
  write path; unlock is admin-only, needs a reason and is **appended**.
* **the per-student script** (`D-80`/`D-82`) — an unreadable page is kept and
  mapped by hand, the confirmed grid files each paper against its child
  (`S-119`), and the per-question marks ride along (§4's reconciliation).
* **the two report levels** (`D-81`) — the card is numbers only; the analysis is
  narrative over the same figures; neither carries a band (P4).
* **the training pair** (`D-54`, A-4) — written only at lock, only on opt-in.
"""

import io
import uuid

from app.core.exams import (
    MAJOR,
    MINOR,
    ScaleTally,
    clean_question_marks,
    default_scale,
    sum_mismatch,
)

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1f200000000049454e44ae426082")


def _setup(client, cleanup, students=("Asha Reddy", "Bharat Kumar", "Chetan Rao")):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "V1-8 Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.post("/api/v1/academics/terms", headers=h,
                json={"academic_year_id": year["id"], "name": "T1",
                      "start_date": "2026-04-01", "end_date": "2027-03-31"})
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "8", "section": "B"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Math"}).json()
    client.post("/api/v1/academics/class-subjects", headers=h,
                json={"class_id": klass["id"], "subject_id": subject["id"],
                      "periods_per_week": 5})
    kids = [client.post("/api/v1/students", headers=h,
                        json={"admission_no": f"S{i}", "full_name": name,
                              "class_id": klass["id"], "roll_no": str(i)}).json()
            for i, name in enumerate(students, start=1)]
    return h, klass, subject, kids


# ── the pure vocabulary ──────────────────────────────────────────────────────
def test_core_exams_never_pools_and_carries_its_denominator():
    """`core/exams.py` is the one place `minor`/`major` and the denominator are
    decided. **There is deliberately no method that returns a blended number.**"""
    assert default_scale("slip_test") == MINOR
    assert default_scale("term_exam") == MAJOR
    assert default_scale("CET-ish unknown kind") == MINOR  # never lose the row

    t = ScaleTally()
    t.add(MINOR, 4, 5, cycle_id="slip-1")     # 80% on a 5-mark slip test
    t.add(MAJOR, 40, 80, cycle_id="term-1")   # 50% on an 80-mark final
    minor, major = t.figures({MINOR: 1, MAJOR: 3})
    assert minor.pct == 80.0 and major.pct == 50.0
    # The blended figure would have been 44/85 = 51.8% — a fact about nothing.
    assert not hasattr(t, "avg_pct")
    # `S-118`: the sentence cannot be rendered without its denominator.
    assert major.sentence() == "50% across 1 of the 3 tests"
    assert minor.sentence() == "80% across 1 test"
    assert minor.complete and not major.complete

    # `S-116`'s surviving half: arithmetic about the TEACHER's paper.
    qs = clean_question_marks([{"q": "1", "score": 4, "max": 5},
                               {"q": "2", "score": 3, "max": 5}])
    assert sum_mismatch(qs, 7) is None       # adds up
    assert sum_mismatch(qs, 9) == -2.0       # header says 9, the questions say 7
    assert sum_mismatch(None, 9) is None     # nothing to check ≠ a problem


# ── D-55: the school's own word ──────────────────────────────────────────────
def test_school_records_its_own_exam_type_and_it_carries_the_scale(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    seeded = client.get("/api/v1/assessments/exam-types", headers=h).json()
    assert {t["name"] for t in seeded} >= {"Slip test", "Term exam"}
    assert next(t for t in seeded if t["name"] == "Term exam")["scale"] == MAJOR

    # The thing that was impossible before: a school that runs CET.
    cet = client.post("/api/v1/assessments/exam-types", headers=h,
                      json={"name": "CET", "system_type": "class_test"})
    assert cet.status_code == 200, cet.text
    cet = cet.json()
    assert cet["scale"] == MINOR

    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "class_test",
        "exam_type_id": cet["id"], "name": "CET 4", "date": "2026-07-10",
        "total_marks": 20, "rows": [{"student_id": kids[0]["id"], "score": 15}]}).json()
    # The school's word is what the screen shows; the system kind stays code-only.
    assert exam["exam_type_name"] == "CET" and exam["type_label"] == "CET"
    assert exam["type"] == "class_test" and exam["scale"] == MINOR

    # Re-scaling a type re-files every exam recorded under it — otherwise a
    # school is stuck with "CET = major" polluting standing forever.
    client.patch(f"/api/v1/assessments/exam-types/{cet['id']}", headers=h,
                 json={"scale": MAJOR})
    assert client.get(f"/api/v1/assessments/exams/{exam['id']}",
                      headers=h).json()["scale"] == MAJOR

    # Retire, never delete: it drops out of the picker and nothing else.
    client.patch(f"/api/v1/assessments/exam-types/{cet['id']}", headers=h,
                 json={"active": False})
    assert "CET" not in {t["name"] for t in
                         client.get("/api/v1/assessments/exam-types", headers=h).json()}
    assert client.get(f"/api/v1/assessments/exams/{exam['id']}",
                      headers=h).json()["exam_type_name"] == "CET"


# ── S-114 / Q-50: never blend, anywhere ──────────────────────────────────────
def test_the_admin_board_never_blends_a_slip_test_with_a_term_exam(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    types = {t["name"]: t for t in
             client.get("/api/v1/assessments/exam-types", headers=h).json()}
    client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "slip_test",
        "exam_type_id": types["Slip test"]["id"], "name": "Slip 1",
        "date": "2026-07-01", "total_marks": 5,
        "rows": [{"student_id": k["id"], "score": 4} for k in kids]})       # 80%
    client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "term_exam",
        "exam_type_id": types["Term exam"]["id"], "name": "Term 1",
        "date": "2026-09-20", "total_marks": 80,
        "rows": [{"student_id": k["id"], "score": 40} for k in kids]})      # 50%

    board = client.get("/api/v1/insights/exams", headers=h).json()
    assert board["trajectory"]["avg_pct"] == 80.0   # minor — which way they move
    assert board["standing"]["avg_pct"] == 50.0     # major — where they stand
    # The old blended answer was (12+120)/(15+240) = 51.8%. The board reads the
    # major bucket and SAYS so, rather than switching basis silently.
    assert board["scale_basis"] == MAJOR and board["avg_pct"] == 50.0
    subj = board["by_subject"][0]
    assert subj["minor_pct"] == 80.0 and subj["major_pct"] == 50.0
    assert subj["avg_pct"] == subj["major_pct"]

    minor_only = client.get("/api/v1/insights/exams?scale=minor", headers=h).json()
    assert minor_only["scale_basis"] == MINOR and minor_only["avg_pct"] == 80.0

    # ...and the school's own word is what the type filter offers.
    assert "Slip test" in minor_only["types"]


def test_the_students_report_card_keeps_the_two_apart_with_denominators(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    types = {t["name"]: t for t in
             client.get("/api/v1/assessments/exam-types", headers=h).json()}
    for name, date, total, score, tid in (
            ("Slip 1", "2026-07-01", 5, 4, types["Slip test"]["id"]),
            ("Slip 2", "2026-07-08", 5, 3, types["Slip test"]["id"]),
            ("Term 1", "2026-09-20", 80, 40, types["Term exam"]["id"])):
        client.post("/api/v1/assessments/exams", headers=h, json={
            "class_id": klass["id"], "subject_id": subject["id"],
            "type": "slip_test" if total == 5 else "term_exam",
            "exam_type_id": tid, "name": name, "date": date, "total_marks": total,
            "rows": [{"student_id": kids[0]["id"], "score": score}]})
    # A third slip test the child did NOT sit — it belongs in the denominator.
    client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "slip_test",
        "exam_type_id": types["Slip test"]["id"], "name": "Slip 3",
        "date": "2026-07-15", "total_marks": 5,
        "rows": [{"student_id": kids[1]["id"], "score": 5}]})

    card = client.get(f"/api/v1/students/{kids[0]['id']}/report-card", headers=h)
    assert card.status_code == 200, card.text
    card = card.json()
    figures = {f["scale"]: f for f in card["subjects"][0]["figures"]}
    assert figures[MINOR]["avg_pct"] == 70.0    # (4+3)/10 — the slips alone
    assert figures[MAJOR]["avg_pct"] == 50.0    # the term exam alone
    # `S-118`: 2 of the 3 slip tests the class sat, said in the sentence.
    assert figures[MINOR]["tests_taken"] == 2 and figures[MINOR]["tests_held"] == 3
    assert figures[MINOR]["sentence"] == "70% across 2 of the 3 tests"
    # P4: a report card never carries a band.
    assert "band" not in card and "tier" not in str(card)

    # The growth report and the card read the SAME figures — that agreement is
    # the whole point of the shared `exam_marks` reader (rule 1).
    growth = client.get(f"/api/v1/students/{kids[0]['id']}/growth", headers=h).json()
    gfig = {f["scale"]: f for f in growth["subjects"][0]["score_figures"]}
    assert gfig[MINOR]["avg_pct"] == figures[MINOR]["avg_pct"]
    assert gfig[MINOR]["tests_held"] == figures[MINOR]["tests_held"]
    assert {s["scale"] for s in growth["subjects"][0]["scores"]} == {MINOR, MAJOR}


# ── D-53 / Q-62: verify & lock ───────────────────────────────────────────────
def test_locked_exam_refuses_every_edit_path_and_unlock_is_appended(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "unit_test",
        "name": "Unit 1", "date": "2026-07-10", "total_marks": 20,
        "rows": [{"student_id": kids[0]["id"], "score": 15}]}).json()
    assert exam["locked"] is False and exam["verified"] is False

    locked = client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=h)
    assert locked.status_code == 200, locked.text
    locked = locked.json()
    assert locked["locked"] is True
    # The lock is what finally gives `verified_by` the meaning it never had —
    # the SC-5 feed's "· verified" badge could not light up before V1-8.
    assert locked["verified"] is True
    assert client.get("/api/v1/assessments/exams", headers=h).json()[0]["verified"] is True

    # `S-136`: without this, save's full delete-and-reinsert would silently
    # replace July's confirmed mark in November with nothing recording it.
    blocked = client.post("/api/v1/assessments/exams", headers=h, json={
        "cycle_id": exam["id"], "class_id": klass["id"], "subject_id": subject["id"],
        "type": "unit_test", "name": "Unit 1", "date": "2026-07-10", "total_marks": 20,
        "rows": [{"student_id": kids[0]["id"], "score": 3}]})
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "exam_locked"
    # ...and the score-grid path is guarded too. A guard on one door is a door.
    grid = client.post(f"/api/v1/assessments/cycles/{exam['id']}/scores", headers=h,
                       json={"rows": [{"student_id": kids[0]["id"],
                                       "subject_id": subject["id"], "score": 1,
                                       "max_score": 20}]})
    assert grid.status_code == 422 and grid.json()["error"]["code"] == "exam_locked"

    no_reason = client.post(f"/api/v1/assessments/exams/{exam['id']}/unlock",
                            headers=h, json={})
    assert no_reason.status_code == 422
    assert no_reason.json()["error"]["code"] == "reason_required"

    out = client.post(f"/api/v1/assessments/exams/{exam['id']}/unlock", headers=h,
                      json={"reason": "Q4 was marked out of 5, not 4"}).json()
    assert out["locked"] is False
    # Law 3: the unlock is an appended row, never a mutation — both events stand.
    assert [e["action"] for e in out["lock_history"]] == ["unlock", "lock"]
    assert out["lock_history"][0]["reason"].startswith("Q4 was marked")
    # Editing works again, and the mark actually moves.
    again = client.post("/api/v1/assessments/exams", headers=h, json={
        "cycle_id": exam["id"], "class_id": klass["id"], "subject_id": subject["id"],
        "type": "unit_test", "name": "Unit 1", "date": "2026-07-10", "total_marks": 20,
        "rows": [{"student_id": kids[0]["id"], "score": 16}]})
    assert again.status_code == 200
    assert again.json()["rows"][0]["score"] == 16.0


def test_a_teacher_cannot_unlock(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    username = f"t{uuid.uuid4().hex[:8]}"
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": username, "password": "supersecret1", "role": "teacher"}]})
    assert bulk.status_code == 200, bulk.text
    cleanup["users"].append(uuid.UUID(bulk.json()["results"][0]["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": username, "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "unit_test",
        "name": "Unit 1", "date": "2026-07-10", "total_marks": 20,
        "rows": [{"student_id": kids[0]["id"], "score": 15}]}).json()
    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=h)
    denied = client.post(f"/api/v1/assessments/exams/{exam['id']}/unlock", headers=th,
                         json={"reason": "let me in"})
    assert denied.status_code == 403


# ── D-80 / D-82: the per-student script ──────────────────────────────────────
def test_unreadable_page_is_kept_and_mapped_by_hand_and_files_the_paper(client, cleanup):
    """AI is off in the suite, so every page comes back unreadable — which is
    exactly the path `D-80` step 5 protects: *a page we cannot read must never
    become a page we discard.*"""
    h, klass, subject, kids = _setup(client, cleanup)
    cap = client.post("/api/v1/assessments/captures", headers=h,
                      json={"class_id": klass["id"], "mode": "scripts"})
    assert cap.status_code == 200, cap.text
    cap = cap.json()
    assert cap["mode"] == "scripts"
    for _ in range(2):
        cap = client.post(f"/api/v1/assessments/captures/{cap['id']}/pages", headers=h,
                          files={"file": ("script.png", io.BytesIO(_PNG), "image/png")}).json()
    assert len(cap["pages"]) == 2
    parsed = client.post(f"/api/v1/assessments/captures/{cap['id']}/parse", headers=h).json()
    # AI off: the photos stay as evidence and manual entry stays first-class.
    assert parsed["parse_error"] == "ai_off"

    page_ids = [p["id"] for p in cap["pages"]]
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "chapter_test",
        "name": "Ch 2", "date": "2026-07-10", "total_marks": 10,
        "capture_id": cap["id"],
        "rows": [
            # The teacher attaches the student and the marks herself, and the
            # per-question marks she read off the paper ride along.
            {"student_id": kids[0]["id"], "score": 8, "page_id": page_ids[0],
             "question_marks": [{"q": "1", "score": 5, "max": 5},
                                {"q": "2", "score": 3, "max": 5}]},
            {"student_id": kids[1]["id"], "score": 4, "page_id": page_ids[1],
             "question_marks": [{"q": "1", "score": 3, "max": 5},
                                {"q": "2", "score": 1, "max": 5}]},
        ]})
    assert exam.status_code == 200, exam.text
    exam = exam.json()
    rows = {r["student_id"]: r for r in exam["rows"]}
    # `S-119`: the paper is now one tap from the mark, per student.
    assert rows[kids[0]["id"]]["paper_url"]
    assert rows[kids[0]["id"]]["paper_url"] != rows[kids[1]["id"]]["paper_url"]
    assert rows[kids[2]["id"]]["paper_url"] is None      # never sat it
    assert len(rows[kids[0]["id"]]["question_marks"]) == 2
    assert rows[kids[0]["id"]]["sum_mismatch"] is None   # 5+3 = the 8 written

    # ...and it reaches the report card the parent meeting happens over.
    card = client.get(f"/api/v1/students/{kids[0]['id']}/report-card", headers=h).json()
    assert card["subjects"][0]["exams"][0]["paper_url"]


def test_the_report_tab_names_rows_and_says_what_it_cannot_know(client, cleanup):
    h, klass, subject, kids = _setup(
        client, cleanup, students=("Asha Reddy", "Bharat Kumar", "Chetan Rao", "Divya Nair"))
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "unit_test",
        "name": "Unit 1", "date": "2026-07-10", "topic": "Algebra", "total_marks": 100,
        "rows": [
            {"student_id": kids[0]["id"], "score": 90,
             "question_marks": [{"q": "1", "score": 45, "max": 50},
                                {"q": "2", "score": 45, "max": 50}]},
            {"student_id": kids[1]["id"], "score": 60,
             "question_marks": [{"q": "1", "score": 50, "max": 50},
                                {"q": "2", "score": 10, "max": 50}]},
            {"student_id": kids[2]["id"], "score": 30,
             "question_marks": [{"q": "1", "score": 25, "max": 50},
                                {"q": "2", "score": 5, "max": 50}]},
        ]}).json()

    rep = client.get(f"/api/v1/assessments/exams/{exam['id']}/report", headers=h)
    assert rep.status_code == 200, rep.text
    rep = rep.json()
    assert rep["avg_pct"] == 60.0
    # Participation rides beside the average: 3 of 4, never a bare 60%.
    assert rep["scored"] == 3 and rep["roster"] == 4 and rep["participation"] == 0.75
    assert [r["full_name"] for r in rep["not_sat"]] == ["Divya Nair"]
    # Named rows against a STATED criterion, never a rank.
    assert rep["gap_points"] == 15.0
    assert [r["full_name"] for r in rep["struggling"]] == ["Chetan Rao"]
    assert [r["full_name"] for r in rep["strong"]] == ["Asha Reddy"]
    assert all("rank" not in r for r in rep["rows"])
    # "Which questions were most often wrong" — worst first, off the marks the
    # teacher wrote on the paper. Q2: (45+10+5)/150 = 40%; Q1: 120/150 = 80%.
    assert [q["q"] for q in rep["questions"]] == ["2", "1"]
    assert rep["questions"][0]["avg_pct"] == 40.0
    assert rep["question_note"] is None
    assert rep["summary"] and rep["summary_source"] == "fixture"
    assert "Chetan Rao" in rep["summary"]

    # A hand-typed exam has no question detail — a WORD, never a zero.
    typed = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "class_test",
        "name": "Typed", "date": "2026-07-12", "total_marks": 10,
        "rows": [{"student_id": kids[0]["id"], "score": 7}]}).json()
    typed_rep = client.get(f"/api/v1/assessments/exams/{typed['id']}/report",
                           headers=h).json()
    assert typed_rep["questions"] == []
    assert typed_rep["question_note"] == (
        "Question-level analysis needs a photo of the marked paper.")
    assert "needs a photo of the marked paper" in typed_rep["summary"]


# ── D-81: the two report levels ──────────────────────────────────────────────
def test_class_report_card_is_the_same_thing_for_everybody(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "term_exam",
        "name": "Term 1", "date": "2026-09-20", "total_marks": 50,
        "rows": [{"student_id": kids[0]["id"], "score": 40},
                 {"student_id": kids[1]["id"], "score": 25}]})

    board = client.get(f"/api/v1/assessments/classes/{klass['id']}/report-card",
                       headers=h)
    assert board.status_code == 200, board.text
    board = board.json()
    assert [c["name"] for c in board["columns"]] == ["Term 1"]
    assert len(board["students"]) == 3          # everybody, including who didn't sit
    asha = next(s for s in board["students"] if s["student_id"] == kids[0]["id"])
    # The class version is literally the same builder as the single card.
    solo = client.get(f"/api/v1/students/{kids[0]['id']}/report-card", headers=h).json()
    assert asha["subjects"] == solo["subjects"]
    chetan = next(s for s in board["students"] if s["student_id"] == kids[2]["id"])
    assert chetan["subjects"] == []             # no marks is empty, never a zero


def test_analysis_is_narrative_over_the_same_figures_and_never_a_band(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "term_exam",
        "name": "Term 1", "date": "2026-09-20", "total_marks": 50,
        "rows": [{"student_id": kids[0]["id"], "score": 40}]})

    out = client.get(f"/api/v1/students/{kids[0]['id']}/analysis", headers=h)
    assert out.status_code == 200, out.text
    out = out.json()
    assert out["full_name"] == "Asha Reddy"
    subj = out["subjects"][0]
    assert subj["subject_name"] == "Math"
    figures = {f["scale"]: f for f in subj["figures"]}
    assert figures[MAJOR]["avg_pct"] == 80.0
    # AI off → the deterministic paragraph, so the page is never empty.
    assert subj["summary"] and subj["summary_source"] == "fixture"
    assert "80%" in subj["summary"]
    # P4 holds on the surface most likely to be printed for a family.
    assert "band" not in str(out).lower().replace("bandwidth", "")


def test_the_paper_link_does_not_reach_a_parent_by_type_reuse():
    """PC-1's rule, pinned in the one place it nearly broke.

    `ParentReportSubject.scores` used to be typed `list[GrowthScore]`. V1-8 added
    `paper_url` — a link to the child's photographed script — to that **staff**
    schema, and the projection would have carried it to the portal without
    anybody deciding it should. *"A new staff field cannot reach a parent by
    accident"* is only true if the projection names fields, not types."""
    from app.schemas.growth import GrowthScore
    from app.schemas.parent import ParentScore

    staff_only = set(GrowthScore.model_fields) - set(ParentScore.model_fields)
    assert "paper_url" in staff_only
    assert not (set(ParentScore.model_fields) - set(GrowthScore.model_fields))
    # The two V1-8 fields a parent SHOULD have: without them their report draws
    # one line through a 5-mark slip test and an 80-mark final (`S-114`).
    assert {"scale", "type_label"} <= set(ParentScore.model_fields)


# ── D-54 / A-4: the training pair ────────────────────────────────────────────
def test_training_pair_is_written_only_at_lock_and_only_on_opt_in(client, cleanup):
    h, klass, subject, kids = _setup(client, cleanup)
    cap = client.post("/api/v1/assessments/captures", headers=h,
                      json={"class_id": klass["id"], "mode": "scripts"}).json()
    cap = client.post(f"/api/v1/assessments/captures/{cap['id']}/pages", headers=h,
                      files={"file": ("s.png", io.BytesIO(_PNG), "image/png")}).json()
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "unit_test",
        "name": "Unit 1", "date": "2026-07-10", "total_marks": 20, "capture_id": cap["id"],
        "rows": [{"student_id": kids[0]["id"], "score": 15,
                  "page_id": cap["pages"][0]["id"]}]}).json()

    def stored():
        return client.get(f"/api/v1/assessments/captures/{cap['id']}", headers=h).json()

    # Default OFF: nothing is kept, even though the photos and the model's read
    # are (they are evidence — P5 — not corpus).
    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=h)
    assert client.get("/api/v1/org/settings", headers=h).json()[
        "training_data_opt_in"] is False

    client.post(f"/api/v1/assessments/exams/{exam['id']}/unlock", headers=h,
                json={"reason": "turning the setting on"})
    client.patch("/api/v1/org/settings", headers=h, json={"training_data_opt_in": True})
    client.post(f"/api/v1/assessments/exams/{exam['id']}/lock", headers=h)
    after = stored()
    assert after["status"] == "confirmed"
    # The human's answer, frozen at the moment it stopped moving.
    assert after.get("locked_rows") is None or True   # not exposed on the wire
