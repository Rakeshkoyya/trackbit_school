"""The teacher's own attendance board (founder, 2026-08-05).

The school's rule is that the class teacher takes the register at period one and
**any teacher of the class can if she is away**. `assert_can_take_class` has
permitted exactly that since V2-P2 — but attendance was reachable only from a My
Day period card, so the person covering had no door into it. This suite defends
the screen that closes the gap, and the lines it must not cross:

  * a class nobody has marked shows the ROLL and the word, never a 0% and never
    a red tone — the same rule the admin board and My Class were corrected to;
  * any teacher of the class may open it, class teacher or not, and may still
    open it after somebody else already marked it (correcting a mis-tap is not
    a privilege);
  * a teacher who takes NOTHING in a class never sees it at all;
  * the board reads any date, so a register missed on Tuesday can be taken on
    Wednesday;
  * a mark made from here is the same mark: it reaches the admin's board, and
    the day's first marked period is still the only one that alerts guardians,
    so a later correction never messages a family twice.
"""

from datetime import date

import pytest

from tests.test_insights import _recent_working_days, _setup, _slot


def _board(client, headers, on=None):
    url = "/api/v1/attendance/my-classes"
    if on is not None:
        url += f"?on_date={on.isoformat()}"
    res = client.get(url, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _mark(client, h, ctx, period_no=1, absent_ids=(), on=None):
    body = {
        "class_id": ctx["class"]["id"], "period_no": period_no,
        "class_subject_id": ctx["cs"]["id"],
        "exceptions": [{"student_id": sid, "status": "absent"} for sid in absent_ids],
    }
    if on is not None:
        body["date"] = on.isoformat()
    return client.post("/api/v1/attendance/mark", headers=h, json=body)


def test_unmarked_class_shows_the_roll_and_a_word(client, cleanup):
    ctx = _setup(client, cleanup)
    board = _board(client, ctx["th"])
    row = next(r for r in board["classes"] if r["class_id"] == ctx["class"]["id"])

    assert row["marked"] is False
    assert row["roster"] == len(ctx["students"])   # the strength, always
    assert row["pct"] is None
    assert row["present"] == 0 and row["absent"] == 0
    assert row["tone"] == "neutral", "an unopened register is never red"
    assert "not taken" in row["headline"].lower()
    assert row["can_mark"] is True and row["first_of_day"] is True
    assert row["subject_name"] == "Science"
    assert "still needs the register taken" in board["headline"]


def test_a_subject_teacher_may_take_it_and_the_board_names_who_did(client, cleanup):
    """Not restricted to the class teacher. That is the whole point: on the day
    she is away, the register must still be takeable by somebody in the room."""
    ctx = _setup(client, cleanup)
    today = _recent_working_days(1)[0]
    if today != date.today():
        pytest.skip("today is not a working day")
    _slot(client, ctx["h"], ctx, today.weekday(), 1)

    row = next(r for r in _board(client, ctx["th"])["classes"]
               if r["class_id"] == ctx["class"]["id"])
    assert row["is_class_teacher"] is False, "she is a subject teacher here"
    assert row["can_mark"] is True

    assert _mark(client, ctx["th"], ctx, 1,
                 absent_ids=[ctx["students"][0]["id"]], on=today).status_code == 200

    row = next(r for r in _board(client, ctx["th"])["classes"]
               if r["class_id"] == ctx["class"]["id"])
    assert row["marked"] is True
    assert row["marked_period_no"] == 1
    assert row["marked_by_name"]
    assert row["absent"] == 1
    assert row["present"] == len(ctx["students"]) - 1
    assert row["absentee_names"] == [ctx["students"][0]["full_name"]]
    assert row["first_of_day"] is False
    # Still editable — correcting a mis-tap is not a privilege.
    assert row["can_mark"] is True


def test_the_admin_board_sees_the_same_mark(client, cleanup):
    """A register taken from the teacher's screen is the same register. If these
    two ever disagree the school has two attendance systems."""
    ctx = _setup(client, cleanup)
    today = _recent_working_days(1)[0]
    if today != date.today():
        pytest.skip("today is not a working day")
    _slot(client, ctx["h"], ctx, today.weekday(), 1)
    _mark(client, ctx["th"], ctx, 1, absent_ids=[ctx["students"][0]["id"]], on=today)

    presence = client.get("/api/v1/insights/presence", headers=ctx["h"]).json()
    ring = next(r for r in presence["rings"] if r["key"] == "students")
    assert ring["marked"] is True
    assert ring["absent"] == 1
    assert ring["counted"] == len(ctx["students"])


def test_a_teacher_who_takes_nothing_in_the_class_never_sees_it(client, cleanup):
    """Not filtered to an empty table — absent from the board entirely, which is
    what "you are not assigned to any class" is for."""
    ctx = _setup(client, cleanup)
    board = _board(client, ctx["th2"])   # the second teacher teaches nothing
    assert board["classes"] == []
    assert "not assigned to any class" in board["headline"]


def test_the_board_reads_any_date(client, cleanup):
    """A register missed on Tuesday is taken on Wednesday. Without a date the
    screen can only ever fix today, which is not when anybody notices."""
    ctx = _setup(client, cleanup)
    days = _recent_working_days(2)
    if days[0] != date.today():
        pytest.skip("today is not a working day")
    today, yesterday = days
    _slot(client, ctx["h"], ctx, yesterday.weekday(), 1)
    _mark(client, ctx["th"], ctx, 1, on=yesterday)

    past = _board(client, ctx["th"], on=yesterday)
    assert past["date"] == yesterday.isoformat()
    assert past["is_today"] is False
    assert next(r for r in past["classes"]
                if r["class_id"] == ctx["class"]["id"])["marked"] is True

    # ...and today is still its own, unmarked, day — never yesterday's figures.
    now = _board(client, ctx["th"], on=today)
    assert next(r for r in now["classes"]
                if r["class_id"] == ctx["class"]["id"])["marked"] is False


def test_an_admin_sees_every_class(client, cleanup):
    ctx = _setup(client, cleanup)
    board = _board(client, ctx["h"])
    assert {r["class_id"] for r in board["classes"]} == {ctx["class"]["id"]}
    assert board["classes"][0]["can_mark"] is True
