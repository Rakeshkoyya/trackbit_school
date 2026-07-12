"""SC-5: exam-first scores screen + band categorization.

Covers the new surfaces end to end: save an exam (create → feed → detail →
edit-in-place), few-students exams (roster scoped to the picked subset), the
draft photo capture that autofills the exam form and is filed as evidence on
save, and band thresholds (config + one-tap categorization from a band test,
append-only history)."""

import io
import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession

# A 1×1 white PNG — enough for the upload path.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1f200000000049454e44ae426082")


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Exam Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.post("/api/v1/academics/terms", headers=h,
                json={"academic_year_id": year["id"], "name": "T1",
                      "start_date": "2026-04-01", "end_date": "2026-09-30"})
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Math"}).json()
    kids = [client.post("/api/v1/students", headers=h,
                        json={"admission_no": f"S{i}", "full_name": name,
                              "class_id": klass["id"], "roll_no": str(i)}).json()
            for i, name in enumerate(["Asha Reddy", "Bharat Kumar", "Chetan Rao"], start=1)]
    return h, reg, year, klass, subject, kids


def test_exam_save_feed_detail_and_edit(client, cleanup):
    h, _reg, _year, klass, subject, kids = _setup(client, cleanup)
    saved = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "chapter_test",
        "name": "Ch 3 Fractions", "date": "2026-07-10", "topic": "Fractions",
        "total_marks": 25, "rows": [
            {"student_id": kids[0]["id"], "score": 20},
            {"student_id": kids[1]["id"], "score": 10},
        ]})
    assert saved.status_code == 200, saved.text
    exam = saved.json()
    assert exam["topic"] == "Fractions" and exam["total_marks"] == 25.0
    # max_score defaulted from total_marks
    asha = next(r for r in exam["rows"] if r["student_id"] == kids[0]["id"])
    assert asha["score"] == 20.0 and asha["max_score"] == 25.0
    assert exam["avg_pct"] == 60.0  # (20+10)/50

    feed = client.get("/api/v1/assessments/exams", headers=h).json()
    assert len(feed) == 1
    post = feed[0]
    assert post["class_label"] == "6-A" and post["subject_name"] == "Math"
    assert post["scored_count"] == 2 and post["roster_count"] == 3
    assert post["avg_pct"] == 60.0 and post["grid_only"] is False
    assert post["created_by_name"] == "Director"

    # Edit in place: fix a mark, drop Bharat entirely (full replace).
    edited = client.post("/api/v1/assessments/exams", headers=h, json={
        "cycle_id": exam["id"], "class_id": klass["id"], "subject_id": subject["id"],
        "type": "chapter_test", "name": "Ch 3 Fractions (re-marked)",
        "date": "2026-07-10", "topic": "Fractions", "total_marks": 25,
        "rows": [{"student_id": kids[0]["id"], "score": 22}]}).json()
    assert edited["name"] == "Ch 3 Fractions (re-marked)"
    scored = [r for r in edited["rows"] if r["score"] is not None]
    assert len(scored) == 1 and scored[0]["score"] == 22.0
    # Same cycle, not a new one.
    assert len(client.get("/api/v1/assessments/exams", headers=h).json()) == 1


def test_few_students_exam_scopes_roster(client, cleanup):
    h, _reg, _year, klass, subject, kids = _setup(client, cleanup)
    picked = [kids[0]["id"], kids[2]["id"]]
    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "slip_test",
        "name": "Retest — weak topics", "date": "2026-07-10", "total_marks": 10,
        "student_ids": picked,
        "rows": [{"student_id": kids[0]["id"], "score": 8}]}).json()
    assert {r["student_id"] for r in exam["rows"]} == set(picked)

    # A score for a student outside the subset is refused.
    bad = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "slip_test",
        "name": "Bad", "date": "2026-07-10", "student_ids": picked,
        "rows": [{"student_id": kids[1]["id"], "score": 5}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "not_in_class"

    feed = client.get("/api/v1/assessments/exams", headers=h).json()
    assert feed[0]["few_students"] is True and feed[0]["roster_count"] == 2


def test_draft_capture_autofills_and_files_as_evidence(client, cleanup, monkeypatch):
    h, _reg, _year, klass, subject, kids = _setup(client, cleanup)
    # Papers first — no cycle yet.
    cap = client.post("/api/v1/assessments/captures", headers=h,
                      json={"class_id": klass["id"]})
    assert cap.status_code == 200, cap.text
    cap = cap.json()
    assert cap["cycle_id"] is None and cap["status"] == "uploaded"

    up = client.post(f"/api/v1/assessments/captures/{cap['id']}/pages", headers=h,
                     files={"file": ("marks.png", io.BytesIO(_PNG), "image/png")})
    assert up.status_code == 200

    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.score_capture.extract_marksheet",
        lambda filename, data: {
            "meta": {"title": "Ch 2 Slip Test", "subject": "math",
                     "total_marks": 20, "topic": "Algebra"},
            "rows": [
                {"name_text": "Asha Reddy", "roll_text": None, "score": 18, "max_score": 20},
            ]})
    parsed = client.post(f"/api/v1/assessments/captures/{cap['id']}/parse", headers=h).json()
    assert parsed["status"] == "parsed"
    meta = parsed["parsed_meta"]
    # Header prefills the form; subject text matched deterministically.
    assert meta["title"] == "Ch 2 Slip Test" and meta["total_marks"] == 20.0
    assert meta["subject_id"] == subject["id"] and meta["topic"] == "Algebra"

    # A draft can't be confirmed directly — it saves through the exam review.
    direct = client.post(f"/api/v1/assessments/captures/{cap['id']}/confirm", headers=h,
                         json={"rows": [{"student_id": kids[0]["id"], "score": 18,
                                         "max_score": 20}]})
    assert direct.status_code == 422 and direct.json()["error"]["code"] == "draft_capture"

    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "slip_test",
        "name": "Ch 2 Slip Test", "date": "2026-07-10", "topic": "Algebra",
        "total_marks": 20, "capture_id": cap["id"],
        "rows": [{"student_id": kids[0]["id"], "score": 18}]}).json()
    assert len(exam["pages"]) == 1  # the photo is filed as evidence

    closed = client.get(f"/api/v1/assessments/captures/{cap['id']}", headers=h).json()
    assert closed["status"] == "confirmed" and closed["cycle_id"] == exam["id"]


def test_teacher_creates_only_for_taught_classes(client, cleanup):
    h, reg, year, klass, subject, kids = _setup(client, cleanup)
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    body = {"class_id": klass["id"], "subject_id": subject["id"], "type": "class_test",
            "name": "Nope", "date": "2026-07-10",
            "rows": [{"student_id": kids[0]["id"], "score": 5}]}
    assert client.post("/api/v1/assessments/exams", headers=th, json=body).status_code == 403
    # mine=true → no classes for this teacher yet.
    assert client.get(f"/api/v1/academics/classes?year_id={year['id']}&mine=true",
                      headers=th).json() == []

    # Assign them the class's Math and both start working.
    teacher_mid = str(_membership_id(cred["user_id"], reg["org"]["id"]))
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "teacher_member_id": teacher_mid})
    assert len(client.get(f"/api/v1/academics/classes?year_id={year['id']}&mine=true",
                          headers=th).json()) == 1
    ok = client.post("/api/v1/assessments/exams", headers=th, json={**body, "name": "Mine"})
    assert ok.status_code == 200, ok.text

    # Band tests stay admin-only even for a teacher who teaches the class.
    band = client.post("/api/v1/assessments/exams", headers=th,
                       json={**body, "type": "band_test", "name": "Band"})
    assert band.status_code == 403


def test_band_config_and_categorize(client, cleanup):
    h, _reg, _year, klass, subject, kids = _setup(client, cleanup)
    cfg = client.get("/api/v1/assessments/bands/config", headers=h).json()
    assert cfg == {"a_min": 75, "b_min": 50}
    bad = client.put("/api/v1/assessments/bands/config", headers=h,
                     json={"a_min": 40, "b_min": 60})
    assert bad.status_code == 422
    cfg = client.put("/api/v1/assessments/bands/config", headers=h,
                     json={"a_min": 80, "b_min": 40}).json()
    assert cfg == {"a_min": 80, "b_min": 40}

    exam = client.post("/api/v1/assessments/exams", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"], "type": "band_test",
        "name": "Term 1 categorization", "date": "2026-07-10", "total_marks": 100,
        "rows": [
            {"student_id": kids[0]["id"], "score": 85},   # ≥80 → A
            {"student_id": kids[1]["id"], "score": 55},   # ≥40 → B
            {"student_id": kids[2]["id"], "score": 30},   # <40 → C
        ]}).json()
    res = client.post("/api/v1/assessments/bands/categorize", headers=h,
                      json={"cycle_id": exam["id"]}).json()
    assert res["applied"] == 3
    assert res["counts"] == {"A": 1, "B": 1, "C": 1, "no_score": 0}

    board = client.get(f"/api/v1/assessments/bands?class_id={klass['id']}", headers=h).json()
    tiers = {r["full_name"]: r["current_tier"] for r in board["rows"]}
    assert tiers == {"Asha Reddy": "A", "Bharat Kumar": "B", "Chetan Rao": "C"}

    # Idempotent: same test, same thresholds → nothing moves, history untouched.
    again = client.post("/api/v1/assessments/bands/categorize", headers=h,
                        json={"cycle_id": exam["id"]}).json()
    assert again["applied"] == 0
    hist = client.get(f"/api/v1/assessments/students/{kids[0]['id']}/bands", headers=h).json()
    assert len(hist) == 1 and "Term 1 categorization" in hist[0]["note"]
