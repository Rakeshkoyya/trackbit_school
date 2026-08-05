"""The day's notice — the admin's, and the teacher's class row (2026-08-05).

Founder call after walking the shipped events module. `/events/whats-on` served
one feed to everybody: the admin's card and the teacher's My Day strip were the
same rows at two depths. That was right when the only question was *does the
calendar read back at all*, and wrong once teachers used it — she was shown the
office's exam block, a colleague's birthday and another class's children on the
screen she opens between rooms.

So the feed gains a scope, and these are the three things that must stay true:

  * a class row is **that class's children and nothing else** — no calendar row,
    no staff birthday, and the coverage denominator is the class's own. A row
    quoting the school's 486 students under a heading about 6-A is a figure
    about somebody else (`S-124`).
  * it is a roster read, so it obeys the ONE class-read rule
    (`periods.visible_class_ids`, AT-1) and is **blocked with a sentence rather
    than filtered to an empty list** (`S-46`): a teacher shown nothing for a
    class she may not see would read it as a class with no birthdays.
  * the unscoped feed is **unchanged**. The admin's notice is the same three
    sources it always was (`S-121`); what changed is the horizon it is read at
    and the fact that it now fits on one line.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Membership
from tests.conftest import AdminSession
from tests.test_events_v1_7 import _membership_id, _set_dob, _setup


def _set_staff_dob(user_id: str, org_id: str, dob: date) -> None:
    db = AdminSession()
    try:
        mid = db.scalar(select(Membership).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id)))
        mid.date_of_birth = dob
        db.commit()
    finally:
        db.close()


def _kid(client, h, class_id, name):
    return client.post("/api/v1/students", headers=h, json={
        "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": name,
        "class_id": class_id}).json()


def test_a_class_row_carries_that_class_and_nothing_else(client, cleanup):
    """The whole point of the scope. Standing in 6-A she is told about 6-A."""
    ctx = _setup(client, cleanup)
    h, today = ctx["h"], date.today()

    # A second class, so "only this class" is a claim the data can falsify.
    other = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "7", "section": "B"}).json()

    mine = _kid(client, h, ctx["class"]["id"], "Rhea Menon")
    theirs = _kid(client, h, other["id"], "Arjun Rao")
    nodob = _kid(client, h, ctx["class"]["id"], "No Date")
    _set_dob(mine["id"], today.replace(year=today.year - 11))
    _set_dob(theirs["id"], today.replace(year=today.year - 11))

    # Something on the school's calendar today, and a colleague with a birthday:
    # both belong on the admin's notice and neither belongs on hers.
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "celebration",
        "title": "Founders Day", "start_date": today.isoformat(),
        "end_date": today.isoformat(), "affects_teaching": False})
    _set_staff_dob(ctx["user_id"], ctx["org_id"], today.replace(year=1980))

    scoped = client.get(
        f"/api/v1/events/whats-on?class_id={ctx['class']['id']}", headers=h)
    assert scoped.status_code == 200, scoped.text
    feed = scoped.json()

    titles = [i["title"] for i in feed["today"]]
    assert titles == ["Rhea Menon"]
    assert {i["source"] for i in feed["today"]} == {"birthday"}
    assert "Arjun Rao" not in titles          # another class's child
    assert "Founders Day" not in titles       # the school's calendar
    assert not any(i["source"] == "staff_birthday" for i in feed["today"])
    # `S-124` — the denominator is this class's roster, not the school's.
    assert feed["dob_known"] == 1 and feed["dob_total"] == 2
    assert nodob["id"] is not None

    # And the unscoped feed is untouched: all three sources, as before.
    whole = client.get("/api/v1/events/whats-on", headers=h).json()
    whole_titles = [i["title"] for i in whole["today"]]
    assert "Founders Day" in whole_titles
    assert "Rhea Menon" in whole_titles and "Arjun Rao" in whole_titles
    assert any(i["source"] == "staff_birthday" for i in whole["today"])
    assert whole["dob_known"] == 2 and whole["dob_total"] == 3


def test_a_class_you_do_not_take_is_refused_not_emptied(client, cleanup):
    """`S-46` — an empty list and a refusal read identically on a screen, and
    only one of them is true. The class teacher's own class opens; a class she
    has nothing to do with says so."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]

    stranger = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "9", "section": "C"}).json()

    # `_setup` makes this teacher 6-A's class teacher AND its Maths teacher.
    ok = client.get(f"/api/v1/events/whats-on?class_id={ctx['class']['id']}",
                    headers=ctx["th"])
    assert ok.status_code == 200, ok.text

    blocked = client.get(f"/api/v1/events/whats-on?class_id={stranger['id']}",
                         headers=ctx["th"])
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "not_your_class"

    # The admin reads any class — the rule is `visible_class_ids`, and an admin's
    # set is unrestricted.
    assert client.get(f"/api/v1/events/whats-on?class_id={stranger['id']}",
                      headers=h).status_code == 200


def test_the_week_is_the_warning(client, cleanup):
    """There is no "Coming up" list any more, so a date has to reach the notice
    on its own: seven days out it is in the feed, three weeks out it is not.

    That is the founder's rule — *"everyday we check and present it, and any
    event will show up 1 week before"* — and it is what makes one dismissible
    line enough.
    """
    ctx = _setup(client, cleanup)
    h, today = ctx["h"], date.today()

    for days, title in ((6, "Independence Day"), (20, "Sports Day")):
        client.post("/api/v1/academics/calendar/events", headers=h, json={
            "academic_year_id": ctx["year"]["id"], "type": "holiday",
            "title": title, "start_date": (today + timedelta(days=days)).isoformat(),
            "end_date": (today + timedelta(days=days)).isoformat()})

    week = client.get("/api/v1/events/whats-on?horizon=7", headers=h).json()
    upcoming = [i["title"] for i in week["upcoming"]]
    assert "Independence Day" in upcoming
    assert "Sports Day" not in upcoming
    # It carries how far away it is, which is the whole of the row's copy.
    assert next(i for i in week["upcoming"]
                if i["title"] == "Independence Day")["days_away"] == 6

    # A teacher who is not in the class picker still gets the school feed at
    # `/dashboard`-less depth — the scope is opt-in, never a new fence.
    tfeed = client.get("/api/v1/events/whats-on?horizon=7", headers=ctx["th"]).json()
    assert "Independence Day" in [i["title"] for i in tfeed["upcoming"]]


def test_a_teacher_may_read_the_homeroom_she_takes_no_subject_in(client, cleanup):
    """AT-1's half of `visible_class_ids`, defended here too: a warden or a
    primary homeroom teacher owns a class whose subjects belong to other people,
    and the birthdays of her own children are exactly what she should see."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"w{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    w = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(w["user_id"]))
    wmid = _membership_id(w["user_id"], ctx["org_id"])
    login = client.post("/api/v1/auth/login", json={
        "identifier": w["username"], "password": "supersecret1"}).json()
    wh = {"Authorization": f"Bearer {login['access_token']}"}

    homeroom = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "5", "section": "A",
        "class_teacher_member_id": wmid}).json()
    kid = _kid(client, h, homeroom["id"], "Ishaan Bose")
    _set_dob(kid["id"], date.today().replace(year=2015))

    r = client.get(f"/api/v1/events/whats-on?class_id={homeroom['id']}", headers=wh)
    assert r.status_code == 200, r.text
    assert [i["title"] for i in r.json()["today"]] == ["Ishaan Bose"]
