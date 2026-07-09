"""V2-P5: setup wizard — resumable state + progress derived from real data
(SPRD2 §5.1)."""

import uuid


def _register(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Wiz Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return {"Authorization": f"Bearer {reg['access_token']}"}


def test_wizard_state_progress_and_resume(client, cleanup):
    h = _register(client, cleanup)
    st = client.get("/api/v1/wizard/state", headers=h)
    assert st.status_code == 200, st.text
    body = st.json()
    assert body["current_step"] == 1 and body["status"] == "in_progress"
    assert body["total_steps"] == 10  # V2-P7 reorder: syllabus before exams
    assert body["progress"]["has_year"] is False and body["progress"]["classes"] == 0

    # write-through step 1: create a year via the real endpoint → progress reflects it
    client.post("/api/v1/academics/years", headers=h,
                json={"label": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"})
    after = client.get("/api/v1/wizard/state", headers=h).json()
    assert after["progress"]["has_year"] is True

    # advance + stash a per-step answer, then confirm it persists (resume after logout)
    adv = client.post("/api/v1/wizard/advance", headers=h,
                      json={"to_step": 4, "payload": {"note": "hi"}}).json()
    assert adv["current_step"] == 4 and adv["payload"]["note"] == "hi"
    resumed = client.get("/api/v1/wizard/state", headers=h).json()
    assert resumed["current_step"] == 4 and resumed["payload"]["note"] == "hi"

    done = client.post("/api/v1/wizard/complete", headers=h).json()
    assert done["status"] == "done"
    # reset reopens at step 1
    assert client.post("/api/v1/wizard/reset", headers=h).json()["current_step"] == 1


def test_wizard_is_admin_only(client, cleanup):
    h = _register(client, cleanup)
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    assert client.get("/api/v1/wizard/state", headers=th).status_code == 403
