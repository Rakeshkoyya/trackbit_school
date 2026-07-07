# TrackBit — Product Requirements Document v2

**Simple, open, stress-free task management for micro-organizations.**

| | |
|---|---|
| **Version** | 2.0 (supersedes v1 — permission model replaced with open model) |
| **Audience** | Engineering, Design |
| **Stack** | Next.js · FastAPI · PostgreSQL (Aiven) |
| **Status** | Decisions locked, ready for build |

---

## 1. Product summary

Small teams (schools, e-commerce sellers, clinics, agencies of 5–25 people) track work in Excel and WhatsApp groups. Big tools are overkill. TrackBit does one job: **anyone in the org can create boards and tasks, assign work to anyone, and everyone sees what's done — with full traceability instead of heavy permissions.**

### Design north star

> **Reduce the dread of being managed.** Celebrate done, forgive missed. Show only today. Be the trusted external brain — which means notifications must never fail.

### The governance philosophy (what changed from v1)

TrackBit v2 is an **open model**. There are no board-manager roles, no assignment permissions. Any member can create a board, add tasks to boards they can see, assign to any member of that board, and reassign tasks they hold. Governance comes from **traceability, not permission**: every assignment and reassignment is a recorded, visible event. In an open system, visibility replaces permission.

> *"Openness in doing work doesn't require openness in judging work."* Everyone can act; only admins see the org-wide judgment layer (rollup dashboard).

---

## 2. Locked product decisions

These were debated and are now final for v1. Do not re-litigate during build.

| # | Decision |
|---|---|
| D1 | **Open assignment.** Any org member can assign/reassign tasks on boards they belong to. No approval step. |
| D2 | **Instant reassignment.** Switching a task to someone maps them immediately. No accept/reject flow in v1. The full chain is recorded and visible. |
| D3 | **No personal boards in v1.** Org-level only. Visibility is `public` or `private`. |
| D4 | **Public board** = visible to the whole org; any member can view, add tasks, claim, and assign to any org member. |
| D5 | **Private board** = visible only to its added members; tasks assignable only to those members. |
| D6 | **New boards default to public.** Creator can flip to private. |
| D7 | **Org dashboard aggregates public boards only.** Private boards never roll up. |
| D8 | **Board-level reports** exist for every board, visible to whoever can see the board. |
| D9 | **Org-wide rollup dashboard is admin-only.** Members see their own stats + board reports for their boards. |
| D10 | **One assignee per task** (or null = claimable). Watchers/comments fine; co-owners never. |
| D11 | **Admin-creates-account is the primary onboarding path** for staff (name + phone → WhatsApp magic link). Email invite is secondary. |
| D12 | **Notification defaults:** assignment & reassignment always notify instantly; due-time reminders fire per task; everything else folds into a daily digest. |

---

## 3. Roles

Only **one** role axis exists: the org role.

| | `admin` | `member` |
|---|:---:|:---:|
| Create boards (public default) | ✅ | ✅ |
| Flip own board public ↔ private | ✅ | ✅ (boards they created) |
| Add members to a private board | ✅ | ✅ (boards they're on) |
| Create / claim / assign / reassign tasks | ✅ | ✅ |
| View board reports (boards they can see) | ✅ | ✅ |
| View own home page / personal stats | ✅ | ✅ |
| **View org-wide rollup dashboard** | ✅ | ❌ |
| Invite / create / remove org members | ✅ | ❌ |
| Billing & subscription | ✅ | ❌ |
| Transfer/own orphaned boards | ✅ | ❌ |

---

## 4. Core concepts

### 4.1 Hierarchy

```
Organization (tenant + billing boundary, has timezone)
 └── Members (admin | member)
      └── Boards (public | private; category preset: tasks | checklist)
           └── TaskTemplates (recurring definitions only)
           └── TaskInstances (every concrete unit of work)
                └── Events (append-only: assigned, passed, completed, …)
```

### 4.2 Template vs Instance (unchanged from v1 — load-bearing)

- **TaskTemplate** — only for recurring tasks. Holds title, description, recurrence rule, default assignee, board.
- **TaskInstance** — every actual to-do. One-time tasks are instances with `template_id = NULL`. Recurring tasks spawn one instance per occurrence via the nightly job.
- Instances are **materialized in advance** (nightly), never lazily — the row must exist for "missed" to be a real, reportable state.

### 4.3 The event log does double duty

An append-only `task_events` table is both:
1. **The reporting backbone** — completion rates over time, on-time %, per-member load are computed from events, never from mutable task rows.
2. **The accountability chain** — in an open model, the visible history *is* the governance. Every task detail screen shows: *created by KC → assigned to Priya → passed to Ramesh → completed.*

---

## 5. Information architecture & navigation

One Next.js app, two experiences by context:

```
MEMBER (mobile-first)                 ADMIN (desktop-primary, responsive)
─────────────────────                 ───────────────────────────────────
🏠 Home (Today)        ←──────────────  same Home exists for admins too
📋 Boards (mine + public)             📋 Boards
✓  Done / History                     📊 Org Dashboard (admin-only)
                                      👥 Members
                                      ⚙  Settings / Billing
```

Bottom tab bar on mobile: **Home · Boards · Done**. Admin gets the extra nav items on desktop.

---

## 6. Screens

> Wireframes are layout/content specs, not visual design. A separate design pass decides look & feel. Frontend should treat every box and label below as required content.

### S1 — Home ("Today") — *the hero screen, every user's landing page*

A personalized summary of **everything assigned to me across all boards I'm on**, grouped by urgency. This is the screen the product lives or dies on; the open-→complete loop must be under 5 seconds.

```
┌──────────────────────────────────────┐
│  Good morning, Priya                  │
│  Tuesday, June 10 · 5 things today    │
├──────────────────────────────────────┤
│  ⚠ OVERDUE (1)                        │
│  ◻ Email parent group                 │
│     Admissions · was due yesterday    │
│                                       │
│  ⏰ DUE TODAY (3)                      │
│  ◻ Submit attendance      10:00 AM    │
│     Daily Ops                         │
│  ◻ Restock display                    │
│     Daily Ops                         │
│  ◻ Reply to reviews                   │
│     Store Tasks · passed by Ramesh ↩  │   ← reassignment visible inline
│                                       │
│  📥 CLAIMABLE ON YOUR BOARDS (1)      │
│  ◻ Update pricing sheet    [ Claim ]  │
│     Store Tasks · unassigned          │
├──────────────────────────────────────┤
│   🏠 Home      📋 Boards      ✓ Done  │
└──────────────────────────────────────┘
```

**Behavior:**
- Sections in order: **Overdue → Due today → Anytime today → Claimable**. Empty sections hidden.
- Tapping the checkbox completes instantly (optimistic UI; sync in background; undo toast for 5s).
- Each task shows its **board name** and, when relevant, **"passed by X"** — the open model's transparency, surfaced casually.
- Claimable section shows unassigned tasks from boards the user belongs to; one-tap **Claim** assigns to self.
- **All-done state:** when today is cleared, the list is replaced by a full-screen "✅ You're done for today" moment with today's count and a subtle summary. This is the permission-to-stop ritual. No upsell, no "do more."
- Overdue styling is **calm** (amber, not red walls). Misses never stack into shame.

### S2 — Task Detail

```
┌──────────────────────────────────────┐
│ ← Submit attendance                   │
│   Daily Ops · Due today 10:00 AM      │
├──────────────────────────────────────┤
│  Description…                         │
│                                       │
│  Assigned to:  Priya  [ ⇄ Reassign ]  │
│                                       │
│  History                              │
│  • Created by KC · Mon 9:02 AM        │
│  • Assigned to Ramesh · Mon 9:02 AM   │
│  • Passed to Priya · Mon 4:15 PM      │   ← the accountability chain
│                                       │
│  [ + Note ]  [ 📷 Photo ]             │
│                                       │
│        ┌────────────────────┐         │
│        │    ✓  Mark done     │         │
│        └────────────────────┘         │
└──────────────────────────────────────┘
```

- **Reassign** opens a member picker (org members for public boards; board members for private). Selection maps instantly (D2), logs a `passed` event, notifies the new assignee.
- History section renders the event chain, newest last. Always visible — this is governance.
- Note + photo = proof-of-completion (matters for checklist boards: restocked shelf, submitted form).

### S3 — Boards list

```
┌──────────────────────────────────────┐
│  Boards                    [ + New ]  │
├──────────────────────────────────────┤
│  MY BOARDS                            │
│  ▸ Daily Ops        🌐 public   8/10  │
│  ▸ Admissions       🔒 private  5/5   │
│                                       │
│  OTHER PUBLIC BOARDS IN ORG           │
│  ▸ Store Tasks      🌐 public   3/7   │
│  ▸ Events           🌐 public   2/2   │
└──────────────────────────────────────┘
```

- "My boards" = boards I created or am a member of. "Other public" = the rest of the org's public boards (visible per D4). Private boards I'm not on **do not appear at all** — not even as a name.
- Each row shows visibility glyph + today's completion fraction.

### S4 — Board view

```
┌────────────────────────────────────────────────────────┐
│ ← Daily Ops  🌐        [ List | Kanban ]    [ + Task ]  │
│   12 members · Report ▸ · ⚙ board settings              │
├────────────────────────────────────────────────────────┤
│  Task                Assignee      Due      Status      │
│  ────────────────────────────────────────────────────  │
│  Submit attendance   Priya         10 AM    ✓ Done      │
│  Restock display     Ramesh        —        ○ Open      │
│  Reply to reviews    ⊕ Unassigned  —        [ Claim ]   │
│  Update pricing      Anil ↩²       5 PM     ⚠ Overdue   │   ← ↩² = passed twice
└────────────────────────────────────────────────────────┘
```

- **List default; Kanban toggle** (Open / Done columns in v1 — keep it minimal).
- The `↩n` badge shows reassignment count — the open model's gentle social pressure.
- **Board settings** (creator + admins): rename, public↔private toggle, member management (private only), category preset (tasks | checklist), archive.
- **Checklist preset** changes the view defaults: instances grouped by day, completion-first layout — same data model, different presentation.

### S5 — Create / Edit Task (side panel on desktop, bottom sheet on mobile)

```
┌─────────────────────────────────┐
│  New task                    ✕  │
│  Title    [___________________] │
│  Details  [___________________] │
│  Board    [ ▼ Daily Ops       ] │
│  Assign   [ ▼ Priya           ] │   ← or "Leave unassigned (anyone claims)"
│  Due      [ date ]  [ time ]    │
│                                 │
│  Repeats?   ◯ off   ● on        │
│   ● Daily                       │
│   ○ Weekdays (Mon–Fri)          │
│   ○ Weekly on  [Mo][Tu]…        │
│   ○ Monthly on day [ n ]        │
│   ○ Custom (advanced)           │   ← collapsed by default
│                                 │
│        [ Cancel ]  [ Save ]     │
└─────────────────────────────────┘
```

- Recurrence = **human presets only**. Never expose cron/RRULE. "Custom" is hidden behind a disclosure.
- Assignee dropdown lists org members (public board) or board members (private board) — enforced server-side too.
- On save: recurring → create template + materialize instances through tomorrow; one-time → create instance. Assignee notified.

### S6 — Board Report (per-board, visible to anyone who can see the board)

```
┌────────────────────────────────────────────────┐
│ ← Daily Ops · Report          [Today ▾] [Week]  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ 80% done │ │ 75% on-  │ │ 2 overdue│         │
│  │  (8/10)  │ │   time   │ │          │         │
│  └──────────┘ └──────────┘ └──────────┘         │
│  By member (this board only)                    │
│  Priya   ████████░░ 4/5                         │
│  Ramesh  ██████████ 3/3                         │
│  Anil    ███░░░░░░░ 1/2                         │
│  Completion trend (14 days)  ▁▃▅▆▅▇█▆▇█▇▆██     │
└────────────────────────────────────────────────┘
```

### S7 — Org Dashboard (admin-only)

```
┌────────────────────────────────────────────────────────┐
│  Org Dashboard · Today          (public boards only) ⓘ  │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐      │
│  │ 82% complete │ │ on-time 74% │ │ 5 overdue    │      │
│  └──────────────┘ └─────────────┘ └──────────────┘      │
│  By member (across public boards)                       │
│  Priya   ████████░░  8/10    [ 🔔 nudge ]               │
│  Anil    █████░░░░░  3/7     [ 🔔 nudge ]               │
│  By board                                               │
│  Daily Ops 8/10 · Store Tasks 3/7 · Events 2/2          │
│  Trends ▸   Reassignment hotspots ▸                     │
└────────────────────────────────────────────────────────┘
```

- The ⓘ states the scope honestly: *"Aggregates public boards. Private boards report individually to their members."* (D7 — no lies, no leaks.)
- **One-tap nudge** sends a gentle reminder for that member's overdue items.
- **Reassignment hotspots** = tasks/members with high pass counts — the open model's only "watchdog," framed as a workflow signal, not an accusation.

### S8 — Members (admin)

```
┌──────────────────────────────────────────────┐
│  Members (12)              [ + Add member ]   │
│  Name      Phone        Role     Last active  │
│  Priya     +91 98… ✓WA  member   today        │
│  KC        +91 97… ✓WA  admin    today        │
├──────────────────────────────────────────────┤
│  + Add member                                 │
│  Name  [________]  Phone [_________]          │
│  Role  ( ● member  ○ admin )                  │
│  ( ● Create account & send WhatsApp link )    │   ← primary path (D11)
│  ( ○ Send email invite )                      │
│            [ Add & send ]                     │
└──────────────────────────────────────────────┘
```

### S9 — Settings / Billing (admin)
Org name, **timezone** (drives recurrence + digests), plan & seats, Razorpay payment method, invoices, notification defaults.

### S10 — Done / History (every user)
Personal record: completed tasks by day, weekly count, gentle stats. Celebrates; never shames. No streak-loss mechanics in v1.

---

## 7. Flows

### F1 — Organization registration (the founder)

```
Landing → Sign up (email + password)
 → "Name your organization" + timezone (auto-detected, editable)
 → org created, user becomes admin, default board "General" (public) created
 → 3-step guided setup (skippable):
     1. Add your first members (S8 quick-add)
     2. Create your first task on General, assign it
     3. See it land — pointer to Home & Dashboard
```
**Activation event:** first task assigned to someone else gets completed. Instrument this.

### F2 — Staff onboarding (admin-creates-account, primary path)

```
Admin enters name + phone → account exists immediately
 → staffer receives WhatsApp: "KC added you to SHANA Ops on TrackBit. Tap to open: <magic link>"
 → link opens app, session created, lands on Home
 → no password ever; future logins via WhatsApp OTP / magic link
```
Email invite (secondary): standard invite → set password or continue passwordless.

### F3 — Daily member loop (< 5 seconds)

```
WhatsApp/push reminder → tap → Home → tap checkbox → ✓ (undo toast)
…last task of the day → "You're done for today" screen
```

### F4 — Assign & recurring loop

```
Board → + Task → fill → (Repeats? on → preset) → Save
 → backend: template created (if recurring) + instances materialized
 → assignee notified ("KC assigned you: Submit attendance, due 10 AM")
```

### F5 — Reassignment (the open model in action)

```
Priya opens task → ⇄ Reassign → picks Ramesh
 → instant remap (D2) · event `passed` logged · chain updated
 → Ramesh notified: "Priya passed you a task: Reply to reviews"
 → task shows "passed by Priya" on Ramesh's Home; board shows ↩ badge
```

### F6 — Claim (pull, not push)

```
Creator saves task with "Leave unassigned"
 → appears as Claimable on the board + in board members' Home claimable section
 → first Claim wins (server-side atomic check; second claimer gets "already taken")
```

### F7 — End-of-day admin loop (the retention ritual)

```
At org-local 6 PM (configurable): admin gets WhatsApp/email report card
  "SHANA Ops today: 82% done · 5 overdue · Anil has 2"
 → taps → Org Dashboard → 🔔 nudge stragglers (one tap each)
```

### F8 — WhatsApp-only completion

```
Instance reminder goes out via Interakt → worker replies "done"
 → Interakt webhook → match phone → user → their earliest open instance due today
 → ambiguous (multiple open)? reply with numbered list: "Which one? 1) Restock 2) Pricing"
 → "1" completes it → confirmation message → dashboard updates like any in-app completion
```

### F9 — Lifecycle edge rules (build these early)

| Event | Rule |
|---|---|
| Board creator leaves org | Board ownership transfers to an org admin (oldest admin by default; reassignable) |
| Member removed from org | Their open instances flip to **unassigned** on their boards; flagged on dashboard ("3 tasks orphaned by removal") so work never silently vanishes |
| Public board → private | Non-members lose visibility; their assigned open tasks on it flip to unassigned; they're notified |
| Private board member removed | Same as above, scoped to that board |
| Template deleted | Future instances stop; past instances and their history remain |
| Template edited | Applies to **future** instances only; never rewrites the past |
| Template paused | No new instances; existing ones unaffected |

---

## 8. Backend design

### 8.1 Architecture

```
┌─────────────┐   REST/JSON    ┌────────────────────────────┐
│  Next.js     │ ─────────────▶ │  FastAPI                   │
│ (admin +     │ ◀───────────── │  · auth middleware (JWT)    │
│  member UX)  │                │  · org-scoping middleware   │
└─────────────┘                │  · visibility guards        │
                               └──────┬─────────────┬───────┘
                                      │             │
                        ┌─────────────▼──┐   ┌──────▼──────────────┐
                        │ PostgreSQL      │   │ Worker (APScheduler  │
                        │ (Aiven)         │   │ or Celery + Redis)   │
                        │ org_id on every │   │ · nightly materialize│
                        │ row · RLS net   │   │ · notif sweep (2 min)│
                        └─────────────────┘   │ · daily digests      │
                                              │ · EOD report cards   │
                                              └──────┬──────────────┘
                                                     │
                                   ┌─────────────────┼──────────────┐
                                   ▼                 ▼              ▼
                              Interakt (WA)      Email (SES/      Web push
                              out + webhook in   Resend)          (PWA)
```

- **Multi-tenancy:** single database, `org_id` on every business row, enforced by a query-scoping layer (every repository/query function takes `org_id` from the authenticated context, never from request params). Postgres **RLS as a safety net** on top. No database-per-tenant.
- **Frontend delivery:** staff experience ships as a **PWA** (installable, push-capable) — no native app in v1.

### 8.2 Database schema

```sql
-- Tenancy & people ---------------------------------------------------
organizations (
  id            uuid PK,
  name          text NOT NULL,
  timezone      text NOT NULL DEFAULT 'Asia/Kolkata',
  plan          text NOT NULL DEFAULT 'free',     -- free | team | org
  created_at    timestamptz NOT NULL DEFAULT now()
)

users (
  id            uuid PK,
  name          text NOT NULL,
  email         citext UNIQUE,                    -- nullable (phone-only users)
  phone         text UNIQUE,                      -- E.164; nullable
  password_hash text,                             -- null for passwordless users
  created_at    timestamptz NOT NULL DEFAULT now()
)

memberships (
  id        uuid PK,
  org_id    uuid NOT NULL REFERENCES organizations,
  user_id   uuid NOT NULL REFERENCES users,
  org_role  text NOT NULL CHECK (org_role IN ('admin','member')),
  status    text NOT NULL DEFAULT 'active',       -- active | removed
  UNIQUE (org_id, user_id)
)

-- Boards --------------------------------------------------------------
boards (
  id          uuid PK,
  org_id      uuid NOT NULL REFERENCES organizations,
  name        text NOT NULL,
  visibility  text NOT NULL DEFAULT 'public'      -- public | private
              CHECK (visibility IN ('public','private')),
  category    text NOT NULL DEFAULT 'tasks'       -- tasks | checklist (view preset)
              CHECK (category IN ('tasks','checklist')),
  created_by  uuid NOT NULL REFERENCES users,
  owner_id    uuid NOT NULL REFERENCES users,     -- transfers on departure (F9)
  archived_at timestamptz
)

board_members (                                    -- meaningful for PRIVATE boards;
  id        uuid PK,                               -- public boards = whole org implicitly
  board_id  uuid NOT NULL REFERENCES boards,
  user_id   uuid NOT NULL REFERENCES users,
  board_role text NOT NULL DEFAULT 'member',       -- UNUSED in v1; kept for future
  UNIQUE (board_id, user_id)                       -- governance tier (do not drop)
)

-- Tasks ----------------------------------------------------------------
task_templates (
  id                  uuid PK,
  org_id              uuid NOT NULL REFERENCES organizations,
  board_id            uuid NOT NULL REFERENCES boards,
  title               text NOT NULL,
  description         text,
  recurrence_rule     jsonb NOT NULL,   -- {"freq":"weekly","days":["mon","fri"],"time":"10:00"}
  default_assignee_id uuid REFERENCES users,       -- null = spawn unassigned/claimable
  active              boolean NOT NULL DEFAULT true,
  created_by          uuid NOT NULL REFERENCES users
)

task_instances (
  id            uuid PK,
  org_id        uuid NOT NULL REFERENCES organizations,
  board_id      uuid NOT NULL REFERENCES boards,
  template_id   uuid REFERENCES task_templates,    -- null = one-time task
  title         text NOT NULL,
  description   text,
  assignee_id   uuid REFERENCES users,             -- null = claimable (D10)
  due_at        timestamptz,                       -- stored UTC; computed from org TZ
  status        text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','done','missed')),
  completed_at  timestamptz,
  completed_by  uuid REFERENCES users,
  created_by    uuid NOT NULL REFERENCES users,
  pass_count    int NOT NULL DEFAULT 0,            -- denormalized ↩ badge
  created_at    timestamptz NOT NULL DEFAULT now()
)
-- indexes: (org_id, assignee_id, status, due_at)  → Home screen
--          (board_id, status, due_at)             → Board view
--          (template_id, due_at)                  → materializer idempotency

task_events (                                       -- APPEND-ONLY
  id           bigserial PK,
  org_id       uuid NOT NULL,
  instance_id  uuid NOT NULL REFERENCES task_instances,
  actor_id     uuid REFERENCES users,               -- null = system (materializer)
  event_type   text NOT NULL CHECK (event_type IN
               ('created','assigned','claimed','passed',
                'completed','reopened','missed','commented','attached')),
  payload      jsonb,                               -- e.g. {"from":"<uid>","to":"<uid>"}
  created_at   timestamptz NOT NULL DEFAULT now()
)
-- This table powers: task history chain, all reports, reassignment hotspots.
-- Never UPDATE or DELETE rows here.

attachments (
  id          uuid PK,
  instance_id uuid NOT NULL REFERENCES task_instances,
  uploaded_by uuid NOT NULL REFERENCES users,
  kind        text NOT NULL CHECK (kind IN ('note','photo')),
  content     text,                                 -- note text
  file_url    text,                                 -- pre-signed object-storage URL
  created_at  timestamptz NOT NULL DEFAULT now()
)

-- Notifications ----------------------------------------------------------
notifications (
  id           uuid PK,
  org_id       uuid NOT NULL,
  user_id      uuid NOT NULL REFERENCES users,
  instance_id  uuid REFERENCES task_instances,
  channel      text NOT NULL CHECK (channel IN ('whatsapp','push','email')),
  notif_type   text NOT NULL CHECK (notif_type IN
               ('assigned','passed','reminder','overdue','digest','report_card','nudge')),
  status       text NOT NULL DEFAULT 'pending',     -- pending | sent | failed
  scheduled_at timestamptz NOT NULL,
  sent_at      timestamptz,
  dedupe_key   text UNIQUE                          -- e.g. 'reminder:<instance_id>'
)                                                   -- guarantees at-most-once per type

auth_tokens (                                        -- magic links & WA OTP sessions
  id         uuid PK,
  user_id    uuid NOT NULL REFERENCES users,
  token_hash text NOT NULL,
  purpose    text NOT NULL,                          -- magic_link | otp
  expires_at timestamptz NOT NULL,
  used_at    timestamptz
)
```

### 8.3 Visibility & authorization rules (enforce server-side, single module)

```
can_view_board(user, board):
    board.visibility == 'public'  → any active org member
    board.visibility == 'private' → board_members row exists (or org admin? NO —
                                     admins do NOT see private boards they're not on)

assignable_pool(board):
    public  → all active org members
    private → board_members of that board          ← enforced on assign & reassign

org_dashboard_scope(org):
    public boards only (D7)

board_report_scope(board, user):
    can_view_board(user, board)
```

> Note the deliberate choice: **admins cannot see private boards they're not members of.** Admin = billing/people/rollup, not omniscience. This keeps "private" honest and is part of the trust story. (The org rollup excludes private boards anyway per D7, so nothing leaks.)

### 8.4 Key API surface

```
AUTH
POST   /auth/register-org            {org_name, name, email, password, timezone}
POST   /auth/login                   email+password
POST   /auth/magic-link/request      {phone}        → sends WA link/OTP
POST   /auth/magic-link/verify       {token}        → session JWT

ORG / MEMBERS (admin)
GET    /org                          settings, plan
POST   /org/members                  {name, phone|email, org_role, mode: wa_create|email_invite}
DELETE /org/members/{id}             triggers F9 orphaning rules

BOARDS
GET    /boards                       my boards + org public boards
POST   /boards                       {name, visibility?, category?}
PATCH  /boards/{id}                  rename, visibility flip (triggers F9), archive
POST   /boards/{id}/members          (private boards)
GET    /boards/{id}/tasks            list/kanban data
GET    /boards/{id}/report?range=

TASKS
POST   /tasks                        {board_id, title, …, assignee_id?, due_at?, recurrence?}
PATCH  /tasks/{id}                   edit fields
POST   /tasks/{id}/complete          → event 'completed' (+undo via /reopen)
POST   /tasks/{id}/claim             atomic: WHERE assignee_id IS NULL → 409 if lost race
POST   /tasks/{id}/reassign          {to_user_id} → instant remap, event 'passed',
                                       pass_count++, notify
POST   /tasks/{id}/attachments

HOME & REPORTS
GET    /me/today                     overdue + due-today + anytime + claimable (S1)
GET    /me/history
GET    /org/dashboard                admin-only rollup (public boards)
POST   /org/nudge/{user_id}          one-tap nudge

WEBHOOKS
POST   /webhooks/interakt            inbound WA messages (F8) — verify signature
```

### 8.5 Background jobs

| Job | Schedule | Logic |
|---|---|---|
| **Materializer** | Nightly per org-local midnight (run hourly, process orgs whose local time just passed 00:00) | For each active template: compute today's occurrences from `recurrence_rule`; insert instances **idempotently** (unique on `template_id + due date`); assignee = default or null (claimable) |
| **Miss-marker** | Same run | Yesterday's still-`open` dated instances → `missed` + event. Recurring misses **expire quietly** (the next day brings a fresh instance — forgive missed); one-time misses surface in Overdue |
| **Notification sweep** | Every 2 min | Select `notifications` rows due & pending → send via channel adapter → mark sent/failed (retry w/ backoff ×3). Reminder rows are *enqueued at instance creation* (e.g., 30 min before due) using `dedupe_key` |
| **Daily digest** | Org-local 8 AM | Per member: today's task summary via preferred channel |
| **Report card** | Org-local 6 PM (configurable) | Per admin: org rollup snapshot (F7) |

> **Reliability contract:** sweep + `dedupe_key` gives at-most-once per notification type per instance; retries give at-least-once delivery effort; monitoring on `failed` rows is a launch requirement, not a nice-to-have.

### 8.6 WhatsApp integration (Interakt)

- **Outbound:** template messages (assignment, reminder, nudge, report card, magic link). Template pre-approval through Meta is required — **start this process week 1; it can take time and gates launch** (open question O3).
- **Inbound webhook:** verify signature → resolve phone → user → orgs. "done"/"completed" → complete matching instance (F8 disambiguation flow). Unrecognized text → polite help message.

### 8.7 Billing (Razorpay)

- Plans: `free` (≤3 seats, 1 board), `team` (per-seat), `org` (volume + report cards + exports).
- Razorpay Subscriptions + webhook → update `organizations.plan`; enforce seat/board limits at the application layer on the relevant `POST` endpoints (clear upgrade-prompt error responses, never silent failures).

---

## 9. Notifications policy (D12 expanded)

| Trigger | Channel behavior | Timing |
|---|---|---|
| Assigned / passed to you | Instant — WA primary, push fallback | Immediately |
| Reminder | Per instance | 30 min before `due_at` (default; per-task override later) |
| Overdue nudge (auto) | Gentle, once | 1 hr after due |
| Admin manual nudge | WA | On tap |
| Daily digest | One message | Org-local 8 AM |
| Admin report card | WA/email | Org-local 6 PM |

Tone rules: nudges never shame ("Reminder: Submit attendance is waiting for you 🙂", not "You FAILED to…"). All copy reviewed against the north star.

---

## 10. Build phasing

| Phase | Scope | Demoable outcome |
|---|---|---|
| **1 — Spine** | Org registration, members (both onboarding paths), public/private boards, one-time tasks, assign/claim/reassign + event chain, Home screen, complete loop, JWT + magic-link auth | Full assign→complete loop, ready to put in front of one friendly school |
| **2 — Recurrence & reliability** | Templates, materializer, miss-marker, notification sweep, Interakt outbound + inbound "done", PWA push | The Amazon-seller daily checklist works end-to-end incl. WhatsApp-only staffer |
| **3 — Visibility** | Board reports, admin org dashboard, report card, nudges, Done/History, reassignment hotspots | The end-of-day retention ritual works |
| **4 — Monetization & polish** | Razorpay tiers + enforcement, Kanban toggle, attachments, onboarding wizard polish, lifecycle edge rules hardened (F9) | Sellable |

---

## 11. Open questions

| # | Question | Owner |
|---|---|---|
| O1 | Reminder default 30 min before due — confirm, and do we allow per-task override in v1? | Product |
| O2 | Recurring-miss policy: quiet expiry (recommended, §8.5) vs roll-forward — confirm | Product |
| O3 | Interakt/Meta template approval timeline — **start week 1, may gate launch** | Eng |
| O4 | Daily digest opt-out per user in v1, or fixed? | Product |
| O5 | Photo storage: Aiven-adjacent object store / S3 + pre-signed URLs — pick provider | Eng |

---

*End of document — TrackBit PRD v2.*
