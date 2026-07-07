"""P1-D/E/F: My Day, quick log, homework + guardian notify, compliance (SPRD §5.2)."""

import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id))
        )
    finally:
        db.close()


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Class Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Science"}).json()
    # assign the class-subject to the director's own membership so My Day surfaces it
    mid = _membership_id(reg["user"]["id"], reg["org"]["id"])
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": str(mid), "periods_per_week": 5}).json()
    return h, year, klass, subject, cs


def test_my_day_and_quick_log(client, cleanup):
    h, _year, _klass, _subject, cs = _setup(client, cleanup)

    day = client.get("/api/v1/classroom/my-day", headers=h).json()
    assert len(day["classes"]) == 1
    mine = day["classes"][0]
    assert mine["subject_name"] == "Science" and mine["class_label"] == "6-A"
    assert mine["logged"] is False

    # quick log → My Day now shows it logged
    logged = client.post("/api/v1/classroom/lesson-logs", headers=h,
                        json={"class_subject_id": cs["id"], "coverage": "full"})
    assert logged.status_code == 200, logged.text
    day2 = client.get("/api/v1/classroom/my-day", headers=h).json()
    assert day2["classes"][0]["logged"] is True


def test_homework_notifies_guardians(client, cleanup):
    h, _year, klass, _subject, cs = _setup(client, cleanup)
    # two students, one guardian each; one guardian opted out
    for adm, opt in [("S1", False), ("S2", True)]:
        client.post("/api/v1/students", headers=h, json={
            "admission_no": adm, "full_name": f"Kid {adm}", "class_id": klass["id"],
            "guardians": [{"name": "Parent", "phone": f"+91980000{adm}", "is_primary": True,
                           "notify_opt_out": opt}]})

    hw = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Draw the water cycle", "due_date": "2026-07-10"})
    assert hw.status_code == 200, hw.text
    # only the non-opted-out guardian is notified (P3 payback, opt-out respected)
    assert hw.json()["notified_count"] == 1

    # next-day completion as a count (never per-item)
    chk = client.post(f"/api/v1/classroom/homework/{hw.json()['id']}/check", headers=h,
                      json={"done_count": 18, "total_count": 20})
    assert chk.status_code == 200


def test_compliance_view(client, cleanup):
    h, _year, _klass, _subject, cs = _setup(client, cleanup)
    comp = client.get("/api/v1/classroom/compliance", headers=h).json()
    assert comp["total"] == 1 and comp["logged_count"] == 0
    client.post("/api/v1/classroom/lesson-logs", headers=h,
                json={"class_subject_id": cs["id"], "coverage": "full"})
    comp2 = client.get("/api/v1/classroom/compliance", headers=h).json()
    assert comp2["logged_count"] == 1
    assert comp2["rows"][0]["logged"] is True
