"""TT-2: the bell schedule, typed slots, blocks and their capture (§4, D-112…D-115).

The negative-authorization tests are not optional decoration. A block's staff
list is the only thing between a teacher and another block's roster, and
`block_id` is the only path by which somebody who does not teach a class may
write its homework verdicts — so both are asserted from the outside, through the
routes, where the guards actually run.
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _school(client, cleanup):
    """An admin, a year, one class with one subject."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Day Shape School", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    admin_mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "7",
                              "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "teacher_member_id": admin_mid, "periods_per_week": 5}).json()
    return {"h": h, "year": year, "class": klass, "subject": subject, "cs": cs,
            "admin_mid": admin_mid, "org_id": reg["org"]["id"]}


def _teacher(client, cleanup, s, name="warden"):
    """A second, non-admin member with a usable token."""
    username = f"{name}{uuid.uuid4().hex[:8]}"
    created = client.post("/api/v1/org/members/bulk", headers=s["h"], json={"members": [
        {"username": username, "password": "supersecret1", "role": "teacher"}]},
    ).json()["results"][0]
    cleanup["users"].append(uuid.UUID(created["user_id"]))
    tok = client.post("/api/v1/auth/login",
                      json={"identifier": username, "password": "supersecret1"}).json()
    return ({"Authorization": f"Bearer {tok['access_token']}"},
            str(_membership_id(created["user_id"], s["org_id"])))


_DAY = [
    {"start": "08:00", "end": "08:40", "kind": "period"},
    {"start": "08:40", "end": "09:20", "kind": "period"},
    {"start": "09:20", "end": "09:40", "kind": "break", "label": "Short break"},
    {"start": "09:40", "end": "10:20", "kind": "period"},
]


def _set_day(client, s, entries=None, **kw):
    return client.put("/api/v1/timetable/bell", headers=s["h"], json={
        "academic_year_id": s["year"]["id"], "entries": entries or _DAY,
        "effective_from": "2026-04-01", **kw})


def _block(client, s, name="Homework class", kind="homework", **kw):
    return client.post("/api/v1/timetable/blocks", headers=s["h"],
                       json={"name": name, "kind": kind, **kw}).json()


# ── the bell schedule ────────────────────────────────────────────────────────
def test_a_break_takes_no_period_number(client, cleanup):
    s = _school(client, cleanup)
    r = _set_day(client, s)
    assert r.status_code == 200, r.text
    got = r.json()
    # Four rows, three of them teachable — the break must not consume a number.
    assert got["periods_per_day"] == 3
    assert len(got["entries"]) == 4
    assert got["has_timings"] is True


def test_reshaping_the_day_keeps_the_old_shape_readable(client, cleanup):
    """`D-115`: September must not re-render with October's clock."""
    s = _school(client, cleanup)
    _set_day(client, s, note="opening shape")
    longer = [*_DAY, {"start": "15:30", "end": "16:30", "kind": "period"}]
    client.put("/api/v1/timetable/bell", headers=s["h"], json={
        "academic_year_id": s["year"]["id"], "entries": longer,
        "effective_from": "2026-10-01", "note": "after Term 1 exams"})

    before = client.get(
        f"/api/v1/timetable/bell?year_id={s['year']['id']}&on_date=2026-05-05",
        headers=s["h"]).json()
    after = client.get(
        f"/api/v1/timetable/bell?year_id={s['year']['id']}&on_date=2026-11-05",
        headers=s["h"]).json()
    assert before["periods_per_day"] == 3, "May must keep May's day"
    assert after["periods_per_day"] == 4
    assert after["note"] == "after Term 1 exams"

    hist = client.get(f"/api/v1/timetable/bell/history?year_id={s['year']['id']}",
                      headers=s["h"]).json()
    assert len(hist["schedules"]) == 2
    assert hist["schedules"][0]["effective_to"] is None
    assert hist["schedules"][1]["effective_to"] == "2026-10-01"


def test_a_day_out_of_order_is_refused(client, cleanup):
    s = _school(client, cleanup)
    r = client.put("/api/v1/timetable/bell", headers=s["h"], json={
        "academic_year_id": s["year"]["id"], "entries": [
            {"start": "09:00", "end": "09:40", "kind": "period"},
            {"start": "08:00", "end": "08:40", "kind": "period"},
        ]})
    assert r.status_code == 422, r.text


# ── typed slots ──────────────────────────────────────────────────────────────
def test_a_block_can_hold_a_period_and_pulls_the_class_in(client, cleanup):
    s = _school(client, cleanup)
    _set_day(client, s)
    cats = client.post("/api/v1/students/categories/seed-defaults",
                       headers=s["h"]).json()
    hosteller = next(c["id"] for c in cats if c["name"] == "Hosteller")
    b = _block(client, s, category_id=hosteller)
    assert b["kind_label"] == "Homework class"

    grid = client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 3,
        "slot_type": "block", "session_id": b["id"]})
    assert grid.status_code == 200, grid.text
    slot = next(x for x in grid.json()["slots"] if x["period_no"] == 3)
    assert slot["slot_type"] == "block"
    assert slot["block_name"] == "Homework class"
    # `D-129`: the slot names the category rather than carrying a boolean, so
    # the grid can say "Hostellers" — or "Transport" — instead of a checked box.
    assert slot["category_id"] == hosteller
    assert slot["category_name"] == "Hosteller"
    # The grid says which classes are in the block — no second place to say it.
    assert s["class"]["id"] in client.get(
        f"/api/v1/timetable/blocks/{b['id']}", headers=s["h"]).json()["class_ids"]


def test_a_subject_slot_needs_a_subject_and_a_block_needs_a_block(client, cleanup):
    s = _school(client, cleanup)
    _set_day(client, s)
    r = client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 1,
        "slot_type": "block"})
    assert r.status_code == 422
    r2 = client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 1,
        "slot_type": "subject"})
    assert r2.status_code == 422


def test_one_block_across_many_classes_is_not_a_clash(client, cleanup):
    """Assembly on every class at period 1 is one engagement, not N-1 clashes."""
    s = _school(client, cleanup)
    _set_day(client, s)
    second = client.post("/api/v1/academics/classes", headers=s["h"],
                         json={"academic_year_id": s["year"]["id"], "name": "8",
                               "section": "A"}).json()
    b = _block(client, s, name="Assembly", kind="assembly",
               staff_member_ids=[s["admin_mid"]])
    for class_id in (s["class"]["id"], second["id"]):
        client.put("/api/v1/timetable/slot", headers=s["h"], json={
            "class_id": class_id, "weekday": 0, "period_no": 1,
            "slot_type": "block", "session_id": b["id"]})
    clashes = client.get("/api/v1/timetable/validate", headers=s["h"]).json()
    assert clashes == [], f"one assembly is one place to stand: {clashes}"


def test_shortening_the_day_closes_the_orphaned_cells(client, cleanup):
    s = _school(client, cleanup)
    _set_day(client, s)
    client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 3,
        "slot_type": "subject", "class_subject_id": s["cs"]["id"]})
    _set_day(client, s, entries=_DAY[:2])
    grid = client.get(
        f"/api/v1/timetable/grid?class_id={s['class']['id']}", headers=s["h"]).json()
    assert grid["periods_per_day"] == 2
    assert all(x["period_no"] <= 2 for x in grid["slots"])


# ── who may edit the day ─────────────────────────────────────────────────────
def test_a_teacher_cannot_edit_the_grid_or_the_timings(client, cleanup):
    s = _school(client, cleanup)
    th, _mid = _teacher(client, cleanup, s)
    r = client.put("/api/v1/timetable/slot", headers=th, json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 1,
        "slot_type": "subject", "class_subject_id": s["cs"]["id"]})
    assert r.status_code == 403
    r2 = client.put("/api/v1/timetable/bell", headers=th, json={
        "academic_year_id": s["year"]["id"], "entries": _DAY})
    assert r2.status_code == 403
    r3 = client.post("/api/v1/timetable/blocks", headers=th,
                     json={"name": "Sneaky", "kind": "sports"})
    assert r3.status_code == 403


# ── capture, and who may do it ───────────────────────────────────────────────
def test_only_the_blocks_staff_can_open_it(client, cleanup):
    s = _school(client, cleanup)
    on_staff_h, on_staff_mid = _teacher(client, cleanup, s, "Warden")
    outsider_h, _ = _teacher(client, cleanup, s, "Outsider")
    b = _block(client, s, name="Games", kind="sports",
               staff_member_ids=[on_staff_mid])

    ok = client.post(f"/api/v1/blocks/{b['id']}/open", headers=on_staff_h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["capture"]["roll"] is True
    assert ok.json()["capture"]["homework_check"] is False

    denied = client.post(f"/api/v1/blocks/{b['id']}/open", headers=outsider_h)
    assert denied.status_code == 403, "a teacher off the staff list must not open it"


def test_the_capture_matrix_decides_what_a_block_accepts(client, cleanup):
    """A games period keeps no class log, and the API says so rather than
    silently storing one nobody will ever read."""
    s = _school(client, cleanup)
    b = _block(client, s, name="Games", kind="sports",
               staff_member_ids=[s["admin_mid"]])
    meeting = client.post(f"/api/v1/blocks/{b['id']}/open", headers=s["h"]).json()
    r = client.put(f"/api/v1/blocks/meetings/{meeting['id']}/note", headers=s["h"],
                   json={"note": "we played football"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_class_log"

    course = _block(client, s, name="AI class", kind="course",
                    staff_member_ids=[s["admin_mid"]])
    m2 = client.post(f"/api/v1/blocks/{course['id']}/open", headers=s["h"]).json()
    ok = client.put(f"/api/v1/blocks/meetings/{m2['id']}/note", headers=s["h"],
                    json={"note": "intro to neural nets"})
    assert ok.status_code == 200
    assert ok.json()["note"] == "intro to neural nets"


def test_a_sports_block_does_not_check_homework(client, cleanup):
    s = _school(client, cleanup)
    b = _block(client, s, name="Games", kind="sports",
               staff_member_ids=[s["admin_mid"]])
    meeting = client.post(f"/api/v1/blocks/{b['id']}/open", headers=s["h"]).json()
    r = client.get(f"/api/v1/blocks/meetings/{meeting['id']}/homework", headers=s["h"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_homework_check"


def test_the_homework_class_checks_books_for_a_class_the_warden_never_teaches(
        client, cleanup):
    """TT-2 §3 — and the reason `_can_touch_homework` grew a block arm."""
    s = _school(client, cleanup)
    warden_h, warden_mid = _teacher(client, cleanup, s, "Warden")
    _set_day(client, s)
    b = _block(client, s, staff_member_ids=[warden_mid])
    client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 3,
        "slot_type": "block", "session_id": b["id"]})

    hw = client.post("/api/v1/classroom/homework", headers=s["h"], json={
        "class_subject_id": s["cs"]["id"], "text": "Chapter 4 sums"}).json()

    meeting = client.post(f"/api/v1/blocks/{b['id']}/open", headers=warden_h).json()
    board = client.get(
        f"/api/v1/blocks/meetings/{meeting['id']}/homework"
        f"?class_id={s['class']['id']}&class_subject_id={s['cs']['id']}",
        headers=warden_h)
    assert board.status_code == 200, board.text
    assert [a["assignment_id"] for a in board.json()["assignments"]] == [hw["id"]]
    # Nothing is claimed before she saves.
    assert board.json()["assignments"][0]["checked"] is False

    done = client.post(
        f"/api/v1/blocks/meetings/{meeting['id']}/homework/{hw['id']}/check",
        headers=warden_h, json={"results": []})
    assert done.status_code == 200, done.text
    assert done.json()["checked"] is True


def test_a_block_is_not_a_skeleton_key_to_another_classs_homework(client, cleanup):
    """`block_id` widens authorization; it must widen it by exactly one class."""
    s = _school(client, cleanup)
    warden_h, warden_mid = _teacher(client, cleanup, s, "Warden")
    other_class = client.post("/api/v1/academics/classes", headers=s["h"],
                              json={"academic_year_id": s["year"]["id"], "name": "9",
                                    "section": "A"}).json()
    other_cs = client.post("/api/v1/academics/class-subjects", headers=s["h"],
                           json={"class_id": other_class["id"],
                                 "subject_id": s["subject"]["id"],
                                 "teacher_member_id": s["admin_mid"],
                                 "periods_per_week": 4}).json()
    outside_hw = client.post("/api/v1/classroom/homework", headers=s["h"], json={
        "class_subject_id": other_cs["id"], "text": "Not her business"}).json()

    _set_day(client, s)
    b = _block(client, s, staff_member_ids=[warden_mid])
    client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": 0, "period_no": 3,
        "slot_type": "block", "session_id": b["id"]})
    meeting = client.post(f"/api/v1/blocks/{b['id']}/open", headers=warden_h).json()

    r = client.post(
        f"/api/v1/blocks/meetings/{meeting['id']}/homework/{outside_hw['id']}/check",
        headers=warden_h, json={"results": []})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "homework_not_in_block"


# ── My Day ───────────────────────────────────────────────────────────────────
def test_my_day_shows_a_block_to_its_staff_and_to_nobody_else(client, cleanup):
    s = _school(client, cleanup)
    staff_h, staff_mid = _teacher(client, cleanup, s, "Warden")
    outsider_h, _ = _teacher(client, cleanup, s, "Outsider")
    _set_day(client, s)
    b = _block(client, s, name="Homework class", staff_member_ids=[staff_mid])

    weekday = datetime.now(ZoneInfo("Asia/Kolkata")).weekday()
    client.put("/api/v1/timetable/slot", headers=s["h"], json={
        "class_id": s["class"]["id"], "weekday": weekday, "period_no": 3,
        "slot_type": "block", "session_id": b["id"]})

    mine = client.get("/api/v1/classroom/my-day", headers=staff_h).json()
    blocks = [p for p in mine["periods"] if p["slot_type"] == "block"]
    assert len(blocks) == 1, mine["periods"]
    assert blocks[0]["block_name"] == "Homework class"
    assert blocks[0]["session_id"] == b["id"]
    # It carries the clock, and asks for no school-day register (D-91).
    assert blocks[0]["start"] == "09:40"
    assert blocks[0]["marks_attendance"] is False
    assert blocks[0]["class_subject_id"] is None

    theirs = client.get("/api/v1/classroom/my-day", headers=outsider_h).json()
    assert [p for p in theirs["periods"] if p["slot_type"] == "block"] == []
