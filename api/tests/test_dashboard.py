"""P2: Director Dashboard — RAG/alerts, alert→task, digest, director-only fees."""

import uuid


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Dash Org", "name": "Director", "email": email,
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
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "periods_per_week": 5}).json()
    return h, year, klass, cs


def test_overview_alerts_and_alert_to_task(client, cleanup):
    h, year, klass, cs = _setup(client, cleanup)
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "U1"}).json()
    for t in ["A", "B", "C", "D", "E", "F"]:
        client.post("/api/v1/planner/syllabus/topics", headers=h,
                    json={"unit_id": unit["id"], "title": t, "est_periods": 4})
    client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h)
    # push the class behind with a 3-week exam block near the start
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": "Block",
        "start_date": "2026-04-13", "end_date": "2026-05-02"})

    ov = client.get("/api/v1/dashboard/overview", headers=h)
    assert ov.status_code == 200, ov.text
    data = ov.json()
    assert data["rag_amber"] + data["rag_red"] >= 1
    assert data["fees"] is not None  # director sees the fee card
    pace = [a for a in data["alerts"] if a["type"] == "pace"]
    assert pace, "expected a pace alert"

    # one-tap alert -> task lands work on a board
    board = client.post("/api/v1/boards", headers=h, json={"name": "Catch-up"}).json()
    task = client.post("/api/v1/dashboard/alerts/create-task", headers=h, json={
        "board_id": board["id"], "title": pace[0]["title"], "description": pace[0]["detail"]})
    assert task.status_code == 200, task.text
    assert task.json()["title"] == pace[0]["title"]


def test_digest_previews_top_issues(client, cleanup):
    h, year, klass, cs = _setup(client, cleanup)
    d = client.get("/api/v1/dashboard/digest", headers=h).json()
    assert "TrackBit" in d["text"] and isinstance(d["issues"], list)


def test_dashboard_is_admin_only(client, cleanup):
    h, _year, _klass, _cs = _setup(client, cleanup)
    inv = client.post("/api/v1/org/members/invite", headers=h,
                      json={"name": "Teach", "phone": "+919800007777", "role": "teacher"})
    cleanup["users"].append(uuid.UUID(inv.json()["user_id"]))
    token = inv.json()["invite_url"].rsplit("/join/", 1)[1]
    ch = {"Authorization": f"Bearer {client.post('/api/v1/auth/verify', json={'token': token}).json()['access_token']}"}
    # v2: teachers don't see the school dashboard at all; the admin does, fee card included
    assert client.get("/api/v1/dashboard/overview", headers=ch).status_code == 403
    cov = client.get("/api/v1/dashboard/overview", headers=h)
    assert cov.status_code == 200
    assert cov.json()["fees"] is not None
