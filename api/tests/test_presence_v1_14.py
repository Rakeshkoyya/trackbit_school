"""V1-14 — the presence panorama (three rings, three blocks, one month).

What each test defends. These are the claims that would be *plausible but wrong*
if the code drifted, and every one of them is a way a dashboard starts lying:

  * a ring nobody has marked is neutral and carries a WORD, never 0% and never
    red — an admin who marks staff at 10am must not open a red board every
    morning, and "nobody has marked it" is not "nobody came in";
  * the student ring carries TWO denominators and never confuses them:
    `counted` (the roster of classes that actually marked) is what the
    percentage divides by, so a day where two of twelve classes captured
    attendance is a day about two classes — while `total` is the school's whole
    strength, readable on a morning nobody has marked anything;
  * on an OPEN day the board is about today, captured or not. It falls back to
    the last day the school ran only when today is closed — showing yesterday's
    figures under today's heading answers "has the register been taken?" with
    last night's answer;
  * three or fewer absentees are NAMED with their actions; four collapse to one
    sentence and a link — the founder's rule, and the difference between a
    morning's work and a screen nobody reads;
  * the teacher block counts uncovered periods, because "2 teachers away" and
    "9 classes with nobody in front of them" are two facts and the second is the
    one that costs a lesson;
  * a month grid cell for a day the class marked nothing is `unmarked`, never
    100% present — the whole reason the grid exists rather than a line;
  * a student's month percentage is denominated on their class's MARKED days,
    so a week nobody captured cannot flatter the school;
  * the board is admin-only.
"""

import uuid
from datetime import date, timedelta

import pytest

from tests.test_insights import _recent_working_days, _setup, _slot


def _mark(client, h, ctx, period_no, absent_ids=(), on=None):
    body = {
        "class_id": ctx["class"]["id"], "period_no": period_no,
        "class_subject_id": ctx["cs"]["id"],
        "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids],
    }
    if on is not None:
        body["date"] = on.isoformat()
    return client.post("/api/v1/attendance/mark", headers=h, json=body)


def _ring(board, key):
    return next(r for r in board["rings"] if r["key"] == key)


def _group(board, key):
    return next(g for g in board["groups"] if g["key"] == key)


# ── the rings ────────────────────────────────────────────────────────────────
def test_unmarked_rings_are_neutral_and_wordy_never_zero(client, cleanup):
    """The single most important rule on this board. Before anybody has marked
    anything, all three rings must read as *not captured* — a 0% ring would tell
    the admin the school is empty, and a red one would tell them it is a
    disaster, when in fact it is 8:15am."""
    ctx = _setup(client, cleanup)
    board = client.get("/api/v1/insights/presence", headers=ctx["h"]).json()

    for key in ("students", "teachers", "admins"):
        ring = _ring(board, key)
        assert ring["marked"] is False, key
        assert ring["pct"] is None, key
        assert ring["tone"] == "neutral", key      # never red, never green
        assert ring["present"] == 0 and ring["caption"], key
        # The word is the whole point — "not marked yet" / "nothing marked yet".
        assert "not" in ring["caption"] or "no " in ring["caption"], ring["caption"]

    # Staff rings still know their denominator: three people are on the roll
    # (the admin plus two teachers) even though nobody has been marked.
    assert _ring(board, "teachers")["total"] == 2
    assert _ring(board, "admins")["total"] == 1


def test_student_ring_denominates_on_classes_that_marked(client, cleanup):
    """Two denominators, and the difference between them is the module.

    A second class that captured nothing must not join the PERCENTAGE's
    denominator — if it did, one class marking on a quiet morning would report
    the school as catastrophically absent and send somebody chasing a phantom.
    That denominator is `counted`.

    But `total` is the school's strength and must be the whole roll whether or
    not anyone has marked (founder, 2026-08-05): before this the ring reported
    the marked classes AS the school, so one class of twelve taking the register
    rendered as a complete day.
    """
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    school_day = _recent_working_days(1)[0]
    _slot(client, h, ctx, school_day.weekday(), 1)

    # A whole second class nobody marks today.
    other = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": ctx["year"]["id"], "name": "7",
                              "section": "A"}).json()
    for name in ("Chandra Iyer", "Divya Nair", "Eshan Roy"):
        client.post("/api/v1/students", headers=h,
                    json={"admission_no": f"B{uuid.uuid4().hex[:6]}", "full_name": name,
                          "class_id": other["id"]})

    _mark(client, h, ctx, 1, absent_ids=[ctx["students"][0]["id"]], on=school_day)
    board = client.get("/api/v1/insights/presence", headers=h).json()
    ring = _ring(board, "students")

    # The percentage is over 6-A's two students only — 7-A captured nothing and
    # its three children are neither present nor absent.
    assert ring["marked"] is True
    assert ring["counted"] == 2
    assert ring["absent"] == 1 and ring["present"] == 1
    assert ring["pct"] == 50.0
    # ...and the strength is the whole school, always.
    assert ring["total"] == 5
    assert ring["unmarked"] == 3
    assert ring["note"] == "1 of 2 classes not marked yet"
    # The caption says what the GAP is — the figure itself is inside the ring,
    # and repeating it there wastes the only line that can add anything.
    assert ring["caption"] == "1 away · 50.0% in"
    # The board's roll is every cohort's strength — students AND staff — so it
    # is asserted structurally rather than as a magic number. `counted` is what
    # in + away sum to; the difference is what nobody has marked.
    assert board["roll"] == sum(r["total"] for r in board["rings"])
    assert board["counted"] == sum(r["counted"] for r in board["rings"] if r["marked"])
    assert board["not_marked"] == board["roll"] - board["counted"]
    assert board["in_building"] + board["away"] == board["counted"]
    # The students' three unmarked children are inside that gap.
    assert board["not_marked"] >= 3


def test_open_day_with_nothing_marked_shows_today_not_yesterday(client, cleanup):
    """The founder's defect, 2026-08-05: a morning nobody had captured showed
    YESTERDAY's figures under today's heading, because the anchor walked back a
    fortnight looking for a day with capture. An open day is now always today,
    and an empty register reads as an empty register — while the roll, which
    does not depend on anyone marking anything, is still there to be read."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    # Newest first. The claim is only meaningful when today itself is a school
    # day — on a Sunday the board is *supposed* to fall back.
    today, yesterday = _recent_working_days(2)
    if today != date.today():
        pytest.skip("today is not a working day")
    _slot(client, h, ctx, yesterday.weekday(), 1)

    # Captured yesterday, nothing today.
    _mark(client, h, ctx, 1, absent_ids=[ctx["students"][0]["id"]], on=yesterday)
    board = client.get("/api/v1/insights/presence", headers=h).json()

    if board["date"] != today.isoformat():
        pytest.skip("today is not a working day for this org")
    assert board["is_today"] is True
    assert board["marked"] is False
    # Not a figure, and never a zero: the strength is known, the register isn't.
    assert board["roll"] == sum(r["total"] for r in board["rings"]) >= 2
    assert board["counted"] == 0
    assert board["in_building"] == 0 and board["away"] == 0
    ring = _ring(board, "students")
    assert ring["marked"] is False and ring["total"] == 2 and ring["pct"] is None
    # And yesterday's absentee is NOT named as away today.
    group = next(g for g in board["groups"] if g["key"] == "students")
    assert group["count"] == 0
    assert group["tone"] == "neutral"  # nothing captured is never good news
    assert "register" in group["headline"].lower()


# ── named under the threshold, counted over it ───────────────────────────────
def test_three_absentees_are_named_with_actions(client, cleanup):
    """At or under the limit the block hands the admin the people and the
    buttons. A count here would just be a second link to the tab."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    school_day = _recent_working_days(1)[0]
    _slot(client, h, ctx, school_day.weekday(), 1)
    _mark(client, h, ctx, 1, absent_ids=[ctx["students"][0]["id"]], on=school_day)

    group = _group(client.get("/api/v1/insights/presence", headers=h).json(), "students")
    assert group["count"] == 1
    assert group["inline"] is True
    assert len(group["rows"]) == 1
    row = group["rows"][0]
    assert row["name"] == "Asha Rao"
    assert row["tone"] == "red"                      # nobody has explained it
    assert "remind_guardian" in row["actions"]
    assert "assign_followup" in row["actions"]
    assert row["done"] == []
    assert "no reason on record" in group["headline"]


def test_over_the_limit_collapses_to_one_sentence(client, cleanup):
    """Four absentees is not four rows with four buttons — it is one line and a
    link. The rule lives server-side so every surface obeys the same threshold."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    school_day = _recent_working_days(1)[0]
    _slot(client, h, ctx, school_day.weekday(), 1)
    extra = [
        client.post("/api/v1/students", headers=h,
                    json={"admission_no": f"C{uuid.uuid4().hex[:6]}", "full_name": name,
                          "class_id": ctx["class"]["id"]}).json()
        for name in ("Farah Sheikh", "Gopi Menon")
    ]
    everyone = [s["id"] for s in ctx["students"]] + [s["id"] for s in extra]
    _mark(client, h, ctx, 1, absent_ids=everyone, on=school_day)

    group = _group(client.get("/api/v1/insights/presence", headers=h).json(), "students")
    assert group["count"] == 4
    assert group["inline"] is False
    assert group["rows"] == []                       # named nowhere, counted here
    assert "4 students are away" in group["headline"]
    assert group["href"] == "/dashboard/attendance"


def test_teacher_block_counts_uncovered_periods_not_just_bodies(client, cleanup):
    """"1 teacher away" is a fact; "3 classes with nobody assigned" is the one
    that costs lessons. The block must carry both."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    today = _recent_working_days(1)[0]
    for period_no in (1, 2, 3):
        _slot(client, h, ctx, today.weekday(), period_no)

    client.post("/api/v1/staff/attendance", headers=h, json={
        "date": today.isoformat(),
        "marks": [{"member_id": ctx["teacher_mid"], "status": "absent",
                   "note": "Sick"}]})

    board = client.get("/api/v1/insights/presence", headers=h).json()
    group = _group(board, "teachers")
    assert group["count"] == 1
    assert group["inline"] is True
    assert group["tone"] == "red"
    assert "3 classes have nobody assigned" in group["headline"]
    row = group["rows"][0]
    assert "3 of 3 periods uncovered" in row["subtitle"]
    assert "Sick" in row["subtitle"]
    assert "arrange_cover" in row["actions"]

    # …and the teachers ring is now marked, with its own denominator.
    ring = _ring(board, "teachers")
    assert ring["marked"] is True and ring["total"] == 2 and ring["present"] == 1


# ── the month grid ───────────────────────────────────────────────────────────
def test_month_grid_keeps_unmarked_days_out_of_every_figure(client, cleanup):
    """The grid's reason to exist. A day the class captured nothing is its own
    state — it must not be drawn as a full house, must not raise the class
    average, and must not enter a student's denominator."""
    ctx = _setup(client, cleanup)
    h, asha = ctx["h"], ctx["students"][0]
    days = _recent_working_days(3)
    for d in days:
        _slot(client, h, ctx, d.weekday(), 1)

    # Marked on two of the three days; Asha absent on one of those two.
    _mark(client, h, ctx, 1, absent_ids=[asha["id"]], on=days[0])
    _mark(client, h, ctx, 1, on=days[2])

    month = client.get("/api/v1/insights/presence/month?days=30", headers=h).json()
    row = month["classes"][0]
    by_date = {c["date"]: c for c in row["cells"]}

    assert by_date[days[0].isoformat()]["state"] == "marked"
    assert by_date[days[2].isoformat()]["state"] == "marked"
    # The middle day: nothing captured. Not 100%, not zero — unmarked.
    assert by_date[days[1].isoformat()]["state"] == "unmarked"
    assert by_date[days[1].isoformat()]["pct"] is None

    assert row["marked_days"] == 2                   # not 3
    assert row["absent_days"] == 1
    # The class average is over the two days it actually marked: (50 + 100) / 2.
    assert row["pct"] == 75.0

    # The org day-series carries the blank day rather than closing it up.
    series = {d["date"]: d for d in month["students"]}
    assert series[days[1].isoformat()]["marked"] is False
    assert series[days[1].isoformat()]["pct"] is None

    # And the student's month is denominated on the class's MARKED days.
    profile = next(p for p in month["profiles"] if p["full_name"] == "Asha Rao")
    assert profile["days_absent"] == 1
    assert profile["marked_days"] == 2               # never 3
    assert profile["pct"] == 50.0
    assert "absent 1 of 2 marked days this month" in profile["summary"]


def test_month_names_the_capture_gap_as_the_schools_own(client, cleanup):
    """A gap in the record is the school's, never a child's. It must appear as
    an anomaly in its own words and never inside an absence figure."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    day = _recent_working_days(1)[0]
    _slot(client, h, ctx, day.weekday(), 1)
    _mark(client, h, ctx, 1, on=day)

    month = client.get("/api/v1/insights/presence/month?days=14", headers=h).json()
    gap = next(a for a in month["anomalies"] if a["key"] == "capture_gap")
    assert "captured no attendance" in gap["detail"]
    assert "not full" in gap["detail"]
    # One marked day out of the window, and the headline says which.
    assert "1 day marked" in month["headline"] or "1 days marked" in month["headline"]


def test_admin_desk_carries_the_work_not_the_periods(client, cleanup):
    """An absent admin's blast radius is their work. The block must be able to
    say so on a day nobody is absent too — "who is carrying what" is a question
    with an answer every morning."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    boards = client.get("/api/v1/boards", headers=h).json()
    board_id = (boards["my_boards"] + boards["other_public"])[0]["id"]
    me = client.get("/api/v1/auth/me", headers=h).json()
    yesterday = date.today() - timedelta(days=1)
    client.post("/api/v1/tasks", headers=h, json={
        "board_id": board_id, "title": "Sign the transfer certificates",
        "assignee_id": me["user"]["id"],
        "due_at": f"{yesterday.isoformat()}T09:00:00Z"})

    month = client.get("/api/v1/insights/presence/month", headers=h).json()
    desk = month["admin_work"][0]
    assert desk["overdue"] == 1
    assert desk["rows"][0]["title"] == "Sign the transfer certificates"
    assert "1 task due or overdue" in desk["summary"]
    # Everyone who could receive a transferred task is offered by name.
    assert month["admin_options"] and month["admin_options"][0]["name"]

    group = _group(client.get("/api/v1/insights/presence", headers=h).json(), "admins")
    assert group["count"] == 0                       # nobody away…
    assert "1 task is due or overdue" in group["headline"]   # …but work is waiting


def test_presence_is_admin_only(client, cleanup):
    """Named students, staff absences and the admin desk — none of it is a
    teacher's to read (§2)."""
    ctx = _setup(client, cleanup)
    for path in ("/api/v1/insights/presence", "/api/v1/insights/presence/month"):
        assert client.get(path, headers=ctx["th"]).status_code == 403
