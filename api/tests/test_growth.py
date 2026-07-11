"""Teacher-view redesign: deep-log observations + the student growth report.

The deep log is optional and exception-only (P1v2): a section save writes concept
rows plus ONLY the tapped students. Growth is a computed join — chapter-level by
default with topic rows nested for drill-down — visible to admin and to teachers
of the student's class only.
"""

import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession


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
                      json={"org_name": "Growth Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()

    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "English"}).json()

    # A dedicated teacher who owns the class-subject.
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    teacher_mid = str(_membership_id(cred["user_id"], reg["org"]["id"]))

    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": teacher_mid, "periods_per_week": 5}).json()
    return h, th, year, klass, cs


def _add_student(client, h, class_id, name):
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name, "class_id": class_id}).json()


def test_observation_section_roundtrip(client, cleanup):
    """Save = full replace of one section; rows are concepts + tapped students only."""
    h, th, _year, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")
    _b = _add_student(client, h, klass["id"], "Bala")

    r = client.put("/api/v1/classroom/observations", headers=th, json={
        "class_subject_id": cs["id"], "section": "Vocabulary", "period_no": 1,
        "concepts": [
            {"concept": "Reading",
             "students": [{"student_id": a["id"], "rating": "needs_work", "note": "slow"}]},
            {"concept": "Writing", "students": []},
        ]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sections"]) == 1
    section = body["sections"][0]
    assert section["section"] == "Vocabulary" and section["period_id"] is not None
    by_concept = {c["concept"]: c for c in section["concepts"]}
    assert set(by_concept) == {"Reading", "Writing"}
    assert by_concept["Reading"]["students"][0]["full_name"] == "Aisha"
    assert by_concept["Writing"]["students"] == []

    # Re-save the same section without the tapped student — replaced, not appended.
    r2 = client.put("/api/v1/classroom/observations", headers=th, json={
        "class_subject_id": cs["id"], "section": "Vocabulary", "period_no": 1,
        "concepts": [{"concept": "Reading", "students": []}]})
    s2 = r2.json()["sections"][0]
    assert [c["concept"] for c in s2["concepts"]] == ["Reading"]
    assert s2["concepts"][0]["students"] == []

    # Delete removes the section entirely.
    r3 = client.delete(
        f"/api/v1/classroom/observations?class_subject_id={cs['id']}&section=Vocabulary",
        headers=th)
    assert r3.status_code == 200
    r4 = client.get(f"/api/v1/classroom/observations?class_subject_id={cs['id']}", headers=th)
    assert r4.json()["sections"] == []


def test_observation_write_requires_teaching_the_class(client, cleanup):
    h, _th, _year, klass, cs = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"x{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    other = {"Authorization": f"Bearer {login['access_token']}"}
    r = client.put("/api/v1/classroom/observations", headers=other, json={
        "class_subject_id": cs["id"], "section": "Vocabulary", "concepts": []})
    assert r.status_code == 403


def test_growth_tracks_chapters_topics_and_absence(client, cleanup):
    """Chapter default + topic drill-down: a topic taught while the student was
    absent shows as missed at both levels; homework and observations roll in."""
    h, th, _year, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")
    b = _add_student(client, h, klass["id"], "Bala")

    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Grammar"}).json()
    t1 = client.post("/api/v1/planner/syllabus/topics", headers=h,
                     json={"unit_id": unit["id"], "title": "Nouns", "est_periods": 2}).json()
    _t2 = client.post("/api/v1/planner/syllabus/topics", headers=h,
                      json={"unit_id": unit["id"], "title": "Verbs", "est_periods": 2}).json()

    # Period 1: Aisha absent; the class covers "Nouns" in that period.
    mark = client.post("/api/v1/attendance/mark", headers=th, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert mark.status_code == 200, mark.text
    log = client.post("/api/v1/classroom/lesson-logs", headers=th, json={
        "class_subject_id": cs["id"], "topic_id": t1["id"], "coverage": "full",
        "period_no": 1})
    assert log.status_code == 200, log.text

    # Class homework + one personal addition for Aisha; a deep-log flag for Aisha.
    client.post("/api/v1/classroom/homework", headers=th,
                json={"class_subject_id": cs["id"], "text": "Read ch 1"})
    client.post("/api/v1/classroom/homework", headers=th,
                json={"class_subject_id": cs["id"], "text": "Extra nouns list",
                      "student_id": a["id"]})
    client.put("/api/v1/classroom/observations", headers=th, json={
        "class_subject_id": cs["id"], "section": "Vocabulary", "period_no": 1,
        "concepts": [{"concept": "Reading",
                      "students": [{"student_id": a["id"], "rating": "needs_work"}]}]})

    g = client.get(f"/api/v1/students/{a['id']}/growth", headers=th)
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["full_name"] == "Aisha"
    assert body["attendance"]["marked_periods"] == 1 and body["attendance"]["absent"] == 1

    subj = next(s for s in body["subjects"] if s["subject_name"] == "English")
    assert subj["homework_assigned"] == 2 and subj["homework_personal"] == 1
    assert len(subj["observations"]) == 1
    assert subj["observations"][0]["concept"] == "Reading"

    chapter = subj["chapters"][0]
    assert chapter["title"] == "Grammar"
    assert chapter["topics_total"] == 2 and chapter["topics_taught"] == 1
    assert chapter["topics_missed"] == 1
    topics = {t["title"]: t for t in chapter["topics"]}
    assert topics["Nouns"]["status"] == "done"
    assert topics["Nouns"]["student_attendance"] == "absent"
    assert topics["Verbs"]["status"] == "pending"
    assert topics["Verbs"]["student_attendance"] is None

    # Bala was present — same chapter, nothing missed, only class homework.
    g2 = client.get(f"/api/v1/students/{b['id']}/growth", headers=th).json()
    subj2 = next(s for s in g2["subjects"] if s["subject_name"] == "English")
    assert subj2["chapters"][0]["topics_missed"] == 0
    assert subj2["homework_assigned"] == 1 and subj2["homework_personal"] == 0
    t_nouns = next(t for t in subj2["chapters"][0]["topics"] if t["title"] == "Nouns")
    assert t_nouns["student_attendance"] == "present"


def test_growth_visible_to_admin_and_assigned_teacher_only(client, cleanup):
    h, th, _year, klass, _cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")

    assert client.get(f"/api/v1/students/{a['id']}/growth", headers=h).status_code == 200
    assert client.get(f"/api/v1/students/{a['id']}/growth", headers=th).status_code == 200

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"y{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    other = {"Authorization": f"Bearer {login['access_token']}"}
    r = client.get(f"/api/v1/students/{a['id']}/growth", headers=other)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "not_your_student"
