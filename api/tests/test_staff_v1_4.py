"""V1-4 — staff, leave, cover and time.

What each test is defending, packet decision by packet decision:

  * `D-04`/`S-18`/`S-31` — half-day carries AM/PM and costs half a day; late is
    present and costs nothing. The whole point is `D-78`'s month summary, so the
    day and the month must agree about what one Tuesday was worth.
  * `S-31`/`S-82` — a half-day only blocks its own half. Refusing a substitute
    for the half she IS in would hand the admin an empty candidate list on the
    exact morning cover matters; accepting one for the half she is NOT in is the
    double-booking `busy_reason` exists to stop.
  * `D-27`/`S-80` — approving a leave hands back the days that need cover.
  * `D-29`/`S-79` — the picker says what the class GAINS (the next planned topic)
    and warns about what the substitute gives up.
  * `D-78`/`S-34` — days worked out of working days, and **a day nobody marked
    is `not marked`, never absent.** That distinction is the one line in this
    packet that becomes a financial rule in v2.
  * `S-68`/`S-70`/`S-75` — hostel evenings counted beside periods, her own
    numbers given back, and the picker pre-selecting without writing anything.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Membership
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


PERIOD_TIMES = [
    {"start": "09:00", "end": "09:40", "kind": "period"},
    {"start": "09:40", "end": "10:20", "kind": "period"},
    {"start": "10:20", "end": "11:00", "kind": "lunch"},
    {"start": "11:00", "end": "11:40", "kind": "period"},
    {"start": "11:40", "end": "12:20", "kind": "period"},
]


def _teacher(client, h, org_id, cleanup):
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"],
                              "password": "supersecret1"}).json()
    return ({"Authorization": f"Bearer {login['access_token']}"},
            str(_membership_id(cred["user_id"], org_id)))


def _setup(client, cleanup):
    """An org with a year, timings with a lunch break, a class and two teachers."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "V14 Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    org_id = reg["org"]["id"]
    cleanup["orgs"].append(uuid.UUID(org_id))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 4,
        "period_times": PERIOD_TIMES})

    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": f"Maths {uuid.uuid4().hex[:4]}"}).json()
    th, teacher_mid = _teacher(client, h, org_id, cleanup)
    th2, teacher2_mid = _teacher(client, h, org_id, cleanup)
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "periods_per_week": 4, "teacher_member_id": teacher_mid}).json()

    return {"h": h, "th": th, "th2": th2, "org_id": org_id, "year": year,
            "class": klass, "subject": subject, "cs": cs,
            "teacher_mid": teacher_mid, "teacher2_mid": teacher2_mid,
            "admin_mid": str(_membership_id(reg["user"]["id"], org_id))}


def _next_weekday(anchor: date, weekday: int) -> date:
    """The next date on or after `anchor` falling on `weekday`."""
    return anchor + timedelta(days=(weekday - anchor.weekday()) % 7)


# ── D-04 / S-18 / S-31: the day is worth what it was ─────────────────────────
def test_half_day_and_late_are_worth_what_they_are():
    """The one place a marked day becomes a number of days present."""
    from app.services.staff_attendance import present_value

    assert present_value("present") == 1.0
    assert present_value("late") == 1.0, "late is a flag to be seen, not a deduction (S-19)"
    assert present_value("half_day") == 0.5
    assert present_value("absent") == 0.0


def test_half_day_periods_split_at_lunch():
    """S-31: '0.5 days' cannot tell the cover board which periods to fill."""
    assert school_clock.periods_before_lunch(PERIOD_TIMES) == 2
    assert school_clock.half_day_periods(PERIOD_TIMES, "am") == [1, 2]
    assert school_clock.half_day_periods(PERIOD_TIMES, "pm") == [3, 4]
    # No break at all: the day still has to be halvable, and the split is shown.
    no_break = [{"start": "09:00", "end": "09:40", "kind": "period"}] * 3
    assert school_clock.half_day_periods(no_break, "am") == [1, 2]


def test_marking_and_half_day_share_one_lunch_cut():
    """twice_daily's 'after lunch' and a half-day's PM must be the same cut, or
    a school on twice_daily reads two different middays."""
    after_lunch = school_clock.marking_period_nos(PERIOD_TIMES, "twice_daily")[1]
    assert after_lunch == school_clock.half_day_periods(PERIOD_TIMES, "pm")[0]


def test_staff_day_carries_half_day_and_late(client, cleanup):
    ctx = _setup(client, cleanup)
    h, t1, t2 = ctx["h"], ctx["teacher_mid"], ctx["teacher2_mid"]
    on = "2026-07-15"

    r = client.post("/api/v1/staff/attendance", headers=h, json={
        "date": on,
        "marks": [{"member_id": t1, "status": "half_day", "portion": "pm",
                   "note": "Doctor"},
                  {"member_id": t2, "status": "late"}]}).json()

    rows = {row["member_id"]: row for row in r["roster"]}
    assert rows[t1]["status"] == "half_day" and rows[t1]["portion"] == "pm"
    assert rows[t2]["status"] == "late"
    # Late is IN — the boolean every existing caller reads must not change
    # meaning under it.
    assert rows[t2]["present"] is True
    assert r["half_day_count"] == 1 and r["late_count"] == 1
    # Director (1.0) + late teacher (1.0) + half-day teacher (0.5).
    assert r["present_days"] == 2.5

    # Full replace still holds: re-marking with nothing clears both rows.
    again = client.post("/api/v1/staff/attendance", headers=h,
                        json={"date": on, "marks": []}).json()
    assert again["half_day_count"] == 0 and again["late_count"] == 0
    assert again["present_days"] == 3.0


# ── S-31 / S-82: a half-day only blocks its own half ─────────────────────────
def test_half_day_blocks_only_its_own_periods(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    on = date(2026, 7, 15)  # a Wednesday
    client.post("/api/v1/staff/attendance", headers=h, json={
        "date": on.isoformat(),
        "marks": [{"member_id": ctx["teacher2_mid"], "status": "half_day",
                   "portion": "am"}]})

    from app.core.context import CurrentMember  # noqa: PLC0415
    from app.services.substitution import SubstitutionService  # noqa: PLC0415

    db = AdminSession()
    try:
        svc = SubstitutionService(db)
        org = uuid.UUID(ctx["org_id"])
        mid = uuid.UUID(ctx["teacher2_mid"])
        # Period 1 is in the half she missed…
        assert "am half" in (svc.busy_reason(org, mid, on, 1) or "")
        # …period 3 is after lunch, and she was in for it.
        assert svc.busy_reason(org, mid, on, 3) is None
        assert CurrentMember is not None  # import kept honest
    finally:
        db.close()


# ── D-27 / S-80: approving leave hands back the cover flow ───────────────────
def test_approving_leave_returns_the_days_needing_cover(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    # A Monday-to-Wednesday span in the future, so every day still needs cover.
    start = _next_weekday(date.today() + timedelta(days=3), 0)
    end = start + timedelta(days=2)

    applied = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "reason": "Family function"}).json()
    assert applied["days"] == 3.0

    decided = client.post(f"/api/v1/staff/leave/{applied['id']}/decision", headers=h,
                          json={"action": "approved"}).json()
    assert decided["status"] == "approved"
    # D-27: the admin who just pressed Approve is handed the days, not asked to
    # remember on Friday morning.
    assert decided["cover_dates"] == [
        (start + timedelta(days=i)).isoformat() for i in range(3)]

    # S-82: and the cover flow refuses to hand those periods to someone who is
    # herself on approved leave that day.
    from app.services.substitution import SubstitutionService  # noqa: PLC0415

    db = AdminSession()
    try:
        reason = SubstitutionService(db).busy_reason(
            uuid.UUID(ctx["org_id"]), uuid.UUID(ctx["teacher_mid"]), start, 1)
        assert reason == "on approved leave that day"
    finally:
        db.close()


def test_half_day_leave_costs_half_a_day_and_names_its_half(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    when = _next_weekday(date.today() + timedelta(days=3), 1)

    applied = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": when.isoformat(), "end_date": when.isoformat(),
        "reason": "Bank", "is_half_day": True, "portion": "pm"}).json()
    assert applied["days"] == 0.5
    assert applied["is_half_day"] is True and applied["portion"] == "pm"

    balance = client.get("/api/v1/staff/leave/balance", headers=th).json()
    assert balance["pending_days"] == 0.5
    assert balance["remaining"] == balance["allowed_per_year"] - 0.5

    # A half-day over a span is refused rather than silently halving a week.
    bad = client.post("/api/v1/staff/leave", headers=th, json={
        "start_date": (when + timedelta(days=7)).isoformat(),
        "end_date": (when + timedelta(days=9)).isoformat(),
        "reason": "Nope", "is_half_day": True})
    assert bad.status_code == 422, bad.text

    # Approved, it pre-fills the staff sheet as a HALF day, not an absence.
    client.post(f"/api/v1/staff/leave/{applied['id']}/decision", headers=h,
                json={"action": "approved"})
    sheet = client.get("/api/v1/staff/attendance", headers=h,
                       params={"on_date": when.isoformat()}).json()
    row = next(r for r in sheet["roster"] if r["member_id"] == ctx["teacher_mid"])
    assert row["status"] == "half_day" and row["portion"] == "pm"


# ── D-29 / S-79: what the class gains, what the substitute gives up ──────────
def test_cover_picker_names_the_next_topic_and_the_cost(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    on = date.today()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["class"]["id"], "weekday": on.weekday(), "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "effective_from": "2026-04-01"})

    # A syllabus with one sized topic, drafted into the plan.
    unit = client.post("/api/v1/planner/syllabus/units", headers=h, json={
        "class_subject_id": ctx["cs"]["id"], "title": "Fractions"}).json()
    client.post("/api/v1/planner/syllabus/topics", headers=h, json={
        "unit_id": unit["id"], "title": "Multiplying fractions", "est_periods": 2})
    client.post(f"/api/v1/planner/plan/{ctx['cs']['id']}/draft", headers=h, json={})

    # The second teacher also teaches the subject somewhere, so she can move it.
    other = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "7", "section": "A"}).json()
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": other["id"], "subject_id": ctx["subject"]["id"],
        "periods_per_week": 4, "teacher_member_id": ctx["teacher2_mid"]})

    client.post("/api/v1/staff/attendance", headers=h, json={
        "date": on.isoformat(), "absent_member_ids": [ctx["teacher_mid"]]})
    # She recorded exam work for that period — shown, never a block (S-74).
    client.put("/api/v1/staff/timesheet/entry", headers=h, json={
        "member_id": ctx["teacher2_mid"], "date": on.isoformat(), "period_no": 1,
        "work_type": "exam_work", "note": "Class 10 scripts"})

    impact = client.get(f"/api/v1/insights/staff/{ctx['teacher_mid']}/impact",
                        headers=h).json()
    period = next(p for p in impact["periods"] if p["period_no"] == 1)
    assert period["next_topic"] == "Multiplying fractions"

    pick = next(c for c in period["candidates"]
                if c["member_id"] == ctx["teacher2_mid"])
    assert pick["can_teach_next_topic"] is True
    assert "Multiplying fractions" in pick["reason"]
    assert pick["rank"] == 1, "the cover that is a real lesson ranks first"
    # …and what she gives up is still on the row, so the admin can weigh it.
    assert pick["work_label"] == "Exam work"


# ── D-78 / S-34: the month summary ───────────────────────────────────────────
def test_month_summary_counts_days_worked_and_never_calls_a_gap_an_absence(
        client, cleanup):
    ctx = _setup(client, cleanup)
    h, teacher = ctx["h"], ctx["teacher_mid"]
    # Three consecutive working days in a settled past month.
    days = [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]  # Mon/Tue/Wed

    client.post("/api/v1/staff/attendance", headers=h,
                json={"date": days[0].isoformat(), "marks": []})
    client.post("/api/v1/staff/attendance", headers=h, json={
        "date": days[1].isoformat(),
        "marks": [{"member_id": teacher, "status": "half_day", "portion": "am"}]})
    # days[2] is deliberately NEVER marked.

    out = client.get("/api/v1/staff/month", headers=h, params={"month": "2026-06"}).json()
    row = next(r for r in out["rows"] if r["member_id"] == teacher)

    assert out["days_marked"] == 2
    assert row["days_marked"] == 2
    assert row["days_present"] == 1.5, "a half-day is half a day worked"
    assert row["days_absent"] == 0.5
    assert row["half_days"] == 1
    # S-34 — THE rule. The unmarked day is its own count, in its own word, and
    # it never lands in days_absent. In v2 this is the difference between a
    # clerical gap and an unpaid day.
    assert row["days_not_marked"] == row["working_days"] - 2
    assert row["days_not_marked"] > 0
    assert row["days_present"] + row["days_absent"] == row["days_marked"]

    # A teacher reads her own month and nobody else's.
    mine = client.get("/api/v1/staff/month", headers=ctx["th"],
                      params={"month": "2026-06"}).json()
    assert [r["member_id"] for r in mine["rows"]] == [teacher]
    denied = client.get("/api/v1/staff/month", headers=ctx["th"],
                        params={"month": "2026-06", "member_id": ctx["admin_mid"]})
    assert denied.status_code == 403
    # No money anywhere on it (D-25/D-78).
    assert not any(k in row for k in ("pay", "salary", "amount", "deduction"))


# ── S-68 / S-70 / S-75: the teacher's own side ───────────────────────────────
def test_her_week_gives_the_numbers_back_and_the_picker_pre_selects(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    monday = _next_weekday(date.today() - timedelta(days=28), 0)
    # Six weeks of "notebook checking" in Monday period 3 — her usual.
    for i in range(3):
        client.put("/api/v1/staff/timesheet/entry", headers=th, json={
            "date": (monday - timedelta(weeks=i + 1)).isoformat(), "period_no": 3,
            "work_type": "notebook_checking"})

    # S-68 — an evening block she runs, three nights a week.
    client.post("/api/v1/sessions", headers=h, json={
        "name": "Evening prep", "owner_member_id": ctx["teacher_mid"],
        "weekdays": [0, 1, 2], "time": "18:00", "kind": "study"})

    week = client.get("/api/v1/staff/timesheet/week", headers=th,
                      params={"week_start": monday.isoformat()}).json()
    day = next(d for d in week["days"] if d["date"] == monday.isoformat())
    cell = next(s for s in day["slots"] if s["period_no"] == 3)

    # S-75: the picker opens pre-selected and NOTHING has been written.
    assert cell["kind"] == "free"
    assert cell["suggested_work_type"] == "notebook_checking"
    assert cell["suggested_work_label"] == "Notebook checking"
    assert week["work_periods"] == 0

    # S-70/S-68: her evenings are her record, counted BESIDE the periods.
    assert week["evening_sessions"] == 3
    assert day["evening_labels"] == ["Evening prep · 18:00"]


def test_month_grid_is_shape_not_gaps(client, cleanup):
    """D-18/S-64: holidays and leave come from the calendar, so a closed school
    never reads as a month of holes."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "title": "Founder's Day",
        "start_date": "2026-06-10", "end_date": "2026-06-10",
        "type": "holiday", "affects_teaching": True})

    grid = client.get("/api/v1/staff/timesheet/month", headers=th,
                      params={"month": "2026-06"}).json()
    by_date = {d["date"]: d for d in grid["days"]}
    assert by_date["2026-06-10"]["state"] == "holiday"
    assert by_date["2026-06-10"]["label"] == "Founder's Day"
    assert by_date["2026-06-07"]["state"] == "off"        # a Sunday
    assert by_date["2026-06-08"]["state"] == "working"
    # A closed day contributes no free periods — it is not a hole in her record.
    assert by_date["2026-06-10"]["free"] == 0
