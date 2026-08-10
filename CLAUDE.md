# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**TrackBit School** — the school's daily operating system. It plans the academic year down to
the period, captures each day with near-zero teacher effort (capture-by-exception), knows what
every student is doing during school and hostel hours, and writes the school's daily report
itself.

A monorepo:

```
api/       FastAPI + SQLAlchemy 2 (sync) + PostgreSQL     the backend
web/       Next.js 16 + React 19 + Tailwind v4           the frontend
docs/      the spec, the architecture, the build record
test_doc/  a generator for mock setup data
```

All v1 product phases are complete and the app is feature-whole: 420 API routes, 92 services,
80 web routes, two staff roles plus a read-only parent portal and a platform operator.

## Documentation map

Read the one that answers your question. Do not read them all.

| You need | Read |
|---|---|
| **Where a feature lives, and who may use it** | [`docs/architecture/FEATURE-MAP.md`](docs/architecture/FEATURE-MAP.md) |
| **What agents (MCP + Lucy) may do, and what they may never** | [`docs/architecture/MCP-SERVER-PLAN.md`](docs/architecture/MCP-SERVER-PLAN.md) |
| **Which agent tools are approved to build** — ⚠️ build nothing not ticked there | [`docs/architecture/MCP-TOOL-LIST.md`](docs/architecture/MCP-TOOL-LIST.md) |
| **How the school day is shaped** — bell schedules, typed periods, blocks | [`docs/architecture/TT2-DAY-SHAPE-PLAN.md`](docs/architecture/TT2-DAY-SHAPE-PLAN.md) |
| The current build spec | `docs/trackbit-school-prd-v2.md` (cite as `SPRD2 §x.y`) |
| The "why" — principles and fences | `docs/trackbit-product-architecture.md` |
| Reference for carried v1 modules (fees, tasks, sessions) | `docs/trackbit-school-prd-v1.md` |
| **Why a design is the way it is** | [`docs/logs/packet-log.md`](docs/logs/packet-log.md) — `Ctrl-F` your module, then stop |
| What is being built now | `docs/v1/PROGRESS.md`, `docs/v1/IMPLEMENTATION-PLAN.md` |
| Design sessions in progress | `docs/brainstorm/` |
| Frontend framework gotchas | `web/AGENTS.md` |

**Conflict order: SPRD2 > architecture doc > SPRD v1.** An explicit later founder decision wins
over all. Nothing in `docs/brainstorm/` outranks anything; a decision graduates into SPRD2 when
it is ready to build.

> ⚠️ `docs/logs/packet-log.md` is **history, not state**. Figures inside it — test counts,
> "prod owes N migrations", "current work" — were true the day they were written and are not
> maintained. The database is the record for schema; `pytest` is the record for tests.

## Commands

Backend, from `api/` (Python 3.12, **uv** — never pip or poetry):

```bash
uv sync --extra dev                              # install
uv run uvicorn app.main:app --port 8000          # run (NO --reload; restart after edits)
uv run pytest -q                                 # full suite — the regression gate
uv run pytest tests/test_lucy.py                 # one file
uv run pytest tests/test_lucy.py::test_name      # one test
uv run ruff check app tests                      # lint (--fix to auto-fix)
uv run alembic upgrade head                      # migrate  <- read the DB section first
uv run alembic current                           # where the schema actually is
uv run python -m scripts.seed                    # demo data  <- never in PRODUCTION mode
uv run python scripts/route_map.py               # every route + the guard it enforces
```

Frontend, from `web/` (Node 20+): `npm run dev` (needs the API up) · `npm run build` ·
`npm run lint` · `npx tsc --noEmit`. Env: only `NEXT_PUBLIC_API_BASE_URL`, which **must** end
in `/api/v1`.

**The green bar for any change:** backend = `pytest` + `ruff`; frontend = `tsc --noEmit` +
`eslint` + `next build`. The full backend suite must stay green after every change — it is the
regression gate, and "the tests pass" means nothing until you have watched them execute.

## Database — read this before running Alembic

**Docker does not work on this machine. Never use it.** There is no Postgres container;
`api/docker-compose.yml` is dead. The Dockerfiles exist only so Dokploy can build remotely.

`api/.env` is **switchable between LOCAL and PROD and says which mode it is in** — look for the
`# --- ACTIVE: ...` banner. The inactive URLs are parked beside it as `# LOCAL_*_BACKUP=` /
`# PROD_*_BACKUP=` comments. Those comments are the only copy of the prod credentials outside
Dokploy: **never delete them, never commit `.env`, never paste it anywhere.**

| var | local mode | prod mode |
|---|---|---|
| `DATABASE_URL` | `trackbit_school_app` (**NOBYPASSRLS**) @ localhost | `doadmin` @ DigitalOcean |
| `ADMIN_DATABASE_URL` | `postgres` @ localhost | `doadmin` @ DigitalOcean — **Alembic only** |
| `TEST_DATABASE_URL` | local `trackbit_school_test` | **unchanged — stays local** |

🚨 **`TEST_DATABASE_URL` stays on the local test database in both modes.** The suite creates and
hard-deletes organizations. `conftest.py` refuses to start if it resolves to the same
host+database as `DATABASE_URL` (escape hatch `ALLOW_TESTS_ON_DATABASE_URL=1`), but that guard
cannot know some *other* remote URL is precious — it is not a substitute for never editing this
line. Never point it at a superuser either: a superuser bypasses RLS even with
`FORCE ROW LEVEL SECURITY`, so `test_rls.py` fails for reasons unrelated to the code.

⚠️ **`.env` is currently in `ACTIVE: PRODUCTION` mode** (founder's request, so the local codebase
runs against the real prod DB). Prod is pre-launch and holds no critical data — that is the only
reason this is safe, and it stops being true the day a real school is on it. While in this mode:

- every click in the app is a **write to production**, and `alembic upgrade head` migrates
  production with no confirmation and no dry run;
- **law 2 is inert** — `doadmin` has `rolbypassrls = true`, so every `org_isolation` policy is
  bypassed. Switch to LOCAL for anything security-related;
- **`ENABLE_SCHEDULER` must stay `false`** — APScheduler runs per process, so a local uvicorn
  plus the Dokploy container would both fire the 19:00 report and the absence alerts off the
  same rows;
- **never run `scripts.seed`** — it would create the demo org and demo users in production.

To migrate a different database without touching `.env`:

```bash
ALEMBIC_DATABASE_URL="postgresql+psycopg2://postgres:PASSWORD@localhost:5432/trackbit_school_test" \
  uv run alembic upgrade head
```

**Run `uv run alembic current` before believing any written claim about a revision.** This file
used to cache "prod owes N migrations" and it drifted three packets before anyone noticed.

Worktrees have no `.env` (gitignored, not copied). Copy it in before running Alembic or pytest
there, or everything DB-backed fails with "connection refused".

### Deployment — Dokploy

Dokploy builds `api/Dockerfile` and `web/Dockerfile` and injects config as environment
variables; nothing is baked into an image. `api/docker-entrypoint.sh` runs migrations then execs
gunicorn, and **forces one worker whenever `ENABLE_SCHEDULER` is on** — APScheduler starts
inside each gunicorn worker, so two workers would send every absent student's guardian two
messages. Health probe is `GET /health` (app root, *not* under `/api/v1`).

## Six architectural laws

Load-bearing. Carry them into every new table and endpoint.

1. **`org_id` comes only from the verified token**, never from params or body. Every authed
   handler reads `member.org_id` via `get_current_member` / `require_admin`.
2. **Two DB roles + Row-Level Security.** The app connects as a restricted role with no
   BYPASSRLS. App-layer org scoping is the primary guard and RLS is defence-in-depth — so scope
   every query by `org_id` explicitly anyway, and give every new table an org-isolation policy.
3. **Append-only history, never overwrite.** Task state via `append_event`. This extends to all
   "who did it" data: band changes, plan approvals, score verifications, fee transactions,
   leave decisions and demo-request notes are **append rows** — undo is a compensating row,
   never a DELETE or UPDATE. (Law 3 governs *decisions*. A mistyped mark or a mis-tapped
   absence is corrected in place; that is not history, it is a typo.)
4. **Template vs Instance.** `TaskTemplate` = recurring definitions only; `TaskInstance` = every
   concrete unit (one-time tasks have `template_id = NULL`), materialized ahead by the
   background job under a `(template_id, occurrence_date)` unique index.
5. **Visibility is centralized** in `core/visibility.py`; endpoints never inline access checks.
   Deliberate: **admins do NOT see private boards** they aren't members of.
6. **Thin endpoints, fat services.** Endpoints do plumbing only. Raise `AppError` subclasses
   (→ `{ "error": { code, message, details } }`), never `HTTPException`, for business errors.

## Five product principles

Acceptance criteria, not slogans.

- **P1v2 — one-minute budget via capture-by-exception.** The teacher confirms the norm in one
  tap and records only deviations. Budgets: quick-log ≤ 3 taps / 25s; period card ≤ 5 taps /
  30s; a 15-student session ≤ 60s. **Any feature needing per-student entry for a whole class is
  mis-designed** — redesign it or cut it.
- **P2 — the plan is the baseline, the log is the actual.** The approved plan is locked;
  re-forecast is *computed* from baseline + logs + remaining effective periods, never stored as
  mutated plan rows.
- **P3 — teachers get value before they give data** (logging homework auto-notifies guardians).
- **P4 — bands (A/B/C) are private intervention tiers, never labels.** Staff-only; they never
  appear on any parent- or guardian-facing surface.
- **P5 — nobody writes a report.** Every report is a byproduct of doing the work, captured at
  the moment with evidence — a tap, a count, a batch photo.

## Roles, access & the two hard rules

**Two roles only.** `admin` runs the school (setup, plan approval, bands, fees, dashboard,
members); `teacher` is all academic staff including wardens. `require_coordinator_up` and
`require_office_up` are **admin-only aliases** — consolidate to `require_admin` when you touch a
file, and add no new uses.

Three more identities exist and none of them is a role value:

- **Class teacher** — derived from `school_classes.class_teacher_member_id`, surfaced as
  `me.is_class_teacher`. `D-89`: it must **never** become a third `org_role`; the same fact in
  two stores diverges on the first reassignment.
- **Parent** — a `User` with **no membership**; a `role="parent"` token, revoked by the live
  guardian-link check. Read-only, through the curated allowlist projection in
  `services/parent_portal.py` (built field by field, never a spread).
- **Super-admin** — the platform operator. `require_super_admin` lifts the RLS GUC by design.

**The two hard rules, true on every surface including Lucy:**

1. **Teachers never see fees.** The single exception is `D-83`: a teacher assigned a fee
   follow-up *task* sees that one student's fee detail inside that task only.
2. **Band tiers never reach parents or guardians.** P4.

`services/periods.py::visible_class_ids` is **the** answer to "which classes may this member
read" — the subjects she teaches **∪ the homeroom she owns**. Do not re-derive it.

Full role × feature × endpoint matrix: [`docs/architecture/FEATURE-MAP.md`](docs/architecture/FEATURE-MAP.md).

## Code map

```
api/app/
  core/               the shared vocabulary + config, security, RLS, visibility
  models/             SQLAlchemy models (31 modules)
  schemas/            Pydantic in/out
  services/           92 modules — all business logic
    ai/               env-gated model calls, each with a deterministic fallback
    insights/         the admin dashboard's 7 tabs
    lucy/             the agent: registry (MCP seed), loop, widgets
  api/v1/endpoints/   36 routers  <- NOT app/endpoints/
alembic/versions/     59 migrations
tests/                83 files
```

```
web/src/
  app/(app)/       the staff shell (role-guarded)   app/parent/  the portal, its own shell
  app/(wizard)/    the operator's setup wizard      app/auth/    login, invite, reset
  components/      21 domains                       lib/         typed API clients
```

Frontend rules that have each been broken once already:

- **`components/charts/` is the one chart kit.** Its palette is validated for CVD and both
  themes. No second charting path, no hand-picked hex.
- **`lib/format.ts` owns calendar dates** (`dayKey`, `todayKey`, `shiftDay`, …). Never serialise
  a local-midnight `Date` through `toISOString()` — east of UTC it returns the previous day.
- **Theme is the `.dark` class, not `prefers-color-scheme`.** Review in both.
- **Percentages are divided server-side.** Two historical definitions of "syllabus covered" were
  `.reduce()` calls in React, which no test could catch.

## One computation, many renderings — the `core/` vocabulary

The most-repeated defect in this codebase's history is the same fact computed differently in two
places, so a parent and a principal could read different numbers for the same subject on the
same day. Each module below ended that for its own domain. **Import them. Never re-derive what
they own, in Python or in the browser.**

| Module | Owns |
|---|---|
| `core/coverage.py` | "syllabus covered" — `taught_weight`, `better_coverage`, `CoverageFigure` (carries its denominator), the three named bases, `rated_status` |
| `core/exams.py` | minor vs major, `ScaleTally` (**no method returns a blended number**), `ScoreFigure` |
| `core/homework_verdict.py` | `done`/`late`/`carried`/`waived`/`not_checked` and what each is worth; `miss_streak` |
| `core/bands.py` | the A/B/C vocabulary, `chip()`, `tier_for`, `movement`, the descriptors |
| `core/band_assessment.py` | `marks` \| `rating` \| `other` — three kinds of statement that never pool |
| `core/collection.py` | fee quarters as due-date windows; `Collection` deliberately has **no `outstanding`** |
| `core/day_shape.py` | what a period **is** — bell-entry kinds, the six block kinds, and `CAPTURE`: what each block asks the teacher to record |
| `core/work_types.py` | staff work categories and their fixed colours |
| `core/staff.py` | `not_operator()` — the operator is a member of every school but is not staff |
| `core/indian_states.py` | the canonical state list; `normalise()` **never guesses** |
| `core/plans.py` | Free/Pro plan limits and their enforcement (see the tiering note below) |
| `core/visibility.py` | who may see a board (law 5) |

Two recurring devices worth recognising:

- **A figure carries its denominator.** `CoverageFigure`, `ScoreFigure` and `PresenceRing`
  cannot render a bare percentage. *"61% across 5 of the 9 tests"*, not *"61%"*.
- **Not-captured is a word, never a zero and never red.** An unmarked register, an unchecked
  homework set, an unsized chapter and an unassessed child are all *states*. Rendering any of
  them as `0%` blames a person for a gap in the record — usually the wrong person.

## AI services

All AI lives in `app/services/ai/`, routed through **OpenRouter** via `ai/client.py`
(`chat_json`, `chat_tools`) — the only functions here that touch the network. **Env-gated:**
with `OPENROUTER_API_KEY` unset every call short-circuits and the caller's deterministic
heuristic runs, so every flow is testable offline and the app runs fully with no key.

Two rules make it safe on the critical path:

- **`chat_json` fails soft, never up.** Timeout, 429, 5xx, prose-instead-of-JSON → returns
  `None` and the heuristic runs. A non-retryable 4xx breaks out immediately.
- **Deterministic validators decide; the model only proposes and phrases.** The importer asks
  the model to map only the columns the keyword heuristic couldn't place, never overriding an
  exact header match, then filters the reply against the real column list. **Every AI output
  lands in a human-confirm surface before it persists.**

Lucy is the one chat surface (staff-only). Its widget numbers come only from server-stored tool
results — the model picks the representation and cannot type the numbers — and its write tools
land in a pending-action confirm card.

## Fences (SPRD2 §11, binding)

**Still OUT:** payroll · HR · library · transport · inventory · visitor · social modules ·
report-card designer · test authoring/conducting · **any parent- or guardian-facing chat or AI
surface** · **parent writes of any kind** (the portal is read-only) · **mandatory per-student
capture** (exception-only, always — P1v2) · per-student evidence photos, with two decided
exceptions: hostel session media and exam script photos, where a photo per marked paper *is* the
capture mechanism.

Moved **in** by founder decision: staff attendance/leave/timesheet (operational only — who
covers period 4, never payroll) · substitutions and the admin operating board · per-period
attendance · timetable (import-first, deterministic validators, still no guaranteed solver) ·
daily report generation · per-student homework · **Lucy** · the **parent portal login**.

## Working conventions

- **Work packet by packet.** Do not mark one done until its Done-when criteria pass, and the v1
  flows still pass their tests.
- **Grep `alembic/versions/` for a free revision id before writing a migration.** The obvious
  next id is often taken, and reusing one makes Alembic report a **revision cycle** across the
  whole graph rather than a duplicate.
- **Prefer additive migrations.** Prod is migrated before code deploys, so a new column must be
  nullable or carry a server default.
- **Read the module before designing it.** Half of what gets "designed" already exists and the
  other half is broken in a way nobody knew.
- **Look at the built screen.** A large share of the defects in the packet log were found by
  opening the page in a real browser, not by reading the diff — a sentence over the wrong
  window, a ring that draws a closed circle at 99%, a percentage rendered as `0.889%`.
- **When the founder says "let's brainstorm on \<module\>"**, read
  `docs/brainstorm/HOW-WE-BRAINSTORM.md` and follow it. **No code is written during a brainstorm
  session.** The output is documentation, tagged `D-nn` decided · `S-nn` suggested · `Q-nn` open.

## Current state and what is next

Schema head is `f9a0b1c2d3e4` (TT-2 day shape: `bell_schedules`, typed
`timetable_slots`, `session_staff` — 2026-08-10; applied to the **local test DB
only**, prod and dev are behind). **Verify with
`uv run alembic current` rather than trusting this line** — it is a cache, and this file has
cached a wrong revision before. As of 2026-08-08 `d7e8f9a0b1c2` is applied to **production
and the local test DB**, verified by querying the tables rather than the version row.
Its parent `c6d7e8f9a0b1` (api_tokens) is also applied to both.
Prod was migrated the moment the running app hit `column organizations.agent_access does
not exist`; the column is additive with a server default, so the four existing orgs took
`agent_access='off'`. ⚠️ The local **dev** database has not been checked — run
`alembic current` against it before assuming.

Two things are queued. The first is **under way**; the second is not started:

- **The agent tool platform (MCP + Lucy).** `services/lucy/registry.py` is the one shared
  pool serving both (`D-93`/`D-94`). **Phase 1 shipped 2026-08-08:** every tool carries a
  `domain` (one of 13 toolsets, `services/lucy/domains.py`); `visible_tools()` filters
  **role → transport → scope → tier**, all at schema time and never by erroring;
  `tools_meta.py` holds the three navigation tools; `manual.py` generates
  `school://manual` from the registry. **45 tools live.**
  **Phase 2's PAT half shipped the same day:** `api_tokens` +
  `organizations.agent_access` (migration `c6d7e8f9a0b1`), `services/api_tokens.py`, a
  second auth door (`get_agent_principal` — accepts only `tbk_*`, never a JWT), and
  `/org/api-tokens` + `GET /agent/me` in `endpoints/agent.py`.
  **Still missing: the MCP transport (`app/mcp/` does not exist) and OAuth 2.1 (`D-99`).**
  - **What may be built is [`MCP-TOOL-LIST.md`](docs/architecture/MCP-TOOL-LIST.md)** —
    163 approved, 32 struck. ⚠️ Build nothing not ticked there (`D-101`), and where it
    disagrees with the plan doc, **the list wins**.
  - The design is [`MCP-SERVER-PLAN.md`](docs/architecture/MCP-SERVER-PLAN.md); **read its
    §0**, written for a cold start. **Next is Phase 2, credentials.**
  - Two rules override convenience while building: tools call **services, never tables**
    (`D-95`, asserted by `tests/test_tool_registry.py`), and **every write tool ships
    with a negative authorization test** — an in-process service call does not run the
    route's FastAPI guard, so `ToolSpec.role` is the only thing between a teacher and an
    admin-only write. The keystone is the **change set** (Phase 5): no write ships first.
- **Package tiers (basic/gold/platinum).** ⚠️ `core/plans.py` today is a **Free/Pro** model
  inherited from the task-management seed; its limits are boards, members, attachments and
  critical alarms, and it knows nothing about any school feature. `organizations.plan` carries a
  `CHECK (plan IN ('free','pro'))`. See [`FEATURE-MAP.md` §9](docs/architecture/FEATURE-MAP.md)
  for what a three-tier move actually requires — including that the pricing in the marketing
  copy and the pricing in `billing.py` currently disagree.

Known open items: production still runs as `doadmin` (`rolbypassrls = true`), so **law 2 is
decorative in the one environment that matters** — `scripts/provision_app_role.py` exists and
the swap is the last release item; and `topic_progress` in `services/planner.py` is a sixth
coverage definition that no screen calls but **Lucy does**.

## Background

Per SPRD §2.4 the app was seeded from two sibling projects, neither inside this folder:
**`../task_management2/`** (the seed copied into `api/` + `web/` — its six architectural laws
govern all code here; read its `CLAUDE.md` before writing backend code) and
**`../fee_management_system/`** (the fee module, **ported not mounted** — an older async/JWT
generation; its money domain was ported nearly verbatim). Legacy, never copy from:
`../task_management/`, `../school_ops*`.

**`test_doc/new_org/`** generates a complete, valid setup pack — a **different school every
run** — for walking a fresh organisation through the wizard: `cd api && uv run python
../test_doc/new_org/generate.py`. It holds four invariants so imports land 100% (periods sum to
weekly capacity · every class-subject has one teacher and nobody is overloaded · every topic is
sized · each syllabus fits the year). `--seed N` reproduces a run; `--messy` injects rows built
to fail, to exercise the error surfaces. The `.xlsx` pack and per-run `SETUP.md` are generated,
not committed.
