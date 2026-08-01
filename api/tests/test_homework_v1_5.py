"""V1-5 — homework: the verdict model, the screen, and the two admin signals.

What each test is defending:

  * `D-85` — `late` is a status the teacher sets whenever she likes, with no
    threshold and nothing locking. It counts as DONE in completion and is
    reported beside it (`S-99`), because folding it in hides a class where
    everything arrives four days late and counting it as a miss punishes a child
    who did the work.
  * `D-34`/`S-98`/`S-102` — an absent child's homework is **carried**, not
    missed: out of the denominator, out of the streak, off the red list that
    fires guardian reminders. `waived` is how it stops being pending, or the
    parent's yellow never clears.
  * HW-1's load-bearing rule, re-asserted — **a teacher who checks nothing must
    never read as a class with perfect completion.**
  * `D-85`'s two derived admin signals: *this teacher has not checked anything
    for N days* and *this class was checked and N children missed it*. Neither
    writes anything into a child's record.
  * `D-36`/`S-100` the queue and its count · `S-85`/`S-89`/`S-97` what the sheet
    tells her while she is holding the notebooks · `D-37` who may see the load.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core import homework_verdict as verdicts
from app.models import Membership
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return str(db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(user_id),
                Membership.org_id == uuid.UUID(org_id))))
    finally:
        db.close()


def _setup(client, cleanup):
    """An org with a year, a class of three, and a teacher who owns Maths."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "HW Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 4,
        "period_times": [{"start": f"0{9 + i}:00", "end": f"0{9 + i}:40", "kind": "period"}
                         for i in range(4)]})

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"],
                              "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    teacher_mid = _membership_id(cred["user_id"], reg["org"]["id"])

    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A",
        "class_teacher_member_id": teacher_mid}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": f"Maths {uuid.uuid4().hex[:4]}"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "periods_per_week": 4, "teacher_member_id": teacher_mid}).json()

    students = [
        client.post("/api/v1/students", headers=h, json={
            "full_name": name, "class_id": klass["id"],
            "admission_no": f"A{uuid.uuid4().hex[:6]}"}).json()
        for name in ("Asha Rao", "Bilal Khan", "Kabir Shah")
    ]
    return {"h": h, "th": th, "year": year, "class": klass, "cs": cs,
            "students": students, "teacher_mid": teacher_mid}


def _set_hw(client, headers, cs_id, text, on, due=None):
    body = {"class_subject_id": cs_id, "text": text, "date": on}
    if due:
        body["due_date"] = due
    return client.post("/api/v1/classroom/homework", headers=headers, json=body).json()


def _check(client, headers, assignment_id, results):
    return client.post(f"/api/v1/classroom/homework/{assignment_id}/check",
                       headers=headers, json={"results": results}).json()


# ── the verdict model, pure ──────────────────────────────────────────────────
def test_one_vocabulary_one_arithmetic():
    """The whole module rests on this table. It is worth asserting directly."""
    # late IS done (S-99) — a child who handed it in late did the work.
    assert verdicts.verdict_weight("done") == 1.0
    assert verdicts.verdict_weight("late") == 1.0
    assert verdicts.verdict_weight("partial") == 0.5
    assert verdicts.verdict_weight("not_done") == 0.0
    # …and these leave the denominator entirely rather than scoring zero.
    for status in ("carried", "waived", "not_checked"):
        assert verdicts.verdict_weight(status) is None
        assert not verdicts.is_graded(status)
        assert not verdicts.is_miss(status), f"{status} must never read as a miss"

    counts = verdicts.tally(["done", "done", "late", "partial", "not_done",
                             "carried", "waived", "not_checked"])
    assert counts["graded"] == 5, "carried/waived/not_checked are not graded"
    # (1 + 1 + 1 + 0.5 + 0) / 5
    assert verdicts.completion(counts) == 0.7
    # Nothing graded is None, and None is not zero — no screen may render it so.
    assert verdicts.completion(verdicts.tally(["not_checked", "carried"])) is None


def test_streak_skips_neutral_days_and_never_counts_them_clean():
    """S-102: a child off sick for a week must not top the red list, and must
    not have their real pattern erased either."""
    d = date(2026, 6, 1)
    days = [(d + timedelta(days=i), s) for i, s in enumerate(
        ["not_done", "carried", "not_checked", "not_done"])]
    # The two carried/unchecked days are skipped, so the two misses are adjacent.
    assert verdicts.miss_streak(days) == 2
    # A genuine done day breaks it.
    assert verdicts.miss_streak(days + [(d + timedelta(days=4), "done")]) == 0
    # Three subjects missed in one afternoon is ONE bad day.
    same = [(d, "not_done"), (d, "not_done"), (d, "not_done")]
    assert verdicts.miss_streak(same) == 1


# ── D-85: late is a status, editable forever ────────────────────────────────
def test_late_counts_as_done_and_is_reported_separately(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    asha, bilal, kabir = ctx["students"]
    on = (date.today() - timedelta(days=2)).isoformat()
    hw = _set_hw(client, th, ctx["cs"]["id"], "Ex 4.2", on)

    sheet = _check(client, th, hw["id"], [
        {"student_id": bilal["id"], "status": "late", "note": "Handed in today"},
        {"student_id": kabir["id"], "status": "not_done"}])
    assert sheet["late_count"] == 1 and sheet["not_done_count"] == 1
    assert sheet["done_count"] == 1

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    # 2 of 3 did the work (one of them late) → completion 2/3, late reported.
    assert ov["overall_completion"] == round(2 / 3, 3)
    assert ov["late"] == 1
    # D-85: nothing locks. Kabir turns up with the book two days later and she
    # changes his verdict — at any time, forever, no threshold. Submitting is a
    # full replace (the same contract as attendance), so she sends the corrected
    # set rather than a delta.
    again = _check(client, th, hw["id"], [
        {"student_id": bilal["id"], "status": "late"},
        {"student_id": kabir["id"], "status": "late", "note": "Brought it Thursday"}])
    assert again["late_count"] == 2 and again["not_done_count"] == 0
    assert client.get("/api/v1/homework/overview",
                      headers=h).json()["overall_completion"] == 1.0


# ── D-34 / S-98 / S-102: carried is not a miss ──────────────────────────────
def test_carried_leaves_every_figure_and_waived_clears_it(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    asha, bilal, kabir = ctx["students"]
    on = (date.today() - timedelta(days=2)).isoformat()
    hw = _set_hw(client, th, ctx["cs"]["id"], "Ex 4.3", on)

    sheet = _check(client, th, hw["id"], [
        {"student_id": kabir["id"], "status": "carried", "note": "Off sick"}])
    assert sheet["carried_count"] == 1
    # Two children were graded, not three — the absent one is not a zero.
    ov = client.get("/api/v1/homework/overview", headers=h).json()
    assert ov["overall_completion"] == 1.0, "a carried child cannot drag completion down"
    assert ov["carried"] == 1
    # …and never reaches the red list that fires guardian reminders.
    assert all(r["student_id"] != kabir["id"] for r in ov["needs_attention"])

    hist = client.get(f"/api/v1/homework/student/{kabir['id']}", headers=h).json()
    assert hist["carried"] == 1 and hist["not_done"] == 0
    assert hist["streak"] == 0, "S-102: an absence is not a streak day"

    # S-98: waiving is how it stops being pending. Without it the parent's
    # yellow never clears.
    waived = _check(client, th, hw["id"], [
        {"student_id": kabir["id"], "status": "waived", "note": "Gave him fresh work"}])
    assert waived["waived_count"] == 1 and waived["carried_count"] == 0
    after = client.get(f"/api/v1/homework/student/{kabir['id']}", headers=h).json()
    assert after["waived"] == 1
    assert after["completion"] is None or after["completion"] == 1.0


def test_absent_when_set_is_carried_without_the_teacher_saying_so(client, cleanup):
    """S-85: attendance already knows who was in the room. A child off sick on
    Tuesday must not be flagged not_done on Wednesday and chased at home."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    asha, bilal, kabir = ctx["students"]
    on = date.today() - timedelta(days=2)
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["class"]["id"], "weekday": on.weekday(), "period_no": 1,
        "class_subject_id": ctx["cs"]["id"], "effective_from": "2026-04-01"})
    client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": ctx["class"]["id"], "period_no": 1, "date": on.isoformat(),
        "exceptions": [{"student_id": kabir["id"], "status": "absent"}]})

    hw = _set_hw(client, th, ctx["cs"]["id"], "Ex 4.4", on.isoformat())
    # The teacher marks him not_done, not knowing he was away…
    _check(client, th, hw["id"], [{"student_id": kabir["id"], "status": "not_done"}])

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    # …and the roll-up reads it as carried instead of a miss.
    assert ov["carried"] == 1 and ov["overall_completion"] == 1.0
    assert all(r["student_id"] != kabir["id"] for r in ov["needs_attention"])

    # S-85 on the sheet: shown, and NOT preselected as a miss.
    sheet = client.get(f"/api/v1/classroom/homework/{hw['id']}/sheet", headers=th).json()
    row = next(r for r in sheet["roster"] if r["student_id"] == kabir["id"])
    assert row["absent_when_set"] is True


def test_a_teacher_who_checks_nothing_is_never_perfect_completion(client, cleanup):
    """HW-1's load-bearing rule, and the one most likely to be broken by
    somebody tidying the copy."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    on = (date.today() - timedelta(days=3)).isoformat()
    _set_hw(client, th, ctx["cs"]["id"], "Never checked", on)

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    assert ov["assigned"] == 1 and ov["checked"] == 0
    assert ov["overall_completion"] is None, "unchecked is not 100%"
    assert ov["check_rate"] == 0.0


# ── D-85's two derived admin signals ────────────────────────────────────────
def test_the_admin_hears_about_a_delayed_teacher_and_a_rough_class(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    old = (date.today() - timedelta(days=8)).isoformat()
    _set_hw(client, th, ctx["cs"]["id"], "Long unchecked", old)

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    delayed = ov["delayed_teachers"]
    assert delayed and delayed[0]["unchecked_overdue"] >= 1
    # Derived only — nothing about this is written against a student.
    for row in ov["needs_attention"]:
        assert row["not_done"] + row["partial"] > 0

    # The other signal needs a big class, so add enough children to cross it.
    for i in range(5):
        client.post("/api/v1/students", headers=h, json={
            "full_name": f"Extra {i}", "class_id": ctx["class"]["id"],
            "admission_no": f"E{uuid.uuid4().hex[:6]}"})
    roster = client.get("/api/v1/students", headers=h,
                        params={"class_id": ctx["class"]["id"]}).json()
    ids = [s["id"] for s in (roster if isinstance(roster, list) else roster["students"])]
    hw = _set_hw(client, th, ctx["cs"]["id"], "Everyone struggled",
                 (date.today() - timedelta(days=1)).isoformat())
    _check(client, th, hw["id"],
           [{"student_id": sid, "status": "not_done"} for sid in ids[:6]])

    ov = client.get("/api/v1/homework/overview", headers=h).json()
    rough = ov["rough_classes"]
    assert rough and rough[0]["missed"] >= 5
    assert rough[0]["text"] == "Everyone struggled"


# ── D-36 / S-100 / S-89 / S-97: the screen ──────────────────────────────────
def test_the_queue_is_the_backlog_oldest_first_and_carries_its_count(client, cleanup):
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    older = (date.today() - timedelta(days=5)).isoformat()
    newer = (date.today() - timedelta(days=1)).isoformat()
    first = _set_hw(client, th, ctx["cs"]["id"], "Friday's work", older)
    _set_hw(client, th, ctx["cs"]["id"], "Yesterday's work", newer)

    q = client.get("/api/v1/homework/queue", headers=th).json()
    assert q["to_check"] == 2, "S-100: the button's number"
    assert q["overdue"] == 2
    # S-83: Friday's homework survives the weekend, and it is at the TOP.
    assert q["items"][0]["assignment_id"] == first["id"]
    assert q["items"][0]["days_waiting"] >= 4

    # A checked one drops below the unchecked ones rather than disappearing —
    # nothing expires (D-85).
    _check(client, th, first["id"], [])
    q = client.get("/api/v1/homework/queue", headers=th).json()
    assert q["to_check"] == 1
    assert q["items"][-1]["assignment_id"] == first["id"]
    assert q["items"][-1]["checked"] is True


def test_the_sheet_hands_her_the_intervention(client, cleanup):
    """S-89: the streak on the row, at the moment she is holding the notebook —
    the cheapest intervention moment in the product."""
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    _asha, _bilal, kabir = ctx["students"]
    days = [(date.today() - timedelta(days=n)).isoformat() for n in (4, 3, 2)]
    for i, on in enumerate(days[:2]):
        hw = _set_hw(client, th, ctx["cs"]["id"], f"Set {i}", on)
        _check(client, th, hw["id"], [{"student_id": kabir["id"], "status": "not_done"}])

    today_hw = _set_hw(client, th, ctx["cs"]["id"], "Today's", days[2])
    sheet = client.get(f"/api/v1/classroom/homework/{today_hw['id']}/sheet",
                       headers=th).json()
    row = next(r for r in sheet["roster"] if r["student_id"] == kabir["id"])
    assert row["miss_streak"] == 2, "she sees '2nd miss running' while holding the book"
    clean = next(r for r in sheet["roster"] if r["student_id"] == ctx["students"][0]["id"])
    assert clean["miss_streak"] == 0


def test_carried_items_follow_the_child_to_the_next_sheet(client, cleanup):
    """S-97: the returning child's pending work appears on his row of the sheet
    she is already opening. Nothing new to remember."""
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    _asha, _bilal, kabir = ctx["students"]
    away = _set_hw(client, th, ctx["cs"]["id"], "While he was away",
                   (date.today() - timedelta(days=3)).isoformat())
    _check(client, th, away["id"], [{"student_id": kabir["id"], "status": "carried"}])

    back = _set_hw(client, th, ctx["cs"]["id"], "Back today",
                   (date.today() - timedelta(days=1)).isoformat())
    sheet = client.get(f"/api/v1/classroom/homework/{back['id']}/sheet", headers=th).json()
    row = next(r for r in sheet["roster"] if r["student_id"] == kabir["id"])
    assert row["carried_pending"] == 1


# ── D-37: who may see the load ──────────────────────────────────────────────
def test_daily_load_reaches_the_admin_and_the_class_teacher_only(client, cleanup):
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    on = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, ctx["cs"]["id"], "Maths", on)

    admin_view = client.get("/api/v1/homework/load", headers=h).json()
    assert admin_view["cells"] and admin_view["busiest_subjects"] >= 1
    # The teacher IS this class's class teacher, so she sees her own class.
    own = client.get("/api/v1/homework/load", headers=th).json()
    assert [c["class_label"] for c in own["cells"]] == ["6-A"]

    # A subject teacher who is nobody's class teacher sees nothing at all.
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"s{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    other = client.post("/api/v1/auth/login", json={
        "identifier": cred["username"], "password": "supersecret1"}).json()
    oh = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get("/api/v1/homework/load", headers=oh).json()["cells"] == []
