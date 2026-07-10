# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is right now

**TrackBit School** — **the school's daily operating system** (v2 redesign, July 2026): it plans
the academic year down to the period, captures each day with near-zero teacher effort
(capture-by-exception), knows what every student is doing during school + hostel hours, and
writes the school's daily report itself.

The spec lives in `docs/` (also mirrored at the repo root):

- `trackbit-school-prd-v2.md` — **SPRD v2.0, the CURRENT build spec** (cite as `SPRD2 §x.y`).
  Vision, roles, IA, new modules (wizard, timetable, attendance, My Day v2, recommendations,
  daily report, student timeline), packets V2-P0..P5.
- `trackbit-school-prd-v1.md` — SPRD v1.0; still the reference for carried modules (fees, tasks,
  assessments, sessions, master data).
- `trackbit-product-architecture.md` — the "why": principles + fences (see its v1.2 addendum).

**Conflict order: SPRD2 > architecture doc > SPRD v1**; an explicit later founder decision wins
over all.

## Build status (what exists now)

**P0 (foundation) is complete**, verified against real Postgres (backend suite **143 passing**,
ruff clean; web tsc + eslint + `next build` clean). Migration head = **`d3f4a5b6c7d8`**.

- **P0-A** — `api/` + `web/` seeded from the task_management2 seed; `docs/`; AI (§8) + WhatsApp (§7)
  config stubs; monorepo git.
- **P0-B** — roles `admin`(Director)/`coordinator`/`teacher`/`office` (`member`→`teacher` migration);
  `core/roles.py` groups; `require_coordinator_up`/`require_academic`/`require_office_up`;
  role-aware nav + `landingForRole`; Members UI on 4 roles.
- **P0-C** — master data (§4.2): `models/academics.py` + `models/students.py` (8 org-scoped+RLS
  tables), `AcademicService`/`StudentService`, 19 endpoints under `/academics` + `/students`;
  frontend `/academics` setup + `/students` (ST-1/ST-2); **roster xlsx importer** (heuristic
  mapping, `roster_import.py`, `/students/import/*`, FE-5).
- **P0-D** — fee port (§4.6): `fee_math.py` (ported money math), `models/fees.py` (5 tables),
  `FeeService`, 11 endpoints under `/fees` (all `require_office_up`).
- **P0-E** — fee frontend: `/fees` (summary + list + enrol), `/fees/[id]` (pay/undo/discount +
  ledger), `/fees/structures`; global year switcher (`year-context` + `YearSwitcher`).

**P1 (Planner + Classroom Log) is in progress** — migration head **`d6c7d8e9fab0`**:
- **P1-A** — `CalendarEvent` + `academic_years.working_weekdays`; `services/calendar.py`
  effective-teaching-days engine; `/academics/calendar/*`; web `/planner` (PL-1).
- **P1-B/C** — `models/planner.py` (syllabus_units/topics, plans, plan_entries); `PlannerService`
  (greedy `distribute`, heuristic `split_text`, draft/approve baseline, computed forecast);
  `/planner/*`; web `/planner/plan` (PL-3/4/5).
- **P1-D/E/F** — `models/classroom.py` (lesson_logs, homework_assignments/checks);
  `ClassroomService` (My Day, quick log, homework + guardian-notify stub, compliance);
  `notify_guardian.py` (WhatsApp console stub); `/classroom/*`; web `/classroom` (My Day, CL-1/2/3)
  + `/classroom/compliance` (CL-4).

Demo logins (all `demo1234`): `kc@` (director), `priya@` (coordinator), `ramesh@`/`anil@` (teachers)
— all `@demo.trackbit.app`.

- **P1.5** — `models/sessions.py` (sessions, session_students, session_meetings, session_attendance;
  migration `d7d8e9fab0c1`); `SessionService`; `/sessions/*`; web `/sessions` (SS-1) +
  `/sessions/[id]` (SS-2 tap-capture + one batch photo).
- **P2** — Director Dashboard (M4): `services/dashboard.py` composes planner forecast + fees + session
  records + classroom compliance/homework + weak-subject trends into a RAG board + alert feed;
  one-tap **alert→task**; Monday **digest** preview. `/dashboard/*` (fee card director-only, §3.3);
  web `/insights`. Board templates (Maintenance/Housekeeping) ship via seed (§5.5).
- **P3** — Assessments & Bands (M3): `models/assessments.py` (skill_areas, assessment_cycles,
  assessment_scores, student_bands, interventions, intervention_items; migration `d8e9fab0c1d2`);
  `AssessmentService` (skill areas, cycles, score grid + verify, band suggestion + append-only set +
  history, skill profile, subject trends + weak detection, interventions that spawn M5 tasks and
  track completion); `/assessments/*`; web `/assessments` (scores grid / bands / trends tabs) + skill
  areas on `/academics`. Weak-subject alerts feed the dashboard. Migration head **`d8e9fab0c1d2`**.

**All SPRD v1 product phases P0–P3 are complete.** v1 deferred items (fees-mode xlsx import, cron
wiring of jobs, day suggestions, growth profile) are folded into the v2 packets (SPRD2 §9–§10).

**v2 redesign (2026-07-07 → 2026-07-08): ALL PACKETS COMPLETE (V2-P0-A … V2-P5).**
Migration head = **`f4e5f6a7b8c9`**. Backend **200 tests passing**, ruff clean; web tsc + eslint +
`next build` clean. Verified end-to-end (server boots, demo login, all v2 screens populated).
- **V2-P0-A (roles) COMPLETE** — two roles admin/teacher (SPRD2 §2); migration `e9fab0c1d2e3`
  applied (head); coordinator/office collapsed into admin; seed + all guards + web types/nav/13
  page guards updated. Backend **162 tests passing**, ruff clean; web tsc + eslint + build clean.
- **V2-P0-B (IA reshell) COMPLETE** — frontend only (SPRD2 §3, §6, §12). Consolidated nav:
  teacher sidebar (5) `My Day · Sessions · Plan · Students · Tasks`; admin (6) `Dashboard · Plan ·
  Students · Fees · Tasks · Setup`. New route-based tab areas (`SubTabs` component + per-area
  `layout.tsx`): **Tasks** (Today/Boards/Done) · **Plan** (Year/Syllabus/Week plan/Timetable —
  Timetable is a V2-P1 placeholder) · **Students** (Directory/Scores/Bands/Trends — Assessments
  moved here) · **Setup** (Academics/Members/Settings, admin-only, hosts the wizard later). Route
  renames `/insights`→`/dashboard`, `/classroom`→`/my-day`, `/academics`→`/setup`; compliance page
  deleted. All 12 old routes 307-redirect via `next.config.ts` (`/boards/:id` etc. preserved).
  `landingForRole`: admin→`/dashboard`, teacher→`/my-day`. web tsc + eslint + `next build` clean.
- **V2-P1 (Timetable) COMPLETE** — SPRD2 §4/§5.3. Backend: `models/timetable.py`
  (`timetable_slots`, effective-dated append-only cells) + `academic_years.periods_per_day`
  /`period_times`; migration `f0a1b2c3d4e5` (head); `TimetableService` (grid CRUD with
  effective-dating, deterministic teacher-clash validator, teacher week, period config,
  photo/xlsx import via env-gated `services/ai/timetable.py` stub, flag-gated assisted draft
  `TIMETABLE_ASSISTED_DRAFT`); 12 endpoints under `/timetable`; My Day now renders today's
  periods from the grid. `test_timetable.py` (8 tests, incl. clash + effective-dating +
  admin-only). Backend **170 tests passing**, ruff clean. Frontend: Plan → Timetable tab
  (grid editor + import + draft + periods/day for admin, own-week read view for teacher),
  `TimetableGrid`/`TeacherWeekGrid` components, `api.put`; web tsc + eslint + build clean.
- **V2-P2 (Attendance + absence alerts + My Day v2) COMPLETE** — SPRD2 §4.4/§5.4/§7.
  Capture-by-exception (P1v2): `models/attendance.py` (`attendance_marks` = one row per
  class-period taken; `attendance_exceptions` = absent|late deviations — **no per-student
  present rows**); migration `f1b2c3d4e5f6` (head). `AttendanceService`: `roster` (capture
  sheet), `mark` (idempotent full-replace of the exception set; "all present" = empty
  exceptions), `period_states`/`roster_sizes` (My Day roll-up). First marked period of the
  day fires guardian **absence alerts** (§7) via `notify_guardians`, idempotent through
  `alerted_at`; plain text only, never band info (P4). Endpoints `/attendance/roster` +
  `/attendance/mark` (require_academic; service checks the teacher teaches the class). My Day
  v2: period cards read attendance state; `test_attendance.py` (6 tests incl. the §5.4
  period-card e2e). Backend **176 tests passing**, ruff clean. Frontend: `/my-day` period
  cards (All-present one-tap + exception sheet cycling present→absent→late, topic log,
  homework), `attendanceRoster`/`markAttendance` in `school-api`, Badge `danger` tone; web
  tsc + eslint + `next build` clean.
- **V2-P3 (Recommendations + daily checks + per-student homework) COMPLETE** — SPRD2 §5.5.
  `models/checks.py` (`daily_checks` = class_subject×date recommendation, band_scope all|A|B|C,
  optional `student_id` for intervention lines, `confirmed_at`; `check_results` = not_done|note
  exception rows only); per-student homework via `homework_assignments.student_id`; migration
  `f2c3d4e5f6a7` (head). `RecommendationsService.ensure` generates-if-absent from planned topic ×
  band distribution — **zero teacher setup**; volume capped (≤2 class-wide + 1 richer C-band +
  ≤1 per intervention student); `confirm` = "class did it ✓" + full-replace exception set.
  `services/ai/checks.py` (env-gated `draft_checks`, deterministic fallback templates, §8).
  Endpoints `/checks` (get-or-create) + `/checks/{id}/confirm` (require_academic; teacher must
  teach the class). Per-student homework notifies only that student's guardians (P3). My Day
  period card gains a Checks section (Class-did-it one-tap + flag-exceptions sheet) + per-student
  homework picker. `test_recommendations.py` (6 tests: zero-setup+cap, C-band richer check,
  intervention targeting, confirm+exceptions, per-student homework, access). Backend **182
  passing**, ruff clean; web tsc + eslint + `next build` clean.
- **V2-P4 (Daily report agent + student timeline + cron wiring) COMPLETE** — SPRD2 §5.6/§5.7/§9.
  `models/reports.py` (`daily_reports`, one row per org×`for_date`, `content_md` + `highlights`
  JSON {risks,ambiguities,wins,sections}, status draft|final; migration `f3d4e5f6a7b8`).
  `DailyReportService`: deterministic day aggregation (attendance/logs/homework/checks/sessions/
  plan pace/fees) → `report_write` narrative; **ambiguity rules** attendance-without-log ·
  log-without-attendance · plan-red streak · repeat-absentee-≥3-days; `generate` upserts one row
  (never overwrites a `final`); reuses services via a synthetic admin context.
  `services/ai/report.py` env-gated (AI-off still produces the deterministic report).
  `/reports/daily` (get-or-create) + `/reports/daily/regenerate` (require_admin — includes fees).
  Student **timeline** (§5.7): `services/timeline.py` — computed join (timetable × attendance ×
  logs × checks × homework × sessions), **no new capture tables**, absent periods = gaps;
  `GET /students/{id}/timeline`. **Cron wiring** (§9): `jobs.run_daily_report` (19:00 draft /
  06:00 regen-draft / 08:00 admin notify), `run_teacher_reminder` (16:00 unmarked/unlogged →
  teacher), `run_saturday_summary` (Sat 08:00 guardian week note) — all TZ-aware + idempotent,
  wired into `run_hourly` + `/ops/run/*`. `test_daily_report.py` (7) + `test_timeline.py` (2).
  Backend **191 passing**, ruff clean. Frontend: Dashboard leads with `ReportView` (risks +
  expandable sections); student profile gains a Timeline block; `dailyReport`/`studentTimeline`
  in `school-api`. web tsc + eslint + `next build` clean.
- **V2-P5 (Wizard + smart ingestion + plan generation) COMPLETE** — SPRD2 §5.1/§5.2. **All v2
  packets done.** `models/onboarding.py` (`onboarding_state`, resumable — no parallel store) +
  `PlanComment` (teacher change-requests on the plan); migration `f4e5f6a7b8c9`. `WizardService`:
  9-step resumable state; **progress derived from the real tables** (write-through, always
  truthful). `services/plan_validate.py`: the 4 deterministic validators V1 capacity · V2
  coverage · V3 ordering · V4 teacher-load (pure, unit-tested). `PlannerService.generate_plan`
  (proposer `distribute` + validators; over-capacity → `fits=False`, reported not squeezed) +
  plan comment add/list/resolve round-trip. Endpoints `/wizard/*`, `/planner/plan/{cs}/generate`,
  `/planner/plan/{cs}/comments`. `test_plan_generation.py` (7) + `test_wizard.py` (2). Backend
  **200 passing**, ruff clean. Frontend: `/setup/wizard` — guided 9-step stepper (year · exams ·
  timings · classes/subjects · syllabus · teachers · students · timetable · generate+lock),
  resumable, reusing every module API; the final step generates + locks all plans. web tsc +
  eslint + `next build` clean.
- **Seed enriched for v2**: the demo org now has school timings, a full **timetable** (75 slots),
  today's **per-period attendance** (with an absence + late), **daily checks** (confirmed + a
  C-band check), and a generated **daily report** — so every v2 screen renders with real data.
  Verified end-to-end: server boots, login works, My Day/timeline/report/wizard all populate.

## How this repo was bootstrapped (background)

Per SPRD §2.4 (packet **P0-A**) the app was **seeded from two sibling projects** (not inside this
folder):

- **`../task_management2/`** — the **SEED** copied into `api/` + `web/`. Its `CLAUDE.md` and its six
  architectural laws (below) govern **all** code here. **Read `../task_management2/CLAUDE.md`
  before writing backend code.** Stack: FastAPI + **sync** SQLAlchemy 2 + PostgreSQL (two DB
  roles + RLS), event-sourced tasks, APScheduler, channel-adapter notifications, magic-link auth,
  Next.js 16 + React 19 + Tailwind v4.
- **`../fee_management_system/`** — the fee module, **PORTED not mounted** (it's an older async /
  JWT / workspace-tenancy generation). Port its money domain nearly verbatim; see its `CLAUDE.md`
  and SPRD §4.6/§5.6 for the behavioral invariants. The real school registers to test the xlsx
  importer against are `shana_fee.xlsx` / `shana_extra_fee.xlsx` in that folder.

Legacy — **never copy from these:** `../task_management/` (old), `../school_ops*`. The old
`fee_management_system` stays live as the school's working tool until the unified app reaches fee
parity (SPRD §5.6 checklist).

### Layout

```
api/    ← FastAPI backend (+ academics/students; sessions/assessments/dashboard/fees to come)
web/    ← Next.js frontend (new IA per SPRD §6.2 as modules land)
docs/   ← the four spec docs
```

## Commands

Backend, from `api/` (Python 3.12, **uv** — not pip/poetry):

```bash
uv sync --extra dev                          # install deps
uv run uvicorn app.main:app --port 8000      # run API (NO --reload; restart after edits)
uv run pytest -q                             # full suite
uv run pytest tests/test_master_data.py::test_name   # single test
uv run ruff check app tests                  # lint (--fix to auto-fix)
uv run alembic upgrade head                  # migrations
uv run python -m scripts.seed                # demo data (login kc@demo.trackbit.app / demo1234)
```

Frontend, from `web/` (Node 20+): `npm run dev` (needs API up), `npm run build`, `npm run lint`,
`npx tsc --noEmit`. Env: only `NEXT_PUBLIC_API_BASE_URL` (must end in `/api/v1`).

**Packet Done-when gate:** backend packets end green on `uv run pytest -q` + `ruff`; frontend packets
end green on `npx tsc --noEmit` + `eslint` + `next build`. The **full backend suite (currently 130) is
the regression gate** — it must stay green after every change.

### Local dev database (validated setup)

Tests/Alembic need **real PostgreSQL** (no SQLite fallback) with the two-role RLS setup. `api/.env`
is a template pointing at a to-be-created Aiven `trackbit_school_db` (SPRD §2.4 — do **not** reuse the
seed's `trackbit_db`). For local dev, the seed's `docker-compose.yml` gives you Postgres on `:5434`:

```bash
# from api/
docker compose up -d db                       # postgres 16 on localhost:5434 (user/pw/db: trackbit)
# one-time: a restricted, NOBYPASSRLS app role so RLS actually applies (test_rls needs this)
docker exec -i trackbit_db psql -U trackbit -d trackbit_test -c \
  "CREATE ROLE trackbit_app LOGIN PASSWORD 'apppass' NOSUPERUSER NOBYPASSRLS; \
   GRANT USAGE ON SCHEMA public TO trackbit_app; \
   GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO trackbit_app; \
   GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO trackbit_app; \
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO trackbit_app;"
# then run with the app role for DATABASE_URL and the owner for migrations:
export DATABASE_URL="postgresql+psycopg2://trackbit_app:apppass@localhost:5434/trackbit_test"
export ADMIN_DATABASE_URL="postgresql+psycopg2://trackbit:trackbit@localhost:5434/trackbit_test"
uv run alembic upgrade head && uv run pytest -q
```

(Grants must be re-run only if migrations add tables *before* those tables have rows the app touches;
`ALTER DEFAULT PRIVILEGES` covers new tables created afterward.)

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

- **P1v2 — One-minute budget via capture-by-exception.** The teacher confirms the norm in one tap
  and records only deviations (attendance = "all present" minus tapped absentees; checks = "class
  did it" minus exceptions). Budgets: quick-log ≤ 3 taps / ≤ 25s; routine period card ≤ 5 taps /
  ≤ 30s; 15-student session ≤ 60s. Any feature needing per-student entry for a whole class is
  mis-designed — redesign or cut.
- **P2 — Plan is baseline, log is actual.** The approved plan is locked; re-forecast is **computed**
  from baseline + logs + remaining effective periods — never stored as mutated plan rows.
- **P3 — Teachers get value before they give data** (logging homework auto-notifies parents).
- **P4 — Bands (A/B/C) are private intervention tiers, never labels.** Staff-only; **never** appear on
  any parent/guardian-facing surface (message, report, anything).
- **P5 — Nobody writes a report.** Every report is a byproduct of doing the work, captured at the
  moment with evidence (a tap, a count, a batch photo — never per-student photos).

## Roles & hard rules (v2 — SPRD2 §2, implemented)

**Two roles only:** `admin` (runs the school: setup, plan approval, bands, fees, dashboard,
members) · `teacher` (all academic staff incl. wardens: My Day, sessions, plan/timetable views,
their students, tasks). Migration `e9fab0c1d2e3` collapsed coordinator/office → admin.
`require_coordinator_up` / `require_office_up` are now **admin-only aliases** (consolidate to
`require_admin` opportunistically when touching a file); `require_academic` = any member.
Non-negotiable: **teachers never see fees; band tiers never reach parents/guardians.**
Parents have **no login** — guardians are records that receive outbound notifications only.

## AI services & stubs

All AI lives in `app/services/ai/`, routed through **OpenRouter** (one OpenAI-compatible endpoint,
any model, one key) via `ai/client.py::chat_json` — the only function here that touches the network.
It is **env-gated**: with `OPENROUTER_API_KEY` unset every call short-circuits and the caller's
deterministic heuristic runs, so all flows are testable offline. Same pattern as the seed's
integrations (email/R2/billing/push stub when keys blank). **No chat UI** — AI is invisible plumbing
(plan drafts, celebration drafts, syllabus split, xlsx/photo parsing), and **every AI output lands in
a human-confirm surface before persisting** (editable drafts, verify grids). Model ids come from env
as OpenRouter slugs (`AI_MODEL_DRAFT=anthropic/claude-opus-4.8`,
`AI_MODEL_PARSE=anthropic/claude-sonnet-5`); browse slugs at openrouter.ai/models.

Two rules make it safe in the setup wizard's critical path:

- **`chat_json` fails soft, never up.** Timeout, 429, 5xx, prose-instead-of-JSON → returns `None`,
  the heuristic runs, the admin never sees a stack trace. A non-retryable 4xx (bad key, bad slug)
  breaks out immediately rather than making them wait through a retry.
- **Deterministic validators decide; the model only proposes and phrases.** `ingest.py` asks the
  model to map only the columns the keyword heuristic *couldn't* place — never overriding an exact
  header match — then filters the reply against the real column list, so a hallucinated column can't
  reach an importer. AI proposals are flagged `low_confidence` for the human's glance.

## Fences — v2 (SPRD2 §11, binding; supersedes arch §8)

**Moved IN by founder decision (July 2026):** per-period attendance (capture-by-exception only) ·
timetable (import-first + AI-assisted draft with **deterministic** validators — still no guaranteed
solver) · daily report generation · per-student homework.

**Still OUT:** payroll/HR/library/transport/inventory/visitor/social modules · report-card
designer · test authoring/conducting · parent app or login (notifications only) · chat UI /
AI-orchestrator surface · **mandatory per-student capture** (exception-only, always — P1v2) ·
per-student evidence photos (batch only). LMS + teacher training = Playground's lane.

## Build order

Work **packet-by-packet** per **SPRD2 §10**; do not mark a packet done until its **Done-when**
criteria pass. Sequence: V2-P0-B (IA reshell) → V2-P1 (timetable) → V2-P2 (attendance + My Day v2)
→ V2-P3 (recommendations/checks) → V2-P4 (daily report + timeline + cron wiring) → V2-P5 (wizard +
plan generation). After every packet the v1 flows (quick log, sessions, fees, tasks) must still
pass their tests. The core loop v2: **wizard compiles the year → teachers confirm each period by
exception → the system joins it into per-student truth → the 8 AM report tells the admin what
needs attention → gaps become tasks.**
