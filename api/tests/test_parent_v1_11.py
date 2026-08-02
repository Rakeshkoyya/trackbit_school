"""V1-11 parent access: the D-13 login, siblings, D-08 messages, Q-56 calendar.

What these tests are really protecting:

* the roster is not browsable by anyone holding a school code (`S-55`);
* a ~5,500-guess credential is locked before it falls (`S-56`), and the lock
  survives the rollback of the request that raised the error;
* proving one child buys exactly one child (`Q-25` b);
* a guardian message that did not arrive becomes a NAMED row on the admin's
  board rather than a silence (`S-62`);
* and the calendar a parent sees carries their own child's birthday and nobody
  else's (`Q-56`).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select, update

from app.models import Guardian, GuardianMessage, Organization, Student
from tests.conftest import AdminSession
from tests.test_parent_portal import _add_student, _setup

DOB = "2015-06-14"


def _school_code(org_id: str) -> str:
    db = AdminSession()
    try:
        return db.scalar(select(Organization.school_code).where(
            Organization.id == uuid.UUID(org_id)))
    finally:
        db.close()


def _set_dob(student_id: str, dob: str) -> None:
    db = AdminSession()
    try:
        db.execute(update(Student).where(Student.id == uuid.UUID(student_id))
                   .values(date_of_birth=date.fromisoformat(dob)))
        db.commit()
    finally:
        db.close()


def _phone():
    return "+919" + str(uuid.uuid4().int)[:9]


def _dob_login(client, code, class_id, query, student_id, dob):
    """The whole D-13 flow, as a parent walks it."""
    school = client.post("/api/v1/parent/auth/school", json={"code": code})
    assert school.status_code == 200, school.text
    org_id = school.json()["org_id"]
    found = client.post("/api/v1/parent/auth/find-child",
                        json={"org_id": org_id, "class_id": class_id, "query": query})
    assert found.status_code == 200, found.text
    assert student_id in [r["student_id"] for r in found.json()]
    return client.post("/api/v1/parent/auth/verify-dob",
                       json={"student_id": student_id, "date_of_birth": dob})


# ── D-13 / S-55 / S-57 ──────────────────────────────────────────────────────
def test_dob_login_end_to_end_and_search_never_browsable(client, cleanup):
    h, _year, klass, _cs = _setup(client, cleanup)
    org_id = None
    code = _school_code(str(cleanup["orgs"][0]))
    assert code, "every org must get a school code — D-13's first step needs it"

    student = _add_student(client, h, klass["id"], "Aisha Khan", _phone())
    _set_dob(student["id"], DOB)

    # Step 1 — a wrong code says nothing at all about what exists.
    bad = client.post("/api/v1/parent/auth/school", json={"code": "ZZZZZZZ"})
    assert bad.status_code == 403
    assert bad.json()["error"]["code"] == "school_not_found"

    school = client.post("/api/v1/parent/auth/school", json={"code": code.lower()})
    assert school.status_code == 200, school.text
    org_id = school.json()["org_id"]
    assert klass["id"] in [c["class_id"] for c in school.json()["classes"]]

    # Step 3 (`S-55`) — a short query is refused, so the section is never a
    # browsable list for anyone holding the code.
    short = client.post("/api/v1/parent/auth/find-child",
                        json={"org_id": org_id, "class_id": klass["id"], "query": "a"})
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "query_too_short"

    # Step 4 — the wrong DOB never says whether the child exists differently
    # from the right one; it just counts.
    wrong = client.post("/api/v1/parent/auth/verify-dob",
                        json={"student_id": student["id"], "date_of_birth": "2015-06-15"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "dob_incorrect"
    assert wrong.json()["error"]["details"]["attempts_left"] == 4

    r = _dob_login(client, code, klass["id"], "Ais", student["id"], DOB)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["org_role"] == "parent"
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))

    ph = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/v1/parent/me", headers=ph)
    assert me.status_code == 200, me.text
    assert [c["full_name"] for c in me.json()["children"]] == ["Aisha Khan"]

    # The session works on the curated reads, and staff surfaces stay shut.
    today = client.get(f"/api/v1/parent/children/{student['id']}/today", headers=ph)
    assert today.status_code == 200, today.text
    assert client.get("/api/v1/students", headers=ph).status_code == 401


def test_dob_missing_is_the_schools_gap_not_a_wrong_attempt(client, cleanup):
    """`Q-24`: no DOB on record must NOT burn an attempt, and must point at the
    recovery path (`Q-29`) rather than leaving the parent with nothing."""
    h, _year, klass, _cs = _setup(client, cleanup)
    student = _add_student(client, h, klass["id"], "Noor Ali", _phone())

    r = client.post("/api/v1/parent/auth/verify-dob",
                    json={"student_id": student["id"], "date_of_birth": DOB})
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "dob_not_on_record"
    assert err["details"]["otp_available"] is True


# ── S-56 ────────────────────────────────────────────────────────────────────
def test_lockout_after_five_wrong_dobs_refuses_even_the_right_one(client, cleanup):
    h, _year, klass, _cs = _setup(client, cleanup)
    student = _add_student(client, h, klass["id"], "Rhea Nair", _phone())
    _set_dob(student["id"], DOB)

    for _ in range(5):
        bad = client.post("/api/v1/parent/auth/verify-dob",
                          json={"student_id": student["id"],
                                "date_of_birth": "2010-01-01"})
        assert bad.status_code == 401

    # The counter survived five rolled-back requests, so the CORRECT date of
    # birth is now refused. This is the assertion the whole lock exists for.
    good = client.post("/api/v1/parent/auth/verify-dob",
                       json={"student_id": student["id"], "date_of_birth": DOB})
    assert good.status_code == 401
    assert good.json()["error"]["code"] == "parent_login_locked"


# ── Q-25 (b) ────────────────────────────────────────────────────────────────
def test_add_another_child_and_one_proof_buys_exactly_one_child(client, cleanup):
    h, _year, klass, _cs = _setup(client, cleanup)
    code = _school_code(str(cleanup["orgs"][0]))
    shared = _phone()          # one family, one number, two children
    first = _add_student(client, h, klass["id"], "Dev Sharma", shared)
    second = _add_student(client, h, klass["id"], "Diya Sharma", shared)
    _set_dob(first["id"], DOB)
    _set_dob(second["id"], "2017-02-02")

    r = _dob_login(client, code, klass["id"], "Dev", first["id"], DOB)
    assert r.status_code == 200, r.text
    cleanup["users"].append(uuid.UUID(r.json()["user"]["id"]))
    ph = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Proving Dev's date of birth does NOT hand over his sister — even though
    # the family shares one phone number. That is the difference between D-13
    # and the OTP path, and it is deliberate.
    assert [c["full_name"] for c in client.get("/api/v1/parent/me",
                                               headers=ph).json()["children"]] == ["Dev Sharma"]
    assert client.get(f"/api/v1/parent/children/{second['id']}/today",
                      headers=ph).status_code == 403

    # A wrong DOB on the add step is refused...
    bad = client.post("/api/v1/parent/children/add", headers=ph,
                      json={"student_id": second["id"], "date_of_birth": DOB})
    assert bad.status_code == 401

    # ...and the right one puts her on the same login, switcher and all.
    ok = client.post("/api/v1/parent/children/add", headers=ph,
                     json={"student_id": second["id"], "date_of_birth": "2017-02-02"})
    assert ok.status_code == 200, ok.text
    names = sorted(c["full_name"] for c in
                   client.get("/api/v1/parent/me", headers=ph).json()["children"])
    assert names == ["Dev Sharma", "Diya Sharma"]
    assert client.get(f"/api/v1/parent/children/{second['id']}/today",
                      headers=ph).status_code == 200


# ── D-08 / D-14 / S-62 ──────────────────────────────────────────────────────
def _mark_absent(client, h, klass, cs, student_id, on_date):
    roster = client.get("/api/v1/attendance/roster", headers=h,
                        params={"class_id": klass["id"], "period_no": 1, "date": on_date})
    assert roster.status_code == 200, roster.text
    return client.post("/api/v1/attendance/mark", headers=h, json={
        "class_id": klass["id"], "class_subject_id": cs["id"], "period_no": 1,
        "date": on_date, "exceptions": [{"student_id": student_id, "status": "absent"}]})


def test_absence_alert_lands_in_the_inbox_and_names_the_unreached(client, cleanup):
    """`D-08` gives the alert a destination; `S-62` records that it did not
    arrive, because push is best-effort and this alert is not."""
    h, _year, klass, cs = _setup(client, cleanup)
    code = _school_code(str(cleanup["orgs"][0]))
    student = _add_student(client, h, klass["id"], "Kabir Rao", _phone())
    _set_dob(student["id"], DOB)
    on_date = date.today().isoformat()

    r = _mark_absent(client, h, klass, cs, student["id"], on_date)
    assert r.status_code == 200, r.text

    # The message exists even though nobody has logged in — that guardian is
    # exactly the family the office most needs to know about.
    db = AdminSession()
    try:
        rows = list(db.scalars(select(GuardianMessage).where(
            GuardianMessage.student_id == uuid.UUID(student["id"]))))
    finally:
        db.close()
    assert len(rows) == 1
    assert rows[0].kind == "absence"
    assert rows[0].push_sent_at is None
    assert rows[0].unreachable_reason == "no_login"

    # `S-62`: the admin's board names the family and gives the number to ring.
    reach = client.get("/api/v1/insights/attendance/reach", headers=h)
    assert reach.status_code == 200, reach.text
    board = reach.json()
    assert board["unreachable"] == 1
    assert board["rows"][0]["student_name"] == "Kabir Rao"
    assert board["rows"][0]["reason_code"] == "no_login"
    assert board["rows"][0]["phone"]
    assert "worth a call" in board["summary"]

    # And once the parent signs in, the message is waiting in the archive.
    login = _dob_login(client, code, klass["id"], "Kab", student["id"], DOB)
    assert login.status_code == 200, login.text
    cleanup["users"].append(uuid.UUID(login.json()["user"]["id"]))
    ph = {"Authorization": f"Bearer {login.json()['access_token']}"}

    feed = client.get("/api/v1/parent/notifications", headers=ph)
    assert feed.status_code == 200, feed.text
    assert feed.json()["unread"] == 1
    item = feed.json()["items"][0]
    assert item["kind"] == "absence"
    assert item["student_name"] == "Kabir Rao"
    # The office's column never reaches the family.
    assert "unreachable_reason" not in item and "push_sent_at" not in item

    assert client.post("/api/v1/parent/notifications/read",
                       headers=ph).status_code == 200
    assert client.get("/api/v1/parent/notifications", headers=ph).json()["unread"] == 0


def test_absence_alert_is_deduped_per_child_per_day(client, cleanup):
    """A family chased twice for one absence stops reading the channel — which
    is the channel the school needs next week."""
    h, _year, klass, cs = _setup(client, cleanup)
    student = _add_student(client, h, klass["id"], "Meera Das", _phone())
    on_date = date.today().isoformat()

    _mark_absent(client, h, klass, cs, student["id"], on_date)
    _mark_absent(client, h, klass, cs, student["id"], on_date)

    db = AdminSession()
    try:
        n = len(list(db.scalars(select(GuardianMessage).where(
            GuardianMessage.student_id == uuid.UUID(student["id"])))))
    finally:
        db.close()
    assert n == 1


def test_opted_out_guardian_is_not_a_delivery_failure(client, cleanup):
    """An opted-out family is a choice, not a problem to clear. It must never
    join the list the office is told to work through."""
    h, _year, klass, cs = _setup(client, cleanup)
    student = _add_student(client, h, klass["id"], "Ishan Roy", _phone())
    db = AdminSession()
    try:
        db.execute(update(Guardian).where(
            Guardian.student_id == uuid.UUID(student["id"])).values(notify_opt_out=True))
        db.commit()
    finally:
        db.close()

    _mark_absent(client, h, klass, cs, student["id"], date.today().isoformat())
    board = client.get("/api/v1/insights/attendance/reach", headers=h).json()
    assert board["opted_out"] == 1
    assert board["unreachable"] == 0
    assert board["rows"] == []


# ── Q-56 ────────────────────────────────────────────────────────────────────
def test_calendar_is_read_only_and_only_this_childs_birthday(client, cleanup):
    h, year, klass, _cs = _setup(client, cleanup)
    code = _school_code(str(cleanup["orgs"][0]))
    mine = _add_student(client, h, klass["id"], "Tara Menon", _phone())
    other = _add_student(client, h, klass["id"], "Someone Else", _phone())
    soon = date.today().replace(year=2015) + timedelta(days=5)
    _set_dob(mine["id"], soon.isoformat())
    _set_dob(other["id"], (soon + timedelta(days=1)).isoformat())

    holiday = date.today() + timedelta(days=3)
    ev = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "title": "Founder's Day",
        "start_date": holiday.isoformat(), "end_date": holiday.isoformat(),
        "type": "holiday", "affects_teaching": True})
    assert ev.status_code == 200, ev.text

    login = _dob_login(client, code, klass["id"], "Tar", mine["id"],
                       soon.isoformat())
    assert login.status_code == 200, login.text
    cleanup["users"].append(uuid.UUID(login.json()["user"]["id"]))
    ph = {"Authorization": f"Bearer {login.json()['access_token']}"}

    cal = client.get(f"/api/v1/parent/children/{mine['id']}/calendar", headers=ph)
    assert cal.status_code == 200, cal.text
    items = cal.json()["items"]
    titles = [i["title"] for i in items]
    assert "Founder's Day" in titles
    assert any(i["closed"] for i in items if i["title"] == "Founder's Day")

    birthdays = [i for i in items if i["kind"] == "birthday"]
    assert [b["title"] for b in birthdays] == ["Tara Menon's birthday"]
    # A list of classmates' birthdays is a roster leak wearing a party hat.
    assert not any("Someone Else" in t for t in titles)


# ── D-35 · the parent's yellow must be able to clear ────────────────────────
def test_carried_homework_shows_as_pending_and_a_waiver_clears_it(client, cleanup):
    """`D-35` shows an absent child's homework as pending — **yellow, never
    red**, because nothing was refused. `S-98` is what stops that yellow being
    permanent: the teacher may decide the backlog isn't required and set fresh
    work instead, and that outcome has to reach this screen or a parent learns
    to ignore it.

    V1-5 proved the teacher's half. This is the parent's half, which nothing
    asserted — and it is the half the decision was actually about.
    """
    from tests.test_homework_v1_5 import _check, _set_hw
    from tests.test_homework_v1_5 import _setup as _hw_setup

    ctx = _hw_setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    kabir = ctx["students"][2]
    _set_dob(kabir["id"], DOB)
    code = _school_code(str(cleanup["orgs"][0]))
    # The homework helper creates students without guardians; the portal needs one.
    g = client.post(f"/api/v1/students/{kabir['id']}/guardians", headers=h, json={
        "name": "Kabir's Father", "relation": "Father", "phone": _phone(),
        "is_primary": True})
    assert g.status_code == 200, g.text

    on = (date.today() - timedelta(days=2)).isoformat()
    hw = _set_hw(client, th, ctx["cs"]["id"], "Ex 4.3", on)
    _check(client, th, hw["id"], [
        {"student_id": kabir["id"], "status": "carried", "note": "Off sick"}])

    login = _dob_login(client, code, ctx["class"]["id"], "Kab", kabir["id"], DOB)
    assert login.status_code == 200, login.text
    cleanup["users"].append(uuid.UUID(login.json()["user"]["id"]))
    ph = {"Authorization": f"Bearer {login.json()['access_token']}"}

    today = client.get(f"/api/v1/parent/children/{kabir['id']}/today", headers=ph)
    assert today.status_code == 200, today.text
    pending = today.json()["pending"]
    assert any(i["text"] == "Ex 4.3" and i["status"] == "carried" for i in pending), \
        "D-35: work set while the child was away is shown, pending"
    # It is pending, never missed — the child was not there to refuse it.
    assert all(i["text"] != "Ex 4.3" for i in today.json()["missed"])

    # `S-98`: the teacher gives him fresh work instead, and the yellow clears.
    _check(client, th, hw["id"], [
        {"student_id": kabir["id"], "status": "waived", "note": "Gave him fresh work"}])
    after = client.get(f"/api/v1/parent/children/{kabir['id']}/today", headers=ph).json()
    assert all(i["text"] != "Ex 4.3" for i in after["pending"]), \
        "S-98: without this the parent's yellow is permanent"
    assert all(i["text"] != "Ex 4.3" for i in after["missed"])
