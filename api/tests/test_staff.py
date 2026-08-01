"""SF-1: staff attendance, timesheet and leave.

What each test is defending:

  * attendance is capture-by-exception and re-editable — the admin can reopen a
    saved day and correct it, with no undo path and no double counting;
  * an unmarked day is not a full house;
  * the timetable owns teaching periods — the timesheet cannot overwrite one;
  * leave arithmetic counts WORKING days and the append-only event log is the
    record, `status` only its cache;
  * an over-policy application still reaches the admin, flagged;
  * role guards: a teacher cannot mark staff attendance, cannot read a
    colleague's timesheet, and cannot decide their own leave.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core import work_types
from app.models import LeaveRequest, LeaveRequestEvent, Membership, StaffAbsence
from app.services import school_clock
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
    """An org with an active year, school timings, one class and a teacher."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Staff Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    admin_mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 4,
        "period_times": [
            {"start": "09:00", "end": "09:40", "kind": "period"},
            {"start": "09:40", "end": "10:20", "kind": "period"},
            {"start": "10:20", "end": "10:40", "kind": "break"},
            {"start": "10:40", "end": "11:20", "kind": "period"},
            {"start": "11:20", "end": "12:00", "kind": "period"},
        ]})

    # A teacher who can log in, so the role guards are exercised for real.
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    teacher_mid = str(_membership_id(cred["user_id"], reg["org"]["id"]))

    return h, th, year, admin_mid, teacher_mid


# ── the school clock (pure, no DB) ───────────────────────────────────────────
def test_period_numbering_skips_breaks():
    """period_no must count only teaching periods, or a teacher's timesheet
    silently misaligns with their timetable."""
    times = [
        {"start": "09:00", "end": "09:40", "kind": "period"},
        {"start": "09:40", "end": "10:20", "kind": "period"},
        {"start": "10:20", "end": "10:40", "kind": "break"},
        {"start": "10:40", "end": "11:20", "kind": "period"},
    ]
    periods = school_clock.periods_of(times)
    assert [p.period_no for p in periods] == [1, 2, 3]
    assert periods[2].start == "10:40"  # the break did NOT consume number 3

    breaks = school_clock.breaks_of(times)
    assert len(breaks) == 1 and breaks[0].after_period_no == 2

    # No timings configured at all still yields a usable day.
    assert len(school_clock.day_periods([], 8)) == 8


def test_work_type_normalisation_keeps_a_schools_own_words():
    assert work_types.normalize("Notebook Checking") == "notebook_checking"
    assert work_types.normalize("notebook checking") == "notebook_checking"
    assert work_types.normalize("") == "other"
    # An unknown bucket is preserved, not flattened — and still reads well.
    assert work_types.normalize("Sports duty") == "sports_duty"
    assert work_types.label_for("sports_duty") == "Sports duty"


# ── staff attendance ─────────────────────────────────────────────────────────
def test_unmarked_day_is_not_a_full_house(client, cleanup):
    h, _th, _year, _amid, _tmid = _setup(client, cleanup)
    r = client.get("/api/v1/staff/attendance", headers=h).json()
    assert r["marked"] is False
    assert r["total"] == 2  # the director and the teacher
    # Everyone renders present so the sheet opens ready to save, but `marked`
    # is what any report must read — nobody has confirmed anything yet.
    assert r["present_count"] == 2


def test_mark_is_exception_shaped_and_re_editable(client, cleanup):
    h, _th, _year, _amid, teacher_mid = _setup(client, cleanup)
    on = "2026-07-15"

    # All present = an empty absence list, and zero rows written.
    r = client.post("/api/v1/staff/attendance", headers=h,
                    json={"date": on, "absent_member_ids": []}).json()
    assert r["marked"] is True and r["absent_count"] == 0
    assert _absence_count(on) == 0

    # Mark the teacher absent.
    r = client.post("/api/v1/staff/attendance", headers=h,
                    json={"date": on, "absent_member_ids": [teacher_mid],
                          "notes": {teacher_mid: "Sick"}}).json()
    assert r["absent_count"] == 1
    assert _absence_count(on) == 1
    row = next(x for x in r["roster"] if x["member_id"] == teacher_mid)
    assert row["present"] is False and row["note"] == "Sick"

    # Reopen and correct: they did come in. Full replace, no undo path.
    r = client.post("/api/v1/staff/attendance", headers=h,
                    json={"date": on, "absent_member_ids": []}).json()
    assert r["absent_count"] == 0
    assert _absence_count(on) == 0

    # Saving twice cannot double-count.
    for _ in range(2):
        r = client.post("/api/v1/staff/attendance", headers=h,
                        json={"date": on, "absent_member_ids": [teacher_mid]}).json()
    assert r["absent_count"] == 1 and _absence_count(on) == 1


def _absence_count(on: str) -> int:
    db = AdminSession()
    try:
        return db.query(StaffAbsence).join(
            StaffAbsence.day).filter_by(date=date.fromisoformat(on)).count()
    finally:
        db.close()


def test_teacher_cannot_mark_staff_attendance(client, cleanup):
    _h, th, _year, _amid, _tmid = _setup(client, cleanup)
    assert client.get("/api/v1/staff/attendance", headers=th).status_code == 403
    assert client.post("/api/v1/staff/attendance", headers=th,
                       json={"absent_member_ids": []}).status_code == 403


# ── timesheet ────────────────────────────────────────────────────────────────
def test_timesheet_marks_free_periods_and_the_grid_wins(client, cleanup):
    h, th, year, _amid, teacher_mid = _setup(client, cleanup)

    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": teacher_mid, "periods_per_week": 4}).json()
    # Wednesday 2026-07-15; give the teacher period 1 on that weekday.
    on = date(2026, 7, 15)
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": on.weekday(), "period_no": 1,
        "class_subject_id": cs["id"], "effective_from": "2026-04-01"})

    day = client.get("/api/v1/staff/timesheet/day", headers=th,
                     params={"on_date": on.isoformat()}).json()
    assert [s["kind"] for s in day["slots"]] == ["class", "free", "free", "free"]
    assert day["slots"][0]["subject_name"] == "Science"

    # The timetable owns period 1 — the timesheet must refuse it.
    bad = client.put("/api/v1/staff/timesheet/entry", headers=th, json={
        "date": on.isoformat(), "period_no": 1, "work_type": "notebook_checking"})
    assert bad.status_code == 409

    # A free period takes work, and is editable afterwards.
    day = client.put("/api/v1/staff/timesheet/entry", headers=th, json={
        "date": on.isoformat(), "period_no": 2, "work_type": "Notebook Checking",
        "note": "6-A science books"}).json()
    slot = day["slots"][1]
    assert slot["kind"] == "work" and slot["work_type"] == "notebook_checking"
    assert slot["work_label"] == "Notebook checking"
    assert day["teaching_count"] == 1 and day["work_count"] == 1 and day["free_count"] == 2

    day = client.put("/api/v1/staff/timesheet/entry", headers=th, json={
        "date": on.isoformat(), "period_no": 2, "work_type": "exam_work"}).json()
    assert day["slots"][1]["work_type"] == "exam_work"  # replaced, not duplicated

    day = client.request("DELETE", "/api/v1/staff/timesheet/entry", headers=th,
                         params={"on_date": on.isoformat(), "period_no": 2}).json()
    assert day["slots"][1]["kind"] == "free"


def test_teacher_cannot_read_another_timesheet_but_admin_can(client, cleanup):
    h, th, _year, admin_mid, teacher_mid = _setup(client, cleanup)
    assert client.get("/api/v1/staff/timesheet/week", headers=th,
                      params={"member_id": admin_mid}).status_code == 403
    ok = client.get("/api/v1/staff/timesheet/week", headers=h,
                    params={"member_id": teacher_mid})
    assert ok.status_code == 200 and ok.json()["member_id"] == teacher_mid
    # The admin's org-wide day view lists every member exactly once.
    rows = client.get("/api/v1/staff/timesheet/today", headers=h).json()
    assert {r["member_id"] for r in rows} == {admin_mid, teacher_mid}


# ── leave ────────────────────────────────────────────────────────────────────
def test_leave_counts_working_days_not_raw_span(client, cleanup):
    """Mon–Mon over a closed Sunday is 7 working days, not 8 calendar days."""
    _h, th, _year, _amid, _tmid = _setup(client, cleanup)
    r = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-13", "end_date": "2026-07-20",  # Mon → next Mon
        "reason": "Family function"}).json()
    assert r["days"] == 7  # the Sunday in between is not a working day
    assert r["status"] == "pending"


def test_leave_flow_is_append_only_and_status_is_a_cache(client, cleanup):
    h, th, _year, admin_mid, _tmid = _setup(client, cleanup)
    req = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-15", "end_date": "2026-07-15", "reason": "Fever"}).json()
    assert req["days"] == 1

    # The teacher sees their own; the admin sees the school's.
    assert client.get("/api/v1/staff/leave", headers=th).json()["pending_count"] == 1
    admin_view = client.get("/api/v1/staff/leave", headers=h).json()
    assert admin_view["pending_count"] == 1

    out = client.post(f"/api/v1/staff/leave/{req['id']}/decision", headers=h,
                      json={"action": "approved", "note": "Get well"}).json()
    assert out["status"] == "approved"
    assert [e["action"] for e in out["events"]] == ["applied", "approved"]

    # Deciding twice is refused — the first decision stands until superseded.
    again = client.post(f"/api/v1/staff/leave/{req['id']}/decision", headers=h,
                        json={"action": "rejected"})
    assert again.status_code == 409

    # The history is rows, not a mutated column.
    db = AdminSession()
    try:
        events = db.query(LeaveRequestEvent).filter(
            LeaveRequestEvent.request_id == uuid.UUID(req["id"])).all()
        assert sorted(e.action for e in events) == ["applied", "approved"]
        assert {str(e.actor_member_id) for e in events if e.action == "approved"} == {admin_mid}
        stored = db.get(LeaveRequest, uuid.UUID(req["id"]))
        assert stored.status == "approved"  # cache agrees with the newest event
    finally:
        db.close()

    # Approved leave pre-unticks that person on the attendance sheet.
    roster = client.get("/api/v1/staff/attendance", headers=h,
                        params={"on_date": "2026-07-15"}).json()
    row = next(r for r in roster["roster"] if r["on_leave"])
    assert row["present"] is False and row["leave_reason"] == "Fever"


def test_over_policy_leave_is_flagged_not_blocked(client, cleanup):
    """A school's own limit is advice to the admin, not a wall for an emergency."""
    h, th, _year, _amid, _tmid = _setup(client, cleanup)
    policy = client.get("/api/v1/staff/leave/policy", headers=th).json()
    assert policy == {"leaves_per_year": 8, "leaves_per_month": 1}

    first = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-06", "end_date": "2026-07-06", "reason": "Personal"}).json()
    client.post(f"/api/v1/staff/leave/{first['id']}/decision", headers=h,
                json={"action": "approved"})

    second = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-20", "end_date": "2026-07-20", "reason": "Emergency"})
    assert second.status_code == 200  # accepted...
    body = second.json()
    assert any("monthly limit" in w for w in body["warnings"])  # ...and flagged

    bal = client.get("/api/v1/staff/leave/balance", headers=th).json()
    assert bal["approved_days"] == 1 and bal["pending_days"] == 1
    assert bal["remaining"] == 6

    # Overlapping the same dates is a genuine conflict, and is refused.
    dupe = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-20", "end_date": "2026-07-20", "reason": "Again"})
    assert dupe.status_code == 409


def test_leave_that_exactly_fits_the_allowance_is_not_flagged(client, cleanup):
    """The regression this guards: `balance` already counts the request being
    checked, so testing `remaining < days` charged the same days twice and warned
    on an application that fit exactly."""
    h, th, _year, _amid, _tmid = _setup(client, cleanup)
    # Room for exactly 2 days a year, 2 a month, so the span below fits precisely.
    client.put("/api/v1/staff/leave/policy", headers=h,
               json={"leaves_per_year": 2, "leaves_per_month": 2})

    r = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-15", "end_date": "2026-07-16", "reason": "Travel"}).json()
    assert r["days"] == 2
    assert r["warnings"] == []  # exactly at the limit is not over it

    bal = client.get("/api/v1/staff/leave/balance", headers=th).json()
    assert bal["pending_days"] == 2 and bal["remaining"] == 0

    # One more day genuinely does exceed it, and says so.
    over = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-20", "end_date": "2026-07-20", "reason": "One too many"}).json()
    assert any("yearly allowance" in w for w in over["warnings"])


def test_teacher_cannot_decide_leave_or_set_policy(client, cleanup):
    h, th, _year, _amid, _tmid = _setup(client, cleanup)
    req = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-15", "end_date": "2026-07-15", "reason": "Fever"}).json()
    assert client.post(f"/api/v1/staff/leave/{req['id']}/decision", headers=th,
                       json={"action": "approved"}).status_code == 403
    assert client.put("/api/v1/staff/leave/policy", headers=th,
                      json={"leaves_per_year": 99, "leaves_per_month": 9}).status_code == 403

    # But they can withdraw their own, and the withdrawal is an appended event.
    out = client.post(f"/api/v1/staff/leave/{req['id']}/cancel", headers=th).json()
    assert out["status"] == "cancelled"
    assert [e["action"] for e in out["events"]] == ["applied", "cancelled"]

    # Admin retunes the policy; the balance reflects it immediately.
    client.put("/api/v1/staff/leave/policy", headers=h,
               json={"leaves_per_year": 12, "leaves_per_month": 2})
    assert client.get("/api/v1/staff/leave/balance", headers=th).json()["allowed_per_year"] == 12


def test_leave_dates_backwards_is_rejected(client, cleanup):
    _h, th, _year, _amid, _tmid = _setup(client, cleanup)
    bad = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": "2026-07-20", "end_date": "2026-07-15", "reason": "Typo"})
    assert bad.status_code == 422

    far = date.today() + timedelta(days=400)
    ok = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": far.isoformat(), "end_date": far.isoformat(),
        "reason": "Booked well ahead"})
    assert ok.status_code == 200
