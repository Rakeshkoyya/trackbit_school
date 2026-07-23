"""Mid-year adoption (tracking_start_date) + partial-term planning.

The school started in April; TrackBit arrived in July. Everything before the
tracking floor is "before our time": pre-tracking terms are excluded from the
forecast, planning windows clamp to the floor, and a partially-planned term is
a first-class state — approve what's scheduled, size the rest as the term
unfolds, extend the plan without touching the locked baseline.
"""

import uuid

TRACKING_START = "2026-07-15"


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Midyear School", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31",
                             "tracking_start_date": TRACKING_START}).json()
    t1 = client.post("/api/v1/academics/terms", headers=h,
                     json={"academic_year_id": year["id"], "name": "Term 1",
                           "start_date": "2026-04-01", "end_date": "2026-06-30"}).json()
    t2 = client.post("/api/v1/academics/terms", headers=h,
                     json={"academic_year_id": year["id"], "name": "Term 2",
                           "start_date": "2026-07-01", "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "periods_per_week": 5}).json()

    def unit(title, term_id, topics):
        u = client.post("/api/v1/planner/syllabus/units", headers=h,
                        json={"class_subject_id": cs["id"], "title": title,
                              "term_id": term_id}).json()
        made = [client.post("/api/v1/planner/syllabus/topics", headers=h,
                            json={"unit_id": u["id"], "title": t, "est_periods": est}).json()
                for t, est in topics]
        return u, made

    return h, year, t1, t2, klass, cs, unit


def test_pre_tracking_term_is_out_of_bounds(client, cleanup):
    h, _year, t1, _t2, _klass, cs, unit = _setup(client, cleanup)
    unit("Taught before TrackBit", t1["id"], [("Old chapter", 4)])

    # Planning a term that ended before the floor is refused with a clear reason.
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/draft?term_id={t1['id']}", headers=h)
    assert r.status_code == 422, r.text
    assert "before" in r.json()["error"]["message"].lower()

    # And the plan screen marks it as before-our-time.
    plan = client.get(f"/api/v1/planner/plan?class_subject_id={cs['id']}", headers=h).json()
    row = next(t for t in plan["terms"] if t["term_id"] == t1["id"])
    assert row["pre_tracking"] is True


def test_partial_term_forecast_and_extend(client, cleanup):
    h, _year, t1, t2, klass, cs, unit = _setup(client, cleanup)
    unit("Taught before TrackBit", t1["id"], [("Old chapter", None)])
    _u2, known = unit("Light", t2["id"], [("Reflection", 3), ("Refraction", 3)])
    _u3, later = unit("Sound", t2["id"], [("Waves", None)])

    # Draft + approve Term 2 with one chapter still unsized — allowed now:
    # partial is a state, not an error.
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/draft?term_id={t2['id']}", headers=h)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t2['id']}", headers=h)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["status"] == "approved"  # every bucket with topics… T1 has topics!
    baseline = {e["topic_id"]: e["week_start"] for e in plan["entries"]}
    assert set(baseline) == {known[0]["id"], known[1]["id"]}

    # Forecast: pre-tracking Term 1 chapters are out of every number; the planned
    # portion gets a real RAG; the unsized Term-2 chapter rides along as info.
    fc = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    row = next(f for f in fc if f["class_subject_id"] == cs["id"])
    assert row["status"] in ("green", "amber", "red")  # a colour, not "unplanned"
    assert row["total_topics"] == 3  # 2 known + 1 later; T1's chapter excluded
    assert row["planned_topics"] == 2
    assert row["unestimated_topics"] == 1
    assert row["current_term_unplanned"] is False

    # Mid-term the school sizes the next chapter — allowed under the lock because
    # it was never sized — and extends the plan without moving the baseline.
    r = client.put(f"/api/v1/planner/syllabus/topics/{later[0]['id']}/estimate",
                   headers=h, json={"est_periods": 4})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/extend?term_id={t2['id']}", headers=h)
    assert r.status_code == 200, r.text
    extended = {e["topic_id"]: e["week_start"] for e in r.json()["entries"]}
    assert extended[later[0]["id"]] > max(baseline.values())  # appended after
    for tid, wk in baseline.items():
        assert extended[tid] == wk  # locked entries untouched (P2)

    # Re-sizing an ALREADY-sized chapter under the lock is still refused.
    r = client.put(f"/api/v1/planner/syllabus/topics/{known[0]['id']}/estimate",
                   headers=h, json={"est_periods": 9})
    assert r.status_code == 422
    assert "approved" in r.json()["error"]["message"].lower()


def test_wholly_unscheduled_subject_stays_unplanned(client, cleanup):
    h, _year, _t1, t2, klass, cs, unit = _setup(client, cleanup)
    unit("Sound", t2["id"], [("Waves", None)])

    # Nothing drafted: no colour, and the running term is flagged as planless.
    fc = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    row = next(f for f in fc if f["class_subject_id"] == cs["id"])
    assert row["status"] == "unplanned"
    assert row["current_term_unplanned"] is True

    # Approving an empty window is refused — locking nothing is a lie.
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/draft?term_id={t2['id']}", headers=h)
    assert r.status_code == 200  # draft succeeds (no sized topics → no entries)
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t2['id']}", headers=h)
    assert r.status_code == 422
    assert "scheduled" in r.json()["error"]["message"].lower()
