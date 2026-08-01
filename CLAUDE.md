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

## Brainstorm sessions — `docs/brainstorm/`

**Trigger: when the founder says "let's brainstorm on \<module\>"** (or "brainstorm session", or
names a module and asks to think about it rather than build it), **read
`docs/brainstorm/HOW-WE-BRAINSTORM.md` and follow that protocol.** It is the ritual; this section
is only the pointer.

Running since 2026-07-30, one module at a time, **UI/UX first** — a person, at a moment, with a
question; never tables and endpoints. **No code is written during a brainstorm session** — no
migrations, no packets, no branches. The output is documentation the founder reads later to
visualise the product screen-wise and role-wise.

The non-negotiables of a session:

1. **Ground it in the real code first.** Read the module before designing it; write down what
   exists today marked *(verified)* with file references. Half of what gets "designed" already
   exists and the other half is broken in a way nobody knew.
2. **Push, don't transcribe.** Offer ideas that weren't asked for, name what will be wrong with
   an idea before it's built, say when something is already built and merely unreachable, and
   flag every fence/law/principle an idea crosses.
3. **Write to all three layers** — `modules/<m>.md` (the thinking), `screens/<role>.md` (the
   visualization, block by block in order), and `decisions.md` / `open-questions.md`.
4. **Tag everything**: `D-nn` decided (founder) · `S-nn` suggestion (Claude, unaccepted) ·
   `Q-nn` open question. Numbers are global, never reused; rejected ideas are marked, never
   deleted.
5. **Close by naming the blockers** for the next session, ordered by what they unblock.

`docs/brainstorm/ux-principles.md` is the checklist every screen is designed against (lead with
a sentence not a number · name the people · every figure carries its denominator · not-captured
is never red · two actions not nine · one computation many renderings · …). Apply it.

Nothing in `docs/brainstorm/` outranks anything. A decision graduates into SPRD2 (or its own
plan doc) when it is ready to build.

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
- **V2-P11 (term-scoped planning) COMPLETE** — migration `f7c8d9e0f1a2` (head). Schools fix the
  year's portion in April but size each chapter when its term begins, which the planner could not
  express. `syllabus_units.term_id` (nullable; NULL = whole-year, so term-less schools are
  unchanged) files a chapter under a `Term`. **`syllabus_topics.est_periods` is now NULLABLE** —
  NULL means *not sized yet* and is never scheduled: `distribute` skips it, validator **V6
  `validate_unsized`** reports it, `approve` refuses to lock it, and `forecast` returns
  **`unplanned`** instead of a RAG colour. (The old `NOT NULL DEFAULT 1` made an unplanned year
  forecast **green**: unsized chapters looked like one-period chapters, so baseline == projection.)
  `plan_approvals` is an **append-only** log per (class-subject, term) — un-approve appends
  `action='revoke'`, never mutates (law 3) — and `plans.status` becomes a derived cache that gains
  **`partial`**. `draft`/`generate`/`approve`/**`unapprove`** take an optional `term_id` and touch
  only that term's `plan_entries`, inside that term's dates, against that term's capacity, so an
  approved Term 1 is never rewritten by a Term 2 re-draft (P2). Also fixed: `effective_periods`
  normalised by the working days *inside* the window, so a boundary-straddling week yielded a full
  week's periods (a Term 2 opening on a Thursday took 6 periods of topics into 3 days) — the
  denominator is now the week's working days, identical for any week wholly inside the window.
  Syllabus importer maps a `Term` column and reports names it can't resolve rather than inventing
  them. `test_term_planning.py`.
- **HS-1 (hostel sessions) COMPLETE** — migration `f8d9e0f1a2b3` (head, revises `a8b9c0d1e2f3`).
  The sessions module is now the **hostel-timetable unit**: `sessions` gains `kind`
  (study|homework|activity — picks the capture surface), `end_time`, `hostellers_only`; new tables
  `session_classes` (class-linked membership — the roster is **computed**: class students,
  optionally Hosteller-category only, ∪ explicit `session_students`, so new admissions appear with
  zero edits), `session_media` (photos/videos of a meeting stored as **R2 object keys**, URLs
  minted per read via presigned GET — private bucket; media attaches to the meeting, never a
  student, P5), `session_student_logs` (optional per-student study note, one row per
  meeting×student, **never mandatory** — P1v2). `SessionService`: admin creates + assigns the
  teacher (`owner_member_id`), deterministic teacher-clash check on create/update (§11: no
  solver), `homework_board` (computed read view over `homework_assignments` for the roster — no
  new capture), `set_logs` (blank note = clear), media presign→direct-PUT→confirm for big videos
  (300 MB cap) + pass-through upload ≤25 MB (also the no-R2 dev fallback; `storage.py` grew
  `url_for`/`presign_put`/`object_stat`/`delete_object`). Endpoints: PATCH `/sessions/{id}`,
  `/sessions/meetings/{id}/logs|homework|media|media/presign|media/confirm`, DELETE
  `/sessions/media/{id}`. Timeline sessions now carry `kind` + `log_note`. Seed adds an
  evening-prep study block (all classes, hostellers-only, with a log) + Saturday yoga.
  `test_hostel_sessions.py` (6). Frontend: **Plan → Hostel** tab (week grid of blocks, admin
  create/edit sheet with kind/days/times/teacher/classes/hostellers-only), session capture page
  is kind-aware (study = optional per-row notes; homework = tonight's-homework board; memories
  strip with photo/video upload on all), My Day gains a **This evening** section. R2 note: set
  `R2_*` in `api/.env` (leave `R2_PUBLIC_BASE_URL` empty to keep the bucket private) and add a
  browser CORS rule (PUT from the web origin) on the bucket for presigned uploads.
- **HS-2 (per-student session capture) COMPLETE** — migration `f9e0f1a2b3c4` (head).
  `session_media.student_id` (NULL = class memory; set = that student's own photo/video —
  explicit founder call, supersedes batch-only P5 for hostel sessions);
  `session_student_logs.section` (named sections per student like the class deep log; unique =
  meeting×student×section, PUT full-replace per student). New `GET/PUT
  /sessions/meetings/{id}/students/{sid}[/logs]` (SessionStudentCard: attendance + homework +
  logs + media in one round trip). Web: session page roster is a grouped/searchable
  **StudentTable** (`components/school/student-table.tsx`, boards-table language; homework tick
  starts EMPTY daily, saves per tap); row click → `/sessions/[id]/student/[studentId]` (homework
  detail + Mark done, sectioned study log editor, per-student memories); hub keeps class-wide
  memories only. Students directory gets the same toolbar (search · group-by class default ·
  class/category/status filters, grouped card tables). Timeline folds sectioned logs into one
  line. `test_hostel_sessions.py` still 6 green.
- **Teacher view + student growth (2026-07-11)** — migration `a8b9c0d1e2f3`. My Day is now
  a clean list of tappable period rows; every action moved to a **period page**
  (`/my-day/period/[classId]/[no]`, backed by the V2-P6 `GET /periods/card`): attendance
  (inline tap-cycle + all-present), **topic picked from the syllabus list** (grouped by chapter,
  ✓/◐ markers) + coverage + note, homework (class-wide or per-student), checks, "not held", and
  the **optional deep log**: `lesson_observations` — named sections ("Vocabulary") with concepts
  ("Reading"/"Writing") where the teacher flags ONLY deviating students
  (needs_work/excellent, exception-only per P1v2; save = full-replace per section, like
  attendance). `PUT/GET/DELETE /classroom/observations`. **Student growth report**
  (`GET /students/{id}/growth`, `services/growth.py`, page `/students/[id]` — directory row click
  opens it, pencil keeps the edit sheet): computed join, **chapter-level default with topic-level
  drill-down** — per subject: attendance, chapters (topics taught / **missed while absent**,
  expandable to per-topic taught-date + the student's presence), homework (incl. personal),
  check flags, observations, test scores; plus skill profile, latest band + history (staff-only,
  P4 intact) and derived **growth areas** phrases. Access: admin = all students, teacher = only
  students in classes they teach (`not_your_student` 403). `test_growth.py` (4).
- **SC-5 (exam-first scores + band categorization screens) COMPLETE** — migration
  `fb2c3d4e5f6a` (head). The Students→Scores tab is now exam-first: landing = class cards
  (teacher sees only taught classes via `/academics/classes?mine=true`; admin all) + a feed of
  previous exams (`GET /assessments/exams`, batched summaries: avg %, scored/roster, evidence
  page count, author). `assessment_cycles` gains `topic`/`total_marks`/`student_ids` (few-students
  subset; NULL = whole class)/`created_by_member_id` + widened types (chapter_test, class_test,
  slip_test, objective, band_test). `/students/scores/[classId]` = capture page with
  **Whole class | Few students** tabs (few = pick who sat it first); `ExamCapture` component:
  drop photos/PDF **before** any typing → cycle-less **draft capture** (`score_captures.cycle_id`
  now nullable, `parsed_meta` = AI-read header with deterministic subject match) prefills
  title/subject/total/topic + matched marks → review step → `POST /assessments/exams` creates the
  cycle + scores + files the capture as evidence in one transaction. Saved exams reopen at
  `/students/scores/exam/[cycleId]` (full-replace edit; org-wide/diagnostic cycles fall back to
  the score grid there). Bands: landing = class buttons + **three-column A/B/C table**, admin
  threshold config (`organizations.band_a_min/band_b_min`, GET/PUT `/assessments/bands/config`);
  `/students/bands/[classId]` records a `band_test` (admin-only) and `POST
  /assessments/bands/categorize` re-tiers the class from that cycle's results (append-only rows
  naming the source test). `test_exams.py` (5). Backend 205 passing-equivalent (suite +5), ruff
  clean; web tsc + eslint + build clean.
- **LU (Lucy, the agentic chat layer) COMPLETE** — migration `fc3d4e5f6a7b` (head). Founder
  decision 2026-07-12 moves a **staff-only chat surface IN** (supersedes the §11 "no chat UI"
  fence for Lucy specifically; parents still have nothing). New sidebar item **Lucy** (both
  roles): ChatGPT-style page → `/lucy` (pin board + composer + recent chats) and `/lucy/[id]`
  (desktop = widget canvas + chat rail, mobile = single column). Backend `services/lucy/`:
  **MCP-ready tool registry** (`registry.py` ToolSpec — name/JSON-schema/role/kind/confirm;
  transport-agnostic, a future MCP server maps it 1:1) with **29 read tools wrapping the existing
  services** (org/teacher scoping and the fee fence ride along; `AppError`s return to the model
  as tool data) + **6 write tools, all confirm-gated**: the agent files a `lucy_pending_actions`
  row (append-only, 15-min expiry) and the human taps Confirm in chat before the service write
  runs. Agent loop (`agent.py`) = `ai/client.py::chat_tools` (OpenRouter streaming tool-calls,
  `AI_MODEL_AGENT`, buffered fallback `LUCY_STREAM_TOKENS`) capped by `LUCY_MAX_ITERATIONS`/
  `LUCY_WALL_SECONDS`; **it never holds a DB session across model I/O** (`lucy_session` per
  phase — the Aiven 20-conn rule). **Data fidelity:** tool results are stored server-side per
  turn; the model renders them via the internal `render_widget(result_id, type, config)` tool and
  `widgets.py` materializes from the STORED result — the model picks the representation, it
  cannot type the numbers (an invented key errors back to the model). SSE endpoint
  `POST /lucy/conversations/{id}/messages` (events status·tool·text·widget·action·error·done,
  fetch-stream client in `web/src/lib/sse.ts`, 10/min SlowAPI). Chat history: `lucy_conversations`
  / `lucy_messages` / `lucy_widgets` — **member-private** (admins don't read teachers' chats);
  widget **pinning** puts it on the Lucy landing board, snapshot-first with live refresh
  (re-executes source tool, role re-checked). Widget catalog v1 (13 renderers + confirm card):
  table (search/group/sort) · stat_group · bar/line/donut (Recharts, one dynamic chunk,
  dataviz-validated palette) · rag_board · roster_grid · timeline · report_card · student_card ·
  alert_list · progress · escaped-markdown. Titles autogen off-thread via `chat_json`.
  `test_lucy.py` (10). AI-off: `/lucy/meta` gates the page, streams degrade politely.
- **V3-P0 (2026-07-20) COMPLETE: super-admin platform layer + mid-year adoption + partial
  plans** — migration head **`fe5f6a7b8c9d`** (applied). `test_platform.py` (3) +
  `test_midyear.py` (3) green; planner/dashboard/report/auth suites re-run green (2 tests in
  `test_term_planning.py` updated to the v3 contract: partial approve is allowed, forecast
  paces the planned portion). Founder redesign: **schools no longer self-onboard.** The dev (super-admin) creates each
  school, runs setup from the data the school hands over, then hands over credentials.
  - **Platform layer:** `users.is_super_admin` (granted only via seed/DB), `require_super_admin`
    (lifts the RLS GUC — platform reads cross orgs by design), `services/platform.py` +
    `/platform/orgs` (list w/ stats · create school+admin, temp password w/ forced change,
    operator auto-joins as admin · enter → session via switch-org). Session/Me carry
    `is_super_admin`; web `/platform` (org cards, New school sheet w/ copyable handover creds,
    Enter&set-up), super-admin lands there, "Schools" nav item, wizard tab now operator-only,
    login's register link removed, `ALLOW_PUBLIC_ORG_SIGNUP` config (set False in prod; default
    True keeps tests green). Seed: `super@trackbit.app / demo1234`. `test_platform.py` (3).
  - **Mid-year adoption:** `academic_years.tracking_start_date` (NULL = year start). Planner
    windows clamp to the floor (`_window`, drafting a pre-tracking term is refused with a clear
    message); forecast excludes pre-tracking terms' chapters from every number; exam-fit skips
    pre-tracking exams + clamps gaps; `_recompute_plan_status` exempts pre-tracking buckets.
    Rule: pre-adoption data = **no-data, never a warning**. Setup → Academic years gains
    "tracking from" (create + inline edit).
  - **Partial plans (chapter-level known, topic detail later):** forecast rates the **planned
    portion** with a real RAG (`planned_topics`, `unestimated_topics` = info) — `unplanned` now
    means NOTHING scheduled; new `current_term_unplanned` flag → dashboard alert only for a
    running term with no plan (unsized future chapters alert nothing). `approve` locks partial
    plans (refuses only an empty window); `set_topic_estimate` allows sizing a never-sized topic
    under a locked term; **`extend_plan`** (`POST /planner/plan/{cs}/extend`) appends newly sized
    chapters after the locked entries (P2: baseline never moves) — web PlanView gains
    "Schedule new chapters" + pre-tracking term handling. `test_midyear.py` (3).
- **RD-1 (reporting redesign, 2026-07-23)** — no migration; additive fields only. The dashboard
  now **leads with a written briefing**: `ai/report.py::report_summary` asks the model (via
  `chat_json`, `AI_MODEL_DRAFT`) for 2–3 sentences over the already-computed figures and falls
  back to `deterministic_summary` on no-key/timeout/bad-JSON, so the headline exists offline;
  it is written once at `generate` time into `daily_reports.highlights.summary`
  (+`summary_source`), and `_to_out` composes it deterministically for rows written before this
  existed. Every figure folds behind **More**. `DashboardService._attendance_pulse` adds a
  computed `attendance` block (14-day per-day roll-up + per-class today, three grouped queries,
  no per-class loop) so the day has a *shape*: present% area chart, RAG donut, per-class
  attendance and homework bars, fee gauge. `GrowthService._strengths` mirrors `_growth_areas`
  (high attendance · "excellent" observations · strong scores, capped at 6) so a report card is
  not only deficits. Frontend: **`components/charts/`** is now the one chart kit
  (`palette.ts` = the dataviz-validated series palette + reserved status colours, `school-charts.tsx`
  = Recharts marks, `index.tsx` = next/dynamic wrappers + `ChartCard`/`StatTile`/`MeterBar`), one
  lazy chunk shared by all three screens. `students/trends` → `components/school/class-analytics.tsx`
  (subject trajectories, class average with a first-test reference line, subject-profile radar,
  score distribution, support-tier donut, movers, full table) replaces the old `TrendsView`.
  `students/[id]` is a report card: identity band + attendance gauge, tiles,
  **ability radar** (diagnostic skill areas) beside subject performance, strengths | growth areas,
  score history, attendance by subject, then the chapter drill-down.
  `components/students/growth-analytics.tsx`. Bands stay staff-only (P4) throughout.
- **EN-1 (enquiries desk, 2026-07-23)** — migration **`b3c4d5e6f7a8`** (head). The operator's inbox
  for `demo_requests`: `demo_request_notes` is the **append-only** history on a lead (remark,
  status move, or both in one row; `author_user_id` SET NULL so history outlives the account),
  and `demo_requests.status` becomes the derived cache of the newest `status_to` — the
  `plans.status` / `plan_approvals` shape (law 3). Re-selecting the current status is not a move:
  the remark lands, `status_from/to` stay null. Platform-level like its parent — no `org_id`, no
  RLS policy, `require_super_admin` on every read and write. New endpoints `GET
  /marketing/demo-requests/{id}` + `POST /marketing/demo-requests/{id}/notes`; the list gains
  `note_count`/`last_activity_at` from one grouped query and stays **unfiltered** so the screen's
  status counts can't lie. Web: `/platform` is now a tabbed area (`layout.tsx` — Schools ·
  Enquiries) with `/platform/enquiries` → `components/school/enquiries-screen.tsx` (status chips
  with counts, search, lead rows, detail sheet with tel:/mailto:, status picker, remark box and
  the history timeline). `test_marketing.py` +3.
- **PC-1 (parent portal, 2026-07-23)** — migration **`c4d5e6f7a8b9`** (head). Guardians get a
  **read-only login** (founder decision; supersedes the "no parent login" fence — P4 intact).
  `guardians.user_id` (claimed at first OTP login), `otp_codes` (phone-keyed, hashed code,
  attempt-capped — the failed-attempt bump commits in its own session so lockout survives the
  request rollback), `organizations.parent_portal_enabled`. `parent_auth.py`: last-10-digit
  phone matching, OTP request/verify (5/hr throttle, 5-attempt lock), find-or-create user +
  link ALL guardian rows with that phone (siblings roll up), `role='parent'` session (no
  membership, no token_version — revocation is the live link check in `get_current_parent`);
  `/auth/login`+`/auth/refresh`+`/auth/me` fall back to parent sessions so the web token
  machinery is shared; optional username/email+password (`/parent/auth/credentials`).
  `otp_delivery.py`: WhatsApp auth-template first, MSG91 SMS fallback, console stub with no
  keys (`OTP_ECHO_IN_RESPONSE` echoes the code in dev). `parent_portal.py`: **curated
  projection** (allowlist, field-by-field — never a spread) over Timeline (today: DAILY
  attendance status present|partial|absent|not_marked|no_school, topics taught, homework,
  evening sessions) and Growth (report: coverage + missed-while-absent, scores, derived
  strengths/growth areas) — **no bands/skills/observations/check-flags**, asserted by
  `test_parent_portal.py` (5). Web: `/parent` area (own mobile-first shell, no staff nav) —
  OTP login, Today/Progress/Report/Profile tabs, sibling switcher; `OrgRole` gains `"parent"`,
  staff shell is `allow={["admin","teacher"]}`. Fees view = PC phase 2 (founder call).
- **SF-1 (staff attendance · timesheet · leave, 2026-07-29)** — migration **`c7d8e9f0a1b2`**
  (revises `d5e6f7a8b9c0`; **applied to DO prod 2026-07-29**). The three things the school could not record. Prerequisite for
  the admin-dashboard v3 build (`docs/trackbit-admin-dashboard-v3-plan.md`), which supersedes that
  plan's PR-1 (self check-in) and PR-4 (deriving teacher work from tasks).
  - **Staff attendance is admin-marked and exception-shaped** (P1v2), the classroom's own shape:
    `staff_attendance_days` (one row per org×date — the difference between "nobody was absent" and
    "nobody marked it") + `staff_absences` (absentees only; present is derived). **Present/absent
    only — no late tier for staff** (founder call). `mark` is a full replace, so the admin reopens
    a day and corrects it with no undo path. Approved leave pre-unticks that person and says why.
  - **Timesheet** (`timesheet_entries`, one row per member×date×period_no) = what a teacher did
    with a period they were **not** teaching. Teaching periods are never copied here — the grid
    owns them, and duplicating would fork the truth. `core/work_types.py` is the picker (8 buckets,
    **no CHECK constraint**: a school's own word is kept, never dropped). This is what makes "who
    is free right now" answerable from capture instead of inference.
  - **Leave** — `leave_requests` + append-only `leave_request_events` (law 3, the
    `plan_approvals`/`demo_request_notes` shape); `status` is a derived cache of the newest event.
    `organizations.leaves_per_year`/`leaves_per_month` (defaults 8/1) configured in Setup →
    Settings. Days count **working days** (year `working_weekdays` minus holidays), never raw span.
    **Over-policy applications are flagged, not blocked** — `warnings` rides on the request and the
    admin decides; a validator that refuses an emergency is one staff route around by phone.
  - `services/school_clock.py` — pure: `period_no` = 1-based index among `period_times` entries
    with `kind == 'period'`, so a lunch break shifts no period number. One function, tested.
  - 11 endpoints under `/staff` (attendance admin-only · timesheet `require_academic` with
    `_resolve_member` letting an admin read anyone · leave apply/cancel by member, decide by admin).
    Dashboard alert feed gains `type='staff'` rows (staff away today · leave waiting) that link to
    the screen instead of becoming a task. `test_staff.py` (12).
  - Web: admin **Staff** area (`/staff` attendance · `/staff/leave` approvals with the history
    timeline · `/staff/today` the period grid of who's teaching/working/free); teacher **My time**
    area (`/timesheet` week grid — classes locked, free cells tappable · `/timesheet/leave` balance
    + apply + own history). Nav gains Staff (admin) and My time (teacher).
- **HW-1 (per-student homework, 2026-07-29)** — migration **`d8e9f0a1b2c3`** (head, revises
  `c7d8e9f0a1b2`; **applied to DO prod 2026-07-29 — Aiven test DB still at `d5e6f7a8b9c0`,
  see the note under Database below**). Completion was a COUNT (`homework_checks.done_count`), which cannot name a
  student — so "who keeps not doing it", "which teacher never checks" and a parent's "did my child
  do yesterday's homework" were all unanswerable. Now:
  - `homework_results` = exception rows (`not_done` | `partial`), one per student who did NOT do
    it, keyed (assignment, student). Capture-by-exception (P1v2): every student's status is
    derivable (roster minus these = done) without the teacher touching 40 names for 3 facts.
  - **A `homework_checks` row means the teacher went through it; its ABSENCE means `not_checked`,
    which is never "everyone did it".** That distinction is the module — without it a teacher who
    checks nothing reads as a class with perfect completion. `not_checked` is counted separately,
    excluded from any completion figure, and never rendered as a student's miss (parent surfaces
    included). Same shape as `class_periods.attendance_marked_at` and `staff_attendance_days`.
  - `homework_checks` gains `checked_by_member_id` + **UNIQUE(assignment_id)** (previously 1:1 only
    by service convention — a double-submit could double-count a class in the dashboard totals).
    `done_count`/`total_count` are KEPT as **derived caches** recomputed on every check, so
    `DashboardService._homework_health` and the existing chart are untouched.
  - `ClassroomService.homework_sheet` (roster pre-loaded with the last verdicts) +
    `check_homework` (full replace, stamps checked_at/by). Per-student homework has a roster of
    one. `services/homework.py::HomeworkService` = the read side: school→class→subject roll-ups,
    **teacher checking discipline** (`unchecked_overdue` counts only past-deadline homework, so
    homework set an hour ago is not a failure), repeat non-doers with the responsible teacher,
    perfect-week and most-improved. Five queries for the whole overview, no per-class loop.
  - Reads updated end-to-end: timeline homework carries this student's status; growth gains
    done/not-done/not-checked per subject; the daily report says who missed it and how much is
    unchecked; the dashboard raises an unchecked-homework alert. **Parent portal** gains
    `yesterday` (the last homework day + its verdict) and `pending` (set, not finished) through
    the same allowlist projection. `/homework/overview` + `/homework/student/{id}` (teachers only
    their own students). `test_homework.py` (7). My Day's check row is now "Everyone did it ✓" +
    a tap-to-flag sheet.
- **DASH3 (admin operating board, 2026-07-29)** — migration **`e0f1a2b3c4d5`** (head, revises
  `d8e9f0a1b2c3`; **applied to DO prod**). `/dashboard` becomes a 7-tab route area — the briefing
  stays first and unchanged, and each tab answers one question the admin arrives with. The plan
  (`docs/trackbit-admin-dashboard-v3-plan.md`) is at **revision 2**: it was written before SF-1 and
  HW-1 shipped, so three of its seven prerequisites were already built (two of them *differently*)
  and its §11 "leave is out of scope" was obsolete. Rev 2 reconciles it with the code — read §0.1
  before touching this module.
  - **Only two new tables.** `period_substitutions` (PR-2) — who covers an absent teacher's period;
    the P2 shape again, **the substitution is the plan and `class_periods.teacher_member_id` stays
    the actual**. Unique on the LIVE rows only (partial index `WHERE cancelled_at IS NULL`), so a
    cancelled cover never blocks a re-cover. `followup_actions` (PR-5) — append-only (law 3), one
    row per action-rail press, which is what stops the same parent being reminded three times in a
    morning: each red row reads today's history for its subject in **one query for the whole list**
    and renders "already reminded". Rev 1's `staff_attendance` and `homework_results` are SF-1/HW-1
    and are NOT recreated.
  - **Read-side of cover:** `ClassroomService.my_day` unions today's substitutions (tagged
    `substituting`/`covering_for`), and `assert_can_take_class` takes `(on_date, period_no)` so a
    substitute can actually OPEN the period card — a period you can see but not open is worse than
    one you never saw. Notified via a new push-only `substitute` notif type (the migration widens
    `ck_notifications_notif_type_valid`, which a CHECK constraint otherwise rejects).
  - **PR-6 `PlannerService.forecast_org(m, year_id)`** — `DashboardService._rag_rows` looped
    `forecast` per class (~4 remote round-trips each, ~80 for a 20-class school, for ONE card).
    Now one batched pass; the existing overview got faster as a side effect.
  - `services/insights/`: `attendance.py` (14-day pulse reused from `DashboardService.attendance_pulse`
    so the two can't disagree · **period capture heatmap** class×period with four states —
    `free`/`pending`/`marked`/`not_held`, the one thing that separates "attendance is bad" from
    "attendance was never taken" · absence streaks: absent in EVERY marked period of consecutive
    school days, days the class marked nothing are **skipped not counted present** · blast radius
    with ranked substitutes) · `syllabus.py` (scope school|class|subject|teacher × checkpoint
    year|term|exam; **teacher is a re-pivot of class-subject rows, not a child of subject**;
    `unplanned`/`unallocated`/`unestimated` stay words, never a colour; ranks guarded at ≥3
    class-subjects and ≥10 logged periods, framed *needs support / ahead of plan*) ·
    `workload.py` (live board off `school_clock`, degrades to before/after/break/holiday/unset;
    free-teacher work from `timesheet_entries` — **capture, not the plan's task-category
    inference**; leave queue with SF-1's policy warnings; org-wide teacher week vs a mean computed
    over people who teach at all) · `homework.py` (thin — delegates to `HomeworkService`, adds only
    the daily series) · `tasks.py` (task health + daily duties denominated by periods **actually
    due**, cover moves the duty to the substitute) · `exams.py` (roll-ups; participation beside
    every average; bucketing done in Postgres) · `actions.py` (the rail + the Follow-ups board) ·
    `cards.py` (overview summary cards).
  - 13 endpoints under `/insights` (all `require_admin`), `services/substitution.py`,
    `models/insights.py`, `schemas/insights.py`. 8 Lucy read tools (`tools_insights.py`, registry
    now 43). Two daily-report ambiguity rules the capture finally allows: *staff away with periods
    uncovered* and *homework not-done streaks by name*. Seed gains the **Follow-ups** board
    (`task_scope='assigned'` — a private per-teacher board would collide with law 5).
  - Web: `dashboard/layout.tsx` + 6 tab pages, `components/insights/*`, `lib/insights-{api,types}.ts`.
    All charts through `components/charts` — no second charting path.
  - `test_insights.py` (11). **Fixed three pre-existing bugs the suite had never been able to
    catch** (see the Database note — the test DB was unmigratable, so these suites had never run):
    `leave.py` returned a stale event list after approve/cancel (`selectinload`ed collection not
    expired), `leave.py::_working_days` passed ORM rows to the pure `expand_blocked_dates`
    (**every leave application 500s in any school with a calendar event**), and
    `test_timeline.py` still asserted HW-1's homework rows were bare strings.
- **DASH3-OV (overview redesign, 2026-07-29)** — no migration, no new table. The overview was six
  one-number tiles over a five-chart grid: a tile could say "78%" but not *what* or *who*, so the
  admin opened a tab every morning to find out, and the charts repeated what the tabs already drew.
  It is now **one block per module** — a plain-sentence headline, the 2–3 figures it rests on
  (sparkline inside a metric, never a second figure), and **named** rows under them ("Anil away —
  Sick · 9 of 9 periods uncovered") — plus a derived **action rail** of what is waiting, each item
  linking to the screen that clears it. `services/insights/cards.py` → **`overview.py`**
  (`OverviewService`, `/insights/cards` → **`GET /insights/overview`**); `ModuleCard(s)` replaced by
  `OverviewSection`/`OverviewMetric`/`OverviewNote`/`QuickAction`/`OverviewBoard`. Every figure is
  still taken from a roll-up a module already computes, so the summary can never disagree with the
  tab it links to; the module boards are read once per load (the pieces of the attendance board
  directly, so the streak walk is not run twice). Rules kept: not-captured never renders red or as
  a zero, `unplanned`/`unestimated` stay neutral **states**, an average carries no invented grading
  threshold, and a "weakest subject" needs two subjects (else it shows the latest exam). Fees keeps
  its own block (client-side, off `DashboardService` — teachers never receive fee figures at all).
  Alerts that the rail already carries are dropped from the feed, so the division is **rail = go do
  it, alerts = file it as a task**. Web: `components/insights/overview.tsx` (`ActionRail`,
  `SectionCard`, `CustomSection`, `MetricCell`) replaces `module-card.tsx`; the `ShapeGrid`/
  `PulseRow` chart grid is gone — those charts live on the tabs that own them. `test_insights.py`
  (13, +2).
- **V1-4 (staff, leave, cover & time, 2026-08-02)** — migration **`b4c5d6e7f8a9`** (head).
  `D-04` reverses SF-1's "present/absent only, no late tier": `staff_absences` widens in place
  (`S-18` — no second table) to `status` **absent | half_day | late** + `portion` **am | pm**, and
  `leave_requests.days` becomes **numeric(4,1)** so a half-day is 0.5 rather than a flag the
  arithmetic must remember. `staff_attendance.present_value` is THE one place a marked day becomes
  a number of days present (late = 1.0 — a flag to be seen, never a deduction, `S-19`).
  - **`school_clock.periods_before_lunch`** is now the one place the school day is cut in half —
    `twice_daily` attendance (V1-3) and a half-day's AM/PM (`S-31`) share it, so a school on
    twice_daily can never read two different middays. `half_day_periods(times, portion)` is what
    tells the cover board which periods a half-day actually costs.
  - **`calendar.org_working_days(db, org_id, a, b)`** — the one org-level working-days read (V1-0
    §5), returning the DATES so the month summary (which must name the days nobody marked) and the
    leave arithmetic (which needs a count) share one definition. `LeaveService._working_days` now
    delegates to it.
  - **`D-27`/`S-80`/`S-81`** — approving a leave returns `cover_dates` (working days from today
    on), the decision sheet hands the admin one CoverSheet per day, and `LeavePulse.upcoming`
    (four batched queries over a 14-day horizon) puts *"Tue 04 Aug: Ramesh away, 6 periods to
    cover"* on the action rail the moment it is approved. `busy_reason` already carried the
    approved-leave clause (`S-82`, V1-0) and now narrows a half-day to its own half.
  - **`D-29`/`S-79`** — the cover picker says what the class **gains** (`_next_topics`: the first
    planned topic with no full-coverage log, two queries for the whole sheet; a candidate who
    teaches the subject AND has a topic to move is tier 0) and what the substitute **gives up**
    (`S-74`'s recorded work, already there, plus `_behind_notes` off the batched `forecast_org` —
    a warning on a still-assignable row, never a block).
  - **`D-78`/`S-34`** — `services/staff_month.py` + `GET /staff/month`: days worked out of the
    month's working days, leave used, leave left. **No money on it and no path from it to one**
    (`D-25`). `days_not_marked` is its own count in its own word and never an absence — today a
    display rule, in v2 the difference between a clerical gap and an unpaid day.
    `LeaveService.prime_balances` batches what would have been two round-trips per member.
  - **`D-18`/`S-64`** — `/timesheet` gains **Day · Week · Month**: month = one cell per DAY with
    holidays and leave read from the calendar (never inferred from "no entries"), day = the
    vertical timeline including breaks. **`S-75`** pre-selects her usual category in the picker
    and **writes nothing**; **`S-70`** gives the counters back to her ("20 taught · 5 recorded ·
    3 evenings"); **`S-68`** unions hostel sessions in as `evening_sessions`, **beside** the
    periods and never inside the load mean.
  - **`D-21`/`S-66`** — the slack profile: teaching/working/free per (weekday, period) over people
    who teach at all, with the best slot as a sentence. **`S-76`** deleted the "free periods
    unlogged" tile rather than fixing it (under `D-23` an unfilled period IS free, and it was at
    its reddest at 8:30am).
  - Also fixed, both pre-existing and both only reproducible on a Sunday: `CallBoard` computed its
    headline and left-after-lunch lists for the raw calendar today, so on any closed day the
    board read as *"nobody was absent"* rather than *"the school was shut"* — it now anchors on
    `_last_school_day`; and `TimesheetService.week` dropped every non-working weekday, so a period
    genuinely worked on a sports Sunday or an exam Saturday could not be seen OR recorded (module
    §4.7) — a non-working day now appears if anything is on it. Seed: each class's subject
    rotation is offset, one teacher was being scheduled into three rooms at once.
  - `test_staff_v1_4.py` (11). Web: `/staff/month` + `/timesheet/month` (one
    `components/staff/month-summary.tsx`), the four-state staff roster, half-day leave apply,
    Arrange-cover from an approval, the slack chart, and `/staff/today` finally naming who is
    covering **for whom**.

- **`test_doc/new_org/`** — the **setup-pack generator** (`generate.py`) for the roster, staff and
  syllabus importers. It invents a **different school on every run** (name, grades, subjects,
  weekly period split, teachers, students, chapters) while holding the four invariants that keep
  the pack valid: periods sum exactly to weekly capacity · every class-subject has one teacher and
  nobody is over-loaded · every topic is sized · each syllabus fits the year. So imports land 100%
  and the wizard can approve+lock every plan. `--seed N` reproduces a run; `--messy` injects rows
  built to fail (unresolvable class-subject, duplicate admission no, missing name, unsized topic)
  to exercise the `errors`/`skipped`/`unresolved` surfaces. The `.xlsx` pack and the per-run
  `SETUP.md` walkthrough are **generated, not committed** — run the generator. See
  `test_doc/new_org/README.md`.

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

### Database — LOCAL Postgres for dev (no Docker)

**Docker does not work on this machine. Never use it.** There is no Postgres container, and
`api/docker-compose.yml` is dead — ignore it. The Dockerfiles exist only for Dokploy to build
remotely; they are never built or run here.

**`api/.env` is switchable between LOCAL and PROD, and it says which mode it is in** — the active
mode is marked by a `# ─── ACTIVE: …` banner, and the inactive URLs are parked next to it as
`# LOCAL_*_BACKUP=` / `# PROD_*_BACKUP=` comments. Those comments are the only copy of the prod
credentials outside Dokploy: **never delete them**, never commit `.env`, never paste it into
`.env.example` or a commit message.

| var | local mode | prod mode | why |
|---|---|---|---|
| `DATABASE_URL` | `trackbit_school_app` (**NOBYPASSRLS**) @ `localhost/trackbit_school` | `doadmin` @ DigitalOcean | the app |
| `ADMIN_DATABASE_URL` | `postgres` @ localhost | `doadmin` @ DigitalOcean | **Alembic only** |
| `TEST_DATABASE_URL` | `trackbit_school_app` @ **`localhost/trackbit_school_test`** | *(unchanged — stays local)* | pytest hard-deletes orgs |

🚨 **`TEST_DATABASE_URL` stays on the local test database in BOTH modes.** The suite creates and
hard-deletes organizations; pointing it at prod would delete real orgs. `conftest.py` blocks the
obvious case (test URL == app URL) but it cannot know that some *other* remote URL is precious —
that guard is not a substitute for never editing this line.

Law 2 note: locally the app runs as a NOBYPASSRLS role, so RLS is genuinely enforced and a
cross-org leak fails a test. In prod mode the app runs as `doadmin`, which **bypasses RLS** — so
prefer local for anything security-related.

⚠️ **Never point `TEST_DATABASE_URL` at a superuser.** A superuser bypasses RLS entirely — even
`FORCE ROW LEVEL SECURITY` — so `test_rls.py` fails for reasons that have nothing to do with the
code. The restricted role needs `GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public`
plus matching `ALTER DEFAULT PRIVILEGES`, so tables from future migrations work without re-granting.

```bash
# from api/ — .env is read automatically, don't export DATABASE_URL over it
uv run alembic upgrade head
uv run alembic current
uv run python -m scripts.seed         # demo org: kc@demo.trackbit.app / demo1234

# Migrate a DIFFERENT database (e.g. the test one) without touching .env:
ALEMBIC_DATABASE_URL="postgresql+psycopg2://postgres:PASSWORD@localhost:5432/trackbit_school_test" \
  uv run alembic upgrade head
```

The Aiven database is retired for this purpose: its `trackbit_school_app` does not own
`organizations`, so `alembic upgrade` failed there with `must be owner of table organizations` and
**the suite had never actually run** — which is how three real bugs reached main (see DASH3).
Treat "the tests pass" as meaningless until you have seen them execute.

✅ **`conftest.py` honours `TEST_DATABASE_URL`** and refuses to start if it resolves to the same
host+database as `DATABASE_URL` (escape hatch: `ALLOW_TESTS_ON_DATABASE_URL=1`) — which is why the
two are separate *databases*, not just separate roles. Both engines, including the privileged
cleanup engine that reads `ADMIN_DATABASE_URL`, are redirected at the test database.

Worktrees have no `.env` (gitignored, not copied). Copy it in before running Alembic or pytest
there; otherwise settings fall back to `localhost:5434` and everything DB-backed fails with
"connection refused".

Current state: local dev DB and **DO prod are both at head `e0f1a2b3c4d5`** (SF-1 + HW-1 + DASH3,
applied 2026-07-29); 55 tables carry an `org_isolation` policy. Full suite **375 passing in
~4.5 min**.

⚠️ **In PRODUCTION `DATABASE_URL` still points at `doadmin`**, not a restricted app role — so
`rolbypassrls = true` and every RLS policy is inert there. Locally the app role is correct, so law
2 is real in dev and a cross-org leak would now fail a test before it could ship.
`scripts/provision_app_role.py` creates the restricted role on a managed cluster; swapping prod
onto it is the outstanding piece.

### Deployment — Dokploy

Dokploy builds `api/Dockerfile` and `web/Dockerfile` and injects config as environment
variables; nothing is baked into an image (`.env` is in both `.dockerignore` files).

`api/docker-entrypoint.sh` runs migrations, then execs gunicorn. **It forces one worker
whenever `ENABLE_SCHEDULER` is on**, because APScheduler starts inside each gunicorn worker —
two workers would send every absent student's guardian two WhatsApp messages. Run exactly one
scheduler instance; scale the rest with `ENABLE_SCHEDULER` unset and `WEB_CONCURRENCY=2+`.
Health probe is `GET /health` (app root, *not* under `/api/v1`).

`web/docker-entrypoint.sh` rewrites a build-time sentinel with the real
`NEXT_PUBLIC_API_BASE_URL` at container start, so the frontend image is repointable without a
rebuild.

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
*(One narrow exception, founder decision `D-83` 2026-08-01: a teacher **assigned a fee follow-up
task** sees that one student's fee detail — history, instalment, pending amount, conversation log —
**inside that task only**. Never a fees nav item, never a class list or collection figure, never a
fee field on any academic surface or Lucy tool.)*
**Parents (PC-1, founder decision 2026-07-23):** guardians get a **read-only portal login** —
NOT a membership. A `guardians.user_id` link + a `role='parent'` token (no token_version;
revocation = the live guardian-link check). Phone-OTP login (`/parent/auth/*`), optional
username/email+password later. Everything a parent sees goes through the **curated projection**
in `services/parent_portal.py` (allowlist, never a spread): attendance/topics/homework/coverage/
scores/derived phrases — never bands, skills, raw observations, or check flags (P4 tests in
`test_parent_portal.py`). Staff guards reject parent tokens and vice versa.

## AI services & stubs

All AI lives in `app/services/ai/`, routed through **OpenRouter** (one OpenAI-compatible endpoint,
any model, one key) via `ai/client.py::chat_json` — the only function here that touches the network.
It is **env-gated**: with `OPENROUTER_API_KEY` unset every call short-circuits and the caller's
deterministic heuristic runs, so all flows are testable offline. Same pattern as the seed's
integrations (email/R2/billing/push stub when keys blank). AI is invisible plumbing
(plan drafts, celebration drafts, syllabus split, xlsx/photo parsing), and **every AI output lands in
a human-confirm surface before persisting** (editable drafts, verify grids). The one chat surface is
**Lucy** (staff-only, founder decision 2026-07-12): `ai/client.py::chat_tools` streams tool-calling
turns for it, widget numbers come only from server-stored tool results, and its write tools land in
the pending-action confirm card — so the doctrine holds there too. Model ids come from env
as OpenRouter slugs (`AI_MODEL_DRAFT=anthropic/claude-opus-4.8`,
`AI_MODEL_PARSE=anthropic/claude-sonnet-5`, `AI_MODEL_AGENT=anthropic/claude-sonnet-4.5` — Lucy's
tool-calling loop); browse slugs at openrouter.ai/models.

Two rules make it safe in the setup wizard's critical path:

- **`chat_json` fails soft, never up.** Timeout, 429, 5xx, prose-instead-of-JSON → returns `None`,
  the heuristic runs, the admin never sees a stack trace. A non-retryable 4xx (bad key, bad slug)
  breaks out immediately rather than making them wait through a retry.
- **Deterministic validators decide; the model only proposes and phrases.** `ingest.py` asks the
  model to map only the columns the keyword heuristic *couldn't* place — never overriding an exact
  header match — then filters the reply against the real column list, so a hallucinated column can't
  reach an importer. AI proposals are flagged `low_confidence` for the human's glance.

## Fences — v2 (SPRD2 §11, binding; supersedes arch §8)

**Moved IN by founder decision (July 2026):** **staff attendance · leave · teacher timesheet
(SF-1, 2026-07-29)** — operational only: who covers period 4, not payroll or HR ·
**period substitutions + the admin operating board (DASH3)** ·
per-period attendance (capture-by-exception only) ·
timetable (import-first + AI-assisted draft with **deterministic** validators — still no guaranteed
solver) · daily report generation · per-student homework · **Lucy, a staff-only agentic chat
surface (2026-07-12)** — tools wrap existing services only, widget data is server-materialized,
writes are human-confirmed pending actions; the registry is the seed of a future MCP server ·
**parent portal login (PC-1, 2026-07-23)** — read-only, phone-OTP, curated projection only
(see Roles above); fees view is planned as PC-phase-2.

**Still OUT:** payroll/HR/library/transport/inventory/visitor/social modules · report-card
designer · test authoring/conducting · **any parent/guardian-facing chat or AI surface** ·
parent WRITES of any kind (the portal is read-only; leave requests/messages are a future
decision) · **mandatory per-student capture** (exception-only, always — P1v2) · per-student
evidence photos (batch only — **two decided exceptions**: hostel session media (HS-2) and **exam
script photos, `D-82` 2026-08-01**, where a photo per student's marked paper *is* the capture
mechanism). LMS + teacher training = Playground's lane.

## Build order

**Current work (2026-08-01 →): the v1 release plan at `docs/v1/IMPLEMENTATION-PLAN.md`** —
14 packets V1-0…V1-13, built from the brainstorm sessions (`docs/brainstorm/`); its scope
decisions are `D-78`–`D-88` in `docs/brainstorm/decisions.md` (session 10). V1-0 (the
one-computation foundation + defect sweep) comes first and everything depends on it.

For historical packets: work **packet-by-packet** per **SPRD2 §10**; do not mark a packet done
until its **Done-when** criteria pass. Sequence: V2-P0-B (IA reshell) → V2-P1 (timetable) → V2-P2 (attendance + My Day v2)
→ V2-P3 (recommendations/checks) → V2-P4 (daily report + timeline + cron wiring) → V2-P5 (wizard +
plan generation). After every packet the v1 flows (quick log, sessions, fees, tasks) must still
pass their tests. The core loop v2: **wizard compiles the year → teachers confirm each period by
exception → the system joins it into per-student truth → the 8 AM report tells the admin what
needs attention → gaps become tasks.**
