"""Once-per-day attendance (`first_period`) — founder, 2026-08-05.

Most schools take ONE register a day. The mode has existed since V1-3, but the
rules around it were written as *"attendance happens in period 1"*, which is a
different and weaker claim: it asks the wrong thing all afternoon, and it has no
answer at all for the morning period 1 does not happen.

The claim these tests defend is **the register belongs to the DAY**:

  * marking from any period lands on the day's ONE register — a teacher fixing a
    mis-tap in period 5 edits this morning's roll rather than opening a second
    one. Without this the day carries two marked periods and
    `classify_marked_day` scores a child who was away all day as `partial`,
    because two people touched the register;
  * the capture sheet READS the same register it WRITES: opening period 5 shows
    this morning's marks, not a blank "everyone present" that would be saved
    over the top of them;
  * the redirected write must not relabel the period it lands on with the
    caller's subject;
  * My Day asks for the register wherever it is still owed — every period while
    it is missing, no period once it is done, except the one holding it (its
    taker can still correct it);
  * the expected-registers denominator is the MODE's, so a once-per-day school
    never reads "1 of 7 periods marked" — six invented failures out of a day
    captured exactly as intended;
  * guardians are alerted once, by the register that was actually taken —
    whichever period that was.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models import ClassPeriod
from tests.conftest import AdminSession
from tests.test_insights import _recent_working_days, _setup, _slot


def _once_per_day(client, h):
    """Put the org on `first_period` — the mode this suite is about."""
    res = client.patch("/api/v1/org/settings", headers=h,
                       json={"attendance_mode": "first_period"})
    assert res.status_code == 200, res.text
    assert res.json()["attendance_mode"] == "first_period"


def _mark(client, h, ctx, period_no, absent_ids=(), on=None, class_subject_id=...):
    body = {
        "class_id": ctx["class"]["id"], "period_no": period_no,
        "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids],
    }
    if class_subject_id is not ...:
        body["class_subject_id"] = class_subject_id
    else:
        body["class_subject_id"] = ctx["cs"]["id"]
    if on is not None:
        body["date"] = on.isoformat()
    return client.post("/api/v1/attendance/mark", headers=h, json=body)


def _marked_periods(org_id, class_id, d):
    db = AdminSession()
    try:
        import uuid as _uuid
        return sorted(db.scalars(
            select(ClassPeriod.period_no).where(
                ClassPeriod.org_id == _uuid.UUID(org_id),
                ClassPeriod.class_id == _uuid.UUID(class_id),
                ClassPeriod.date == d,
                ClassPeriod.attendance_marked_at.is_not(None))))
    finally:
        db.close()


def _today(ctx):
    today = _recent_working_days(1)[0]
    if today != date.today():
        pytest.skip("today is not a working day")
    return today


def test_a_second_period_edits_the_days_register_not_a_second_one(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)

    away = ctx["students"][0]
    first = _mark(client, h, ctx, 1, absent_ids=[away["id"]], on=today).json()
    assert first["period_no"] == 1

    # She notices in period 5 that she tapped the wrong child. Marking from
    # there must EDIT the morning register, not open an evening one.
    second = _mark(client, h, ctx, 5, absent_ids=[ctx["students"][1]["id"]], on=today).json()
    assert second["period_no"] == 1, "the write must land on the day's register"

    assert _marked_periods(ctx["org_id"], ctx["class"]["id"], today) == [1], \
        "a once-per-day school must never carry two marked periods on one day"

    # And the correction stuck: exactly one child away, the second one.
    assert second["absent_count"] == 1
    assert second["present_count"] == len(ctx["students"]) - 1


def test_the_sheet_opens_on_the_days_register_from_any_period(client, cleanup):
    """The read and the write have to agree about which period holds the day.

    If period 5 read a blank sheet while `mark` wrote to period 1, the teacher
    would see "everyone present", save it, and silently wipe the morning's
    absences — the worst possible outcome and an entirely invisible one."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)
    away = ctx["students"][0]
    _mark(client, h, ctx, 1, absent_ids=[away["id"]], on=today)

    sheet = client.get("/api/v1/attendance/roster", headers=h, params={
        "class_id": ctx["class"]["id"], "period_no": 5,
        "on_date": today.isoformat()}).json()
    assert sheet["marked"] is True, "period 5 must open on the day's register"
    assert sheet["period_no"] == 1
    row = next(r for r in sheet["roster"] if r["student_id"] == away["id"])
    assert row["status"] == "absent"


def test_the_redirected_write_does_not_relabel_the_period(client, cleanup):
    """The register moves; the PERIOD does not. Carrying the caller's subject
    across would relabel period 1 as Science because the Science teacher fixed a
    typo in period 3."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)
    _mark(client, h, ctx, 1, on=today)

    db = AdminSession()
    try:
        import uuid as _uuid
        before = db.scalar(select(ClassPeriod.class_subject_id).where(
            ClassPeriod.class_id == _uuid.UUID(ctx["class"]["id"]),
            ClassPeriod.date == today, ClassPeriod.period_no == 1))
    finally:
        db.close()

    _mark(client, h, ctx, 4, on=today, class_subject_id=ctx["cs"]["id"])

    db = AdminSession()
    try:
        import uuid as _uuid
        after = db.scalar(select(ClassPeriod.class_subject_id).where(
            ClassPeriod.class_id == _uuid.UUID(ctx["class"]["id"]),
            ClassPeriod.date == today, ClassPeriod.period_no == 1))
    finally:
        db.close()
    assert after == before


def test_my_day_asks_wherever_it_is_owed_and_nowhere_once_done(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _once_per_day(client, h)
    today = _today(ctx)
    for p in (1, 2, 3):
        _slot(client, h, ctx, today.weekday(), p)

    # Nothing captured: EVERY period offers it, because period 1 may not happen
    # and the register still has to get taken.
    day = client.get("/api/v1/classroom/my-day", headers=th).json()
    periods = [p for p in day["periods"] if p["class_id"] == ctx["class"]["id"]]
    assert len(periods) >= 2
    assert all(p["marks_attendance"] for p in periods)
    assert all(p["day_attendance_taken"] is False for p in periods)

    # Taken in period 2 (period 1 was cancelled). Now only period 2 keeps the
    # row — its taker can still correct it — and the afternoon stops asking.
    _mark(client, th, ctx, 2, on=today)
    day = client.get("/api/v1/classroom/my-day", headers=th).json()
    periods = {p["period_no"]: p for p in day["periods"]
               if p["class_id"] == ctx["class"]["id"]}
    assert periods[2]["marks_attendance"] is True
    assert periods[2]["attendance_marked"] is True
    for pno, p in periods.items():
        assert p["day_attendance_taken"] is True
        if pno != 2:
            assert p["marks_attendance"] is False, \
                f"period {pno} is still asking for a register taken at period 2"


def test_the_period_card_says_the_day_is_done_rather_than_going_silent(client, cleanup):
    """Two different reasons a card has no attendance section, and the teacher
    cares which: it was already taken, or this period never marks."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)
    _slot(client, h, ctx, today.weekday(), 3)
    _mark(client, th, ctx, 1, on=today)

    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 3}).json()
    assert card["marks_attendance"] is False
    assert card["day_attendance_taken"] is True


def test_the_denominator_is_the_modes_not_the_timetables(client, cleanup):
    """`1 of 7 periods marked` in a once-per-day school is a screen inventing
    six failures out of a day captured exactly as intended."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _once_per_day(client, h)
    today = _today(ctx)
    for p in (1, 2, 3):
        _slot(client, h, ctx, today.weekday(), p)
    _mark(client, h, ctx, 1, on=today)

    att = client.get(f"/api/v1/my-class/{ctx['class']['id']}/overview",
                     headers=h).json()["attendance"]
    assert att["periods_scheduled"] == 1
    assert att["periods_marked"] == 1


def test_the_board_points_every_teacher_at_the_same_register(client, cleanup):
    """Once-per-day: the suggested period is the day's register wherever it is,
    never each teacher's own first slot — or two of them write two registers."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)

    board = client.get("/api/v1/attendance/my-classes", headers=th).json()
    assert board["once_per_day"] is True
    row = next(r for r in board["classes"] if r["class_id"] == ctx["class"]["id"])
    assert row["suggested_period_no"] == 1

    _mark(client, th, ctx, 3, on=today)     # nothing held yet → lands on 3
    board = client.get("/api/v1/attendance/my-classes", headers=th).json()
    row = next(r for r in board["classes"] if r["class_id"] == ctx["class"]["id"])
    assert row["marked"] is True
    assert row["suggested_period_no"] == 3, "everyone must be sent to the held register"


def test_guardians_are_alerted_once_by_whichever_period_took_it(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _once_per_day(client, h)
    today = _today(ctx)
    _slot(client, h, ctx, today.weekday(), 1)
    away = ctx["students"][0]
    client.post(f"/api/v1/students/{away['id']}/guardians", headers=h,
                json={"name": "Meera Rao", "phone": "+919000000901", "is_primary": True})

    # Period 1 never happened; period 3 takes the roll.
    first = _mark(client, h, ctx, 3, absent_ids=[away["id"]], on=today).json()
    assert first["alerted_count"] == 1

    # A correction later in the day must not message the family a second time.
    again = _mark(client, h, ctx, 6, absent_ids=[away["id"]], on=today).json()
    assert again["period_no"] == 3
    assert again["alerted_count"] == 0
