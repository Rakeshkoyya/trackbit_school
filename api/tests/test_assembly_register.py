"""TT-6 — the whole-school register, taken once at assembly.

Founder, 2026-08-18: *"if I added assembly in my timetable at first period and I
want to take attendance of that whole school that are in assembly, it should
reflect in each class."*

What each test is defending:

  * assembly is the one block kind whose roll IS the school-day register
    (`school_roll`), and a sports or study block still keeps its own roll — a
    block that quietly wrote everybody's register would be the second store of
    "was this child in today" this codebase keeps deleting;
  * one roll call in the hall writes one register PER CLASS, on the period the
    grid puts assembly on, so the month register, the report card and the
    guardian alert are untouched and learn nothing about assembly;
  * the door is the BLOCK. The person who takes assembly teaches almost none of
    the school, so `assert_can_take_class` would refuse her — and a teacher who
    is not on the block's staff must still be refused, which is the negative
    authorization test every write of ours ships with;
  * the classes she reaches are the ones the block holds ON THE GRID at that
    period, never a list she names — otherwise `session_id` is a skeleton key
    into every register in the school;
  * once the hall's register is in, every class's day is settled: a once-per-day
    school stops asking its subject teachers for a roll that was taken at 08:20.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import AttendanceException, ClassPeriod, Membership
from tests.conftest import AdminSession

TIMINGS = [
    {"start": "08:20", "end": "08:40", "kind": "period"},
    {"start": "08:40", "end": "09:20", "kind": "period"},
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
    """The most recent Monday — weekday 0, which every fixture below sits on."""
    d = date.today()
    return d - timedelta(days=d.weekday())


def _eff() -> str:
    return (_monday() - timedelta(days=7)).isoformat()


def _invite_teacher(client, cleanup, h, name):
    """Another member, and her own headers — (member_id, auth header)."""
    inv = client.post("/api/v1/org/members/invite", headers=h, json={
        "name": name, "phone": "+9198" + str(uuid.uuid4().int)[:8],
        "role": "teacher"}).json()
    cleanup["users"].append(uuid.UUID(inv["user_id"]))
    token = inv["invite_url"].rsplit("/join/", 1)[1]
    access = client.post("/api/v1/auth/verify", json={"token": token}).json()
    th = {"Authorization": f"Bearer {access['access_token']}"}
    org_id = client.get("/api/v1/auth/me", headers=th).json()["org"]["id"]
    return str(_membership_id(inv["user_id"], org_id)), th


def _setup(client, cleanup):
    """A small school: two classes, Maths in period 2, and assembly in period 1
    for both of them — taken by a warden who teaches neither class."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Assembly Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    # One register a day is the school's mode — the case the founder is in.
    assert client.patch("/api/v1/org/settings", headers=h,
                        json={"attendance_mode": "first_period"}).status_code == 200

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 2, "period_times": TIMINGS})
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Maths"}).json()

    def make_class(name, students):
        klass = client.post("/api/v1/academics/classes", headers=h,
                            json={"academic_year_id": year["id"], "name": name,
                                  "section": "A"}).json()
        cs = client.post("/api/v1/academics/class-subjects", headers=h,
                         json={"class_id": klass["id"], "subject_id": maths["id"],
                               "teacher_member_id": mid, "periods_per_week": 1}).json()
        client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": klass["id"], "weekday": 0, "period_no": 2,
            "class_subject_id": cs["id"], "effective_from": _eff()})
        kids = [client.post("/api/v1/students", headers=h, json={
            "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": n,
            "class_id": klass["id"]}).json() for n in students]
        return {"class": klass, "cs": cs, "students": kids}

    five = make_class("5", ["Asha Rao", "Bilal Khan"])
    six = make_class("6", ["Chitra Das"])

    warden_mid, warden_h = _invite_teacher(client, cleanup, h, "Morning Warden")
    block = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Morning assembly", "kind": "assembly",
        "staff_member_ids": [warden_mid]}).json()
    for c in (five, six):
        r = client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": c["class"]["id"], "weekday": 0, "period_no": 1,
            "slot_type": "block", "session_id": block["id"],
            "effective_from": _eff()})
        assert r.status_code == 200, r.text

    return {"h": h, "reg": reg, "year": year, "mid": mid, "maths": maths,
            "five": five, "six": six, "block": block,
            "warden_h": warden_h, "warden_mid": warden_mid}


def _sheet(client, headers, ctx, on=None):
    return client.get(
        f"/api/v1/attendance/assembly?session_id={ctx['block']['id']}"
        f"&on_date={(on or _monday()).isoformat()}", headers=headers)


def _mark(client, headers, ctx, absent_ids=(), on=None, session_id=None):
    return client.post("/api/v1/attendance/assembly", headers=headers, json={
        "session_id": session_id or ctx["block"]["id"],
        "date": (on or _monday()).isoformat(),
        "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids]})


# ── the sheet is the hall ────────────────────────────────────────────────────
def test_the_sheet_is_the_whole_school_grouped_by_class(client, cleanup):
    ctx = _setup(client, cleanup)
    r = _sheet(client, ctx["warden_h"], ctx)
    assert r.status_code == 200, r.text
    sheet = r.json()

    # The period comes from the GRID — "assembly is at period 1" is said once.
    assert sheet["period_no"] == 1
    assert sheet["block_name"] == "Morning assembly"
    assert sheet["kind_label"] == "Assembly / yoga"
    assert len(sheet["roster"]) == 3
    assert sorted(c["class_label"] for c in sheet["classes"]) == ["5-A", "6-A"]
    # Every child carries their class, or a warden cannot find a name in 400.
    assert {r["class_label"] for r in sheet["roster"]} == {"5-A", "6-A"}
    assert sheet["marked"] is False
    # Never a zero and never red before anybody has taken it.
    assert sheet["headline"] == "Not taken yet · 3 children across 2 classes"


def test_a_teacher_who_is_not_on_the_block_is_refused(client, cleanup):
    """The negative authorization test. `assert_may_take_block` is the ONLY thing
    between an outsider and every register in the school, because the assembly
    path deliberately skips the per-class guard."""
    ctx = _setup(client, cleanup)
    _outsider_mid, outsider_h = _invite_teacher(
        client, cleanup, ctx["h"], "Somebody Else")

    r = _sheet(client, outsider_h, ctx)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "not_your_block"

    r = _mark(client, outsider_h, ctx)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "not_your_block"
    # And nothing was written on the way to being refused.
    db = AdminSession()
    try:
        assert db.scalar(select(ClassPeriod).where(
            ClassPeriod.org_id == uuid.UUID(ctx["reg"]["org"]["id"]))) is None
    finally:
        db.close()


# ── one roll call, every class's register ────────────────────────────────────
def test_one_roll_call_writes_one_register_per_class(client, cleanup):
    ctx = _setup(client, cleanup)
    asha = ctx["five"]["students"][0]["id"]

    r = _mark(client, ctx["warden_h"], ctx, absent_ids=[asha])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["classes_marked"] == 2
    assert (out["roster_count"], out["present_count"], out["absent_count"]) == (3, 2, 1)
    assert out["period_no"] == 1
    assert out["headline"] == "2 of 3 present · filed to 2 classes"

    org_id = uuid.UUID(ctx["reg"]["org"]["id"])
    db = AdminSession()
    try:
        periods = list(db.scalars(select(ClassPeriod).where(
            ClassPeriod.org_id == org_id, ClassPeriod.date == _monday())))
        # One row per class, both on the block's period, both actually marked.
        assert len(periods) == 2
        assert {p.class_id for p in periods} == {
            uuid.UUID(ctx["five"]["class"]["id"]), uuid.UUID(ctx["six"]["class"]["id"])}
        assert all(p.period_no == 1 for p in periods)
        assert all(p.attendance_marked_at is not None for p in periods)
        # The absence lands on HER class's register and nowhere else — the hall's
        # exception list is filtered by whose roster each child is on.
        exceptions = list(db.scalars(select(AttendanceException).where(
            AttendanceException.period_id.in_([p.id for p in periods]))))
        assert len(exceptions) == 1
        assert str(exceptions[0].student_id) == asha
        five_period = next(p for p in periods
                           if str(p.class_id) == ctx["five"]["class"]["id"])
        assert exceptions[0].period_id == five_period.id
        # Assembly is not a subject: the register is filed against no lesson.
        assert all(p.class_subject_id is None for p in periods)
    finally:
        db.close()


def test_it_reflects_in_each_class_register(client, cleanup):
    """The founder's own words. The class's ordinary sheet — the one its own
    teacher opens — must already show this morning's roll."""
    ctx = _setup(client, cleanup)
    asha = ctx["five"]["students"][0]["id"]
    assert _mark(client, ctx["warden_h"], ctx, absent_ids=[asha]).status_code == 200

    five = client.get(
        f"/api/v1/attendance/roster?class_id={ctx['five']['class']['id']}"
        f"&period_no=2&on_date={_monday().isoformat()}", headers=ctx["h"]).json()
    # Opened at period 2 and handed the day's register, taken at period 1.
    assert five["marked"] is True
    assert five["period_no"] == 1
    assert five["absent_count"] == 1
    assert next(r for r in five["roster"] if r["student_id"] == asha)["status"] == "absent"

    six = client.get(
        f"/api/v1/attendance/roster?class_id={ctx['six']['class']['id']}"
        f"&period_no=2&on_date={_monday().isoformat()}", headers=ctx["h"]).json()
    assert six["marked"] is True
    assert six["absent_count"] == 0

    # And the sheet the warden reopens shows what she recorded, not a blank one.
    again = _sheet(client, ctx["warden_h"], ctx).json()
    assert again["marked"] is True
    assert again["absent_count"] == 1
    assert again["headline"] == "2 of 3 present · filed to 2 classes"


def test_the_register_settles_the_day_for_the_subject_teachers(client, cleanup):
    """Once-per-day: the roll was taken at 08:20, so nobody is asked for it
    again — this is what stops the school taking two registers a day."""
    ctx = _setup(client, cleanup)
    assert _mark(client, ctx["warden_h"], ctx).status_code == 200

    day = client.get(
        f"/api/v1/classroom/my-day?on_date={_monday().isoformat()}",
        headers=ctx["h"]).json()
    maths = [p for p in day["periods"] if p["slot_type"] == "subject"]
    assert maths, day["periods"]
    assert all(p["day_attendance_taken"] is True for p in maths)
    assert all(p["marks_attendance"] is False for p in maths)


def test_my_day_shows_the_hall_and_goes_green(client, cleanup):
    ctx = _setup(client, cleanup)

    def assembly_row():
        day = client.get(
            f"/api/v1/classroom/my-day?on_date={_monday().isoformat()}",
            headers=ctx["warden_h"]).json()
        return next(p for p in day["periods"] if p["slot_type"] == "block")

    before = assembly_row()
    assert before["school_roll"] is True
    assert before["marks_attendance"] is True
    # The row is the whole hall, and it is the one block row that IS owed.
    assert before["roster_count"] == 3
    assert before["optional"] is False
    assert before["captured"] is False
    assert before["class_label"] == "5-A + 6-A"

    assert _mark(client, ctx["warden_h"], ctx,
                 absent_ids=[ctx["six"]["students"][0]["id"]]).status_code == 200

    after = assembly_row()
    assert after["captured"] is True
    assert after["attendance_marked"] is True
    assert (after["present_count"], after["absent_count"]) == (2, 1)


def test_a_half_marked_hall_is_not_done(client, cleanup):
    """5-A's register in and 6-A's missing is not "assembly taken". A green row
    there would lose a class's day quietly, which is the one thing it must never
    do — the same ALL rule the combined roll call holds itself to."""
    ctx = _setup(client, cleanup)
    # 5-A marked on its own, the ordinary way, by the teacher who teaches it.
    assert client.post("/api/v1/attendance/mark", headers=ctx["h"], json={
        "class_id": ctx["five"]["class"]["id"], "period_no": 1,
        "date": _monday().isoformat(), "exceptions": []}).status_code == 200

    sheet = _sheet(client, ctx["warden_h"], ctx).json()
    assert sheet["marked"] is False
    assert [c["marked"] for c in sheet["classes"]] == [True, False]

    day = client.get(f"/api/v1/classroom/my-day?on_date={_monday().isoformat()}",
                     headers=ctx["warden_h"]).json()
    row = next(p for p in day["periods"] if p["slot_type"] == "block")
    assert row["captured"] is False


# ── the block is the boundary ────────────────────────────────────────────────
def test_only_the_classes_the_grid_puts_in_the_hall_are_touched(client, cleanup):
    """A class with no assembly cell is not in assembly, however many children of
    it the caller names. `session_id` must not be a skeleton key."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    seven = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "7", "section": "A"}).json()
    outsider = client.post("/api/v1/students", headers=h, json={
        "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": "Deepa Nair",
        "class_id": seven["id"]}).json()

    sheet = _sheet(client, ctx["warden_h"], ctx).json()
    assert outsider["id"] not in {r["student_id"] for r in sheet["roster"]}

    out = _mark(client, ctx["warden_h"], ctx, absent_ids=[outsider["id"]]).json()
    assert out["classes_marked"] == 2
    assert out["absent_count"] == 0  # she is on nobody's roster in this hall

    db = AdminSession()
    try:
        assert db.scalar(select(ClassPeriod).where(
            ClassPeriod.class_id == uuid.UUID(seven["id"]))) is None
    finally:
        db.close()


def test_a_sports_block_keeps_its_own_roll(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    games = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Games", "kind": "sports",
        "staff_member_ids": [ctx["warden_mid"]]}).json()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["five"]["class"]["id"], "weekday": 0, "period_no": 2,
        "slot_type": "block", "session_id": games["id"], "effective_from": _eff()})

    r = _mark(client, ctx["warden_h"], ctx, session_id=games["id"])
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "no_school_roll"

    day = client.get(f"/api/v1/classroom/my-day?on_date={_monday().isoformat()}",
                     headers=ctx["warden_h"]).json()
    row = next(p for p in day["periods"]
               if p["slot_type"] == "block" and p["block_kind"] == "sports")
    assert row["school_roll"] is False
    assert row["marks_attendance"] is False
    assert row["optional"] is True


def test_a_day_the_block_is_not_on_the_grid_has_no_register_to_take(client, cleanup):
    """Assembly does not run on Sunday. That is a state, not a fault — but it
    still has no period to file against, so it cannot write one."""
    ctx = _setup(client, cleanup)
    sunday = _monday() + timedelta(days=6)

    assert _sheet(client, ctx["warden_h"], ctx, on=sunday).status_code == 422
    r = _mark(client, ctx["warden_h"], ctx, on=sunday)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "block_not_on_grid"


def test_retaking_the_hall_replaces_the_registers_rather_than_adding_to_them(
        client, cleanup):
    """A mis-tap is corrected in place (law 3's typo clause): re-marking the hall
    edits the day's registers, it does not open a second one per class."""
    ctx = _setup(client, cleanup)
    asha, bilal = (s["id"] for s in ctx["five"]["students"])

    assert _mark(client, ctx["warden_h"], ctx, absent_ids=[asha]).status_code == 200
    out = _mark(client, ctx["warden_h"], ctx, absent_ids=[bilal]).json()
    assert out["absent_count"] == 1

    org_id = uuid.UUID(ctx["reg"]["org"]["id"])
    db = AdminSession()
    try:
        periods = list(db.scalars(select(ClassPeriod).where(
            ClassPeriod.org_id == org_id, ClassPeriod.date == _monday())))
        assert len(periods) == 2
        exceptions = list(db.scalars(select(AttendanceException).where(
            AttendanceException.period_id.in_([p.id for p in periods]))))
        assert [str(e.student_id) for e in exceptions] == [bilal]
    finally:
        db.close()
