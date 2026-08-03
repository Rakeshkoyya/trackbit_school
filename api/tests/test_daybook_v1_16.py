"""V1-16 — the day-book and the staff record.

What each test defends. These are the claims that would be *plausible but wrong*
if the code drifted, and the ones that carry a product law:

  * the grid tells a teaching period, a recorded period, a free period and an
    away period apart — the whole board is that distinction, and folding any two
    of them makes it a picture of nothing;
  * an unfilled period is FREE (`D-23`), so it is never counted as work, never
    coloured, and never appears in a "watch" line about the person;
  * the ring's denominator is the day's actual staff period slots, and a person
    who is away contributes none of them (`S-72`) — otherwise a school with two
    people on leave reads as a school with sixteen idle periods;
  * a non-working day says the school was shut rather than showing an empty grid
    that reads as "nobody worked" (the V1-4 call-board fix, third surface);
  * a category's colour comes from the server and is one of the validated five —
    a hand-typed hex is refused rather than stored;
  * the record is admin-or-self: a teacher may read their own and gets 403 on a
    colleague's, because this payload carries attendance and leave figures;
  * `days_not_marked` never becomes an absence, and never lands in a sentence
    about the person (`S-34`).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core.work_types import CATEGORY_COLORS, OTHER_COLOR, SLATE
from app.models import Membership
from tests.conftest import AdminSession


def _membership_id(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership.id).where(
            Membership.user_id == uuid.UUID(user_id), Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _teacher(client, cleanup, h, org_id):
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": cred["username"], "password": "supersecret1"}).json()
    return ({"Authorization": f"Bearer {login['access_token']}"},
            str(_membership_id(cred["user_id"], org_id)))


def _last_weekday() -> date:
    """A Mon–Sat date — the default `working_weekdays`. Running the suite on a
    Sunday must not turn every day-book assertion into "the school was shut"."""
    d = date.today()
    while d.weekday() == 6:
        d -= timedelta(days=1)
    return d


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Daybook Org", "name": "Director", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    org_id, h = reg["org"]["id"], {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"}).json()
    client.put("/api/v1/timetable/period-config", headers=h, json={
        "academic_year_id": year["id"], "periods_per_day": 3,
        "period_times": [
            {"start": "09:00", "end": "09:40", "kind": "period"},
            {"start": "09:40", "end": "10:20", "kind": "period"},
            {"start": "10:20", "end": "11:00", "kind": "period"},
        ]})
    th, teacher_mid = _teacher(client, cleanup, h, org_id)
    th2, teacher2_mid = _teacher(client, cleanup, h, org_id)

    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": subject["id"],
        "teacher_member_id": teacher_mid, "periods_per_week": 3}).json()

    on = _last_weekday()
    client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": klass["id"], "weekday": on.weekday(), "period_no": 1,
        "class_subject_id": cs["id"], "effective_from": "2026-04-01"})
    return {"h": h, "th": th, "th2": th2, "org_id": org_id, "year": year,
            "teacher_mid": teacher_mid, "teacher2_mid": teacher2_mid,
            "admin_mid": str(_membership_id(reg["user"]["id"], org_id)), "on": on}


# ── the grid ─────────────────────────────────────────────────────────────────
def test_grid_separates_teaching_recorded_and_free(client, cleanup):
    """Teaching · recorded work · free are three different facts. A board that
    cannot tell them apart tells the admin nothing they did not already assume."""
    ctx = _setup(client, cleanup)
    h, on = ctx["h"], ctx["on"]

    # The teacher records period 2 as notebook checking; period 3 stays free.
    client.put("/api/v1/staff/timesheet/entry", headers=ctx["th"], json={
        "date": on.isoformat(), "period_no": 2, "work_type": "notebook_checking"})

    book = client.get(f"/api/v1/insights/daybook?on={on}", headers=h).json()
    row = next(r for r in book["rows"] if r["member_id"] == ctx["teacher_mid"])
    kinds = {c["period_no"]: c["kind"] for c in row["cells"]}
    assert kinds == {1: "class", 2: "work", 3: "free"}

    # And the colours: teaching and free are structural tokens the client paints;
    # only the recorded cell carries a category hue, because it is the only one
    # that says something the timetable did not already know.
    colors = {c["period_no"]: c["color"] for c in row["cells"]}
    assert colors[1] == "teaching"
    assert colors[3] == "free"
    assert colors[2] in CATEGORY_COLORS

    assert row["teaching"] == 1 and row["work"] == 1 and row["free"] == 1


def test_free_periods_are_never_counted_as_work(client, cleanup):
    """`D-23`: an unfilled period IS a free one. `S-76` deleted a tile for
    counting them; nothing here may quietly bring it back as a percentage."""
    ctx = _setup(client, cleanup)
    book = client.get(f"/api/v1/insights/daybook?on={ctx['on']}",
                      headers=ctx["h"]).json()
    assert book["slots_work"] == 0
    assert book["slots_free"] > 0
    # Occupancy counts teaching + recorded work over the day's real slots — it
    # is never 100% just because nobody wrote anything down.
    assert book["occupied_pct"] < 100
    assert "free" in book["headline"]


def test_away_periods_leave_the_denominator(client, cleanup):
    """`S-72`: a person who is away has no free periods. Counting their day as
    eight idle slots would tell the admin the school has capacity it does not."""
    ctx = _setup(client, cleanup)
    h, on = ctx["h"], ctx["on"]
    before = client.get(f"/api/v1/insights/daybook?on={on}", headers=h).json()

    client.post("/api/v1/staff/attendance", headers=h, json={
        "date": on.isoformat(),
        "marks": [{"member_id": ctx["teacher2_mid"], "status": "absent"}]})

    after = client.get(f"/api/v1/insights/daybook?on={on}", headers=h).json()
    assert after["slots_away"] == 3
    assert after["slots_total"] == before["slots_total"] - 3
    row = next(r for r in after["rows"] if r["member_id"] == ctx["teacher2_mid"])
    assert {c["kind"] for c in row["cells"]} == {"away"}
    assert row["free"] == 0
    assert row["summary"].startswith("Away")


def test_closed_day_says_so_rather_than_showing_an_empty_grid(client, cleanup):
    """A Sunday is not a day nobody worked. The V1-4 call-board fix, extended to
    a third surface — an empty grid with no sentence reads as a school of idlers."""
    ctx = _setup(client, cleanup)
    sunday = ctx["on"]
    while sunday.weekday() != 6:
        sunday += timedelta(days=1)
    book = client.get(f"/api/v1/insights/daybook?on={sunday}", headers=ctx["h"]).json()
    assert book["is_working_day"] is False
    assert "Not a school day" in book["headline"]

    # And — the defect this test was extended for — it does not manufacture a
    # day's worth of free periods out of a day nobody was asked to work. Every
    # untouched cell is `closed`, the free count is zero, and the ring has no
    # denominator at all rather than reporting a share of nothing.
    kinds = {c["kind"] for r in book["rows"] for c in r["cells"]}
    assert kinds <= {"closed", "work", "class", "cover"}
    assert book["slots_free"] == 0
    assert book["slots_total"] == 0
    assert book["occupied_pct"] is None


def test_glimpse_is_the_same_computation_trimmed(client, cleanup):
    """The overview block and the tab must not be two reads. If they diverge, one
    of them is wrong and nobody can tell which (`S-51`)."""
    ctx = _setup(client, cleanup)
    on = ctx["on"]
    full = client.get(f"/api/v1/insights/daybook?on={on}", headers=ctx["h"]).json()
    small = client.get(f"/api/v1/insights/daybook/glimpse?on={on}&limit=1",
                       headers=ctx["h"]).json()
    assert small["headline"] == full["headline"]
    assert small["occupied_pct"] == full["occupied_pct"]
    assert small["slots_total"] == full["slots_total"]
    assert len(small["rows"]) == 1
    # The trim is NAMED, so the block can say "and 2 more" rather than showing a
    # partial school as if it were the whole one.
    assert small["rows_total"] == len(full["rows"])


# ── colours ──────────────────────────────────────────────────────────────────
def test_category_colours_come_from_the_validated_list(client, cleanup):
    """A colour a human typed is a colour nobody checked for colour-blind
    readers, and no test downstream could catch it."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    settings = client.get("/api/v1/org/settings", headers=h).json()
    cats = {c["key"]: c for c in settings["work_categories"]}
    assert cats["other"]["color"] == OTHER_COLOR
    assert all(c["color"] in {*CATEGORY_COLORS, SLATE} for c in cats.values())

    bad = client.patch("/api/v1/org/settings", headers=h, json={
        "work_categories": [{"key": "notebook_checking", "label": "Notebooks",
                             "active": True, "color": "#ff00ff"}]})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "bad_category_color"

    ok = client.patch("/api/v1/org/settings", headers=h, json={
        "work_categories": [{"key": "notebook_checking", "label": "Notebooks",
                             "active": True, "color": CATEGORY_COLORS[2]}]})
    assert ok.status_code == 200
    picked = {c["key"]: c["color"] for c in ok.json()["work_categories"]}
    assert picked["notebook_checking"] == CATEGORY_COLORS[2]
    # Rule 2 survives a colour edit: a category the payload dropped is retired,
    # never deleted, and keeps rendering on last month's grid.
    assert "exam_work" in picked


# ── one person's record ──────────────────────────────────────────────────────
def test_record_reads_as_a_record_not_a_score(client, cleanup):
    """`D-25`/`S-67`. The payload may carry where the time went; it may not carry
    a rating, and `days_not_marked` must stay the office's gap in its own word."""
    ctx = _setup(client, cleanup)
    h, on = ctx["h"], ctx["on"]
    client.put("/api/v1/staff/timesheet/entry", headers=ctx["th"], json={
        "date": on.isoformat(), "period_no": 2, "work_type": "exam_work",
        "note": "Marking the term papers"})

    rec = client.get(
        f"/api/v1/insights/staff/{ctx['teacher_mid']}/record?month={on:%Y-%m}&on={on}",
        headers=h).json()

    assert rec["teaching_periods"] >= 1
    assert rec["work_periods"] >= 1
    assert any(s["key"] == "exam_work" for s in rec["slices"])
    assert any("Exam work" in line for line in rec["where_time_went"])

    # The written part exists offline — most schools have no AI key at all.
    assert rec["summary"].strip()
    assert rec["summary_source"] == "computed"

    # Nothing anywhere in the written part reads as a verdict on the person.
    # This is the guard that stops a well-meaning edit turning a timesheet into
    # an appraisal, which is the one thing `D-25` promised it would never be.
    text = " ".join(
        [rec["headline"], rec["summary"], *rec["where_time_went"],
         *rec["highlights"], *rec["watch"]]).lower()
    for word in ("productive", "efficient", "underutilis", "underutiliz",
                 "poor", "rank", "rating", "target", "needs improvement",
                 "idle", "wasted"):
        assert word not in text, f"appraisal language reached the record: {word!r}"

    # `S-34`: the office's unmarked days are named as the office's, and the word
    # "absent" only appears if this person was actually marked away.
    watch = " ".join(rec["watch"]).lower()
    if rec["days_not_marked"]:
        assert "no staff attendance taken" in watch
    if rec["days_absent"] == 0:
        assert "absent" not in watch

    # The day's own timeline came back, with the note the teacher typed.
    work = next(s for s in rec["today"] if s["kind"] == "work")
    assert work["detail"] == "Marking the term papers"


def test_record_is_admin_or_self(client, cleanup):
    """It carries attendance and leave figures, so it is no more permissive than
    the stricter of the two services it merges."""
    ctx = _setup(client, cleanup)
    mine = client.get(f"/api/v1/insights/staff/{ctx['teacher_mid']}/record",
                      headers=ctx["th"])
    assert mine.status_code == 200

    theirs = client.get(f"/api/v1/insights/staff/{ctx['teacher_mid']}/record",
                        headers=ctx["th2"])
    assert theirs.status_code == 403

    # And the board itself stays admin-only — it names every colleague's day.
    assert client.get("/api/v1/insights/daybook", headers=ctx["th"]).status_code == 403


def test_record_stops_at_today_and_its_slices_add_up(client, cleanup):
    """Two defects a screenshot found, now pinned.

    The page read *"Teaching — 38 of 38 periods (100%)"* beside three categories
    at 3% each — 109% — because the ring's slices and the totals beside them were
    counted over two different sets of days. And on the 2nd of the month it
    called the whole month's timetable work already done, which is a forecast
    wearing a record's clothes on the one page that must not be one.
    """
    ctx = _setup(client, cleanup)
    h, on = ctx["h"], ctx["on"]
    client.put("/api/v1/staff/timesheet/entry", headers=ctx["th"], json={
        "date": on.isoformat(), "period_no": 2, "work_type": "prep"})

    rec = client.get(
        f"/api/v1/insights/staff/{ctx['teacher_mid']}/record?month={on:%Y-%m}&on={on}",
        headers=h).json()

    # 1. Nothing in the future is counted as worked.
    counted = [d for d in rec["days"] if d["state"] != "future"]
    assert rec["teaching_periods"] == sum(d["teaching"] for d in counted)
    assert rec["work_periods"] == sum(d["work"] for d in counted)
    assert any(d["state"] == "future" for d in rec["days"]) is (
        rec["end_date"] > on.isoformat())

    # 2. The ring adds up to the figure printed beside it.
    total = rec["teaching_periods"] + rec["cover_periods"] + rec["work_periods"]
    assert sum(s["periods"] for s in rec["slices"]) == total
    shares = [line for line in rec["where_time_went"] if "%" in line]
    assert shares, "the record must state each share with its denominator"
