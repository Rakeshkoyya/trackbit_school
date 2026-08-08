"""`school://manual` — the agent's orientation document, generated (§5.3).

Generated from the registry rather than written, so it cannot drift from the
tools it describes. A client that supports MCP resources attaches this once and
skips most discovery calls; a client that does not is unaffected, because
`tools_meta` answers the same questions three cheap calls at a time.

It carries the two things a tool list alone cannot teach a model:

- **the id-resolution order** — never guess an id, resolve it;
- **the vocabulary** — the `core/` modules each own one computation, and a
  number that disagrees with them is wrong even when it looks right.

Deliberately no per-school data: this is the *shape* of the product, and it is
identical for every org. Anything school-specific is a tool call.
"""

from app.core.context import CurrentMember
from app.services.lucy import domains
from app.services.lucy.registry import ToolSpec, visible_tools

# What each core/ module owns. Straight from CLAUDE.md's vocabulary table —
# the most-repeated defect in this codebase is the same fact computed two ways,
# and a model re-deriving a percentage from rows is that defect with a new
# author.
_VOCABULARY: tuple[tuple[str, str], ...] = (
    ("coverage", "\"syllabus covered\" — every coverage figure carries the "
                 "denominator it was computed against"),
    ("exams", "minor vs major tests; scores on different scales never pool "
              "into one blended number"),
    ("homework_verdict", "done / late / carried / waived / not_checked, and "
                         "what each is worth"),
    ("bands", "the A/B/C support vocabulary — private intervention tiers, "
              "never labels, never shown to a parent"),
    ("collection", "fee quarters as due-date windows; collected, pending and "
                   "overdue are three facts with no valid total"),
    ("visibility", "who may see a board"),
)

_PRINCIPLES = """\
- **Not-captured is a word, never a zero.** An unmarked register, an unchecked
  homework set and an unassessed child are *states*. Reporting any of them as
  0% blames a person for a gap in the record — usually the wrong person. Say
  "not marked", not "0%".
- **A figure carries its denominator.** "61% across 5 of the 9 tests", never a
  bare "61%".
- **Bands are private.** A/B/C tiers are staff-only and per subject — there is
  no overall letter for a child.
- **Teachers never see fees.** If the fee tools are absent from your list, that
  is the answer, not an obstacle to route around.
- **You see only what this connection was granted.** A tool that is not in your
  list is not available to you; there is no argument that unlocks it."""

_RESOLUTION = """\
**Never invent an id.** Every id-shaped argument is resolved by a call first:

1. `get_school_structure` — years, terms, classes and subjects with their ids.
   This is the first call of almost every task.
2. `get_class_subjects(class_id)` — the class-subject ids, which are what the
   planning, syllabus and lesson-log tools take (a *class-subject* is one
   subject taught to one class, not a subject).
3. `search_students(query)` — resolve a child named by a human to a student id.
4. Feed-shaped tools (`get_exam_feed`, `list_task_boards`, ...) return the ids
   their detail tools consume.

Dates are ISO `YYYY-MM-DD` and mean the school's local calendar day."""


def _tool_line(spec: ToolSpec) -> str:
    text = " ".join(spec.description.split())
    cut = text.find(". ")
    if cut != -1:
        text = text[: cut + 1]
    marks = []
    if spec.kind == "write":
        marks.append("write")
    if spec.confirm:
        marks.append("needs approval")
    if spec.role == "admin":
        marks.append("admin")
    suffix = f" *({', '.join(marks)})*" if marks else ""
    return f"- `{spec.name}`{suffix} — {text}"


def build_manual(m: CurrentMember, *,
                 scope: set[str] | frozenset[str] | None = None,
                 tier: str | None = None) -> str:
    """The manual for one caller, listing exactly the tools they can reach."""
    specs = visible_tools(m, scope=scope, tier=tier)
    by_domain: dict[str, list[ToolSpec]] = {}
    for spec in specs:
        by_domain.setdefault(spec.domain, []).append(spec)

    out: list[str] = [
        "# TrackBit School — agent manual",
        "",
        "TrackBit School is a school's daily operating system: it plans the "
        "academic year down to the period, captures each day with near-zero "
        "teacher effort, and writes the school's daily report itself. You are "
        "acting through a staff member's own authority — every tool sees "
        "exactly what that person would see on screen, and nothing more.",
        "",
        "## Resolving ids",
        "",
        _RESOLUTION,
        "",
        "## How numbers work here",
        "",
        _PRINCIPLES,
        "",
        "The server computes every figure. Do not re-derive one from rows — "
        "each of these owns exactly one definition, and a second definition is "
        "a defect even when the arithmetic is right:",
        "",
    ]
    out += [f"- **{name}** — {owns}" for name, owns in _VOCABULARY]
    out += [
        "",
        "## Writing",
        "",
        "Some tools change the school's record. Those marked *needs approval* "
        "do not apply when you call them: they propose the change for a human "
        "with the authority to make it by hand, who approves or rejects it. "
        "Everything else applies immediately and is corrected by a further "
        "call, never by deletion — this record is append-only.",
        "",
        f"## Your tools ({len(specs)} across {len(by_domain)} toolsets)",
        "",
    ]
    for d in domains.DOMAINS:
        group = by_domain.get(d.name)
        if not group:
            continue
        out += [f"### `{d.name}`", "", d.summary, ""]
        out += [_tool_line(s) for s in group]
        out.append("")
    out += [
        "Toolsets absent from this list were not granted to this connection.",
        "Use `list_domains`, `list_tools` and `describe_tool` to navigate, and "
        "`describe_tool` before calling anything unfamiliar.",
        "",
    ]
    return "\n".join(out)
