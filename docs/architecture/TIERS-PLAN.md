# Package tiers — the build plan

Four tiers (`free` · `pro` · `max` · `ultra`), assigned by hand from the operator's
screen, enforced on every surface, and surfaced to the school as a lock with a
one-tap upgrade *request* — not a checkout.

Founder brief 2026-08-08, decisions `D-106`…`D-111` taken the same day. This is the
build plan for [`FEATURE-MAP.md` §9](FEATURE-MAP.md), which recorded what the
current billing code can and cannot express. **Read §0 before touching anything.**

> **Status — 2026-08-08.** **P1 and P2 are done** on branch `worktree-tiers-p1`.
>
> - **P1** — `core/features.py` is the tier map; `PlanLimitError` carries
>   `required_tier`; the inherited Free/Pro quotas are deleted (`D-109`) along
>   with `core/plans.py` itself; `GET /org/settings` returns `features[]`
>   instead of `limits`.
> - **P2** — migration **`e8f9a0b1c2d3`** (parent `d7e8f9a0b1c2`) widens
>   `plan_valid` to the four tiers, adds `organizations.plan_source` +
>   `plan_expires_at`, and creates `plan_prices` (seeded with the launch
>   prices), `plan_changes`, `upgrade_requests` and `upgrade_request_notes`.
>   Models are in `models/tiers.py` — named `tiers`, not `plans`, because this
>   codebase already means the *academic* plan by that word.
>   ⚠️ **Applied to the local test DB only. Production and the local dev DB
>   are still on `d7e8f9a0b1c2`** — `.env` is in `ACTIVE: PRODUCTION` mode, so
>   migrate those deliberately, never with a bare `alembic upgrade head`.
>
> - **P3** — `services/tiers.py` + `schemas/tiers.py`: the price list, the
>   per-school quote, `assign_plan` (appends `plan_changes`, snapshots the
>   amount, caches on `organizations`), the upgrade queue with its append-only
>   note trail, and the "expiring soon" list. `billing.handle_webhook` now
>   **refuses any org whose `plan_source` is `manual`** (§1.8) — and
>   `start_checkout` is what hands ownership to the gateway.
>
> > - **P4b** — the mixed modules, gated per route: `insights` (staff, exams,
>   tasks, homework, reach and the action rail; attendance/presence/syllabus
>   stay free) and `students` (Directory free, Academics `pro`). MCP composes
>   with `agent_access` inside `api_tokens.py` and `oauth.py` — the tier makes
>   the door exist, `agent_access` opens it — and both are checked on every
>   call, so dropping off Ultra ends live sessions rather than only blocking
>   new ones. **176 of 443 routes are now tier-gated**; `route_map.py` prints
>   the feature column so a hole is visible rather than assumed.
> - **P6 (web)** — `lib/features.ts` (pure) + `lib/use-feature.ts` (hooks, split
>   to avoid the `nav-items → auth-context` cycle); `<FeatureGate>`,
>   `<UpgradeWall>`, `<UpgradeDialog>` and `<UpgradeGate>`; area layouts for
>   fees/staff/timesheet/tasks/lucy/sessions; sidebar padlocks; the `/setup/plan`
>   screen; `errors.ts` now routes its 402 toast there instead of the old dead
>   end. `D-111`'s in-place lock is on the presence table's Remind and Follow-up
>   controls.
> - **P7 (backend + operator queue)** — eight super-admin routes (prices,
>   assign, history, the queue, notes, expiring) and `/platform/upgrades`, where
>   the operator reads who asked, which wall they hit, what it comes to, and
>   sets the plan.
>
> **Still open: P5** (Lucy/MCP tool filtering — largely a no-op while tiers are
> cumulative, since anything that can reach Lucy already has every non-Ultra
> feature), **P8** (the marketing page still advertises the retired ₹100 flat
> price) and **P9** (FEATURE-MAP §9 still describes the Free/Pro world).

**P4 — the gate is live.** `feature_gate` sits beside the role guards in
> `core/dependencies.py` and is applied at `include_router` level in
> `api/v1/router.py`, so the whole tier map is one readable file. Eleven modules
> gated: boards/tasks/recurring, staff, sessions and lucy at `max`; homework
> analytics, assessments and main-exams and fees at `pro`; oauth at `ultra`.
> `/auth/me`, the session and the org switcher carry `features[]`, computed from
> an `Organization.features` property so there is one source. 31 tests in
> `test_feature_gate.py`.

### A note for whoever builds P4

Two things found while building P1–P3 that are not obvious from the plan:

- **`created_at` cannot order an append-only log.** Its `now()` default is the
  *transaction* timestamp, so two appends in one transaction tie and the
  history sorts arbitrarily. `assign_plan` and `add_note` stamp
  `datetime.now(UTC)` in Python instead. Any new append-only table here should
  do the same.
- **The operator writes across org boundaries.** `require_super_admin` lifts
  the RLS GUC, which is right for reading every school but leaves an INSERT
  with no org to satisfy the policy's WITH CHECK. `TierService.assign_plan`
  sets the scope around the write, the same dance as
  `PlatformService.create_school`.

---

## §0 What already exists (verified, 2026-08-08)

Not a survey — these are the facts the plan builds on.

| Thing | Where | State |
|---|---|---|
| `organizations.plan` | `models/org.py:64` | `CHECK (plan IN ('free','pro'))` — **blocks max/ultra until migrated** |
| `organizations.plan_status` | `models/org.py:68` | `CHECK IN ('none','active','grace')` |
| `PlanLimits` | `core/plans.py` | 6 fields, **all task-management concepts** — boards, members, report_days, report_card, attachments, critical. Knows nothing about any school module. **Deleted by `D-109`.** |
| Enforcement | 4 call sites | `enforce_board_quota`, `enforce_member_quota`, `enforce_critical_allowed`, `enforce_attachments_allowed` + `services/org.py:49`, `jobs.py:210` |
| `PlanLimitError` | `core/exceptions.py:52` | 402, `code="plan_limit"`, carries `{feature, limit, current}` — **reuse it, add `required_tier`** |
| Client handling | `web/src/lib/errors.ts` | Already turns `plan_limit` into a toast + "Upgrade" action (pointing at a screen that does not exist — §1.6) |
| Razorpay billing | `services/billing.py` | ₹500/month **flat per org**, webhook-driven, stub mode without keys |
| `/auth/me` | `schemas/auth.py:86` | `OrgOut` **already carries `plan`** — the web can read it today |
| Lucy tier seam | `services/lucy/registry.py:153` | `TIER_DOMAINS: dict = {}` + `domains_for_tier()` — the filter is written, the *mapping* is empty |
| Toolset vocabulary | `services/lucy/domains.py` | 13 domains named after FEATURE-MAP feature-ID prefixes |
| `agent_access` | `models/org.py:62` | Per-org MCP/connector kill switch (`off` by default), enforced in `api_tokens.py:193` + `oauth.py:362` |
| The action rail | `services/insights/actions.py` | `followup_assigned` · `substitute_assigned` · `task_reassigned` · guardian reminders — **every red row's button, and most of them create Tasks** (§1.5) |
| Guardian messaging | `notify_guardian.py`, `config.py:183` | WhatsApp Business API + MSG91 SMS — **real per-message cost** (§1.7) |
| Lead queue pattern | `models/marketing.py` | `demo_requests` + append-only `demo_request_notes`, `/platform/enquiries` screen — **copy this shape for upgrade requests** |
| Operator screens | `endpoints/platform.py`, `web/.../platform/` | list · create · enter · setup pack · readiness · handover · enquiries · catalogue |

Schema head is `d7e8f9a0b1c2`. **Run `uv run alembic current` before believing that.**

---

## §1 Decisions and their consequences

### D-106 — per-student tiers replace the ₹100 flat price, and **the price is data**

The published ₹100/student/month with a 500-student minimum, and `billing.py`'s
₹500/month flat per org, are both retired. Four tiers: free · ₹10 · ₹25 · ₹80 per
student per month.

> Founder: *"the plan number and costing might change regularly because we are just
> launching."*

That sentence is an architectural requirement, not a caveat. Three consequences:

1. **One module owns the price.** A number that moves monthly cannot be duplicated
   in `billing.py`, the marketing page, the pricing calculator and the upgrade wall.
   All four read one server-provided list.
2. **The list price is operator-editable without a deploy.** Same reasoning that
   put the observance catalogue in the database rather than a file in the repo
   (`platform.py`, "one curation serves every school"). A `plan_prices` table the
   operator edits beats a constant we redeploy to change.
3. **A school is billed at what it was sold, not at today's list price.**
   `plan_changes.monthly_amount_snapshot` (§4) is what makes the list price safe to
   move: raising ₹10 → ₹15 must not silently reprice every existing school. The
   snapshot is the invoice; the list is the quote.

**Also retired:** the "below 500 students we are not a fit" note in
`models/marketing.py:33`. A free tier makes small schools a funnel, not a misfit.

### D-107 — capture is never gated

> Founder: *"capturing student routine should be in free tier so move the homework
> logging and classwork logging to the free tier."*

This matches FEATURE-MAP §9.7 and P1v2 exactly. The rule, stated once so it settles
every future argument:

> **Free buys the act of recording. Paid buys the record over time.**

A free school marks the register, logs the lesson, logs homework, sizes the
syllabus and runs its ABC programme — every daily capture surface, in full. What it
does not get is the boards that turn a year of that into a picture: the check-sheet
desk, the class-log board, Students → Academics, the trend charts, the history.

This is also why it is the right commercial shape. The free school spends a term
building a record it cannot yet read; the upgrade is one switch away from a year of
its own data, not a leap of faith. A paywalled capture loop would have sold an
empty board.

**Judgment call inside this:** exam marks entry *is* a capture act, but exams are a
term event, not the daily routine, and the brief put "exams screens monitoring" in
pro. **Exams stay wholly pro** — cycles, marks, result sheets, trends. (Q8 if you
want to revisit.)

### D-108 — the parent portal and parent communications are `max`

The read-only portal, guardian logins, OTP delivery and the reach insights all
move together. See §1.7 for the one piece of this that cannot be a clean line.

### D-109 — the legacy quotas die; Tasks is all-or-nothing at `max`

> Founder: *"the legacy board and member quota for tasks won't survive — if they
> take max plan complete task module will be available."*

Delete all four enforcement functions and their call sites. `enforce_member_quota`
was capping a *school* at 8 members, which no school is; `attachments` and
`critical` are Tasks-module concepts and ride along. `PlanLimits` as a dataclass
goes with them — `core/features.py` replaces it entirely.

### D-110 — only an admin may raise an upgrade request

A teacher who hits a wall sees the wall and *why*, then: **"Only admins can change
your school's plan — please contact your admin."** No request form, no queue entry.
One locked screen would otherwise generate forty requests from forty teachers for
the operator to dedupe by hand.

### D-111 — a gate has three renderings, not one

> Founder: *"in dashboard we have option to assign task for a teacher like some
> quick actions, so there the user will get popup like upgrade your plan to use
> tasks."*

This is the finding that changes the architecture. A route-level gate cannot express
it: the dashboard is a **free** screen carrying a **max** button. So one feature
check drives three renderings:

| Rendering | Where | Behaviour |
|---|---|---|
| **Nav lock** | `nav-items.ts` → sidebar, bottom bar, menu | Item stays visible with a lock chip. Nothing is ever hidden (founder: *"we show everything on the screen like as it is now"*). |
| **Page wall** | area layouts | The screen is replaced by `<UpgradeWall>` — what the tier unlocks, this school's own price, one button. |
| **Action popup** | in-place, on a button | `<UpgradeGate>` wraps the control. The row, the number and the diagnosis all still render; the *button* opens the upgrade dialog. |

### 🟠 1.5 The consequence D-111 exposes: the action rail is mostly Tasks

`services/insights/actions.py` is DASH3's action rail — "every button on every red
row". Its four verbs are `followup_assigned`, `substitute_assigned`,
`task_reassigned` (all create or move **Tasks** → `max`) and the guardian reminder
(**parent comms** → `max`). The rail is spread across seven dashboard components:
`overview`, `presence`, `presence-tables`, `syllabus`, `daybook`, `homework`,
`now-board`, `cover-sheet`.

So on free and pro, **every button on the rail is gated even though every row is
free.** That is coherent and worth saying out loud on the upgrade wall:

> **The dashboard tells you what is wrong on free. Acting on it in one tap is
> what you are buying.**

The diagnosis stays free — the red row, the named child, the reason. The dispatch is
paid. `<UpgradeGate>` on the rail's buttons is the single biggest UI surface in P6.

### 🔴 1.6 Still true from the first pass — the gate must be server-side

Blocking screens is a `web/` concern; the same data sits behind **420 API routes,
45 Lucy tools and the MCP connector**. A `pro` school would read its `max` timesheet
by asking Lucy. Three gates, one source of truth (§3).

And the current "Upgrade" CTA in `errors.ts` points at `/settings` → `/setup/settings`,
which has **no plan section at all** — no billing screen was ever built in `web/`.
The upgrade screen is net-new.

### 🟠 1.7 New: a free tier that sends WhatsApp messages costs us money

`config.py:183` wires the WhatsApp Business API and an MSG91 SMS fallback. Both bill
per message. D-107 puts homework logging on free, and P3 says the teacher's reward
for logging homework is that guardians are auto-notified — but D-108 puts parent
communications on `max`.

Those two cannot both hold literally. Three ways out, in preference order:

1. **Absence alerts free, homework auto-notify free but volume-capped, everything
   else max.** The absence alert is safety-critical and is the school's legal-ish
   duty of care; capping homework notifications bounds the cash cost without
   breaking P3. *Recommended, and the default this plan builds unless told otherwise.*
2. Homework auto-notify at `pro`. Cleaner line, but P3 is weaker on free — the
   teacher logs and nothing visibly happens.
3. All guardian messaging at `max`. Cheapest for us, and the least defensible: a
   parent hears nothing when their child is absent because the school is on free.

Note the portal itself (D-108) is a different question from outbound messages — the
portal costs us nothing per parent. **This is Q7 and the only open question that
changes the free tier's shape.**

### 🔴 1.8 The Razorpay webhook will silently overwrite a hand-set plan

`billing.py:handle_webhook` writes `org.plan = "pro"` on activate and `_downgrade`
writes `"free"` on cancel — **with no check on how the plan got there**. One replayed
webhook downgrades a school the operator just put on ultra. Add
`organizations.plan_source` (`manual`|`billing`) and make the webhook refuse to touch
a `manual` org.

### 🟡 1.9 Law 3 applies to plan changes

A plan assignment is a *decision* — who put this school on max, when, at what price —
not a typo. **Append row, never a bare `UPDATE`** (`plan_changes`, the same shape as
`plan_approvals` over `plans.status`).

### 🟡 1.10 Gates compose with roles; they never replace them

`feature_gate` runs **alongside** the role guard. The two hard rules survive tiering
unchanged: **teachers never see fees** even on ultra (except `D-83`), and **band
tiers never reach parents** even on ultra. `ultra` is a *precondition* for MCP —
`agent_access` stays the per-org kill switch on top of it.

### 🟡 1.11 Toolsets are too coarse to carry the tiers

`TIER_DOMAINS` maps tier → **domain**, but `capture` holds attendance, homework *and*
lesson logs (all free under D-107) while `planning` holds syllabus (free) and the
timetable. Add `feature: Feature` to `ToolSpec` and filter on that; `TIER_DOMAINS`
becomes `TIER_FEATURES`. `tests/test_tool_registry.py` gains the assertion that every
tool names a feature, exactly as it asserts `domain` today.

### 🟡 1.12 "Exam OCR / auto-capture" does not exist

No OCR anywhere in `api/app/services/ai/`. `ai/scores.py` and `ai/exam_analysis.py`
work from typed input. List it on the `max` card as coming; it cannot be what sells
`max` this quarter.

### 🟡 1.13 Manual plans need an expiry story (Q4, still open)

A hand-set plan with no end date never lapses. `ENABLE_SCHEDULER` is `false` in the
current `.env` mode, so this plan defaults to **`plan_expires_at` + an operator
"expiring soon" list** — no scheduler, no background downgrade, and the operator is
in that screen weekly anyway. A nightly auto-downgrade job can come later.

---

## §2 The tier map (decided)

**Cumulative** — each tier includes everything below it.

### free — *the record exists*
Every capture surface, in full (`D-107`).

Students → **Directory** · **My Day** + the period card · **Attendance** (all
surfaces) · **Homework logging** · **Classwork / lesson logging** · **Syllabus &
Plan** (plan, week, my-subjects, my-class/syllabus, chapter sizing) · **Events,
observances & DOB** · **ABC bands** (whole area) · the **daily report** · **absence
alerts to guardians** · Setup, Members, Account
Dashboard: the **Attendance** and **Syllabus** tabs — *read-only; the action rail is
gated (§1.5)*

### pro — *the record becomes a picture* · ₹10/student/month
**Homework check-sheet desk** + day book · **Class-log board** ·
**Students → Academics** (the whole half: class logs, homework, analytics, trends,
report cards) · **Exams** end to end (cycles, marks, result sheets, monitoring,
bands/exams) · **Fees** (collection, structures, ledgers, follow-ups — admin only,
always)
Dashboard: the **Homework**, **Exams** and **Fees** tabs

### max — *the school runs itself* · ₹25/student/month
**Staff** (directory, leave, month, today, substitutions, operating board) ·
**Timesheet** · **Teacher workload** · **Task management** — the complete module,
no quotas (`D-109`) · **Sessions** (hostel/activity) · **Parent portal + parent
communications** (`D-108`) · **AI Lucy** · **advanced exams** (script-photo capture,
OCR — ⚠️ unbuilt, §1.12) · **the dashboard action rail** (`D-111`, §1.5)
Dashboard: the **Staff** and **Tasks** tabs

### ultra — *the school connects* · ₹80/student/month
**MCP connections** — the connector, OAuth 2.1, API tokens, `/setup/connections`,
`/oauth/consent`, `/agent/*`. Composes with `agent_access`, which stays the per-org
switch.

> One open item above this line: **Q7** (§1.7) decides whether homework auto-notify
> sits in free capped, or in pro. Everything else is decided.

---

## §3 The architecture — one vocabulary, three gates

The most-repeated defect in this codebase is the same fact computed two ways
(CLAUDE.md, "One computation, many renderings"). A tier is exactly that kind of
fact — and under `D-106` it is a fact that *changes monthly*. So **one module owns
it, and nothing re-derives it, in Python or in the browser.**

### `api/app/core/features.py` — new, the single source

```python
class Feature(StrEnum):                # IDs match FEATURE-MAP §2–§7 prefixes
    CAPTURE_ATTENDANCE = "capture.attendance"      # free
    CAPTURE_HOMEWORK   = "capture.homework"        # free  (D-107)
    CAPTURE_LESSON_LOG = "capture.lesson_log"      # free  (D-107)
    PLAN_SYLLABUS      = "plan.syllabus"           # free
    BANDS_PROGRAMME    = "bands.programme"         # free
    STUDENTS_ACADEMICS = "students.academics"      # pro
    EXAMS_BOARD        = "exams.board"             # pro
    FEES_COLLECTION    = "fees.collection"         # pro
    STAFF_ROSTER       = "staff.roster"            # max
    TASKS_BOARDS       = "tasks.boards"            # max  (D-109)
    INSIGHTS_ACTIONS   = "insights.actions"        # max  (D-111, §1.5)
    PARENT_PORTAL      = "parent.portal"           # max  (D-108)
    AGENT_LUCY         = "agent.lucy"              # max
    AGENT_MCP          = "agent.mcp"               # ultra
    ...

TIERS = ("free", "pro", "max", "ultra")                 # ordered, cumulative
TIER_FEATURES: dict[str, frozenset[Feature]] = {...}

def features_for(plan: str) -> frozenset[Feature]       # cumulative union
def has_feature(org, f) -> bool
def tier_for(f) -> str                                  # the tier that unlocks it
def require_feature(org, f) -> None                     # raises PlanLimitError(required_tier=…)
```

`PlanLimitError` gains `required_tier` and `feature_label` in `details`. The existing
402 / `plan_limit` contract is preserved, so `errors.ts` keeps working.

**Prices live elsewhere** (`D-106`): `core/features.py` owns *what a tier contains*;
a `plan_prices` table owns *what it costs*. They change on completely different
clocks — the map moves when we build something, the price moves when we feel like it.

### Gate 1 — the API (a dependency, not a service call)

```python
router = APIRouter(dependencies=[Depends(feature_gate(Feature.FEES_COLLECTION))])
```

Applied at **router** level where a whole module is one feature (fees, staff,
timesheet, tasks/boards/recurring, lucy, sessions, parent, agent, oauth) and at
**route** level for the mixed ones (`insights`, `dashboard`, `students`, `my_class`,
`main_exams`). It lands in the dependency tree, so **`scripts/route_map.py` can print
a `feature` column** and coverage becomes verifiable instead of asserted.

⚠️ `homework.py` and `classroom.py` are now **free** — they are capture. Do not gate
them by reflex; the boards that read them are what's gated.

### Gate 2 — Lucy + MCP (schema time, never an error)

`ToolSpec` gains `feature`. `visible_tools()` becomes a five-filter chain —
`role → transport → scope → tier → feature` — and the Lucy loop and the agent
principal both pass `plan=org.plan`. A tool the school has not bought is **absent**,
exactly like the role filter. Note Lucy herself is `max`, so on free/pro the whole
tool surface is moot; the filter matters for `ultra`'s connector, where a school on
ultra still must not reach a feature it… has, by definition, all of. **The filter's
real job is `max`-without-`ultra` and any future non-cumulative tier.**

### Gate 3 — the web (visible, locked, explains itself)

`/auth/me` → `OrgOut` gains `features: string[]`, **server-computed**, so the browser
never re-derives the mapping.

- `lib/features.ts` — `useFeature(f)` reading `me.org.features`. No tier names in
  component code; a component asks for a *feature*, never for `plan === "max"`.
- `nav-items.ts` — each `NavItem` gains `feature?: Feature`. Nothing is hidden; the
  sidebar, bottom bar and menu render a lock chip.
- `<FeatureGate feature=…>` in the area layouts (`plan/`, `bands/`, `setup/` exist;
  add `fees/`, `staff/`, `timesheet/`, `tasks/`, `lucy/`, `sessions/`).
- `<UpgradeGate feature=…>` wrapping individual controls — the action rail (§1.5),
  the dashboard quick actions, any button on a free screen that reaches a paid verb.
- `<UpgradeWall>` / `<UpgradeDialog>` — one component, two presentations. Shows what
  the tier unlocks, this school's own monthly price (list price × its student count),
  and:
  - **admin** → "Request upgrade", or the pending state if a request is open;
  - **teacher** → "Only admins can change your school's plan — please contact your
    admin." No form (`D-110`).

---

## §4 Data model

Three new tables. `plan_changes` and `upgrade_requests` are org-scoped and need an
`org_isolation` policy (law 2) — unlike `demo_requests`, which is platform-level and
deliberately has none. `plan_prices` is platform data (no `org_id`, no RLS,
super-admin writes) — the same shape as the observance catalogue.

**`plan_prices`** (`D-106`) — `plan`, `amount_paise_per_student`, `currency`,
`effective_from`, `created_by`, `created_at`. Append-only: the current list price is
the newest row per plan, and history is why an old quote can be explained.

**`plan_changes`** — append-only (law 3). `org_id`, `from_plan`, `to_plan`,
`changed_by_user_id`, `reason`, `student_count_at_change`,
`monthly_amount_snapshot`, `effective_from`, `expires_at`, `created_at`.
The **amount is snapshotted, never recomputed** — students change and the list price
moves (`D-106`), an invoice does not. `organizations.plan` remains the derived cache
of the newest row.

**`upgrade_requests`** + **`upgrade_request_notes`** — the exact shape of
`demo_requests` / `demo_request_notes`. `org_id`, `requested_plan`,
`requested_by_member_id`, `feature_id` (**which wall they hit** — the product-signal
column, and the reason to build this properly rather than as an email link),
`message`, `status` (`new|contacted|won|lost`), plus an append-only note trail
carrying every status move and remark.

**Columns on `organizations`:** `plan_source` (`manual`|`billing`, default `manual`)
and `plan_expires_at` (nullable).

**Migration:** widen `plan_valid` to `('free','pro','max','ultra')`. Everything else
is additive with a server default, so prod migrates before code deploys.
⚠️ **Grep `alembic/versions/` for a free revision id** — the obvious next id is
usually taken, and reuse makes Alembic report a revision cycle across the graph.

---

## §5 Build order

Nine packets. Each is independently green (`pytest` + `ruff`; `tsc --noEmit` +
`eslint` + `next build`).

| # | Packet | Done when |
|---|---|---|
| **P1** | `core/features.py` — the `Feature` enum, `TIER_FEATURES`, `features_for`/`has_feature`/`tier_for`/`require_feature`; `PlanLimitError.required_tier`. **Delete `core/plans.py`'s four enforcers and their call sites** (`D-109`) | Unit tests over all four tiers; `ruff` clean; nothing imports `PlanLimits` |
| **P2** | Migration: widen the CHECK, `plan_source`, `plan_expires_at`, `plan_prices`, `plan_changes`, `upgrade_requests(+notes)` + RLS policies | `alembic upgrade head` on the **test DB first**; `test_rls.py` green in **LOCAL** mode |
| **P3** | `services/plans.py` — assign a plan (append + cache + snapshot), list/edit prices, raise a request, the operator queue. Webhook refuses `plan_source='manual'` (§1.8) | Negative test: a webhook cannot move a manual org. Price-change test: an existing school's snapshot does not move |
| **P4** | **API gate** — `feature_gate` across the 36 routers; `route_map.py` prints the feature column; `/auth/me` carries `features[]`; `GET /plans` (public price list) | A **402 negative test per gated router**; `route_map.py --json` shows no ungated route in a gated module; **an explicit test that `homework`/`classroom` capture routes are NOT gated** (`D-107`) |
| **P5** | **Lucy + MCP gate** — `ToolSpec.feature`, five-filter `visible_tools`, plan passed from the loop and the agent principal | `test_tool_registry.py` asserts every tool names a feature; a `pro` org's schema excludes `max` tools |
| **P6** | **Web** — `lib/features.ts`, nav lock chips, `<FeatureGate>` in the area layouts, **`<UpgradeGate>` across the seven action-rail components** (`D-111`, §1.5), `<UpgradeWall>`/`<UpgradeDialog>` with the admin/teacher split (`D-110`), the new `/setup/plan` screen, fix the `errors.ts` dead-end CTA | Walk all four tiers in a browser, both themes; a teacher account sees the "contact your admin" copy, never a form |
| **P7** | **Operator** — Plan column + filter on `/platform`, plan-change action with reason (writes `plan_changes`), `/platform/upgrades` request queue with append-only notes, the price editor (`D-106`), the expiring-soon list (§1.13) | Operator moves a school across all four tiers, edits a price, and reads the history |
| **P8** | **Marketing** — four-tier pricing section reading `GET /plans`, rewrite `PricingCalculator`, drop the 500-student note in `models/marketing.py` | Site pricing is **fetched, not typed** — changing a price needs no deploy (`D-106`) |
| **P9** | Update `FEATURE-MAP.md` §9 from "what does not exist" to as-built; add `D-106`…`D-111` to the decisions log | The docs no longer describe a Free/Pro world |

**Regression gate throughout:** the full backend suite (811 as of `2c2172f`) stays
green. Expect churn in `test_phase4.py` (asserts `plan_limit`) and anything asserting
`plan == "pro"` or the deleted quotas.

**Suggested first cut if you want something on screen fast:** P1 → P2 → P4 → P6's
nav-lock + `<UpgradeWall>` only. That gives a real, enforced, visible gate before the
request queue and the price editor exist, and the operator can still move plans by
hand with a SQL update in the meantime.

---

## §6 Open questions

| | Question | Why it blocks | Default if unanswered |
|---|---|---|---|
| **Q7** | Guardian messaging on free — absence alerts free + homework notify capped, or homework notify at pro? (§1.7) | It is the only thing left that changes the free tier's shape, and it has a real per-message cash cost | Option 1: absence free, homework free but capped |
| **Q4** | Do manual plans expire — scheduler job or operator list? (§1.13) | ⚠️ `ENABLE_SCHEDULER` is `false` in the current `.env` mode | `plan_expires_at` + an operator "expiring soon" list, no job |
| **Q8** | Exam **marks entry** is a capture act — does it follow `D-107` into free, or stay pro with the rest of exams? (`D-107`) | One route group either side of the line | Stays pro — exams are a term event, not the daily routine |
