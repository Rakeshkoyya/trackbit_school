# TrackBit v2 — Implementation Action Plan

**Companion to [trackbit-prd-v2.md](trackbit-prd-v2.md). The PRD says *what*; this document says *how, in what order, and by whom*.**

| | |
|---|---|
| **Date** | 2026-06-11 · **Rev 1.1** 2026-06-12 (founder vision update: landing page + 5-min setup, Flutter native track, Free/Pro billing) |
| **Build mode** | Solo founder + AI agents (tasks written as independent, dispatchable packets) |
| **Approach** | Greenfield rebuild. Old repos (`school_ops_sv`, `school_ops_ui`) are reference + component quarry only. No data migration. |
| **Status** | Ready to execute |

---

## 1. Build decisions locked in this planning session

These extend the PRD's locked decisions (D1–D12). Do not re-litigate during build.

| # | Decision | Rationale |
|---|---|---|
| B1 | **Greenfield rebuild** in new folders `trackbit_api/` (FastAPI) and `trackbit_web/` (Next.js). Existing data is discarded. | PRD schema (UUID, orgs, boards, append-only events) is incompatible with v1 (BigInt, projects, RBAC). Removing RBAC/menu-screens/role-assignment in place costs more than rebuilding. Clean codebases are also dramatically better for agent-driven development. |
| B2 | **Reuse the v1 UI kit, not the v1 pages.** Copy over `src/components/ui/*` (shadcn), the TanStack Query provider, the api-client pattern, and the toast/sonner setup. Do **not** copy pages, contexts, guards, or the data-table (v2's views are simpler and mobile-first). | Saves ~a week of component plumbing without dragging in v1 assumptions. |
| B3 | **WhatsApp/Interakt is out of the v2 critical path.** All notification code goes through a channel-adapter interface (`email`, `push`, `whatsapp`); only `email` + `push` ship at launch. WA is a parallel track that can land any time after Phase 2 without touching core code. | Per founder decision. Meta approval no longer gates anything. |
| B4 | **Onboarding without WhatsApp:** admin-creates-account produces a **shareable magic invite link** (copy button + native share sheet). Admin pastes it into their own WhatsApp/SMS chat with the staffer. Email invite remains the secondary automated path. | Preserves the PRD's phone-first, no-password onboarding spirit (D11/F2) with zero external dependencies. When Interakt lands, the same link gets sent automatically. |
| B5 | **Gamification = "lighter" celebration layer** (spec in §3). No points, no leaderboard, no streak-loss. Entirely derived from existing data (`task_events`); zero new tables. | Per founder decision; aligns with north star "reduce the dread of being managed." |
| B6 | **PRD open questions resolved:** O1 → 30-min default confirmed; store `remind_before_minutes` on instances now (nullable, default 30) so per-task override later is a UI change, not a migration. O2 → quiet expiry for recurring misses. O3 → moot (B3). O4 → digest fixed-on in v2; store a `notification_prefs` JSONB on memberships now, wire the opt-out UI later. O5 → Cloudflare R2 (S3-compatible, cheap egress) — only needed in Phase 4. | Keeps schema future-proof while cutting scope now. |
| B7 | **Email provider: Resend. Push: standard Web Push (VAPID) via the PWA service worker.** | Simplest credible production setup. |
| B8 | **Org timezone governs everything** ("today", due times, digests, materializer). The client always renders in org TZ. Users in v2 belong to one org in the UI (schema supports many via `memberships`; the org-switcher is deferred). | A 5–25 person micro-org is in one timezone. Removes a whole class of bugs. |
| B9 | **A public landing page is the front door, and setup is a timed "5-minute" ritual.** Landing = product facts, how-it-works, pricing teaser, register CTA. Registration → members-invited must be realistically achievable in ≤ 5 minutes, and we instrument that duration. | Founder vision (Rev 1.1). First impression + activation speed are the funnel. |
| B10 | **Flutter native app (Android-first) is a parallel track — Track FL — not a launch gate.** Web ships M1–M3 first; the Flutter app consumes the same API, becomes the primary *member* mobile experience, and unlocks what PWA can't: FCM, exact alarms, full-screen alarm-style reminders for critical tasks, and (future, out of v2) call-style escalation. | Founder vision (Rev 1.1). Native alarm capability is the differentiator for ground-level staff; web push can't do it. |
| B11 | **Billing = two plans only: Free and Pro at ₹500/month flat per organization** (Razorpay Subscriptions). The PRD's per-seat "team" tier is dropped. The core loop (create/assign/claim/complete/recur/celebrate) is never paywalled — limits land on boards, members, report depth, and premium extras (proposal in R6). | Founder vision (Rev 1.1). One price, whole org — dead simple to sell to micro-orgs. |

---

## 2. PM review — gaps found in the PRD, and the fixes

I reviewed the PRD as a product manager against the v1 implementation and the stated north star. These gaps are now **part of the spec**; each one maps to tasks in §5.

### G1 — The celebration layer is a north-star promise with no spec
The PRD says "celebrate done" but specifies only the all-done screen. §3 below is the full spec. (Tasks: P3-FE-01…04)

### G2 — Members screen shows "Last active" but no schema supports it
S8 displays a Last-active column; no table stores it. **Fix:** add `memberships.last_active_at`, updated (throttled, max once/5 min) by the auth middleware. (Task: P0-BE-02)

### G3 — Tasks can never be deleted or cancelled
The API surface has no delete, and `status` only allows `open/done/missed`. Mistyped tasks would live forever. **Fix:** add `cancelled` status + `cancelled` event type. Cancel is available to the task creator and org admins; cancelled tasks are excluded from all reports and hidden from Home/board default views (visible under a filter). Append-only integrity preserved — no hard deletes. (Tasks: P1-BE-06, P1-FE-05)

### G4 — Task editing is unspecified in an open model
Anyone can create and assign — but who can edit a title/description/due? **Fix:** anyone who can see the board can edit; every edit appends an `edited` event with a field-level diff in `payload`. Visibility *is* the governance, same as assignment. (Task: P1-BE-05)

### G5 — Tasks with no due date have no home
S1 sections are Overdue / Due today / Anytime today / Claimable — but where does a dateless task live? **Fix:** assigned tasks with `due_at IS NULL` appear in **Anytime today** every day until done (they are never "missed"). This makes "Anytime today" a real bucket, not a leftover. (Task: P1-BE-07)

### G6 — Old overdue items will stack into a shame wall
One-time misses "surface in Overdue" forever — directly violating "misses never stack into shame." **Fix:** Overdue section shows at most items from the **last 7 days**; older open items collapse into a single calm row: *"3 older tasks — review"* → opens a review list where each can be completed, re-dated, or cancelled. (Tasks: P1-BE-07, P1-FE-03)

### G7 — No activation instrumentation exists
F1 names the activation event ("first task assigned to someone else gets completed") and says *instrument this* — but nothing in the PRD stores product analytics. **Fix:** a minimal `analytics_events` table (event name, org, user, props, ts) + a tiny `track()` helper called from ~10 key code paths. A dashboard query, not a BI stack. (Task: P0-BE-06)

### G8 — Empty states are unspecified, and this product's first-run is mostly empty states
A brand-new org sees an empty Home, one empty board, no members. Every empty state must teach the next action:
- **Home, no tasks ever:** "Your day will show up here. Create your first task →"
- **Home, all done (has history):** the celebration ritual (§3).
- **Board, empty:** ghost rows + "+ Add the first task".
- **Boards list, only General:** "Boards keep work separated — create one for each area of work."
- **Done/History, empty:** "Tasks you complete will build your record here."
(Task: P1-FE-08)

### G9 — Undo semantics must be event-true
The 5-second undo toast calls `/reopen` — it must append a `reopened` event, never delete the `completed` event. Reports compute **net state** from the event chain. The celebration trigger must also debounce: undo within the toast window suppresses the "done for today" screen. (Tasks: P1-BE-04, P1-FE-04)

### G10 — Notifications policy assumed WhatsApp as primary
With B3, the channel ladder becomes: **push if subscribed → email fallback**; assignment/pass = instant; reminders/digests per PRD §9 timings. The `notifications` table and sweep are channel-agnostic already — only the adapter set changes. The nudge button works day 1 via this ladder. (Tasks: P2-BE-04…07)

### G11 — Auth lifecycle gaps
PRD has magic links but no logout-everywhere, no token rotation, no rate limits. **Fix (minimum production bar):** refresh-token rotation, magic-link single-use + 72 h expiry (invite links: 7 days), rate limiting on auth + claim endpoints (slowapi), session revocation on member removal. (Tasks: P0-BE-04, P1-BE-09)

### G12 — "Claim" race is specified, "complete" race is not
Two people can tap complete on the same claimable task from the board view. **Fix:** `/complete` is also a conditional update (`WHERE status='open'`); the loser gets a friendly "Already done by Priya ✓" toast, not an error. (Task: P1-BE-04)

---

## 3. The celebration & return-loop layer (spec)

Design principle: **variable, earned, and quiet by default.** Celebration psychology that works long-term avoids two failure modes: constant confetti (habituates in a week) and loss-framed streaks (creates dread — the exact thing the north star forbids). Everything below derives from `task_events` — no new tables.

### 3.1 The completion moment (every single completion)
- Checkbox fills with a **150 ms spring animation** + haptic tap (mobile). The row settles to a calm "done" state, then **gently slides out** after ~800 ms (the list visibly shrinks — progress you can feel).
- A **day-progress indicator** in the Home header ("3 of 5") ticks up with a micro-animation. Goal-gradient effect: people accelerate as the bar approaches full.
- **Variable reward:** roughly 1 in 7 completions (random, not scheduled) triggers a slightly richer animation (brief sparkle burst). Unpredictability is what makes it addictive; predictable confetti becomes wallpaper.
- Undo toast (5 s) sits at the bottom and never blocks the next tap.

### 3.2 The "done for today" ritual (the product's signature moment)
When the last item of today clears: full-screen takeover. Big ✓, "You're done for today," today's count, **one** contextual line of meaning, rotated:
- "That's 4 days in a row finishing everything." (only when an active all-clear run ≥ 2 days exists — **never** shown as lost/broken)
- "12 tasks this week — your best week yet." (personal record, only when true)
- "Quiet day tomorrow — 2 things scheduled." (forward peek, builds tomorrow's return intent)
- Default: a calm rotating affirmation ("Nothing is waiting on you.")
No buttons except a soft "Done" dismiss. No upsell. This screen is the permission-to-stop ritual and the #1 reason members will open the app tomorrow.

### 3.3 Done / History as a trophy room (S10, expanded)
- **Dot calendar** (last ~10 weeks): each day a dot — filled = all-clear day, half = partial, empty = nothing due. Reads as a mosaic of effort, never as a broken chain (no "streak lost" framing, no red).
- Weekly count + personal best ("Best week: 18, May 12–16").
- Completed list grouped by day, newest first, each row showing board + time.

### 3.4 Weekly recap (Monday 8 AM, replaces that day's digest)
"Last week: 23 done · 87% on time · busiest day Wednesday." One positive stat, one gentle forward look. Delivered via the digest channel; also a dismissible card at the top of Home on Monday.

### 3.5 First-run aha (new member's first 60 seconds)
The magic-link landing shows a **2-step spotlight** (not a tour): (1) "This is your day" highlight on Home, (2) "Tap to finish" on their first task. Their **first-ever completion** always triggers the rich celebration + "That's how it works. See you tomorrow 👋". Instrument this moment (G7).

### 3.6 Admin return loop
The admin's "celebration" is the 6 PM report card (F7) — their ritual is *closing the org's day*. Report card copy mirrors member tone: "SHANA Ops today: 82% · 3 still open" with one-tap nudges. Never "Anil failed."

---

## 4. Target architecture

```
D:\real_projects\task_management\
├── school_ops_sv/        (v1 backend — reference only, untouched)
├── school_ops_ui/        (v1 frontend — component quarry, untouched)
├── trackbit_api/         (NEW — FastAPI + SQLAlchemy 2 + Alembic + APScheduler)
├── trackbit_web/         (NEW — Next.js App Router, PWA, mobile-first; landing + admin + member web)
└── trackbit_app/         (NEW, Track FL — Flutter, Android-first; member-focused native client)
```

**Backend** — FastAPI, Postgres (Aiven), SQLAlchemy 2.0, Alembic, APScheduler in-process behind `ENABLE_SCHEDULER` flag (v1 pattern, proven; Celery only if scale demands later). Schema exactly per PRD §8.2 **plus** the deltas from §1–2 of this doc:
`memberships.last_active_at`, `memberships.notification_prefs jsonb`, `task_instances.remind_before_minutes int default 30`, `task_instances.status` adds `cancelled`, `task_events.event_type` adds `edited`, `cancelled`, `analytics_events` table, `auth_tokens.purpose` adds `invite`, `refresh`, **`device_tokens` table** (per-user push registrations: platform `fcm|webpush`, token, last_seen — Track FL consumes this), **`task_instances.is_critical bool default false`** (+ same on templates, inherited) gating native alarm-style reminders.

**Layering rule (the one architectural law):** every service function takes `org_id` from authenticated context — never from request params. One `visibility.py` module owns `can_view_board / assignable_pool / dashboard_scope`; endpoints may not inline these checks. All task state changes go through one `events.py` writer that appends the event and mutates the instance in the same transaction.

**Frontend** — Next.js App Router. Routes: `/(member)` group: `home`, `boards`, `boards/[id]`, `task/[id]`, `done`; `/(admin)` group: `dashboard`, `members`, `settings`; `/auth/*`, `/join/[token]`, `/onboarding`. Bottom tab bar (mobile) / sidebar (desktop ≥ lg). TanStack Query with optimistic mutations for complete/claim/reassign. PWA: manifest + service worker (Serwist) + Web Push. The public landing page lives in this app (static, unauthenticated, fast). Once Track FL ships, the Flutter app becomes the primary member mobile client; the web member views remain for desktop and uninstalled users.

**Explicitly dropped from v1:** RBAC/permissions/menu-screens, super-admin tier, projects, task categories, task-view-styles, evo-points ledger, attendance/exams/students/fees/holidays, Google OAuth (email+password, magic links, and invite links cover v2; OAuth can return later).

---

## 5. Work breakdown — task packets

Each packet is sized for one focused agent session (S ≈ ½ day, M ≈ 1 day, L ≈ 1.5–2 days solo-equivalent). **Deps** gate ordering; anything with the same batch letter can run in parallel. Every packet ends with its **Done-when** checklist — treat these as acceptance tests.

### Phase 0 — Foundations (Batches A → B)

| ID | Size | Deps | Task |
|---|---|---|---|
| **P0-BE-01** | M | — | **Scaffold `trackbit_api`.** FastAPI app factory, settings (pydantic-settings), Postgres via Docker Compose, Alembic wired, ruff + pytest, healthcheck route, Dockerfile. Mirror v1's clean layout (`api/v1/endpoints`, `core`, `models`, `schemas`, `services`). **Done-when:** `uvicorn` serves `/health`; `pytest` green in CI-able form. |
| **P0-FE-01** | M | — | **Scaffold `trackbit_web`.** Next.js (App Router, TS, Tailwind), copy `components/ui/*`, sonner, query-provider, api-client pattern from v1 (strip project-header logic). Mobile-first layout shell: bottom tab bar (Home/Boards/Done), desktop sidebar, theme tokens. **Done-when:** shell renders with 3 stub tabs on a 380 px viewport and on desktop. |
| **P0-BE-02** | L | P0-BE-01 | **Full schema + migration 0001.** All tables from PRD §8.2 with §4 deltas (incl. `last_active_at`, `notification_prefs`, `remind_before_minutes`, `cancelled`, `analytics_events`, `device_tokens`, `is_critical`). Indexes per PRD. Postgres RLS policies on org-scoped tables as safety net. Seed script: demo org, 4 users, 2 boards, 12 instances in mixed states. **Done-when:** `alembic upgrade head` from scratch passes; seed loads; RLS denies cross-org reads in a test. |
| **P0-BE-03** | M | P0-BE-02 | **Auth core.** Register-org (F1: org+admin+default "General" board in one transaction), login, JWT access (15 min) + rotating refresh, `get_current_member` dependency that resolves org context and throttle-updates `last_active_at`. **Done-when:** register→login→`/me` round-trip test passes; refresh rotation invalidates old token. |
| **P0-BE-04** | M | P0-BE-03 | **Magic links + invites (B4).** `auth_tokens` issuance/verify (hashed, single-use, expiry: magic 72 h / invite 7 d), `POST /auth/magic-link/request` (email delivery stub → console in dev), invite-link generation returning shareable URL, rate limiting (slowapi) on all auth routes. **Done-when:** invite URL → session created → lands authenticated; reuse of a used token returns 401; 6th rapid request returns 429. |
| **P0-BE-05** | S | P0-BE-02 | **Visibility module.** `visibility.py` implementing PRD §8.3 verbatim (incl. *admins do NOT see private boards they're not on*) + `assignable_pool`. Pure functions + a FastAPI dependency. **Done-when:** unit-test matrix covers admin/member × public/private × member/non-member (8 cases). |
| **P0-BE-06** | S | P0-BE-02 | **Analytics (G7).** `analytics_events` writer `track(org, user, event, props)`, called from: org_registered, member_invited, member_joined, task_created, task_assigned, task_completed, task_claimed, task_passed, all_clear_reached, first_completion. Plus one SQL view: `activation_funnel` (org → first assign-to-other → its completion). **Done-when:** events written from a test flow; view returns the funnel for seed data. |
| **P0-FE-02** | M | P0-FE-01, P0-BE-03 | **Auth screens + session.** Login, register-org (org name + auto-detected editable TZ), `/join/[token]` landing, auth context (token storage, refresh, 401 redirect), route guards by org_role. **Done-when:** full register→login→guarded-route flow works against local API. |
| **P0-FE-03** | M | P0-FE-01 | **Public landing page (B9).** Unauthenticated `/`: one-line promise hero, the problem (Excel + WhatsApp chaos), how-it-works in 3 steps (create boards → assign or leave claimable → everyone sees what's done), who-it's-for strip (schools, sellers, clinics, agencies), pricing teaser (Free / Pro ₹500 per month for the whole org), screenshot placeholders, register CTA → `/auth/register`, login link. Static-rendered, no auth bundle, SEO meta. **Done-when:** Lighthouse ≥ 90 mobile; CTA lands in registration; renders at 380 px and desktop. |

**Batch A (parallel):** P0-BE-01 ∥ P0-FE-01 → **Batch B (parallel):** P0-BE-02 → {P0-BE-03 → P0-BE-04, P0-BE-05, P0-BE-06} ∥ P0-FE-02 (starts once P0-BE-03 is up) ∥ P0-FE-03.

### Phase 1 — The Spine (assign → complete loop)

| ID | Size | Deps | Task |
|---|---|---|---|
| **P1-BE-01** | M | P0-BE-05 | **Boards API.** CRUD per PRD: list (my + other-public, with today's completion fraction), create (default public), patch (rename/visibility-flip/archive), private-board member management. Visibility flip public→private triggers F9 rule: non-members' open tasks → unassigned + notification rows. **Done-when:** endpoint tests incl. the flip-orphaning case; private boards absent from non-members' list responses. |
| **P1-BE-02** | M | P0-BE-05 | **Event writer + task create/read.** `events.py` single-transaction writer. `POST /tasks` (one-time path only; emits `created` + optional `assigned`), `GET /boards/{id}/tasks`, `GET /tasks/{id}` returning the full event chain resolved to names. Server-side `assignable_pool` enforcement. **Done-when:** creating an assigned task yields 2 events; assigning a non-board-member on a private board → 422. |
| **P1-BE-03** | M | P1-BE-02 | **Assign / claim / reassign.** `/claim` atomic (`WHERE assignee_id IS NULL`, loser → 409 + current holder name), `/reassign` (instant remap, `passed` event, `pass_count++`, notification row), assign-on-edit. **Done-when:** concurrent-claim test (two sessions) produces exactly one winner; chain reads created→assigned→passed correctly. |
| **P1-BE-04** | M | P1-BE-02 | **Complete / reopen (G9, G12).** `/complete` conditional on `status='open'` (loser → 200-with-already-done payload), `completed` event, `completed_by`; `/reopen` appends `reopened`, resets status. Reports must derive from net event state. **Done-when:** complete→reopen→complete chain leaves 3 events and final status done; double-complete returns the friendly payload. |
| **P1-BE-05** | S | P1-BE-02 | **Edit semantics (G4).** `PATCH /tasks/{id}` open to anyone who can view the board; appends `edited` event with `{field: [old, new]}` diff payload. Due-date change re-enqueues the reminder row (dedupe-key replace). **Done-when:** edit by a non-creator board member succeeds and the diff event is correct. |
| **P1-BE-06** | S | P1-BE-02 | **Cancel (G3).** `POST /tasks/{id}/cancel` (creator or admin), `cancelled` status + event; excluded from Home, default board view, and all report denominators. **Done-when:** cancelled task vanishes from `/me/today` and report counts but remains fetchable with its chain. |
| **P1-BE-07** | M | P1-BE-02 | **Home endpoint (S1, G5, G6).** `GET /me/today`: overdue (≤ 7 days) + older-count, due-today (timed, ordered), anytime (untimed today + dateless), claimable (my boards), day-progress counts, all in org TZ. Single query set, < 100 ms on seed. **Done-when:** response fixture matches an S1-shaped JSON contract test incl. the 7-day collapse and dateless bucketing. |
| **P1-BE-08** | M | P0-BE-04 | **Members API (S8).** List (role, contact, ✓-channel badge, last-active), add (mode: invite-link | email-invite; returns shareable URL), role change, remove → F9: open instances → unassigned + `edited` events + dashboard flag payload. **Done-when:** removing a member with 3 open tasks produces 3 unassigned claimables and the orphan-count surfaces in the response. |
| **P1-BE-09** | S | P1-BE-08 | **Session revocation (G11).** Member removal + role downgrade invalidate refresh tokens (token-version on membership). **Done-when:** removed member's refresh attempt → 401. |
| **P1-FE-01** | L | P0-FE-02, P1-BE-07 | **Home screen (S1) — the hero.** Sections in PRD order, empty sections hidden, board-name + "passed by X ↩" metadata lines, claim button, day-progress header ("3 of 5"), older-overdue collapse row (G6). Calm amber overdue styling. **Done-when:** matches S1 wireframe content on 380 px; loads from `/me/today` with skeletons. |
| **P1-FE-02** | M | P1-FE-01 | **Optimistic complete loop.** Checkbox → instant strike + slide-out (≈ 800 ms) → background sync → 5 s undo toast → rollback on failure or undo (G9). Day-progress ticks optimistically. **Done-when:** airplane-mode tap shows optimistic state then clean rollback + retry toast. |
| **P1-FE-03** | M | P1-BE-02 | **Task detail (S2).** Title/board/due header, description, assignee row + Reassign member-picker (pool from API), history chain rendered human ("Created by KC · Mon 9:02"), Mark done button, cancel action (creator/admin). Notes/photos deferred to Phase 4 — show note input disabled with "coming soon" only if trivial, else omit. **Done-when:** reassign round-trip updates chain in place; matches S2 content spec. |
| **P1-FE-04** | M | P1-FE-02 | **Celebration v1 (§3.1–3.2 core).** Spring checkbox animation, haptics (`navigator.vibrate`), variable sparkle (~1/7), all-done full-screen ritual with count + default line, undo-debounce suppressing the ritual. Contextual lines (streak/record) come in P3-FE-02. **Done-when:** completing the last seeded task triggers the ritual; undo within 5 s suppresses it. |
| **P1-FE-05** | M | P1-BE-01, P1-BE-02 | **Boards list + board view (S3, S4 list-mode).** My/other-public grouping, visibility glyphs, completion fractions; board view list (task/assignee/due/status/↩n/claim), board settings sheet (rename, visibility, members, archive). Kanban deferred (P4). **Done-when:** matches S3/S4 content spec; private board flip shows the member-management UI. |
| **P1-FE-06** | M | P1-BE-02 | **Create/edit task sheet (S5, recurrence UI stubbed).** Bottom-sheet (mobile) / side-panel (desktop): title, details, board select, assignee select incl. "Leave unassigned (anyone claims)", due date+time. "Repeats" toggle present but disabled with "Phase 2" tag. **Done-when:** create→appears on board and assignee's Home without refresh (query invalidation). |
| **P1-FE-07** | M | P1-BE-08 | **Members screen (S8) + invite flow.** Table per S8, add-member sheet with the two modes; invite-link mode shows copy + native-share buttons (B4). Onboarding spotlight for invited member's first session (§3.5, simple version). **Done-when:** full F2 flow works end-to-end with a copied link in a second browser profile. |
| **P1-FE-08** | S | P1-FE-01, P1-FE-05 | **Empty states (G8).** All five specified states implemented as a reusable `EmptyState` component with illustration slot. **Done-when:** fresh-org walkthrough never shows a blank panel. |
| **P1-FE-09** | M | P0-FE-02, P1-BE-08 | **5-minute setup wizard (F1 + B9, skippable).** Post-registration: (1) bulk quick-add members — multi-row name + contact grid, invite links generated in one click each with copy/share; (2) create the first task on General and assign it; (3) "see it land" pointer to Home. Progress indicator, every step skippable, total time instrumented (`setup_completed` event with duration + members_added). **Done-when:** a new org realistically goes register → members invited → first task assigned in ≤ 5 minutes; the duration shows up in analytics. |

**Batches:** **C:** P1-BE-01 ∥ P1-BE-02 ∥ P1-BE-08 → **D:** P1-BE-03 ∥ P1-BE-04 ∥ P1-BE-05 ∥ P1-BE-06 ∥ P1-BE-07 ∥ P1-BE-09 ∥ P1-FE-05(partial) → **E:** P1-FE-01 → P1-FE-02 → P1-FE-04, with P1-FE-03 ∥ P1-FE-06 ∥ P1-FE-07 alongside → **F:** P1-FE-08 ∥ P1-FE-09.

**🚩 Milestone M1 (end of Phase 1):** register an org, invite via link, assign, claim, pass, complete with celebration — demoable to a friendly school. Activation funnel visible in SQL.

### Phase 2 — Recurrence & reliability

| ID | Size | Deps | Task |
|---|---|---|---|
| **P2-BE-01** | M | P1-BE-02 | **Templates API + recurrence rules.** Template CRUD (create/edit/pause/delete with F9 semantics: future-only effects), recurrence JSON validator for the human presets (daily / weekdays / weekly-days / monthly-day / custom). On create: materialize instances through tomorrow immediately. **Done-when:** each preset round-trips and yields correct next-3-occurrence dates in unit tests (incl. month-end edge: "day 31" in April → Apr 30). |
| **P2-BE-02** | M | P2-BE-01 | **Materializer job.** Hourly tick; for orgs whose local midnight just passed: spawn today's instances idempotently (unique `template_id + due-date`), assignee = default or null. APScheduler behind `ENABLE_SCHEDULER` (v1 pattern). Manual trigger endpoint for ops. **Done-when:** double-run produces zero duplicates; TZ test with two orgs (Kolkata, Dubai) spawns at each org's midnight. |
| **P2-BE-03** | S | P2-BE-02 | **Miss-marker.** Same tick: yesterday's still-open *dated* instances → `missed` + event. Recurring misses expire quietly (B6/O2); one-time misses feed Overdue (G6 window). **Done-when:** mixed seed of recurring/one-time yields correct missed/overdue split. |
| **P2-BE-04** | M | P0-BE-02 | **Notification core.** Enqueue helpers writing `notifications` rows with `dedupe_key`; channel-adapter interface + **email adapter (Resend)** with templates: assigned, passed, reminder, magic link, digest, report card, nudge. Reminder rows enqueued at instance creation (`due_at − remind_before_minutes`). **Done-when:** duplicate enqueue with same dedupe_key is a no-op; emails render from a test harness. |
| **P2-BE-05** | M | P2-BE-04 | **Notification sweep.** 2-min job: due+pending → send via adapter → sent/failed, retry ×3 with backoff; `failed`-row count exposed on `/health/metrics`. Wire instant sends (assigned/passed) to bypass the sweep latency (send-now, row recorded). **Done-when:** kill-the-adapter test shows retries then failed status; assignment email arrives < 5 s in dev. |
| **P2-FE-01** | M | P0-FE-01 | **PWA + Web Push.** Manifest, icons, Serwist service worker, install prompt (gentle, after first completion — not on first visit), push subscribe flow, `push` adapter on backend (pywebpush), notification click → deep link to task. **Done-when:** installed PWA on Android receives an assignment push that opens task detail. *(Post-Track-FL: FCM becomes the primary mobile channel; web push remains for desktop/web users.)* |
| **P2-FE-02** | M | P2-BE-01, P1-FE-06 | **Recurrence UI (S5 full).** Enable the Repeats section: presets exactly per wireframe, custom collapsed; template management view per board (list, pause, edit-future-only, delete) — admin-visible under board settings. **Done-when:** create weekday-recurring task → instances appear for today/tomorrow; pausing stops next-day spawn (assert via manual materializer trigger). |
| **P2-BE-06** | S | P2-BE-04 | **Daily digest job.** Org-local 8 AM per member: today's summary (skip if empty day). Monday's digest = weekly recap payload (§3.4 data: counts, on-time %, best-week flag). **Done-when:** snapshot test of digest content for seed user; Monday variant carries recap numbers. |
| **P2-BE-07** | S | P2-BE-04 | **Defensive auto-nudge.** Overdue gentle reminder 1 h after due (once, dedupe-keyed), PRD §9 tone. **Done-when:** overdue seed instance generates exactly one nudge row across repeated sweeps. |

**Batches:** **G:** P2-BE-01 ∥ P2-BE-04 ∥ P2-FE-01 → **H:** P2-BE-02 → P2-BE-03, P2-BE-05 → {P2-BE-06 ∥ P2-BE-07}, P2-FE-02.

**🚩 Milestone M2:** the daily-checklist org works end-to-end — tasks spawn nightly, reminders arrive by push/email, missed forgives, digest lands at 8 AM.

### Phase 3 — Visibility & retention

| ID | Size | Deps | Task |
|---|---|---|---|
| **P3-BE-01** | M | P1-BE-04 | **Board report (S6).** `GET /boards/{id}/report?range=today|week`: completion %, on-time %, overdue count, per-member bars, 14-day trend — all computed from `task_events` (never mutable rows), cancelled excluded. **Done-when:** numbers reconcile against hand-computed seed fixtures incl. a reopen and a cancel. |
| **P3-BE-02** | M | P3-BE-01 | **Org dashboard (S7, admin-only).** Public-boards rollup: org %, on-time, overdue, per-member across public boards, per-board summary, reassignment hotspots (instances with `pass_count ≥ 2`, members ranked by passes-received last 14 d). **Done-when:** private-board data provably absent (test asserts a private task never affects rollup); non-admin → 403. |
| **P3-BE-03** | S | P3-BE-02, P2-BE-04 | **Manual nudge + report card.** `POST /org/nudge/{user_id}` (gentle template, lists that member's overdue), 6 PM org-local report-card job to admins (configurable hour in org settings). **Done-when:** nudge dedupes within 4 h; report card snapshot matches F7 copy shape. |
| **P3-BE-04** | S | P1-BE-04 | **History + stats endpoint.** `GET /me/history`: completions by day (10-week dot-calendar data: all-clear/partial/none per day), weekly counts, personal best, current all-clear run (for §3.2 lines — server-computed so client logic stays dumb). **Done-when:** dot states correct for a fixture month incl. days with nothing due. |
| **P3-FE-01** | M | P3-BE-01 | **Board report screen (S6).** Stat cards, member bars, trend sparkline (lightweight — no chart lib heavier than recharts), Today/Week toggle. **Done-when:** matches S6 content; renders on mobile width. |
| **P3-FE-02** | M | P3-BE-04 | **Done/History trophy room (S10 + §3.3) & ritual upgrades.** Dot calendar, weekly count + personal best, day-grouped completions; wire contextual lines (run / record / tomorrow-peek) into the all-done ritual (§3.2) and Monday recap card on Home (§3.4). **Done-when:** ritual shows "N days in a row" only when run ≥ 2; no broken-streak state exists anywhere in the UI. |
| **P3-FE-03** | M | P3-BE-02 | **Org dashboard screen (S7).** Rollup cards, member bars with nudge buttons (optimistic "sent ✓"), board summaries, hotspots panel framed as workflow signal, the honest ⓘ scope note. Desktop-primary, responsive. **Done-when:** matches S7 content; nudge round-trip works. |
| **P3-FE-04** | S | P1-FE-07 | **First-run spotlight polish (§3.5).** 2-step spotlight + guaranteed rich first-completion celebration + "See you tomorrow 👋". **Done-when:** fresh invited user in a clean profile experiences the full 60-second arc. |

**Batches:** **I:** P3-BE-01 ∥ P3-BE-04 → **J:** P3-BE-02 → P3-BE-03 ∥ P3-FE-01 ∥ P3-FE-02 → **K:** P3-FE-03 ∥ P3-FE-04.

**🚩 Milestone M3:** the end-of-day admin ritual works: 6 PM report card → dashboard → one-tap nudges. Members have a trophy room. Retention loops live on both sides.

### Phase 4 — Monetization, polish & parallel tracks

| ID | Size | Deps | Task |
|---|---|---|---|
| **P4-BE-01** | L | P0-BE-03 | **Razorpay subscriptions (B11).** Two plans only: **Free** and **Pro — ₹500/month flat per org**. Subscription create + webhook → `organizations.plan` (handle renewal, failed payment → grace period 7 d → downgrade to Free limits without deleting anything). Limit enforcement on the relevant POST endpoints with explicit structured upgrade-prompt error payloads (never silent). Free limits per R6 proposal: 2 boards · 8 members · 14-day report window · no EOD report card · no attachments · no critical alarms. The core loop is never paywalled. **Done-when:** sandbox webhook flips plan both directions; creating board #3 on Free returns the structured upgrade error; Pro org passes all limit checks; downgrade hides nothing destructively. |
| **P4-FE-01** | M | P4-BE-01 | **Settings/Billing screen (S9).** Org name, TZ, report-card hour, **Free vs Pro comparison card (₹500/month, whole org — one price, no per-seat math)**, Razorpay checkout, invoices list; upgrade prompts wired to the structured limit errors everywhere they can fire (board create, member add, report range, attachments, critical toggle). **Done-when:** the full upgrade flow works in Razorpay test mode; every limit error renders its upgrade prompt. |
| **P4-BE-02** | M | P1-BE-02 | **Attachments (notes + photos).** R2 bucket, pre-signed upload/download, `attachments` rows + `attached`/`commented` events, image resize on upload (thumbnail). **Done-when:** photo upload from mobile web → appears in task history. |
| **P4-FE-02** | S | P4-BE-02 | **Task detail: note + photo UI (S2 complete).** **Done-when:** S2 fully matches wireframe. |
| **P4-FE-03** | M | P1-FE-05 | **Kanban toggle (S4) + checklist preset.** Open/Done columns, drag-to-complete (fires same `/complete`); checklist-category boards default to day-grouped completion-first layout. **Done-when:** drag completes with celebration; checklist board renders grouped by day. |
| **P4-BE-03** | M | P1-BE-01, P1-BE-08 | **F9 lifecycle hardening.** Creator-leaves → board ownership to oldest admin (reassignable); orphaned-task dashboard flags; private-member-removal edge; template-deleted/edited/paused rules verified end-to-end. **Done-when:** the full F9 table from the PRD passes as an integration-test suite. |
| **P4-OPS-01** | M | M2 | **Production deploy.** API + worker (single instance, scheduler on) on Railway/Render/Cloud Run, web on Vercel, Aiven Postgres, Resend domain auth (SPF/DKIM), Sentry both sides, uptime check, `failed`-notification alert (the PRD's launch requirement), backup verification. **Done-when:** staging org runs a full day cycle (materialize → remind → digest → report card) in production infra. |
| **P4-QA-01** | M | M3 | **E2E smoke suite.** Playwright: register → invite → assign → claim → pass → complete → ritual → report. Runs against staging. **Done-when:** suite green and wired to run pre-deploy. |
| **PT-WA-01** | L | P2-BE-04 | **(Parallel track, optional, post-launch)** WhatsApp adapter via Interakt: outbound templates, inbound webhook + "done" matching with numbered disambiguation (F8), magic-link delivery. Slots behind the existing adapter interface — zero core changes. Start Meta template approval whenever you decide to pursue it. |

**Batches:** **L:** P4-BE-01 ∥ P4-BE-02 ∥ P4-BE-03 ∥ P4-FE-03 → **M:** P4-FE-01 ∥ P4-FE-02 → **N:** P4-OPS-01 → P4-QA-01. PT-WA-01 floats freely after Phase 2.

**🚩 Milestone M4: sellable.**

### Track FL — Flutter native app (parallel track; starts once M2 APIs are stable)

The member experience as a native Android-first app (B10), consuming the exact same API. Web remains the admin surface and the fallback member surface. The app exists for the things PWA cannot do: reliable FCM delivery, exact alarms, and **full-screen alarm-style reminders for critical tasks** — the founder's differentiator for ground-level staff.

**North-star guardrail for alarms:** an alarm is an *alarm clock*, not a hostage screen. It fires only for tasks explicitly flagged **critical** by the creator (flag visible to the assignee from the moment of assignment), always offers Snooze, respects org quiet hours, and keeps the same calm copy. It re-fires through snoozes until the task is completed or cancelled — persistence is the feature; humiliation is not.

| ID | Size | Deps | Task |
|---|---|---|---|
| **FL-BE-01** | M | P2-BE-04 | **Device registry + FCM adapter.** `device_tokens` endpoints (register/refresh/remove on logout), FCM channel adapter behind the existing adapter interface, channel ladder becomes: FCM (if device) → web push (if subscribed) → email. Token hygiene: purge on FCM 404/410. **Done-when:** assignment to a user with a registered device delivers via FCM in dev; dead token gets purged after one failed send. |
| **FL-01** | L | P0-BE-04 | **Flutter scaffold + auth.** Flutter project (Android-first; iOS deferred per R7), design tokens mirroring web, API client (dio) with refresh-token rotation, deep linking: `/join/[token]` invite links and magic links open the app via Android App Links, login screen. **Done-when:** invite link tapped on a phone with the app installed lands authenticated on Home; without the app, falls back to web. |
| **FL-02** | L | FL-01, P1-BE-07 | **Home/Today + complete loop + celebrations.** S1 parity: sections, day-progress, claim, optimistic complete with undo; full §3 celebration layer natively (spring animation, haptics via `HapticFeedback`, variable sparkle ~1/7, all-done ritual with contextual lines). **Done-when:** the F3 daily loop (notification → tap → complete → ritual) runs end-to-end on a physical device in < 5 s. |
| **FL-03** | M | FL-02 | **Boards + task detail + create.** S3/S4 list views, S2 task detail with event chain and reassign picker, S5 create/edit sheet incl. recurrence presets and the **Critical toggle** (Pro-gated per R6). **Done-when:** create → assign → pass → complete round-trip works app-to-web (changes visible on web without refresh). |
| **FL-04** | M | FL-BE-01, FL-01 | **Push receive + notification UX.** FCM foreground/background handling, tap → deep link to task detail, in-app notification permission education (ask after first completion, not at install), notification settings screen (per-channel view of what arrives where). **Done-when:** assignment, pass, reminder, and nudge each arrive and deep-link correctly with the app killed. |
| **FL-05** | L | FL-04, FL-03 | **Alarm-style critical reminders (the differentiator).** For `is_critical` instances: schedule exact alarms (`SCHEDULE_EXACT_ALARM`) at due time; full-screen intent (`USE_FULL_SCREEN_INTENT`) with ringtone + vibration over lock screen, actions: **✓ Complete now · Snooze 10 min · Open task**. Re-fires on snooze until completed/cancelled. Guardrails: org quiet hours (default 9 PM–7 AM, R8) defer alarms to morning; flag settable only by task creator/admins; assignee sees a ⏰ badge from assignment; all copy north-star calm ("Submit attendance is due now"). Server fallback: critical tasks also send FCM high-priority. The web create-sheet gains the Critical toggle in this packet too. **Done-when:** locked phone rings full-screen at due time; Complete from the alarm screen completes the task and logs the event; quiet-hours alarm arrives at 7 AM instead. |
| **FL-06** | M | FL-02 | **Done/History + first-run + store presence.** §3.3 trophy room parity, §3.5 first-run spotlight, web → app install prompts for members on Android web, Play Console internal-testing track build with store listing assets. **Done-when:** internal-testing build installable from Play Console; a fresh invitee experiences the full first-60-seconds arc natively. |
| **PT-CALL-01** | — | FL-05 + pilot data | **(Future placeholder — explicitly out of v2.)** Call-style escalation for repeatedly-ignored critical tasks (Exotel/Twilio programmable voice: automated call reads the task aloud). Revisit only with pilot evidence that alarms alone under-deliver, and with a consent + dignity design — an unwanted robocall is where "reduce the dread" goes to die. |

**FL batches:** FL-BE-01 (anytime after P2-BE-04) · FL-01 → FL-02 → {FL-03 ∥ FL-04} → FL-05 → FL-06. The track can start right after M2 and run alongside Phase 3/4 web work — different repo, zero spine-file contention.

---

## 6. Dependency overview & suggested agent dispatch

```
A: P0-BE-01 ∥ P0-FE-01
B: P0-BE-02 ──► P0-BE-03 ──► P0-BE-04        ∥  P0-BE-05 ∥ P0-BE-06 ∥ P0-FE-02
C: P1-BE-01 ∥ P1-BE-02 ∥ P1-BE-08
D: P1-BE-03..07, P1-BE-09 (all ∥)            ∥  P1-FE-05/06/07 begin
E: P1-FE-01 ──► P1-FE-02 ──► P1-FE-04        ∥  P1-FE-03
F: P1-FE-08 ∥ P1-FE-09                       🚩 M1
G: P2-BE-01 ∥ P2-BE-04 ∥ P2-FE-01
H: P2-BE-02 ──► P2-BE-03 · P2-BE-05 ──► P2-BE-06 ∥ P2-BE-07 · P2-FE-02   🚩 M2
I: P3-BE-01 ∥ P3-BE-04
J: P3-BE-02 ──► P3-BE-03 ∥ P3-FE-01 ∥ P3-FE-02
K: P3-FE-03 ∥ P3-FE-04                       🚩 M3
L–N: Phase 4 batches                          🚩 M4   (PT-WA-01 floats)
FL:  FL-BE-01 · FL-01 ──► FL-02 ──► FL-03 ∥ FL-04 ──► FL-05 ──► FL-06   (post-M2, runs beside Phase 3–4)
```

Working solo with agents: dispatch each batch's packets to parallel agents (worktrees), review and merge batch-by-batch. The packets are written to be self-contained — paste the packet text + PRD section references into the agent prompt. **Rule of thumb: never let two agents touch `events.py`, the schema, or `visibility.py` in the same batch** — those three files are the spine; schedule their changes serially.

---

## 7. Cross-cutting standards (apply to every packet)

1. **Every state change goes through the event writer** — if a feature mutates `task_instances` without an event, it's wrong by definition.
2. **Reports read events, never instance rows.**
3. **`org_id` comes from auth context only.** Any endpoint reading it from body/query fails review.
4. **Copy tone:** every user-facing string passes the north-star test — would this sentence increase the dread of being managed? Amber not red; "waiting for you" not "you failed"; counts not percentages on member-facing surfaces.
5. **Mobile first:** every member screen built and reviewed at 380 px before desktop.
6. **Optimistic UI for the big three** (complete, claim, reassign) with visible rollback.
7. **Tests required per packet:** the Done-when items, as pytest/Playwright where applicable. Visibility, claim-race, idempotency, and TZ tests are non-negotiable.
8. **Seed data stays runnable** — every schema change updates the seed script; the demo org is the shared dev fixture.

---

## 8. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Timezone bugs (materializer, "today", digests) | Wrong-day tasks destroy trust in "the external brain" | Single `org_now()` helper; the two-org TZ test in P2-BE-02; all `due_at` stored UTC, converted at the edge only |
| Celebration layer over-fires and habituates | The addictive loop dies in week 2 | Variable ratio locked at ~1/7; ritual only on true all-clear; review §3 against real usage after first pilot org |
| Notification deliverability (email in spam) | "Notifications must never fail" north star broken | Resend with proper domain auth in P4-OPS-01; push as primary channel once subscribed; `failed`-row alerting from day 1 |
| Scheduler single-point (in-process APScheduler) | Missed materialization = missing tasks at 8 AM | `ENABLE_SCHEDULER` on exactly one instance; hourly tick is self-healing (processes any org past midnight not yet materialized); manual trigger endpoint |
| Scope creep back toward v1 (categories, RBAC, view styles) | v2 becomes school_ops again | §1 B-decisions + PRD locked decisions are the contract; anything not in §5 is a post-M4 proposal |
| Solo review bandwidth (agents produce faster than you review) | Quality erosion | Merge batch-by-batch; spine files serialized (§6); E2E suite (P4-QA-01) pulled earlier if regressions appear |
| Alarm-style reminders read as surveillance/harassment | Kills the north star; staff uninstall the app | Critical flag is explicit, creator-set, and visible to the assignee at assignment; Snooze always available; org quiet hours + R8 caps; every alarm string passes the tone test (FL-05 guardrails); PT-CALL-01 stays gated behind pilot evidence + consent design |
| Two frontends (web + Flutter) double UI maintenance for a solo founder | Velocity halves after Track FL ships | API-first contracts so features are backend-once; web leans admin + landing, Flutter leans member; shared design tokens; never ship the same feature to both surfaces in the same batch |
| ₹500 flat org pricing under-monetizes large orgs | Revenue ceiling per account | Acceptable for v2 simplicity (founder call, B11); revisit per-seat or an "Org" tier only after pilot conversion data |

---

## 9. Remaining open decisions (small, non-blocking)

| # | Decision | Needed by | Default if undecided |
|---|---|---|---|
| R1 | Product display name & domain (TrackBit?) | P0-FE-01 (branding tokens) | Keep "TrackBit" |
| R2 | Email "from" domain for Resend | P2-BE-04 dev / P4-OPS-01 prod | `notify@<your-domain>` |
| R3 | Deploy target for API (Railway / Render / Cloud Run) | P4-OPS-01 | Railway (simplest worker+cron story) |
| R4 | Sound on celebrations | P3-FE-02 | Off by default, toggle in profile — haptics only |
| R5 | Pilot org (the "one friendly school" for M1) | M1 | — |
| R6 | **Free-tier limit values.** Proposal: 2 boards · 8 members · 14-day report window · no EOD report card · no attachments · no critical alarms. Core loop always free. | P4-BE-01 | The proposal |
| R7 | Flutter platform scope for v1 of the app: Android-only vs Android + iOS | FL-01 | Android-only (ground-staff reality; iOS when a paying org asks) |
| R8 | Critical-alarm guardrail values: quiet hours window, max alarm re-fires per task per day | FL-05 | Quiet hours 9 PM–7 AM org-local; unlimited snoozes inside the day window |

---

*End of implementation plan.*
