# The agent tool platform — MCP server, Lucy, and the shared tool pool

**Status:** design agreed, nothing built. Revision 3, 2026-08-08. **New here? Read §0 —
it is written for a cold start and assumes no prior context.** Written against the
app as it runs (420 routes, 92 services, 42 tools, verified with
`uv run python scripts/route_map.py` and by importing the live registry).

**Read alongside:** [`FEATURE-MAP.md`](FEATURE-MAP.md) (where every feature lives and who
may use it), `CLAUDE.md` (the six laws, the two hard rules, the fences).

> **Revision 2 changed the plan.** Revision 1 recommended a read-only server. That was
> calibrated to a weak confirmation story — MCP has no confirm card, so a write had
> nowhere safe to land. Founder decision `D-96` builds a real approval surface instead,
> which makes most of revision 1's `NEVER` verdicts defensible as confirmed writes. The
> catalogue below is rebuilt on that basis. What stays out (§9) is now a short list with
> hard reasons rather than a long list of caution.

> ⚠️ **Two later decisions supersede parts of this file. Read
> [`MCP-TOOL-LIST.md`](MCP-TOOL-LIST.md) first — it is the current authority on both.**
>
> - **`D-99` replaces §4.** Connector auth is **OAuth** (URL + Client ID + Client
>   Secret), because that is what claude.ai and most agent clients require — the API
>   becomes an OAuth 2.1 authorization server and the connection screen issues client
>   credentials. §4's PAT is still built, but as the header credential for Claude Code /
>   Cursor and for testing, not as the primary connector story. OAuth moves from Phase 12
>   to Phase 2.
> - **`D-100` replaces §3.3's "every write is `confirm=True`".** Approval is now **by
>   exception**: routine, correctable writes apply immediately; only append-only
>   decisions, outbound-effect writes, and anything crossing a volume threshold ask
>   first. Dangerous operations are **not exposed at all** rather than gated. The change
>   set (§3.3) survives — it is how the ~18 approval-tier writes are reviewed, and how
>   any bulk call that trips the volume guard escalates.
>
> §7 and §8's catalogues are superseded by the numbered, tickable list in
> `MCP-TOOL-LIST.md`. §1–§3.2, §5, §6 and §9–§12 stand unchanged.

---

## 0. Start here — cold start for the next session

Everything below this section assumes context. This section does not. Read it, then
go to §10 Phase 1.

### 0.1 State of play, 2026-08-08

| | |
|---|---|
| Built | **Phase 1, and Phase 2's PAT half** (2026-08-08). The registry carries domains and role→transport→scope→tier filtering, the three discovery tools and the manual generator; `api_tokens` + `agent_access` exist, and `GET /agent/me` authenticates a connector. **No transport yet — `app/mcp/` does not exist — and no OAuth.** |
| The seed | `api/app/services/lucy/registry.py` — **45 tools live today** (39 read, 6 write, all writes `confirm=True`); 42 predate Phase 1, which added `list_domains`, `list_tools` and `describe_tool`. Verify by importing `REGISTRY`; do not trust this number. |
| Decided | `D-93`…`D-101` (§1 here, and the header of `MCP-TOOL-LIST.md`) |
| Approved to build | **151 tools** ticked in [`MCP-TOOL-LIST.md`](MCP-TOOL-LIST.md) — 106 read, 35 auto-write, 10 approval-write. 32 struck. |
| Awaiting a tick | **12 exam-capture tools**, `MCP-TOOL-LIST.md` §8A (#184–195) |
| New dependency | the official `mcp` Python SDK — **not yet added**. `uv add mcp`. |

**`MCP-TOOL-LIST.md` is the authority on what gets built. This file is the authority on
how.** Where they disagree, the list wins — §7 and §8 here are superseded by it.

### 0.2 What the founder has decided, and what is still open

**Answered 2026-08-08** — recorded as `D-102`–`D-105` in `MCP-TOOL-LIST.md`'s header:

| | Answer |
|---|---|
| **Q1 + Q2** | `agent_access` is `off` for a new org, `admins` once live; **a teacher may hold her own connector**, scoped to her own authority. Shapes Phase 2. |
| **Q7 + §8A** | All 12 exam-capture tools approved, and Q7 answered **(b)** — capture on `BandAssessment` itself. **Its own packet; it has a migration.** |
| **Q8** | A strike removes a tool from **MCP only**, not the product. Built in Phase 1. |
| **prod** | Build against production deliberately (`D-105`) — ⚠️ so **no RLS behaviour can be verified there**. |

**Still open: Q3, Q4, Q5, Q6** (§11). None blocks Phase 2. **Q3 (change-set TTL and size
cap) and Q5 (re-auth for high-blast-radius approvals) must be settled before Phase 5.**

### 0.3 The first three tasks, in order

1. ~~**Phase 1 — registry domains + scope.**~~ ✅ **Done 2026-08-08.** See §10 Phase 1
   for what landed and the two things it deliberately left as seams.
2. ~~**Phase 2 — PAT credentials.**~~ ✅ **Done 2026-08-08** — `api_tokens`,
   `agent_access`, issue/list/revoke, and `GET /agent/me`. **OAuth 2.1 (`D-99`) is
   still outstanding** and is the primary connector story; §4.3's verification against
   Anthropic's current connector docs has not been done. ⚠️ **Prod is not migrated.**
3. **Phase 3 — transport.** `app/mcp/`, stdio first, then streamable HTTP at `/mcp`.
   **Read the `mcp` SDK's own README** — training data on MCP is stale.
4. **Phase 5 — the change-set engine.** The keystone: no write tool ships before it.
   *Done when a 40-item `create_tasks_bulk` renders as one card, approves once, and
   applies in one transaction.* Needs **Q3 and Q5** answered first.

### 0.4 Landmines live right now — check these first

- 🔴 **Another packet is mid-flight in the working tree.** The setup-pack / operator
  redesign (`services/setup_pack/`, `school_setup.py`, `schemas/setup_pack.py`, five
  test files, `platform-api.ts`, `setup-pack-screen.tsx`, `SETUP-REDESIGN-PLAN.md`) is
  **uncommitted** and edits `endpoints/{academics,planner,platform,timetable}.py`,
  `core/dependencies.py` and `schemas/auth.py`. Run `git status` before anything.
  It also **changes what "setup" means**, so `MCP-TOOL-LIST.md` §16's "structural setup
  is not exposed" is worth re-reading against it.
- 🔴 **`topic_progress` is still a sixth definition of "syllabus covered".** It now skips
  `not_planned` chapters, but it still invents `done|in_progress|pending` and still has
  no `not_scheduled` state. It is cross-stack (period card, Lucy, three TS unions, a
  test) and `growth.py:179` duplicates the rule for the growth **and parent** reports.
  See FEATURE-MAP §11. It does **not** block Phases 1–4 — every planning write was
  struck — but tool #52 answers "is 7A on track?" wrongly until it is fixed.
- 🔴 **Prod runs as `doadmin` (`rolbypassrls = true`)**, so law 2 is decorative there.
  `scripts/provision_app_role.py` exists. **Gate the HTTP transport (Phase 3) on it**;
  stdio-local is not exposed and is fine before it.
- ⚠️ **`.env` is in `ACTIVE: PRODUCTION`.** Every click writes to the live database, and
  `alembic upgrade head` migrates prod with no confirmation. Switch to LOCAL for anything
  security-related — RLS is bypassed under `doadmin`, so `test_rls.py` cannot tell you
  the truth there.
- ⚠️ **Read the `mcp` SDK's own README before writing transport code.** MCP moved fast
  and training data on it is stale — the same standing warning `web/AGENTS.md` carries
  for Next.js.

### 0.5 The four rules that make the whole thing safe

If only one thing survives from this document, make it these.

1. **Tools wrap services, never tables** (`D-95`). Scoping lives in the service —
   `assert_can_take_class`, `not_your_student`, the fee fence — and a tool that calls the
   service inherits all of it. A tool that writes SQL inherits none of it.
2. **Every write tool ships with a negative authorization test.** An in-process service
   call does **not** run the route's FastAPI guard, so `ToolSpec.role` is the only thing
   between a teacher and an admin-only write. This is the single most important gate here.
3. **Filtering happens at schema time, never by erroring.** Out-of-scope tools are
   *absent*, not refused — cheaper, and nothing to jailbreak.
4. **The fee and band fences are asserted by regex over the whole teacher tool surface.**
   Extend those tests to the MCP tool list in Phase 1, *before* any widening.

---

## 1. Decisions taken

| # | Decision |
|---|---|
| **D-93** | **One tool pool, many consumers.** `services/lucy/registry.py` is *the* registry. Lucy and the MCP server are two transports over the same `ToolSpec`s. A tool is never written for one of them. |
| **D-94** | **Lucy becomes agentic on the same pool.** Every write tool added for MCP is a write tool Lucy gains, under the same approval surface. |
| **D-95** | **Tools never touch the database.** Every handler calls a service method with a real `CurrentMember`. No raw SQL, no table access, no ORM query in a tool — in-process service calls only. |
| **D-96** | **The surface is read *and* write, as wide as is safe.** The product is an agent that can act on the school, not a reporting API. Breadth is the goal; the safety comes from §3, not from omission. |
| **D-97** | **Connector credentials plus an in-app connection screen.** A user copies a server URL and an auth token from a screen in the app and pastes them into their client. |
| **D-98** | **The tool list must stay navigable** as the pool grows past a hundred. Solved by §5 — scoped toolsets plus discovery tools plus a manual resource. |

Still open: **Q1–Q6 in §11.**

---

## 2. The shape

```
                       ┌─────────────────────────────┐
   Claude Desktop ─┐   │  services/lucy/registry.py   │
   Claude Code    ─┼──▶│  ToolSpec × N               │──▶ services/*  ──▶ DB
   Cursor / other ─┘   │  domain · role · kind ·      │    (the ONLY
        (MCP)          │  confirm · scope             │     data path)
                       │                             │
   Lucy chat  ────────▶│  same specs, same handlers  │
        (SSE)          └─────────────────────────────┘
```

Two transports, one pool, one data path. The registry docstring already promised this:
*"transport-agnostic: a `ToolSpec` knows nothing about FastAPI, SSE or widgets, so the
same registry can later back an MCP server 1:1."*

**Today: 42 tools — 36 read (22 academic, 14 admin), 6 write, every write
`confirm=True`.** Verified by importing `REGISTRY`, not read off a doc.

**Target: ~95 read + ~75 write across 13 toolsets.**

### 2.1 What "through the services, never the DB" buys, and its one catch

`D-95` is not a style rule. Every guard in this codebase that matters for *scoping* —
as opposed to *role* — lives in the service:

| Service | Helper | Refuses |
|---|---|---|
| `periods.py:53` | `assert_can_take_class` | a teacher marking a class she does not teach |
| `bands.py:257` | `assert_can_band` | banding a class-subject she does not own |
| `main_exams.py:453` | `assert_can_record_subject` | recording another subject's marks |
| `growth.py:108`, `my_class.py:1136`, `homework.py:493`, `support.py:527`, `band_assessments.py:531` | `not_your_student` | reading or writing a child who is not hers |
| `attendance.py:616`, `classroom.py:104`, `recommendations.py:59`, `report_card.py:221`, `student_records.py:98`, `my_syllabus.py:120`, `whats_on.py:184` | `not_your_class` | the same, per class |

A tool that calls the service inherits all of it. A tool that writes SQL inherits none of
it. That is the whole argument, and it is why `D-95` is load-bearing rather than
aesthetic.

**The catch, and it is the biggest quality risk in this plan:** an in-process service
call does **not** run the route's FastAPI guard. `require_admin` on
`POST /academics/classes` is not executed when a tool calls `AcademicService.create_class`
directly. The `ToolSpec.role` field is therefore the *only* thing standing between a
teacher and an admin-only write. With 6 write tools that was reviewable by eye. With ~75
it is not.

> 🔴 **Hard rule: every write tool ships with a negative authorization test.** A teacher
> calling the admin version gets `ForbiddenError`, asserted in `tests/test_tools_*.py`.
> No write tool merges without one. This is the single most important gate in this
> document.

---

## 3. The four mechanisms that make a wide write surface safe

Breadth is safe because of these four, not because of restraint. Build all four before
the write catalogue, not alongside it.

### 3.1 Service-call-only (`D-95`)

Above. Enforced by review plus a test that asserts no module under `services/lucy/tools_*`
imports `sqlalchemy`, `select`, or any `models.*`.

### 3.2 Toolsets — the scope unit, doing three jobs at once

Every `ToolSpec` gains a `domain`. A credential (and a Lucy session) carries a set of
enabled domains. `visible_tools()` filters on **role → scope → tier**, all at schema
time, all invisible rather than erroring.

```python
def visible_tools(m, *, scope: set[str] | None = None, tier: str | None = None):
    ...
```

The same filter solves three separate problems that would otherwise get three
mechanisms:

| Problem | Solved by |
|---|---|
| A teacher must not see admin tools | `role` — exists today |
| A connector must not be able to do everything the user can | `scope` — the credential's toolsets |
| A `basic`-tier school must not see platinum features | `tier` — FEATURE-MAP §9.6 says this must happen at schema time, "like the role filter, not by erroring" |

The thirteen toolsets, named after the feature-ID prefixes already in FEATURE-MAP §2–§7
so a tier, a nav gate, a connector scope and a tool filter all name a feature the same
way:

| Toolset | Covers | Notes |
|---|---|---|
| `core` | orientation, search, structure, settings, calendar, setup | **always on**, cannot be disabled |
| `students` | directory, growth, timeline, records, report cards, guardians | |
| `attendance` | register, roster, exceptions, absence reasons | |
| `capture` | my day, period card, lesson logs, homework, checks, observations | the teacher's daily loop |
| `planning` | syllabus, plans, forecast, timetable, exam calendar | |
| `exams` | cycles, scores, reports, analytics, exam types | |
| `bands` | the A/B/C support programme | **staff-only, P4, never on any parent-reachable surface** |
| `staff` | directory, leave, timesheet, substitutions | |
| `tasks` | boards, tasks, recurring templates | |
| `insights` | the 7 dashboard tabs, daily report | admin |
| `fees` | collection, structures, ledger | **admin only**, off by default |
| `sessions` | hostel sessions | |
| `events` | observances, what's on | |

Default for a new connector: `core + students + capture + planning + tasks`. `fees` and
`bands` require an explicit, separately-worded opt-in on the issue screen.

### 3.3 The change set — propose many, approve once

`create_tasks_bulk` for 40 teachers cannot be 40 confirm cards. The write foundation is a
**change set**: the agent proposes N operations as one reviewable unit, the human
approves once, and the whole set applies in one transaction.

```
agent  ──▶ change_set(status=proposed)
             ├─ item 1  tool=create_task  params={…}  summary="Task for Priya M — …"
             ├─ item 2  …
             └─ item 40 …
                     │
human ──▶ approve ───┴──▶ one transaction, N service calls, all-or-nothing
                          each item stamped applied|failed; the set is append-only (law 3)
```

Built on what exists. `lucy_pending_actions` already carries `tool`, `params`, `summary`,
`status`, `result`, `error`, `expires_at` (`models/lucy.py:164`). The changes:

| Change | Why |
|---|---|
| new `agent_change_sets` table; `lucy_pending_actions` gains `change_set_id` | a set of one is still a set — one code path, not two |
| `conversation_id` → nullable, plus `source` (`chat` \| `mcp`) and `api_token_id` | it is `nullable=False` with an FK to `lucy_conversations` today (`models/lucy.py:170`); an MCP proposal has no conversation. `api_token_id` answers "which connector asked for this" |
| its own TTL, not `LUCY_ACTION_EXPIRE_MINUTES = 15` | 15 minutes is right for a chat card and useless for out-of-band approval. A change set wants hours to days. |
| a `preview` payload per item | the card must render *what will change*, not the raw params. "Approve 6 plans" is not consent; "Approve 6 plans — 7A Maths finishing 12 Feb with 3 weeks buffer, …" is. |

**Rules:**
- Every write tool is `confirm=True`. **There is no second pattern, and no bypass flag.**
- A bulk tool is **N service calls in one transaction**, never a bulk SQL insert
  (`D-95`) — so every per-row scoping check still runs, and one refused row fails the set.
- The approval is by a **member with the authority to do it by hand**. An agent holding a
  teacher's credential cannot get an admin action approved by that teacher.
- Application is append-only (law 3). Undo is a compensating change set, never a DELETE.

### 3.4 Per-call audit

Every tool call records `(api_token_id | conversation_id, tool, params_digest, ok,
duration_ms)`. Reads included. "What did the agent look at, and when" is a question a
principal will eventually ask, and there is no retrofitting it.

---

## 4. Credentials — the honest answer on JWT

**JWT is the right thing for humans and the wrong thing for connectors, and the app
already proves it.**

What exists: a **15-minute access JWT** (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15`) and a
30-day refresh token (`POST /auth/refresh`, plain body param). Neither is a machine
credential.

Four reasons a long-lived JWT is the wrong instrument here, in order of weight:

1. **You cannot revoke it.** A JWT is valid until it expires, by construction. A leaked
   connector token would stay live for its whole lifetime with no button to press.
2. **You are already paying the price of statelessness and getting nothing for it.**
   `get_current_member` hits the database on *every* request — membership lookup plus
   `token_version` (`dependencies.py:59-70`). The one advantage of a JWT is avoiding
   that lookup, and this codebase deliberately does not take it. So an opaque token
   costs exactly the same and buys revocation.
3. **It cannot be named or scoped per connector** without minting a different token type
   — at which point you have built a PAT with extra steps.
4. **A prefixed opaque token is scannable.** `tbk_live_…` can be grepped for in a repo,
   caught by secret scanning, and recognised in a log. A JWT looks like every other JWT.

**Recommendation: keep JWT for human sessions exactly as it is; add an opaque PAT for
machines.** That is the standard split, and it honours the instinct behind "JWT is best"
— the bearer-token *shape* stays identical, so the transport and the client config look
the same. Only issuance and revocation change.

### 4.1 The table

`api_tokens` — one additive migration (grep `alembic/versions/` for a free revision id
first; the obvious next id is often taken and reuse reports a revision *cycle* across the
whole graph):

| Column | Notes |
|---|---|
| `org_id`, `membership_id` | the authority this token acts with — law 1 applies, `org_id` never comes from a request |
| `name` | "Rakesh's Claude Desktop" — the thing that makes revocation possible in practice |
| `token_hash` | SHA-256; the raw token is never stored. `core/security.py` already has `generate_raw_token` / `hash_token` |
| `prefix` | first 12 chars, shown in the list so a user can tell two tokens apart |
| `scopes` | JSONB array of toolset names (§3.2) |
| `mode` | `read` \| `read_write` — orthogonal to scopes, and the default is `read` |
| `expires_at` | nullable; the screen offers 30/90/365 days or never |
| `last_used_at`, `last_used_ip` | throttled write, like `_touch_last_active` |
| `created_by_membership_id`, `revoked_at`, `revoked_by_membership_id` | the audit |

**Resolution runs the same checks as `get_current_member`** — membership `status ==
"active"`, `token_version`, `_engage_rls(db, org_id)` — plus `revoked_at IS NULL` and
expiry. Write it as one shared function so there is no second auth path that forgets
revocation.

Raw token format: `tbk_live_<43 url-safe chars>` (`tbk_test_` outside production).

### 4.2 Who may issue one

New org setting `agent_access`: `off` (default for a new school) | `admins` |
`all_staff`. A member may only issue a token with **their own** authority and a subset of
their own toolsets — a teacher's connector can never exceed the teacher.

### 4.3 The connector question to verify before Phase 4

A pasted bearer token works today with Claude Code (`claude mcp add --transport http
… --header "Authorization: Bearer …"`), Cursor, and any client that lets you set headers.
**Whether claude.ai's one-click custom-connector UI accepts a static bearer token, or
requires OAuth, must be verified against Anthropic's current connector documentation at
implementation time — do not assume either way from memory.** If it requires OAuth, the
PAT still ships (it serves every other client) and OAuth becomes Phase 12 rather than
optional. Design the screen so a second auth method can appear beside the token without
a redesign.

---

## 5. Keeping ~170 tools navigable (`D-98`)

Two approaches were proposed: hierarchical navigation tools, or one large manual relying
on long context. **Both are right, for different reasons, and neither is sufficient
alone.**

The manual instinct is correct that context length is no longer the constraint. But the
constraint was never context length — it is **selection accuracy and per-turn cost**.
Tool schemas are re-sent on every request in most clients, so 170 schemas is a tax on
every turn of every conversation, and selection quality degrades well before any context
limit is reached. So:

### 5.1 The bound is the credential, not the model's patience

**The tool list a client sees is bounded by the credential's toolsets.** A default
connector (`core + students + capture + planning + tasks`) sees ~60 tools, not 170.
Someone who enables all thirteen has chosen that. This is the primary answer, it is
static, it is testable, and — the elegant part — **the same choice that keeps the list
small is the choice that limits what the agent can do.** One concept, two problems.

### 5.2 Discovery tools, always present in `core`

For the case where a lot is enabled, and for the model to orient itself:

| Tool | Returns |
|---|---|
| `list_domains()` | enabled toolsets, one line each, with tool counts |
| `list_tools(domain)` | names + one-line descriptions in that domain |
| `describe_tool(name)` | full description, input schema, and a worked example call |

This is the navigation idea made concrete: the model narrows by domain, then by tool,
then reads the schema — three cheap calls instead of 170 permanent schemas. MCP's
`tools/list_changed` notification allows a server to *expand* the advertised list after
discovery, but **client support for it is uneven — treat it as an optimisation, never as
the mechanism.** All tools in enabled toolsets stay callable regardless.

### 5.3 The manual, as a resource

`school://manual` — a generated document describing the domain model, the vocabulary
(`core/` modules and what each owns), the id-resolution order (*never guess an id; call
`get_school_structure` first*), the propose-and-approve flow, and every tool grouped by
domain. **Generated from the registry so it cannot drift.** Clients that support
resources attach it once and skip most discovery calls; clients that do not are
unaffected.

### 5.4 Lucy needs all of this too

Lucy sends all 42 schemas to the model on every turn today. At ~170 that breaks — cost,
latency and accuracy. **§5 is not MCP-specific work; it is the precondition for `D-94`.**
Lucy's session gains the same scope set (from the member's role and the org's policy),
the same discovery tools, and the same manual as a system-prompt attachment.

---

## 6. The connection screens (`D-97`)

New area under Settings — `/settings/connections`. Admin-visible always; teacher-visible
when `agent_access = all_staff`.

| Screen | Contents |
|---|---|
| **Connect** | the server URL (`https://api.trackbit.in/mcp`), a copy-ready snippet per client (Claude Code CLI one-liner, Claude Desktop / `mcp.json` block, generic HTTP), and a "test connection" button that round-trips `list_domains` |
| **New token** | name · toolsets (checkboxes; `fees` and `bands` separately worded) · `read` vs `read and write` · expiry. **The raw token is shown exactly once**, with a copy button and an explicit "you will not see this again" |
| **Tokens** | name, prefix, scopes, mode, created by, last used, expiry — and Revoke |
| **Approvals** | 🔴 **the important one.** Pending change sets: what the agent proposes, item by item, with the human-readable preview; Approve all · Approve selected · Reject. This is where a 40-task proposal becomes 40 real tasks, and it is the surface the entire write story rests on |
| **Activity** | the audit trail (§3.4) — which token, which tool, when, ok/failed |

The Approvals screen is not a settings page in spirit. It should also surface as a badge
in the main nav and as a push notification, because a change set nobody notices is a
feature that does not work. Lucy's in-chat confirm card stays exactly as it is for
single-item, in-conversation actions.

---

## 7. The read catalogue

Verdicts: **HAVE** (in the registry today) · **ADD-1** (first widening, real gaps) ·
**ADD-2** (worth having, not blocking).

| Toolset | HAVE | ADD-1 | ADD-2 |
|---|---|---|---|
| `core` | `get_school_structure` · `get_class_subjects` · `search_students` · `get_student` | `get_org_settings` (timings, policies, **`attendance_mode`** — the model gets school shape wrong without it) · `get_calendar` (working days, holidays — "how many teaching days are left" is unanswerable today) · `get_exam_calendar` | `list_members` · `list_domains` / `list_tools` / `describe_tool` (§5.2) |
| `students` | `get_student_growth` · `get_student_timeline` | `get_class_academics` · `get_my_class` · `get_student_report_card` | `get_student_analysis` · `get_student_notes` · `get_guardians` |
| `attendance` | `get_attendance_roster` · `get_attendance_day` | — | `get_attendance_register` (check the overlap with `get_attendance_day` first — F8) · `get_my_classes` · `get_absence_notes` |
| `capture` | `get_my_day` · `get_compliance` *(admin)* | `get_period_card` · `list_checks` 🔴 · `get_homework_log` · `get_homework_queue` · `get_student_homework` | `get_class_log` · `get_observations` · `get_homework_load` |
| `planning` | `get_plan_forecast` · `get_exam_fit` · `get_topic_progress` 🔴 · `get_syllabus_board` *(admin)* | `get_syllabus` · `get_my_subjects` · `get_week_schedule` · `get_timetable_grid` · `get_my_week` | `get_class_syllabus` · `get_plan_comments` · `get_exam_map` · `get_teacher_week` · `validate_timetable` |
| `exams` | `get_exam_feed` · `get_exam_detail` · `get_assessment_trends` · `get_weak_subjects` · `get_class_analysis` · `get_skill_profile` · `get_exams_board` *(admin)* | `get_exam_report` | `get_exam_types` · `get_cycle_grid` · `get_class_report_card` |
| `bands` | `get_band_board` · `get_band_history` | — | `get_band_distribution` · `get_my_band_students` · `get_band_programme` · `get_support_summary` |
| `staff` | `get_staff_board` *(admin)* · `get_absence_impact` *(admin)* | `get_staff_directory` | `get_staff_attendance` · `get_leave_queue` · `get_leave_balance` · `get_my_timesheet` · `get_my_month` · `get_staff_record` 🔴 · `get_substitutions` |
| `tasks` | `list_task_boards` · `get_task_board` *(admin)* | `get_my_tasks` · `get_board_tasks` | `get_task` · `get_board_report` · `list_recurring` |
| `insights` | `get_dashboard` · `get_daily_report` · `get_school_overview` · `get_teacher_load` · `get_absence_streaks` · `get_capture_grid` · `get_syllabus_board` · `get_homework_board` · `get_task_board` · `get_exams_board` | `get_presence` · `get_daybook` | `get_attendance_reach` · `get_calls` · `get_syllabus_pulse` · `get_actions_history` |
| `fees` | `get_fee_collection` | — | `get_overdue_students` · `get_fee_structures` · `get_student_fee` · `get_fee_transactions` |
| `sessions` | `get_session_records` | — | `list_sessions` · `get_session` |
| `events` | — | — | `get_whats_on` · `get_event_suggestions` · `get_catalogue` |

🔴 **Three read-side landmines:**

- **`get_topic_progress` is a sixth definition of "syllabus covered"** — it decides
  done/in-progress/pending on its own rules instead of `core/coverage.py`. No screen
  calls it; Lucy does. **Phase 0 blocks everything else on fixing it** (FEATURE-MAP §11).
- **`confirm_check` exists with no `list_checks`.** The model has to guess a `check_id`
  today. ADD-1.
- **`get_staff_record` is a record, not an appraisal** (`D-25`). No score, no rank, no
  completeness percentage. The tool description must forbid appraisal language *in the
  negative*, as the AI summary prompt already does, and the suite greps the payload for
  it.

**Never, on the read side:** `FeeService.summary` — `B-2`: it has no quarters and drops
`opening_dues` from every figure. `CollectionService.board` is the one fee computation
every screen renders, and V1-12 exists to have stopped Lucy using the other one.

---

## 8. The write catalogue

Every write is `confirm=True` and lands in a change set (§3.3). Every write ships with a
negative authorization test (§2.1). "bulk" means N service calls in one transaction.

### 8.1 `tasks` — the headline scenario

*"Here is my action-plan PDF; create the tasks for each teacher."*

| Tool | Wraps | Role |
|---|---|---|
| `create_task` | `TaskService.create` | academic *(HAVE)* |
| **`create_tasks_bulk`** | `TaskService.create` × N | academic — **the scenario above; the reason the change set exists** |
| `assign_task` · `reassign_task` · `claim_task` | `TaskService` | academic |
| `complete_task` · `reopen_task` · `cancel_task` | `TaskService` — event-sourced, law 3 native | academic |
| `add_task_note` | `TaskService` | academic |
| `create_board` · `add_board_member` · `create_category` | `BoardService` — law 5 visibility inherited | academic |
| `create_recurring_template` · `update_recurring` · `toggle_recurring` | `templates.py` — law 4: templates are definitions; instances are materialized by the background job | academic |

### 8.2 `capture` — the daily loop

| Tool | Wraps | Role |
|---|---|---|
| `mark_attendance` | `AttendanceService.mark` | academic *(HAVE)* |
| `mark_attendance_bulk` | × N classes | academic |
| `set_absence_reason` · `add_absence_note` | `attendance.py` | academic |
| `log_lesson` · **`log_lessons_bulk`** | `ClassroomService.log` | academic *(single HAVE)* |
| `assign_homework` · **`assign_homework_bulk`** | `ClassroomService.add_homework` | academic *(single HAVE)* |
| `check_homework` | `POST /classroom/homework/{id}/check` — verdicts for a set | academic |
| `confirm_check` | `RecommendationsService.confirm` | academic *(HAVE)* |
| `add_class_log_entry` · `save_observations` | `student_records.py`, `classroom.py` | academic |

> **F12 — `not_checked` is not zero.** A homework tool that lets a model render an
> unchecked set as a child's miss has broken the product's promise to teachers. The
> descriptions must say so, as `get_homework_board`'s already does.
>
> **P3 note:** `assign_homework` already notifies guardians. That is the product working,
> not the agent messaging a parent — see §9's precise formulation.

### 8.3 `planning`

| Tool | Wraps | Role |
|---|---|---|
| `add_plan_comment` · `resolve_plan_comment` | `PlannerService` | academic *(first HAVE)* |
| `draft_plan` · `generate_plan` · `extend_plan` | `planner.py`, `plan_validate.py` | admin |
| **`approve_plan` · `unapprove_plan`** | `planner.py` | admin — allowed because the approval card **is** the governance act, and shows more than the screen does. The preview must render the promise: baseline finish date, weeks of buffer, exam fit. |
| `reschedule_plan` | `plan_schedule.py` — P2 freezes `baseline_week_start`; the service honours it | academic |
| `create_syllabus_unit` · `create_topic` · `set_topic_estimate` · `split_topic` | `planner.py` | admin |
| `set_exam_portion` · `set_exam_map` | `exam_map.py` | admin |
| `create_calendar_events` *(bulk holidays / working days)* | `calendar.py` | admin |
| `syllabus_import_analyze` | `syllabus_import.py` — **stage only**, see §9 | admin |

### 8.4 `setup` *(inside `core`, admin-gated)*

| Tool | Wraps | Role |
|---|---|---|
| `create_year` · `create_term` · `create_class` · `create_subject` · `create_class_subject` | `AcademicService` | admin |
| `allocate_teachers` · `copy_subjects` | `AcademicService` | admin |
| `update_org_settings` | `org.py` | admin |
| `activate_year` | `AcademicService` — **the highest blast-radius write in the app**; the preview must spell out what changes for whom | admin |
| `create_exam_type` · `create_student_category` · `create_skill_area` | `exam_types.py`, `students.py`, `assessments.py` | admin |

### 8.5 `students`

| Tool | Wraps | Role |
|---|---|---|
| `create_student` · `update_student` | `StudentService` | admin |
| `add_guardian` · `update_guardian` | `students.py` — ⚠️ guardian rows are the parent portal's authentication; changing a phone number ends a parent's session by design | admin |
| `set_student_status` | `StudentService` — status, never delete | admin |
| `add_student_note` | `my_class.py` | class teacher + admin |
| `roster_import_analyze` | `roster_import.py` — **stage only** | admin |

### 8.6 `exams` — the spreadsheet scenario

| Tool | Wraps | Role |
|---|---|---|
| `create_exam_cycle` · `create_main_exam` | `exams.py`, `main_exams.py` | academic / admin |
| **`save_scores`** | `AssessmentService.save_scores` — an agent transcribing a marks spreadsheet lands scores in the **existing verify grid**; a human still verifies and locks. That preserves the integrity step instead of bypassing it. | subject teacher |
| `verify_scores` | `assessments.py` | admin |
| `lock_exam` · `unlock_exam` | `exams.py` — a locked exam is the record; both `ExamService.save` and `AssessmentService.save_scores` refuse it | teacher / admin |

> **Minor and major exams never pool** (`core/exams.py`). `ScaleTally` has no method
> returning a blended number. A tool must not invent one.

### 8.7 `bands` — staff-only, always

| Tool | Wraps | Role |
|---|---|---|
| `file_bands` | `bands.py` — `assert_can_band` | teacher of a monitored class-subject |
| `create_band_assessment` · `save_band_results` | `band_assessments.py` — `marks` \| `rating` \| `other` **never pool** (`core/band_assessment.py`) | band owner |
| `support_check_in` · `close_intervention` | `support.py` | band owner |
| `promote_exam_to_band_test` | `bands.py` — the guard is `locked`, not role | teacher |
| `assign_band_owner` · `set_monitored_subjects` · `update_descriptor` | `bands.py` | admin |

> **P4 is absolute.** Band tiers never reach a parent or guardian on any surface, and the
> band is **per subject — there is no overall letter** (`D-75`). The chip never renders
> without its sentence.

### 8.8 `staff`

| Tool | Wraps | Role |
|---|---|---|
| `apply_leave` · `cancel_leave` | `leave.py` | member (own) |
| `decide_leave` | `leave.py` | admin |
| `mark_staff_attendance` | `staff_attendance.py` | admin |
| `set_timesheet_entry` · `delete_timesheet_entry` | `timesheet.py` | member (own) |
| `update_leave_policy` · `update_staff_profile` | `leave.py`, `staff_directory.py` | admin |
| `assign_substitution` · `cancel_substitution` | `substitution.py` — allowed **only because** the preview names the person being assigned and shows whether someone already covered it | admin |

> 🔴 `D-25` / `S-67`: **a record, not an appraisal.** No score, no rank, no completeness
> percentage, no path to pay — enforced by a suite that greps the payload.

### 8.9 `sessions`, `events`, `fees`, `insights`

| Toolset | Writes | Role |
|---|---|---|
| `sessions` | `create_session` · `update_session` · `create_meeting` · `mark_session_attendance` · `save_session_logs` | academic |
| `events` | `approve_observance` · `dismiss_observance` · `set_event_cost` | admin |
| `fees` | `create_fee_structure` · `assign_fee_structure` · `update_student_fee` · `add_fee_note` · `set_installment_due_date` — **configuration only, never money movement** | admin |
| `insights` | `regenerate_daily_report` | admin |

### 8.10 Rough totals

| | Read | Write |
|---|---:|---:|
| HAVE today | 36 | 6 |
| ADD-1 | ~20 | — |
| ADD-2 + the write catalogue | ~40 | ~70 |
| **Target pool** | **~95** | **~75** |

A default connector scope sees ~60 of these (§5.1).

---

## 9. What stays out, and the exact reason

Short list, hard reasons. Everything not here is in.

| Out | Reason |
|---|---|
| **The entire parent portal** (`parent.*`, 13 routes) | SPRD2 §11: *no parent- or guardian-facing chat or AI surface*, and *no parent writes*. An MCP tool over parent data is that surface with one extra hop. Absolute. |
| **Platform / operator** (`platform.*`, `marketing.*`, 16 routes) | A different product with a different blast radius. `require_super_admin` **lifts the RLS org scope by design** (`dependencies.py:152`). If it is ever built it is a separate server and a separate credential — never this process. |
| **Account administration** — invite member, change role, reset password, remove member, switch org | A tool that mints or alters credentials is a privilege-escalation primitive. An agent that can grant itself admin has no fence. |
| **Money movement** — `mark-paid`, `pay`, `undo` | Recording money received is a claim about the physical world that no confirm card can verify. Fee *configuration* is in (§8.9); recording a payment is not. **This is the one place I would push back if overruled** — see Q4. |
| **Every `import/commit`** — roster, staff, syllabus, timetable, members | The human review step between `analyze` and `commit` is the only place import errors are caught. The agent may **stage** (`analyze`) — genuinely useful, and how the spreadsheet scenarios should work — and the human commits in the existing review screen. Removing that step deletes the safety mechanism, not the friction. |
| **Free-text messages to guardians** — `run_action` reminders, `/org/nudge`, `/fees/…/remind` | Precise formulation: *the agent never composes or triggers a free-text message to a person outside the school.* Product-generated notifications that are a side effect of a captured fact — logging homework notifies guardians (P3) — are the product working and stay in. |
| **Period open / close / not-held** | Device-level capture state. An agent opening a period fabricates presence. |
| **Binary upload** — exam script pages, session media, task photos | The photo *is* the capture mechanism (SPRD2 §11's two decided exceptions). There is nothing for an agent to contribute, and MCP is a poor transport for it. |
| **Deleting a student, class, subject or year that holds data** | `set_student_status` exists. Destruction is not an agent's call. |
| **Auth, billing, push, `ops/run`** | Credentials, money, device subscriptions and job triggers. `ops/run` is defensible on a *builder's* credential only. |

---

## 10. The build plan

### Phase 0 — Prerequisites

| | Task | Done when |
|---|---|---|
| 0.1 | 🔴 Fix topic status onto `core/coverage.py` — **re-scoped, see below** | every topic surface agrees, and an unplanned topic reads `not_scheduled`, not `pending` |
| 0.2 | Answer Q1–Q7 (§11 + `MCP-TOOL-LIST.md` §8A) | recorded as `D-nn` |
| 0.3 | *(gates Phase 3 HTTP only)* run `scripts/provision_app_role.py` on prod | `rolbypassrls` false for the app role |

> ⚠️ **0.1 was scoped "Small — a contained service fix" on the strength of
> FEATURE-MAP §11's claim that no screen called `topic_progress`. Investigation on
> 2026-08-07 found that claim false, and a seventh definition beside it.** The true
> blast radius:
>
> | Touches | Where |
> |---|---|
> | the route | `endpoints/planner.py:242` |
> | **the period card** | `services/classroom.py:816` |
> | Lucy | `tools_read.py:336` |
> | a duplicated copy of the same rule | `services/growth.py:179::topic_row` — feeds the growth report **and the parent report** |
> | three TypeScript unions | `web/src/lib/school-types.ts:1306`, `:1584`, `web/src/lib/parent-api.ts:131` |
> | a test asserting the exact words | `tests/test_periods.py:236` |
>
> The defect worth fixing is not the vocabulary — it is that **neither computation has
> a `not_scheduled` state**, so a topic nobody planned renders as *pending*. On the
> parent portal that is `S-54` (the school reading as behind on work it never
> promised). `chapter_status(topics=1, …)` is the fix for one topic, but the fourth
> state changes a union a **parent surface** renders.
>
> **Re-scoped: Medium, cross-stack, and its own packet.** It gates Lucy's
> `get_topic_progress` and any planning tool — but the approved list struck every
> planning write, so **it no longer blocks Phases 1–4.** Do it as a normal packet; do
> not let it hold up the transport.

**0.3** is the last v1 release item and independently worth doing.

### Phase 1 — Registry: domains, scope, discovery ✅ **built 2026-08-08**

| Landed | Where |
|---|---|
| The 13 toolsets as a declared vocabulary, with `ALWAYS_ON` and `DEFAULT_SCOPE` | `services/lucy/domains.py` *(new)* |
| `ToolSpec.domain`, **required** by the `tool()` decorator and validated at registration | `services/lucy/registry.py` |
| All 42 pre-existing tools stamped with the domain `MCP-TOOL-LIST.md` assigns them | `tools_read/write/insights.py` |
| `visible_tools(m, *, scope, tier)` filtering **role → scope → tier**, all at schema time | `registry.py` |
| `ToolScope` + a contextvar published by `execute()`, so a discovery tool answers for *this* caller | `registry.py` |
| `list_domains` / `list_tools` / `describe_tool` | `services/lucy/tools_meta.py` *(new)* |
| The `school://manual` generator | `services/lucy/manual.py` *(new)* |
| 17 unit tests, no DB — including the `D-95` import guard | `tests/test_tool_registry.py` *(new)* |

**Verified:** `test_lucy.py`, `test_widget_catalog.py` and `test_dashboard_v1_12.py` all
pass **unchanged**; `ruff` clean. Lucy calls `visible_tools(m)` positionally and so stays
unscoped, which is correct until Phase 11.

**Two things were deliberately left as seams, not built:**

- **`TIER_DOMAINS` is empty.** The filter is real and ordered third; the *mapping* is a
  pricing decision nobody has taken — `core/plans.py` is still the inherited Free/Pro
  model (FEATURE-MAP §9.6). Populating that dict is the whole of the tool-filtering half
  of the package-tiers packet.
- **The `D-95` guard allows `from sqlalchemy.orm import Session`** and nothing else from
  sqlalchemy. Every handler annotates `db: Session`; the guard bans the query
  constructors (`select`, `func`, `text`, `insert`, `update`, `delete`, …) and any
  `app.models` import, which is what "never touches a table" actually means.

> ⚠️ **One question this phase surfaced and could not answer** — see §11 `Q8`: three tools
> that exist in Lucy today (`assign_homework`, `confirm_check`, `add_plan_comment`) are
> **struck** in `MCP-TOOL-LIST.md`. They are still registered and still Lucy's, because
> `D-93` says one pool; but whether the strike means "not over MCP" or "gone from the
> product" decides whether the registry needs a per-transport flag.

### Phase 2 — Credentials · **PAT half built 2026-08-08; OAuth still to do**

| Landed | Where |
|---|---|
| `api_tokens` + `organizations.agent_access`, with `org_isolation` RLS on the new table | migration `c6d7e8f9a0b1` |
| The model | `models/api_token.py` *(new)* |
| Issue / list / revoke / **resolve**, with the "never exceeds its issuer" rule | `services/api_tokens.py` *(new)* |
| `AgentPrincipal` + `get_agent_principal` — a **second door** that accepts only `tbk_*`, never a JWT | `core/dependencies.py` |
| `POST`/`GET` `/org/api-tokens`, `DELETE /org/api-tokens/{id}`, and `GET /agent/me` | `endpoints/agent.py` *(new)* |
| `agent_access` on the existing `PATCH /org/settings` (`D-103`) | `schemas/org.py`, `services/org.py` |
| 15 tests, mostly negative | `tests/test_api_tokens.py` *(new)* |

**Done-when met:** a token issues, is used, records `last_used_at`, revokes, and 401s on
the next call; and a teacher cannot issue a token exceeding her own authority — asking for
`fees` or `insights` is **refused**, not silently emptied.

Three behaviours worth knowing because they are not obvious from the plan:

- **`GET /agent/me`** is the token's own identity endpoint — the "test connection" round
  trip §6 asks for, and the first thing on the agent side that works. It reports the tools
  the credential *actually resolves*, not what was requested at issue time, so a role
  change shows up there first.
- **Setting `agent_access` to `off` kills tokens already issued**, not just new ones.
- **Every refusal is the same `AuthError`** — revoked, expired and never-existed are
  indistinguishable to the caller.

**OAuth 2.1 (`D-99`) shipped 2026-08-08**, and with it Phase 3's transport.

### Phase 2b — OAuth 2.1 ✅ **built 2026-08-08**

| Landed | Where |
|---|---|
| `oauth_clients` + `oauth_grants`, and five OAuth columns on `api_tokens` | migration `d7e8f9a0b1c2` |
| The authorization server: authorize, consent, token, refresh-with-rotation, revoke | `services/oauth.py`, `endpoints/oauth.py` *(new)* |
| Discovery: RFC 9728 protected-resource + RFC 8414 AS metadata, at the app **root** | `app/mcp/server.py` |
| Connections screen + consent screen | `web/src/app/(app)/settings/connections`, `.../oauth/consent` |

**An OAuth access token *is* an `api_tokens` row.** That is the load-bearing decision:
`ApiTokenService.resolve()` stays the single resolver, so revocation, membership liveness
and the `agent_access` kill switch cover connector tokens without being reimplemented.

### Phase 3 — Transport ✅ **built 2026-08-08**

`app/mcp/` — Streamable HTTP at `/mcp`, POST/GET/DELETE. `initialize`,
`notifications/initialized`, `ping`, `tools/list`, `tools/call`, `resources/list`,
`resources/read`. Tools come from the registry filtered by the credential's scope, and the
manual is served as `school://manual`.

> ⚠️ **HTTP transport was gated on 0.3 (the prod app-role swap), which has NOT happened.**
> Production still runs as `doadmin` with `rolbypassrls = true`, so RLS is decorative
> there — app-layer `org_id` scoping is the only tenant guard in the one environment that
> matters. Shipped ahead of that gate on the founder's explicit instruction (`D-105`); the
> swap remains the last release item.

**§4.3's verification was done** — against Anthropic's live connector docs, not memory.
The contract that actually matters:

| | Verified value |
|---|---|
| Claude's redirect URI | `https://claude.ai/api/mcp/auth_callback` |
| Claude Code | loopback, **port-agnostic** match on `localhost`/`127.0.0.1` |
| Discovery | **401** + `WWW-Authenticate: Bearer resource_metadata="…"` — ignored on a 200 |
| PRM `resource` | must equal the URL the user typed into Claude, path included |
| Token endpoint | must accept `application/x-www-form-urlencoded` (JSON-only ⇒ 415) |
| Refresh failure | must return `invalid_grant`, not a custom code |
| Latency budget | 10s discovery/token, 30s refresh |
| Anthropic egress | `160.79.104.0/21` |

**Not built: Dynamic Client Registration.** Custom connectors use pre-registered client
credentials generated in Settings → Connections — the documented non-DCR path, which also
avoids registering a fresh client on every connection. A *directory* listing would need
DCR or CIMD.

✅ **Production is migrated** to `d7e8f9a0b1c2` (verified by querying the tables).

### Phase 3 — Transport

`app/mcp/` — stdio entry (`uv run python -m app.mcp`) first, then streamable HTTP mounted
at `/mcp`, rate-limited like `/lucy`. Sessions short-lived, never held across model I/O
(`endpoints/lucy.py`'s rule). Map `params_schema` → `inputSchema`, `model_view` → text,
`ToolExecution(ok=False)` → `isError`. **Verify the `mcp` SDK's current API against its
own README** — training data on MCP is stale, as `web/AGENTS.md` warns for Next.js.

**Done when:** a real client lists exactly the credential's scope, executes a read, and an
out-of-scope tool is *absent* rather than refused. HTTP gated on 0.3. **Medium.**

### Phase 4 — The connection screens

Connect · New token · Tokens · Activity (§6). Approvals ships in Phase 5.

**Done when:** a founder can go from zero to a working connector without touching a
terminal. **Medium.**

### Phase 5 — The change-set engine + Approvals *(the write foundation)*

`agent_change_sets` · `lucy_pending_actions` gains `change_set_id`, nullable
`conversation_id`, `source`, `api_token_id`, a longer TTL and a `preview` payload ·
transactional apply · the Approvals screen, nav badge and push · **Lucy uses the same
engine** (`D-94`).

**Done when:** an MCP-proposed 40-item `create_tasks_bulk` renders as one reviewable card,
approves once, creates 40 tasks in one transaction, records `source='mcp'` with the token
id, and a single refused row fails the whole set cleanly. **Medium–Large. This is the
keystone — nothing in Phases 6–10 ships before it.**

### Phase 6 — Read widening (ADD-1, ~20 tools)

Can run in parallel with 4–5; each lands in the shared registry, so Lucy gains it too.

### Phases 7–10 — Writes, by domain, in this order

`tasks` → `capture` → `planning` + `setup` → `students` + `exams` → `staff` + `bands` →
`sessions` + `events` + `fees`.

**Per-domain done-when:** every write has a negative authorization test; the full `pytest`
suite green; the fee and band fence tests extended to cover the new tools; no tool imports
`models` or `sqlalchemy`.

### Phase 11 — Lucy on the full pool (`D-94`)

Scope set per session, discovery tools, the manual in the system prompt, batch confirm
cards in chat.

### Phase 12 — OAuth 2.1

Priority depends entirely on §4.3's verification.

---

## 11. Still open

**Answered 2026-08-08: Q1, Q2, Q7, Q8.** Recorded as `D-102`–`D-105` in the header of
[`MCP-TOOL-LIST.md`](MCP-TOOL-LIST.md). **Q3, Q4, Q5, Q6 remain open** — none of them
blocks Phase 2, and Q3/Q5 must be settled before Phase 5.

| # | Question | My recommendation |
|---|---|---|
| ~~**Q1**~~ | Default `agent_access` for a school | ✅ **Decided (`D-103`): `off` for a brand-new org, `admins` once it is live.** |
| ~~**Q2**~~ | Does a teacher get her own connector? | ✅ **Decided (`D-103`): yes, scoped to her own authority and never exceeding it.** |
| **Q3** | Change-set TTL and size cap? | **7 days, 200 items.** Past that it is an import, and imports have their own surface. |
| **Q4** | Fee payment recording — hold the line or open it? | **Hold.** Configuration in, money movement out (§9). If overruled, it needs a second confirmation by a *different* admin, and that is a bigger build than the tool. |
| **Q5** | Should approving a change set require re-authentication for high-blast-radius items (`activate_year`, `unlock_exam`, role-adjacent writes)? | **Yes, for a named list of ~6 tools.** Cheap to build, and it is the difference between an approval and a reflex. |
| **Q6** | Does the audit log surface to the school, or stay internal? | **Surface it** (§6 Activity). A principal who can see what the agent did will trust it with more. |
| ~~**Q8**~~ *(raised by Phase 1)* | Does a strike remove a tool from the product, or only from MCP? | ✅ **Decided (`D-102`): only from MCP, and built** — `ToolSpec.transports` plus a `transport` filter. The three stay Lucy's. |
| ~~**Q7**~~ | Band-assessment answer-sheet capture — (a) the existing bridge, or (b) capture on `BandAssessment` itself? | ✅ **Decided (`D-104`): (b)**, overruling the recommendation of (a). (b) is the only option that covers `rating` and `other` assessments, which never become an exam cycle. **Its own packet — it has a migration.** |
| **Q9** *(new, raised by Phase 2)* | §4.1 lists `token_version` among the checks `resolve()` should repeat, and **it is not implemented** — see the deviation note in `services/api_tokens.py`. Should bumping `token_version` ("sign everyone out") also kill agent connectors? | **Probably yes, but it is a decision, not a default.** A connector embeds nothing, so it already tracks a role change live — a demoted admin loses her admin tools on the next call, which is the important direction and works today. What is missing is the *other* direction: "sign everyone out" currently leaves connectors alive. Only `revoke`, removing the membership, or `agent_access = off` stop them. Fixing it is one column plus a migration. |

---

## 12. Acceptance

- [ ] Q1–Q6 answered and recorded as `D-nn`
- [ ] `topic_progress` uses `core/coverage.py`
- [ ] No module under `services/lucy/tools_*` imports `sqlalchemy` or `models` (`D-95`)
- [ ] **Every write tool has a negative authorization test**
- [ ] Every write tool is `confirm=True` and lands in a change set — no bypass flag exists
- [ ] The fee fence regex and the band fence cover the MCP tool list, not just Lucy's
- [ ] A teacher's tool list contains zero admin tools and zero fee tools
- [ ] No parent-facing tool exists on any surface
- [ ] A revoked token fails on the next call
- [ ] Full `pytest` green
