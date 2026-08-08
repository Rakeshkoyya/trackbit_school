"""Print every API route with the guard the server actually enforces.

Keeps `docs/architecture/FEATURE-MAP.md` honest. The guard column is read off
each route's real dependency tree rather than from a decorator grep, so an
alias (`require_office_up`) or a router-level dependency is reported the same
way the request path would apply it.

    uv run python scripts/route_map.py           # grouped, human-readable
    uv run python scripts/route_map.py --json    # machine-readable

Read-only: imports the app, never starts it, opens no database connection.
"""

import json
import sys

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


def collect() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "dependant"):
            continue  # mounts, static files, websockets
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            found = sorted(guards_for(route.dependant))
            rows.append(
                {
                    "method": method,
                    "path": route.path,
                    # No guard at all is a fact worth seeing, not a blank cell.
                    "guard": ",".join(found) if found else "PUBLIC",
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
    for r in rows:
        by_guard[r["guard"]] = by_guard.get(r["guard"], 0) + 1

    current = None
    for r in rows:
        module = r["module"].split(".")[-1]
        if module != current:
            current = module
            print(f"\n### {module}")
        print(f"  {r['method']:6} {r['path']:52} {r['guard']}")

    print("\n### guard totals")
    for guard, count in sorted(by_guard.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4}  {guard}")


if __name__ == "__main__":
    main()
