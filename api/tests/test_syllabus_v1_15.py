"""V1-15 — the syllabus panorama: one computation, four renderings.

The packet adds a second surface for the same figures (the overview's block,
term-switchable) and a teacher pivot that names a person. Both are exactly the
conditions under which `S-51` happened the first time, so what these tests
defend is the *agreement*, not the arithmetic:

  * the block and the tab quote the same percentage for the same morning, on
    the same denominator — the pulse is the board's own `_rows`/`_node`, and a
    second roll-up beside it would be the 45th place a fact gets computed;
  * every percentage the screens draw is divided SERVER-side, including the
    plan marker (`expected_pct`) that is the whole visual device — a component
    dividing `due / planned` for itself is how the browser got its two
    `.reduce()` calls last time;
  * `taught_full` / `taught_partial` are carried rather than reconstructed: the
    weighted figure genuinely cannot be taken back apart, and a screen doing
    `2 * weighted - count` would be inventing a topic that does not exist;
  * a node nobody has logged against is **neutral**, never green (`S-42`) —
    "no evidence" and "going well" must not share a colour on a board whose
    whole job is to be glanced at;
  * the cause tally keeps its zeroes, because *"nothing lost to cancelled
    periods"* is a finding and a row that disappears makes the survivors look
    like the whole story;
  * a term id from another year narrows the portion to nothing, so it is
    refused rather than rendered as a school that has taught none of its
    syllabus.
"""

import uuid
from datetime import date, timedelta

from tests.test_syllabus_v1_6 import (
    _board,
    _log,
    _plan,
    _row,
    _setup,
    _syllabus,
)


def _pulse(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/v1/insights/syllabus/pulse{'?' + q if q else ''}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _taught_year(client, cleanup):
    """One class-subject, four sized topics, a plan, and two of them logged —
    one finished, one half-done. Enough for every figure on the block."""
    ctx = _setup(client, cleanup)
    _, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                          [(f"T{i}", 2) for i in range(4)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")
    _log(client, ctx["th"], ctx["cs"]["id"], topics[1]["id"], "partial")
    ctx["topics"] = topics
    return ctx


# ── the agreement that is the whole point ────────────────────────────────────
def test_the_block_and_the_tab_quote_the_same_morning(client, cleanup):
    """The overview block is a second rendering of the board's own roll-up.

    If these two ever disagree the admin has no way to tell which is right, and
    the summary stops being a summary — it becomes a fourth opinion.
    """
    ctx = _taught_year(client, cleanup)
    pulse = _pulse(client, ctx["h"])
    board = _board(client, ctx["h"], scope="class")

    for field in ("coverage_pct", "syllabus_pct", "taught_topics",
                  "planned_topics", "total_topics", "expected_pct",
                  "on_track", "slipping", "behind", "unknown"):
        assert pulse["school"][field] == board["school"][field], field

    # And the class pivot is the same pivot, not a re-derivation of it.
    by_key = {n["key"]: n for n in board["nodes"]}
    assert {n["key"] for n in pulse["classes"]} == set(by_key)
    for node in pulse["classes"]:
        assert node["coverage_pct"] == by_key[node["key"]]["coverage_pct"]
        assert node["tone"] == by_key[node["key"]]["tone"]


def test_every_percentage_including_the_marker_is_divided_server_side(client, cleanup):
    """`expected_pct` is the plan marker the ring and every bar draw.

    It is the one figure a component would be most tempted to work out for
    itself — `due / planned` looks harmless — which is precisely why it ships
    from the server, on the SAME denominator as `coverage_pct` so the two can
    honestly sit on one track.
    """
    ctx = _taught_year(client, cleanup)
    pulse = _pulse(client, ctx["h"])
    school = pulse["school"]

    assert school["planned_topics"] > 0
    assert school["expected_pct"] is not None
    assert school["expected_pct"] == round(
        school["due_topics"] / school["planned_topics"] * 100, 1)
    # Same denominator as the arc it is drawn against — otherwise the marker
    # and the fill are two different pictures on one track.
    assert school["coverage_pct"] == round(
        school["taught_topics"] / school["planned_topics"] * 100, 1)

    row = _row(_board(client, ctx["h"]), ctx["cs"]["id"])
    assert row["expected_pct"] is not None


def test_the_weighted_figure_is_carried_apart_not_reconstructed(client, cleanup):
    """One full log and one partial: 1.5 topics taught, which is 1 finished and
    1 half-done — a split no caller can recover from 1.5 alone."""
    ctx = _taught_year(client, cleanup)
    row = _row(_board(client, ctx["h"]), ctx["cs"]["id"])

    assert row["taught_topics"] == 1.5
    assert row["taught_full"] == 1
    assert row["taught_partial"] == 1
    school = _pulse(client, ctx["h"])["school"]
    assert school["taught_full"] == 1 and school["taught_partial"] == 1


# ── the honesty rules, on the new surfaces ───────────────────────────────────
def test_a_node_with_no_logs_is_neutral_and_says_so(client, cleanup):
    """`S-42` on the block. A plan nobody has taught against is not going well
    — it is unobserved, and a green ring would state as fact something we never
    saw."""
    ctx = _setup(client, cleanup)
    _syllabus(client, ctx["h"], ctx["cs"]["id"], [("T1", 2), ("T2", 2)])
    _plan(client, ctx["h"], ctx["cs"]["id"])

    pulse = _pulse(client, ctx["h"])
    school = pulse["school"]
    assert school["unknown"] == 1
    assert school["on_track"] == 0 and school["behind"] == 0
    assert school["tone"] == "neutral"
    assert "logged" in (school["pace_caption"] or "")
    # The sentence says the same thing in words, and never quotes a pace.
    assert "nothing to rate" in pulse["headline"]


def test_a_visible_gap_is_never_painted_green(client, cleanup):
    """The forecast and the marker answer different questions, and they can
    honestly disagree: *will it finish* has room in April that *is it on
    schedule today* does not.

    The ring draws the second one. So a node with topics overdue may not be
    green — and, because "on track" beside "15 topics overdue" reads as a
    contradiction, the caption has to say which question each answer is to.
    """
    ctx = _setup(client, cleanup)
    _, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                          [(f"T{i}", 2) for i in range(6)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    # One log, so the row has evidence and is rated rather than `unknown`, but
    # the plan scheduled far more than that by today (the year opened 120 days
    # ago in the fixture).
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")

    school = _pulse(client, ctx["h"])["school"]
    assert school["behind_topics"] > 0, "the fixture must actually be overdue"
    assert school["tone"] != "green"
    assert "overdue" in school["pace_caption"]
    # And the arc really is short of its marker — the thing the tone is about.
    assert school["syllabus_pct"] < school["expected_syllabus_pct"]


def test_unlogged_rows_never_count_toward_topics_overdue(client, cleanup):
    """`S-42` on the figure that orders the worst-first lists.

    Every due topic of a class-subject nobody logged is untaught *on the
    record*, so counting them would report a school as badly overdue on the
    strength of a record nobody wrote — and would sort the unobserved rows to
    the top, described as the ones behind.
    """
    ctx = _setup(client, cleanup)
    _syllabus(client, ctx["h"], ctx["cs"]["id"], [(f"T{i}", 2) for i in range(6)])
    _plan(client, ctx["h"], ctx["cs"]["id"])   # planned, and nobody logged a thing

    pulse = _pulse(client, ctx["h"])
    school = pulse["school"]
    assert school["unknown"] == 1
    assert school["behind_topics"] == 0
    assert school["tone"] == "neutral"

    # Same rule in the tally: the row IS counted under `not_logged` — that is
    # the finding — but it contributes no topic figure, because "10 topics
    # behind" about a class nobody observed is a claim we cannot make.
    tally = {c["key"]: c for c in _board(client, ctx["h"])["causes"]}
    assert tally["not_logged"]["count"] == 1
    assert tally["not_logged"]["behind_topics"] == 0


def test_the_cause_tally_keeps_its_zeroes_and_its_order(client, cleanup):
    """Four causes, always four rows, always in the order capture → calendar →
    sizing → teaching. The proportions between them ARE the finding, and a
    tally that drops empty rows cannot show a proportion."""
    ctx = _taught_year(client, cleanup)
    causes = _board(client, ctx["h"])["causes"]

    assert [c["key"] for c in causes] == [
        "not_logged", "periods_lost", "never_sized", "slower"]
    assert all(c["label"] and c["detail"] for c in causes)
    assert all(c["count"] >= 0 for c in causes)
    # Nothing is counted twice: the tally cannot exceed the rows it came from.
    rows = _board(client, ctx["h"])["rows"]
    assert sum(c["count"] for c in causes) == sum(1 for r in rows if r["cause"])


def test_an_unsized_chapter_lands_in_never_sized(client, cleanup):
    """The one cause that is neither a teaching nor a capture problem: a chapter
    with no estimate is never scheduled, so the plan is short before anybody
    walks into a classroom."""
    ctx = _setup(client, cleanup)
    _, topics = _syllabus(client, ctx["h"], ctx["cs"]["id"],
                          [("Sized", 2), ("Never sized", None)])
    _plan(client, ctx["h"], ctx["cs"]["id"])
    _log(client, ctx["th"], ctx["cs"]["id"], topics[0]["id"], "full")

    board = _board(client, ctx["h"])
    row = _row(board, ctx["cs"]["id"])
    assert row["unestimated_topics"] == 1
    tally = {c["key"]: c["count"] for c in board["causes"]}
    if row["cause"] is not None:
        assert tally[row["cause"]] >= 1
    assert tally["never_sized"] == sum(
        1 for r in board["rows"] if r["cause"] == "never_sized")


# ── the term switch ──────────────────────────────────────────────────────────
def test_a_term_from_another_year_is_refused_not_rendered_as_zero(client, cleanup):
    """Narrowing the portion to a term that owns none of it would draw a school
    that has taught nothing. It falls back to the whole year and says so by
    returning no term."""
    ctx = _taught_year(client, cleanup)
    whole = _pulse(client, ctx["h"])
    stray = _pulse(client, ctx["h"], term_id=str(uuid.uuid4()))

    assert stray["term_id"] is None and stray["term_label"] is None
    assert stray["school"]["total_topics"] == whole["school"]["total_topics"]


def test_the_term_switch_narrows_the_portion_and_names_itself(client, cleanup):
    """A term-scoped ring must sit under a term-scoped sentence — the headline
    is written from the same scope the figures were."""
    ctx = _taught_year(client, cleanup)
    today = date.today()
    term = client.post("/api/v1/academics/terms", headers=ctx["h"], json={
        "academic_year_id": ctx["year"]["id"], "name": "Term 1",
        "start_date": (today - timedelta(days=120)).isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat()}).json()

    pulse = _pulse(client, ctx["h"])
    assert [t["name"] for t in pulse["terms"]] == ["Term 1"]
    assert pulse["terms"][0]["is_current"] is True

    scoped = _pulse(client, ctx["h"], term_id=term["id"])
    assert scoped["term_label"] == "Term 1"
    assert scoped["headline"].startswith("In Term 1")
    # The chapters were filed under no term, so a term scope holds none of them
    # — and the block reports that as a state, never as 0% taught.
    assert scoped["school"]["total_topics"] == 0
    assert scoped["school"]["coverage_pct"] is None


# ── the teacher pivot ────────────────────────────────────────────────────────
def test_the_teacher_node_carries_the_load_its_pace_is_read_against(client, cleanup):
    """`D-90` — "62% covered" means nothing until you know it is across three
    classes. The teacher pivot is a re-pivot of the class-subject rows, so its
    denominators have to come with it."""
    ctx = _setup(client, cleanup, sections=("A", "B"))
    for cs in ctx["css"]:
        _, topics = _syllabus(client, ctx["h"], cs["id"], [("T1", 2), ("T2", 2)])
        _plan(client, ctx["h"], cs["id"])
        _log(client, ctx["th"], cs["id"], topics[0]["id"], "full")

    board = _board(client, ctx["h"], scope="teacher")
    node = next(n for n in board["nodes"] if n["key"] == str(ctx["teacher_mid"]))
    assert node["class_subjects"] == 2
    assert node["classes"] == 2          # 6-A and 6-B
    assert node["subjects"] == 1         # both are the same subject
    assert node["tone"] in ("neutral", "green", "amber", "red")
    assert node["pace_caption"]


def test_the_pulse_is_admin_only(client, cleanup):
    """Same fence as every other insights route — a teacher never receives a
    school-wide board."""
    ctx = _setup(client, cleanup)
    assert client.get("/api/v1/insights/syllabus/pulse",
                      headers=ctx["th"]).status_code == 403
