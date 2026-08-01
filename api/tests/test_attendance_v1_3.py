"""V1-3 — attendance modes, reasons, the status machine, My Class, the parent
pattern.

What each test is defending:

  * the marking slots are pure and mode-driven — twice_daily finds the
    after-lunch period from the timings alone (D-01, Q-03);
  * a recorded reason SURVIVES a re-mark (full-replace must not un-explain a
    child) and is what turns a red row amber (D-02/D-86, S-22: the status is
    computed server-side, the UI only paints);
  * an informed absence suppresses the guardian alert (S-13) and pre-explains
    the board row (S-24);
  * present-AM absent-PM is `left_after_lunch` — its own state, its own parent
    signal, and never a streak day (Q-03/S-05);
  * the class-teacher register is HER screen (another teacher gets 403), an
    unmarked day is `not_marked` (a word, never an absence), and the summary
    denominates on marked days (D-03, ux §4/§5);
  * the parent's month strip and reason ride the curated projection — same
    classifier as the register, never per-period detail (S-11/S-25).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Membership
from app.services.school_clock import marking_period_nos
from tests.conftest import AdminSession

TIMINGS = [
    {"start": "09:00", "end": "09:40", "kind": "period"},
    {"start": "09:40", "end": "10:20", "kind": "period"},
    {"start": "10:20", "end": "11:00", "kind": "lunch"},
    {"start": "11:00", "end": "11:40", "kind": "period"},
]


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _recent_school_day() -> str:
    """The most recent Mon–Sat (the year's default working week)."""
    d = date.today()
    while d.weekday() == 6:
        d -= timedelta(days=1)
    return d.isoformat()


def _setup(client, cleanup, mode="every_period"):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Att Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    if mode != "every_period":
        client.patch("/api/v1/org/settings", headers=h, json={"attendance_mode": mode})
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 3,
        "period_times": TIMINGS})
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 5}).json()
    students = [
        client.post("/api/v1/students", headers=h,
                    json={"admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": name,
                          "class_id": klass["id"]}).json()
        for name in ("Asha Rao", "Bilal Khan")
    ]
    return {"h": h, "reg": reg, "year": year, "class": klass, "cs": cs,
            "students": students, "admin_mid": mid}


def _guardian(client, h, student_id, name="Guardian"):
    r = client.post(f"/api/v1/students/{student_id}/guardians", headers=h, json={
        "name": name, "relation": "Father",
        "phone": "+919" + str(uuid.uuid4().int)[:9], "is_primary": True})
    assert r.status_code == 200, r.text


def _mark(client, h, ctx, period_no, exceptions, on=None):
    r = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": period_no,
        "class_subject_id": ctx["cs"]["id"], "date": on or _recent_school_day(),
        "exceptions": exceptions})
    assert r.status_code == 200, r.text
    return r.json()


# ── D-01: the marking slots are pure and mode-driven ─────────────────────────
def test_marking_period_nos_by_mode():
    assert marking_period_nos(TIMINGS, "every_period") == [1, 2, 3]
    assert marking_period_nos(TIMINGS, "first_period") == [1]
    # twice_daily: period 3 is the first period after the lunch entry.
    assert marking_period_nos(TIMINGS, "twice_daily") == [1, 3]
    # No break at all → degrades to first_period rather than inventing a slot.
    no_break = [t for t in TIMINGS if t["kind"] == "period"]
    assert marking_period_nos(no_break, "twice_daily") == [1]
    # No timings: first_period still means "period 1".
    assert marking_period_nos(None, "first_period") == [1]
    assert marking_period_nos(None, "every_period") == []


def test_first_period_mode_shapes_heatmap_and_my_day(client, cleanup):
    ctx = _setup(client, cleanup, mode="first_period")
    h = ctx["h"]
    today = date.today()
    for pno in (1, 2, 3):
        client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": ctx["class"]["id"], "weekday": today.weekday(),
            "period_no": pno, "class_subject_id": ctx["cs"]["id"],
            "effective_from": "2026-04-01"})

    board = client.get("/api/v1/insights/attendance", headers=h).json()
    grid = board["capture"]
    assert grid["mode"] == "first_period"
    row = next(r for r in grid["rows"] if r["class_id"] == ctx["class"]["id"])
    assert row["expected"] == 1, "the denominator is the marking periods only"
    states = {c["period_no"]: c["state"] for c in row["cells"]}
    assert states[1] == "pending"
    assert states[2] == "not_expected", "scheduled but the mode doesn't mark it"

    my_day = client.get("/api/v1/classroom/my-day", headers=h).json()
    flags = {p["period_no"]: p["marks_attendance"] for p in my_day["periods"]}
    assert flags == {1: True, 2: False, 3: False}


# ── D-02/D-86: reasons and the status machine ────────────────────────────────
def test_reason_survives_remark_and_turns_the_row_amber(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    asha, bilal = ctx["students"]
    d = _recent_school_day()
    _mark(client, h, ctx, 1, [{"student_id": asha["id"], "status": "absent"},
                              {"student_id": bilal["id"], "status": "absent"}], on=d)

    r = client.put("/api/v1/attendance/absences/reason", headers=h, json={
        "student_id": asha["id"], "date": d, "reason_code": "sick",
        "note": "fever, back Monday"})
    assert r.status_code == 200
    assert r.json()["updated_periods"] == 1

    # The full-replace re-mark must NOT un-explain the child.
    _mark(client, h, ctx, 1, [{"student_id": asha["id"], "status": "absent"},
                              {"student_id": bilal["id"], "status": "absent"}], on=d)

    board = client.get("/api/v1/insights/attendance/calls", headers=h).json()
    rows = {r["full_name"]: r for r in board["needs_call"]}
    assert rows["Asha Rao"]["status"] == "explained", "reason recorded → amber"
    assert rows["Asha Rao"]["reason_note"] == "fever, back Monday"
    assert rows["Bilal Khan"]["status"] == "unexplained", "nobody explained → red"
    # D-86: red sorts first.
    assert board["needs_call"][0]["full_name"] == "Bilal Khan"


def test_informed_absence_suppresses_alert_and_explains(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    asha, bilal = ctx["students"]
    _guardian(client, h, asha["id"])
    _guardian(client, h, bilal["id"])
    d = _recent_school_day()
    # The office already took the call: away this whole week.
    r = client.post("/api/v1/attendance/absences/notes", headers=h, json={
        "student_id": asha["id"], "from_date": d, "to_date": d,
        "reason_code": "family", "note": "family function, away till Friday",
        "source": "parent_call"})
    assert r.status_code == 200

    out = _mark(client, h, ctx, 1, [{"student_id": asha["id"], "status": "absent"},
                                    {"student_id": bilal["id"], "status": "absent"}], on=d)
    # Bilal's family is alerted; Asha's announced absence is not re-announced.
    assert out["alerted_count"] == 1

    board = client.get("/api/v1/insights/attendance/calls", headers=h).json()
    rows = {r["full_name"]: r for r in board["needs_call"]}
    assert rows["Asha Rao"]["status"] == "explained"
    assert "family function" in rows["Asha Rao"]["reason_note"]

    notes = client.get(f"/api/v1/attendance/absences/{asha['id']}/notes",
                       headers=h).json()
    assert len(notes) == 1 and notes[0]["source"] == "parent_call"


# ── Q-03/S-05: left after lunch ──────────────────────────────────────────────
def test_twice_daily_left_after_lunch_is_its_own_state(client, cleanup):
    ctx = _setup(client, cleanup, mode="twice_daily")
    h = ctx["h"]
    asha, _bilal = ctx["students"]
    _guardian(client, h, asha["id"])
    d = _recent_school_day()
    for pno in (1, 3):  # the timeline's "scheduled" comes from the timetable
        client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": ctx["class"]["id"],
            "weekday": date.fromisoformat(d).weekday(), "period_no": pno,
            "class_subject_id": ctx["cs"]["id"], "effective_from": "2026-04-01"})

    # Morning slot: everyone present. After-lunch slot: Asha gone.
    first = _mark(client, h, ctx, 1, [], on=d)
    assert first["alerted_count"] == 0
    second = _mark(client, h, ctx, 3, [{"student_id": asha["id"], "status": "absent"}], on=d)
    assert second["alerted_count"] == 1, "the after-lunch signal reaches the family"

    tl = client.get(f"/api/v1/students/{asha['id']}/timeline?on_date={d}",
                    headers=h).json()
    assert tl["day_status"] == "left_after_lunch"

    board = client.get("/api/v1/insights/attendance/calls", headers=h).json()
    assert [r["full_name"] for r in board["left_after_lunch"]] == ["Asha Rao"]
    # Present in a marked period → never a streak day, never on the red list.
    assert all(r["student_id"] != asha["id"] for r in board["needs_call"])


# ── D-03: My Class ───────────────────────────────────────────────────────────
def test_my_class_register_access_and_honest_cells(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    asha, _bilal = ctx["students"]
    d = _recent_school_day()
    _mark(client, h, ctx, 1, [{"student_id": asha["id"], "status": "absent"}], on=d)

    # Two teachers: the class teacher, and a bystander.
    creds = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"ct{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"},
        {"username": f"ot{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]}).json()["results"]
    for c in creds:
        cleanup["users"].append(uuid.UUID(c["user_id"]))
    ct_mid = str(_membership_id(creds[0]["user_id"], ctx["reg"]["org"]["id"]))
    client.patch(f"/api/v1/academics/classes/{ctx['class']['id']}", headers=h,
                 json={"class_teacher_member_id": ct_mid})

    def login(username):
        tok = client.post("/api/v1/auth/login",
                          json={"identifier": username,
                                "password": "supersecret1"}).json()
        return {"Authorization": f"Bearer {tok['access_token']}"}

    ct_h, other_h = login(creds[0]["username"]), login(creds[1]["username"])

    # The nav signal (D-03): the class teacher sees it, the bystander doesn't.
    assert client.get("/api/v1/auth/me", headers=ct_h).json()["is_class_teacher"] is True
    assert client.get("/api/v1/auth/me", headers=other_h).json()["is_class_teacher"] is False

    denied = client.get(f"/api/v1/my-class/{ctx['class']['id']}/register",
                        headers=other_h)
    assert denied.status_code == 403

    reg = client.get(f"/api/v1/my-class/{ctx['class']['id']}/register",
                     headers=ct_h).json()
    assert reg["class_label"] == "6-A"
    row = next(r for r in reg["rows"] if r["full_name"] == "Asha Rao")
    by_date = {c["date"]: c for c in row["cells"]}
    assert by_date[d]["status"] == "absent"
    # Days the class never marked are a GAP in the record — a word, never red.
    unmarked = [c for c in row["cells"] if c["date"] != d]
    assert all(c["status"] == "not_marked" for c in unmarked)
    # The summary denominates on marked days only (ux §4).
    assert row["marked_days"] == 1 and row["present_days"] == 0

    other_row = next(r for r in reg["rows"] if r["full_name"] == "Bilal Khan")
    assert other_row["present_days"] == 1 and other_row["marked_days"] == 1


# ── S-11/S-25: the parent's pattern ──────────────────────────────────────────
def test_parent_month_strip_reason_and_phone(client, cleanup, monkeypatch):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    asha = ctx["students"][0]
    d = _recent_school_day()
    client.patch("/api/v1/org/settings", headers=h, json={"phone": None})  # no-op guard

    phone = "+919" + str(uuid.uuid4().int)[:9]
    client.post(f"/api/v1/students/{asha['id']}/guardians", headers=h, json={
        "name": "Asha's Father", "relation": "Father", "phone": phone,
        "is_primary": True})
    # The timeline's "scheduled" count comes from the timetable.
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["class"]["id"],
        "weekday": date.fromisoformat(d).weekday(), "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "effective_from": "2026-04-01"})
    _mark(client, h, ctx, 1, [{"student_id": asha["id"], "status": "absent"}], on=d)
    client.put("/api/v1/attendance/absences/reason", headers=h, json={
        "student_id": asha["id"], "date": d, "reason_code": "sick",
        "note": "fever"})

    sent = {}
    monkeypatch.setattr("app.services.parent_auth.send_otp",
                        lambda p, c: sent.update(code=c) or "stub")
    client.post("/api/v1/parent/auth/request-otp", json={"phone": phone})
    v = client.post("/api/v1/parent/auth/verify-otp",
                    json={"phone": phone, "code": sent["code"]}).json()
    cleanup["users"].append(uuid.UUID(v["user"]["id"]))
    ph = {"Authorization": f"Bearer {v['access_token']}"}

    today = client.get(f"/api/v1/parent/children/{asha['id']}/today?on_date={d}",
                       headers=ph).json()
    assert today["status"] == "absent"
    assert today["absence_reason"] == "fever"
    assert today["marked_days"] == 1 and today["present_days"] == 0
    strip = {x["date"]: x["status"] for x in today["month"]}
    assert strip[d] == "absent"
    assert all(s in ("present", "partial", "absent", "left_after_lunch", "not_marked")
               for s in strip.values())
    # P4 discipline intact: nothing band-shaped in the payload.
    assert "band" not in str(today).lower()
