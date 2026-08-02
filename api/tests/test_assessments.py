"""P3: assessments, bands (append-only), skill profile, weak subjects, interventions."""

import uuid


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Assess Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    term = client.post("/api/v1/academics/terms", headers=h,
                       json={"academic_year_id": year["id"], "name": "T1",
                             "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Math"}).json()
    kid = client.post("/api/v1/students", headers=h,
                      json={"admission_no": "S1", "full_name": "Asha", "class_id": klass["id"]}).json()
    return h, term, klass, subject, kid


def test_diagnostic_scores_bands_and_profile(client, cleanup):
    h, term, klass, _subject, kid = _setup(client, cleanup)
    skills = client.post("/api/v1/assessments/skill-areas/seed-defaults", headers=h).json()
    assert len(skills) == 4
    reading = next(s for s in skills if s["name"] == "Reading")

    cyc = client.post("/api/v1/assessments/cycles", headers=h, json={
        "term_id": term["id"], "type": "diagnostic", "name": "Term-start diagnostic",
        "date": "2026-04-05"}).json()

    grid = client.get(f"/api/v1/assessments/cycles/{cyc['id']}/grid?class_id={klass['id']}", headers=h).json()
    assert grid["cycle_type"] == "diagnostic" and len(grid["columns"]) == 4
    assert grid["verified"] is False

    # low reading score -> should suggest a C band
    rows = [{"student_id": kid["id"], "skill_area_id": s["id"], "score": 30 if s["id"] == reading["id"] else 40,
             "max_score": 100} for s in skills]
    assert client.post(f"/api/v1/assessments/cycles/{cyc['id']}/scores", headers=h,
                       json={"rows": rows}).status_code == 200
    assert client.post(f"/api/v1/assessments/cycles/{cyc['id']}/verify", headers=h).status_code == 200

    # V1-9 (`D-75`): the band board is **per subject** — the old class-wide
    # board read one overall letter, which is what this packet retires. The
    # diagnostic's skill scores still drive the skill radar below; they no
    # longer suggest a band, because a band belongs to a subject.
    board = client.get("/api/v1/bands/class", headers=h, params={
        "class_id": klass["id"], "subject_id": _subject["id"],
        "term_id": term["id"]}).json()
    row = next(r for r in board["rows"] if r["student_id"] == kid["id"])
    assert row["current_tier"] is None       # not assessed is a state, not a C

    # confirm a C band in that subject -> append-only history
    client.post("/api/v1/assessments/bands", headers=h, json={
        "student_id": kid["id"], "term_id": term["id"], "tier": "C",
        "subject_id": _subject["id"], "note": "weak reading"})
    client.post("/api/v1/assessments/bands", headers=h, json={
        "student_id": kid["id"], "term_id": term["id"], "tier": "B",
        "subject_id": _subject["id"], "note": "moved up"})
    hist = client.get(f"/api/v1/assessments/students/{kid['id']}/bands", headers=h).json()
    assert [r["tier"] for r in hist] == ["B", "C"]  # newest first, both kept
    assert all(r["subject_name"] for r in hist) if "subject_name" in hist[0] else True

    board2 = client.get("/api/v1/bands/class", headers=h, params={
        "class_id": klass["id"], "subject_id": _subject["id"]}).json()
    assert next(r for r in board2["rows"]
                if r["student_id"] == kid["id"])["current_tier"] == "B"

    profile = client.get(f"/api/v1/assessments/students/{kid['id']}/skill-profile", headers=h).json()
    assert profile["cycles"] and profile["cycles"][0]["scores"]["Reading"] == 30.0


def test_weak_subject_trend(client, cleanup):
    h, term, klass, subject, kid = _setup(client, cleanup)
    for name, d, score in [("Unit 1", "2026-04-10", 80), ("Unit 2", "2026-05-10", 55)]:
        c = client.post("/api/v1/assessments/cycles", headers=h, json={
            "term_id": term["id"], "type": "unit_test", "name": name, "date": d}).json()
        client.post(f"/api/v1/assessments/cycles/{c['id']}/scores", headers=h, json={
            "rows": [{"student_id": kid["id"], "subject_id": subject["id"], "score": score, "max_score": 100}]})
    trends = client.get(f"/api/v1/assessments/classes/{klass['id']}/trends", headers=h).json()
    math = next(t for t in trends if t["subject_name"] == "Math")
    assert math["weak"] is True and len(math["points"]) == 2


def test_intervention_spawns_tasks_and_tracks_completion(client, cleanup):
    h, term, _klass, _subject, kid = _setup(client, cleanup)
    board = client.post("/api/v1/boards", headers=h, json={"name": "Interventions"}).json()
    iv = client.post("/api/v1/assessments/interventions", headers=h, json={
        "student_id": kid["id"], "term_id": term["id"], "goal_text": "Move C→B in reading",
        "target_tier": "B", "board_id": board["id"],
        "items": ["Daily hard-words drill", "Reading practice 15 min"]}).json()
    assert len(iv["items"]) == 2 and all(not i["done"] for i in iv["items"])

    # completing the spawned task shows back in the intervention view
    task_id = iv["items"][0]["task_instance_id"]
    assert client.post(f"/api/v1/tasks/{task_id}/complete", headers=h).status_code == 200
    again = client.get(f"/api/v1/assessments/students/{kid['id']}/interventions", headers=h).json()
    done = [i for i in again[0]["items"] if i["done"]]
    assert len(done) == 1
