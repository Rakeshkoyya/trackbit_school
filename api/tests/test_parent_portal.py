"""Parent portal: phone-OTP login, curated child views, P4 leak tests.

Parents are not memberships — a parent session is minted from a guardian phone
match and stays valid only while the guardian link is live. The projection
layer must never emit bands, skills, observations or check flags (founder
decision 2026-07-23: curated only).
"""

import uuid

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession

DATE = "2026-08-03"  # Monday (weekday 0)


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _phone():
    """A unique fake Indian mobile per test — last-10-digit matching is the key."""
    return "+919" + str(uuid.uuid4().int)[:9]


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "PP Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "English"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 5}).json()
    return h, year, klass, cs


def _add_student(client, h, class_id, name, phone):
    s = client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name, "class_id": class_id}).json()
    g = client.post(f"/api/v1/students/{s['id']}/guardians", headers=h, json={
        "name": f"{name}'s Father", "relation": "Father", "phone": phone,
        "is_primary": True})
    assert g.status_code == 200, g.text
    return s


def _login_parent(client, monkeypatch, phone):
    """Run the OTP round-trip, capturing the code instead of sending it."""
    sent = {}
    monkeypatch.setattr("app.services.parent_auth.send_otp",
                        lambda p, c: sent.update(code=c) or "stub")
    r = client.post("/api/v1/parent/auth/request-otp", json={"phone": phone})
    assert r.status_code == 200, r.text
    v = client.post("/api/v1/parent/auth/verify-otp",
                    json={"phone": phone, "code": sent["code"]})
    assert v.status_code == 200, v.text
    body = v.json()
    cleanup_user = uuid.UUID(body["user"]["id"])
    return {"Authorization": f"Bearer {body['access_token']}"}, body, cleanup_user


def test_otp_flow_children_and_session(client, cleanup, monkeypatch):
    h, _year, klass, _cs = _setup(client, cleanup)
    phone = _phone()
    s = _add_student(client, h, klass["id"], "Aisha", phone)

    # Unregistered numbers are told so (rate-limited surface, explicit UX).
    r = client.post("/api/v1/parent/auth/request-otp", json={"phone": "+919000000001"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "phone_not_registered"

    # Wrong code fails; the right one signs in — matching ignores +91 formatting.
    sent = {}
    monkeypatch.setattr("app.services.parent_auth.send_otp",
                        lambda p, c: sent.update(code=c) or "stub")
    bare = phone.removeprefix("+91")  # parent types the bare 10 digits
    assert client.post("/api/v1/parent/auth/request-otp",
                       json={"phone": bare}).status_code == 200
    bad = client.post("/api/v1/parent/auth/verify-otp",
                      json={"phone": bare, "code": "000000"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "otp_incorrect"
    ok = client.post("/api/v1/parent/auth/verify-otp",
                     json={"phone": bare, "code": sent["code"]})
    assert ok.status_code == 200, ok.text
    session = ok.json()
    assert session["org_role"] == "parent"
    cleanup["users"].append(uuid.UUID(session["user"]["id"]))
    ph = {"Authorization": f"Bearer {session['access_token']}"}

    # /parent/me lists the child; /auth/me works so the web shell can hydrate.
    me = client.get("/api/v1/parent/me", headers=ph).json()
    assert [c["full_name"] for c in me["children"]] == ["Aisha"]
    assert me["children"][0]["class_label"] == "6-A"
    auth_me = client.get("/api/v1/auth/me", headers=ph)
    assert auth_me.status_code == 200 and auth_me.json()["org_role"] == "parent"

    # Parent tokens never reach staff endpoints; staff tokens never reach parent ones.
    assert client.get("/api/v1/students", headers=ph).status_code == 401
    staff_hit = client.get(f"/api/v1/parent/children/{s['id']}/today", headers=h)
    assert staff_hit.status_code == 401
    assert staff_hit.json()["error"]["code"] == "not_parent"

    # Refresh continues the parent session (no membership behind it).
    ref = client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert ref.status_code == 200 and ref.json()["org_role"] == "parent"


def test_otp_lockout_after_max_attempts(client, cleanup, monkeypatch):
    h, _year, klass, _cs = _setup(client, cleanup)
    phone = _phone()
    _add_student(client, h, klass["id"], "Bala", phone)
    sent = {}
    monkeypatch.setattr("app.services.parent_auth.send_otp",
                        lambda p, c: sent.update(code=c) or "stub")
    assert client.post("/api/v1/parent/auth/request-otp",
                       json={"phone": phone}).status_code == 200
    for _ in range(5):
        client.post("/api/v1/parent/auth/verify-otp", json={"phone": phone, "code": "999999"})
    # Even the correct code is refused once locked.
    r = client.post("/api/v1/parent/auth/verify-otp",
                    json={"phone": phone, "code": sent["code"]})
    assert r.status_code == 401 and r.json()["error"]["code"] == "otp_locked"


def test_today_view_daily_status_and_content(client, cleanup, monkeypatch):
    h, _year, klass, cs = _setup(client, cleanup)
    phone = _phone()
    s = _add_student(client, h, klass["id"], "Aisha", phone)

    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Grammar"}).json()
    topic = client.post("/api/v1/planner/syllabus/topics", headers=h,
                        json={"unit_id": unit["id"], "title": "Nouns", "est_periods": 2}).json()
    for period_no in (1, 2):
        client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": klass["id"], "weekday": 0, "period_no": period_no,
            "class_subject_id": cs["id"], "effective_from": "2026-04-01"})
    # P1 marked with Aisha absent; P2 all present; topic logged; homework set.
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": [{"student_id": s["id"], "status": "absent"}]})
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 2, "class_subject_id": cs["id"], "date": DATE,
        "exceptions": []})
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topic["id"], "coverage": "full",
        "period_no": 2, "date": DATE})
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Read chapter 1", "date": DATE})

    ph, _session, parent_uid = _login_parent(client, monkeypatch, phone)
    cleanup["users"].append(parent_uid)
    r = client.get(f"/api/v1/parent/children/{s['id']}/today?on_date={DATE}", headers=ph)
    assert r.status_code == 200, r.text
    body = r.json()
    # One absent period out of two marked = partial day, not a per-period feed.
    assert body["status"] == "partial"
    assert body["marked_periods"] == 2 and body["absent_periods"] == 1
    assert body["taught"] == [{"subject_name": "English", "topic": "Nouns"}]
    assert any("Read chapter 1" in hw["text"] for hw in body["homework"])
    # No per-period attendance states anywhere in the payload.
    assert "periods" not in body


def test_report_is_curated_no_band_leak(client, cleanup, monkeypatch):
    """P4: the parent report carries progress but never bands, skills,
    observations or check flags — even when all of them exist for the child."""
    h, year, klass, cs = _setup(client, cleanup)
    phone = _phone()
    s = _add_student(client, h, klass["id"], "Aisha", phone)
    other = _add_student(client, h, klass["id"], "Zoya", _phone())

    # Give the student staff-only signals: a band and an observation.
    term = client.post("/api/v1/academics/terms", headers=h, json={
        "academic_year_id": year["id"], "name": "Term 1",
        "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()
    band = client.post("/api/v1/assessments/bands", headers=h, json={
        "student_id": s["id"], "term_id": term["id"], "tier": "C",
        "note": "needs support"})
    assert band.status_code == 200, band.text
    client.put("/api/v1/classroom/observations", headers=h, json={
        "class_subject_id": cs["id"], "section": "Vocabulary", "period_no": 1,
        "concepts": [{"concept": "Reading",
                      "students": [{"student_id": s["id"], "rating": "needs_work"}]}]})

    ph, _session, parent_uid = _login_parent(client, monkeypatch, phone)
    cleanup["users"].append(parent_uid)
    r = client.get(f"/api/v1/parent/children/{s['id']}/report", headers=ph)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Aisha"
    # The projection is an allowlist — these keys must not exist at any level.
    assert "band" not in body and "band_history" not in body and "skills" not in body
    for subj in body["subjects"]:
        assert "observations" not in subj and "checks_flagged" not in subj

    # Cross-parent isolation: another family's child is unreachable.
    denied = client.get(f"/api/v1/parent/children/{other['id']}/report", headers=ph)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "not_your_child"


def test_optional_credentials_then_password_login(client, cleanup, monkeypatch):
    h, _year, klass, _cs = _setup(client, cleanup)
    phone = _phone()
    _add_student(client, h, klass["id"], "Bala", phone)
    ph, session, parent_uid = _login_parent(client, monkeypatch, phone)
    cleanup["users"].append(parent_uid)

    uname = f"p{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/parent/auth/credentials", headers=ph, json={
        "username": uname, "password": "parentpass1"})
    assert r.status_code == 200, r.text

    # Username+password and phone+password both land back in a parent session.
    for identifier in (uname, phone):
        login = client.post("/api/v1/auth/login",
                            json={"identifier": identifier, "password": "parentpass1"})
        assert login.status_code == 200, login.text
        assert login.json()["org_role"] == "parent"
        assert login.json()["user"]["id"] == session["user"]["id"]
