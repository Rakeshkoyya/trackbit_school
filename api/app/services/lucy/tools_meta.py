"""The discovery tools — how a model finds its way around ~170 tools (`D-98`).

MCP-SERVER-PLAN §5.2. The credential's toolsets are the *primary* answer to the
size problem (a default connector sees ~60 tools, not the whole pool); these
three are how the model orients itself inside whatever it was given, and how it
narrows by domain -> tool -> schema instead of carrying every schema on every
turn.

They describe the **caller's own surface**, never the registry's: a tool this
member's role or credential does not reach is absent from these listings and
`describe_tool` reports it as unknown. That is deliberate — an out-of-scope tool
the model can see the name of is an out-of-scope tool the model will ask about.

Reads nothing but the registry, so `D-95` holds trivially here.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import AppError
from app.services.lucy import domains
from app.services.lucy.registry import (
    REGISTRY,
    ToolSpec,
    current_scope,
    tool,
    visible_tools,
)

# A placeholder per JSON-Schema shape, for the worked example in describe_tool.
# Deliberately unusable as-is: the model must resolve a real id (never guess
# one), and a template that looks like real data invites it to send the
# template.
_EXAMPLE: dict[str, Any] = {
    "uuid": "<uuid — resolve it first, never invent one>",
    "date": "2026-03-14",
    "string": "<text>",
    "integer": 3,
    "number": 1.5,
    "boolean": True,
    "array": [],
    "object": {},
}


def _my_tools(m: CurrentMember) -> list[ToolSpec]:
    """Everything this caller can actually reach, role and scope applied."""
    sc = current_scope()
    return visible_tools(m, scope=sc.domains, tier=sc.tier)


def _one_line(spec: ToolSpec, limit: int = 140) -> str:
    """The first sentence of a description — enough to choose between two
    tools, short enough that listing 30 of them is cheap."""
    text = " ".join(spec.description.split())
    cut = text.find(". ")
    if cut != -1:
        text = text[: cut + 1]
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _example_args(spec: ToolSpec) -> dict[str, Any]:
    props = spec.params_schema["properties"]
    out: dict[str, Any] = {}
    for pname in spec.params_schema["required"]:
        ps = props.get(pname, {})
        fmt = ps.get("format")
        key = fmt if fmt in _EXAMPLE else ps.get("type", "string")
        out[pname] = _EXAMPLE.get(key, "<value>")
    return out


@tool("list_domains",
      "The toolsets available on this connection, one line each, with how many "
      "tools each holds. Start here when you do not know which tool answers a "
      "question — pick a domain, then call list_tools on it.",
      domain="core", widgets=("table",))
def list_domains(m: CurrentMember, db: Session):
    counts: dict[str, int] = {}
    for spec in _my_tools(m):
        counts[spec.domain] = counts.get(spec.domain, 0) + 1
    return [{
        "domain": d.name,
        "summary": d.summary,
        "tools": counts[d.name],
        "always_on": d.always_on,
    } for d in domains.DOMAINS if counts.get(d.name)]


@tool("list_tools",
      "The tools in one domain: name, what it answers, and whether it reads or "
      "writes. Call describe_tool before using an unfamiliar one — this listing "
      "gives you the choice, not the arguments.",
      {"domain": {"type": "string", "required": True,
                  "description": "a domain name from list_domains"}},
      domain="core", widgets=("table",))
def list_tools(m: CurrentMember, db: Session, domain: str):
    mine = _my_tools(m)
    known = {s.domain for s in mine}
    if domain not in known:
        # Unknown and out-of-scope read the same on purpose (rule 3).
        # AppError, not NotFoundError: the latter appends " not found" to its
        # argument, which would mangle a message whose value is the list.
        raise AppError(
            f"no domain {domain!r} on this connection — "
            f"available: {', '.join(sorted(known))}", code="not_found")
    return [{
        "tool": s.name,
        "answers": _one_line(s),
        "kind": s.kind,
        "needs_approval": s.confirm,
    } for s in mine if s.domain == domain]


@tool("describe_tool",
      "One tool in full: its complete description, its JSON input schema, and a "
      "worked example call. Read this before calling a tool you have not used, "
      "rather than guessing an argument name.",
      {"name": {"type": "string", "required": True,
                "description": "a tool name from list_tools"}},
      domain="core", widgets=("stat_group", "table"),
      default_widget="stat_group")
def describe_tool(m: CurrentMember, db: Session, name: str):
    spec = next((s for s in _my_tools(m) if s.name == name), None)
    if spec is None:
        hint = "" if name in REGISTRY else " (no tool by that name)"
        raise AppError(f"no tool {name!r} on this connection{hint}",
                       code="not_found")
    return {
        "tool": spec.name,
        "domain": spec.domain,
        "description": " ".join(spec.description.split()),
        "kind": spec.kind,
        "needs_approval": spec.confirm,
        "input_schema": spec.params_schema,
        "example": {"name": spec.name, "arguments": _example_args(spec)},
    }
