"""SC-1: photo score capture — matcher, capture lifecycle, daily-test cycles.

The matcher tests are pure (no DB). The flow tests exercise the API end to end:
AI off keeps everything working (photos stored as evidence, parse reports
`ai_off`), a monkeypatched transcription drives the parse → review → confirm
path, and scores land in `assessment_scores` only on human confirm (§8)."""

import io
import uuid

from app.services.score_match import match_rows

# A 1×1 white PNG — enough for the upload path (downscale is a no-op-safe path).
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1f200000000049454e44ae426082")


# ── matcher (pure) ────────────────────────────────────────────────────────────
def _roster():
    return [
        {"id": "s1", "full_name": "Asha Reddy", "roll_no": "1", "admission_no": "A101"},
        {"id": "s2", "full_name": "Bharat Kumar", "roll_no": "2", "admission_no": "A102"},
        {"id": "s3", "full_name": "Chetan Rao", "roll_no": "3", "admission_no": "A103"},
    ]


def test_match_exact_and_roll():
    rows = match_rows([
        {"name_text": "Asha Reddy", "roll_text": None, "score": 18, "max_score": 20},
        {"name_text": "someone", "roll_text": "A102", "score": 12, "max_score": 20},
    ], _roster())
    assert rows[0]["student_id"] == "s1" and rows[0]["confidence"] == "exact"
    assert rows[1]["student_id"] == "s2" and rows[1]["confidence"] == "roll"


def test_match_fuzzy_misspelling():
    rows = match_rows(
        [{"name_text": "Bharath Kumar", "roll_text": None, "score": 9, "max_score": 20}],
        _roster())
    assert rows[0]["student_id"] == "s2" and rows[0]["confidence"] == "fuzzy"


def test_match_ambiguous_duplicate_names_go_to_human():
    roster = _roster() + [{"id": "s4", "full_name": "Asha Reddy",
                           "roll_no": "4", "admission_no": "A104"}]
    rows = match_rows(
        [{"name_text": "Asha Reddy", "roll_text": None, "score": 15, "max_score": 20}],
        roster)
    assert rows[0]["student_id"] is None and rows[0]["confidence"] is None
    assert {c["student_id"] for c in rows[0]["candidates"]} == {"s1", "s4"}


def test_match_never_claims_a_student_twice():
    rows = match_rows([
        {"name_text": "Chetan Rao", "roll_text": None, "score": 10, "max_score": 20},
        {"name_text": "Chetan Rao", "roll_text": None, "score": 11, "max_score": 20},
    ], _roster())
    assert rows[0]["student_id"] == "s3"
    assert rows[1]["student_id"] is None
    assert rows[1]["candidates"][0]["student_id"] == "s3"


def test_match_gibberish_is_unmatched():
    rows = match_rows(
        [{"name_text": "Zzzz Qqqq", "roll_text": None, "score": 5, "max_score": 20}],
        _roster())
    assert rows[0]["student_id"] is None


# ── API flow ──────────────────────────────────────────────────────────────────
def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Capture Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.post("/api/v1/academics/terms", headers=h,
                json={"academic_year_id": year["id"], "name": "T1",
                      "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Math"}).json()
    kids = [client.post("/api/v1/students", headers=h,
                        json={"admission_no": f"S{i}", "full_name": name,
                              "class_id": klass["id"], "roll_no": str(i)}).json()
            for i, name in enumerate(["Asha Reddy", "Bharat Kumar", "Chetan Rao"], start=1)]
    return h, klass, subject, kids


def _upload_page(client, h, cap_id):
    return client.post(f"/api/v1/assessments/captures/{cap_id}/pages", headers=h,
                       files={"file": ("marks.png", io.BytesIO(_PNG), "image/png")})


def test_daily_test_cycle_derives_term_and_scopes_grid(client, cleanup):
    h, klass, subject, _kids = _setup(client, cleanup)
    cyc = client.post("/api/v1/assessments/cycles", headers=h, json={
        "type": "daily_test", "name": "Math slip test", "date": "2026-07-10",
        "class_id": klass["id"], "subject_id": subject["id"]})
    assert cyc.status_code == 200, cyc.text
    body = cyc.json()
    assert body["term_id"] and body["class_id"] == klass["id"]
    grid = client.get(f"/api/v1/assessments/cycles/{body['id']}/grid?class_id={klass['id']}",
                      headers=h).json()
    assert len(grid["columns"]) == 1 and grid["columns"][0]["name"] == "Math"

    # A date outside every term is refused, not silently misfiled.
    bad = client.post("/api/v1/assessments/cycles", headers=h, json={
        "type": "daily_test", "name": "Oops", "date": "2027-12-01",
        "class_id": klass["id"], "subject_id": subject["id"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "no_term"


def test_capture_flow_ai_off_then_parse_then_confirm(client, cleanup, monkeypatch):
    h, klass, subject, kids = _setup(client, cleanup)
    cyc = client.post("/api/v1/assessments/cycles", headers=h, json={
        "type": "daily_test", "name": "Math slip test", "date": "2026-07-10",
        "class_id": klass["id"], "subject_id": subject["id"]}).json()

    cap = client.post("/api/v1/assessments/captures", headers=h, json={
        "cycle_id": cyc["id"], "class_id": klass["id"], "subject_id": subject["id"]})
    assert cap.status_code == 200, cap.text
    cap = cap.json()
    assert cap["status"] == "uploaded" and len(cap["roster"]) == 3

    up = _upload_page(client, h, cap["id"])
    assert up.status_code == 200 and len(up.json()["pages"]) == 1
    assert up.json()["pages"][0]["url"]  # evidence is fetchable

    # AI off → parse reports ai_off; nothing breaks, photos stay.
    parsed = client.post(f"/api/v1/assessments/captures/{cap['id']}/parse", headers=h).json()
    assert parsed["status"] == "uploaded" and parsed["parse_error"] == "ai_off"

    # Simulate a configured model: transcription rows come back, matcher runs.
    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.score_capture.extract_marksheet",
        lambda filename, data: {"meta": None, "rows": [
            {"name_text": "Asha Reddy", "roll_text": None, "score": 18, "max_score": 20},
            {"name_text": "Bharath Kumar", "roll_text": None, "score": 9, "max_score": 20},
            {"name_text": "Unknown Kid", "roll_text": None, "score": 7, "max_score": 20},
        ]})
    parsed = client.post(f"/api/v1/assessments/captures/{cap['id']}/parse", headers=h).json()
    assert parsed["status"] == "parsed" and parsed["parse_error"] is None
    rows = parsed["parsed_rows"]
    assert rows[0]["student_id"] == kids[0]["id"] and rows[0]["confidence"] == "exact"
    assert rows[1]["student_id"] == kids[1]["id"] and rows[1]["confidence"] == "fuzzy"
    assert rows[2]["student_id"] is None

    # No scores exist until the human confirms (§8).
    grid = client.get(f"/api/v1/assessments/cycles/{cyc['id']}/grid?class_id={klass['id']}",
                      headers=h).json()
    assert grid["cells"] == []

    # Human fixes the unmatched row to Chetan and confirms.
    conf = client.post(f"/api/v1/assessments/captures/{cap['id']}/confirm", headers=h, json={
        "rows": [
            {"student_id": kids[0]["id"], "score": 18, "max_score": 20},
            {"student_id": kids[1]["id"], "score": 9, "max_score": 20},
            {"student_id": kids[2]["id"], "score": 7, "max_score": 20},
        ]})
    assert conf.status_code == 200 and conf.json()["status"] == "confirmed"

    grid = client.get(f"/api/v1/assessments/cycles/{cyc['id']}/grid?class_id={klass['id']}",
                      headers=h).json()
    assert len(grid["cells"]) == 3
    asha = next(c for c in grid["cells"] if c["student_id"] == kids[0]["id"])
    assert asha["score"] == 18.0 and asha["max_score"] == 20.0

    # A confirmed capture is closed.
    again = client.post(f"/api/v1/assessments/captures/{cap['id']}/confirm", headers=h, json={
        "rows": [{"student_id": kids[0]["id"], "score": 1, "max_score": 20}]})
    assert again.status_code == 422 and again.json()["error"]["code"] == "capture_closed"

    # Summary list shows the confirmed capture with its page count.
    lst = client.get(f"/api/v1/assessments/captures?cycle_id={cyc['id']}", headers=h).json()
    assert len(lst) == 1 and lst[0]["status"] == "confirmed" and lst[0]["page_count"] == 1


def test_confirm_rejects_students_outside_the_class(client, cleanup):
    h, klass, subject, _kids = _setup(client, cleanup)
    cyc = client.post("/api/v1/assessments/cycles", headers=h, json={
        "type": "daily_test", "name": "T", "date": "2026-07-10",
        "class_id": klass["id"], "subject_id": subject["id"]}).json()
    cap = client.post("/api/v1/assessments/captures", headers=h, json={
        "cycle_id": cyc["id"], "class_id": klass["id"], "subject_id": subject["id"]}).json()
    stranger = uuid.uuid4()
    r = client.post(f"/api/v1/assessments/captures/{cap['id']}/confirm", headers=h, json={
        "rows": [{"student_id": str(stranger), "score": 5, "max_score": 20}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_in_class"


def test_capture_requires_teaching_the_class(client, cleanup):
    """A teacher with no subject in the class can neither create a capture nor a
    daily-test cycle for it (SPRD2 §2)."""
    h, klass, subject, _kids = _setup(client, cleanup)
    cyc = client.post("/api/v1/assessments/cycles", headers=h, json={
        "type": "daily_test", "name": "T", "date": "2026-07-10",
        "class_id": klass["id"], "subject_id": subject["id"]}).json()
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.post("/api/v1/assessments/captures", headers=th, json={
        "cycle_id": cyc["id"], "class_id": klass["id"], "subject_id": subject["id"]})
    assert r.status_code == 403

    r = client.post("/api/v1/assessments/cycles", headers=th, json={
        "type": "daily_test", "name": "Mine", "date": "2026-07-10",
        "class_id": klass["id"], "subject_id": subject["id"]})
    assert r.status_code == 403

    # And an org-wide cycle is admin-only regardless.
    r = client.post("/api/v1/assessments/cycles", headers=th, json={
        "type": "unit_test", "name": "Nope", "date": "2026-07-10"})
    assert r.status_code == 403
