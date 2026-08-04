"""Load the shipped observance corpus into the platform catalogue (V1-19).

    uv run python -m scripts.load_observances --dry-run          # see it first
    uv run python -m scripts.load_observances --year 2026 2027   # write it

`observances` is **platform data** (`D-60` / `S-149`) — no `org_id`, no RLS, one
curation serving every school. So this writes to whichever database `.env` is
pointing at, and a run against production is a run against every school at once.
It therefore refuses to write without seeing the target first, prints the host
and database it resolved, and requires `--yes` for a non-localhost target.

**Idempotent by construction.** It goes through `ObservanceService.bulk`, which
upserts on `(key, date)` — the same path the operator's paste-import uses. Run
it twice and the second run reports `updated`, not a duplicated catalogue. Fix a
date in `app/data/observances/` and re-run, and the correction reaches every
school that has not yet decided on that row (`S-151`).

**What it never does:** touch `event_decisions`. A school's approve/dismiss
record is append-only history and belongs to the school; re-importing reference
data must never rewrite what somebody decided (law 3).
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.indian_states import unresolved
from app.data.observances import available_years, build, collisions, summarise
from app.schemas.events import ObservanceBulkIn, ObservanceIn
from app.services.observances import ObservanceService


def _target() -> tuple[str, str, bool]:
    """(host, database, is_local) for the URL the app is configured with."""
    parsed = urlparse(settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://"))
    host = parsed.hostname or "?"
    return host, (parsed.path or "/?").lstrip("/"), host in ("localhost", "127.0.0.1")


def _entries(year: int) -> tuple[list[ObservanceIn], list[str]]:
    """Corpus rows as validated payloads, plus any state token the corpus itself
    got wrong. The second half matters: a hand-written data file is exactly
    where a typo like "Tamilnadu" comes from, and an unresolvable state imports
    perfectly and then matches no school for a year."""
    rows = build(year)
    bad: list[str] = []
    for r in rows:
        for token in unresolved(r.states):
            if token not in bad:
                bad.append(token)
    return [ObservanceIn(**r.as_payload()) for r in rows], bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, nargs="+", default=available_years(),
                    help=f"years to load (curated: {available_years()})")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and validate, write nothing")
    ap.add_argument("--yes", action="store_true",
                    help="required to write to a non-local database")
    args = ap.parse_args()

    host, database, is_local = _target()
    print(f"target: {host}/{database}  ({'local' if is_local else 'REMOTE'})")

    # Self-check before anything is written. A duplicate (key, date) does not
    # raise on import — bulk() upserts, so the second row silently overwrites
    # the first, which is the exact defect this corpus exists to fix.
    problems = False
    for year in args.year:
        dupes = collisions(year)
        if dupes:
            print(f"  ✗ {year}: duplicate (key, date): {dupes}")
            problems = True
        if year not in available_years():
            print(f"  ! {year}: no curated MOVABLE block — fixed dates only, "
                  f"no festivals. Curated years: {available_years()}")
    if problems:
        print("refusing to load a corpus that would overwrite itself.")
        return 1

    for year in args.year:
        s = summarise(year)
        print(f"  {year}: {s['total']} rows · {s['all_india']} all-India · "
              f"{s['state_scoped']} state-scoped across {s['states_covered']} states · "
              f"{s['by_tier'].get('major', 0)} major / {s['by_tier'].get('minor', 0)} minor")

    if args.dry_run:
        print("dry run — nothing written.")
        return 0
    if not is_local and not args.yes:
        print("\nThis is a REMOTE database and the catalogue is shared by every "
              "school on it.\nRe-run with --yes if that is what you intend.")
        return 2

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    total_created = total_updated = 0
    with Session(engine) as db:
        # Platform data has no org and no RLS policy, but the app role's GUC is
        # set per request in normal operation; a script has no request, so make
        # the absence explicit rather than inheriting whatever was last set.
        db.execute(text("SELECT set_config('app.org_id', '', true)"))
        svc = ObservanceService(db)
        for year in args.year:
            entries, bad_states = _entries(year)
            if bad_states:
                print(f"  ✗ {year}: corpus contains unresolvable states: {bad_states}")
                return 1
            # bulk() caps at 1000 entries; chunk so the corpus can grow past it
            # without this script quietly truncating a year.
            created = updated = 0
            for i in range(0, len(entries), 500):
                chunk = entries[i:i + 500]
                out = svc.bulk(ObservanceBulkIn(
                    source=f"TrackBit shipped corpus {year}", entries=chunk), None)
                created += out.created
                updated += out.updated
                if out.unresolved_states:
                    print(f"  ! unresolved states: {out.unresolved_states}")
            db.commit()
            total_created += created
            total_updated += updated
            print(f"  {year}: {created} created, {updated} updated")

    print(f"done — {total_created} created, {total_updated} updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
