# TrackBit School — Product Requirements Document (SPRD v1.0)

**The unified school product: Academic Health Layer + Tasks + Fees in one app.**
July 2026 · Companion docs: `trackbit-product-architecture.md` (v1.1 — the WHY and the fences),
`trackbit-prd-v2.md` (task module spec), `trackbit-v2-implementation-plan.md` (task module build history).

> Cite this document in code comments as `SPRD §x.y`. Where this doc and the architecture doc
> conflict, the architecture doc's principles and fences win; where either conflicts with an
> explicit founder decision recorded later, the founder decision wins.

---

## §0. How to use this document (for the implementing agent)

1. This PRD assumes a **new project folder** (founder creates it; name suggestion: `trackbit_school/`).
   Bootstrap per §2.4 — you do NOT start from an empty repo; you seed from `task_management2`.
2. Work packet-by-packet (§10). Every packet has **Done-when** criteria — do not mark a packet
   complete until they pass. Backend packets end with `uv run pytest -q` green + `ruff` clean;
   frontend packets end with `npx tsc --noEmit`, `eslint`, and `next build` green.
3. The five product principles (§1.2) are acceptance criteria, not slogans. P1 (one-minute
   teacher budget) is measured in taps and seconds on every teacher-facing screen (§6.4).
4. Architectural laws inherited from the seed codebase (§2.2) are non-negotiable. Read
   `task_management2/CLAUDE.md` before writing backend code.
5. Copy this file, `trackbit-product-architecture.md`, and the two companion docs into the new
   repo under `docs/` in packet P0-A so future agents have them in-repo.

---

## §1. Product definition

### §1.1 One-liner

TrackBit tells a school director whether teaching is on plan and which students are slipping —
early enough to act — while asking each teacher for less than a minute a day.

TrackBit is **not** a school ERP. It sits beside whatever the school already uses and answers:
**"Is my school actually teaching well, right now?"** Full positioning, module rationale, and
the fences: `trackbit-product-architecture.md`.

### §1.2 Principles (every feature must pass all five)

- **P1 — One-minute teacher budget.** ≤ ~1 min/day of capture per teacher. Feature needs more → redesign or cut.
- **P2 — Plan is baseline, log is actual.** The system re-forecasts automatically; nobody manually maintains the plan.
- **P3 — Teachers get value before they give data.** Every capture pays the teacher back immediately.
- **P4 — Bands are private intervention tiers, never labels.** Staff-only, framed as support tiers with goals.
- **P5 — Nobody writes a report.** Every report is a byproduct of doing the work, captured at the
  moment of action, with evidence (a tap, a count, a photo).

### §1.3 Modules

| Code | Module | Status |
|---|---|---|
| M1 | Academic Planner (calendar · syllabus · plan · day celebrations) | NEW |
| M2 | Classroom Log & Sessions (lesson log · homework · after-school sessions) | NEW |
| M3 | Assessments & Bands (diagnostic · marks · skill profiles · A/B/C · interventions) | NEW |
| M4 | Director Dashboard & Weekly Digest (RAG · alerts · growth profiles) | NEW |
| M5 | Tasks (boards, recurring, celebration layer) | EXISTS — `task_management2` |
| M6 | Fees (structures, installments, payments, audit trail, xlsx import) | EXISTS — `fee_management_system`, to be PORTED |

---

## §2. Existing systems audit & integration strategy

### §2.1 What exists

**A. `task_management2/` (trackbit_api + trackbit_web) — the SEED.**
- Backend: FastAPI, **sync** SQLAlchemy 2, Alembic, PostgreSQL (Aiven) with **two DB roles + RLS**
  (org isolation), event-sourced task state, APScheduler jobs, notification engine
  (push → email ladder, Resend, web push), plan limits + Razorpay billing (stubbed), attachments
  (R2/local fallback), password-first auth (global usernames, magic-link invites, forced first
  password set), 91 passing tests, ruff clean.
- Frontend: Next.js 16 + React 19 + Tailwind v4 (CSS-first tokens, forest-green theme), TanStack
  Query, app shell (sidebar + mobile bottom tabs), Monday-style task tables with groups, kanban,
  celebration layer, PWA + web push, org dashboard/reports/trophy room.
- Read `task_management2/CLAUDE.md` — its six architectural laws apply to the whole unified app.

**B. `fee_management_system/` — working, but a different generation. To be PORTED, not mounted.**
- Backend: FastAPI, **async** SQLAlchemy, workspace-based tenancy (`workspace_id` FK scoping, no
  RLS), JWT auth (superadmin/admin write, staff read-only), no tests.
- Domain (the valuable part — port with care):
  - `FeeStructure` per (class + category + year) with installment templates; creating a new one
    archives the old (history preserved).
  - `StudentFee` per (student + academic_year) with concrete `Installment` rows (custom schedule /
    scaled from structure / lump).
  - **Money math** in `services/fees.py`: 2-dp `Decimal` via `q()`; status (paid/partial/
    overdue/pending) is **computed, never stored**; `opening_dues` arrears; discount changes
    re-scale only the unpaid portion.
  - **Append-only `transactions`** audit (payment | undo | discount | installment_edit); undo is a
    compensating row, never a delete.
  - **AI xlsx importer** (analyze → confirm mapping → commit) with keyword-heuristic fallback —
    tuned against the school's real registers. This becomes the unified app's roster+fee onboarding tool.
- Frontend: Next.js 14 pages — dashboard, students (list/add/detail), fee-structure, import, settings.

### §2.2 Integration decision (locked)

**One unified application.** New monorepo folder, single backend + single frontend, seeded by
copying `task_management2`'s two repos. The fee module is **ported into** the unified codebase
(models get `org_id` + RLS, routers become thin endpoints + services per the seed's laws, money
logic ports nearly verbatim, UI pages rebuilt on the v2 UI kit). Rationale:

1. The academic modules and the fee module both need **one students/classes/years master** (§4.2).
   Two apps = two student tables = permanent sync hell.
2. One auth, one sidebar, one notification engine, one DB, one deploy — right-sized for a solo
   founder + AI agents.
3. The seed codebase is strictly stronger (RLS, tests, event sourcing, jobs, channel-adapter
   notifications); porting fees up is cheaper than porting academics down.

The old `fee_management_system/` stays untouched as reference + the school's current working tool
until the unified app reaches fee parity (P0-F done-when includes a parity checklist §10).
`school_ops*` and the old `task_management/` folder are legacy — never copy from them.

### §2.3 New repo layout

```
trackbit_school/                  # founder creates this folder
  docs/                           # SPRD (this file), architecture v1.1, prd-v2, plan
  api/                            # seeded from task_management2/trackbit_api
    app/
      api/v1/endpoints/           # + academics/, fees/, students/, sessions/, assessments/, dashboard/
      services/                   # + academic_plan.py, calendar.py, lesson_log.py, homework.py,
                                  #   session.py, assessment.py, band.py, fees.py, students.py,
                                  #   day_suggest.py, ai/ (drafting + parsing)
      models/                     # + academics.py, students.py, fees.py, sessions.py, assessments.py
      schemas/                    # mirrors
      core/                       # unchanged laws; roles extended (§3)
  web/                            # seeded from task_management2/trackbit_web
    src/app/(app)/                # new IA per §6.2: today/, planner/, classroom/, sessions/,
                                  #   students/, assessments/, dashboard/, boards/ (existing),
                                  #   fees/, members/, settings/
```

Keep the seed's env conventions (`.env` / `.env.local`, stub-when-unconfigured integrations).
The Flutter app (`trackbit_app`) is **out of scope** for SPRD v1 — teachers use the PWA.

### §2.4 Bootstrap procedure (packet P0-A)

1. Copy `task_management2/trackbit_api` → `trackbit_school/api`; `trackbit_web` → `trackbit_school/web`
   (exclude `.venv`, `node_modules`, `.next`, `.git`; `git init` fresh repos; copy `.env.example`s).
2. Create a **new database** (same Aiven instance is fine): `trackbit_school_db`, with the same
   two-role setup (app role without BYPASSRLS + admin role for migrations). Do NOT point at the
   existing `trackbit_db`.
3. Run existing migrations against the new DB; seed; boot API + web; demo login works; existing
   task suite green. Only then start new packets.

---

## §3. Tenancy, roles & permissions

### §3.1 Tenancy

Org = school (unchanged from seed). All new tables carry `org_id`, are scoped in every query, and
get RLS org-isolation policies exactly like existing tables. `org_id` comes only from the verified
token (seed law #1).

### §3.2 Roles (extends the seed's admin/member)

`org_members.role` becomes: `admin` (Director — keeps all existing admin semantics) ·
`coordinator` · `teacher` · `office`. Existing `member` maps to `teacher` on migration.
New deps alongside `require_admin`: `require_coordinator_up` (admin|coordinator),
`require_academic` (admin|coordinator|teacher), `require_office_up` (admin|office).

### §3.3 Permissions matrix (backend-enforced; UI mirrors)

| Capability | Director (admin) | Coordinator | Teacher | Office |
|---|---|---|---|---|
| M1 calendar/syllabus/plan — edit & approve | ✔ | ✔ (approve = director only) | view own classes | — |
| Day suggestions — accept/skip | ✔ | ✔ | — | — |
| M2 log/homework — write | ✔ | ✔ | ✔ own classes | — |
| M2 sessions — run/capture | ✔ | ✔ | ✔ own sessions | — |
| M3 scores intake / verify | verify | verify | enter own classes | — |
| M3 bands & interventions | ✔ | ✔ | view/override own classes | — |
| M4 dashboard (whole school) | ✔ | ✔ | own growth profile only | fees card only |
| M5 tasks | per existing board rules (unchanged) | | | |
| M6 fees — write | ✔ | — | — | ✔ |
| M6 fees — read | ✔ | — | — | ✔ |
| Members/settings/billing | ✔ | — | — | — |

Hard rules: **teachers never see fees**; **office never sees academic data**; **band tiers are
never exposed on any parent-facing surface** (P4); admins still don't see private boards (seed law #5).

### §3.4 Parents

No login (v1). Guardians exist as **records** (§4.2) and receive outbound notifications only (§7).

---

## §4. Domain model (new tables; all with `id`, `org_id`, timestamps, RLS)

### §4.1 Conventions

Sync SQLAlchemy 2 models; Alembic migrations with the seed's naming convention; money = `Numeric(10,2)`
handled through the ported `q()` helper; dates in org timezone via `core/timeutil.py`. Where a
"who did it" matters, follow the seed's event/audit spirit: append rows, don't overwrite history.

### §4.2 Master data (shared by academics AND fees — the reason for unification)

- `academic_years` — label (`2026-27`), start_date, end_date, is_active. (Port concept from fee
  system's year selector; becomes a real table.)
- `terms` — academic_year_id, name, start_date, end_date.
- `school_classes` — name ("6"), section ("B"), academic_year_id, class_teacher_member_id?.
- `subjects` — name; `class_subjects` — class_id, subject_id, teacher_member_id,
  periods_per_week (int — entered, never generated). Unique (class_id, subject_id).
- `students` — admission_no (unique per org), full_name, class_id (current), roll_no?, status
  (active/left), category_id? (fee category FK), photo?. **Single master used by fees, academics,
  sessions, assessments.**
- `guardians` — student_id, name, relation, phone (E.164), is_primary, notify_opt_out bool.
- `student_categories` — ported from fee system (data, not enum; per-org; seeded "Day Scholar"/"Hosteller").

### §4.3 Calendar & plan (M1)

- `calendar_events` — type (`holiday` | `exam_block` | `event` | `celebration`), title, start_date,
  end_date, affects_teaching bool, notes. Working weekdays + term dates live on `academic_years`/org settings.
- `syllabus_units` — class_subject_id, position, title (chapter); `syllabus_topics` — unit_id,
  position, title, est_periods (int, default 1).
- `plan_entries` — class_subject_id, topic_id, week_start (Monday date). The approved set is the
  **baseline** (P2). `plans` — class_subject_id, status (`draft` | `approved`), approved_by/at.
  Re-forecast is **computed** from baseline + logs + remaining effective periods — never stored
  as mutated plan rows.
- `day_catalog` — global seed table (not org-scoped): date_rule (fixed date), name, blurb, tags.
  Curated list of national/international/observance days relevant to Indian schools.
- `day_suggestions` — org_id, catalog_id, for_date, status (`suggested` | `accepted` | `skipped`),
  accepted → creates a `calendar_events` row (type celebration) + AI-drafted prep checklist as M5 tasks.

### §4.4 Capture (M2)

- `lesson_logs` — class_subject_id, date, member_id, topic_id (nullable for off-plan), coverage
  (`full` | `partial`), note?. Unique (class_subject_id, date, topic_id).
- `homework_assignments` — class_subject_id, date, text, due_date?, attachment_id?, notified_at?.
- `homework_checks` — assignment_id, done_count, total_count, checked_at. (Counts only — never per-item grading.)
- `sessions` — name, owner_member_id, schedule (weekday set + time), active. `session_students` —
  session_id, student_id. `session_meetings` — session_id, date, evidence_attachment_id?.
  `session_attendance` — meeting_id, student_id, status (`present` | `late` | `absent`),
  late_minutes?, homework_done bool?.

### §4.5 Assessments & bands (M3)

- `skill_areas` — org-scoped, configurable (seed: Reading, Writing, Speaking, Math). Matches the
  director's existing paper diagnostic; TrackBit records, never authors (fence).
- `assessment_cycles` — type (`diagnostic` | `unit_test` | `term_exam`), term_id, name, date.
- `assessment_scores` — cycle_id, student_id, subject_id? (tests) or skill_area_id? (diagnostic),
  score, max_score, entered_by, verified_by?. CHECK: exactly one of subject_id/skill_area_id.
- `student_bands` — student_id, term_id, tier (`A` | `B` | `C`), scope (`overall` | skill_area_id),
  set_by, note. History kept: new row per change (append, don't update tier in place).
- `interventions` — student_id, term_id, goal_text, target_tier, status; `intervention_items` —
  checklist template lines. Activating an intervention **creates recurring M5 tasks** for the
  class teacher (template per item) and links back via `task_templates.intervention_id` (nullable FK).

### §4.6 Fees (M6 — ported; see fee CLAUDE.md for behavioral spec)

Port tables with `org_id` replacing `workspace_id`, FKs re-pointed at the unified `students` /
`school_classes` / `academic_years` / `student_categories`:
`fee_structures` + `fee_installment_templates`, `student_fees` (+ opening_dues, discount),
`installments`, `transactions` (**append-only — preserve undo-as-compensating-row exactly**).
Behavioral invariants to carry over verbatim: computed status, `q()` Decimal math, archive-on-replace
structures, proportional discount rescaling of unpaid amounts, waterfall spread on lump payments.
Importer: port analyze→confirm→commit flow + heuristic mapping; swap OpenRouter for the unified
AI service (§8) keeping the heuristic fallback.

---

## §5. Module functional specs

Format: capabilities → key endpoints (`/api/v1/...`) → Done-when. Thin endpoints, fat services,
`AppError` envelope (seed law #6) throughout.

### §5.1 M1 — Academic Planner

Capabilities: year/term/calendar setup; classes/subjects/periods; syllabus editor; AI week-draft;
plan review + approve (baseline lock); mid-year event insertion with visible absorption + reforecast;
day-celebration suggestion feed.

Endpoints: CRUD `years|terms|classes|subjects|class-subjects|calendar-events|syllabus`;
`POST /plans/{class_subject_id}/draft` (AI) · `PUT .../entries` (adjust) · `POST .../approve`;
`GET /plans/forecast?class_id=` (computed baseline-vs-projected per class-subject);
`GET /day-suggestions` · `POST /day-suggestions/{id}/accept|skip`.

Done-when: a director completes Flow 0 (arch doc §6) end-to-end in one sitting; adding a 2-week
event visibly shifts the forecast of affected class-subjects without mutating baseline rows;
accepting a day suggestion creates the calendar event + a prep board with AI-drafted tasks;
`effective_periods(class_subject, week)` has unit tests covering holidays, exam blocks, events.

### §5.2 M2 — Classroom Log & Sessions

Capabilities: teacher "My Day"; quick log (pre-filled topic → covered full/partial, deviation =
two taps); homework entry (text/photo/voice) → **guardian auto-notify**; next-day completion count;
4 pm reminder for unlogged classes; coordinator compliance view; sessions (define, roster, run
today's meeting: attendance + late minutes + homework ticks + one batch photo).

Endpoints: `GET /me/day` (classes today + planned topics + sessions + log status);
`POST /lesson-logs`; `POST /homework` (triggers notify) · `POST /homework/{id}/check`;
`GET/POST /sessions` · `POST /sessions/{id}/meetings` · `PUT /meetings/{id}/attendance`;
`GET /compliance?date=` (coordinator).

Done-when: quick log ≤ 3 taps for the pre-filled path and ≤ 25s wall-clock; homework post enqueues
guardian notifications (visible in console stub) within the same request cycle; scheduler fires the
4 pm unlogged reminder (org-local, tested like existing digest jobs); Flow 6 (arch doc) executes
end-to-end in ≤ 60s for a 15-student session; session record appears on the director dashboard
data API the same day.

### §5.3 M3 — Assessments & Bands

Capabilities: diagnostic intake (photo/xlsx/manual grid vs. configured skill areas); marks intake
per cycle; coordinator verify step; trends; weak-subject alert generation; band board (suggest →
confirm/override, append-history); interventions with checklist → recurring M5 tasks; band-movement
report; skill progress line per student across cycles.

Endpoints: CRUD `skill-areas|assessment-cycles`; `POST /cycles/{id}/scores/import` (photo/xlsx →
parsed rows for verify) · `PUT /cycles/{id}/scores` · `POST /cycles/{id}/verify`;
`GET /classes/{id}/trends`; `GET/POST /bands` ; `POST /interventions` (spawns tasks);
`GET /students/{id}/skill-profile`.

Done-when: importing the school's real diagnostic sheet (sample xlsx in fee repo root proves the
parser pattern) yields a verify grid with ≥ 90% cells pre-filled; confirming bands writes
append-only history; activating an intervention creates the recurring tasks and completing those
tasks shows in the intervention view; weak-subject alert fires in tests when a class average drops
across cycles.

### §5.4 M4 — Director Dashboard & Weekly Digest

Capabilities: RAG board (pace vs plan per class-subject); homework health; yesterday's session
records; alert feed; band-movement + skill summary; fees collection card (from M6, read-only);
one-tap alert→task; Monday digest (WhatsApp when configured, email/push meanwhile);
teacher growth profile (**v1.5** — per-term snapshots from existing data; growth-framed; no rankings).

Endpoints: `GET /dashboard/rag` · `/dashboard/homework` · `/dashboard/sessions?date=` ·
`/dashboard/alerts` · `POST /alerts/{id}/create-task`; digest job in `services/jobs.py`
(extend existing Monday recap machinery).

Done-when: dashboard renders from seeded demo data with all cards live; every alert row has a
working create-task that lands a pre-filled task on the right board; digest job passes the same
idempotency/TZ tests style as `run_digest`; teacher profile shows only self-data to teachers.

### §5.5 M5 — Tasks (existing; integration only)

No regressions to existing boards/recurrence/celebration/reports. Additions: `intervention_id`
on templates (§4.5); alert→task pre-fill; event/celebration → prep board; **two seeded board
templates**: Maintenance (task + photo + assignee convention) and Housekeeping (recurring
checklists + photo proof). Done-when: existing 91-test suite still green after all integrations.

### §5.6 M6 — Fees (ported)

Parity checklist = everything in §2.1-B works in the unified app against unified students/classes/
years, plus: role gates per §3.3, fees dashboard card exposed to M4, xlsx import (students + fees)
functioning with heuristic fallback. Done-when: side-by-side manual run — same xlsx imported into
old and new systems produces matching totals, installment schedules, and computed statuses; undo
produces a compensating transaction row; new backend tests cover `q()` math, discount rescale,
waterfall, status computation (the old system had none — write them during the port).

---

## §6. UI / UX specification

### §6.1 Design system

Reuse `trackbit_web`'s Tailwind v4 token system (globals.css `@theme`) as-is: forest-green primary,
amber warning, existing radii/spacing/type ramp, shadcn-style primitives, sonner toasts, TanStack
Query patterns, celebration layer (tasks only). Additions (build once in `components/ui/`):

- `RagChip` — red/amber/green status pill (semantic colors ≠ accent; used on dashboard + planner forecast).
- `WeekPlanBoard` — horizontal week columns × topic cards, drag between weeks (plan review).
- `YearCalendar` — 12-month grid with event/holiday/exam overlays + teaching-days counter.
- `SkillRadarCard` / `ProgressLine` — student skill profile (inline SVG like existing TrendSparkline; no chart lib).
- `BandBoard` — three-column tier board with movement arrows; private-to-staff badge always visible.
- `TapAttendanceRow` — tap-cycle present→late(+minutes stepper)→absent; ≤ 1 tap per present student.
- `SuggestionCard` — day-celebration card (Accept / Skip).
- `PhotoEvidenceButton` — camera-first capture, one per group (never per student).

Voice: plain school language ("Syllabus", "Homework", "Session", "Fees"), no jargon; every screen
has an empty state that teaches ("No plan yet — draft one in 2 minutes"); every error says what to do.

### §6.2 Information architecture — sidebar & mobile tabs

Desktop sidebar (grouped, role-filtered per §3.3; existing shell component extended):

```
TrackBit [school name]
├─ Today                      ← role-aware home: teacher=My Day, director=Dashboard, office=Fees
├─ ACADEMICS
│  ├─ Planner                 (calendar · syllabus · plan board · day suggestions)   [dir/coord; teacher read]
│  ├─ Classroom               (quick log · homework · compliance)                    [teacher/coord/dir]
│  ├─ Sessions                (my sessions · session capture)                        [teacher/coord/dir]
│  ├─ Students                (directory · profile · skill/band views)               [teacher own classes; coord/dir all]
│  └─ Assessments             (cycles · score intake · band board · interventions)   [per §3.3]
├─ Dashboard                  (RAG · alerts · reports · growth profiles)             [dir/coord; teacher sees own profile]
├─ Tasks                      (existing boards UI unchanged)                         [all staff]
├─ Fees                       (dashboard · students&fees · structures · import)      [dir/office]
├─ Members                    [dir]
└─ Settings                   (org · academic years · skill areas · billing)         [dir]
```

Mobile (PWA) bottom tabs, role-based — teacher (the primary mobile user): **Today · Log · Sessions ·
Tasks · More**. Director: **Dashboard · Alerts · Tasks · Fees · More**. Office: **Fees · Tasks · More**.
Existing 5-tab cap and bottom-tab component are reused.

### §6.3 Screen inventory & specs

Prefixes: PL (planner), CL (classroom), SS (sessions), ST (students), AS (assessments),
DB (dashboard), FE (fees). Existing task screens (S1–S10) and members/settings are unchanged.
Each spec = purpose / layout / states / budget. All screens: loading skeleton, taught empty state,
error+retry (patterns already exist in the seed).

**PL-1 Calendar (year view).** YearCalendar + right rail: add holiday/event/exam (type, dates,
affects-teaching). Header: "Effective teaching days: N" recomputes live. Director/coord edit.
**PL-2 Classes & subjects.** Table of classes → drawer per class: subjects, teacher assignment,
periods/week steppers. Guard: warns when Σ periods > weekly slots.
**PL-3 Syllabus editor.** Class-subject picker → unit/topic outline (inline add, drag reorder,
est_periods stepper). Import: paste chapter list → AI splits to topics (editable before save).
**PL-4 Plan board.** WeekPlanBoard; "Draft with AI" CTA when empty; topic cards show est_periods;
footer: effective periods vs plan load per week (over-budget weeks amber). Approve → locks baseline
(banner: "Baseline locked · [date]"). Post-approval the board becomes forecast view (PL-5 overlay).
**PL-5 Plan vs forecast.** Per class-subject: baseline line vs projected line (ProgressLine),
RagChip, "projected finish: [date] (exam: [date])". Drill rows → week detail.
**PL-6 Day suggestions.** SuggestionCard feed ("Teachers' Day · in 12 days"); Accept → confirm
sheet (periods affected preview + draft plan) → creates event + prep board. Skip is one tap.

**CL-1 My Day (teacher home).** Today's periods as cards (class · subject · this week's topic
pre-filled) with log state; today's sessions below; yesterday's homework check chips. This is the
teacher's `Today` tab. Budget: everything reachable in ≤ 2 taps.
**CL-2 Quick log.** One screen per class card: big "Covered: [topic]" button (tap = full),
"partially" secondary, "different topic" opens topic picker (2 taps). Homework field below:
text / mic / camera. Save → toast "Logged · 38 parents notified". Budget: ≤ 3 taps, ≤ 25s.
**CL-3 Homework check.** Yesterday's assignment → count stepper "34 / 40 done". One screen, one number.
**CL-4 Compliance (coordinator).** Date grid: teachers × periods, logged/unlogged dots; tap → nudge
(reuses task/notification nudge with 4h dedupe).

**SS-1 My sessions.** Session cards (name, schedule, roster count) + create sheet (name, weekdays,
time, student picker filtered by class).
**SS-2 Session capture.** Roster list of TapAttendanceRow; homework toggle per row; sticky footer:
PhotoEvidenceButton (batch) + Done. Budget: 15 students ≤ 60s.

**ST-1 Students directory.** Search/filter by class; row → ST-2. Bulk import CTA → FE-5 importer
(students mode). **ST-2 Student profile.** Tabs: Overview (class, guardians, session attendance
strip) · Skills (SkillRadarCard + ProgressLine across cycles) · Band & intervention (tier history,
goal, checklist task status) · Fees (director/office only — office deep-links to FE-3). Band tab
carries the "Staff only — never shared with parents" badge (P4).

**AS-1 Cycles.** List + create (type, term, date). **AS-2 Score intake.** Grid students × (skills |
subjects); prefill via xlsx/photo upload → parsed cells marked for review; manual entry fallback;
submit → "awaiting verification". **AS-3 Verify (coordinator).** Diff-style review → confirm.
**AS-4 Band board.** BandBoard per class; suggested moves flagged; confirming C-tier opens
intervention sheet (goal, target, checklist template → spawns recurring tasks). **AS-5 Trends.**
Class/subject averages across cycles; weak-subject alerts inline.

**DB-1 Director home.** Card grid: RAG board (top), Alerts feed (each row: context + "Create task"),
Yesterday's sessions, Homework health, Fees collection card, Band movement. 10-minute-read design:
summary numbers first, drill-downs behind taps. **DB-2 Class-subject drill-down.** Pace line,
log history, homework rate, marks trend, teacher + create-task. **DB-3 Growth profile (v1.5).**
Per-teacher term snapshots (pace, consistency, homework regularity, band movement); teacher sees
self; director sees all; explicitly no ranking view. **DB-4 Digest archive.** Past Monday digests.

**FE-1 Fees dashboard** · **FE-2 Students & fees list (year-scoped)** · **FE-3 Student fee detail**
(installments, pay, undo, discount — port of old detail page) · **FE-4 Fee structures** ·
**FE-5 Import (xlsx analyze→map→commit; modes: students / fees)** — all rebuilt on v2 UI kit,
functionality per §5.6. Global academic-year switcher lives in the app header (replaces the old
fee app's year state) and scopes FE-* and relevant academic views.

### §6.4 UX laws (acceptance criteria for every teacher-facing screen)

1. Interaction budgets are tested claims: CL-2 ≤ 3 taps; SS-2 ≤ 60s/15 students; log-state visible
   without scrolling on a 360px viewport.
2. Prefill over input: the planned topic, today's date, the session roster — the user confirms,
   not enters. Free text is always optional, never required to save.
3. Optimistic UI with rollback (existing `lib/optimistic.ts` pattern) on all captures; teachers on
   flaky school Wi-Fi must never lose a tap — mutations queue one retry before erroring.
4. Evidence is batch-level (one photo per pile/meeting), never per student (P1 fence).
5. Semantic color (RAG) is reserved for status; never decorate with red/amber/green.
6. Every notification a teacher receives must be actionable in ≤ 2 taps from the notification.

---

## §7. Notifications matrix

Reuse the seed's channel-adapter dispatcher + jobs. **New channel: `whatsapp`** (Interakt or Meta
WhatsApp Cloud API) — env-gated like Resend/R2 (`WHATSAPP_*` keys; console stub logs the exact
message when unconfigured). Guardian messages REQUIRE WhatsApp/SMS in production (parents have no
app/email); dev + pilot-start run on the stub, and go-live of guardian notify is gated on keys.

| Trigger | Recipient | Channel ladder | Content |
|---|---|---|---|
| Homework logged | guardians of class (opt-out respected) | whatsapp → (none) | subject, homework text, due date |
| Weekly summary (Sat) | guardians | whatsapp | homework given/done counts for their child |
| 4 pm unlogged class | teacher | push → email | "2 classes not logged — tap to log" |
| Session missed (no meeting record on scheduled day) | session owner | push | reminder |
| Weak-subject alert / pace red | director + coordinator | push → email | class, subject, gap |
| Monday digest | director | whatsapp → email | top 3 issues + wins, deep link |
| Day suggestion (T-14d) | director | in-app card (+digest mention) | Accept/Skip |
| Fee events (receipt, defaulter batch) | as per ported fee flows | existing | unchanged |
| Task notifications | existing | existing | unchanged |

Compliance notes: store guardian consent flag at roster import; every guardian message footer
supports opt-out; никогда — band/tier information **never** appears in any guardian message (P4).

## §8. AI services (`app/services/ai/`)

Single internal client, env-gated (`ANTHROPIC_API_KEY`; stub returns deterministic fixtures when
unset so all flows are testable offline). Invisible plumbing — no chat surfaces (fence).

| Service | Used by | Model default | Notes |
|---|---|---|---|
| `plan_draft` | PL-4 | `claude-sonnet-5` | syllabus + effective periods → week distribution JSON; human approves |
| `celebration_draft` | PL-6 | `claude-sonnet-5` | day + school context → activities + prep checklist |
| `syllabus_split` | PL-3 | `claude-haiku-4-5-20251001` | pasted chapter text → units/topics |
| `sheet_map` | FE-5, AS-2 | `claude-haiku-4-5-20251001` | column mapping (port of fee importer's AI step; heuristic fallback KEPT and tested) |
| `marks_photo_parse` | AS-2 | `claude-sonnet-5` (vision) | marks-register photo → grid cells flagged low-confidence for review |
| `homework_parse` | CL-2 (voice/photo path) | `claude-haiku-4-5-20251001` | free capture → structured homework |

Model ids in env (`AI_MODEL_DRAFT`, `AI_MODEL_PARSE`) so upgrades are config, not code. Every AI
output lands in a human-confirm surface before persisting (verify grids, editable drafts).

## §9. Non-functional requirements

- **Security/tenancy:** seed laws 1–2 (org_id from token; RLS engaged per request) on every new
  table/endpoint; permissions matrix §3.3 enforced in services; attachments ACL: session evidence
  and marks photos readable by academic roles only.
- **Auditability:** band changes, plan approvals, score verifications, and all fee transactions are
  append-only rows with actor + timestamp.
- **Performance:** teacher screens (CL-1/2, SS-2) interactive < 2s on 4G; dashboard queries served
  by indexed aggregates (add indexes with each packet); no N+1 in list endpoints (test with seed data
  at 1 school × 20 classes × 800 students scale).
- **Reliability:** scheduler idempotency + org-TZ correctness tested like existing jobs; notification
  retry ×3 (existing sweep).
- **Compatibility:** existing task module behavior unchanged (its test suite is the regression gate).
- **Seeds:** `scripts/seed.py` extended — demo school with 3 classes, 2 teachers, coordinator,
  office user, 60 students + guardians, one approved plan, a week of logs, one session, one
  diagnostic cycle, fee structures + payments. Every screen must render meaningfully from seed.

## §10. Build plan — phases & packets

Sequence respects the pilot logic (architecture doc §9). Each packet is agent-dispatchable;
backend/frontend packets within a phase can run in parallel unless marked serial. **Done-when**
gates per §0.2 plus what's listed.

**P0 — Foundation (serial start)**
- **P0-A Bootstrap** (§2.4) + copy docs into `docs/`. Done-when: fresh clone boots, task suite green on new DB.
- **P0-B Roles** (§3.2–3.3): enum migration (`member`→`teacher`), new deps, role-aware nav skeleton +
  role-based `Today` redirect. Done-when: matrix §3.3 has a permissions test per row.
- **P0-C Master data** (§4.2): models + CRUD + Settings screens (years/terms/classes/subjects/skill areas)
  + ST-1/ST-2(Overview) + roster xlsx import (importer port, students mode). Done-when: demo school
  seedable via UI alone; roster import round-trips the sample sheet.
- **P0-D Fee port — backend** (§4.6, §5.6): models on org_id, services (money math + tests), endpoints,
  RLS. Serial after P0-C (needs students). Done-when: §5.6 backend tests green.
- **P0-E Fee port — frontend**: FE-1..5 on v2 kit + header year switcher. Done-when: §5.6 parity run passes.

**P1 — Planner + Classroom Log (the make-or-break phase)**
- **P1-A Calendar & effective days** (PL-1, calendar_events, effective-periods engine + tests).
- **P1-B Syllabus** (PL-3 + syllabus_split AI + PL-2 periods).
- **P1-C Plan draft/approve/forecast** (PL-4, PL-5, plan_draft AI, forecast computation + tests). Serial after A+B.
- **P1-D Quick log + My Day** (CL-1, CL-2, lesson_logs, 4 pm reminder job).
- **P1-E Homework + guardian notify** (homework tables, WhatsApp adapter + stub, CL-3, Sat summary job).
- **P1-F Compliance** (CL-4 + nudge reuse).
- Phase gate: Flow 0 + Flow 1 + Flow 2 demo-able end-to-end on seed data; pilot metric
  instrumented (daily log compliance % query exists — it's the week-4 make-or-break number).

**P1.5 — Sessions** (founder is first user)
- **P1.5-A** Sessions backend + SS-1/SS-2. **P1.5-B** dashboard sessions feed (DB-1 card) + missed-session
  reminder. Done-when: Flow 6 ≤ 60s live run; next-morning director view shows the record.

**P2 — Dashboard & digest**
- **P2-A** RAG/homework/alerts aggregates + DB-1/DB-2 + alert→task. **P2-B** Monday digest job
  (whatsapp→email ladder) + DB-4. **P2-C** Maintenance/Housekeeping board templates + day_catalog
  seed + PL-6 suggestions (celebration_draft AI). Done-when: §5.4 criteria.

**P3 — Assessments & bands (term-start aligned)**
- **P3-A** Cycles/scores/verify (AS-1..3, sheet_map + marks_photo_parse). **P3-B** Bands +
  interventions + ST-2 Skills/Band tabs + AS-4/5 + weak-subject alerts → tasks. Done-when: §5.3
  criteria + band history append-only test.

**v1.5 (post-pilot):** DB-3 growth profile; WhatsApp capture channel for CL-2; report polish.

## §11. Fences

The architecture doc §8 table is binding. Agent shorthand: no timetable generator (periods/week is
data), no school-wide attendance registers (Sessions only), no test authoring, no parent app/login,
no chat UI, no per-student evidence photos, no visitor/inventory/social/health modules, no
report-card designer, LMS/teacher-training = Playground (separate product).

## §12. Defaults taken (change only by founder decision)

INR; Asia/Kolkata; April–March academic year; English UI (v1); guardian channel = WhatsApp
(stub until keys); billing = existing Free/Pro scaffold with school pricing TBD before sales;
old fee app remains the school's live tool until §5.6 parity passes; Flutter app deferred;
diagnostic skill areas seeded as Reading/Writing/Speaking/Math and edited in Settings to match the
director's paper test.
