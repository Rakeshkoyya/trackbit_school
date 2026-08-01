"""HW-1: per-student homework capture, analytics, and the parent view.

The distinctions this suite exists to protect:

  * **not-checked is not all-done.** A teacher who never checks must not read as
    a class with perfect completion — that was the whole defect in the old count.
  * **not-checked is never the student's miss.** It appears in its own bucket and
    is excluded from a student's completion, on staff surfaces and parent ones.
  * exception capture: no rows for the students who did it; counts are derived,
    so the existing dashboard chart keeps working.
  * full replace, so a mis-tap is fixed by re-submitting.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import HomeworkCheck, HomeworkResult, Membership
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
                      json={"org_name": "HW Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Mathematics"}).json()

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    teacher_mid = str(_membership_id(cred["user_id"], reg["org"]["id"]))

    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": teacher_mid, "periods_per_week": 5}).json()
    return h, th, klass, cs


def _student(client, h, class_id, name, phone=None):
    guardians = ([{"name": f"{name} parent", "phone": phone, "is_primary": True}]
                 if phone else [])
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": name,
        "class_id": class_id, "guardians": guardians}).json()


def _homework(client, h, cs_id, text, on=None, due=None, student_id=None):
    body = {"class_subject_id": cs_id, "text": text}
    if on:
        body["date"] = on
    if due:
        body["due_date"] = due
    if student_id:
        body["student_id"] = student_id
    return client.post("/api/v1/classroom/homework", headers=h, json=body).json()


def _rows(assignment_id) -> int:
    db = AdminSession()
    try:
        return db.query(HomeworkResult).filter(
            HomeworkResult.assignment_id == uuid.UUID(assignment_id)).count()
    finally:
        db.close()


# ── capture ──────────────────────────────────────────────────────────────────
def test_unchecked_homework_is_not_full_completion(client, cleanup):
    """The defect the old count had: no check at all looked like everyone did it."""
    h, _th, klass, cs = _setup(client, cleanup)
    for n in ("Aisha", "Bala", "Chandra"):
        _student(client, h, klass["id"], n)
    hw = _homework(client, h, cs["id"], "Exercise 4.2")

    sheet = client.get(f"/api/v1/classroom/homework/{hw['id']}/sheet", headers=h).json()
    assert sheet["checked"] is False
    assert len(sheet["roster"]) == 3
    # Every row reads `done` for the capture sheet's convenience, but `checked`
    # is what any report must consult — nobody has looked at this yet.
    assert sheet["done_count"] == 3 and sheet["not_done_count"] == 0
    assert _rows(hw["id"]) == 0

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    assert ov["assigned"] == 1 and ov["checked"] == 0
    assert ov["check_rate"] == 0.0
    # Nothing was checked, so there is no completion figure to report — not 100%.
    assert ov["overall_completion"] is None


def test_exception_capture_derives_counts_and_replaces(client, cleanup):
    h, _th, klass, cs = _setup(client, cleanup)
    a = _student(client, h, klass["id"], "Aisha")
    b = _student(client, h, klass["id"], "Bala")
    _student(client, h, klass["id"], "Chandra")
    hw = _homework(client, h, cs["id"], "Exercise 4.2")

    # "Everyone did it" writes no per-student rows at all (P1v2).
    out = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h,
                      json={"results": []}).json()
    assert out["checked"] is True and out["done_count"] == 3
    assert _rows(hw["id"]) == 0

    out = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h, json={
        "results": [{"student_id": a["id"], "status": "not_done", "note": "No book"},
                    {"student_id": b["id"], "status": "partial"}]}).json()
    assert out["done_count"] == 1 and out["not_done_count"] == 1 and out["partial_count"] == 1
    assert _rows(hw["id"]) == 2
    row = next(r for r in out["roster"] if r["student_id"] == a["id"])
    assert row["status"] == "not_done" and row["note"] == "No book"

    # The derived cache the existing dashboard chart reads stays correct.
    db = AdminSession()
    try:
        chk = db.scalar(select(HomeworkCheck).where(
            HomeworkCheck.assignment_id == uuid.UUID(hw["id"])))
        assert chk.total_count == 3 and chk.done_count == 1
        assert chk.checked_by_member_id is not None
    finally:
        db.close()

    # Full replace: correcting a mis-tap removes the row, never accumulates.
    out = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h,
                      json={"results": [{"student_id": a["id"], "status": "not_done"}]}).json()
    assert out["done_count"] == 2 and _rows(hw["id"]) == 1


def test_per_student_homework_has_a_roster_of_one(client, cleanup):
    h, _th, klass, cs = _setup(client, cleanup)
    a = _student(client, h, klass["id"], "Aisha")
    b = _student(client, h, klass["id"], "Bala")
    hw = _homework(client, h, cs["id"], "Extra reading", student_id=a["id"])

    sheet = client.get(f"/api/v1/classroom/homework/{hw['id']}/sheet", headers=h).json()
    assert [r["student_id"] for r in sheet["roster"]] == [a["id"]]

    # A student it wasn't set for cannot be flagged on it.
    out = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h, json={
        "results": [{"student_id": b["id"], "status": "not_done"}]}).json()
    assert out["not_done_count"] == 0 and _rows(hw["id"]) == 0


# ── analytics ────────────────────────────────────────────────────────────────
def test_overview_names_repeat_offenders_and_unchecking_teachers(client, cleanup):
    h, _th, klass, cs = _setup(client, cleanup)
    a = _student(client, h, klass["id"], "Aisha")
    _student(client, h, klass["id"], "Bala")
    today = date.today()

    # Two days running, Aisha doesn't do it.
    for back in (2, 1):
        d = (today - timedelta(days=back)).isoformat()
        hw = _homework(client, h, cs["id"], f"Sums {back}", on=d, due=d)
        client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=h,
                    json={"results": [{"student_id": a["id"], "status": "not_done"}]})
    # A third, set and overdue, that nobody ever checked.
    stale = (today - timedelta(days=3)).isoformat()
    _homework(client, h, cs["id"], "Never checked", on=stale, due=stale)

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    assert ov["assigned"] == 3 and ov["checked"] == 2

    flagged = {s["full_name"]: s for s in ov["needs_attention"]}
    assert "Aisha" in flagged and flagged["Aisha"]["streak"] == 2
    assert "Mathematics" in flagged["Aisha"]["subjects"]
    assert "Bala" not in flagged
    assert "Bala" in {s["full_name"] for s in ov["perfect"]}

    teacher = ov["teachers"][0]
    assert teacher["assigned"] == 3 and teacher["checked"] == 2
    # Only the OVERDUE unchecked one counts against them.
    assert teacher["unchecked_overdue"] == 1

    # Class and subject roll-ups agree with the totals.
    assert ov["by_class"][0]["key"] == "6-A"
    assert ov["by_subject"][0]["key"] == "Mathematics"
    assert ov["by_class"][0]["not_done"] == 2


def test_student_history_separates_not_checked_from_missed(client, cleanup):
    h, _th, klass, cs = _setup(client, cleanup)
    a = _student(client, h, klass["id"], "Aisha")
    today = date.today()

    missed = _homework(client, h, cs["id"], "Missed one",
                       on=(today - timedelta(days=1)).isoformat())
    client.post(f"/api/v1/classroom/homework/{missed['id']}/check", headers=h,
                json={"results": [{"student_id": a["id"], "status": "not_done"}]})
    _homework(client, h, cs["id"], "Nobody looked", on=today.isoformat())

    hist = client.get(f"/api/v1/homework/student/{a['id']}", headers=h).json()
    assert hist["assigned"] == 2
    assert hist["not_done"] == 1 and hist["not_checked"] == 1 and hist["done"] == 0
    # Completion is over what was actually graded — the unchecked one is excluded
    # rather than counted against her.
    assert hist["completion"] == 0.0
    statuses = {i["text"]: i["status"] for i in hist["items"]}
    assert statuses["Missed one"] == "not_done"
    assert statuses["Nobody looked"] == "not_checked"


def test_teacher_cannot_read_a_student_they_dont_teach(client, cleanup):
    h, th, klass, _cs = _setup(client, cleanup)
    other = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": client.get("/api/v1/academics/years", headers=h).json()[0]["id"],
        "name": "9", "section": "C"}).json()
    outsider = _student(client, h, other["id"], "Not mine")
    mine = _student(client, h, klass["id"], "Mine")

    assert client.get(f"/api/v1/homework/student/{outsider['id']}", headers=th).status_code == 403
    assert client.get(f"/api/v1/homework/student/{mine['id']}", headers=th).status_code == 200
    # The school-wide report is the admin's.
    assert client.get("/api/v1/homework/overview", headers=th).status_code == 403


# ── the parent view ──────────────────────────────────────────────────────────
def test_parent_sees_yesterdays_verdict_and_pending_work(client, cleanup, monkeypatch):
    """The two questions the portal exists to answer, and the one thing it must
    never do: report the teacher's missing check as the child's miss."""
    h, _th, klass, cs = _setup(client, cleanup)
    phone = f"+9198{uuid.uuid4().int % 10**8:08d}"
    kid = _student(client, h, klass["id"], "Aisha", phone=phone)
    today = date.today()
    yest = (today - timedelta(days=1)).isoformat()

    done = _homework(client, h, cs["id"], "Did this one", on=yest, due=yest)
    client.post(f"/api/v1/classroom/homework/{done['id']}/check", headers=h,
                json={"results": []})
    missed = _homework(client, h, cs["id"], "Skipped this one", on=yest, due=yest)
    client.post(f"/api/v1/classroom/homework/{missed['id']}/check", headers=h,
                json={"results": [{"student_id": kid["id"], "status": "not_done"}]})
    # Set today, due tomorrow, nobody has checked it: that is pending work.
    _homework(client, h, cs["id"], "Tonight's work", on=today.isoformat(),
              due=(today + timedelta(days=1)).isoformat())

    sent: dict = {}
    monkeypatch.setattr("app.services.parent_auth.send_otp",
                        lambda p, c: sent.update(code=c) or "stub")
    assert client.post("/api/v1/parent/auth/request-otp",
                       json={"phone": phone}).status_code == 200
    session = client.post("/api/v1/parent/auth/verify-otp",
                          json={"phone": phone, "code": sent["code"]}).json()
    cleanup["users"].append(uuid.UUID(session["user"]["id"]))
    ph = {"Authorization": f"Bearer {session['access_token']}"}

    out = client.get(f"/api/v1/parent/children/{kid['id']}/today", headers=ph).json()
    y = out["yesterday"]
    assert y is not None and y["date"] == yest
    assert y["done"] == 1 and y["not_done"] == 1
    assert {i["text"]: i["status"] for i in y["items"]} == {
        "Did this one": "done", "Skipped this one": "not_done"}

    pending = {i["text"] for i in out["pending"]}
    assert "Tonight's work" in pending
    assert "Did this one" not in pending  # finished work is not outstanding

    # P4 holds: nothing band-shaped rides along on the parent payload.
    assert "band" not in out and "bands" not in out
