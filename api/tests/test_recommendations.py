"""V2-P3: recommendations engine (daily checks from plan × bands), confirm +
exceptions, per-student homework (SPRD2 §5.4, §5.5)."""

import uuid

from sqlalchemy import select

from app.models import Intervention, Membership
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
                      json={"org_name": "Rec Org", "name": "Director", "email": email,
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
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Maths"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 5}).json()
    return h, year, klass, cs, reg["org"]["id"]


def _add_student(client, h, class_id, name, *, guardian_phone=None):
    guardians = [{"name": f"{name} parent", "phone": guardian_phone}] if guardian_phone else []
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name,
        "class_id": class_id, "guardians": guardians}).json()


def _make_term(client, h, year_id):
    return client.post("/api/v1/academics/terms", headers=h, json={
        "academic_year_id": year_id, "name": "Term 1",
        "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()


def test_checks_generate_with_zero_setup_and_cap(client, cleanup):
    """§5.5 Done-when: checks appear with zero teacher setup; class-wide capped ≤2."""
    h, _year, klass, cs, _org = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")

    got = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=h)
    assert got.status_code == 200, got.text
    body = got.json()
    class_wide = [c for c in body["checks"] if c["band_scope"] == "all"]
    assert 1 <= len(class_wide) <= 2  # cap enforced
    assert all(c["source"] == "ai" for c in body["checks"])
    # No C-band students → no C-scoped check.
    assert not any(c["band_scope"] == "C" for c in body["checks"])

    # Idempotent: a second GET does not duplicate the checks.
    again = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=h).json()
    assert len(again["checks"]) == len(body["checks"])


def test_c_band_students_get_the_richer_check(client, cleanup):
    h, year, klass, cs, org_id = _setup(client, cleanup)
    s = _add_student(client, h, klass["id"], "Bala")
    term = _make_term(client, h, year["id"])
    set_band = client.post("/api/v1/assessments/bands", headers=h, json={
        "student_id": s["id"], "term_id": term["id"], "tier": "C"})
    assert set_band.status_code == 200, set_band.text

    body = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=h).json()
    c_checks = [c for c in body["checks"] if c["band_scope"] == "C"]
    assert len(c_checks) == 1
    assert "one-on-one" in c_checks[0]["description"]
    # Class-wide still capped at 2 alongside the C-band check.
    assert len([c for c in body["checks"] if c["band_scope"] == "all"]) <= 2


def test_intervention_student_gets_one_targeted_check(client, cleanup):
    h, year, klass, cs, org_id = _setup(client, cleanup)
    s = _add_student(client, h, klass["id"], "Chetan")
    term = _make_term(client, h, year["id"])
    # Insert an active intervention directly (the board/task machinery is M5's job).
    db = AdminSession()
    try:
        db.add(Intervention(
            org_id=uuid.UUID(org_id),
            student_id=uuid.UUID(s["id"]), term_id=uuid.UUID(term["id"]),
            goal_text="Times tables to 12", target_tier="B", status="active"))
        db.commit()
    finally:
        db.close()

    body = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=h).json()
    targeted = [c for c in body["checks"] if c["student_id"] == s["id"]]
    assert len(targeted) == 1  # ≤ 1 per intervention student
    assert "Chetan" in targeted[0]["description"] and "Times tables" in targeted[0]["description"]


def test_confirm_class_did_it_then_exception(client, cleanup):
    h, _year, klass, cs, _org = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")
    _add_student(client, h, klass["id"], "Bala")
    body = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=h).json()
    check_id = body["checks"][0]["id"]

    # "Class did it ✓" — confirmed, no exception rows.
    ok = client.post(f"/api/v1/checks/{check_id}/confirm", headers=h, json={"exceptions": []})
    assert ok.status_code == 200, ok.text
    assert ok.json()["confirmed"] is True and ok.json()["results"] == []

    # Re-confirm with one deviation → a single check_result, full-replace.
    ex = client.post(f"/api/v1/checks/{check_id}/confirm", headers=h, json={
        "exceptions": [{"student_id": a["id"], "status": "not_done"}]})
    res = ex.json()["results"]
    assert len(res) == 1 and res[0]["status"] == "not_done" and res[0]["full_name"] == "Aisha"


def test_per_student_homework_notifies_only_that_student(client, cleanup):
    h, _year, klass, cs, _org = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha", guardian_phone="+911111111111")
    _add_student(client, h, klass["id"], "Bala", guardian_phone="+912222222222")

    # Whole-class homework → both guardians.
    whole = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Read page 10"})
    assert whole.json()["notified_count"] == 2

    # Per-student homework → only that student's guardian.
    one = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Extra practice sheet", "student_id": a["id"]})
    assert one.status_code == 200, one.text
    assert one.json()["student_id"] == a["id"] and one.json()["notified_count"] == 1


def test_checks_require_teaching_the_class(client, cleanup):
    h, _year, klass, cs, _org = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    r = client.get(f"/api/v1/checks?class_subject_id={cs['id']}", headers=th)
    assert r.status_code == 403
