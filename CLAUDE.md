# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is right now

**TrackBit School** — the unified school product: an *Academic Health Layer* + Tasks + Fees in one
app. It answers one question no ERP answers: *"Is my school actually teaching well, right now?"* It
sits **beside** the school's existing ERP; it does not replace it.

This folder currently contains **only the spec — no code yet.** Two documents:

- `trackbit-school-prd-v1.md` — **SPRD v1.0**, the build spec (modules, domain model, endpoints,
  screens, packets, Done-when gates). This is the primary implementation guide.
- `trackbit-product-architecture.md` — **v1.1**, the "why": positioning, product principles, and the
  fences (what we deliberately do *not* build).

Cite the spec in code comments as `SPRD §x.y`. **Conflict order:** the architecture doc's principles
and fences win over the PRD; an explicit later founder decision wins over both.

## The bootstrap (this is the first real work)

The app is not started from an empty repo. Per SPRD §2.4 (packet **P0-A**), it is **seeded by copying
two sibling projects**, which are *not* inside this folder:

- **`../task_management2/`** — the **SEED**. Copy `trackbit_api` → `api/`, `trackbit_web` → `web/`
  (excluding `.venv`, `node_modules`, `.next`, `.git`; `git init` fresh). Its `CLAUDE.md` and its six
  architectural laws (below) govern **all** code in this app. **Read `../task_management2/CLAUDE.md`
  before writing backend code.** Its stack: FastAPI + **sync** SQLAlchemy 2 + PostgreSQL (two DB
  roles + RLS), event-sourced tasks, APScheduler, channel-adapter notifications, magic-link auth,
  Next.js 16 + React 19 + Tailwind v4. Ships with 91 passing tests, ruff clean.
- **`../fee_management_system/`** — the fee module, **PORTED not mounted** (it's an older async /
  JWT / workspace-tenancy generation). Port its money domain nearly verbatim; see its `CLAUDE.md`
  and SPRD §4.6/§5.6 for the behavioral invariants. The real school registers to test the xlsx
  importer against are `shana_fee.xlsx` / `shana_extra_fee.xlsx` in that folder.

Legacy — **never copy from these:** `../task_management/` (old), `../school_ops*`. The old
`fee_management_system` stays live as the school's working tool until the unified app reaches fee
parity (SPRD §5.6 checklist).

Copy the four spec docs into `docs/` during P0-A so future agents have them in-repo.

### Target layout after bootstrap

```
api/    ← from task_management2/trackbit_api; adds services/models/endpoints for academics,
          students, sessions, assessments, dashboard, fees (see SPRD §2.3)
web/    ← from task_management2/trackbit_web; new IA: today/ planner/ classroom/ sessions/
          students/ assessments/ dashboard/ boards/(existing) fees/ members/ settings/
docs/   ← the four spec docs
```

Use a **new database** `trackbit_school_db` with the same two-role setup — do **not** point at the
seed's `trackbit_db`.

## Commands (inherited from the seed — apply once `api/`/`web/` exist)

Backend, from `api/` (Python 3.12, **uv** — not pip/poetry):

```bash
uv sync --extra dev                          # install deps
uv run uvicorn app.main:app --port 8000      # run API (NO --reload; restart after edits)
uv run pytest -q                             # full suite
uv run pytest tests/test_rls.py::test_name   # single test
uv run ruff check app tests                  # lint (--fix to auto-fix)
uv run alembic upgrade head                  # migrations
uv run python -m scripts.seed                # demo data
```

Frontend, from `web/` (Node 20+): `npm run dev` (needs API up), `npm run build`, `npm run lint`,
`npx tsc --noEmit`. Env: only `NEXT_PUBLIC_API_BASE_URL` (must end in `/api/v1`).

Tests/Alembic run against **real PostgreSQL** (no SQLite fallback); need `DATABASE_URL` +
`ADMIN_DATABASE_URL` in `.env`. **Packet Done-when gate:** backend packets end green on
`uv run pytest -q` + `ruff`; frontend packets end green on `npx tsc --noEmit` + `eslint` +
`next build`. The **existing 91-test task suite is the regression gate** — it must stay green after
every integration.

## Six architectural laws (load-bearing — carry into all new tables/endpoints)

1. **`org_id` comes only from the verified token**, never from params/body. Every authed handler
   reads `member.org_id` via `get_current_member` / `require_admin`.
2. **Two DB roles + Row-Level Security.** App connects as a restricted role (no BYPASSRLS); app-layer
   org scoping is the primary guard, RLS is defense-in-depth. Always scope queries by `org_id`
   explicitly anyway. Every new table gets an org-isolation RLS policy.
3. **Append-only history, never overwrite.** Task state via `append_event` (event-sourced). This
   spirit extends to all new "who did it" data: band changes, plan approvals, score verifications,
   and fee `transactions` are **append rows** (undo = compensating row, never a delete/UPDATE).
4. **Template vs Instance.** `TaskTemplate` = recurring definitions only; `TaskInstance` = every
   concrete unit (one-time tasks have `template_id = NULL`). Recurring instances are materialized
   ahead of time by the background job, guarded by a `(template_id, occurrence_date)` unique index.
5. **Visibility is centralized** in `core/visibility.py`; endpoints never inline access checks.
   Deliberate rule: **admins do NOT see private boards** they aren't members of.
6. **Thin endpoints, fat services.** Endpoints do plumbing only; logic lives in `services/`. Raise
   `AppError` subclasses (→ `{ "error": { code, message, details } }` envelope), never
   `HTTPException`, for business errors.

## Five product principles (acceptance criteria, not slogans)

- **P1 — One-minute teacher budget.** ≤ ~1 min/day capture per teacher; measured in taps and seconds
  on every teacher screen (quick-log ≤ 3 taps / ≤ 25s; 15-student session ≤ 60s). Feature over
  budget → redesign or cut.
- **P2 — Plan is baseline, log is actual.** The approved plan is locked; re-forecast is **computed**
  from baseline + logs + remaining effective periods — never stored as mutated plan rows.
- **P3 — Teachers get value before they give data** (logging homework auto-notifies parents).
- **P4 — Bands (A/B/C) are private intervention tiers, never labels.** Staff-only; **never** appear on
  any parent/guardian-facing surface (message, report, anything).
- **P5 — Nobody writes a report.** Every report is a byproduct of doing the work, captured at the
  moment with evidence (a tap, a count, a batch photo — never per-student photos).

## Roles & hard rules

Roles extend the seed's admin/member: `admin` (Director) · `coordinator` · `teacher` · `office`
(existing `member` → `teacher` on migration). New deps: `require_coordinator_up`, `require_academic`,
`require_office_up`. Permissions are backend-enforced (SPRD §3.3), UI mirrors. Non-negotiable:
**teachers never see fees; office never sees academic data; band tiers never reach parents.**
Parents have **no login** in v1 — guardians are records that receive outbound notifications only.

## AI services & stubs

All AI lives in `app/services/ai/`, is a single internal client, and is **env-gated** — when keys are
unset it returns deterministic fixtures so every flow is testable offline. Same pattern as the seed's
integrations (email/R2/billing/push stub when keys blank). **No chat UI** — AI is invisible plumbing
(plan drafts, celebration drafts, syllabus split, xlsx/photo parsing), and **every AI output lands in
a human-confirm surface before persisting** (editable drafts, verify grids). Model ids come from env
(`AI_MODEL_DRAFT`, `AI_MODEL_PARSE`); use current Claude models per the claude-api skill.

## Fences — do NOT build (SPRD §11 / arch §8, binding)

No timetable generator (periods/week is entered data, never generated) · no school-wide attendance
registers (M2 Sessions are teacher-run classes only, not registers) · no test authoring/conducting
(TrackBit records the school's own paper tests) · no parent app/login · no chatbot/AI-orchestrator
UI · no per-student evidence photos (batch only) · no visitor/inventory/social/health modules · no
report-card designer. LMS + teacher training belong to a separate product (Playground). If a school
asks for these, the answer is "we work alongside your ERP," not a rebuild.

## Build order

Work **packet-by-packet** per SPRD §10; do not mark a packet done until its **Done-when** criteria
pass. Sequence: **P0** foundation (bootstrap → roles → master data → fee port) → **P1** Planner +
Classroom Log (the make-or-break phase: are teachers still logging in week 4?) → **P1.5** Sessions →
**P2** Dashboard + digest → **P3** Assessments & Bands. Growth profiles and WhatsApp capture are
v1.5. The core loop: **M1 sets the plan → M2 records reality → M3/M4 detect gaps → M5 assigns the
response → M4 shows whether it worked.**
