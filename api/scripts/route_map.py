"""Print every API route with the guard and the package tier it enforces.

Keeps `docs/architecture/FEATURE-MAP.md` honest. Both columns are read off each
route's real dependency tree rather than from a decorator grep, so an alias
(`require_office_up`) or a router-level dependency is reported the same way the
request path would apply it.

Two questions, two columns: **guard** is who may call this (role), **feature**
is whether the school bought it (tier, `D-106`). They compose — a teacher on
ultra still never reaches fees — so a route can be restricted by either, and
this is the one place you can see both at once.

    uv run python scripts/route_map.py           # grouped, human-readable
    uv run python scripts/route_map.py --json    # machine-readable

Read-only: imports the app, never starts it, opens no database connection.
"""

import json
import sys

from app.core.features import Feature
from app.main import app

# The dependencies that decide who may call a route. Anything not in here is
# plumbing (db session, pagination) and is not worth reporting.
GUARDS = {
    "require_super_admin",
    # The operator acting inside one school — school structure is ours to change
    # (SETUP-REDESIGN-PLAN §6). A guard missing from this set reads as no guard
    # at all, which is the one way this script can lie.
    "require_operator",
    "require_admin",
    "require_coordinator_up",
    "require_office_up",
    "require_academic",
    "get_current_member",
    "get_current_parent",
    "get_current_principal",
    "get_current_user",
    # An agent connector acting with a member's authority (`D-97`). A separate
    # door: it accepts only an opaque `tbk_*` token, never a JWT.
    "get_agent_principal",
}


def guards_for(dependant, seen: set[int] | None = None) -> set[str]:
    """Collect guard names anywhere in a route's dependency tree.

    Recursive because a guard is usually reached through another dependency
    (`require_admin` depends on `get_current_member`), and because routers can
    attach one above the endpoint.
    """
    if seen is None:
        seen = set()
    found: set[str] = set()
    for sub in dependant.dependencies:
        name = getattr(sub.call, "__name__", None)
        if name in GUARDS:
            found.add(name)
        if id(sub) not in seen:
            seen.add(id(sub))
            found |= guards_for(sub, seen)
    return found


def tier_features_for(dependant, seen: set[int] | None = None) -> set[str]:
    """Collect the package features a route requires (`D-106`).

    `feature_gate(Feature.X)` returns a closure called `_gate`, so the feature
    is not visible from the function name — it is read out of the closure cell.
    Walked recursively for the same reason as `guards_for`: the gate is usually
    attached at `include_router`, above the endpoint.

    This is what makes tier coverage checkable rather than asserted: a module
    that ought to be gated and shows FREE here is a hole.
    """
    if seen is None:
        seen = set()
    found: set[str] = set()
    for sub in dependant.dependencies:
        call = sub.call
        if getattr(call, "__name__", None) == "_gate":
            for cell in getattr(call, "__closure__", None) or ():
                value = cell.cell_contents
                if isinstance(value, Feature):
                    found.add(str(value))
        if id(sub) not in seen:
            seen.add(id(sub))
            found |= tier_features_for(sub, seen)
    return found


def collect() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "dependant"):
            continue  # mounts, static files, websockets
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            found = sorted(guards_for(route.dependant))
            tiers = sorted(tier_features_for(route.dependant))
            rows.append(
                {
                    "method": method,
                    "path": route.path,
                    # No guard at all is a fact worth seeing, not a blank cell.
                    "guard": ",".join(found) if found else "PUBLIC",
                    # Likewise: "FREE" is a claim, not an absence.
                    "feature": ",".join(tiers) if tiers else "FREE",
                    "handler": route.name,
                    "module": getattr(route.endpoint, "__module__", ""),
                }
            )
    rows.sort(key=lambda r: (r["module"], r["path"], r["method"]))
    return rows


def main() -> None:
    rows = collect()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
        return

    print(f"TOTAL ROUTES: {len(rows)}")
    by_guard: dict[str, int] = {}
    by_feature: dict[str, int] = {}
    for r in rows:
        by_guard[r["guard"]] = by_guard.get(r["guard"], 0) + 1
        by_feature[r["feature"]] = by_feature.get(r["feature"], 0) + 1

    current = None
    for r in rows:
        module = r["module"].split(".")[-1]
        if module != current:
            current = module
            print(f"\n### {module}")
        print(f"  {r['method']:6} {r['path']:46} {r['guard']:24} {r['feature']}")

    print("\n### guard totals")
    for guard, count in sorted(by_guard.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4}  {guard}")

    print("\n### feature totals (FREE = no tier gate on this route)")
    for feature, count in sorted(by_feature.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4}  {feature}")


if __name__ == "__main__":
    main()
