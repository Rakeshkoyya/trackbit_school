# docs/logs — the build record

History, not state. Nothing in this folder is maintained after the day it is
written; it exists so a decision can be traced back to the problem that caused
it.

| File | What it is |
|---|---|
| [`packet-log.md`](packet-log.md) | Every packet shipped (P0 → MC-3/EX-3), in order, with the defect or founder decision behind each. Moved out of `CLAUDE.md` on 2026-08-07. |

## How to use it

`Ctrl-F` the module you are about to touch, read that entry, then stop. Reading
it front to back is ~1,800 lines and will tell you about forty modules you are
not changing.

The entries are dense on purpose. Most record a rule that looks arbitrary until
you know what went wrong — for example, "a `homework_checks` row means the
teacher went through it; its *absence* means `not_checked`, which is never
'everyone did it'". Removing that distinction looks like a simplification and
silently makes a teacher who checks nothing read as a class with perfect
completion.

## What does not live here

- **Live schema state** → `uv run alembic current`. The packet log's
  "prod owes N migrations" notes drifted three packets before anyone noticed;
  the database is the record.
- **What is being built now** → `docs/v1/PROGRESS.md`.
- **The rules you must follow** → `CLAUDE.md` (laws, principles, fences).
- **Where a feature lives today** → `docs/architecture/FEATURE-MAP.md`.

## Adding to it

Append a new entry at the end when a packet closes, in the existing shape: what
changed, which migration, and — the part that matters — *why*, including any
defect the packet found. Keep the tags (`D-nn` founder decision, `S-nn`
suggestion, `Q-nn` open question) so entries stay linked to
`docs/brainstorm/decisions.md`.

Do not edit older entries to make them agree with today's code. If an entry is
now wrong about how the system works, that is what the newer entry is for.
