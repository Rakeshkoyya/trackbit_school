"""V2-P1: timetable grid, effective-dating, clash validator, import, My Day (SPRD2 §5.3)."""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.models import Membership, TimetableSlot
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _slot_count(class_id):
    db = AdminSession()
    try:
        return db.query(TimetableSlot).filter(
            TimetableSlot.class_id == uuid.UUID(class_id)).count()
    finally:
        db.close()


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "TT Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    mid = str(_membership_id(reg["user"]["id"], reg["org"]["id"]))

    def make_cs(class_name, subject_name):
        klass = client.post("/api/v1/academics/classes", headers=h,
                            json={"academic_year_id": year["id"], "name": class_name,
                                  "section": "A"}).json()
        subject = client.post("/api/v1/academics/subjects", headers=h,
                              json={"name": subject_name}).json()
        cs = client.post("/api/v1/academics/class-subjects", headers=h,
                         json={"class_id": klass["id"], "subject_id": subject["id"],
                               "teacher_member_id": mid, "periods_per_week": 5}).json()
        return klass, subject, cs

    return h, year, mid, make_cs


def test_period_config(client, cleanup):
    h, year, _mid, _mk = _setup(client, cleanup)
    got = client.get(f"/api/v1/timetable/period-config?year_id={year['id']}", headers=h).json()
    assert got["periods_per_day"] == 8  # default

    put = client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 6,
        "period_times": [{"start": "09:00", "end": "09:40", "kind": "period"},
                         {"start": "09:40", "end": "10:20", "kind": "period"}]})
    assert put.status_code == 200, put.text
    assert put.json()["periods_per_day"] == 6
    again = client.get(f"/api/v1/timetable/period-config?year_id={year['id']}", headers=h).json()
    assert again["periods_per_day"] == 6
    assert len(again["period_times"]) == 2


def test_grid_set_and_effective_dating(client, cleanup):
    h, _year, _mid, mk = _setup(client, cleanup)
    klass, _s1, cs1 = mk("6", "Science")
    # a second subject in the SAME class to swap the cell to
    subj2 = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Maths"}).json()
    cs2 = client.post("/api/v1/academics/class-subjects", headers=h,
                      json={"class_id": klass["id"], "subject_id": subj2["id"],
                            "periods_per_week": 5}).json()

    today = date(2026, 8, 3)  # a Monday
    nxt = today + timedelta(days=14)
    r1 = client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs1["id"], "effective_from": today.isoformat()})
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["slots"]) == 1

    # Swap the same cell to cs2 from a future date → old row closed, new opened.
    r2 = client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs2["id"], "effective_from": nxt.isoformat()})
    assert r2.status_code == 200, r2.text

    # History preserved: two rows for the cell (one closed, one current).
    assert _slot_count(klass["id"]) == 2

    # Grid at `today` still shows Science; at `nxt` shows Maths.
    g_now = client.get(f"/api/v1/timetable/grid?class_id={klass['id']}&on_date={today.isoformat()}", headers=h).json()
    assert g_now["slots"][0]["class_subject_id"] == cs1["id"]
    g_future = client.get(f"/api/v1/timetable/grid?class_id={klass['id']}&on_date={nxt.isoformat()}", headers=h).json()
    assert g_future["slots"][0]["class_subject_id"] == cs2["id"]

    # Clear the current cell → grid empty at that date.
    client.post("/api/v1/timetable/slot/clear", headers=h, json={
        "class_id": klass["id"], "weekday": 0, "period_no": 1,
        "effective_from": (nxt + timedelta(days=7)).isoformat()})
    g_cleared = client.get(f"/api/v1/timetable/grid?class_id={klass['id']}&on_date={(nxt + timedelta(days=8)).isoformat()}", headers=h).json()
    assert g_cleared["slots"] == []


def test_clash_validator_rejects_teacher_in_two_places(client, cleanup):
    """Done-when: the clash validator provably flags one teacher in two classes."""
    h, _year, _mid, mk = _setup(client, cleanup)
    class_a, _sa, cs_a = mk("6", "Science")
    class_b, _sb, cs_b = mk("7", "History")  # same teacher (director) teaches both

    # Effective from today (default) so the slots are current when validated.
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_a["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs_a["id"]})
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_b["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs_b["id"]})

    clashes = client.get("/api/v1/timetable/validate", headers=h).json()
    assert len(clashes) == 1
    c = clashes[0]
    assert c["weekday"] == 0 and c["period_no"] == 1
    assert sorted(c["class_labels"]) == ["6-A", "7-A"]

    # The affected class's grid surfaces the same clash for live highlighting.
    grid_a = client.get(f"/api/v1/timetable/grid?class_id={class_a['id']}", headers=h).json()
    assert len(grid_a["clashes"]) == 1


def test_no_clash_when_periods_differ(client, cleanup):
    h, _year, _mid, mk = _setup(client, cleanup)
    class_a, _sa, cs_a = mk("6", "Science")
    class_b, _sb, cs_b = mk("7", "History")
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_a["id"], "weekday": 0, "period_no": 1,
        "class_subject_id": cs_a["id"]})
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": class_b["id"], "weekday": 0, "period_no": 2,
        "class_subject_id": cs_b["id"]})
    assert client.get("/api/v1/timetable/validate", headers=h).json() == []


def test_teacher_week_and_my_day_read_timetable(client, cleanup):
    h, _year, _mid, mk = _setup(client, cleanup)
    klass, _s, cs = mk("6", "Science")
    wd = datetime.now(ZoneInfo("Asia/Kolkata")).date().weekday()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": wd, "period_no": 2, "class_subject_id": cs["id"]})

    week = client.get("/api/v1/timetable/my-week", headers=h).json()
    assert any(s["period_no"] == 2 and s["class_subject_id"] == cs["id"] for s in week["slots"])

    day = client.get("/api/v1/classroom/my-day", headers=h).json()
    assert any(p["period_no"] == 2 and p["class_subject_id"] == cs["id"] for p in day["periods"])


def test_import_analyze_and_commit(client, cleanup):
    h, _year, _mid, mk = _setup(client, cleanup)
    klass, _s, cs = mk("6", "Science")
    subj2 = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Maths"}).json()
    client.post("/api/v1/academics/class-subjects", headers=h,
                json={"class_id": klass["id"], "subject_id": subj2["id"], "periods_per_week": 4})

    an = client.post(f"/api/v1/timetable/import/analyze?class_id={klass['id']}", headers=h)
    assert an.status_code == 200, an.text
    body = an.json()
    assert body["source"] == "fixture" and len(body["cells"]) > 0

    commit = client.post("/api/v1/timetable/import/commit", headers=h, json={
        "class_id": klass["id"],
        "cells": [{"weekday": c["weekday"], "period_no": c["period_no"],
                   "class_subject_id": c["class_subject_id"]} for c in body["cells"]]})
    assert commit.status_code == 200, commit.text
    assert len(commit.json()["slots"]) == len(body["cells"])


def test_assisted_draft_flag(client, cleanup):
    h, _year, _mid, mk = _setup(client, cleanup)
    klass, _s, _cs = mk("6", "Science")

    off = client.post(f"/api/v1/timetable/draft?class_id={klass['id']}", headers=h).json()
    assert off["enabled"] is False

    prev = settings.TIMETABLE_ASSISTED_DRAFT
    settings.TIMETABLE_ASSISTED_DRAFT = True
    try:
        on = client.post(f"/api/v1/timetable/draft?class_id={klass['id']}", headers=h).json()
        assert on["enabled"] is True and len(on["cells"]) > 0
    finally:
        settings.TIMETABLE_ASSISTED_DRAFT = prev


def test_slot_write_is_admin_only(client, cleanup):
    """Teachers can read the grid but not edit it (SPRD2 §2/§5.3)."""
    h, year, mid, mk = _setup(client, cleanup)
    klass, _s, cs = mk("6", "Science")
    # add a teacher-role member
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1", "role": "teacher"}]})
    assert bulk.status_code == 200, bulk.text
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    # teacher read ok
    assert client.get(f"/api/v1/timetable/grid?class_id={klass['id']}", headers=th).status_code == 200
    # teacher write forbidden
    w = client.put("/api/v1/timetable/slot", headers=th, json={
        "class_id": klass["id"], "weekday": 0, "period_no": 1, "class_subject_id": cs["id"]})
    assert w.status_code == 403
