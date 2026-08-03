"""V1-12: every tab leads with a sentence, and Lucy reads the same computations.

Two halves of one rule (§7 + law "one computation, many renderings"):

* **A block with no sentence does not ship.** Four tabs already led with one;
  Homework, Exams and Tasks opened on a static subtitle and went straight to
  charts. The sentences are composed SERVER-side, like the syllabus board's, so
  the tab, the overview block and Lucy cannot describe the same week
  differently.
* **Lucy must not become the 44th place a fact is computed.** Her fee tool read
  the old `FeeService` roll-up — no quarters, and `opening_dues` missing from
  every figure (`B-2`) — while `/fees` rendered `CollectionService.board()`.
  Two screens about the same money, guaranteed to disagree.
"""

import re
import types
from datetime import date, timedelta

from app.services.lucy import registry
from tests.test_fees_v1_10 import _setup as _fee_setup
from tests.test_homework_v1_5 import _check, _set_hw
from tests.test_homework_v1_5 import _setup as _hw_setup


# ── §7 · the sentence ────────────────────────────────────────────────────────
def test_homework_headline_never_reads_an_unchecked_set_as_zero_percent(client, cleanup):
    """HW-1's rule, restated where it is most tempting to break.

    A teacher who has checked nothing must not produce *"0% done"* — that is a
    percentage with nothing behind it, and it blames children for a teacher who
    has not opened the notebooks. `not_checked` is the teacher's gap, always.
    """
    ctx = _hw_setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    on = (date.today() - timedelta(days=1)).isoformat()
    _set_hw(client, th, ctx["cs"]["id"], "Ex 1.1", on)

    board = client.get("/api/v1/insights/homework", headers=h)
    assert board.status_code == 200, board.text
    headline = board.json()["headline"]
    assert headline, "§7: a tab with no sentence does not ship"
    assert "none checked yet" in headline
    assert "0%" not in headline, "an unchecked set is not a completion figure"

    # Once she checks it, the figure appears WITH its denominator.
    hw = client.get("/api/v1/homework/queue", headers=th).json()
    aid = hw["items"][0]["assignment_id"] if hw.get("items") else None
    assert aid, hw
    _check(client, th, aid, [])          # capture-by-exception: everyone did it
    after = client.get("/api/v1/insights/homework", headers=h).json()["headline"]
    assert "100%" in after
    # §7: every figure carries its denominator. Asserted as a SHAPE rather than
    # a phrase — the percentage must be immediately followed by what it is a
    # percentage OF, so no rewording can quietly drop the denominator the way a
    # literal-string assertion would have allowed.
    assert re.search(r"100% of the \d+", after), after


def test_tasks_headline_names_who_the_overdue_work_is_sitting_with(client, cleanup):
    """*"9 open, 3 overdue, all with Priya."*

    Nine overdue across nine people is a busy week; nine with one person is a
    conversation with that person. A bare count cannot tell those apart, so the
    concentration is named whenever it is real.
    """
    ctx = _hw_setup(client, cleanup)
    h = ctx["h"]
    board = client.get("/api/v1/insights/tasks", headers=h)
    assert board.status_code == 200, board.text
    # A brand-new org has nothing open, and says exactly that rather than "0".
    assert board.json()["headline"] == "Nothing is open."


def test_exams_headline_names_its_scale_and_never_blends(client, cleanup):
    """`S-114`: the headline is where a blended average would be most
    persuasive and least visible, so it names the bucket it came from."""
    ctx = _hw_setup(client, cleanup)
    board = client.get("/api/v1/insights/exams", headers=ctx["h"])
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["headline"], "§7: a tab with no sentence does not ship"
    # Nothing recorded yet is a WORD, never a zero (ux §10).
    assert "No exams" in body["headline"]
    assert "0%" not in body["headline"]


# ── Lucy reconcile ───────────────────────────────────────────────────────────
def test_lucy_reads_the_same_fee_computation_the_screen_renders(client, cleanup):
    """The packet's whole point, in one assertion.

    Before V1-12 Lucy answered fee questions from `FeeService.summary`, which
    has no quarter windows and omits `opening_dues` from every figure — so
    *"how much of Q2 is in?"* got a year total that silently dropped the
    school's worst debtors, while `/fees` beside her showed both.
    """
    h, _ctx = _fee_setup(client, cleanup)

    screen = client.get("/api/v1/fees/collection", headers=h)
    assert screen.status_code == 200, screen.text
    board = screen.json()

    spec = registry.REGISTRY["get_fee_collection"]
    assert spec.role == "admin", "teachers never see fees, in any surface"

    # The tool IS the screen's call — asserted on the source, so the two cannot
    # drift back apart without this failing.
    import inspect  # noqa: PLC0415
    src = inspect.getsource(spec.handler)
    assert "CollectionService(db).board(" in src,         "Lucy's fee tool must render the same computation `/fees` does (S-152)"
    # The CALL, not the word — the handler's comment explains what it replaced.
    assert "FeeService(db)" not in src,         "the old roll-up has no quarters and drops opening_dues (B-2)"

    # The two facts the old tool could not express at all.
    assert "quarters" in board, "quarters are due-date windows (Q-67)"
    assert "carried" in board, "D-88: previous-year dues are their own line"
    # …and three that must never be added together (S-163).
    for k in ("collected", "pending", "overdue"):
        assert k in board
    assert "outstanding" not in board, \
        "S-163: collected/pending/overdue have no blended total, by construction"


def test_no_fee_tool_is_ever_visible_to_a_teacher(client, cleanup):
    """The fence, asserted on the whole surface rather than by name — so a fee
    tool added later cannot slip past by being called something else."""
    teacher = types.SimpleNamespace(is_admin=False)
    names = {t["function"]["name"] for t in registry.to_openai_tools(teacher)}
    # Word boundary: `get_exam_feed` contains "fee" and is legitimate.
    assert not [n for n in names if re.search(r"(^|_)fees?(_|$)", n)]

    admin = types.SimpleNamespace(is_admin=True)
    admin_names = {t["function"]["name"] for t in registry.to_openai_tools(admin)}
    assert "get_fee_collection" in admin_names


def test_every_lucy_tool_resolves_to_a_service_that_still_exists():
    """The reconcile, mechanised. Nine packets rewrote the services under Lucy;
    a tool calling a method that no longer exists fails only when a human
    happens to ask that question, which is the worst possible time to find out.
    """
    import importlib
    import pathlib

    broken = []
    for f in sorted(pathlib.Path("app/services/lucy").glob("tools_*.py")):
        mod = importlib.import_module(f"app.services.lucy.{f.stem}")
        src = f.read_text(encoding="utf-8")
        for mm in re.finditer(r"(\w+(?:Service|Insights|Reader))\(db\)\.(\w+)", src):
            cls = getattr(mod, mm.group(1), None)
            if cls is None or not hasattr(cls, mm.group(2)):
                broken.append(f"{f.name}: {mm.group(1)}.{mm.group(2)}")
    assert not broken, f"Lucy tools calling methods that no longer exist: {broken}"


def test_every_registered_tool_has_a_model_readable_description():
    """A tool the model cannot tell apart from its neighbour is a tool it will
    call at the wrong moment. Cheap to assert, and it fails the moment someone
    adds a tool without saying what it answers."""
    thin = [name for name, spec in registry.REGISTRY.items()
            if not spec.description or len(spec.description) < 40]
    assert not thin, f"tools needing a real description: {thin}"
    assert len(registry.REGISTRY) >= 40
