"""V2-P4: daily report agent — sections, ambiguity rules, idempotency, AI-off
determinism (SPRD2 §5.6)."""

import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession

DATE = "2026-08-03"  # a Monday (weekday 0) inside the academic year


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Rep Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 5}).json()
    return h, year, klass, cs


def _add_student(client, h, class_id, name):
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name, "class_id": class_id}).json()


def _slot(client, h, class_id, cs_id, period_no=1):
    return client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_id, "weekday": 0, "period_no": period_no,
        "class_subject_id": cs_id, "effective_from": "2026-04-01"})


def test_report_has_sections_and_is_idempotent(client, cleanup):
    h, _year, klass, cs = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    _slot(client, h, klass["id"], cs["id"])
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": []})
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "coverage": "full", "date": DATE})

    got = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h)
    assert got.status_code == 200, got.text
    body = got.json()
    assert len(body["sections"]) >= 3
    assert body["status"] == "draft"
    # AI-off deterministic markdown still renders a titled report.
    assert body["content_md"].startswith("# ") and len(body["content_md"]) > 40
    headings = {s["heading"] for s in body["sections"]}
    assert {"Attendance", "Teaching"} <= headings

    # Idempotent: get-or-create returns the same row; regenerate upserts in place.
    again = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h).json()
    assert again["id"] == body["id"]
    regen = client.post(f"/api/v1/reports/daily/regenerate?on_date={DATE}", headers=h).json()
    assert regen["id"] == body["id"] and regen["status"] == "draft"


def test_ambiguity_attendance_without_log(client, cleanup):
    h, _year, klass, cs = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    _slot(client, h, klass["id"], cs["id"])
    # attendance taken, but the class was never logged.
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": []})
    body = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h).json()
    assert any("attendance but no lesson log" in a for a in body["highlights"]["ambiguities"])


def test_ambiguity_log_without_attendance(client, cleanup):
    h, _year, klass, cs = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    _slot(client, h, klass["id"], cs["id"])
    # logged, but attendance was never taken.
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "coverage": "full", "date": DATE})
    body = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h).json()
    assert any("attendance wasn't taken" in a for a in body["highlights"]["ambiguities"])


def test_repeat_absentee_is_flagged_as_risk(client, cleanup):
    h, _year, klass, cs = _setup(client, cleanup)
    s = _add_student(client, h, klass["id"], "Bala")
    # absent on 3 distinct days within the 5-day window ending DATE.
    for day in ("2026-08-01", "2026-08-02", "2026-08-03"):
        client.post("/api/v1/attendance/mark", headers=h, json={
            "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "date": day,
            "exceptions": [{"student_id": s["id"], "status": "absent"}]})
    body = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h).json()
    assert any("Bala" in r and "absent 3" in r for r in body["highlights"]["risks"])


def test_plan_red_streak_is_flagged(client, cleanup):
    h, year, klass, cs = _setup(client, cleanup)
    client.post(f"/api/v1/academics/years/{year['id']}/activate", headers=h)
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Unit 1"}).json()
    for t in ["Cells", "Tissues", "Organs", "Systems", "Ecology", "Genetics"]:
        client.post("/api/v1/planner/syllabus/topics", headers=h,
                    json={"unit_id": unit["id"], "title": t, "est_periods": 4})
    client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h)
    # A long block pushes projected finish >2 weeks past baseline → red.
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": "Long block",
        "start_date": "2026-04-13", "end_date": "2026-06-05"})
    body = client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=h).json()
    assert any("behind plan" in r for r in body["highlights"]["risks"])


def test_cron_jobs_run_without_error(client, cleanup):
    """The scheduler wires these via run_hourly; each self-gates on org-local time.
    Invoking them off-hour should be a clean no-op (not an error)."""
    h, _year, _klass, _cs = _setup(client, cleanup)
    for job in ("daily_report", "teacher_reminder", "saturday_summary"):
        r = client.post(f"/api/v1/ops/run/{job}", headers=h)
        assert r.status_code == 200, r.text
        assert "result" in r.json()


def test_report_is_admin_only(client, cleanup):
    h, _year, klass, _cs = _setup(client, cleanup)
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    assert client.get(f"/api/v1/reports/daily?on_date={DATE}", headers=th).status_code == 403
