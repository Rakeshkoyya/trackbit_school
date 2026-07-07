"""P1.5: after-school sessions — create, capture, records (SPRD §5.2, Flow 6)."""

import uuid


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Sess Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    ids = []
    for i in range(3):
        s = client.post("/api/v1/students", headers=h, json={
            "admission_no": f"S{i}", "full_name": f"Kid {i}", "class_id": klass["id"]}).json()
        ids.append(s["id"])
    return h, ids


def test_session_capture_and_records(client, cleanup):
    h, ids = _setup(client, cleanup)

    created = client.post("/api/v1/sessions", headers=h, json={
        "name": "Homework Class 6A", "weekdays": [0, 2, 4], "time": "16:15", "student_ids": ids})
    assert created.status_code == 200, created.text
    sess = created.json()
    assert sess["roster_count"] == 3 and len(sess["students"]) == 3

    assert len(client.get("/api/v1/sessions", headers=h).json()) == 1

    # open today's meeting (get-or-create; idempotent)
    m1 = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    m2 = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    assert m1["id"] == m2["id"]  # same meeting, not a duplicate
    assert len(m1["roster"]) == 3 and all(r["status"] is None for r in m1["roster"])
    mid = m1["id"]

    # capture: present / late(5m) / absent, with homework flags
    rows = [
        {"student_id": ids[0], "status": "present", "homework_done": True},
        {"student_id": ids[1], "status": "late", "late_minutes": 5, "homework_done": False},
        {"student_id": ids[2], "status": "absent"},
    ]
    rec = client.patch(f"/api/v1/sessions/meetings/{mid}/attendance", headers=h, json={"rows": rows})
    assert rec.status_code == 200, rec.text
    by_id = {r["student_id"]: r for r in rec.json()["roster"]}
    assert by_id[ids[1]]["status"] == "late" and by_id[ids[1]]["late_minutes"] == 5

    # re-capture is idempotent (correcting a tap), not duplicated
    client.patch(f"/api/v1/sessions/meetings/{mid}/attendance", headers=h,
               json={"rows": [{"student_id": ids[2], "status": "present", "homework_done": True}]})

    # records feed (the next-morning director view precursor)
    records = client.get("/api/v1/sessions/records", headers=h).json()
    assert len(records) == 1
    r = records[0]
    assert r["present"] == 2 and r["late"] == 1 and r["absent"] == 0
    assert r["homework_done"] == 2 and r["total"] == 3
