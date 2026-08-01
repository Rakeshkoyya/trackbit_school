# v1 build progress

Tracks packet-by-packet progress against `IMPLEMENTATION-PLAN.md` (rev 1, `D-78`–`D-88`).
Updated at the close of every working session. **Read this first when resuming v1 work.**

## Packet status

| Packet | Status | Commit | Notes |
|---|---|---|---|
| **V1-0** · Foundation: one computation | ✅ **DONE** | `c14daf6` | 5 facts unified (day status · partial weight · who-is-free · homework verdict · working days) + defect sweep. Backend 381 passed. Also pre-landed V1-1's FIX items: S-111 client re-filter deleted, S-112 org-local rail due dates, D-47 open-task dedupe. |
| **V1-1** · Tasks & the action rail | ✅ **DONE** | see git log | Migration `e1f2a3b4c5d6` (subject/outcome on task_instances) applied to **prod+dev+test**. D-46 subject+outcome (rail sets it, dedupe keys on it, timeline shows it, complete asks "what happened?") · D-44 board 7-day done window + date filter + hidden count · D-45 stale group (never auto-closed) · D-41/D-43 My Day task window (3 working days ∪ due today, cap 5, older-count footer) · S-106 asked-by. `test_tasks_v1_1.py` (7) + 64 regression green; web tsc/eslint/build clean. |
| V1-2 · Setup, onboarding & handover | not started | — | Migration: school_code, students.date_of_birth, memberships.date_of_birth. |
| V1-3 · Attendance + class teacher | not started | — | Needs V1-1, V1-2. |
| V1-4 · Staff, leave, cover & time | not started | — | Needs V1-2. |
| V1-5 · Homework | not started | — | Needs V1-3. Simplified by D-85. |
| V1-6 · Syllabus, planning & mid-year | not started | — | |
| V1-7 · Events, dates & birthdays | not started | — | Needs V1-2 (DOB). Q-63 research runs before this packet. |
| V1-8 · Exams, scores & reports | not started | — | Largest packet. Corrections + lock ship first; photo flow + report levels follow. |
| V1-9 · Bands / support programme | not started | — | Needs V1-2 + V1-8's lock. Step 0 = four fixes. |
| V1-10 · Fees | not started | — | Needs V1-1. Migration: fee_notes. |
| V1-11 · Parent portal | not started | — | Needs V1-2, V1-3, V1-5, V1-10. |
| V1-12 · Dashboard visual layer + Lucy | not started | — | Needs all module packets. |
| V1-13 · Hardening & release | not started | — | Prod app-role swap (RLS) is the 🔴 item. |

## Packet-close gate (every packet)

- backend `uv run pytest -q` green + `ruff check app tests` clean
- frontend `npx tsc --noEmit` + `eslint` + `next build` clean
- **the no-dead-ends grep**: no exported client API method with no caller; no endpoint with no client
- the packet's own Done-when from the plan

## Session log

- **2026-08-01 (session 1)** — V1-0 shipped + committed (`c14daf6`). Backend 381 passing.
- **2026-08-01 (session 2)** — this tracker created; **V1-1 built and shipped** (backend +
  frontend + tests). Also fixed en route: the rail lost its default title when an explicit
  assignee was picked for a student follow-up. Note: `api/.env` was in PROD mode, so the
  migration went to DO prod first (additive, safe), then test+dev were migrated via
  `ALEMBIC_DATABASE_URL`. Next up: **V1-2 (setup, onboarding & handover)**.

## Standing reminders

- Fence propagation (plan §12.4): `D-82` (per-student exam photos) + `D-83` (teacher fee detail
  inside an assigned task) are already noted in `CLAUDE.md`; ux-principles.md + SPRD2 §11 still
  need the same note **before V1-8 / V1-10 start**.
- Test DB: local `trackbit_school_test` only; full suite ~4.5 min. Mid-work, run the touched
  file + ruff/tsc only (user preference).
- Migration head at V1-0 close: `e0f1a2b3c4d5`.
