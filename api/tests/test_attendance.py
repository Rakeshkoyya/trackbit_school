"""V2-P2: per-period attendance (capture-by-exception), absence alerts, My Day v2
period card (SPRD2 §4.4, §5.4, §7)."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import AttendanceException, AttendanceMark, Membership
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
                      json={"org_name": "Att Org", "name": "Director", "email": email,
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
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 5}).json()
    return h, year, mid, klass, cs


def _add_student(client, h, class_id, name, *, guardian_phone=None, opt_out=False):
    guardians = ([{"name": f"{name} parent", "phone": guardian_phone, "notify_opt_out": opt_out}]
                 if guardian_phone else [])
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name,
        "class_id": class_id, "guardians": guardians}).json()


def _marks(class_id):
    db = AdminSession()
    try:
        return db.query(AttendanceMark).filter(
            AttendanceMark.class_id == uuid.UUID(class_id)).count()
    finally:
        db.close()


def _exceptions(class_id):
    db = AdminSession()
    try:
        return (db.query(AttendanceException)
                .join(AttendanceMark, AttendanceMark.id == AttendanceException.mark_id)
                .filter(AttendanceMark.class_id == uuid.UUID(class_id)).count())
    finally:
        db.close()


def test_all_present_then_exception_is_capture_by_exception(client, cleanup):
    h, _year, _mid, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")
    _b = _add_student(client, h, klass["id"], "Bala")
    _c = _add_student(client, h, klass["id"], "Chetan")

    # "All present ✓" — one mark, zero exception rows.
    r = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"], "exceptions": []})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["roster_count"] == 3
    assert body["present_count"] == 3 and body["absent_count"] == 0
    assert _marks(klass["id"]) == 1 and _exceptions(klass["id"]) == 0

    # Re-mark the same period with one absentee → present derived, one exception row.
    r2 = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["present_count"] == 2 and b2["absent_count"] == 1
    # Idempotent re-capture: still one mark, exception set replaced (not appended).
    assert _marks(klass["id"]) == 1 and _exceptions(klass["id"]) == 1

    # Roster sheet reflects the current exception state.
    sheet = client.get(
        f"/api/v1/attendance/roster?class_id={klass['id']}&period_no=1", headers=h).json()
    assert sheet["marked"] is True and sheet["present_count"] == 2
    statuses = {row["full_name"]: row["status"] for row in sheet["roster"]}
    assert statuses["Aisha"] == "absent" and statuses["Bala"] is None


def test_late_student_is_present_but_flagged(client, cleanup):
    h, _year, _mid, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha")
    _add_student(client, h, klass["id"], "Bala")
    r = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 2, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "late", "late_minutes": 10}]})
    body = r.json()
    assert body["present_count"] == 2  # late counts as present
    assert body["late_count"] == 1 and body["absent_count"] == 0


def test_first_marked_period_fires_absence_alerts_once(client, cleanup):
    h, _year, _mid, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha", guardian_phone="+911111111111")
    _add_student(client, h, klass["id"], "Bala", guardian_phone="+912222222222")

    # First marked period with an absentee → that student's guardian is alerted.
    r1 = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert r1.json()["alerted_count"] == 1

    # A later period is NOT the first — no alerts even with an absentee.
    r2 = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 2, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert r2.json()["alerted_count"] == 0

    # Re-marking the first period does not re-alert (idempotent, alerted_at set).
    r3 = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert r3.json()["alerted_count"] == 0


def test_opt_out_guardian_not_alerted(client, cleanup):
    h, _year, _mid, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha",
                     guardian_phone="+913333333333", opt_out=True)
    r = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert r.json()["alerted_count"] == 0


def test_my_day_period_card_end_to_end(client, cleanup):
    """§5.4 Done-when: a fully-confirmed period writes 1 attendance_mark + exceptions,
    1 lesson_log, homework rows — and My Day reflects the state."""
    h, _year, _mid, klass, cs = _setup(client, cleanup)
    a = _add_student(client, h, klass["id"], "Aisha", guardian_phone="+914444444444")
    _add_student(client, h, klass["id"], "Bala")

    # Put this class-subject on today's timetable so it shows on My Day.
    wd = datetime.now(ZoneInfo("Asia/Kolkata")).date().weekday()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": wd, "period_no": 3, "class_subject_id": cs["id"]})

    day0 = client.get("/api/v1/classroom/my-day", headers=h).json()
    p0 = next(p for p in day0["periods"] if p["period_no"] == 3)
    assert p0["attendance_marked"] is False and p0["roster_count"] == 2
    assert p0["class_id"] == klass["id"] and p0["logged"] is False

    # Confirm the card: attendance (one absentee) + lesson log + homework.
    mark = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "period_no": 3, "class_subject_id": cs["id"],
        "exceptions": [{"student_id": a["id"], "status": "absent"}]})
    assert mark.status_code == 200, mark.text
    log = client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "coverage": "full"})
    assert log.status_code == 200, log.text
    hw = client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Read chapter 4"})
    assert hw.status_code == 200, hw.text

    day1 = client.get("/api/v1/classroom/my-day", headers=h).json()
    p1 = next(p for p in day1["periods"] if p["period_no"] == 3)
    assert p1["attendance_marked"] is True
    assert p1["present_count"] == 1 and p1["absent_count"] == 1
    assert p1["logged"] is True
    assert _marks(klass["id"]) == 1 and _exceptions(klass["id"]) == 1


def test_mark_requires_teaching_the_class(client, cleanup):
    """A teacher who doesn't teach the class cannot mark its attendance (SPRD2 §2)."""
    h, _year, _mid, klass, _cs = _setup(client, cleanup)
    _add_student(client, h, klass["id"], "Aisha")
    # A second teacher who teaches nothing in this class.
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.post("/api/v1/attendance/mark", headers=th, json={
        "class_id": klass["id"], "period_no": 1, "exceptions": []})
    assert r.status_code == 403
