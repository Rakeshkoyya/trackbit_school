"""V1-7 — events, dates and birthdays.

What each test is defending:

  * **Defect 1** — the school calendar was write-only. An admin painted "Diwali"
    in April and the product never mentioned it again; its only consumer was the
    function that subtracts it from the teaching total. `/events/whats-on` is
    the read side, and it is one computation over three sources (`S-121`).
  * `D-79`/`D-57` — **a suggestion is never a date, it is a prompt to pick one.**
    One suggested row must produce *"Christmas — school closed, 25 Dec"* AND
    *"Christmas celebration — runs as usual, 22 Dec"*, on two dates, at two lock
    levels. That is the packet's Done-when, and it is what removes the
    wrong-date risk structurally rather than by accepting it.
  * `S-143` — **the cost, before they commit.** Locking a day moves RAG colours
    across the school the instant it is written, because `effective_periods` is
    live. A principal who is not told concludes the system is broken.
  * `S-148` — dismissal is append-only and permanent, and keys on the stable
    `key` so next year's entry does not come back.
  * `S-145` — a locked period **leaves what is still expected**: My Day, the
    capture heatmap, the 16:00 reminder. `Q-65`: it never erases what was
    already recorded.
  * `S-147` — "not held, because" points at the approved event, so *"what did
    Diwali cost us in periods?"* is answerable.
  * `S-149`/`S-150` — the catalogue is platform data (no org_id, super-admin on
    every write) and every entry carries its provenance.
  * `S-128`/`S-133` — the vacation birthday rolls to a working day and says so;
    the feed shows the day, never the age.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Membership, Student, User
from tests.conftest import AdminSession


def _make_super(user_id: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return str(db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id))))
    finally:
        db.close()


def _set_dob(student_id: str, dob: date) -> None:
    db = AdminSession()
    try:
        db.get(Student, uuid.UUID(student_id)).date_of_birth = dob
        db.commit()
    finally:
        db.close()


def _setup(client, cleanup):
    """A year, one class, Maths with a syllabus + an approved plan, one teacher.

    The plan matters: `S-143`'s cost preview is only meaningful against a school
    that has something to lose.
    """
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Events Org", "name": "Director", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    client.patch("/api/v1/org/settings", headers=h,
                 json={"state": "Telangana", "board": "CBSE"})

    today = date.today()
    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=60)).isoformat(),
        "end_date": (today + timedelta(days=200)).isoformat()}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 4,
        "period_times": [{"start": f"{9 + i:02d}:00", "end": f"{9 + i:02d}:40",
                          "kind": "period"} for i in range(4)]})

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    t = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(t["user_id"]))
    tlogin = client.post("/api/v1/auth/login", json={
        "identifier": t["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {tlogin['access_token']}"}
    tmid = _membership_id(t["user_id"], reg["org"]["id"])

    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": f"Maths {uuid.uuid4().hex[:4]}"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A",
        "class_teacher_member_id": tmid}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "periods_per_week": 4, "teacher_member_id": tmid}).json()

    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs["id"], "title": "Chapter One"}).json()
    for i in range(24):
        client.post("/api/v1/planner/syllabus/topics", headers=h, json={
            "unit_id": unit["id"], "title": f"Topic {i}", "est_periods": 4})
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h)

    return {"h": h, "th": th, "year": year, "class": klass, "cs": cs,
            "org_id": reg["org"]["id"], "user_id": reg["user"]["id"],
            "teacher_mid": tmid}


def _catalogue(client, sh, cleanup, *, name, on, key=None, **kw):
    """The catalogue is platform data, so a test row outlives the org that read
    it — hence the explicit key per run and the cleanup registration."""
    body = {"name": name, "date": on.isoformat(),
            "key": key or f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
            "source": kw.pop("source", "Telangana state holiday list 2026"), **kw}
    r = client.post("/api/v1/platform/observances", headers=sh, json=body)
    assert r.status_code == 200, r.text
    cleanup["observances"].append(uuid.UUID(r.json()["id"]))
    return r.json()


def _timetable(client, h, ctx, periods=(1, 2, 3, 4)):
    """Put the class-subject in every period of every weekday."""
    for wd in range(6):
        for p in periods:
            r = client.put("/api/v1/timetable/slot", headers=h, json={
                "class_id": ctx["class"]["id"], "weekday": wd, "period_no": p,
                "class_subject_id": ctx["cs"]["id"],
                "effective_from": (date.today() - timedelta(days=30)).isoformat()})
            assert r.status_code == 200, r.text


def _next_working(days_ahead: int = 7) -> date:
    """A date the default Mon-Sat week actually works — otherwise the cost
    preview legitimately costs nothing and the assertion is about the weekend."""
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


# ── the read side that never existed ─────────────────────────────────────────
def test_whats_on_reads_back_the_calendar_the_school_has_always_written(client, cleanup):
    """Defect 1. A painted event was invisible to every human surface — the row
    existed, was correct, was org-scoped, and was read by exactly one function
    whose job was to subtract it."""
    ctx = _setup(client, cleanup)
    h, today = ctx["h"], date.today()

    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "celebration",
        "title": "Guru Purnima", "start_date": today.isoformat(),
        "end_date": today.isoformat(), "affects_teaching": False})
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "holiday",
        "title": "Independence Day", "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=10)).isoformat()})

    r = client.get("/api/v1/events/whats-on", headers=h)
    assert r.status_code == 200, r.text
    feed = r.json()
    assert [i["title"] for i in feed["today"]] == ["Guru Purnima"]
    assert feed["today"][0]["detail"].endswith("school open")
    assert any(i["title"] == "Independence Day" and i["days_away"] == 10
               for i in feed["upcoming"])

    # The teacher gets the same feed — one computation, two depths (module §1).
    tfeed = client.get("/api/v1/events/whats-on", headers=ctx["th"]).json()
    assert [i["title"] for i in tfeed["today"]] == ["Guru Purnima"]
    # `Q-64` (a): her surface is never provisional, so it carries no suggestion
    # count at all.
    assert tfeed["pending_suggestions"] == 0


def test_birthdays_are_derived_and_carry_their_denominator(client, cleanup):
    """`S-121` — a birthday is DERIVED from a DOB, never stored as an event.
    `S-124` — an empty card says why it is empty, with its denominator.
    `S-133` — the day, never the age."""
    ctx = _setup(client, cleanup)
    h, today = ctx["h"], date.today()

    kids = []
    for i in range(3):
        s = client.post("/api/v1/students", headers=h, json={
            "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": f"Kid {i}",
            "class_id": ctx["class"]["id"]}).json()
        kids.append(s)
    # Two of three have a DOB; one of those is today, 20 years ago.
    _set_dob(kids[0]["id"], today.replace(year=today.year - 20))
    _set_dob(kids[1]["id"], (today + timedelta(days=3)).replace(year=today.year - 21))

    feed = client.get("/api/v1/events/whats-on", headers=h).json()
    assert feed["dob_known"] == 2 and feed["dob_total"] == 3
    birthday = next(i for i in feed["today"] if i["source"] == "birthday")
    assert birthday["title"] == "Kid 0"
    assert birthday["class_label"] == "6-A"
    # No age anywhere on the shared surface.
    assert "20" not in (birthday["detail"] or "")
    assert any(i["source"] == "birthday" and i["title"] == "Kid 1"
               for i in feed["upcoming"])


# ── the approval flow: the module's whole shape ──────────────────────────────
def test_one_suggestion_two_approvals_at_two_lock_levels(client, cleanup):
    """The packet's Done-when, verbatim.

    `D-79` — a suggestion is a prompt to pick a date, not a date. So Christmas
    the *holiday* (25 Dec, school closed) and the Christmas *celebration*
    (22 Dec, runs as usual) are two approvals from one suggested row, which is
    how schools actually behave and which the first draft could not express.
    """
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    sup = client.post("/api/v1/auth/register-org", json={
        "org_name": "Ops", "name": "Op", "email": f"op-{uuid.uuid4().hex[:10]}@e.com",
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(sup["org"]["id"]))
    cleanup["users"].append(uuid.UUID(sup["user"]["id"]))
    _make_super(sup["user"]["id"])
    sh = {"Authorization": f"Bearer {sup['access_token']}"}

    christmas = date.today() + timedelta(days=20)
    obs = _catalogue(client, sh, cleanup, name="Christmas", on=christmas, kind="holiday",
                     prep_days=30, source="National gazetted holidays 2026")

    sug = client.get("/api/v1/events/suggestions", headers=h).json()
    row = next(s for s in sug if s["key"] == obs["key"])
    # `S-150` — the provenance rides on the row the admin is looking at.
    assert row["source"] == "National gazetted holidays 2026"
    assert row["approved_count"] == 0

    # ① the holiday, on the catalogue's date, school closed
    r1 = client.post(f"/api/v1/events/suggestions/{obs['id']}/approve", headers=h, json={
        "start_date": christmas.isoformat(), "lock": "closed", "event_type": "holiday"})
    assert r1.status_code == 200, r1.text
    # ② the celebration, three days earlier, school OPEN — the same row
    r2 = client.post(f"/api/v1/events/suggestions/{obs['id']}/approve", headers=h, json={
        "title": "Christmas celebration",
        "start_date": (christmas - timedelta(days=3)).isoformat(),
        "lock": "open", "event_type": "celebration"})
    assert r2.status_code == 200, r2.text

    summary = client.get("/api/v1/academics/calendar/summary",
                         headers=h, params={"year_id": ctx["year"]["id"]}).json()
    by_title = {e["title"]: e for e in summary["events"]}
    assert by_title["Christmas"]["affects_teaching"] is True
    assert by_title["Christmas"]["start_date"] == christmas.isoformat()
    # The celebration marks the calendar and costs the planner nothing — this is
    # the module's live defect 2, closed by making the choice the central act.
    assert by_title["Christmas celebration"]["affects_teaching"] is False
    assert by_title["Christmas celebration"]["start_date"] == (
        christmas - timedelta(days=3)).isoformat()

    # Two decisions were made, and the row says so rather than disappearing.
    again = client.get("/api/v1/events/suggestions", headers=h).json()
    assert next(s for s in again if s["key"] == obs["key"])["approved_count"] == 2


def test_dismissal_is_permanent_and_survives_next_years_entry(client, cleanup):
    """`S-148` — a dismissal is a row, not a delete, and it keys on the stable
    `key`. Otherwise the same suggestion returns every week and every year, and
    the admin learns to ignore the whole feed, which kills the module."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    sup = client.post("/api/v1/auth/register-org", json={
        "org_name": "Ops2", "name": "Op", "email": f"op-{uuid.uuid4().hex[:10]}@e.com",
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(sup["org"]["id"]))
    cleanup["users"].append(uuid.UUID(sup["user"]["id"]))
    _make_super(sup["user"]["id"])
    sh = {"Authorization": f"Bearer {sup['access_token']}"}

    this_year = date.today() + timedelta(days=15)
    obs = _catalogue(client, sh, cleanup, name="Onam", on=this_year, tradition="Hindu",
                     source="Kerala state list 2026")
    assert any(s["key"] == obs["key"]
               for s in client.get("/api/v1/events/suggestions", headers=h).json())

    d = client.post(f"/api/v1/events/suggestions/{obs['id']}/dismiss", headers=h,
                    json={"note": "We don't observe this"})
    assert d.status_code == 200 and d.json()["action"] == "dismissed"
    assert not any(s["key"] == obs["key"]
                   for s in client.get("/api/v1/events/suggestions", headers=h).json())

    # Next year's entry is a different ROW with the same stable key — still gone.
    _catalogue(client, sh, cleanup, name="Onam", key=obs["key"],
               on=this_year + timedelta(days=20),
               tradition="Hindu", source="Kerala state list 2027")
    assert not any(s["key"] == obs["key"]
                   for s in client.get("/api/v1/events/suggestions", headers=h).json())


def test_lock_cost_names_what_moves_before_the_admin_commits(client, cleanup):
    """`S-143`. `effective_periods` is computed live, so the instant days are
    locked every class-subject's capacity shrinks and colours move with nothing
    explaining why. The sheet says it first, in a sentence."""
    ctx = _setup(client, cleanup)
    h, year = ctx["h"], ctx["year"]
    start = _next_working(7)

    whole = client.post("/api/v1/events/cost", headers=h, json={
        "academic_year_id": year["id"], "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=13)).isoformat(), "lock": "closed"}).json()
    assert whole["periods_lost"] > 0
    assert whole["working_days"] >= whole["days_lost"] > 0
    assert "removes" in whole["sentence"]

    # `open` is the level that costs nothing, and the sentence says so — this is
    # the reassurance that makes a celebration recordable at all.
    nothing = client.post("/api/v1/events/cost", headers=h, json={
        "academic_year_id": year["id"], "start_date": start.isoformat(),
        "lock": "open"}).json()
    assert nothing["periods_lost"] == 0 and nothing["moves"] == []
    assert "full teaching day" in nothing["sentence"]

    # A partial lock costs periods, not a day — `S-142`, and V2-P7 already
    # prorates it.
    partial = client.post("/api/v1/events/cost", headers=h, json={
        "academic_year_id": year["id"], "start_date": start.isoformat(),
        "lock": "periods", "blocks_periods": [1, 2]}).json()
    assert partial["periods_lost"] == 2
    assert partial["days_lost"] < 1


# ── `S-145` the locked period leaves what is EXPECTED, not what was recorded ─
def test_a_locked_day_leaves_the_capture_surface_but_not_the_record(client, cleanup):
    """`S-145` + `Q-65`.

    If the admin locks 15 August and every teacher still sees eight period rows
    saying "not logged", the product has invented work on a holiday and made the
    capture rate lie. But a school that closed at 11am genuinely did teach
    period 1 — locking removes the period from what is still ASKED FOR, never
    from what was already captured.
    """
    ctx = _setup(client, cleanup)
    h, th, today = ctx["h"], ctx["th"], date.today()
    _timetable(client, h, ctx)

    before = client.get("/api/v1/classroom/my-day", headers=th).json()
    if not before["periods"]:
        return  # today is not a working weekday for this school; nothing to prove
    assert before["day_closed"] is False

    # ① a partial lock — periods 1 and 2 only.
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "event",
        "title": "Sports heats", "start_date": today.isoformat(),
        "end_date": today.isoformat(), "blocks_periods": [1, 2]})
    part = client.get("/api/v1/classroom/my-day", headers=th).json()
    assert part["locked_periods"] == [1, 2]
    assert all(p["period_no"] not in (1, 2) for p in part["periods"])
    assert part["lock_reason"] == "Sports heats"

    # The heatmap agrees — a locked period is `not_expected`, never a red gap.
    grid = client.get("/api/v1/insights/attendance", headers=h).json()["capture"]
    row = next(r for r in grid["rows"] if r["class_id"] == ctx["class"]["id"])
    assert {c["state"] for c in row["cells"] if c["period_no"] in (1, 2)} == {"not_expected"}

    # ② the whole day. The period cards go; the day says why.
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "holiday",
        "title": "Independence Day", "start_date": today.isoformat(),
        "end_date": today.isoformat()})
    closed = client.get("/api/v1/classroom/my-day", headers=th).json()
    assert closed["day_closed"] is True and closed["periods"] == []

    # `Q-65` — what was recorded on that day is untouched. The period card still
    # opens and still knows it was locked, so a half-day's period 1 survives.
    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 1}).json()
    assert card["locked"] is True
    assert card["lock_reason"] in ("Sports heats", "Independence Day")


def test_not_held_points_at_the_event_not_at_free_text(client, cleanup):
    """`S-147`. Forty teachers typing forty spellings of "independance day
    rehersal" answers nothing; a reference to the approved row makes "what did
    this cost us in periods?" a query."""
    ctx = _setup(client, cleanup)
    h, th, today = ctx["h"], ctx["th"], date.today()
    _timetable(client, h, ctx)

    # `S-146`: this is the PER-CLASS case — the school is open, 6-A went to the
    # rehearsal. The admin has not locked anything, so the teacher's block is
    # the only record that exists.
    ev = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "event",
        "title": "Independence Day rehearsal", "start_date": today.isoformat(),
        "end_date": today.isoformat(), "affects_teaching": False}).json()

    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 3}).json()
    assert card["locked"] is False               # school open — she IS still asked
    assert [e["id"] for e in card["day_events"]] == []  # only affects_teaching rows lock

    opened = client.post("/api/v1/periods/open", headers=th, json={
        "class_id": ctx["class"]["id"], "period_no": 3,
        "class_subject_id": ctx["cs"]["id"]}).json()
    r = client.post(f"/api/v1/periods/{opened['id']}/not-held", headers=th, json={
        "reason": "Rehearsal", "event_id": ev["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["not_held_event_id"] == ev["id"]
    assert r.json()["status"] == "not_held"

    # A foreign event id cannot be attached.
    other = client.post("/api/v1/periods/open", headers=th, json={
        "class_id": ctx["class"]["id"], "period_no": 4,
        "class_subject_id": ctx["cs"]["id"]}).json()
    bad = client.post(f"/api/v1/periods/{other['id']}/not-held", headers=th, json={
        "reason": "x", "event_id": str(uuid.uuid4())})
    assert bad.status_code == 404


# ── the catalogue is platform data ───────────────────────────────────────────
def test_catalogue_is_platform_owned_and_scoped_by_what_setup_already_asks(client, cleanup):
    """`S-149` — no org_id, no RLS, super-admin on every write, the
    `demo_requests` shape. `D-61` — a school is scoped by **address → state**
    and **board**, both of which setup already collects, so it is never asked to
    declare a region or a religion. `S-150` — `source` is not optional."""
    ctx = _setup(client, cleanup)          # Telangana / CBSE
    h = ctx["h"]
    sup = client.post("/api/v1/auth/register-org", json={
        "org_name": "Ops3", "name": "Op", "email": f"op-{uuid.uuid4().hex[:10]}@e.com",
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(sup["org"]["id"]))
    cleanup["users"].append(uuid.UUID(sup["user"]["id"]))
    sh = {"Authorization": f"Bearer {sup['access_token']}"}

    # A school admin can never write the catalogue.
    denied = client.post("/api/v1/platform/observances", headers=h, json={
        "name": "Made up day", "date": date.today().isoformat(), "source": "me"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "super_admin_only"

    _make_super(sup["user"]["id"])
    soon = date.today() + timedelta(days=10)
    # V1-19: `states` is a set, not a single state — one row per (key, date),
    # so a festival observed in five states has to name five.
    ours = _catalogue(client, sh, cleanup, name="Bathukamma", on=soon,
                      states=["Telangana"],
                      source="Telangana state holiday list 2026")
    theirs = _catalogue(client, sh, cleanup, name="Pongal Kerala", on=soon,
                        states=["Kerala", "Puducherry"],
                        source="Kerala state list 2026")
    everyone = _catalogue(client, sh, cleanup, name="World Book Day", on=soon, tier="minor",
                          source="UN observances")

    keys = {s["key"] for s in client.get("/api/v1/events/suggestions", headers=h).json()}
    assert ours["key"] in keys          # our state
    assert everyone["key"] in keys      # everybody
    assert theirs["key"] not in keys    # another state's list

    # `S-150` — provenance is required, not decorative.
    bad = client.post("/api/v1/platform/observances", headers=sh, json={
        "name": "Unsourced", "date": soon.isoformat()})
    assert bad.status_code == 422


def test_bulk_import_corrects_rather_than_double_suggests(client, cleanup):
    """`S-151` — the realistic architecture is a small importer per source plus
    one annual human review. Re-running a corrected file must FIX every school,
    not suggest the same date to all of them twice."""
    sup = client.post("/api/v1/auth/register-org", json={
        "org_name": "Ops4", "name": "Op", "email": f"op-{uuid.uuid4().hex[:10]}@e.com",
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(sup["org"]["id"]))
    cleanup["users"].append(uuid.UUID(sup["user"]["id"]))
    _make_super(sup["user"]["id"])
    sh = {"Authorization": f"Bearer {sup['access_token']}"}

    d = date.today() + timedelta(days=40)
    key = f"diwali-{uuid.uuid4().hex[:6]}"
    payload = {"source": "Telangana state holiday list 2026", "entries": [
        {"key": key, "name": "Diwali", "date": d.isoformat(), "kind": "holiday",
         "source": "Telangana state holiday list 2026", "prep_days": 21}]}
    first = client.post("/api/v1/platform/observances/bulk", headers=sh, json=payload).json()
    assert (first["created"], first["updated"]) == (1, 0)
    # V1-19 — an unplaceable state is reported, never silently dropped.
    assert first["unresolved_states"] == []

    payload["entries"][0]["name"] = "Deepavali"
    second = client.post("/api/v1/platform/observances/bulk", headers=sh, json=payload).json()
    assert (second["created"], second["updated"]) == (0, 1)

    rows = [o for o in client.get("/api/v1/platform/observances", headers=sh).json()
            if o["key"] == key]
    assert len(rows) == 1 and rows[0]["name"] == "Deepavali"
    # Platform data outlives the org, and a state-less row would otherwise show
    # up in every other test's suggestion feed.
    cleanup["observances"].append(uuid.UUID(rows[0]["id"]))


def test_only_a_human_press_writes_the_school_calendar(client, cleanup):
    """The packet's third Done-when clause, and the module's most severe trap
    (`S-122`, made structural by `D-57`): a catalogue entry must not reach
    `calendar_events` by any route except an approval. If a festival pack ever
    auto-created rows it would silently rewrite the effective-days denominator
    behind every plan forecast in the product."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    sup = client.post("/api/v1/auth/register-org", json={
        "org_name": "Ops5", "name": "Op", "email": f"op-{uuid.uuid4().hex[:10]}@e.com",
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(sup["org"]["id"]))
    cleanup["users"].append(uuid.UUID(sup["user"]["id"]))
    _make_super(sup["user"]["id"])
    sh = {"Authorization": f"Bearer {sup['access_token']}"}

    before = client.get("/api/v1/academics/calendar/summary", headers=h,
                        params={"year_id": ctx["year"]["id"]}).json()
    _catalogue(client, sh, cleanup, name="Holi", on=date.today() + timedelta(days=12),
               kind="holiday", source="National gazetted holidays 2026")
    # Reading the feed, reading the suggestions, reading the cost — none of them
    # may write a row.
    client.get("/api/v1/events/whats-on", headers=h)
    client.get("/api/v1/events/suggestions", headers=h)
    client.post("/api/v1/events/cost", headers=h, json={
        "academic_year_id": ctx["year"]["id"],
        "start_date": (date.today() + timedelta(days=12)).isoformat(), "lock": "closed"})
    after = client.get("/api/v1/academics/calendar/summary", headers=h,
                       params={"year_id": ctx["year"]["id"]}).json()
    assert len(after["events"]) == len(before["events"])
    assert after["teaching_days"] == before["teaching_days"]

    # A teacher cannot approve, dismiss, or price a lock.
    obs_id = client.get("/api/v1/events/suggestions", headers=h).json()[0]["id"]
    for path in (f"/api/v1/events/suggestions/{obs_id}/approve",
                 f"/api/v1/events/suggestions/{obs_id}/dismiss"):
        r = client.post(path, headers=ctx["th"], json={
            "start_date": date.today().isoformat(), "lock": "closed"})
        assert r.status_code == 403
    assert client.get("/api/v1/events/suggestions",
                      headers=ctx["th"]).status_code == 403
