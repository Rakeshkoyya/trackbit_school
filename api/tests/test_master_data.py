"""P0-C: master-data CRUD, role gating, and cross-org isolation (SPRD §4.2)."""

import uuid


def _register_admin(client, cleanup, *, org="Master Org", email=None):
    email = email or f"admin-{uuid.uuid4().hex[:12]}@example.com"
    resp = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": org, "name": "Director", "email": email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return body


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _make_year(client, h, label="2026-27"):
    r = client.post("/api/v1/academics/years", headers=h,
                    json={"label": label, "start_date": "2026-04-01", "end_date": "2027-03-31"})
    assert r.status_code == 200, r.text
    return r.json()


def test_academic_and_roster_flow(client, cleanup):
    admin = _register_admin(client, cleanup)
    h = _h(admin["access_token"])

    year = _make_year(client, h)
    assert year["is_active"] is True  # first year is auto-activated

    # duplicate label -> 409
    dup = client.post("/api/v1/academics/years", headers=h,
                      json={"label": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"})
    assert dup.status_code == 409

    # end before start -> 422 (schema validator)
    bad = client.post("/api/v1/academics/years", headers=h,
                      json={"label": "bad", "start_date": "2027-04-01", "end_date": "2026-04-01"})
    assert bad.status_code == 422

    term = client.post("/api/v1/academics/terms", headers=h,
                       json={"academic_year_id": year["id"], "name": "Term 1",
                             "start_date": "2026-04-01", "end_date": "2026-09-30"})
    assert term.status_code == 200, term.text

    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Mathematics"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "B"}).json()

    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"], "periods_per_week": 5})
    assert cs.status_code == 200, cs.text
    assert cs.json()["subject_name"] == "Mathematics"
    assert cs.json()["periods_per_week"] == 5

    # same subject twice on a class -> 409
    again = client.post("/api/v1/academics/class-subjects", headers=h,
                        json={"class_id": klass["id"], "subject_id": subject["id"]})
    assert again.status_code == 409

    # category + student with inline guardian
    cat = client.post("/api/v1/students/categories", headers=h, json={"name": "Day Scholar"}).json()
    st = client.post("/api/v1/students", headers=h, json={
        "admission_no": "A100", "full_name": "Asha Rao", "class_id": klass["id"],
        "category_id": cat["id"],
        "guardians": [{"name": "Ravi Rao", "phone": "+919800001234", "is_primary": True}],
    })
    assert st.status_code == 200, st.text
    detail = st.json()
    assert detail["class_label"] == "6-B"
    assert detail["category_name"] == "Day Scholar"
    assert len(detail["guardians"]) == 1 and detail["guardians"][0]["is_primary"] is True

    # duplicate admission_no -> 409
    dup_adm = client.post("/api/v1/students", headers=h,
                          json={"admission_no": "A100", "full_name": "Someone Else"})
    assert dup_adm.status_code == 409

    # search finds her
    found = client.get("/api/v1/students?q=Asha", headers=h)
    assert found.status_code == 200 and len(found.json()) == 1


def test_teacher_cannot_write_master_data(client, cleanup):
    admin = _register_admin(client, cleanup)
    h = _h(admin["access_token"])
    inv = client.post("/api/v1/org/members/invite", headers=h,
                      json={"name": "Teacher", "phone": "+919811112222", "role": "teacher"})
    cleanup["users"].append(uuid.UUID(inv.json()["user_id"]))
    token = inv.json()["invite_url"].rsplit("/join/", 1)[1]
    th = _h(client.post("/api/v1/auth/verify", json={"token": token}).json()["access_token"])

    # teacher may READ the structure ...
    assert client.get("/api/v1/academics/years", headers=th).status_code == 200
    # ... but not create it (coordinator/director only)
    blocked = client.post("/api/v1/academics/years", headers=th,
                          json={"label": "2027-28", "start_date": "2027-04-01", "end_date": "2028-03-31"})
    assert blocked.status_code == 403


def test_students_are_org_isolated(client, cleanup):
    a = _register_admin(client, cleanup, org="Org A")
    b = _register_admin(client, cleanup, org="Org B")
    ha, hb = _h(a["access_token"]), _h(b["access_token"])

    sid = client.post("/api/v1/students", headers=ha,
                      json={"admission_no": "A1", "full_name": "Only In A"}).json()["id"]

    # Org B cannot see or fetch Org A's student.
    assert client.get("/api/v1/students", headers=hb).json() == []
    assert client.get(f"/api/v1/students/{sid}", headers=hb).status_code == 404
