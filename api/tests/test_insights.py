"""DASH3 — the admin operating board.

What each test is defending. These are the claims the board makes that would be
*plausible but wrong* if the code drifted:

  * the capture grid separates "scheduled but not marked" from "no lesson" and
    from "not held" — without that the tab cannot answer its own question;
  * an absence streak needs absence in EVERY marked period of consecutive school
    days, and a day the class marked nothing is skipped, never counted as
    present (a school that stops capturing must not clear its red list);
  * the action rail is idempotent per day — the second Remind returns
    `already_done` and sends nothing, which is the entire reason
    `followup_actions` exists;
  * a substitute must genuinely be free, the cover lands in THEIR My Day, and
    they can actually open the period card (a period you can see but not open is
    worse than one you never saw);
  * duty completion is denominated by periods actually due, and cover moves the
    duty to the substitute;
  * the board is admin-only — a teacher gets 403 on every route;
  * `unplanned` never arrives as a RAG colour.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import FollowupAction, Membership, PeriodSubstitution
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id),
                Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _teacher(client, cleanup, h, org_id, role="teacher"):
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": role}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"],
                              "password": "supersecret1"}).json()
    return ({"Authorization": f"Bearer {login['access_token']}"},
            str(_membership_id(cred["user_id"], org_id)))


def _setup(client, cleanup):
    """An org with a year, timings, one class of two students, two teachers and
    a timetable — the minimum for every board to have something to say."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Board Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    org_id = reg["org"]["id"]
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 3,
        "period_times": [
            {"start": "09:00", "end": "09:40", "kind": "period"},
            {"start": "09:40", "end": "10:20", "kind": "period"},
            {"start": "10:20", "end": "11:00", "kind": "period"},
        ]})

    th, teacher_mid = _teacher(client, cleanup, h, org_id)
    th2, teacher2_mid = _teacher(client, cleanup, h, org_id)

    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": teacher_mid, "periods_per_week": 3}).json()
    students = [
        client.post("/api/v1/students", headers=h,
                    json={"admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": name,
                          "class_id": klass["id"]}).json()
        for name in ("Asha Rao", "Bilal Khan")
    ]
    return {
        "h": h, "th": th, "th2": th2, "org_id": org_id, "year": year, "class": klass,
        "subject": subject, "cs": cs, "students": students,
        "teacher_mid": teacher_mid, "teacher2_mid": teacher2_mid,
        "admin_mid": str(_membership_id(reg["user"]["id"], org_id)),
    }


def _recent_working_days(n: int) -> list[date]:
    """The n most recent Mon–Sat dates, newest first (the year's default)."""
    out: list[date] = []
    d = date.today()
    while len(out) < n:
        if d.weekday() < 6:
            out.append(d)
        d -= timedelta(days=1)
    return out


def _slot(client, h, ctx, weekday, period_no):
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["class"]["id"], "weekday": weekday, "period_no": period_no,
        "class_subject_id": ctx["cs"]["id"], "effective_from": "2026-04-01"})


def _every_period(client, h):
    """Put the org on `every_period` — a register per timetabled period.

    Required explicitly since 2026-08-11, when the default became `first_period`
    (one register a day). A test that marks two periods and expects two marked
    periods is testing THIS mode; on the default the second mark is redirected
    into the first register by design, and the test would be asserting
    per-period behaviour against a school that does not keep it."""
    res = client.patch("/api/v1/org/settings", headers=h,
                       json={"attendance_mode": "every_period"})
    assert res.status_code == 200, res.text


# ── the capture grid ─────────────────────────────────────────────────────────
def test_capture_grid_separates_unmarked_from_no_lesson(client, cleanup):
    """The tab's whole reason to exist: an empty cell must say WHICH kind of
    empty it is. Folding 'no lesson' into 'not marked' would make every school
    look like it stopped taking attendance after lunch."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _every_period(client, h)
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)
    _slot(client, h, ctx, today.weekday(), 2)

    # Mark period 1 only.
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "exceptions": []})

    grid = client.get("/api/v1/insights/attendance", headers=h).json()["capture"]
    row = grid["rows"][0]
    states = {c["period_no"]: c["state"] for c in row["cells"]}
    assert states[1] == "marked"
    assert states[2] == "pending"     # scheduled, nobody marked it
    assert states[3] == "free"        # no lesson at all — not a failure
    assert row["expected"] == 2 and row["marked"] == 1
    assert grid["expected"] == 2


# ── the streak rule ──────────────────────────────────────────────────────────
def test_streak_needs_every_marked_period_and_skips_uncaptured_days(client, cleanup):
    """Two rules in one test, because they interact:
      * absent in SOME marked periods is partial, and breaks a streak;
      * a day the class marked nothing is skipped, not treated as present —
        otherwise a school that stops capturing silently clears its red list."""
    ctx = _setup(client, cleanup)
    h, asha, bilal = ctx["h"], ctx["students"][0], ctx["students"][1]
    _every_period(client, h)
    # The four most recent WORKING days (the year defaults to Mon–Sat). A raw
    # four-day window would silently include a Sunday, which the streak walk
    # correctly skips — and the test would then fail for the right reason at the
    # wrong time, depending on the day it happened to run.
    days = _recent_working_days(4)
    for d in days:
        _slot(client, h, ctx, d.weekday(), 1)
        _slot(client, h, ctx, d.weekday(), 2)

    def mark(d, period_no, absent_ids):
        client.post("/api/v1/attendance/mark", headers=h, json={
            "class_id": ctx["class"]["id"], "period_no": period_no,
            "class_subject_id": ctx["cs"]["id"], "date": d.isoformat(),
            "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids]})

    # days[3], days[1], days[0]: Asha absent in EVERY marked period.
    # days[2]: nothing marked at all — must be skipped, not counted as present.
    # Bilal is absent in only one of two marked periods on days[0] → partial.
    for d in (days[3], days[1], days[0]):
        mark(d, 1, [asha["id"]])
        mark(d, 2, [asha["id"]] + ([bilal["id"]] if d == days[0] else []))

    board = client.get("/api/v1/insights/attendance/streaks", headers=h,
                       params={"min_days": 3}).json()
    ids = {r["student_id"]: r for r in board["rows"]}
    assert asha["id"] in ids, "an uncaptured day must not break the run"
    assert ids[asha["id"]]["streak"] == 3
    assert bilal["id"] not in ids, "absent in some but not all marked periods is partial"

    # V1-0d cross-surface agreement (ux §9): the timeline — which the parent
    # portal and the report card render — must say the same thing about the same
    # day as the streak board just did. One rule, two payloads, zero drift.
    def day_status(student_id, d):
        return client.get(f"/api/v1/students/{student_id}/timeline", headers=h,
                          params={"on_date": d.isoformat()}).json()["day_status"]

    assert day_status(asha["id"], days[0]) == "absent"      # every marked period
    assert day_status(bilal["id"], days[0]) == "partial"    # one of two
    assert day_status(asha["id"], days[2]) == "not_marked"  # nothing captured


# ── the action rail ──────────────────────────────────────────────────────────
def test_guardian_reminder_fires_once_a_day(client, cleanup):
    """Three people looking at the same red row in one morning is the normal
    case. The second press must return already_done and send nothing."""
    ctx = _setup(client, cleanup)
    h, student = ctx["h"], ctx["students"][0]
    client.post(f"/api/v1/students/{student['id']}/guardians", headers=h,
                json={"name": "Parent", "phone": "9876500011", "relation": "mother"})

    first = client.post("/api/v1/insights/actions/guardian_reminded", headers=h,
                        json={"student_id": student["id"]})
    assert first.status_code == 200
    assert first.json()["already_done"] is False

    second = client.post("/api/v1/insights/actions/guardian_reminded", headers=h,
                         json={"student_id": student["id"]}).json()
    assert second["already_done"] is True

    db = AdminSession()
    try:
        rows = db.scalars(select(FollowupAction).where(
            FollowupAction.org_id == uuid.UUID(ctx["org_id"]),
            FollowupAction.kind == "guardian_reminded")).all()
    finally:
        db.close()
    assert len(rows) == 1, "the audit trail must record one send, not two"


def test_followup_lands_on_the_shared_board_assigned_to_someone(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    # The class teacher is who a follow-up defaults to.
    client.patch(f"/api/v1/academics/classes/{ctx['class']['id']}", headers=h,
                 json={"class_teacher_member_id": ctx["teacher_mid"]})

    res = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                      json={"student_id": ctx["students"][0]["id"]}).json()
    assert res["ok"] is True and res["task_id"]
    assert "Follow-ups" in res["message"]

    boards = client.get("/api/v1/boards", headers=h).json()
    names = [b["name"] for b in boards["my_boards"] + boards["other_public"]]
    assert "Follow-ups" in names


# ── cover ────────────────────────────────────────────────────────────────────
def test_substitute_must_be_free_and_the_period_reaches_their_day(client, cleanup):
    """A cover that double-books the substitute leaves a class with nobody in
    it; a cover the substitute can see but not open is worse than none."""
    ctx = _setup(client, cleanup)
    h, th2 = ctx["h"], ctx["th2"]
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)

    # Teacher 2 teaches nothing, so they are free — assign them the period.
    res = client.post("/api/v1/insights/actions/substitute_assigned", headers=h, json={
        "substitution": {
            "date": today.isoformat(), "class_id": ctx["class"]["id"], "period_no": 1,
            "class_subject_id": ctx["cs"]["id"],
            "substitute_member_id": ctx["teacher2_mid"],
            "absent_member_id": ctx["teacher_mid"]}})
    assert res.status_code == 200, res.text
    sub = res.json()["substitution"]
    assert sub["period_no"] == 1

    # It shows up in the substitute's own day, flagged as cover.
    my_day = client.get("/api/v1/classroom/my-day", headers=th2).json()
    covered = [p for p in my_day["periods"] if p["period_no"] == 1]
    assert covered and covered[0]["substituting"] is True
    assert covered[0]["class_id"] == ctx["class"]["id"]

    # …and they can actually OPEN it, despite not teaching the class.
    card = client.get("/api/v1/periods/card", headers=th2, params={
        "class_id": ctx["class"]["id"], "period_no": 1})
    assert card.status_code == 200, card.text

    # Q-37: the cover is on the substitute's OWN week grid — before this it
    # read as a free cell there, the mirror image of S-72 on the admin's side.
    week = client.get("/api/v1/staff/timesheet/week", headers=th2).json()
    day = next(d for d in week["days"] if d["date"] == today.isoformat())
    cell = next(s for s in day["slots"] if s["period_no"] == 1)
    assert cell["kind"] == "cover"
    assert week["covered_periods"] == 1

    # S-72: the admin's day grid shows the same fact from the same read.
    grid = client.get("/api/v1/staff/timesheet/today", headers=h).json()
    row = next(r for r in grid if r["member_id"] == ctx["teacher2_mid"])
    assert next(s for s in row["days"][0]["slots"]
                if s["period_no"] == 1)["kind"] == "cover"

    # A second cover for the same period cancels the first rather than
    # double-booking the class.
    client.post("/api/v1/insights/actions/substitute_assigned", headers=h, json={
        "substitution": {
            "date": today.isoformat(), "class_id": ctx["class"]["id"], "period_no": 1,
            "class_subject_id": ctx["cs"]["id"],
            "substitute_member_id": ctx["admin_mid"],
            "absent_member_id": ctx["teacher_mid"]}})
    db = AdminSession()
    try:
        live = db.scalars(select(PeriodSubstitution).where(
            PeriodSubstitution.org_id == uuid.UUID(ctx["org_id"]),
            PeriodSubstitution.cancelled_at.is_(None))).all()
    finally:
        db.close()
    assert len(live) == 1, "only one live cover per period"


def test_cover_cannot_land_on_someone_on_approved_leave(client, cleanup):
    """S-82: a future date has no staff-absence row, so before this clause an
    admin arranging Friday's cover from a leave approval (D-27) could hand it
    to a teacher who is herself on approved leave that Friday."""
    ctx = _setup(client, cleanup)
    h, th2 = ctx["h"], ctx["th2"]
    # Next Monday — a working day in every default calendar, safely future.
    on = date.today() + timedelta(days=(7 - date.today().weekday()) or 7)
    _slot(client, h, ctx, on.weekday(), 1)

    req = client.post("/api/v1/staff/leave", headers=th2, json={
        "start_date": on.isoformat(), "end_date": on.isoformat(),
        "reason": "Family function"}).json()
    client.post(f"/api/v1/staff/leave/{req['id']}/decision", headers=h,
                json={"action": "approved"})

    bad = client.post("/api/v1/insights/actions/substitute_assigned", headers=h, json={
        "substitution": {
            "date": on.isoformat(), "class_id": ctx["class"]["id"], "period_no": 1,
            "class_subject_id": ctx["cs"]["id"],
            "substitute_member_id": ctx["teacher2_mid"],
            "absent_member_id": ctx["teacher_mid"]}})
    assert bad.status_code == 409
    assert "approved leave" in bad.json()["error"]["message"]


def test_a_busy_substitute_is_refused_with_the_reason(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)

    # The class's own teacher is teaching that very period — refuse.
    bad = client.post("/api/v1/insights/actions/substitute_assigned", headers=h, json={
        "substitution": {
            "date": today.isoformat(), "class_id": ctx["class"]["id"], "period_no": 1,
            "class_subject_id": ctx["cs"]["id"],
            "substitute_member_id": ctx["teacher_mid"]}})
    assert bad.status_code == 409
    assert "already teaching" in bad.json()["error"]["message"]


# ── duties ───────────────────────────────────────────────────────────────────
def test_duty_denominator_is_periods_actually_due(client, cleanup):
    """A teacher with two periods who marked one is at 50% on attendance — not
    0%, and not scored against the whole timetable."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)
    _slot(client, h, ctx, today.weekday(), 2)
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "exceptions": []})

    board = client.get("/api/v1/insights/tasks", headers=h).json()
    mine = next((d for d in board["duties"] if d["member_id"] == ctx["teacher_mid"]), None)
    if mine is None:      # a non-working weekday has no duties at all
        assert board["duties"] == []
        return
    assert mine["due_periods"] == 2
    assert mine["attendance_marked"] == 1


# ── guards and states ────────────────────────────────────────────────────────
def test_every_board_is_admin_only(client, cleanup):
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    for path in ("/api/v1/insights/overview", "/api/v1/insights/attendance",
                 "/api/v1/insights/attendance/streaks", "/api/v1/insights/staff",
                 "/api/v1/insights/syllabus", "/api/v1/insights/homework",
                 "/api/v1/insights/tasks", "/api/v1/insights/exams"):
        assert client.get(path, headers=th).status_code == 403, path
    assert client.post("/api/v1/insights/actions/guardian_reminded", headers=th,
                       json={"student_id": ctx["students"][0]["id"]}).status_code == 403


def test_unplanned_is_a_state_not_a_colour(client, cleanup):
    """V2-P11's hard-won distinction. A class-subject with a syllabus but no plan
    must arrive as `unplanned`, never as green."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    unit = client.post("/api/v1/planner/syllabus/units", headers=h, json={
        "class_subject_id": ctx["cs"]["id"], "title": "Matter"}).json()
    client.post("/api/v1/planner/syllabus/topics", headers=h, json={
        "unit_id": unit["id"], "title": "States of matter", "est_periods": 2})

    board = client.get("/api/v1/insights/syllabus", headers=h).json()
    row = next(r for r in board["rows"] if r["class_subject_id"] == ctx["cs"]["id"])
    assert row["status"] == "unplanned"
    assert row["status"] not in ("green", "amber", "red")
    # The school node counts it as unplanned, never as on-track.
    assert board["school"]["unplanned"] >= 1
    assert board["school"]["on_track"] == 0


def test_boards_survive_a_school_with_a_calendar(client, cleanup):
    """Every real school has holidays on its calendar; no test org did.

    Both the streak walk and the live board flatten calendar events to skip
    non-teaching days, and `expand_blocked_dates` is a PURE function over tuples —
    handing it ORM rows raises `'CalendarEvent' object is not subscriptable` the
    moment a single event exists. That shipped in SF-1's leave arithmetic too and
    went unseen for exactly this reason, so the fixture now has a holiday in it.
    """
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "holiday", "title": "Founders Day",
        "start_date": "2026-08-15", "end_date": "2026-08-15", "affects_teaching": True})
    # Marked attendance WITH an absence, so the streak walk gets past its
    # early returns and actually reaches the calendar flattening.
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": 1,
        "class_subject_id": ctx["cs"]["id"],
        "exceptions": [{"student_id": ctx["students"][0]["id"], "status": "absent"}]})

    for path in ("/api/v1/insights/attendance", "/api/v1/insights/attendance/streaks",
                 "/api/v1/insights/staff", "/api/v1/insights/overview"):
        assert client.get(path, headers=h).status_code == 200, path
    # …and the leave arithmetic that counts working days around it.
    applied = client.post("/api/v1/staff/leave", headers=ctx["th"], json={
        "start_date": "2026-08-15", "end_date": "2026-08-15", "reason": "Family"})
    assert applied.status_code == 200, applied.text


def test_staff_board_says_not_marked_rather_than_a_full_house(client, cleanup):
    """`marked=False` is information. A board that renders it as "everyone in"
    would let an unmarked morning read as a perfect one."""
    ctx = _setup(client, cleanup)
    board = client.get("/api/v1/insights/staff", headers=ctx["h"]).json()
    assert board["presence"]["marked"] is False
    assert board["now"]["phase"] in ("before", "period", "break", "after", "unset", "holiday")
    assert board["leave"]["pending"] == 0


# ── the overview ─────────────────────────────────────────────────────────────
def test_overview_summarises_every_module_without_inventing_a_number(client, cleanup):
    """The overview replaced six one-number tiles with a block per module.

    What must hold: all six modules are present, each with a sentence and two or
    three figures (a fourth turns the summary back into the tab), and an
    un-captured morning is summarised as un-captured — never as 0% present, and
    never red, or the board opens red every single morning.
    """
    ctx = _setup(client, cleanup)
    today = date.today()
    _slot(client, ctx["h"], ctx, today.weekday(), 1)

    board = client.get("/api/v1/insights/overview", headers=ctx["h"]).json()
    sections = {s["key"]: s for s in board["sections"]}
    assert set(sections) == {"attendance", "staff", "syllabus", "homework", "tasks", "exams"}
    for key, s in sections.items():
        assert s["headline"], key
        assert 2 <= len(s["metrics"]) <= 3, key
        assert s["href"].startswith("/"), key

    att = {mtr["key"]: mtr for mtr in sections["attendance"]["metrics"]}
    assert att["present"]["value"] == "—"          # nothing marked ≠ 0% present
    assert att["capture"]["tone"] != "red"         # ...and ≠ a failure
    # The rail is derived: nothing has been captured, so nothing is "waiting" on
    # an admin whose school day may not have started.
    assert all(a["count"] >= 0 for a in board["actions"])


def test_overview_keeps_unplanned_a_state_not_a_colour(client, cleanup):
    """V2-P11's distinction, carried into the summary: a class-subject with a
    syllabus and no plan must never lift or lower a RAG figure."""
    ctx = _setup(client, cleanup)
    unit = client.post("/api/v1/planner/syllabus/units", headers=ctx["h"], json={
        "class_subject_id": ctx["cs"]["id"], "title": "Matter"}).json()
    client.post("/api/v1/planner/syllabus/topics", headers=ctx["h"], json={
        "unit_id": unit["id"], "title": "States of matter", "est_periods": 2})

    board = client.get("/api/v1/insights/overview", headers=ctx["h"]).json()
    syllabus = next(s for s in board["sections"] if s["key"] == "syllabus")
    metrics = {m["key"]: m for m in syllabus["metrics"]}
    assert metrics["unplanned"]["value"] == "1"
    assert metrics["unplanned"]["tone"] == "neutral"   # a state, never a colour
    assert metrics["pace"]["value"] == "—"             # nothing rated, so no pace


# ── V1-0e: the rail dedupes on the open task (D-47) ──────────────────────────
def test_followup_dedupes_on_the_open_task_not_the_day(client, cleanup):
    """Three presses for the same child must extend ONE open follow-up, never
    file identical rows — the old rule was per calendar day, so three days of
    absence created three tasks in one teacher's list."""
    ctx = _setup(client, cleanup)
    h, student = ctx["h"], ctx["students"][0]

    first = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                        json={"student_id": student["id"]}).json()
    assert first["already_done"] is False
    assert first["task_id"]

    second = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                         json={"student_id": student["id"]}).json()
    assert second["already_done"] is True
    assert second["task_id"] == first["task_id"], "one open task, nudged — not a twin"
    assert "due date moved" in second["message"]


# ── V1-0e: a substitute can check homework (S-93) ────────────────────────────
def test_substitute_can_check_homework_for_a_class_they_covered(client, cleanup):
    """`homework_checks.checked_by_member_id` exists precisely so someone other
    than the setter can be on record as the checker."""
    ctx = _setup(client, cleanup)
    h, th, th2 = ctx["h"], ctx["th"], ctx["th2"]
    today = date.today()
    _slot(client, h, ctx, today.weekday(), 1)

    hw = client.post("/api/v1/classroom/homework", headers=th, json={
        "class_subject_id": ctx["cs"]["id"], "text": "Ex 1",
        "date": today.isoformat()}).json()

    # A colleague with no connection to the class is still refused…
    denied = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=th2,
                         json={"results": []})
    assert denied.status_code == 403

    # …until they cover a period for that class.
    client.post("/api/v1/insights/actions/substitute_assigned", headers=h, json={
        "substitution": {
            "date": today.isoformat(), "class_id": ctx["class"]["id"], "period_no": 1,
            "class_subject_id": ctx["cs"]["id"],
            "substitute_member_id": ctx["teacher2_mid"],
            "absent_member_id": ctx["teacher_mid"]}})
    ok = client.post(f"/api/v1/classroom/homework/{hw['id']}/check", headers=th2,
                     json={"results": []})
    assert ok.status_code == 200, ok.text
    assert ok.json()["checked"] is True
