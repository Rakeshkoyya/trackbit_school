"""V2-P6: the class-period anchor — open-on-action lifecycle, and the double-period
bug it exists to fix (two periods of one class-subject on one day are independent).
"""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import ClassPeriod, LessonLog, Membership
from tests.conftest import AdminSession

IST = ZoneInfo("Asia/Kolkata")


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
                      json={"org_name": "Period Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    # Start the year on this week's Monday so the drafted plan's first week IS the
    # current week — otherwise no topic is planned for today and the cards are blank.
    today = datetime.now(IST).date()
    monday = today - timedelta(days=today.weekday())
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": monday.isoformat(),
                             "end_date": (monday + timedelta(days=364)).isoformat()}).json()
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "3", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Mathematics"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": mid, "periods_per_week": 6}).json()
    client.post("/api/v1/students", headers=h, json={
        "admission_no": uuid.uuid4().hex[:10], "full_name": "Aisha", "class_id": klass["id"]})
    return h, year, mid, klass, cs


def _periods(class_id):
    db = AdminSession()
    try:
        return db.query(ClassPeriod).filter(
            ClassPeriod.class_id == uuid.UUID(class_id)).count()
    finally:
        db.close()


def _double_period(client, h, klass, cs):
    """Put the same class-subject on TWO of today's periods — the case that used to
    make both My Day cards render off one shared class-subject row."""
    wd = datetime.now(ZoneInfo("Asia/Kolkata")).date().weekday()
    for period_no in (1, 4):
        client.put("/api/v1/timetable/slot", headers=h, json={
            "class_id": klass["id"], "weekday": wd, "period_no": period_no,
            "class_subject_id": cs["id"]})


def _syllabus(client, h, cs, titles):
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Numbers"}).json()
    out = []
    for t in titles:
        out.append(client.post("/api/v1/planner/syllabus/topics", headers=h,
                               json={"unit_id": unit["id"], "title": t, "est_periods": 1}).json())
    client.post(f"/api/v1/planner/plan/{cs['id']}/draft", headers=h)
    return out


# ── open-on-action lifecycle ─────────────────────────────────────────────────
def test_card_read_does_not_create_a_period_but_open_does(client, cleanup):
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)

    card = client.get(
        f"/api/v1/periods/card?class_id={klass['id']}&period_no=1", headers=h).json()
    assert card["period_id"] is None and card["opened"] is False
    assert card["attendance_marked"] is False and card["roster_count"] == 1
    assert _periods(klass["id"]) == 0, "reading the card must not write a period row"

    # "Start attendance" — the button the period row hides behind. Idempotent.
    o1 = client.post("/api/v1/periods/open", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"]})
    assert o1.status_code == 200, o1.text
    o2 = client.post("/api/v1/periods/open", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"]})
    assert o2.json()["id"] == o1.json()["id"]
    assert _periods(klass["id"]) == 1

    card2 = client.get(
        f"/api/v1/periods/card?class_id={klass['id']}&period_no=1", headers=h).json()
    assert card2["opened"] is True and card2["attendance_marked"] is False
    assert card2["closed"] is False


def test_close_and_not_held(client, cleanup):
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    pid = client.post("/api/v1/periods/open", headers=h, json={
        "class_id": klass["id"], "period_no": 1, "class_subject_id": cs["id"]}).json()["id"]

    closed = client.post(f"/api/v1/periods/{pid}/close", headers=h).json()
    assert closed["closed_at"] is not None and closed["status"] == "held"

    # A not-held period keeps its row (the day's coverage arithmetic still balances).
    nh = client.post(f"/api/v1/periods/{pid}/not-held", headers=h,
                     json={"reason": "Teacher on leave, no substitute"}).json()
    assert nh["status"] == "not_held"
    assert nh["not_held_reason"] == "Teacher on leave, no substitute"
    assert nh["closed_at"] is not None

    card = client.get(
        f"/api/v1/periods/card?class_id={klass['id']}&period_no=1", headers=h).json()
    assert card["status"] == "not_held" and card["closed"] is True


def test_period_records_who_actually_took_it(client, cleanup):
    """A substitution is a period whose teacher differs from the class-subject's
    year-long assignment — no override table needed."""
    h, _y, mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    # The admin (not the assigned teacher... who here IS the admin) opens it.
    p = client.post("/api/v1/periods/open", headers=h, json={
        "class_id": klass["id"], "period_no": 4, "class_subject_id": cs["id"]}).json()
    assert p["teacher_member_id"] == mid
    assert p["class_subject_id"] == cs["id"]


# ── the double-period bug ────────────────────────────────────────────────────
def test_double_period_has_independent_cards_and_logs(client, cleanup):
    """3-A Maths in period 1 AND period 4 of the same day. Before V2-P6 both cards
    read off one shared class-subject row: logging period 1 flipped period 4 to
    "logged" and re-proposed the same topic."""
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    topics = _syllabus(client, h, cs, ["Place value", "Rounding", "Estimation"])

    day0 = client.get("/api/v1/classroom/my-day", headers=h).json()
    p1, p4 = (next(p for p in day0["periods"] if p["period_no"] == n) for n in (1, 4))
    assert p1["logged"] is False and p4["logged"] is False
    # Each period is offered the NEXT topic, not the same one twice.
    assert p1["planned_topic_id"] == topics[0]["id"]
    assert p4["planned_topic_id"] == topics[1]["id"]

    # Log period 1 only.
    log1 = client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[0]["id"],
        "coverage": "full", "period_no": 1})
    assert log1.status_code == 200, log1.text
    assert log1.json()["period_id"] is not None

    day1 = client.get("/api/v1/classroom/my-day", headers=h).json()
    p1, p4 = (next(p for p in day1["periods"] if p["period_no"] == n) for n in (1, 4))
    assert p1["logged"] is True, "period 1 was logged"
    assert p4["logged"] is False, "period 4 must NOT inherit period 1's log"
    assert p4["planned_topic_id"] == topics[1]["id"]

    # Logging period 4 with a different topic must not overwrite period 1's row.
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[1]["id"],
        "coverage": "full", "period_no": 4})
    db = AdminSession()
    try:
        logs = db.query(LessonLog).filter(
            LessonLog.class_subject_id == uuid.UUID(cs["id"])).all()
        assert len(logs) == 2, "one lesson log per period, not one per class-subject"
        assert {log.period_id for log in logs} == set(
            db.scalars(select(ClassPeriod.id).where(
                ClassPeriod.class_id == uuid.UUID(klass["id"]))).all())
    finally:
        db.close()


def test_same_topic_twice_in_one_day_is_two_rows(client, cleanup):
    """The old UNIQUE(class_subject, date, topic) silently UPDATE'd the first row."""
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    topics = _syllabus(client, h, cs, ["Place value", "Rounding"])

    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[0]["id"],
        "coverage": "partial", "period_no": 1})
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[0]["id"],
        "coverage": "full", "period_no": 4})

    db = AdminSession()
    try:
        logs = db.query(LessonLog).filter(
            LessonLog.class_subject_id == uuid.UUID(cs["id"])).all()
        assert len(logs) == 2
        assert {log.coverage for log in logs} == {"partial", "full"}
    finally:
        db.close()


def test_quick_log_without_a_period_resolves_from_the_grid(client, cleanup):
    """A plain CL-2 quick log still lands on a period: the earliest of today's slots
    for that class-subject that has no log yet."""
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    topics = _syllabus(client, h, cs, ["Place value", "Rounding"])

    a = client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[0]["id"], "coverage": "full"}).json()
    b = client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[1]["id"], "coverage": "full"}).json()
    assert a["period_id"] != b["period_id"], "the second quick log fills the second period"

    db = AdminSession()
    try:
        nos = sorted(db.scalars(select(ClassPeriod.period_no).where(
            ClassPeriod.class_id == uuid.UUID(klass["id"]))).all())
        assert nos == [1, 4]
    finally:
        db.close()


# ── period card assembly ─────────────────────────────────────────────────────
def test_card_shows_topic_progress_and_homework(client, cleanup):
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    topics = _syllabus(client, h, cs, ["Place value", "Rounding", "Estimation"])

    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[0]["id"],
        "coverage": "full", "period_no": 1})
    client.post("/api/v1/classroom/lesson-logs", headers=h, json={
        "class_subject_id": cs["id"], "topic_id": topics[1]["id"],
        "coverage": "partial", "period_no": 4})
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Sums 1-10"})

    card = client.get(
        f"/api/v1/periods/card?class_id={klass['id']}&period_no=1", headers=h).json()
    assert card["subject_name"] == "Mathematics"
    assert card["plan"]["logged_topic_id"] == topics[0]["id"]
    assert card["plan"]["logged_coverage"] == "full"

    by_title = {r["topic_title"]: r["status"] for r in card["plan"]["progress"]}
    assert by_title == {"Place value": "done", "Rounding": "in_progress",
                        "Estimation": "pending"}
    # Homework is day-scoped by design: it shows on BOTH period cards.
    assert [h_["text"] for h_ in card["homework"]] == ["Sums 1-10"]
    card4 = client.get(
        f"/api/v1/periods/card?class_id={klass['id']}&period_no=4", headers=h).json()
    assert [h_["text"] for h_ in card4["homework"]] == ["Sums 1-10"]


def test_card_requires_teaching_the_class(client, cleanup):
    h, _y, _mid, klass, cs = _setup(client, cleanup)
    _double_period(client, h, klass, cs)
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    r = client.get(f"/api/v1/periods/card?class_id={klass['id']}&period_no=1", headers=th)
    assert r.status_code == 403
    o = client.post("/api/v1/periods/open", headers=th, json={
        "class_id": klass["id"], "period_no": 1})
    assert o.status_code == 403
