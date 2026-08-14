"""TT-4 — two or more classes taught as ONE meeting.

What each test is defending:

  * a combined period is the honest way to say what the clash validator was
    right to flag: the warning names its own fix (`combinable`), and combining
    silences that clash and only that one;
  * combining is refused unless it really is one meeting — every named class has
    the cell filled, they all run a subject, and they share one teacher;
  * the teacher's week and My Day draw ONE row per meeting, with the room's
    roster, not one row per class;
  * one roll call writes one register PER CLASS, so every existing reader (the
    month register, the report card, the guardian alert) is untouched;
  * the syllabus stays per class — the card carries a plan for each — while
    homework can be set once for the room;
  * the arrangement dissolves the moment it stops being one: a member cell given
    something else to do, or split off, leaves nothing half-combined behind.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import AttendanceException, ClassPeriod, Membership
from tests.conftest import AdminSession

TIMINGS = [
    {"start": "09:00", "end": "09:40", "kind": "period"},
    {"start": "09:40", "end": "10:20", "kind": "period"},
]


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _monday() -> date:
    """The most recent Monday — weekday 0, which every fixture below places on."""
    d = date.today()
    return d - timedelta(days=d.weekday())


def _setup(client, cleanup):
    """One school, two small classes, both doing Maths in period 1 on Monday
    with the same teacher — the founder's own example."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Combined Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 2, "period_times": TIMINGS})
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Maths"}).json()

    def make_class(name, teacher_mid, students):
        klass = client.post("/api/v1/academics/classes", headers=h,
                            json={"academic_year_id": year["id"], "name": name,
                                  "section": "A"}).json()
        cs = client.post("/api/v1/academics/class-subjects", headers=h,
                         json={"class_id": klass["id"], "subject_id": maths["id"],
                               "teacher_member_id": teacher_mid,
                               "periods_per_week": 2}).json()
        kids = [client.post("/api/v1/students", headers=h, json={
            "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": n,
            "class_id": klass["id"]}).json() for n in students]
        return {"class": klass, "cs": cs, "students": kids}

    five = make_class("5", mid, ["Asha Rao", "Bilal Khan"])
    six = make_class("6", mid, ["Chitra Das"])
    for c in (five, six):
        r = client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": c["class"]["id"], "weekday": 0, "period_no": 1,
            "class_subject_id": c["cs"]["id"],
            "effective_from": (_monday() - timedelta(days=7)).isoformat()})
        assert r.status_code == 200, r.text
    return {"h": h, "reg": reg, "year": year, "mid": mid,
            "maths": maths, "five": five, "six": six}


def _invite_teacher(client, cleanup, h):
    """A second teacher, and her own headers — (member_id, auth header)."""
    inv = client.post("/api/v1/org/members/invite", headers=h, json={
        "name": "Second Teacher", "phone": "+9198" + str(uuid.uuid4().int)[:8],
        "role": "teacher"}).json()
    cleanup["users"].append(uuid.UUID(inv["user_id"]))
    token = inv["invite_url"].rsplit("/join/", 1)[1]
    access = client.post("/api/v1/auth/verify", json={"token": token}).json()
    th = {"Authorization": f"Bearer {access['access_token']}"}
    org_id = client.get("/api/v1/auth/me", headers=th).json()["org"]["id"]
    return str(_membership_id(inv["user_id"], org_id)), th


def _combine(client, ctx, classes=None, eff=None):
    ids = classes or [ctx["five"]["class"]["id"], ctx["six"]["class"]["id"]]
    r = client.post("/api/v1/timetable/combine", headers=ctx["h"], json={
        "weekday": 0, "period_no": 1, "class_ids": ids,
        "effective_from": (eff or _monday() - timedelta(days=7)).isoformat()})
    return r


# ── the clash names its own fix ───────────────────────────────────────────────
def test_clash_is_reported_as_combinable(client, cleanup):
    ctx = _setup(client, cleanup)
    clashes = client.get("/api/v1/timetable/validate", headers=ctx["h"]).json()
    assert len(clashes) == 1, clashes
    assert clashes[0]["combinable"] is True
    assert sorted(clashes[0]["class_labels"]) == ["5-A", "6-A"]
    # The ids the Combine button posts back — labels are for reading, not keying.
    assert set(clashes[0]["class_ids"]) == {
        ctx["five"]["class"]["id"], ctx["six"]["class"]["id"]}


def test_combining_silences_that_clash_and_shows_on_the_grid(client, cleanup):
    ctx = _setup(client, cleanup)
    combo = _combine(client, ctx)
    assert combo.status_code == 200, combo.text
    assert combo.json()["label"] == "5-A + 6-A"
    assert len(combo.json()["classes"]) == 2

    assert client.get("/api/v1/timetable/validate", headers=ctx["h"]).json() == []

    grid = client.get(
        f"/api/v1/timetable/grid?class_id={ctx['five']['class']['id']}",
        headers=ctx["h"]).json()
    cell = next(s for s in grid["slots"] if s["weekday"] == 0 and s["period_no"] == 1)
    assert cell["combined_id"] == combo.json()["id"]
    # The chip says who ELSE is in the room, never this class over again.
    assert cell["combined_with"] == ["6-A"]
    assert grid["clashes"] == []


def test_a_third_class_still_clashes(client, cleanup):
    """Combining is not a blanket amnesty. A genuine double-booking elsewhere in
    the same period must survive it, or the arrangement becomes a way to hide
    exactly the mistake the validator exists for."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    seven = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "7", "section": "A"}).json()
    cs7 = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": seven["id"], "subject_id": ctx["maths"]["id"],
        "teacher_member_id": ctx["mid"], "periods_per_week": 2}).json()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": seven["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs7["id"],
        "effective_from": (_monday() - timedelta(days=7)).isoformat()})

    assert _combine(client, ctx).status_code == 200
    clashes = client.get("/api/v1/timetable/validate", headers=h).json()
    assert len(clashes) == 1
    assert "7-A" in clashes[0]["class_labels"]
    # …and it too offers the same fix: grow the combination.
    assert clashes[0]["combinable"] is True
    grown = _combine(client, ctx, classes=[
        ctx["five"]["class"]["id"], ctx["six"]["class"]["id"], seven["id"]])
    assert grown.status_code == 200, grown.text
    assert len(grown.json()["classes"]) == 3
    assert client.get("/api/v1/timetable/validate", headers=h).json() == []


# ── it has to really be one meeting ───────────────────────────────────────────
def test_different_teachers_are_refused_with_a_sentence(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    other_mid, _th = _invite_teacher(client, cleanup, h)
    r = client.patch(f"/api/v1/academics/class-subjects/{ctx['six']['cs']['id']}",
                     headers=h, json={"teacher_member_id": other_mid})
    assert r.status_code == 200, r.text

    r = _combine(client, ctx)
    assert r.status_code == 422, r.text
    assert "same teacher" in r.json()["error"]["message"]


def test_an_empty_cell_cannot_be_combined(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    client.post("/api/v1/timetable/slot/clear", headers=h, json={
        "class_id": ctx["six"]["class"]["id"], "weekday": 0, "period_no": 1,
        "effective_from": (_monday() - timedelta(days=7)).isoformat()})
    r = _combine(client, ctx)
    assert r.status_code == 422, r.text
    assert "6-A" in r.json()["error"]["message"]


def test_a_teacher_cannot_combine(client, cleanup):
    """`ToolSpec`-style negative check: the route is admin-only and the service
    is reachable in-process, so the guard is the only thing in the way."""
    ctx = _setup(client, cleanup)
    _mid, th = _invite_teacher(client, cleanup, ctx["h"])
    r = client.post("/api/v1/timetable/combine", headers=th, json={
        "weekday": 0, "period_no": 1,
        "class_ids": [ctx["five"]["class"]["id"], ctx["six"]["class"]["id"]]})
    assert r.status_code == 403, r.text


# ── one row per meeting ───────────────────────────────────────────────────────
def test_teacher_week_draws_one_row_for_the_room(client, cleanup):
    ctx = _setup(client, cleanup)
    before = client.get("/api/v1/timetable/my-week", headers=ctx["h"]).json()
    mon_p1 = [s for s in before["slots"] if s["weekday"] == 0 and s["period_no"] == 1]
    assert len(mon_p1) == 2  # two classes, two rows — the double booking

    assert _combine(client, ctx).status_code == 200
    after = client.get("/api/v1/timetable/my-week", headers=ctx["h"]).json()
    mon_p1 = [s for s in after["slots"] if s["weekday"] == 0 and s["period_no"] == 1]
    assert len(mon_p1) == 1
    assert mon_p1[0]["class_labels"] == ["5-A", "6-A"]
    assert len(mon_p1[0]["class_ids"]) == 2


def test_my_day_shows_the_room_with_a_summed_roster(client, cleanup):
    ctx = _setup(client, cleanup)
    assert _combine(client, ctx).status_code == 200
    day = client.get(
        f"/api/v1/classroom/my-day?on_date={_monday().isoformat()}",
        headers=ctx["h"]).json()
    p1 = [p for p in day["periods"] if p["period_no"] == 1]
    assert len(p1) == 1, p1
    assert p1[0]["class_label"] == "5-A + 6-A"
    assert p1[0]["roster_count"] == 3  # 2 + 1, the whole room
    assert len(p1[0]["combined_class_ids"]) == 2


# ── one roll call, one register per class ─────────────────────────────────────
def test_one_roll_call_writes_both_registers(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    assert _combine(client, ctx).status_code == 200
    on = _monday().isoformat()

    sheet = client.get(
        f"/api/v1/attendance/roster?class_id={ctx['five']['class']['id']}"
        f"&period_no=1&on_date={on}", headers=h).json()
    assert sheet["combined_label"] == "5-A + 6-A"
    assert len(sheet["roster"]) == 3
    assert {r["class_label"] for r in sheet["roster"]} == {"5-A", "6-A"}

    # One child absent from EACH class, saved once.
    absent = [ctx["five"]["students"][0]["id"], ctx["six"]["students"][0]["id"]]
    r = client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["five"]["class"]["id"], "period_no": 1, "date": on,
        "class_ids": sheet["combined_class_ids"],
        "exceptions": [{"student_id": s, "status": "absent"} for s in absent]})
    assert r.status_code == 200, r.text
    assert r.json()["roster_count"] == 3
    assert r.json()["absent_count"] == 2

    # Each class got its OWN register row with its OWN absentee — never a shared
    # one. Read from the database, because that is the claim: nothing downstream
    # of attendance learns a new shape.
    db = AdminSession()
    try:
        for c in (ctx["five"], ctx["six"]):
            period = db.scalar(select(ClassPeriod).where(
                ClassPeriod.class_id == uuid.UUID(c["class"]["id"]),
                ClassPeriod.date == _monday(), ClassPeriod.period_no == 1))
            assert period is not None, c["class"]["name"]
            assert period.attendance_marked_at is not None
            absents = db.scalars(select(AttendanceException.student_id).where(
                AttendanceException.period_id == period.id,
                AttendanceException.status == "absent")).all()
            assert [str(s) for s in absents] == [c["students"][0]["id"]]
    finally:
        db.close()


def test_the_card_keeps_a_syllabus_per_class(client, cleanup):
    """The one thing that must NOT be shared. Two classes sat in one room; their
    chapters are still their own, and pooling them would move the wrong
    syllabus."""
    ctx = _setup(client, cleanup)
    assert _combine(client, ctx).status_code == 200
    card = client.get(
        f"/api/v1/periods/card?class_id={ctx['five']['class']['id']}"
        f"&period_no=1&on_date={_monday().isoformat()}", headers=ctx["h"]).json()
    assert card["combined_label"] == "5-A + 6-A"
    assert len(card["combined"]) == 2
    assert {c["class_label"] for c in card["combined"]} == {"5-A", "6-A"}
    # Each half carries its own class-subject, so each logs against its own plan.
    assert len({c["class_subject_id"] for c in card["combined"]}) == 2
    # This class's own roster stays this class's — the room is on the sheet.
    assert len(card["roster"]) == 2


def test_homework_can_be_set_once_for_the_room(client, cleanup):
    ctx = _setup(client, cleanup)
    assert _combine(client, ctx).status_code == 200
    r = client.post("/api/v1/classroom/homework", headers=ctx["h"], json={
        "class_subject_id": ctx["five"]["cs"]["id"], "text": "Exercise 4",
        "also_class_subject_ids": [ctx["six"]["cs"]["id"]]})
    assert r.status_code == 200, r.text
    assert len(r.json()["created_ids"]) == 2
    for c in (ctx["five"], ctx["six"]):
        book = client.get(
            f"/api/v1/classroom/homework-log?class_subject_id={c['cs']['id']}",
            headers=ctx["h"]).json()
        assert [e["text"] for e in book["entries"]] == ["Exercise 4"]


# ── it dissolves the moment it stops being one meeting ────────────────────────
def test_uncombine_restores_the_clash(client, cleanup):
    ctx = _setup(client, cleanup)
    combo = _combine(client, ctx).json()
    r = client.post("/api/v1/timetable/uncombine", headers=ctx["h"], json={
        "combined_id": combo["id"],
        "effective_from": _monday().isoformat()})
    assert r.status_code == 200, r.text
    assert r.json() == []
    assert len(client.get("/api/v1/timetable/validate", headers=ctx["h"]).json()) == 1


def test_changing_a_member_cell_dissolves_the_arrangement(client, cleanup):
    """A combination of one is not a combination. Leaving the survivor stamped
    would keep silencing a clash against a partner that no longer exists."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    assert _combine(client, ctx).status_code == 200
    hindi = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Hindi"}).json()
    cs6b = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": ctx["six"]["class"]["id"], "subject_id": hindi["id"],
        "teacher_member_id": ctx["mid"], "periods_per_week": 2}).json()
    r = client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["six"]["class"]["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs6b["id"], "effective_from": _monday().isoformat()})
    assert r.status_code == 200, r.text

    assert client.get("/api/v1/timetable/combined", headers=h).json() == []
    grid = client.get(
        f"/api/v1/timetable/grid?class_id={ctx['five']['class']['id']}",
        headers=h).json()
    cell = next(s for s in grid["slots"] if s["weekday"] == 0 and s["period_no"] == 1)
    assert cell["combined_id"] is None
    assert cell["combined_with"] == []
