"""Phase 1 of the agent platform: domains, scope, discovery, the manual.

The load-bearing assertion in this file is `test_no_tool_module_touches_the_database`
(`D-95`). Every scoping guard that matters — `assert_can_take_class`,
`not_your_student`, the fee fence — lives in a *service*. A tool that calls the
service inherits all of it; a tool that writes its own query inherits none of
it, and no amount of review catches that reliably once the pool is ~170 tools.

Everything here is a unit test over the in-memory registry: no database, no
fixtures, so it runs in milliseconds and cannot be skipped by a DB problem.
"""

import ast
import pathlib
import re
import types

import pytest

import app.services.lucy  # noqa: F401  — importing registers every tool
from app.services.lucy import domains, manual
from app.services.lucy.registry import REGISTRY, execute, tool, visible_tools

TEACHER = types.SimpleNamespace(is_admin=False)
ADMIN = types.SimpleNamespace(is_admin=True)

LUCY = pathlib.Path("app/services/lucy")


# --- domains ------------------------------------------------------------------

def test_every_registered_tool_declares_a_real_domain():
    """A tool with no toolset is unreachable through any scoped credential —
    it would be invisible to every connector and nobody would notice."""
    bad = {n: s.domain for n, s in REGISTRY.items()
           if s.domain not in domains.DOMAIN_NAMES}
    assert not bad, f"tools with an unknown domain: {bad}"


def test_a_tool_cannot_be_registered_without_a_valid_domain():
    with pytest.raises(TypeError):  # domain is keyword-only and required
        tool("x", "y")
    with pytest.raises(ValueError, match="unknown domain"):
        tool("x", "y", domain="not_a_toolset")


def test_resolve_scope_always_folds_in_core():
    """`core` carries the discovery tools and every id-resolution tool. A scope
    without it is a scope the model cannot navigate out of."""
    assert "core" in domains.resolve_scope({"tasks"})
    assert domains.resolve_scope(None) is None, "None means unscoped, not empty"
    with pytest.raises(ValueError, match="unknown toolset"):
        domains.resolve_scope({"payroll"})


def test_fees_and_bands_are_not_in_the_default_scope():
    """Both need a separately-worded opt-in when a credential is issued."""
    assert "fees" not in domains.DEFAULT_SCOPE
    assert "bands" not in domains.DEFAULT_SCOPE


# --- the filter: role -> scope -> tier ----------------------------------------

def test_scope_makes_a_tool_absent_rather_than_refused():
    """Rule 3: filtering happens at schema time. There is no error to provoke
    and nothing to jailbreak — the tool simply is not there."""
    unscoped = {s.name for s in visible_tools(ADMIN)}
    scoped = {s.name for s in visible_tools(ADMIN, scope={"tasks"})}
    assert "get_fee_collection" in unscoped
    assert "get_fee_collection" not in scoped
    assert "create_task" in scoped
    assert scoped < unscoped


def test_scope_can_only_narrow_never_widen():
    """A connector is issued by a member and can never exceed that member.
    Asking for `fees` as a teacher grants nothing — role is applied first."""
    everything = set(domains.DOMAIN_NAMES)
    teacher_all = {s.name for s in visible_tools(TEACHER, scope=everything)}
    admin_all = {s.name for s in visible_tools(ADMIN, scope=everything)}
    assert not [n for n in teacher_all if re.search(r"(^|_)fees?(_|$)", n)], \
        "no fee tool may reach a teacher through any scope, whatever it is named"
    assert "get_school_overview" not in teacher_all
    assert teacher_all < admin_all


def test_tier_is_the_third_filter_and_gates_nothing_today():
    """Package tiers are not built — `core/plans.py` is still Free/Pro and knows
    nothing about school features (FEATURE-MAP 9.6). The *seam* is real and
    ordered after role and scope; the mapping is empty, which is the truth."""
    from app.services.lucy import registry

    assert registry.TIER_DOMAINS == {}, \
        "populating this is the package-tiers packet, not this one"
    assert registry.domains_for_tier("platinum") is None
    baseline = {s.name for s in visible_tools(ADMIN, tier="platinum")}
    assert baseline == {s.name for s in visible_tools(ADMIN)}

    # And when a mapping does exist it narrows, after role and scope.
    registry.TIER_DOMAINS["basic"] = frozenset({"core", "attendance"})
    try:
        got = {s.domain for s in visible_tools(ADMIN, tier="basic")}
        assert got == {"core", "attendance"}
        # the intersection of scope and tier, never the union
        both = {s.domain for s in visible_tools(
            ADMIN, scope={"attendance", "tasks"}, tier="basic")}
        assert both == {"core", "attendance"}
    finally:
        registry.TIER_DOMAINS.clear()


def test_struck_tools_leave_mcp_without_leaving_lucy():
    """`D-102`. Three tools shipped in Lucy are struck from the approved MCP
    list. One pool (`D-93`) means the fix is a filter, not a deletion — Lucy
    users must not lose a working feature to a decision about connectors."""
    struck = {"assign_homework", "confirm_check", "add_plan_comment"}
    lucy = {s.name for s in visible_tools(ADMIN, transport="lucy")}
    mcp = {s.name for s in visible_tools(ADMIN, transport="mcp")}
    assert struck <= lucy, "a struck tool must still work in Lucy"
    assert not (struck & mcp), "a struck tool must not reach an MCP client"
    assert mcp == lucy - struck, \
        "nothing else may differ between the two transports"


def test_a_tool_cannot_declare_an_unknown_transport():
    with pytest.raises(ValueError, match="transports"):
        tool("x", "y", domain="core", transports=("carrier_pigeon",))
    with pytest.raises(ValueError, match="transports"):
        tool("x", "y", domain="core", transports=())


def test_lucy_keeps_the_unscoped_surface_it_has_today():
    """Phase 1 is additive. Lucy passes no scope, so it must still see the whole
    pool its role allows — the three discovery tools are the only addition."""
    assert len(visible_tools(ADMIN)) == len(REGISTRY)
    assert {"list_domains", "list_tools", "describe_tool"} <= \
        {s.name for s in visible_tools(TEACHER)}


# --- discovery ----------------------------------------------------------------

def _run(name, member, params=None, scope=None):
    return execute(REGISTRY[name], member, None, params or {}, scope=scope)


def test_list_domains_reports_only_what_this_connection_has():
    ex = _run("list_domains", TEACHER, scope=domains.DEFAULT_SCOPE)
    assert ex.ok, ex.error_message
    listed = {r["domain"]: r["tools"] for r in ex.result.data}
    assert set(listed) <= set(domains.DEFAULT_SCOPE)
    assert "fees" not in listed and "insights" not in listed
    # The counts are the caller's own, not the registry's.
    for name, count in listed.items():
        assert count == len([s for s in visible_tools(
            TEACHER, scope=domains.DEFAULT_SCOPE) if s.domain == name])


def test_list_tools_treats_out_of_scope_and_unknown_alike():
    """An out-of-scope domain must not be distinguishable from a made-up one:
    a differing error message is a directory of what exists elsewhere."""
    denied = _run("list_tools", TEACHER, {"domain": "fees"},
                  scope=domains.DEFAULT_SCOPE)
    missing = _run("list_tools", TEACHER, {"domain": "payroll"},
                   scope=domains.DEFAULT_SCOPE)
    assert denied.ok is False and missing.ok is False
    assert denied.error_code == missing.error_code == "not_found"
    assert "fees" not in missing.error_message

    ok = _run("list_tools", TEACHER, {"domain": "capture"},
              scope=domains.DEFAULT_SCOPE)
    assert ok.ok
    assert {r["tool"] for r in ok.result.data} == {
        s.name for s in visible_tools(TEACHER, scope=domains.DEFAULT_SCOPE)
        if s.domain == "capture"}


def test_describe_tool_hides_what_the_caller_cannot_reach():
    ex = _run("describe_tool", ADMIN, {"name": "get_fee_collection"})
    assert ex.ok and ex.result.data["domain"] == "fees"
    assert ex.result.data["input_schema"]["type"] == "object"

    hidden = _run("describe_tool", TEACHER, {"name": "get_fee_collection"})
    assert hidden.ok is False and hidden.error_code == "not_found"


def test_describe_tool_example_never_invents_an_id():
    """The worked example must not look like real data — a plausible-looking
    uuid in a template is a uuid the model will send."""
    ex = _run("describe_tool", TEACHER, {"name": "get_attendance_roster"})
    args = ex.result.data["example"]["arguments"]
    assert "class_id" in args
    assert args["class_id"].startswith("<"), args["class_id"]


def test_the_scope_does_not_leak_between_calls():
    """The active scope is a contextvar. If it survived a call, the next
    caller's discovery tools would describe the previous caller's surface."""
    _run("list_domains", TEACHER, scope={"tasks"})
    after = _run("list_domains", ADMIN)
    assert {r["domain"] for r in after.result.data} > {"tasks"}


# --- the manual ---------------------------------------------------------------

def test_manual_generates_from_the_registry_and_respects_scope():
    md = manual.build_manual(TEACHER, scope=domains.DEFAULT_SCOPE)
    visible = visible_tools(TEACHER, scope=domains.DEFAULT_SCOPE)
    for spec in visible:
        assert f"`{spec.name}`" in md, f"{spec.name} missing from the manual"
    assert "get_fee_collection" not in md
    assert "get_band_board" not in md
    # The two things a tool list alone cannot teach.
    assert "Never invent an id" in md
    assert "never a zero" in md


def test_manual_marks_writes_and_approvals():
    md = manual.build_manual(ADMIN)
    for line in md.splitlines():
        if line.startswith("- `mark_attendance`"):
            assert "write" in line and "needs approval" in line
            break
    else:
        raise AssertionError("mark_attendance missing from the admin manual")


# --- D-95: tools call services, never tables ----------------------------------

# `Session` is a type annotation on every handler signature and touches nothing;
# these are the names that would mean a tool is querying for itself.
_BANNED_SQLALCHEMY = {"select", "insert", "update", "delete", "text", "func",
                      "and_", "or_", "join", "exists", "literal", "case"}


def test_no_tool_module_touches_the_database():
    """`D-95`, mechanised. Scoping lives in the services; a tool that writes its
    own query inherits none of it. Checked on imports rather than by review,
    because review does not scale to ~170 tools."""
    offenders: list[str] = []
    files = sorted(LUCY.glob("tools_*.py"))
    assert files, "no tool modules found — is the test running from api/?"
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = {a.name for a in node.names}
                if mod.startswith("app.models"):
                    offenders.append(f"{path.name}: imports {mod}")
                elif mod.startswith("sqlalchemy"):
                    bad = names & _BANNED_SQLALCHEMY
                    if bad:
                        offenders.append(
                            f"{path.name}: imports {sorted(bad)} from {mod}")
                    if names - {"Session"} - _BANNED_SQLALCHEMY:
                        offenders.append(
                            f"{path.name}: imports {sorted(names)} from {mod} "
                            "— only the Session type annotation is allowed")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith(("app.models", "sqlalchemy")):
                        offenders.append(f"{path.name}: imports {a.name}")
    assert not offenders, (
        "tools must call services, never the database (D-95): "
        + "; ".join(offenders))


def test_the_fee_and_band_fences_hold_across_every_scope():
    """The fences asserted on the whole surface, under scoping — extending the
    existing regex fence to the scoped tool list, before any widening."""
    for scope in (None, domains.DEFAULT_SCOPE, set(domains.DOMAIN_NAMES)):
        names = {s.name for s in visible_tools(TEACHER, scope=scope)}
        assert not [n for n in names if re.search(r"(^|_)fees?(_|$)", n)], \
            f"a fee tool reached a teacher with scope={scope}"
    # Bands are staff-only but not admin-only: a teacher who owns a band does
    # see them. What must never happen is a band tool on a parent surface —
    # and there is no parent tool surface at all, which is the real assertion.
    assert not [n for n in REGISTRY if "parent" in n or "guardian_portal" in n]
