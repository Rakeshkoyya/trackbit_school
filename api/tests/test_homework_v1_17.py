"""V1-17 — the homework funnel, and the series that used to disagree with it.

Two things this defends:

  * **The three headline figures nest, in one unit.** `set → checked → done` was
    previously two figures counted in *sets of homework* and one counted in
    *students*, so they could not be drawn on one track and did not read as one
    story. They are now all student-homeworks, and the invariant
    `given ⊇ checked ⊇ graded` is asserted rather than assumed.

  * **The series goes through `core/homework_verdict` like everything else.**
    It used to be a second walk over the window with its own rules: `late` was
    dropped from the numerator, `carried`/`waived` stayed in the denominator,
    and the absent→carried rewrite never ran. The chart therefore read lower
    than the sentence printed directly above it, and a child off sick pulled
    the line down. That is `S-51` — one fact, two computations — and these
    tests are what stop it coming back.

The rule that outranks both, re-asserted here because the funnel is where it is
most tempting to break: **the `given → checked` gap is the teacher's and is
never spent on the children.** `completion` divides by `graded`, never by
`given`, so a school that checked nothing can never read as a school that did
nothing.
"""

from datetime import date, timedelta

from app.core import homework_verdict as verdicts
from app.services.homework import bucket_days
from tests.test_homework_v1_5 import _check, _set_hw
from tests.test_homework_v1_5 import _setup as _hw_setup


def _board(client, h, **params):
    r = client.get("/api/v1/insights/homework", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _queue_ids(client, th):
    q = client.get("/api/v1/homework/queue", headers=th).json()
    return {i["text"]: i["assignment_id"] for i in q.get("items", [])}


# ── the funnel ───────────────────────────────────────────────────────────────
def test_the_three_stages_nest_and_share_one_unit(client, cleanup):
    """`given ⊇ checked ⊇ graded`, all in student-homeworks.

    Three students, two sets of homework, one of them checked. The old board
    would have said "2 assigned, 1 checked, 3 done" — two units in one row.
    """
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    yest = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Ex 1.1", yest)
    _set_hw(client, th, cs, "Ex 1.2", yest)

    ids = _queue_ids(client, th)
    _check(client, th, ids["Ex 1.1"], [])          # everyone did it

    f = _board(client, h)["overview"]["funnel"]
    # 2 sets × 3 students. Both sets contribute to `given`; only the checked one
    # contributes to `checked`.
    assert f["given"] == 6, f
    assert f["checked"] == 3, f
    assert f["graded"] == 3, f
    assert f["given"] >= f["checked"] >= f["graded"], "the stages must nest"
    assert f["assignments"] == 2
    assert f["class_subjects"] == 1

    # Each rate names the denominator it actually uses, and they are different
    # denominators — that is the whole reason both exist.
    assert f["check_rate"] == round(3 / 6, 3)
    assert f["completion"] == 1.0
    assert f["done_weighted"] == 3.0


def test_completion_never_divides_by_what_was_merely_given(client, cleanup):
    """HW-1's load-bearing rule, at the funnel.

    A teacher who has gone through nothing must not produce a completion figure
    at all — not 0%, not a low score. The gap belongs to her, and spending it on
    the children is the one mistake this module exists to prevent.
    """
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    _set_hw(client, th, cs, "Unchecked", (date.today() - timedelta(days=1)).isoformat())

    board = _board(client, h)
    f = board["overview"]["funnel"]
    assert f["given"] == 3
    assert f["checked"] == 0
    assert f["graded"] == 0
    assert f["completion"] is None, "None is not zero and must not become one"
    assert f["check_rate"] == 0.0, "0% CHECKED is a true statement about the teacher"

    # And the sentence says so in words rather than printing a percentage.
    assert "0%" not in board["headline"]
    assert "none checked yet" in board["headline"]


def test_carried_and_waived_leave_the_denominator_but_stay_visible(client, cleanup):
    """`D-34`/`S-98`: between `checked` and `graded` sit the children who were
    away and the work that was let go. They must be reported, never folded
    silently into either gap."""
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    sids = [s["id"] for s in ctx["students"]]
    yest = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Ex 2.1", yest)

    aid = _queue_ids(client, th)["Ex 2.1"]
    _check(client, th, aid, [
        {"student_id": sids[0], "status": "carried"},
        {"student_id": sids[1], "status": "waived"},
    ])                                              # sids[2] did it

    f = _board(client, h)["overview"]["funnel"]
    assert f["checked"] == 3, "all three were checked"
    assert f["graded"] == 1, "carried + waived leave the denominator"
    assert f["carried"] == 1 and f["waived"] == 1, "…and are still reported"
    assert f["completion"] == 1.0, "the one child who was asked, did it"
    # The scope rows carry `waived` too — it used to be missing from them
    # entirely, so waived work was invisible on the by-class table while the
    # student history reported it.
    assert _board(client, h)["overview"]["by_class"][0]["waived"] == 1


# ── the series ───────────────────────────────────────────────────────────────
def test_the_series_counts_late_as_done_like_every_other_figure(client, cleanup):
    """`S-99` on the chart, not only in the sentence.

    The series used to count `status == "done"` literally, so a class where
    everything arrived late drew as a collapse while the headline above it read
    fine. Same window, same rows, two answers.
    """
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    sids = [s["id"] for s in ctx["students"]]
    yest = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Ex 3.1", yest)

    aid = _queue_ids(client, th)["Ex 3.1"]
    _check(client, th, aid, [{"student_id": s, "status": "late"} for s in sids])

    board = _board(client, h)
    ov = board["overview"]
    assert ov["funnel"]["late"] == 3
    assert ov["funnel"]["completion"] == 1.0, "late IS done"

    day = [d for d in board["daily"] if d["date"] == yest]
    assert day, board["daily"]
    day = day[0]
    assert day["done"] == 3, "the chart must not drop late from its numerator"
    assert day["completion"] == 1.0
    # The bucket and the roll-up are the same arithmetic, so they agree.
    assert day["completion"] == ov["funnel"]["completion"]


def test_an_unchecked_day_is_a_state_on_the_series_never_a_zero(client, cleanup):
    """§5 / §10: not-captured is never a failure and never a zero. The bucket
    still reports the volume — how much was given, and how much nobody has been
    through — so the day is visible without being scored."""
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    yest = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Ex 4.1", yest)

    day = [d for d in _board(client, h)["daily"] if d["date"] == yest][0]
    assert day["completion"] is None, "no verdict is not a bad verdict"
    assert day["given"] == 3
    assert day["not_checked"] == 3
    assert day["expected"] == 0, "nothing is in the denominator yet"
    assert day["done"] == 0
    # given == checked + not_checked at every scope, which is what lets the two
    # gaps be drawn as lengths on one track.
    assert day["given"] == day["not_checked"] + day["expected"]


def test_long_ranges_bucket_by_week_rather_than_drawing_a_year_of_days():
    """A year at one column per day is 365 marks nobody can read, and the shape
    — the only reason the series exists — survives weekly buckets fine."""
    assert bucket_days(7) == 1
    assert bucket_days(14) == 1
    assert bucket_days(21) == 1
    assert bucket_days(30) == 7
    assert bucket_days(365) == 7


def test_a_year_range_is_a_real_range_not_a_clamp(client, cleanup):
    """The tab offers Week · Month · Term · Year, so the endpoint has to accept
    a year. It used to cap at 60 days and silently return a different window
    from the one the filter said."""
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    _set_hw(client, th, cs, "Ex 5.1", (date.today() - timedelta(days=200)).isoformat())

    board = _board(client, h, window_days=365)
    assert board["overview"]["window_days"] == 365
    assert board["overview"]["funnel"]["given"] == 3, "the old 60-day cap hid this"
    assert all(d["days"] == 7 for d in board["daily"]), "a year buckets weekly"
    assert all(d["label"] for d in board["daily"]), "a week bucket is not a date"


# ── the matrix ───────────────────────────────────────────────────────────────
def test_the_matrix_resolves_a_class_and_a_subject_into_one_cell(client, cleanup):
    """The two bar charts each collapsed a whole axis, so "6-A is low" and
    "Maths is low" could not resolve into "6-A Maths is where it happens"."""
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    sids = [s["id"] for s in ctx["students"]]
    yest = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Ex 6.1", yest)
    aid = _queue_ids(client, th)["Ex 6.1"]
    _check(client, th, aid, [{"student_id": sids[0], "status": "not_done"}])

    ov = _board(client, h)["overview"]
    assert ov["matrix_classes"] == ["6-A"]
    assert len(ov["matrix_subjects"]) == 1
    cell = ov["matrix"][0]
    assert cell["class_key"] == "6-A"
    assert cell["given"] == 3 and cell["graded"] == 3
    assert cell["completion"] == round(2 / 3, 3)
    # Tone is decided server-side (the V1-15 precedent): three surfaces render
    # these cells, and a tone each worked out for itself would be three
    # verdicts about one teacher on one morning.
    assert cell["tone"] == "amber"


def test_a_pair_nobody_checked_is_a_neutral_cell_not_a_red_one(client, cleanup):
    """The one rule the matrix could most easily break: a hole in the record
    must not look like the worst cell on the grid."""
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    _set_hw(client, th, cs, "Ex 7.1", (date.today() - timedelta(days=1)).isoformat())

    cell = _board(client, h)["overview"]["matrix"][0]
    assert cell["completion"] is None
    assert cell["tone"] == "neutral", "not-captured is never red"
    assert cell["given"] == 3 and cell["checked"] == 0


# ── the improvement delta ────────────────────────────────────────────────────
def test_most_improved_carries_its_own_field_and_not_the_streak(client, cleanup):
    """The delta used to be written over `streak`, so the row claimed a miss
    streak it did not have and the screen printed "N fewer misses" out of a
    field named for the opposite thing. Any second consumer inherited the lie.
    """
    ctx = _hw_setup(client, cleanup)
    h, th, cs = ctx["h"], ctx["th"], ctx["cs"]["id"]
    sids = [s["id"] for s in ctx["students"]]

    # Missed it early in the window, did it recently.
    early = (date.today() - timedelta(days=10)).isoformat()
    late_day = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, cs, "Early", early)
    _set_hw(client, th, cs, "Recent", late_day)
    ids = _queue_ids(client, th)
    _check(client, th, ids["Early"], [{"student_id": sids[0], "status": "not_done"}])
    _check(client, th, ids["Recent"], [])

    improved = _board(client, h)["overview"]["most_improved"]
    row = next((r for r in improved if r["student_id"] == sids[0]), None)
    assert row is not None, improved
    assert row["improvement"] >= 1
    # `streak` still means what its name says: this child's most recent
    # homework day was done, so there is no run of misses.
    assert row["streak"] == 0


# ── the invariant, stated once ───────────────────────────────────────────────
def test_the_funnel_and_the_verdict_table_cannot_drift():
    """`done_weighted` is what `completion` divides. Asserting it here means a
    screen can render the numerator without re-deriving it from the parts and
    getting `partial` wrong on the way."""
    counts = verdicts.tally(["done", "late", "partial", "not_done",
                             "carried", "waived", "not_checked"])
    weighted = counts["done"] + counts["late"] + 0.5 * counts["partial"]
    assert counts["graded"] == 4
    assert verdicts.completion(counts) == round(weighted / counts["graded"], 3)
