"""P1-B/C: syllabus → draft → approve → forecast (SPRD §5.1 done-when).

Key invariant: adding a mid-year event shifts the *projected* finish of affected
class-subjects WITHOUT mutating the approved baseline rows (P2)."""

import uuid


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Plan Org", "name": "Director", "email": email,
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


def test_syllabus_split_is_heuristic():
    from app.services.planner import PlannerService
    units = PlannerService(None).split_text("Chapter 1: Plants\nRoots\nLeaves\nChapter 2: Animals\nMammals")
    assert [u.title for u in units] == ["Plants", "Animals"]  # text after the colon
    assert units[0].topics == ["Roots", "Leaves"]
    assert units[1].topics == ["Mammals"]


def test_plan_draft_approve_and_forecast_shift(client, cleanup):
    h, year, klass, cs = _setup(client, cleanup)

    # syllabus: one unit, several topics
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Unit 1"}).json()
    for t in ["Cells", "Tissues", "Organs", "Systems", "Ecology", "Genetics"]:
        client.post("/api/v1/planner/syllabus/topics", headers=h,
                    json={"unit_id": unit["id"], "title": t, "est_periods": 4})

    # draft → entries produced across weeks
    draft = client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=h)
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"
    assert len(draft.json()["entries"]) == 6

    # approve (director only) → baseline locked
    approved = client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h).json()
    assert approved["status"] == "approved"
    baseline_finish = approved["entries"][-1]["week_start"]

    # forecast at approval time: on track (green)
    fc = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    assert fc[0]["status"] == "green" and fc[0]["weeks_behind"] == 0

    # insert a 3-week event mid-year → projected finish shifts later, baseline unchanged
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": "Long block",
        "start_date": "2026-04-13", "end_date": "2026-05-02"})
    fc2 = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    assert fc2[0]["weeks_behind"] >= 1
    assert fc2[0]["status"] in ("amber", "red")

    # baseline rows are untouched (P2) — the plan's stored last week is the same
    plan = client.get(f"/api/v1/planner/plan?class_subject_id={cs['id']}", headers=h).json()
    assert plan["entries"][-1]["week_start"] == baseline_finish


def test_approve_requires_director(client, cleanup):
    h, _year, _klass, cs = _setup(client, cleanup)
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "U"}).json()
    client.post("/api/v1/planner/syllabus/topics", headers=h,
                json={"unit_id": unit["id"], "title": "T", "est_periods": 2})
    client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=h)

    inv = client.post("/api/v1/org/members/invite", headers=h,
                      json={"name": "Teach", "phone": "+919800005555", "role": "teacher"})
    cleanup["users"].append(uuid.UUID(inv.json()["user_id"]))
    token = inv.json()["invite_url"].rsplit("/join/", 1)[1]
    ch = {"Authorization": f"Bearer {client.post('/api/v1/auth/verify', json={'token': token}).json()['access_token']}"}
    # v2: teachers can view plans but neither draft nor approve (admin-only)
    assert client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=ch).status_code == 403
    assert client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=ch).status_code == 403
    # the admin can approve
    assert client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h).status_code == 200
