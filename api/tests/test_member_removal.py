"""Removing a teacher must hand back the classes they taught.

Member removal is a soft revoke (`memberships.status = 'removed'`), so the row
survives and the `ondelete="SET NULL"` on `class_subjects.teacher_member_id` never
fires. Left alone, the class-subject keeps naming a teacher the Members list no
longer returns: the admin's teacher dropdown renders blank while the row still
points at them, and the timetable keeps counting their weekly load.
"""

import uuid


def _register_admin(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    body = client.post("/api/v1/auth/register-org",
                       json={"org_name": "Removal Org", "name": "Director", "email": email,
                             "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return {"Authorization": f"Bearer {body['access_token']}"}


def _teacher(client, h, username):
    r = client.post("/api/v1/org/members/bulk", headers=h, json={
        "members": [{"username": username, "password": "temp12345", "role": "teacher"}]})
    assert r.status_code == 200, r.text
    user_id = r.json()["results"][0]["user_id"]
    member = next(m for m in client.get("/api/v1/org/members", headers=h).json()["members"]
                  if m["user_id"] == user_id)
    return user_id, member["member_id"]


def _class_subject(client, h):
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Mathematics"}).json()
    return year, subject


def test_removing_a_teacher_releases_their_class_subjects(client, cleanup):
    h = _register_admin(client, cleanup)
    year, subject = _class_subject(client, h)
    user_id, member_id = _teacher(client, h, f"t{uuid.uuid4().hex[:10]}")

    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A",
                              "class_teacher_member_id": member_id}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": member_id, "periods_per_week": 5}).json()
    assert cs["teacher_member_id"] == member_id

    assert client.delete(f"/api/v1/org/members/{user_id}", headers=h).status_code == 200

    rows = client.get(f"/api/v1/academics/classes/{klass['id']}/subjects", headers=h).json()
    # The subject survives — the class still teaches Mathematics, it just has nobody
    # in front of it, which is the state the admin has to see and fix.
    assert len(rows) == 1
    assert rows[0]["teacher_member_id"] is None

    klass_after = next(c for c in client.get(
        f"/api/v1/academics/classes?year_id={year['id']}", headers=h).json()
        if c["id"] == klass["id"])
    assert klass_after["class_teacher_member_id"] is None


def test_removal_leaves_other_teachers_alone(client, cleanup):
    h = _register_admin(client, cleanup)
    year, subject = _class_subject(client, h)
    leaver, leaver_mid = _teacher(client, h, f"a{uuid.uuid4().hex[:10]}")
    stayer, stayer_mid = _teacher(client, h, f"b{uuid.uuid4().hex[:10]}")

    k1 = client.post("/api/v1/academics/classes", headers=h,
                     json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    k2 = client.post("/api/v1/academics/classes", headers=h,
                     json={"academic_year_id": year["id"], "name": "6", "section": "B"}).json()
    client.post("/api/v1/academics/class-subjects", headers=h,
                json={"class_id": k1["id"], "subject_id": subject["id"],
                      "teacher_member_id": leaver_mid, "periods_per_week": 5})
    client.post("/api/v1/academics/class-subjects", headers=h,
                json={"class_id": k2["id"], "subject_id": subject["id"],
                      "teacher_member_id": stayer_mid, "periods_per_week": 5})

    client.delete(f"/api/v1/org/members/{leaver}", headers=h)

    assert client.get(f"/api/v1/academics/classes/{k1['id']}/subjects",
                      headers=h).json()[0]["teacher_member_id"] is None
    assert client.get(f"/api/v1/academics/classes/{k2['id']}/subjects",
                      headers=h).json()[0]["teacher_member_id"] == stayer_mid
    assert stayer  # the surviving teacher's account is untouched


def test_class_subject_teacher_can_be_reassigned_in_place(client, cleanup):
    """PATCH exists so the admin never has to delete a class-subject to change its
    teacher — deleting it would cascade away the syllabus, plan and timetable slots."""
    h = _register_admin(client, cleanup)
    year, subject = _class_subject(client, h)
    _u1, mid1 = _teacher(client, h, f"c{uuid.uuid4().hex[:10]}")
    _u2, mid2 = _teacher(client, h, f"d{uuid.uuid4().hex[:10]}")

    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "7", "section": "A"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid1, "periods_per_week": 5}).json()

    r = client.patch(f"/api/v1/academics/class-subjects/{cs['id']}", headers=h,
                     json={"teacher_member_id": mid2})
    assert r.status_code == 200 and r.json()["teacher_member_id"] == mid2

    # Periods-only PATCH must not disturb the teacher (exclude_unset).
    r = client.patch(f"/api/v1/academics/class-subjects/{cs['id']}", headers=h,
                     json={"periods_per_week": 7})
    assert r.json()["periods_per_week"] == 7
    assert r.json()["teacher_member_id"] == mid2

    # Explicit null un-assigns without destroying the subject.
    r = client.patch(f"/api/v1/academics/class-subjects/{cs['id']}", headers=h,
                     json={"teacher_member_id": None})
    assert r.json()["teacher_member_id"] is None
    assert len(client.get(f"/api/v1/academics/classes/{klass['id']}/subjects",
                          headers=h).json()) == 1
