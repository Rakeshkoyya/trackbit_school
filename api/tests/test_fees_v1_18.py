"""V1-18 — fees against the calendar: "are we where we should be by now?"

The module could say how much came in and could not say whether that was good.
45% is excellent in May and alarming in February, and every fee figure in the
product was printed without the date that makes it readable. `due_by_today` is
the missing denominator, and these tests pin down what it is and — more
importantly — what it is NOT.

Three things defended here:

  * **`due_by_today` is not `overdue`.** Overdue is the *unpaid* part of what
    was due; `due_by_today` is all of it, paid or not. Confusing them makes a
    school that collected every rupee on time look like it was never asked for
    anything.

  * **A quarter that has not come due is neutral and says so.** It has not been
    missed. This is the one rule the board would most easily break, because
    "0% collected" is technically true of next January all year long.

  * **Money paid early is not money owed.** `shortfall` is
    `max(0, due_by_today − collected)`, so a school that is ahead is not
    reported as negatively behind.

And the identity that falls out of the arithmetic, worth stating once because
it is the reason the pace figure adds something the old board could not:

    shortfall = overdue − prepayments

With nobody paying early the two agree exactly. With prepayments the school is
*less* behind than its overdue figure alone suggests — which the old four-figure
line had no way to express.
"""

import uuid
from datetime import date, timedelta

from app.core.collection import Collection, pace_tone
from tests.test_fees_v1_10 import _setup


def _board(client, h, **params):
    r = client.get("/api/v1/fees/collection", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ── the vocabulary, pure ─────────────────────────────────────────────────────
def test_due_by_today_is_not_overdue():
    """The distinction the whole packet rests on."""
    c = Collection()
    # An instalment due last month, paid on time.
    c.add(billed=10000, collected=10000, due_by_today=10000)
    # One due last month and NOT paid.
    c.add(billed=10000, overdue=10000, due_by_today=10000)
    # One due next term — billed, but nobody has been asked for it yet.
    c.add(billed=10000, pending=10000)

    assert c.billed == 30000
    assert c.due_by_today == 20000, "both past instalments, paid or not"
    assert c.overdue == 10000, "only the unpaid one"
    assert c.collected == 10000
    assert c.shortfall == 10000
    # The identity: with no prepayments, shortfall IS overdue.
    assert c.shortfall == c.overdue

    assert c.pct == round(10000 / 30000 * 100, 1)
    assert c.due_pct == round(20000 / 30000 * 100, 1)


def test_paying_early_is_never_reported_as_being_behind():
    """`shortfall` floors at zero, and the identity bends the right way: money
    in ahead of the date means the school is less behind than `overdue` alone
    would say."""
    c = Collection()
    c.add(billed=10000, overdue=10000, due_by_today=10000)   # due, unpaid
    c.add(billed=10000, collected=10000)                     # not due, paid early

    assert c.collected == 10000
    assert c.due_by_today == 10000
    assert c.shortfall == 0, "level once the early payment is counted"
    # shortfall = overdue − prepaid  →  0 = 10000 − 10000
    assert c.shortfall == c.overdue - 10000
    assert pace_tone(c) == "green"


def test_a_scope_with_nothing_due_is_neutral_and_never_a_score():
    """ux §5 / §10 pointed at money. Next January is not 0% collected in
    August; it has not been asked for."""
    future = Collection()
    future.add(billed=50000, pending=50000)        # billed, none of it due yet
    assert future.due_by_today == 0
    assert future.due_pct == 0
    assert future.shortfall == 0
    assert pace_tone(future) == "neutral", "a future quarter is not a red one"

    nothing = Collection()
    assert nothing.pct is None, "nothing billed is not 0% collected"
    assert pace_tone(nothing) == "neutral"


def test_tone_thresholds_are_measured_against_what_was_asked_for():
    """Not against what was billed — that is the whole point. A school 100% of
    the way through what it asked for is green even at 25% of the year."""
    level = Collection(); level.add(billed=100000, collected=25000, due_by_today=25000)
    assert level.pct == 25.0
    assert pace_tone(level) == "green", "25% of the year, and every rupee asked for is in"

    slipping = Collection(); slipping.add(billed=100000, collected=23000, due_by_today=25000)
    assert pace_tone(slipping) == "amber"

    behind = Collection(); behind.add(billed=100000, collected=10000, due_by_today=25000)
    assert pace_tone(behind) == "red"


# ── the board ────────────────────────────────────────────────────────────────
def test_the_year_rollup_reconciles_with_its_own_quarters(client, cleanup):
    """The year figure is accumulated in the same pass as the quarter rows, so
    it cannot drift from them. Before this it did not exist at all, and the
    dashboard summed quarter rows in the browser — adding `pending` to
    `overdue` on the way, which is the blend `Collection` has no `outstanding`
    property in order to prevent (`S-163`).
    """
    h, _ = _setup(client, cleanup)
    b = _board(client, h)
    y = b["year"]

    assert y["billed"] == sum(q["billed"] for q in b["quarters"]) + b["unscheduled_billed"]
    assert y["collected"] == sum(q["collected"] for q in b["quarters"])
    assert y["due_by_today"] == sum(q["due_by_today"] for q in b["quarters"])
    # The three the board leads with nest on one denominator.
    assert y["billed"] >= y["due_by_today"]
    assert y["due_pct"] is not None and 0 <= y["due_pct"] <= 100


def test_a_paid_past_instalment_still_counts_as_asked_for(client, cleanup):
    """The fixture's first instalment is 90 days past its due date and one
    family paid it. It must be inside `due_by_today` and outside `overdue` —
    if `due_by_today` were derived from `overdue`, that payment would vanish
    from the denominator and the school would read as ahead of a schedule it
    was never measured against."""
    h, _ = _setup(client, cleanup)
    y = _board(client, h)["year"]

    assert y["collected"] > 0, "the fixture pays one instalment"
    assert y["due_by_today"] >= y["collected"], (
        "everything collected here was against an instalment already due")
    # Money in, and money still owed, both sit inside what was asked for.
    assert y["due_by_today"] >= y["overdue"]
    assert y["shortfall"] == max(0.0, y["due_by_today"] - y["collected"])


def test_a_future_quarter_on_the_board_is_neutral_not_zero(client, cleanup):
    """End to end: the fixture's second instalment is ~80 days out, so its
    quarter is billed but nothing in it is due."""
    h, _ = _setup(client, cleanup)
    b = _board(client, h)

    future = [q for q in b["quarters"] if q["billed"] > 0 and q["due_by_today"] == 0]
    assert future, b["quarters"]
    for q in future:
        assert q["tone"] == "neutral", f"{q['label']} has not been asked for yet"
        assert q["shortfall"] == 0
        assert q["state"] in ("current", "future")

    # And every quarter carries the state a renderer would otherwise have to
    # work out by comparing dates — in whatever timezone the browser is in.
    assert {q["state"] for q in b["quarters"]} <= {"past", "current", "future"}


def test_an_unscheduled_instalment_is_billed_but_never_due(client, cleanup):
    """An instalment with no due date is `unscheduled` — the school has not said
    when it wants the money, so it cannot be late. It belongs in `billed` and
    must never reach `due_by_today`, or a school that simply has not set dates
    would read as massively behind."""
    h, ctx = _setup(client, cleanup)
    sf_id = ctx["fees"]["Diya Nair"]["id"]
    r = client.post("/api/v1/fees/student-fees", headers=h, json={
        "student_id": ctx["kids"][1]["id"], "academic_year_id": ctx["year"]["id"],
        "total_fee": 5000, "discount": 0,
        "installments": [{"installment_number": 9, "label": "No date", "amount": 5000}],
    })
    # The student already has a fee row for this year (unique per year), so the
    # enrolment is refused — set the due date to NULL on an existing one instead.
    if r.status_code != 200:
        detail = client.get(f"/api/v1/fees/student-fees/{sf_id}", headers=h).json()
        inst = detail["installments"][-1]
        cleared = client.patch(f"/api/v1/fees/installments/{inst['id']}/due-date",
                               headers=h, json={"due_date": None})
        assert cleared.status_code == 200, cleared.text

    b = _board(client, h)
    assert b["unscheduled_billed"] > 0, b["unscheduled_note"]
    assert b["unscheduled_note"], "a word on the screen, never a silent bucket"
    y = b["year"]
    # It is in the year's billed total but not in what has been asked for.
    assert y["billed"] >= b["unscheduled_billed"]
    assert y["due_by_today"] == sum(q["due_by_today"] for q in b["quarters"]), (
        "unscheduled money must not leak into the schedule")


def test_the_quarter_figures_do_not_change_when_a_quarter_is_picked(client, cleanup):
    """The board's TOP-LEVEL figures are the picked quarter's — that is the
    trap `year` exists to remove. The per-quarter rows and the year roll-up must
    stay the same whichever quarter is in focus, or the rings would rearrange
    themselves every time somebody tapped one."""
    h, _ = _setup(client, cleanup)
    base = _board(client, h)
    labels = [q["label"] for q in base["quarters"]]

    for label in labels:
        scoped = _board(client, h, quarter=label)
        assert scoped["year"] == base["year"], "the year does not depend on the focus"
        assert scoped["quarters"] == base["quarters"], "nor do the quarter rings"
        # …while the top-level figures deliberately DO follow the picked quarter.
        picked = next(q for q in scoped["quarters"] if q["label"] == label)
        assert scoped["billed"] == picked["billed"]
        assert scoped["collected"] == picked["collected"]


def test_fee_pace_never_reaches_a_teacher(client, cleanup):
    """The fence, re-asserted at the new field. `due_by_today` is fee data like
    any other and the collection route stays admin-only."""
    h, _ = _setup(client, cleanup)
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(cred["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": cred["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    assert client.get("/api/v1/fees/collection", headers=th).status_code == 403
    assert client.get("/api/v1/fees/summary", headers=th).status_code == 403


def test_quarter_windows_cover_the_year_without_gaps(client, cleanup):
    """The rings tile the year. A gap between two windows would be money in no
    quarter that is also not `unscheduled` — invisible on every surface."""
    h, _ = _setup(client, cleanup)
    b = _board(client, h)
    qs = b["quarters"]
    assert len(qs) >= 2
    for a, nxt in zip(qs, qs[1:], strict=False):
        assert date.fromisoformat(nxt["start"]) == date.fromisoformat(a["end"]) + timedelta(days=1), (
            f"{a['label']} ends {a['end']} but {nxt['label']} starts {nxt['start']}")
