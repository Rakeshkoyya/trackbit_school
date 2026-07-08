"""V2-P4: student timeline — computed join, absent periods as gaps, sessions
(SPRD2 §5.7)."""

import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession

DATE = "2026-08-03"  # Monday (weekday 0)


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
                      json={"org_name": "TL Org", "name": "Director", "email": email,
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
    return h, klass, cs


def _slot(client, h, class_id, cs_id, period_no):
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_id, "weekday": 0, "period_no": period_no,
        "class_subject_id": cs_id, "effective_from": "2026-04-01"})


def test_timeline_renders_periods_with_gaps_and_homework(client, cleanup):
    h, klass, cs = _setup(client, cleanup)
    s = client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": "Aisha", "class_id": klass["id"]}).json()
    _slot(client, h, klass["id"], cs["id"], 1)
    _slot(client, h, klass["id"], cs["id"], 2)

    # P1: student absent; P2: all present.
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": [{"student_id": s["id"], "status": "absent"}]})
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 2, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": []})
    # a per-student homework should surface on the timeline
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Extra reading", "student_id": s["id"], "date": DATE})

    tl = client.get(f"/api/v1/students/{s['id']}/timeline?on_date={DATE}", headers=h)
    assert tl.status_code == 200, tl.text
    body = tl.json()
    assert body["class_label"] == "6-A"
    periods = {p["period_no"]: p for p in body["periods"]}
    assert len(periods) == 2
    assert periods[1]["attendance"] == "absent" and periods[1]["gap"] is True
    assert periods[2]["attendance"] == "present" and periods[2]["gap"] is False
    assert any("Extra reading" in hw for hw in periods[1]["homework"])


def test_timeline_includes_sessions(client, cleanup):
    h, klass, cs = _setup(client, cleanup)
    s = client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": "Bala", "class_id": klass["id"]}).json()
    session = client.post("/api/v1/sessions", headers=h, json={
        "name": "Evening Study", "weekdays": [0], "time": "16:30", "student_ids": [s["id"]]}).json()
    meeting = client.post(f"/api/v1/sessions/{session['id']}/meetings?on_date={DATE}",
                          headers=h).json()
    client.patch(f"/api/v1/sessions/meetings/{meeting['id']}/attendance", headers=h, json={
        "rows": [{"student_id": s["id"], "status": "present", "homework_done": True}]})

    body = client.get(f"/api/v1/students/{s['id']}/timeline?on_date={DATE}", headers=h).json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["session_name"] == "Evening Study"
    assert body["sessions"][0]["status"] == "present"
