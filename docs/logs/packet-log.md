# Packet log — the build history

Every packet shipped, in order, with what it changed and **why**. This was the
`## Build status` section of `CLAUDE.md` until 2026-08-07, when CLAUDE.md was
compressed; it is moved here verbatim so nothing is lost.

**Read this when** you need the reasoning behind a design that looks odd — most
of it records a defect that was found the hard way, and the "obvious fix" is
usually the bug being described. **Do not read it front to back.** `Ctrl-F` the
module you are touching.

> ⚠️ **This file is history, not state.** Figures inside it (test counts,
> "prod owes N migrations", "current work") were true on the day they were
> written and are not maintained. For live state:
> - schema revision → `uv run alembic current`
> - test count → `uv run pytest -q`
> - what is being built now → `docs/v1/PROGRESS.md`
>
> A claim in here is evidence about a decision, never evidence about today.

Tags used throughout: `D-nn` decided (founder) · `S-nn` suggestion (Claude) ·
`Q-nn` open question — all defined in `docs/brainstorm/decisions.md`.

---

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

Demo logins (all `demo1234`, all `@demo.trackbit.app` unless noted):
- **admin** `kc@` · `priya@`
- **teacher** `ramesh@` (6-A Maths/Science, 6-A class teacher — the richest teacher walk) ·
  `anil@` (6-A English/Social/Hindi) · `sunita@`/`farhan@` (6-B) · `meera@`/`kavya@` (7-A)
- **super-admin** `super@trackbit.app` → lands on `/platform`
- **parent** — school code `DEMO123`, then class → section → child → date of birth
- **mid-year school** (`scripts/seed_midyear.py`, school code `MIDYR26`):
  `head@midyear.trackbit.app` (admin) · `asha@midyear.trackbit.app` (teacher, 8-A)

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
- **V1-5 (homework: the verdict model, 2026-08-02)** — migration **`c5d6e7f8a9b0`** (widens
  `homework_results.status` to `late`/`carried`/`waived`) — **on dev + test; prod is at
  `b4c5d6e7f8a9` and still needs it.**
  - **`core/homework_verdict.py` is THE vocabulary and arithmetic** — import it, never re-decide
    what `late`/`carried`/`partial` is worth. `late` counts as **done** and is reported *beside*
    completion (`S-99`); `carried` (absent when it was set) and `waived` leave the denominator
    entirely (`D-34`/`S-98`); `not_checked` is the **teacher's** gap and may never render as a
    child's miss on any surface, parent-facing included. It also owns `miss_streak`, so one number
    appears beside a name everywhere.
  - `GET /homework/queue` (backlog + `to_check`) · `GET /homework/load` (`D-37`) ·
    `GET /homework/student/{id}` · the check sheet carries `absent_when_set`, `carried_pending`
    and `miss_streak`. `homework_gap_days` (org setting) drives the delayed-teacher signal —
    never hardcode it.
  - Frontend: **`/homework`** is `D-36`'s three levels and My Day keeps only `S-100`'s counted
    button (the yesterday-homework block is **deleted on purpose** — checking is a desk activity).
    `components/school/homework-check-sheet.tsx` (five-verdict cycle, `S-85` absentee badge shown
    but **never preselected**, `S-97` carried, `S-89` streak) and
    `components/school/student-homework-history.tsx` are each mounted **twice** — the second is the
    teacher's by-student view *and* the admin's `D-31` drill-down. `/dashboard/homework` gains
    `delayed_teachers` + `rough_classes` as named rows. `test_homework_v1_5.py` (11).
- **V1-6 (syllabus, planning & the mid-year proof, 2026-08-02)** — **no migration.** `S-51`: the
  phrase *"syllabus covered"* was computed in **five** places with no two alike — the admin board
  (planned denominator, partial=0.5), the growth report (whole syllabus, partial=0), the class
  overview (whole syllabus, full logs only), and **two `.reduce()` calls in React** (parent
  progress, plan→classes). A parent and a principal could read different percentages for the same
  subject on the same day, and no test could have caught the browser ones.
  - **`core/coverage.py` is now the whole vocabulary**, not just `PARTIAL_WEIGHT`: `taught_weight` ·
    `better_coverage` (best log wins per topic — a topic taught across two periods is taught
    *once*) · `coverage_pct` · `CoverageFigure` (carries its denominator, so no screen can quote a
    bare percentage) · the three named bases **`SYLLABUS` / `PLANNED` / `PLANNED_TO_DATE`** ·
    `rated_status` (`S-42`) · `attribute_cause` (`S-41`). **Import it — never compute coverage
    again**, in Python or in the browser.
  - **`services/coverage.py::CoverageReader`** — the batched read: **3 queries for any number of
    class-subjects**, pre-tracking terms excluded from numerator *and* denominator (plan §5,
    pinned by `test_midyear.py`). `snapshot()` also hands back the per-topic detail, so `S-40`'s
    weekly series costs no extra query.
  - **`Q-16`/`S-54`**: the parent's denominator is the **whole syllabus** — the only one that
    cannot fall when the school sizes next term's chapters. The admin sees both, side by side.
  - **`S-42`**: `ForecastOut.logged_periods` rides along with the pace, and every *screen* runs the
    pair through `rated_status` → **`unknown`**. The forecast still returns green/amber/red (its
    arithmetic is plan-against-calendar and is valid with zero logs); `unknown` is a **rendering**
    decision, applied on the board *and* the overview so the summary and the tab agree.
  - **`S-41`** every behind row says why — `not_logged` · `periods_lost` · `never_sized` ·
    `slower`, in that test order, because "nobody recorded anything" invalidates the rest and
    "periods were lost" is nobody's fault while "slower" is a conversation about a person.
  - **`S-45`** `rank_reason` replaces the unexplainable `on_track_share×60 + coverage×40` ·
    **`S-50`** the exam leads the page, which needed the new batched **`PlannerService.exam_fit_org`**
    (the per-class form ran a units query *per class-subject*) · **`S-40`** coverage-over-time vs
    the baseline · **`S-43`** section compare (6-A vs 6-B).
  - **`D-16`/`S-60`** `catchup_requested` — a **meeting request, not a directive**: a task on the
    subject teacher carrying the gap and the cause, which the board reads back and which clears on
    the recorded **outcome**, never on the press. `task_instances.subject_type` accepts
    `class_subject` (free-text column, no migration) and resolves to "6-B Maths".
  - **`S-46`/`D-15`** `/planner/my-subjects` (scoped on `teacher_member_id` — blocked, not
    filtered) + `/planner/class-syllabus/{id}` (class teacher or admin, 403 `not_your_class`).
    Web: `/plan/my-subjects` (a teacher's Plan nav points here), `components/school/subject-pace-list.tsx`
    shared with My Class's new syllabus block. `test_syllabus_v1_6.py` (12).
- **V1-7 (events, dates & birthdays, 2026-08-02)** — migration **`d6e7f8a9b0c1`** (head)
  **on dev + test; prod still needs it and `c5d6e7f8a9b0`.** `calendar_events` had had a write
  side for a year and **no reader**: its only consumer was the function that *subtracts* it from
  the teaching total, so the most-asked question about a calendar — what is on this week — had no
  surface anywhere.
  - **`services/whats_on.py`** is the read side: **one computation, three sources** (`S-121`) —
    student birthdays and staff birthdays **DERIVED** from `date_of_birth` (V1-2), never stored as
    events, plus the school's own `calendar_events`. `GET /events/whats-on` (`require_academic`)
    serves the admin card and the teacher strip from one endpoint; `components/school/whats-on.tsx`
    is built once and mounted twice. `S-128` rolls a vacation birthday to the nearest working day
    **and says so**; `S-133` renders the day, never the age; `S-124` carries the denominator
    ("birthdays known for 13 of 15").
  - **`calendar.day_lock()` / `day_locks()` is THE "is this period still expected?"** (`S-145`) —
    now read by My Day, `jobs.run_teacher_reminder`, the capture heatmap and the daily report.
    Before it, a declared holiday showed every teacher eight unlogged period rows, pushed her at
    16:00, and read as the year's worst capture day. ⚠️ `Q-65`: it removes a period from what is
    **asked for**, never from what was **recorded** — a school that shut at 11am did teach
    period 1, and the period card still opens on a locked period.
  - **The approval sheet is the module** (`D-57`/`D-58`/`D-79`): the date is **editable**,
    pre-filled from the suggestion, so *"Christmas — closed, 25 Dec"* and *"Christmas celebration
    — open, 22 Dec"* are two approvals from one row. Three lock levels map onto the existing
    `affects_teaching` + `blocks_periods`, which `effective_periods` has prorated since V2-P7 —
    no new engine. **`S-143`** prices it first: `PlannerService.forecast_org` gained
    `extra_events`, so `POST /events/cost` runs the identical computation against the calendar the
    school *would* have and names the RAG moves.
  - **`observances` is PLATFORM data** (`D-60`/`S-149`) — no `org_id`, no RLS, `require_super_admin`
    on every write, the `demo_requests`/EN-1 shape; scoped per school by **`state` + `board`**
    (`D-61`), both already collected at setup. `source` is **NOT NULL** (`S-150`).
    `event_decisions` is the school's **append-only** record (`S-148`), and a dismissal keys on the
    stable `key` so next year's entry does not return. `/platform/catalogue` is the curation tab
    (3rd, beside Schools · Enquiries) with an annual paste-import that upserts on (key, date).
  - 🔴 **The catalogue ships EMPTY and that is correct.** `Q-63` (what the real sources are, and
    the annual cycle) is unanswered; filling the table by asking a model when Diwali is would be
    `S-123`'s rejected row wearing a table for a hat. Steps 1–6 of the module run on the school's
    own dates and birthdays alone.
  - `S-147` `class_periods.not_held_event_id` — the teacher's "not held, because" points at the
    approved event, so *"what did Diwali cost us in periods?"* is a query. `S-146`: **if the admin
    locked it, the teacher is never asked** (both would subtract the day twice). `D-56` staff DOB
    is self-entered on Account via `PATCH /auth/me` (`set_date_of_birth` guards it). `Q-64`
    answered (a) — the teacher's strip is never provisional. `Q-60` answered (a)+(b) — the feed
    lives on Plan → Year, the card is an agenda list, **no third month view**.
    `test_events_v1_7.py` (10).
- **V1-8 (exams, scores & reports, 2026-08-02)** — migration **`e7f8a9b0c1d2`** (head, revises
  `d6e7f8a9b0c1`) **on dev + test; prod needs `c5d6e7f8a9b0` → `d6e7f8a9b0c1` → this.** The module
  recorded exams and did not **organise** them: a 5-mark slip test and an 80-mark term exam were
  added into one fraction on three screens, a school running **CET** could not record one, and the
  feed's *"· verified"* badge could not light up for any exam saved through SC-5.
  - **`core/exams.py` is now THE exam vocabulary** — import it, never re-decide it. `minor` |
    `major` and **never pooled** (`S-114`/`Q-50`): trajectory is drawn from minor, standing read
    from major, and `ScaleTally` **has no method that returns a blended number**, so a caller who
    wants one must write the addition where a reviewer can see it. `ScoreFigure` cannot render
    without its denominator (`S-118`) — *"61% across 5 of the 9 tests"* — plus
    `clean_question_marks` and `sum_mismatch` (`S-116`'s surviving half: **the marks don't add
    up**, arithmetic about the teacher's paper, never a claim about a child).
  - **`services/exam_marks.py::load_class_marks` is the one batched marks read** (4 queries for a
    whole class): the growth report, the student report card and the class card all go through it,
    which is what lets a test assert two screens agree.
  - **`D-55`/`S-135` `exam_types`** — the school's own word (*CET*, *pre-board*), a table not free
    text because it is the grouping key for a year of trend lines. It carries the `scale`, so the
    teacher picks **one** thing. `assessment_cycles.type` stays the **system kind code branches
    on** and is never rendered; if an analytic groups by `type`, the two have diverged. Retire,
    never delete. Seeded on first read (write-on-GET, the `RecommendationsService.ensure` shape).
  - **`D-53`/`Q-62` verify & lock** — locking stamps `verified_by` on every score (the meaning it
    never had) and makes the exam the record: `ExamService.save` **and**
    `AssessmentService.save_scores` both refuse a locked cycle, so the full delete-and-reinsert
    can no longer replace July's confirmed mark in November. Unlock is **admin-only, reasoned and
    appended** (`exam_lock_events`; `locked_at`/`locked_by` are its derived cache) — the
    `plan_approvals` shape a fifth time.
  - **`D-80`/`D-82` per-student script capture** — `score_captures.mode='scripts'`, one photo per
    marked paper; `ai/scores.py::extract_script` transcribes identity, total **and the per-question
    marks already written on the page** (stored as `assessment_scores.question_marks`: no new
    table, no new capture surface, `Q-51`'s answer-judging stays out). `score_match.py` still
    decides identity. An **unreadable page is kept as its own row** and mapped by hand — losing 39
    good pages to a blurred 40th was the old behaviour. `S-119` the page↔student link is written
    from the **confirmed** grid, never at parse time, and puts the paper one tap from the mark on
    the exam page, the report card and growth.
  - **`D-80` two tabs** — Score (`ExamDetail`) and **Report** (`services/exam_report.py`): a
    sentence, the distribution, **named rows against a stated criterion** (±15 points from the
    class average — never a rank), most-often-lost questions where a photo gave them, and coverage
    from `services/coverage.py`. Question analysis absent is **a word** ("needs a photo of the
    marked paper"), never a zero.
  - **`D-81` two report levels** (`services/report_card.py`) — the card (numbers only, per student
    and, batched, per class) and the analysis (per topic, skill abilities, per-subject narrative
    via `ai/exam_analysis.py`, deterministic fallback so it is never empty). Neither carries a band
    (P4). `S-115` `exam_event_id` links the recorded exam to its planned block.
  - **`D-54`/A-4 the training pair** (`services/exam_corpus.py`) — `parsed_rows` vs `locked_rows`
    plus the **diff with reason buckets**, written once **at lock** and only when
    `organizations.training_data_opt_in` is on (default off, asked for in Settings). **No export
    path in v1**; de-identification must exist before the first export, not the first row.
  - Web: the exam page is two tabs + verify/lock + lock history; `ExamCapture` is scripts-first
    with hand-mapping and the sum-mismatch flag; `/students/[id]` gains the report card and the
    analysis; the score history splits minor/major; `/dashboard/exams` leads with **standing** and
    **trajectory** side by side and names the basis; Settings gains exam types + the opt-in.
    `test_exams_v1_8.py` (11).
- **V1-9 (bands / the support programme, 2026-08-02)** — migration **`f8a9b0c1d2e3`** (head,
  revises `e7f8a9b0c1d2`) **on dev + test; prod now needs four.** Bands stop being a letter
  stamped on a child and become a **programme**: assess against a written standard, group, give
  every C child an owner, work, re-assess on evidence, measure the **movement**.
  - **Step 0 first — four fixes, and nothing else was honest until they landed** (`S-180`):
    an intervention could **never be finished**, and `RecommendationsService` filters on
    `status == 'active'`, so a goal achieved in July kept injecting a targeted daily check in
    March · every intervention was created **unassigned** (the assignee came from
    `class_teacher_member_id`, which no screen set until V1-2) · `studentInterventions` was wired
    into the client and **called by nothing** · and **`apply_band_suggestions` +
    `categorize_from_cycle` are DELETED** (`S-183`) — the first re-banded a class from *each
    child's most recent cycle, whatever it was*, so a Tuesday slip test could move eleven children
    between support tiers.
  - **`core/bands.py` is THE vocabulary** — `chip()` renders **"C · Hindi"** (`S-186`: the lowest
    band with the subject that earned it, never a bare letter and never an average),
    `tier_for`/`movement`/`size_warnings`, and the **pre-written descriptors** (`S-175`: 27 empty
    boxes get filled in by nobody). **`services/bands.py::BandService` is the only place a band is
    read or written** — `placements()` is the per-subject read the directory chip, the class
    donut, the daily-check generator and growth all go through.
  - **`D-75` the band is per subject and there is no overall letter.** One letter for a child who
    reads two years below grade and is fine at arithmetic described neither — and the check
    generator then handed him easier *maths*. Rows with `subject_id IS NULL` are the retired
    letter: kept as history, read by nothing. This also makes the daily checks more accurate for
    free, because `_generate` already ran per class-subject.
  - **`D-69`/`D-74` descriptors** (`band_descriptors`, seeded pre-written, editable) carry each
    subject's **own** threshold — before this, two org-wide numbers assumed English and Maths grade
    alike. `S-166`: **the letter never renders without its sentence**, on every staff surface.
  - **`D-70`/`S-185` entry may be judgement; movement is a test.** `/bands/class` pre-fills from a
    chosen locked test and the teacher moves only what she disagrees with (`Q-79`); a child who
    did not sit it is **not assessed** — a word, never a C.
  - **`D-76` promotion** — *"use this as the band test"* at the bottom of an exam she just locked:
    a **flag, never a type change** (`S-182` — re-typing would trade the test for the band),
    **locked only** (`S-184`/`D-53`), size shown with **warn-never-block**, **one subject**
    (`S-187`), and the moves **reviewed before they commit** (`Q-81`) because `student_bands` is
    append-only and a child slipping B → C is the most consequential thing this module does.
    Deliberately **teacher-allowed**: the guard that matters is `locked`, not the role.
  - **`D-77`/`D-87` one owner per subject + the weekly check-in.** `/support` (her children grouped
    by subject) and `/support/[id]`, which **opens already written** (`S-164`) from five tables
    other teachers already fill — attendance, observations, checks, homework, evening study — so
    she is asked only for what nobody else knows. Four fields, once a week (`S-165`), append-only.
    She proposes readiness; **a test moves the band**.
  - **`D-73`/`S-169` the admin board**: movement is the headline, every stuck row names its
    **subject** (`S-188`), the distribution is not on the screen at all, and **no ranking of
    teachers by children moved** (`S-170`).
  - New: `services/bands.py`, `services/support.py`, `endpoints/bands.py`, `schemas/bands.py`; web
    `/support` + `/support/[id]` (new nav item), the rewritten `/students/bands` (+ `[classId]`),
    `band-assess.tsx`, `band-promote.tsx`, `support-block.tsx`, Settings → Support programme.
    `test_bands_v1_9.py` (11); `test_exams.py` / `test_assessments.py` /
    `test_recommendations.py` updated to the new contract.
- **V1-10 (fees — the collection board, 2026-08-02)** — migration **`a9b0c1d2e3f4`**
  (`fee_notes` · `notifications.notif_type` gains `fee_reminder`) on dev + test. `D-62`: **read
  and remind only** — the money math, the append-only ledger and the counter screen `/fees/[id]`
  are untouched. What did not exist was the read a principal needs, plus one list that did exist
  and **nothing ever called**.
  - **`core/collection.py` is the vocabulary.** A quarter is a **due-date window** (`Q-67`):
    `installment_number` breaks the moment juniors pay in 2 instalments and seniors in 4, and
    `label` is free text that fragments into *"Q1" / "Quarter 1" / "1st term" / "April"*. An
    instalment with no due date is **`unscheduled`** — a word, never silently bucketed into Q1.
    `Collection` has **no `outstanding` property** (`S-163`): pending is a forecast, overdue is a
    phone call, and the blend has no name — the `ScaleTally` device a third time.
  - **`services/collection.py::board()` is the one computation every fee screen renders**
    (`S-152`) — the quarter strip, the collection curve against the previous quarter (`S-155`),
    the class table, the defaulter list and the dashboard block. Do not add a second roll-up
    beside it; two screens about the same subject will disagree.
  - **Defect 1 closed:** `overdue_students` has returned name + class + amount + earliest due
    date since P0-D and `school-api.ts` had no function for it. `S-158` the list is built from
    what is **owed**, so a child on a full concession never appears; `S-157` the row names the
    **family** and hands you the number; `S-159` every class row carries **both denominators**
    (*"14 of 38 families · ₹1.4L"*), sorted by families because a morning of calls is
    denominated in calls.
  - **`D-88` years never pool.** `opening_dues` used to be missing from `summary`,
    `overdue_students` **and** `status` — so a child carrying ₹20,000 from last year with this
    year paid read as `paid`. It is now its own labelled line, still outside this year's totals,
    with the year switcher as the route to the year that owns it.
  - **`D-84` the fee conversation history** (`fee_notes`, append-only, the `demo_request_notes`
    shape a sixth time). `said` is the load-bearing column: *"reminded"* is an event, *"spoke to
    the mother — paying after the 15th"* is what makes the row go away (`S-161`) — and it travels
    into the follow-up task so the next caller is not the fourth person this month.
  - **`S-156` the reminder has money-specific manners**, reusing `followup_actions` for
    idempotence (no new table): one per week however many staff press it, **quiet hours**,
    **primary guardian only** (`Q-70` — deliberately unlike the absence alert, which reaches
    everyone), never to an opt-out, and it **stops the moment the payment lands**. Every reminder
    is a human press: no scheduler, because money messages that fire themselves eventually reach
    a family in the week of a bereavement.
  - **`D-83` the one place a teacher sees fee data** — `GET /fees/followup/{task_id}`, guarded on
    being the assignee of that task, rendering the amount, the date and the conversation log for
    **that student only**. The narrowing is asserted by tests in both directions, including a
    sweep of `growth` / `report-card` / `timeline` / `analysis` proving no fee word reaches an
    academic surface (`S-157`).
  - **`Q-69` the parent gets one line**, through the curated allowlist as its own `ParentFeeLine`
    — how much and by when — and **nothing at all when nothing is due**. Never red, never the
    word defaulter.
  - Web: `/fees` leads with the board (the four bare numbers on three denominators are gone),
    `/fees/[id]` gains the conversation above the ledger, the task detail gains the follow-up
    card, and the parent's Today gains the fee line. `test_fees_v1_10.py` (7).

- **V1-11 (parent access: login, notifications, calendar, 2026-08-02)** — migration
  **`b0c1d2e3f4a5`** (`parent_login_attempts` · `guardian_messages`). Two halves of one problem:
  *a notification is worthless if the parent cannot log in to act on it, and a login is worthless
  if nothing ever tells them to open the app.*
  - **`D-13` the front door is school code → class → section → child → date of birth.** Phone-OTP
    could not survive `D-08` removing WhatsApp: a login that depends on message delivery is one
    the school cannot hand out, and it excluded every family whose number the office recorded
    wrong. **`S-55` the child step is type-to-search, never a list** — code → class → section
    would otherwise return every child's name *before any password*, so anyone holding a code
    could harvest the roster; 3+ characters, capped results, rate-limited. **`S-56` the lock is
    keyed per STUDENT**, because a date of birth is ~5,500 guesses and the picker names the
    target; it bumps in its **own committed session** (the `otp_codes` trick) so it survives the
    rollback of the request that raised the error — the test asserts the *correct* DOB is refused
    after five wrong ones.
  - **`Q-29` phone-OTP is kept, not deleted** — moved to `/parent/login/otp` as the recovery
    path. It is the more secure credential and the only way in for a family whose child has no
    DOB on record; `Q-24` that case **burns no attempt** and links straight to it, because it is
    the school's gap and not the parent's mistake.
  - **`Q-25` (b) *"Add another child"*** — each child proved once with their own DOB, then the
    existing sibling switcher works unchanged. Proving one child buys **exactly one child**, even
    when siblings share a phone: deliberately narrower than `verify_otp`, where the phone *is*
    the proof. (`Q-27`: the guardian-phone link stays and stays the notification target — the
    login method changing does not rewrite the account model.)
  - **`D-08`/`D-14` guardian messaging finally has a destination.** `notify_guardian.py` was a
    WhatsApp stub that logged to a file whatever keys were set, so the absence alert, the
    homework notification and the Saturday note all ended their life in a log line.
    **`guardian_messages` is the inbox** (org-scoped + RLS) and all five callers are rewritten to
    it; delivery is web push, which parents can now register for (`/push/subscribe` takes
    `get_current_principal` — a `DeviceToken` is keyed on the User and a parent IS a User, so the
    table needed nothing; only the guard was wrong). **`dispatcher.push_to_user` is the ONE push
    path** — staff and guardian messages share it, so a dead subscription is purged once and the
    rules cannot drift. Deliberately NOT the `notifications` table: its `user_id` is NOT NULL and
    most guardians have never logged in — precisely the families the office most needs to know
    about, which a table that cannot represent them would have hidden.
  - **`S-62` is the honest half of removing WhatsApp.** Push is best-effort (iOS wants the site
    on the home screen, permission can be denied, phones are off) and the absence alert is not.
    So `push_sent_at`/`unreachable_reason` are recorded, and `services/insights/reach.py` +
    `GET /insights/attendance/reach` turn them into **named rows carrying the phone number** on
    the attendance tab and the overview rail. *The reach problem does not disappear; it becomes
    visible.* An **opted-out family is counted apart** and never joins the list the office is told
    to clear — chasing someone who asked not to be messaged is how a school loses the channel.
    `GuardianDelivery.notified` therefore excludes them (two existing tests encode that rule).
  - **`Q-56` the school calendar** — read-only, **zero new capture**, the cheapest win available
    to the portal (*"is school open on Monday?"* is the most-asked question in a school office).
    `whats_on.py` is **not** reused: it lists every student's and every colleague's birthday, and
    a parent sees **only their own child's** — a list of classmates' birthdays is a roster leak
    wearing a party hat.
  - **`S-61` Today is the delivery surface; `Updates` is the archive**, so a parent who opens the
    app once a day has already seen everything and nobody checks two places. Marking-read is the
    one write a parent makes — session bookkeeping, never content; an unread badge that cannot
    clear is just a broken archive. **No replies** (`Q-01` holds): a notification a parent can
    answer is a messaging product.
  - Also shipped: **`S-94`'s `missed` list**, which the server has returned since V1-5 and no
    page rendered, plus `late`/`carried` counts on Today (`S-99`/`D-35`); three drifted
    `parent-api.ts` types repaired against the Python schemas. **Defect found and fixed:**
    `register_org` never minted a `school_code`, so every self-registered org had a parent portal
    that literally could not be entered — and nothing said so.
  - Web: `/parent/login` (the 5-step stepper), `/parent/login/otp`, `/parent/notifications`,
    `/parent/calendar`, `components/parent/{notification-settings,add-child}.tsx`, and the
    "Not reached" block on `/dashboard/attendance`. Seed: the demo org gets school code
    **`DEMO123`** plus a reached and an unreached guardian message. `test_parent_v1_11.py` (9).

- **V1-12 (dashboard visual layer + Lucy reconcile, 2026-08-02)** — **no migration.** Two halves of
  one law: *one computation, many renderings.*
  - **§7's sentence, on the three tabs that lacked it.** Overview, Attendance, Staff and Syllabus
    already led with a computed headline; **Homework, Exams and Tasks opened on a static subtitle
    and went straight to charts**. All three now carry a server-composed `headline` — composed
    server-side, following V1-6's precedent and for exactly its reason: so the tab, the overview
    block and Lucy cannot describe the same week differently. Each sentence keeps its own module's
    rule: homework **never renders an unchecked set as "0% done"** (a percentage with nothing
    behind it blames children for a teacher who has not opened the notebooks — `not_checked` is the
    teacher's gap, always), and reports `late` beside completion rather than inside it (`S-99`);
    exams **names the scale its figure came from** and needs two rated classes before claiming a
    weakest (`S-114`/`S-118`); tasks names **who** the overdue work sits with, because nine overdue
    across nine people is a busy week and nine with one person is a conversation.
  - **The Lucy reconcile, and what it found.** `get_fee_summary` / `get_overdue_fees` still read
    the OLD `FeeService` roll-up — **no quarter windows at all, and `opening_dues` absent from
    every figure** (`B-2`, the defect V1-10 existed to close). So *"how much of Q2 is in?"* got a
    year total that silently dropped the school's worst debtors, while `/fees` beside her showed
    both the quarter strip and the carried line. That is the 44th place a fact gets computed
    differently, and it is precisely what this packet exists to stop. Both are replaced by one
    **`get_fee_collection`** over `CollectionService.board()` — the same computation the screen
    renders (`S-152`) — and the old pair is subsumed, because the board already carries the named
    defaulter list. Registry **43 → 42**, still `role="admin"`: teachers never see fees, in any
    surface.
  - **Verified rather than assumed:** all 42 tool→service calls resolve (nine packets rewrote the
    services underneath Lucy since LU shipped), V1-9 had already made `get_band_board` per-subject
    (`D-75`), and `services/overview.py` was already reading `services/coverage.py` from V1-6.
    A test now **mechanises** that check, so a tool calling a vanished method fails in CI rather
    than the first time a human asks that question.
  - **Charts: no change was the correct answer.** Every chart on those tabs is one §7 explicitly
    prescribes (completion trend → by-class bars · open work by assignee · trajectories →
    distribution · the slack profile · coverage-over-time → RAG donut), so folding any behind
    **More** would remove what the spec asks for. The "no-decision charts" instruction was aimed at
    the old overview's five-chart grid, which DASH3-OV already deleted, and at attendance, which
    already has its toggle. The one-palette grep is clean.
  - ⚠️ **The fee-fence test was strengthened**: it asserted two tool *names* were absent from the
    teacher surface, so renaming the pair would have silently retired the guard. It now checks the
    whole teacher surface with a word-boundary regex (`get_exam_feed` contains "fee" and is
    legitimate). `test_dashboard_v1_12.py` (7).

- **V1-13 (hardening & release, 2026-08-02)** — **no migration.** The release gate, run rather
  than asserted: full suite **492 passed** on real local Postgres, ruff/tsc/eslint/`next build`
  clean, and a **route sweep driving the running server** — 131 GET routes × 3 roles against the
  seeded org (admin 117×200, **0 404s, 0 5xx**; teacher 38×403; **0 `/fees` routes reachable by a
  teacher**). The suite cannot catch a guard that is wrong in the *wired* direction; this can.
  - **The no-dead-ends grep, client side: 30 orphan methods → 0.** Four were not dead code but
    **missing UI**, and one was load-bearing: **`createTerm`/`deleteTerm` had no caller anywhere**,
    so the only terms that could ever exist were the seed's — while `BandService.assign_owner`
    refuses with *"Set up a term first"*, `syllabus_units.term_id` files every chapter under one,
    and `draft`/`approve`/`unapprove` all take one. **A school set up through the wizard could not
    plan term by term at all.** Setup → Academics now has a Terms card. Also wired: **guardian
    add / remove / make-primary / `notify_opt_out`** on the student sheet (a guardian could only be
    set at creation — no second parent, no corrected number, no way to honour a family asking to
    stop being messaged, and every guardian-facing thing in the product keys on those rows); the
    **timetable clash banner** (`/timetable/validate` has existed since V2-P1 and returned its
    verdict to nobody, so the one thing the grid can be *wrong* about was invisible); and clearing
    an exam portion, which feeds `exam_fit` and could be set but never un-set.
  - **19 superseded client methods deleted**, each with its replacement recorded in
    `strip_orphans`' table — e.g. `feeSummary`/`markPaid` (V1-10: `board()` is the only fee read a
    screen may use, and the counter screen records through `pay`), `bandConfig`/`setBand`
    (V1-9 replaced org thresholds with per-subject descriptors and deleted the direct write),
    `skillProfile`/`bandHistory` (the growth payload already carries both).
  - ⚠️ **31 GET routes still have no web caller, and that is reported, not hidden.** Three groups:
    **not web surfaces** (`/billing/webhook`, `/ops/*`); **reached through Lucy, whose tools call
    the service and not the route**; and **genuinely superseded** — which should be deleted, but
    each is covered by a test, so it is a ~17-route change across 8 test files and belongs to a
    deliberate pass, not the end of a session. See `docs/v1/PROGRESS.md` for the list.
  - 🔴 **`topic_progress` (`services/planner.py`) is a SIXTH coverage definition** — it decides
    "done / in progress / pending" from lesson logs on its own rules instead of `core/coverage.py`.
    No screen calls it; **Lucy does**. That is `S-51` wearing a tool for a hat, and it is the first
    thing to fix next.
  - **The demo seed's timetable was unrunnable and every staff screen inherited it.** Anil was in
    three rooms at once on Monday period 4 (the known V1-4 defect, deferred here). The cause was
    not the rotation — V1-4 already offset it — but the subject→teacher map: the three classes are
    always on three *different* subjects, so one teacher owning two subjects collides by
    construction. Fixed **structurally**: each class has its own pair of teachers, so a teacher
    never appears in two classes and no rotation can collide. 6 teaching staff now (also the
    smallest roster on which leave, cover and the slack profile say anything). Today's periods are
    stamped with the teacher who actually holds them. `/timetable/validate` returns `[]`.
  - **`scripts/seed_midyear.py`** — plan §5's acceptance fixture, and the case no other fixture
    exercised: a school adopting part-way through a running year (`tracking_start_date` = the start
    of Term 2). **Three states coexist on one screen, and that IS the test** — Term 1 pre-tracking
    and never planned, Term 2 sized + approved, Term 3 chapters known but unsized. Verified live:
    no red rows, no data claimed before the tracking date, the syllabus board showing the planned
    basis (30%) beside the whole-syllabus basis (16.7%), and `₹18,000 carried from before 2026-27,
    across 3 families — not counted in the figures above` on its own line (`D-88`). Do not "tidy"
    it by sizing Term 1 or Term 3.
  - **`api/.env` was switched from PRODUCTION back to LOCAL**, because this session clicked through
    the app and every tap is a write. `PROD_*_BACKUP` comments are intact — read the
    `# ─── ACTIVE:` banner before running Alembic.
  - 🔴 **Still open, and it is a founder decision:** production runs as `doadmin`
    (`rolbypassrls = true`), so **law 2 is decorative in the one environment that matters**.
    `scripts/provision_app_role.py` exists; swapping prod onto the restricted role is the last v1
    release item.

- **V1-14 (the morning roll — presence, visual, 2026-08-02)** — **no migration.** Founder call after
  walking the shipped v1: the admin dashboard *stated* attendance and could not *resolve* it. One
  card said `91%`; who the 9% were, whether anybody had rung them, which teacher was away and what
  that broke were four more screens away. So presence becomes a board with three denominators, a
  month you can read, and the actions on the row.
  - **`services/insights/presence.py` is the one read.** It COMPOSES — absence runs from
    `AttendanceInsights.streaks`, reasons from the new `absence_reasons`, staff from
    `staff_presence`, "already done today" from `ActionService.done_today`. It does not compute a
    second version of who was absent, which is the whole of `S-51`'s lesson. `GET /insights/presence`
    (the rings + blocks) and `GET /insights/presence/month` (the register, the series, the tables).
  - **Three rings, three denominators** (`students` · `teachers` · `admins`). Averaging them into one
    "school attendance" would describe nobody. **A cohort nobody has marked is neutral and carries a
    WORD** — never 0%, never red; the ring is drawn with a dashed track, visibly waiting to be filled
    in. `in_building`/`roll` are summed **server-side and only over marked cohorts**, so the centre
    figure can never sweep in a roster nobody has claimed to have seen.
  - **Named under three, counted over it** (`INLINE_LIMIT`, decided server-side so the overview, the
    tab and anything reading this board later obey one rule). At or under three absentees the block
    names them with the buttons beside each; above it, one sentence and a link.
  - **The board anchors on the last day the school CAPTURED, not the calendar today** — the V1-4 call-
    board fix, extended. Two bugs it closed: on a Sunday every list came back empty and the board read
    as *"nobody was absent"* rather than *"the school was shut"*; and anchoring on the last *working*
    day still put a *"nothing marked"* ring beside a block naming two absent students. `date`/
    `is_today` ride on the payload and the headline distinguishes **closed** from **not captured yet**.
  - Also fixed, both pre-existing: **a non-working day that was actually taught on** (an exam Saturday)
    vanished from the month grid — the same defect V1-4 fixed in the timesheet, so a day with marks on
    it now appears; and **`ScrollX` did not actually contain its table** — `overflow-x: auto` alone
    does not stop a child's `min-width` propagating its min-content contribution up the tree, so a
    `min-w-[520px]` table scrolled *and* dragged the whole page sideways at 390px. `contain: layout
    inline-size` (both keywords — inline-size alone does not take) fixes it for every tab.
  - **The design is the school's own artifact, the register.** The roll is a **medallion** of three
    concentric arcs — arcs keyed by **cohort identity** (teal/magenta/violet, from the app's validated
    series palette, all pairs passing CVD and normal-vision separation on both surfaces; deliberately
    NOT amber, which on this board means attention), because three arcs in one status hue are three
    green rings and say nothing. Status lives in text on the ledger row beside it. The month is a
    **class × day grid**, not a line: attendance sits at ninety-something percent every day, so a line
    is a flat line, while a bad day is a vertical stripe and a struggling class a horizontal one. The
    ramp is sequential on absence with an explicit zero; **`unmarked` is a dashed outline, its own
    texture and never a step on the ramp**. **Geist Mono** — bundled and previously unused here —
    carries every figure, denominator, date column and column head, so the board reads as a document
    of record. `components/insights/{presence,presence-tables,month-grid,reason-sheet}.tsx`,
    `RollMedallion` in the chart kit.
  - The overview's attendance and staff cards are **removed**: the panorama says both, better, and
    keeping them would state the same two facts twice. `ReasonSheet` was extracted from the tab so
    the dashboard's "Add reason" is not a dead button. `ColumnChart` gained `xInterval` (a month of
    dates at `interval={0}` was a smear). `test_presence_v1_14.py` (9). Full suite **501 passing**.
  - **Revision 1 (same day, founder walkthrough).** Six fixes, three of them real defects:
    · **the ring gap.** A round stroke cap extends the arc by `stroke/2` at EACH end, so 238 of 240
      drew as a closed circle — identical to 240 of 240, which is the one thing a presence ring may
      never do. `arcGeometry` subtracts the cap overhang, floors a tiny-but-real share at a visible
      mark, and draws the closed circle only at a true 100%.
    · **`spanDays` / `ReasonSheet` serialised dates through `toISOString()`**, which in any timezone
      east of UTC returns the PREVIOUS day for a local-midnight Date. Cover opened on the wrong day
      for every Indian school, and an absence reason recorded before 05:30 was filed against
      yesterday. Both now format from local Y-M-D.
    · **"Arrange cover" only ever knew about today** — a teacher away Mon–Wed showed *"no lessons
      today"* while nine periods went uncovered. `_approved_leave` now carries the leave's span,
      `StaffAbsentee` carries `date`/`leave_start`/`leave_end`, and the sheet gains a day switcher
      across the absence.
    Plus: **"Follow up" asks who** (a member picker with the class teacher as the one-tap default —
    it used to fire straight at the server, which guessed the class teacher and told the admin
    nothing about whose list it landed in); the attendance tab shows **three separate rings** side
    by side and drops the three blocks beside them (the tables below are the fuller version of the
    same lists, and saying it twice raises the question of which is authoritative); the **admin
    section is hidden when no admin is away**; and the three tables are rebuilt in the **task
    module's table language** — `Popover` extracted to `components/ui/popover.tsx` and shared with
    `boards/board-table.tsx`, plus its card shell, colour-barred group headers, uppercase column
    heads over CSS-grid rows and `Avatar`. The difference kept deliberately: these rows END in an
    action rail rather than inline edits, because a task row is a thing you change and an absence
    row is a thing you respond to. The register's class margin and month total are now **sticky** to
    both edges, and the staff chart drops unmarked days rather than plotting empty slots.

- **V1-15 (the syllabus panorama, 2026-08-02)** — **no migration.** Founder call: the module could
  say *how much* and never *is that good for today*. A percentage is unreadable without the
  calendar — 47% is excellent in July and alarming in February — so the board answered "how much?"
  four times (four stat tiles, a coverage bar chart, then a table of the same nodes with a
  percentage column) and left the verdict to a RAG chip three columns away.
  - **The device: every figure is drawn on a track carrying the plan's own marker** — the share the
    approved plan had scheduled by today. The verdict becomes a distance you can see: arc past the
    tick is ahead, arc short of it is behind, and the gap is the size of the problem. `PaceRing` and
    `PaceBar` in the chart kit, repeated at three scales (school ring · ledger row · matrix cell), so
    one visual habit reads the module. It is `S-51`'s law applied to the drawing.
  - **Both markers ship, and a marker is only ever drawn against the figure it shares a denominator
    with**: `expected_pct` beside `coverage_pct` (of the plan), `expected_syllabus_pct` beside
    `syllabus_pct` (of the whole portion). Divided server-side, like every other percentage here —
    a component dividing `due / planned` for itself is how the browser got its two `.reduce()`
    calls the first time.
  - **`GET /insights/syllabus/pulse` + `SyllabusInsights.pulse()`** — the overview's block: the ring
    and the class/subject breakdowns, **narrowable to a term**, worst-first. The same `_rows` batch
    and the same `_node` roll-up the tab uses (no exam checkpoints, no trend), so the summary and
    the board it links to cannot quote different numbers for the same morning. Its own route because
    the term switcher re-reads on every press and recomposing seven modules to change one filter is
    a cost the other six never asked for. The overview's syllabus `SectionCard` is **removed** — the
    precedent V1-14 set for attendance and staff.
  - **`SyllabusNode` now carries what it needs to be DRAWN** — `tone` and `pace_caption` decided
    server-side, because three surfaces render these nodes and a tone each worked out for itself
    would be three verdicts about one teacher on one morning. Plus `due/taught_due/behind_topics`,
    `taught_full`/`taught_partial`/`untaught_topics` (a weighted figure cannot be taken back
    apart — 12.5 is 12 finished plus one half-done or 11 plus three), and `classes`/`subjects`,
    the load a teacher's pace has to be read against.
  - ⚠️ **The marker exposed a disagreement that was always there.** The forecast answers *will it
    finish* — plan against remaining calendar — so a subject that has taught nothing in April is
    still green if the year has room; `behind_topics` answers *is it on schedule today*, and that
    is what the arc draws. Painting a visible gap green would make the device lie, so overdue
    topics take the tone to amber and the caption names which question each answer is to (*"all 1
    on course to finish · 5 topics overdue"*). Neither figure is invented and neither overrides the
    other. `behind_topics` on a node counts **rated rows only** (`S-42`) — every due topic of an
    unlogged class-subject is untaught *on the record*, so counting it would report a school as
    badly overdue on a record nobody wrote, and it orders the worst-first lists.
  - **New analytics, all from capture that already existed.** `causes` — `S-41`'s four causes
    **counted**, zeroes kept, in the order capture → calendar → sizing → teaching, because "6
    subjects behind" and "4 of those 6 are behind because nobody wrote a lesson log" are different
    findings and only the last cause is about teaching (the tally counts the row but contributes no
    topic figure for `not_logged` — `S-42` again). `PortionMeter` — finished / part-taught / not
    started, which a weighted percentage cannot say. **`FinishForecast`** — `baseline_finish` and
    `projected_finish` have ridden on every row since P1 and were rendered **nowhere**, so the board
    could say a subject was three weeks behind and never that at this pace it lands after the year
    ends (`overrun_days`, `overruns_year`). **`TeacherMatrix`** — teacher × class, cells are
    class-subjects and never an average of them; a row's width is the load, the fill of its cells is
    the pace, and load and pace are one conversation a list can only show half of.
  - Also fixed, pre-existing: **`arcGeometry` drew a coloured nub at 0%** — the visible-minimum floor
    (there so a tiny-but-real share is still a mark) applied to a true zero, which is the mirror of
    V1-14's closed-circle bug and just as much a lie; it hit every `ActivityRing` and the roll
    medallion. `Fraction` and `ColumnHead` are now **one component each** in `insights/shared.tsx` —
    both had been written twice.
  - Web: `components/insights/syllabus.tsx` (the kit), `PaceRing`/`PaceBar` in `components/charts`,
    the rewritten `/dashboard/syllabus`. `test_syllabus_v1_15.py` (12). Full suite **513 passing**,
    ruff clean; web tsc + eslint + `next build` clean; no sideways scroll at 360px with the matrix
    open; reviewed in the browser in light and dark.

- **V1-16 (the day-book — staff time, seen, 2026-08-02)** — **no migration** (the category
  colour rides on the existing `organizations.work_categories` JSONB). The timesheet has
  existed since SF-1 and the admin could only ever read it **one person at a time**
  (`/timesheet`) or **one period at a time** (`/staff/today`); nobody could see the school's
  day. Now `/dashboard/staff` leads with a grid — people down, periods across, one cell each —
  and `/dashboard` carries the same board trimmed, beside the one figure it implies: how much
  of the day's staff period capacity was spoken for.
  - **`services/insights/daybook.py` COMPOSES, it does not recompute.** `TimesheetService.org_day`
    is the three-query batch that already unions the timetable, the timesheet, the cover board
    and staff attendance (`S-72`/`Q-37`), so the day-book and the timesheet cannot disagree
    about the same Tuesday (`S-51`). It adds only the tally and the sentence.
    `GET /insights/daybook` (any date) + `/daybook/glimpse` — **the same payload**, trimmed,
    with `rows_total` so the overview says "and 6 more" rather than showing a partial school
    as if it were the whole one.
  - **`services/staff_record.py`** + `GET /insights/staff/{id}/record` — one person's day,
    month, categories and the SF-1/V1-4 attendance and leave figures, with a written summary
    (`ai/staff_record.py`, env-gated, deterministic floor). 🔴 **It is a record, not an
    appraisal, and that is enforced rather than intended** (`D-25`/`S-67`): no score, no rank,
    no completeness percentage, no path to pay — and the model's system prompt forbids
    appraisal language **in the negative**, because a model asked to "summarise a teacher's
    month" reaches for *productive* / *needs improvement* unprompted. The suite greps the whole
    written payload for it. `/staff/me/record` exists so the self-access the service already
    allowed has a door (`/timesheet/month` links to it).
  - **`core/work_types.py::CATEGORY_COLORS` — five colours, from a fixed list, never a hex an
    admin types.** They were run through the dataviz six-checks against BOTH surfaces, in the
    ring order they are assigned in, together with the teaching ink they sit beside. There are
    five because a sixth fails a check: categories past the fifth render **slate** and are read
    by name, which makes the colour budget the short-picker rule with teeth. `other` is pinned
    to gold so it means the same thing in every school. **Do not add a sixth by eye.** The grid
    paints ONLY recorded work: teaching is the day's default state and a wall of green says
    nothing, so the hues land on the cells the timesheet ADDS.
  - **New cell kind `closed`** — a period nobody was asked to work. It is not free, it leaves
    every denominator, and `occupied_pct` is **None** rather than a share of nothing. Found by
    looking at a Sunday: the board said "not a school day, nothing was expected of anybody" and
    then drew 43 FREE cells and a ring reading 4%.
  - **Two pre-existing defects fixed, both in `TimesheetService.month`:** it **zeroed every
    non-working day**, so a warden's Sunday prep and a Saturday exam duty vanished from the
    month's totals while sitting plainly in `timesheet_entries` (V1-4 fixed exactly this in
    `week` and never carried it here — **this also lands on the teacher's own
    `/timesheet/month`**); and the record **counted the future as worked**, so on the 2nd of
    August it read *"Teaching — 38 of 38 periods (100%)"*. Together those two put **109%** on
    the page, the ring's slices and the totals beside them having come from two different day
    sets. Totals now stop at today and the slices use the same window.
  - Also: `away` became a hatch (a dashed hairline at 84px in dark mode was indistinguishable
    from an empty cell — the two facts the board exists to separate), "FREE"/"AWAY" typed into
    forty cells was deleted in favour of texture + tooltip + the row's own summary, the shared
    `Donut` legend **wraps instead of truncating**, and the record's month line needs 5 points
    before it draws. `test_daybook_v1_16.py` (9). Web: `components/insights/daybook.tsx` (one
    component at two densities), `components/staff/record-view.tsx`,
    `/staff/member/[memberId]`. The Staff tab's old "Today" strip column is **deleted** — the
    day-book above it is the same fact at full size.

- **V1-17 (homework — the funnel, 2026-08-03)** — **no migration, no new capture.** The board
  opened on four stat tiles and then drew the **same measure three times** (completion over the
  window · by class · by subject). None of them said how much homework there was or whether
  anyone had looked at it, and the two bar charts each collapsed a whole axis, so *"6-B is low"*
  and *"Hindi is low"* could never resolve into *"6-B Hindi is where it happens"* — the only
  version an admin can act on.
  - 🔴 **The three headline figures were in two units.** `assigned`/`checked` counted **sets of
    homework** and `done` counted **students**, so they could not be drawn on one track and did
    not read as one story. **`HomeworkFunnel` is the fix and the vocabulary**: everything counts
    *student-homeworks*, one row per student a homework was given to, so the stages **nest** —
    `given ⊇ checked ⊇ graded` — and each gap is a length. Import it; do not re-derive it. The
    numerator rides along as `done_weighted` so no screen reconstructs it from the parts and gets
    `partial` wrong on the way.
  - **The two gaps are two findings and are never the same colour.** `given − checked` is nobody
    having gone through it — HW-1's rule, the **teacher's** gap: it wears the no-record hatch
    (V1-14's unmarked cell, V1-16's away cell), sits in the same right-hand zone on both bars so
    the eye reads how much of the page is simply unknown, and is never a colour and never a zero.
    `checked − graded` is `carried` + `waived` (`D-34`/`S-98`), reported in words rather than
    absorbed into either side. **`completion` divides by `graded`, never by `given`** — a school
    that checked nothing can never read as a school that did nothing.
  - 🔴 **Fixed: the daily series was a SECOND walk with its own arithmetic.** It re-ran
    `HomeworkService._load` (ten queries to draw one board, against a docstring promising five),
    counted `status == "done"` literally so **`late` was dropped from the numerator**, kept
    `carried`/`waived` **in** the denominator, and never ran the absent→carried rewrite. The chart
    therefore read lower than the sentence printed directly above it, and a child off sick pulled
    the line down. It is now accumulated inside `overview()`'s single pass through
    `core/homework_verdict` — `S-51` closed for the third time in this module.
  - **`ClassSubjectMatrix`** (class × subject, one cell) replaces the two duplicate bar charts;
    tone is decided **server-side** (the V1-15 precedent — three surfaces render these cells) and
    an unchecked pair is **dashed, never red**: the grid's worst-looking square must not be a hole
    in the record. **`LoadStrip`**'s column **height carries volume**, so a quiet day and a day
    where nothing came back are no longer the same short column. Range filter **Week · Month ·
    Term · Year** in one row above everything it scopes; the endpoint's 60-day clamp is gone
    (400) and the series **buckets weekly past 21 days**.
  - **Best/worst goes to classes and subjects only.** Ranking teachers by their children's
    completion would make a person's standing a function of forty other people's evenings; the
    checking ledger rates her on **her own act** — did she go through what she set — and that is
    the only thing on the screen that rates her at all (`D-39`/`S-92`). Deliberate, not an
    oversight.
  - The **stage ramp** is ordinal, not categorical (the stages are ordered and nested — one hue
    deepening is the honest encoding), stepped off series slot 1, validated `--ordinal` against
    both card surfaces, and **re-stepped rather than flipped** for dark, where "more" must read
    brighter. It lives in `globals.css` as `--hw-stage-1/2/3`. Do not adjust by eye.
  - Also fixed: **`waived` was missing from `HomeworkScopeRow` entirely**, so waived work was
    invisible on the by-class and by-subject tables while the student history reported it · the
    improvement delta was **written over `streak`**, so a row claimed a miss streak it did not
    have and the screen printed *"N fewer misses"* out of a field named for the opposite thing
    (it has its own `improvement` now) · **`homework:unchecked` had been rendering twice** on the
    dashboard since DASH3, once on the rail and once in the alert feed.
  - ⚠️ **Found by looking at the built screen, and the reason to keep doing that:** the new
    overview block printed a **14-day sentence over a 7-day funnel** — *"430 given"* above bars
    reading 205 — because the server composes that sentence over `HomeworkInsights.WINDOW_DAYS`
    and the client asked for its own window. One exported `OVERVIEW_WINDOW_DAYS`, the strip's
    label read off the payload, and a test asserting the section's metrics equal the board's
    funnel. `test_homework_v1_17.py` (12).
  - **Deliberately NOT built:** an `opened_at` "teacher started checking" capture. A
    `homework_checks` row already means *she went through it*, and its absence meaning
    `not_checked` is the load-bearing rule of the module; a second, weaker definition would let a
    teacher who merely opened the sheet count as having checked.

- **V1-18 (fees — collection against the calendar, 2026-08-04)** — **no migration, no new
  capture.** A collection percentage cannot be read on its own: 45% is excellent in May and
  alarming in February, and every fee figure in the product was printed without the date that
  makes it readable — four bare numbers on one line, then a strip of quarter buttons carrying a
  percentage each.
  - **`Collection.due_by_today` is the missing denominator** — everything the school has **asked
    for** by today, paid or not. It is deliberately **not `overdue`**, which is only the *unpaid*
    part of it; confusing the two makes a school that collected every rupee on time look like it
    was never asked for anything. One extra accumulator on a loop that already had
    `inst.due_date` and `today` in hand. `due_pct` puts the marker on the same track as `pct`,
    `shortfall` floors at zero (a school that collected early is not "minus ₹40,000 behind"), and
    **`pace_tone()` decides the colour once, server-side** — three surfaces render these rows.
  - **`CollectionBoard.year`** — the whole year, which nothing exposed before: the board's
    top-level figures are the **picked quarter's**, so "how is the year going" could only be got
    by summing quarter rows in a browser. Accumulated in the same pass as the quarter rows, so
    the year ring and the quarter rings cannot disagree.
  - **The device is V1-15's, reused** so fees reads with the habit the syllabus board already
    taught: the arc is what came in, the tick is where the schedule says you should be, and the
    distance between them is the finding. **The year is ONE ring, not three** — the three figures
    share one denominator, so three rings would draw the same track three times and the "billed"
    one would be a full circle saying nothing; and `collected` can **exceed** `due_by_today` when
    families pay in advance, which a marker expresses and stacked arcs cannot. **Quarters are one
    ring each** — those *are* independent scopes.
  - **A quarter nobody has been asked to pay yet is neutral, dashed, and says "not due yet"** —
    never a bold 0%, never red. It has not been missed, and painting next January red every
    August is how a board stops being read (ux §5, §10). `state` (`past|current|future`) rides on
    the row so no renderer compares dates itself and gets a different answer in another timezone.
  - 🔴 **The dashboard fee block was the last surface on the old fee arithmetic.** It read
    `FeeService.summary()` — four fields, no quarters, `opening_dues` excluded — while `/fees`
    read `CollectionService.board()`, contradicting `collection.py`'s own *"every fee screen is a
    rendering of `board()`"* and repeating the defect V1-12 fixed for Lucy. It also computed
    `outstanding = total − collected` **in the browser**: exactly the pending+overdue blend
    `Collection` refuses to have an `outstanding` property in order to prevent (`S-163`).
  - 🔴 **`PATCH /fees/installments/{id}/due-date` 500'd on every call** — routed to
    `FeeService.update_due_date` since P0-D, and that method never existed. Nothing called the
    route, and V1-13's no-dead-ends sweep looked for orphan *client* methods and orphan *GET*
    routes, so it was neither. It matters here because an instalment with no due date is
    **`unscheduled`** and this route is the only way to resolve the state the board now names.
    Implemented (append-only `installment_edit` row; clearing back to NULL is allowed, because
    `unscheduled` is a legitimate state). ⚠️ **Still no web caller** — wire it in the fee deep pass.
  - Also: the collection curve's y-axis rendered clipped as `)0₹` (a rupee figure plus a suffix is
    wider than the 44px gutter) — `TrendLine` gains **`yFormat`** · `by_class` was an unsorted,
    uncoloured text table of seven numeric fields, now ranked rows with bars and both
    denominators (`S-159`) · `shortMoney` is the lakh/crore short form for ring centres, because
    "₹1,35,000" at 26px either overflows the hole or shrinks below reading size.
  - `test_fees_v1_18.py` (11), including the identity that makes the pace figure worth having:
    **`shortfall = overdue − prepayments`**.

- **V1-19 (the observance corpus — India's calendar, by state, 2026-08-04)** — migration
  **`c1d2e3f4a5b6`** (head) — **applied to local dev, test AND DO prod on 2026-08-04**, and the
  668-row corpus is loaded in prod. ⚠️ Unlike every migration before it this one is **not purely
  additive**: it DROPS `observances.state`, so prod code that predates it 500s on
  `/events/suggestions` and `/platform/observances` until the deploy lands. V1-7 built the whole
  events module — catalogue tables, approval sheet with an editable date (`D-79`), the cost
  preview, the what's-on feed — and shipped the table **empty** (`Q-63`, deliberately: filling it
  by asking a model when Diwali is would have been `S-123`'s rejected row wearing a table for a
  hat). So every school's suggestions queue was blank with nothing on screen to say why. `Q-63` is
  now answered from named sources.
  - 🔴 **`observances.state` (text) could not express the corpus, and failed SILENTLY.**
    `UNIQUE(key, date)` is load-bearing — it is what makes re-importing a corrected file *fix*
    every school rather than double-suggest (`S-151`) — so there is one row per observance per
    year, and one `state` per row. Almost nothing in the Indian calendar works that way (Onam:
    Kerala + Lakshadweep; Chhath: four states; Ugadi: five, under three names). Importing the
    second state did not error: `bulk()` upserts, so it **overwrote** the first. Now
    **`states text[]`** (NULL/empty = all-India) + a GIN index; the read is
    `:school_state = ANY(states)`.
  - 🔴 **`organizations.state` was FREE TEXT and nothing had ever read it.** A school that typed
    `TN`, `Tamilnadu` or `Orissa` matched no row — empty feed, no error, no log, forever. Worse,
    the old query was `Observance.state == (org.state or "")`, so an **unset** school compared
    against `""` and matched nothing, reading exactly like an empty catalogue.
    **`core/indian_states.py`** is the canonical vocabulary (28 states + 8 UTs, ~60 aliases:
    postal codes, former names, common misspellings). `normalise()` **never guesses** — no fuzzy
    matching, no prefixes — because unresolvable text must mean *no state* (all-India rows only:
    thin, never wrong), not a school in Kerala reading Punjab's gazette. Both surfaces that set it
    are now **pickers** (Setup → Settings, and the operator's New-school sheet); a value typed
    before the picker is kept, shown as `(unrecognised)`, never silently rewritten.
  - **The corpus is `app/data/observances/`, split by how much work next year costs.**
    **`FIXED`** recurs on the same (month, day) — the three national holidays, all 36 state/UT
    formation days, the school observance calendar (Children's Day, Teachers' Day, National
    Science Day…), and the **whole UN international-days list** — and is generated by arithmetic
    for **any** year, forever. **`MOVABLE[year]`** is the lunisolar/Hijri half (Diwali, Eid, Onam,
    Holi, Easter) and is the *only* block a human touches: extending to 2028 is one afternoon with
    a panchang and the state notifications, not a re-key. **334 rows/year × 2 years = 668**, all
    36 states covered, zero (key, date) collisions.
  - **`S-125` is what keeps the UN list from drowning the feed**: ~150 of its entries ship
    `minor`, ~35 school-relevant ones `major`, and the feed defaults to major. Tier is the only
    editorial judgement in that file; the dates and names are the UN's own.
  - **`S-150` enforced rather than intended** — every row carries its `source`
    (drikpanchang · the state notifications · the reorganisation acts · un.org), and **where
    authorities genuinely disagree the row takes one date and `note` names the other**, never an
    average. Real disagreements recorded: Makar Sankranti 2027 (gazettes 14 Jan vs panchang
    15th), Muharram 2027 (all state lists 16 Jun vs panchang 15th), Holi 2027 (22nd in WB/TS/BR,
    Dhulandi 23rd in GJ/MH/RJ/PB/OD — filed as **two rows**, because they are two holidays),
    Vijayadashami 2026 (20th vs 21st by state), Onam 2027, Milad-un-Nabi 2027. **`D-79`'s
    editable approval date is the structural answer** to the fact that no single national
    calendar is correct for every school — the corpus gets a school most of the way, the admin
    resolves the rest in one tap.
  - `collisions()` is **the corpus checking itself for the exact defect that caused the packet**,
    called by the loader before it writes and by the suite. `scripts/load_observances.py` goes
    through the same `bulk()` path the operator's paste-import uses (idempotent: re-running
    reports `updated`, never duplicates), prints the target host, and **refuses a non-localhost
    database without `--yes`** — the catalogue is shared by every school on it.
  - `ObservanceBulkOut.unresolved_states` **reports** what it could not place (the syllabus
    importer's rule): an unresolvable state is the one failure here with no symptom.
  - **The seed's three placeholder rows are gone** — `scripts/seed.py` now loads the real corpus,
    so the demo school sees the suggestions a real school would. Web: the catalogue's state field
    is a multi-select, the paste format's state cell is **pipe-separated** inside the
    comma-delimited row, and a row's scope reads *"Kerala, Lakshadweep"* / *"Bihar, Jharkhand +2
    more"* / *"all India"* — never a wall of 36 names.
  - `test_observance_corpus_v1_19.py` (14). Full suite **559 passing**; two V1-7 tests updated to
    the `states` contract. ⚠️ Birthday/event **notifications are NOT in this packet** — the corpus
    and its scoping only; the notification surfaces are the next piece.

- **V1-20 (the calendar, in use — xlsx import, the year board, Show events, 2026-08-04)** —
  **no migration.** V1-19 filled the catalogue; this is the two surfaces that make it usable —
  the operator adding **next** year without a deploy, and the school admin actually deciding
  dates on the calendar they already look at.
  - **Super-admin: `services/observance_import.py` + `/platform/observances/import/{analyze,commit}`.**
    `S-151`'s "a small importer per source plus one annual human review", made real. Two calls
    on purpose: **nothing is written until the operator has seen every row**, and what commits is
    the values they looked at (the client posts the *parsed* rows back under an identity mapping,
    so a parser change between the two calls cannot save something nobody saw).
    `ingest.py`'s division of labour holds — **the model maps COLUMNS and never decides a date**
    (`S-123`); the suite runs AI-off and the keyword heuristic alone must place a plainly named
    sheet. `_parse_date` reads Excel serials, real datetimes and fourteen written formats and is
    **day-first**: `%m/%d/%Y` is *absent*, because accepting it turns 3 April into 4 March on
    exactly the rows where both readings parse — a calendar's worst failure and a completely
    silent one. **Broken rows come back WITH their problems, never dropped** (an importer that
    discards 8 of 150 reports "142 imported" and nobody finds the 8; here each one is a day a
    school stays open for), blocked rows sort to the top of the preview, and a **duplicate
    (key, date) inside one file** is caught and named rather than silently upserting over itself.
  - **School: the year calendar carries two levels of certainty**, which is the whole design.
    **Decided** = a `calendar_events` row that has already changed every plan's capacity — solid
    fill, weighted numeral. **Proposed** = an undecided catalogue date that has changed nothing —
    **dashed outline**, faint tint. Outline-vs-fill rather than two greens because the difference
    is categorical (is this real yet?) not one of degree, and because texture survives greyscale,
    a projector and CVD; the dashed device is the roll medallion's / day-book's / homework
    funnel's own "no record here". A **tap** on a suggested day opens the V1-7 approval sheet
    (date still editable `D-79`, open/closed still the central act `D-58`, cost still shown
    `S-143`); a **drag** still paints. Splitting them matters — painting a fresh "Holiday" over
    Diwali would throw away the name, the source and the note the catalogue carries.
  - **`GET /events/catalogue` + `EventsBrowser`** — the **Show events** modal: the whole researched
    corpus, grouped by month, filterable by state/year/search, the school's own state
    **preselected**. Deliberately not fenced to that state (the feed answers *what should I act
    on*; this answers *what is in the calendar you shipped*, and hiding other states leaves an
    admin unable to tell a missing date from an out-of-scope one). Every row carries
    `applies_here`, and decided rows are **labelled, not hidden**. `decided_count` is never sent
    to a school — how many other schools acted on a row is platform telemetry.
    ⚠️ **Absent `state` ≠ "all states"**: omitting the param means *this school's state* (what the
    dropdown shows first) and the sentinel `state=all` means every state. They cannot be collapsed
    — and `""` cannot carry it, because the browser's `qs` helper drops empty params, which would
    have made "All states" silently mean "my state".
  - 🔴 **Two defects found by running the built screen, not by reading it.**
    · **`suggestions()` had no tier filter.** Written when the catalogue was empty, it returned
    **248 rows over a year** the moment a real corpus landed — "World Steelpan Day" beside
    Independence Day — painting a third of the calendar as *decide me* and running the sidebar
    queue down the whole page. `S-125` had already called this: the feed is **major-tier by
    default** (90/year, 23 in the 90-day queue), `include_minor=true` is the escape hatch, and the
    sidebar caps at 6 with the rest one tap away in Show events.
    · **A fast tap could not paint or open anything.** `commit` runs on a window `pointerup` that
    can arrive in the same tick as the `pointerdown` that set the anchor; React state is async, so
    it read a stale `null`, bailed, and left the cell stuck in its selection ring. Invisible with a
    slow human press, reliable with a quick one — and now on the critical path, since tapping one
    date is a primary action. Anchor/hover are mirrored in refs.
    Also fixed: the header row hit 393px at a 390px viewport once "Show events" joined it, scrolling
    the whole page sideways (`flex-wrap`).
  - Web: `components/ui/modal.tsx` (centred dialog — the sibling of `Sheet`: `Sheet` is for acting
    on one thing, this is for looking something up), `school/events-browser.tsx`,
    `school/observance-import.tsx`; the catalogue screen gains year + state filters (editing "any
    saved date" is the operator's job and a flat search over two 334-row years cannot get them
    there) and keeps the paste box for fixing six rows without opening Excel. Seed: the demo org is
    now **Telangana / CBSE**, without which the whole regional feature is invisible in the one org
    anyone clicks through. `test_events_v1_20.py` (17). Full suite **576 passing**, ruff clean; web
    tsc + eslint + `next build` clean; verified in a real browser end-to-end — tap a suggested date
    → approve → 45 suggestions become 44, the cell turns solid, and teaching days correctly stay
    297 for a *school-open* approval. One V1-7 test updated to the major-tier contract, pinned in
    both directions.

- **BD-2 (ABC bands — the programme gets its own area, 2026-08-04)** — **no migration.** V1-9 built
  the support programme and left it reachable only as a tab under **Students**, which is where you
  go to look a child *up*. Founder call: bands become a first-class area with the three things the
  module could not do — see the shape of the school, allocate owners from one table, and let the
  subject teacher set a band at all.
  - 🔴 **A teacher could not file a band.** Every band write was `require_admin` (V1-9's
    `endpoints/bands.py`), so the person who knows whether the child can read the passage could see
    a band and never set one — the whole teacher half of the module was unreachable.
    `POST /bands/class/file` is now `require_academic` and **`BandService.assert_can_band`** gives
    her exactly her own monitored class-subjects, **blocked with a sentence rather than filtered to
    an empty table** she would read as "nobody is banded here" (`S-46`). Reading a class board is
    the same permission as writing it. `GET /bands/scope` resolves it to names and is what the two
    tab rows and the nav item are both built from; `me.has_band_scope` rides on `/auth/me` like
    `is_class_teacher`, so a teacher outside the programme never sees the item (ux §13).
  - **`services/insights/bands.py` COMPOSES** — every tier comes from `BandService.placements` and
    the headline is `programme()`'s own movement sentence, so the dashboard block, the Overview tab
    and the programme board cannot describe one term differently (`S-51`).
  - ⚠️ **`S-169` is kept, not reversed.** It rejected the distribution as the admin's *headline*,
    and it still is not one: `BandDistribution.headline` is the movement sentence and the tiers
    render underneath. What the founder asked for is the **shape** — which class carries the
    support load, and which subject — which movement genuinely cannot answer.
  - **The unit is the PLACEMENT, not the child** (`D-75`). There is no overall letter, so a boy who
    is A in Maths and C in Hindi is counted in both columns; only a *subject* row collapses back to
    children. `caption` states it on every mounting, and a test asserts the arithmetic, because the
    obvious "fix" is to collapse him to one row and that quietly reinstates the letter the module
    deleted. Tiers are **current standing**, not this term's rows — `student_bands` is append-only,
    so the newest row IS the band, and scoping to the running term would empty the board for every
    school that banded in April. Percentages divide by what was **assessed**, never the roster;
    `eligible - assessed` is its own number beside them; a subject that is taught but not monitored
    reaches no denominator.
  - **The A/B/C ramp is ORDINAL and computed, not chosen** — what deepens along it is how much
    support a child needs, so it is one hue (V1-17's homework-stage precedent), stepped off series
    slot 6 so a band chart and a homework chart on one scroll are never two blues, and validated
    with `validate_palette.js --ordinal` against both card surfaces (dark **re-stepped, not
    flipped**). It is deliberately **not** the status palette: painting C red turns a teaching
    group into a verdict on a child. `--band-a/-b/-c` in `globals.css`, `BAND_COLOR` in the chart
    kit. **"Not assessed" is not a step on the ramp** — it wears the dashed no-record texture the
    register (V1-14) and the homework funnel (V1-17) already use.
  - **Allocation** (`/bands/allocation`, admin-only) — unassigned first, grouped by class or
    subject, filtered **server-side** so the headline and the rows cannot disagree.
    `GET /bands/allocation/suggestions` returns the teachers already in front of the child first
    *with the reason*, then **everyone else**: suggested, never restricted (a picker that refuses is
    one the office routes around by phone). `load` is **capacity, never a score** — `S-170`.
  - **The written summary** (`GET /bands/support/{id}/summary`, `ai/band_summary.py`) — the
    `ai/report.py` contract: the model voices figures it was handed, and no key / timeout / bad JSON
    falls through to the deterministic builder, so the owner's page is never blank. Its prompt
    forbids diagnosis and ability language **in the negative** (a band is a teaching group, not a
    condition) and forbids reading absence as effort; the suite greps the payload for that
    vocabulary rather than trusting the prompt.
  - **Assignments on the support page** reuse **per-student homework** (`homework_assignments
    .student_id`, V2-P3) and `core/homework_verdict.py` — deliberately not a support-specific
    store, which would be a seventh definition of "did the child do the work" and would let a
    child's support page disagree with his own homework history. `not_checked` renders as "not
    checked yet" and never as the child's miss (HW-1's rule).
  - Web: `/bands` area (Overview · Manage bands · **Teacher allocation** (admin) / **My students**
    (teacher) · Reports), `components/insights/band-distribution.tsx` mounted twice (full tab +
    compact dashboard block), `components/school/support-assignments.tsx`, `SupportListView`
    extracted from `/support` and mounted in both places. `/support` and every `/support/[id]` link
    still resolve. `test_bands_v2.py` (10). Full suite **586 passing**, ruff clean; web tsc +
    eslint + `next build` clean; reviewed in a real browser at 1440px in both themes and at 390px.

- **AT-1 (attendance end-to-end: the staff directory, the class teacher's desk, the register's own
  door, 2026-08-05)** — migration **`c2d3e4f5a6b7`** (head) **on dev + test; prod is at
  `c1d2e3f4a5b6` and still needs it.** Founder walkthrough of the attendance loop. One new table
  (`student_notes`); everything else is a screen for capture that already existed, or a defect.
  - 🔴 **The admin board showed YESTERDAY under today's heading.** `PresenceService._anchor` walked
    back a fortnight for the most recent day anything was captured, so a school that had marked
    nothing by 9am read last night's figures — the admin's actual question ("has the register been
    taken?") answered about a different day. **An open day is now always today**; the fallback
    survives for CLOSED days only, where it was always right (on a Sunday an empty board would read
    as "nobody was absent"). `school_open` rides on the payload so the two are never confused.
  - 🔴 **One class marking read as the whole school.** `_students_today` denominated the ring on the
    marked classes, so 1 of 12 classes taking the register rendered a complete, healthy day.
    `PresenceRing` now carries **two denominators and never confuses them**: `total` = the cohort's
    whole strength, populated whether or not anything is marked (the founder's ask — the roll is
    readable every morning), and `counted` = the part of it in a marked group, which is what `pct`
    divides by. `unmarked`/`not_marked` are their own numbers, `PresenceBoard.marked` is the "has
    anything been captured" flag the medallion branches on (`roll` is now non-zero on an untouched
    morning, so reading it as capture would put a confident 0 in the centre of an empty register),
    and the students-away block is narrowed to classes that marked ON the anchor day — `streaks`
    walks each class's own last captured day, so yesterday's absentees were being named under a ring
    saying nothing was marked.
  - **Staff → People** (`services/staff_directory.py`, `/staff/directory`) — the join across
    `memberships` × `school_classes` × `class_subjects` nobody had written. Setup → Members is the
    ACCOUNT screen (invite state, reset a password); this is the people screen: who works here,
    whose homeroom is whose, what each person carries. Filter/group by role or class, inline role
    edit, row → the person's file (`/staff/member/[id]`, which now leads with an editable
    `StaffProfileCard` above the V1-16 record — establishment above time, and the record stays
    deliberately un-editable: it is a record, never an appraisal, `D-25`/`S-67`).
  - **`D-89`: "class teacher" is a DERIVED role, never a third `org_role`.** Founder call. `org_role`
    stays the two-value CHECK column every guard is built on (SPRD2 §2); the directory's Role
    dropdown offers Admin · Teacher · **Class teacher**, and picking the third opens a class picker
    and writes `school_classes.class_teacher_member_id` — the one place the fact has ever lived. A
    `class_teacher` value in the role column would be the same fact in two stores, and they would
    disagree on the first reassignment. `role_key`/`role_label` are the rendering of the pair.
    `class_teacher_of` is a **full replace** (so un-assigning is expressible), and handing a class to
    a second teacher REPLACES the first — a homeroom has one owner, and a silent refusal would leave
    the admin unable to hand it over. Role changes route through `MemberService.change_role` so the
    last-admin guard and the `token_version` bump cannot be skipped by a second door.
  - 🔴 **`services/periods.py::visible_class_ids` is now THE class-read rule** — the subjects she
    teaches **∪ the homeroom she owns**. The homeroom half was missing everywhere, so a class teacher
    who takes none of her own class's subjects (a warden, a primary homeroom teacher) could see the
    register and the syllabus and was **refused her own class's exam feed and report cards**.
    `ExamService._taught_class_ids` and `ReportCardService._assert_class` both delegate to it.
  - **My Class is a six-tab area** (Overview · Attendance · Students · Syllabus · Homework · ABC
    bands). `services/my_class.py` **composes and computes almost nothing**: coverage from
    `MySyllabusService`, homework from `core/homework_verdict`, exams from `ExamService.feed`, bands
    from `BandService.placements`, attendance from `day_matrix`/`classify_marked_day` — so a class
    teacher and her principal cannot read different numbers for one Tuesday (`S-51`). The unmarked
    rules hold on every tab: the register shows the roll and a **word**, the homework funnel reports
    **no completion figure at all** rather than 0% when nothing is checked, and the band block counts
    **placements not children** (`D-75`) with `not_assessed` its own number and never a tier.
  - **`student_notes`** — the class teacher's own log about a child, **append-only** (law 3, the
    `fee_notes` shape), staff-only, and writable only by the homeroom's teacher or an admin (reading
    is the wider `visible_class_ids` set). The one deliberate exception to P5: everything else the
    school knows is a byproduct of doing the work; this is the thing she noticed that no capture
    surface has a field for. It stays out of the parent portal **by construction** — that projection
    is an allowlist built field by field. Mounted at the foot of `/students/[id]`.
  - **`GET /attendance/my-classes` + `/attendance`** — the register's own door. The school's rule is
    *the class teacher takes it at period one, and if she is away any teacher of the class can*;
    `assert_can_take_class` has permitted exactly that since V2-P2, but attendance was reachable
    **only from a My Day period card**, so the person covering — who by definition is not standing in
    that class at period one — had nowhere to go. **Nothing here widens permission**: it adds the
    screen the rule needed. Any date (a register missed on Tuesday is taken on Wednesday), a class
    this teacher takes nothing in never appears at all, an already-marked class stays editable by the
    same set (correcting a mis-tap is not a privilege), and the day's first marked period is still
    the only one that alerts guardians. Capture reuses `RollCall` — `S-12`'s one component, one
    default — so a second way to write the same rows was not created. Nav gains **Attendance** for
    every teacher.
  - `test_staff_directory.py` (7) · `test_my_class_v2.py` (9) · `test_attendance_board.py` (6);
    `test_presence_v1_14.py` +1 and its denominator test rewritten to the two-denominator contract.
    Full suite **609 passing**, ruff clean; web tsc + eslint + `next build` clean.
  - ⚠️ **Staff attendance itself needed no change** — SF-1 + V1-4 already own it (admin-marked,
    exception-shaped, half-day/late, the month summary). It was verified, not rebuilt.
  - **Revision 1 (same day, founder walkthrough).** Three changes, one of them a defect that had
    been shipped in four files:
    · 🔴 **`toISOString().slice(0, 10)` broke day navigation.** It serialises a LOCAL-midnight Date
      through UTC, so east of UTC stepping forward a day returns the same string (the button looks
      dead — the reported symptom on Staff → Attendance) while stepping back jumps two. V1-14 fixed
      the identical bug in the cover sheet and the reason sheet; six more files still had it.
      **`dayKey`/`todayKey`/`shiftDay`/`shiftMonth`/`thisMonth` in `lib/format.ts` are now the one
      implementation** — never format a calendar date through UTC again.
    · **`/attendance` is the register book** (`D-90`): class buttons (assigned classes only, first
      open by default) + **Take attendance** beside them, then the month as a read-only grid.
      **`build_register` was extracted from `MyClassService.register`** so the class teacher's
      annotated grid and the every-teacher read-only one are ONE computation with two doors —
      they differ only in who may open which class. `GET /attendance/register` guards on
      `visible_class_ids`: reading is deliberately not narrower than writing, because a teacher who
      can mark the roll and cannot see last week's is being asked to work blind. `RegisterBook`
      replaces the old `<table>` + `position: sticky` with **two panes** — a fixed name column and
      a grid that scrolls sideways — so the phone and the desktop run one code path (sticky cells
      inside a scroller depend on table layout, and at 360px the name column had to truncate to
      nothing). `contain: layout inline-size` on the scroller is load-bearing (the V1-14 `ScrollX`
      fix). Column totals ride at the foot of each day, `—` on a day nobody marked.
    · 🔴 **`D-91` — once-per-day is now the DAY's register, not period 1's.** `first_period` has
      existed since V1-3 but its rules said *"attendance happens in period 1"*, which asks the
      wrong thing all afternoon and has no answer at all for the morning period 1 does not happen.
      Now: **`mark` lands on the day's existing register wherever it was taken** (and `roster`
      READS the same one, or period 5 would show a blank sheet and save it over the morning's
      absences — invisible data loss); the redirect clears `class_subject_id` so the register
      moving does not relabel the period; `marks_attendance` on My Day is **dynamic** — every
      period while the register is missing, none once it is done, except the holder so its taker
      can still correct it; `day_attendance_taken` rides alongside so a card can say *"already
      taken today"* instead of silently dropping the section. The heatmap treats the holder as the
      only expected cell (otherwise a register taken at period 3 left period 1 amber forever and a
      captured day read "1 of 2"), and `periods_scheduled` is the MODE's count, so a once-per-day
      school never reads "1 of 7 periods marked". `test_once_per_day.py` (8); one V1-3 test updated
      to the new contract and pinned in both directions.

- **EV-2 (the day's notice — events & birthdays, dismissible, 2026-08-05)** — **no migration.**
  Founder call after walking V1-7 in the built app. The feed was right and its *siting* was wrong:
  a card on the dashboard with a "Coming up" list under it, plus a strip on My Day, spent real
  vertical space every day on the one block nobody has to act on — and the teacher's copy showed
  her the **whole school** (the office's exam block, a colleague's birthday, another class's
  children) on the screen she opens walking between rooms.
  - **One line, dismissible for the day, opening into a popover** (`components/school/day-notice.tsx`,
    replacing `whats-on.tsx`). The expanded list is a `Popover`, not a disclosure, so **nothing on
    the page moves** — the whole point was the layout cost. Dismissal stores the feed's own `date`
    under `day-notice:<scope>`, so tomorrow's notice is a new notice and yesterday's press does not
    silence it; it is an external store (`useSyncExternalStore`), not effect-written state, with an
    in-memory fallback so a browser with storage blocked still gets a button that does something.
  - **There is no "upcoming" section any more, and the horizon is the reason.** Both surfaces read
    at **7 days**: a date joins the notice a week out and leaves it the day after (founder — *"any
    event will show up 1 week before"*), which is the only warning a school acts on. A 21-day
    horizon is what forced a second list to hold it.
  - **`feed(class_id=…)` is the teacher's scope** — that class's children, no calendar row, no
    staff birthday, and the `S-124` denominator is the **class's own roster**. It is a roster read,
    so it goes through `periods.visible_class_ids` (AT-1) and is **refused with a sentence, never
    filtered to an empty list** (`S-46`) — nothing showing for a class she may not see reads as a
    class with no birthdays. Still one computation (`S-121`): the same rows, scoped, never a second
    birthday reader with its own idea of a leap year or a vacation.
  - Mounted where the class is actually in front of her: the **period card**, **My Class** (on the
    shell, so all six tabs agree and it re-scopes with the picker) and the **register** door. The
    My Day strip is **deleted on purpose** — recorded so nobody optimises it back.
  - `S-132`/`S-133`/`S-128` all hold: it asks for nothing and is absent when there is nothing on ·
    the day, never the age · a vacation birthday says it was moved. The admin keeps one quiet
    pointer to the undecided-dates queue; the teacher's row has no action on it at all.
  - `test_day_notice.py` (4). Reviewed in a real browser (light + dark, 1440px + 390px, expanded
    and dismissed, zero sideways scroll).

- **BA-1 (the support owner's assessments — ABC bands, the teacher's half, 2026-08-05)** — migration
  **`d3e4f5a6b7c8`** (head) **on dev + test; prod is at `c1d2e3f4a5b6` and needs `c2d3e4f5a6b7`
  then this.** Founder walkthrough of BD-2: the admin side was right and the teacher side was a
  list she could not filter over a programme she could not measure. She could give work
  (per-student homework, reused) and write a weekly check-in; what she could not do was **set a
  check and record how each child did on it**, so *"did the last three weeks move anybody?"* was
  answered from memory.
  - **Support loses its sidebar item.** The programme is one job and it had two doors — the weekly
    check-in under `Support`, the bands under `ABC bands`. `/support` now 307s to
    `/bands/my-students`; **`/support/[id]`, the child page, is unchanged** and every link to it
    still resolves (it is the one screen the module lives or dies on and a second copy is a second
    place for the check-in to be half-implemented).
  - 🔴 **That removal would have stranded people, and the fix is the interesting part.** An admin
    may hand a Band C child to **anyone** — `OwnerSuggestion` suggests and never restricts — but
    `has_band_scope` asked only whether you *teach* a monitored subject. A warden given three
    children would have had them assigned to her and **no nav item to reach them by**. `has_scope`
    now means *gets the area*; **`can_band`** is the narrower signal (a monitored class-subject)
    that the Manage-bands tab is keyed on, and **`owns_students`** is the new one. Same widening on
    `/auth/me`.
  - **`core/band_assessment.py` is THE vocabulary** — three metrics, and they are three kinds of
    statement: `marks` (a number with a denominator) · `rating` (an ordinal judgement on her own
    scale) · `other` (a word). **They never pool.** `Tally` has no method returning a blended
    figure — the `ScaleTally` device a fourth time — a rating has **no percentage** (3 of 5 is not
    60% of anything, and printing it as one invites it to be added to a mark), and `result_text`
    cannot render without its scale.
  - **Not `assessment_cycles`, and the separation is load-bearing.** That table carries
    `core/exams.py`'s scale, verify-and-lock, question marks, and it moves a child's band under
    `D-76`. A support owner's 1-to-5 reading rating reaching any of that is exactly the pooling
    `ScaleTally` exists to make un-writable. Nothing recorded here touches a child's standing,
    report card or band.
  - **`covers_all` keeps the roster COMPUTED** (HS-1's `session_classes` rule): a child assigned to
    her next week is on a standing weekly check with nobody editing anything, and one who moves on
    drops off. A picked list is frozen — right for *"these two are re-doing it"*, and the create
    dialog says which she is getting rather than leaving her to find out in a month.
  - **Not evaluated is a word**, three times over (HW-1's rule): `pending` is a state and never a
    bold 0% · a child with no row is not a zero · **the average divides by the children actually
    evaluated**, so a teacher who has marked two of three does not read as a class that scored
    badly. `status` is **derived**, never stored, so it cannot drift from the rows that decide it.
  - **Results are a full replace** (`homework_results` / `attendance_exceptions`), not an append
    log: law 3 governs *decisions*, and a mistyped 7 for 17 is corrected in place the way a
    mis-tapped absence is. Leaving a child out puts him back to *not evaluated* — the only way to
    undo a mark typed against the wrong name. Deleting an assessment is refused once any result is
    on it (`D-53`'s reason).
  - **The student log is `student_notes`, not a per-assessment note store** — the same log the
    class teacher writes, with a nullable `assessment_id` for what occasioned it. A year later the
    person asking *"what happened with Kabir"* wants everything anyone noticed in one scroll.
    `_can_log` gains a **third author**: the owner of his active support plan (widened by one named
    relationship, not by a role — another teacher is still refused), and **reading is no longer
    narrower than writing**, which it was for an owner outside the class.
  - **Deliberately not capture-by-exception**, and that is not a lapse: P1v2's budget is about
    *daily* capture across a whole class, and this is six children where the number for each one IS
    the point — the reasoning that already lets `file_bands` touch every row of a class.
  - Web: **`/bands/my-students`** rewritten (class chips, table, the two actions on the row —
    assigned work and the log) and **`/bands/assessments`** added (paginated, grouped by class,
    status filter, create dialog, evaluation sheet whose input follows the metric: number · slider ·
    word). `S-170` holds throughout — no completion percentage for her check-ins, no comparison
    against another owner, no streak. `test_band_assessments.py` (16).
  - ⚠️ **Three defects found by running the built screen, not by reading it** — the reason to keep
    doing that:
    · 🔴 **"Asha hasn't been checked in None weeks."** The V1-9 headline filtered on
      `(weeks_since_checkin or 99) >= 3`, which sweeps in a child with **no check-in at all** and
      then formats his `None` straight into the sentence. **Never checked in is a state, not a
      duration** — the two now get two sentences, because they call for two different actions
      (start, or catch up). Fixed in `SupportService.my_students` too, where it originated.
    · 🔴 **The headline said "5 children" over a table showing three names.** Placements and
      children are two counts (`D-75`), and the unit discipline the schemas keep has to reach the
      sentence: *"3 children assigned to you, 5 across subjects"*.
    · 🔴 **The band chip was white text on all three tiers, and the ramp INVERTS between themes** —
      so white on light-mode A is **2.28:1** and on dark-mode C is **1.55:1**, a letter nobody can
      read at whichever end is currently pale. `--band-ink-a/b/c` is now chosen per tier per theme
      (all ≥ 4.5:1) and **`components/school/band-chip.tsx` is the one component** — it had been
      written three times in this packet alone. Recompute the inks if the ramp is re-stepped; never
      adjust either by eye.
  - Reviewed in a real browser (Chrome, teacher login, light + dark via the `.dark` class — **not
    `prefers-color-scheme`, which this app does not use** — 1440px + 390px), including the whole
    create → evaluate → record flow: zero sideways scroll on every screen, and a child left blank
    stays *not evaluated* rather than scoring zero. Full suite **637 passing**, ruff clean; web tsc
    + eslint + `next build` clean.

- **SY-1 (the syllabus board — the table, the exam map, the teacher's plan, 2026-08-05)** —
  migration **`e4f5a6b7c8d9`** (head) **on dev + test; prod is at `c1d2e3f4a5b6` and now owes
  three** (`c2d3e4f5a6b7` → `d3e4f5a6b7c8` → this; all purely additive). Founder call. Plan →
  Syllabus was a one-class, one-subject **editor**: to answer *"which chapters are late?"* an admin
  picked her way through class × subject holding the comparison in her head, and the module could
  say *how much* (V1-6) and *is that good for today* (V1-15) but could never show **the syllabus
  itself**.
  - 🔴 **`plan_entries.baseline_week_start` — the change everything else rests on.**
    `_forecast_rows` computed `baseline_finish = max(week_start)` from the LIVE rows, so "the
    baseline" was whatever the plan currently said. Harmless while the only writer was a full
    re-draft behind a lock; a hole the moment a teacher can move a chapter, because dragging
    chapters into December would raise the baseline to meet the projection and **turn every red
    subject in the school green with nothing taught**. Stamped once at `approve`
    (`_freeze_baseline`, NULL rows only — approving Term 2 in October must not forgive Term 1's
    slip since April), read as `COALESCE(baseline_week_start, week_start)`. P2's "the approved plan
    is the baseline" is now true of the *data*, not only as long as nobody wrote to it. The table
    renders both dates, so a move is visible rather than silent.
  - **`services/plan_schedule.py` — moving a chapter, and it is allowed on an APPROVED plan.**
    That is safe only because of the freeze above: she reschedules the schedule, the promise stays
    where the admin locked it, and the distance between them is the slip. Refused: a chapter nobody
    sized, dates outside the year, another teacher's subject (403 `not_your_subject`, `S-46` — a
    sentence, never an empty screen). **Reported but still saved**: a range too short for what she
    put in it (V2-P5's rule — she is the one who knows whether she can go faster).
    ⚠️ `_place` deliberately does **not** reuse the drafter's greedy `distribute`: greedy fills from
    the front and stops, so dragging a chapter's end out a fortnight saved the dates and returned
    an identical plan — the control looked broken. **The range she draws IS the chapter's span**;
    topics spread across it in proportion to their sizes, last topic in the final teaching week.
  - **`exam_portion_units` — a portion is a SET of chapters.** `upto_topic_id` is a prefix and
    cannot say what a school says in November: *"Term 1 examines chapters 1, 2, 3 and 5; chapter 4
    goes to Term 2."* The prefix is **kept, nullable, and still read** (`_portion_topic_ids`
    resolves either form to one topic set), so every portion recorded before today keeps its exact
    arithmetic and is shown as `legacy_prefix` rather than silently rewritten. `_exam_fit_rows` now
    subtracts SETS instead of walking "after the previous cut", which is what makes the skipped
    chapter land in Term 2 instead of vanishing between the two exams.
  - **`services/syllabus_board.py` COMPOSES and computes nothing** — coverage/plan/logs from
    `CoverageReader.snapshot` (V1-6's one definition), pace from `forecast_org`, the status word
    from the new `core/coverage.py::chapter_status`. Six queries for any number of classes. Scope
    is a **block**: admin = the school, teacher = `visible_class_ids` (her subjects ∪ her homeroom).
    `expected_pct` is V1-15's pace marker at chapter scale — how much of the chapter's own window
    has gone by in **teaching** days — divided server-side, because two of the five places
    "syllabus covered" used to be computed were `.reduce()` calls in React.
  - `difficulty` + `remarks` on `syllabus_units`: plain editable columns, not an append log (law 3
    governs *decisions*; a remark is corrected in place, the `homework_results` call). Writable by
    the subject's own teacher — a chapter remark only an admin may write is a remark nobody writes.
    `difficulty` is NULL until judged and renders **"not set"**, never a defaulted "moderate".
  - **Web:** Plan → Syllabus is two tabs (**Syllabus** · **Exam mapping**). The table groups by
    class/subject/term/status, filters, sorts, expands to topics **only when the school tracks
    them** (`has_topic_detail` — a chapter-only school's single topic mirrors its chapter and does
    not expand). The subject is a **sub-heading, not a column** (grouping by class already names
    the class, and the column was eating the width that made chapter names readable), the chapter
    column is **sticky** and the progress cell is V1-15's `PaceBar`. `not_scheduled` wears the
    dashed no-record texture everywhere and is never red and never a 0%. **`/plan/classes` is
    deleted** (founder) — both routes 307 to the board; `TeacherLoad` + `schoolOverview`/
    `teacherLoad` went with it (teacher load is Dashboard → Staff, off real timetable rows).
    **My subjects** is now a dashboard: four tiles about *her*, the V1-6 pace list, one subject's
    chapters, and **Adjust the plan** — a ribbon where chapters are draggable bars, exams and term
    ends are rules drawn through every lane, gaps are hatched and counted, and the ledger below is
    the keyboard path. **Plan → Year opens in View mode** with a View / Mark dates switch: a tap
    used to declare a holiday on the spot, which on a year grid at phone width is a fat-fingered
    closure that silently leaves every plan's capacity. Reviewing a suggested date still works in
    view mode — that opens the approval sheet and commits nothing.
  - `test_syllabus_board.py` (15). ⚠️ **Three defects the browser found and the suite could not**,
    all now pinned by tests: the board **500'd whenever `year_id` was omitted** (`AcademicYear
    .is_current` does not exist — and the first request a real screen makes has no year yet, so
    that was the common path, not an edge case) · **extending a chapter did nothing** (the greedy
    placer above) · and the ribbon's scale was read live mid-drag, so a bar dragged past the axis
    edge accelerated away from the pointer.

- **ST-2 (the student's two halves — Directory and Academics, 2026-08-05)** — migration
  **`a4b5c6d7e8f9`** (head) **on dev + test; prod is at `c1d2e3f4a5b6` and now owes four**
  (`c2d3e4f5a6b7` → `d3e4f5a6b7c8` → `e4f5a6b7c8d9` → this; all purely additive). Founder call. A
  school holds two different KINDS of fact about a child and Students offered one door for both:
  the **administration record** (name, parents, phone, date of birth — entered once, corrected by
  the office) and the **record the school MAKES** (register, class log, homework, exams — written
  every day by teachers, read as a trend). One table carrying both columns served neither.
  - **Students becomes a nav GROUP for the admin** (`children[]` on `NavItem`, rendered by
    `sidebar.tsx`, flattened in the mobile hamburger — a drawer inside a popover is a second layer
    of open-to-find). **A teacher gets Academics only, flat**: every write on Directory is
    admin-only, so a group whose first entry is read-only is a drawer with one useful thing in it.
    Scoping is the SERVICE's job, not the nav's. **The top-level Homework item is gone** — the
    homework log lives under Academics now; `/homework` (the check-sheet desk, `D-36`) is untouched
    and linked from it.
  - **`services/student_records.py` COMPOSES and decides nothing.** Attendance is the marked-periods
    minus exceptions derivation `growth.py` already makes; exams go through
    `exam_marks`/`ScaleTally`; homework through `core/homework_verdict`; the chip through
    `BandService.chip_map`. **Six queries for the whole school** — `load_class_marks` is four
    round-trips and the roster asks it of every class on one page load, so `exam_marks.load_marks`
    batches across classes (the `forecast_org` precedent, `PR-6`) and the per-class reader is now a
    one-line wrapper. `GET /students/records`.
  - 🔴 **A per-student class-log line is `lesson_observations`, NOT `lesson_logs.student_id`.**
    Fifteen call sites read `lesson_logs` as *what a CLASS was taught* — coverage, growth, the daily
    report, the timeline, the forecast, the capture heatmap — and every one would have had to learn
    to exclude the per-student rows, with the first to forget inflating the syllabus board with a
    lesson that reached one child. `entry_kind` (`observation` | `log`) separates the period card's
    tap-a-deviating-student flag from a line a teacher deliberately wrote, and **each read is scoped
    to the kind it means**.
  - 🔴 **Two live defects that separation exposed**, both pinned in both directions: `growth.py`
    renders a rating-less observation as **`needs_work`**, and `support.py` labelled one
    **"excellent"** — so a neutral note ("forgot his book") would have become evidence about a
    child's ability, in opposite directions on two screens. The support prefill now reads the label
    off the row (`S-164` keeps BOTH kinds — a class-log line about her child is exactly what the
    owner's check-in wants).
  - **`assessment_scores.remark`** — the teacher's optional word about one paper, written at the
    only moment she knows why the mark is what it is. Per (student, exam), never required, and
    **not on the parent projection** (an allowlist built field by field; a test asserts it).
  - Endpoints: `GET/POST/DELETE /classroom/class-log`, `GET /classroom/homework-log`,
    `GET /students/records`. `HomeworkIn.student_ids` writes **one assignment row per child**, never
    a shared row with a list on it — every reader keys on (assignment, student).
  - Web: `/students` is a role-aware landing; `/students/directory` (+ `[id]`, the record edited one
    fact at a time — a single-save sheet meant a half-typed name discarded a fixed phone number);
    `/students/academics` with six tabs (Students · Class logs · Homework · Exams · Reports ·
    Analytics). `scores` → `academics/exams` and `trends` → `academics/analytics` moved with
    `git mv` and 307 from their old paths; `/students/bands` redirects into the `/bands` area,
    finishing BD-2's move. `components/students/class-subject-picker.tsx` is shared by both log
    tabs and lands a teacher on **her own** subject.
  - `test_student_records.py` (17). ⚠️ **Found by running the built screen:** the roster's
    `completion` is a 0–1 FRACTION (`core/coverage.completion_pct`, as everywhere else in the
    product) and the homework log rendered it as `0.889%`; and each class group is its own
    `<table>`, so auto layout put "Attendance" at a different x in 6-A than in 6-B and no column
    could be scanned down — `table-fixed` + a colgroup on both halves.

- **MC-3 / EX-3 (My Class deepened · the exam module gets its calendar, 2026-08-05)** — **no
  migration.** Founder walkthrough of the class teacher's area and of exams. Two halves, one rule
  each time: a screen must answer the question it is *opened with*.
  - 🔴 **Plan → Syllabus was showing a class teacher her homeroom's five other subjects.**
    `SyllabusBoardService.board` filtered on `visible_class_ids` — her subjects **∪** the homeroom
    she owns — so the screen she opens to plan *her own teaching* was four-fifths somebody else's
    plan, and her own rows were outnumbered on it. The union is gone from that board; the homeroom
    read has its own door in **My Class → Syllabus**, which asks for the SAME
    `SyllabusBoardService.board` with `whole_class=True` after `_klass` has established she owns
    it. The flag is deliberately **not on the wire** (no query param) — only `MyClassService` sets
    it, or any teacher could ask for any class by guessing an id. `scope` gains `class`.
  - **My Class → Syllabus is now the full SY-1 chapter table**, not a five-line pace list: which
    chapter, when it was due, when it was taught, the frozen baseline beside the live date. Same
    `SyllabusTable` component, same service — a class teacher and her principal cannot read
    different figures for one chapter (`S-51`). The pace list stays above it as the summary, since
    *"is Maths moving?"* and *"which chapter is late?"* are two questions.
  - **My Class → Homework is a day book.** V1-17's funnel says how much came back and cannot say
    **what was given**, which is the question asked at the gate. Today's homework now renders in
    full (the `text`, the subject, the teacher, who did not do it, by name), earlier days are
    paginated rows that open, and the funnel is folded to a strip. Same arithmetic throughout —
    `core/homework_verdict`, student-homeworks, `carried`/`waived` outside the denominator — and
    the rule that mattered most here: **a day nobody checked carries no percentage at all**, never
    a 0% and never red. Paginated over DAYS, not assignments: a day cut in half by a page boundary
    is unreadable.
  - **My Class → ABC bands expands to its children.** "Not assessed" is no longer a **tile** — beside
    A, B and C it read as a fourth tier, the one thing it must never be (`D-75`); it survives as the
    header denominator ("11 of 15 assessed") and as the dashed segment of the bar. Opening a subject
    names its children with how each is doing **in that subject**, through
    `exam_marks::ClassMarks.figures`, so the row carries the **scale** its percentage came from
    (`S-114` — a bare number here is exactly what `ScaleTally` exists to prevent) and reads "no marks
    yet" rather than 0%. Ordered A → B → C then by **name**: sorting children by their marks turns a
    teaching group into a ranking (`S-170`). `_attendance_window` was extracted so the roster table
    and the tier list walk the register **once**.
  - **Plan → Exams (new tab) — the school's own exam calendar, in use.** Not a new table:
    `calendar_events` with `type='exam_block'` has been the exam calendar since V2-P7 (the planner
    paces against it, `ExamPortion` maps chapters onto it) and the only way to make one was to
    paint a date on the year grid. `services/main_exams.py` **composes** — the exam is the calendar
    row, a paper's marks are `ExamService.save` unchanged, the report card is
    `ReportCardService` — and gives it two levels: the exam list (admin adds/edits/removes; a
    teacher reads the identical list locked, never a second thinner one) and, under a picked exam,
    the class × subject papers. The link is `assessment_cycles.exam_event_id`, which V1-8 added
    (`S-115`) and **nothing had ever populated from a screen**.
  - 🔴 **A teacher could overwrite a colleague's paper.** `ExamService.save` asked
    `assert_can_take_class`, which answers *may she stand in front of this class* — true for every
    subject of a class she teaches one subject of. Right for attendance, wrong for a mark.
    `MainExamService.assert_can_record_subject` is the narrower question (admin · the subject's own
    teacher · the homeroom's class teacher, who enters the paper for a colleague who has left) and
    is asked in the **service**, so every write path gets it. `can_edit` on the grid is computed
    from the same three clauses — a greyed cell the server would have accepted is a screen lying
    about permission. Reading stays deliberately **wider** than writing: she sees every subject's
    card for her classes, and may alter only her own column.
  - 🔴 **`ExamService.detail` 500'd on any exam filed under an exam block** — it selected
    `CalendarEvent.name`, and the column is `title`. Dormant since V1-8 precisely because nothing
    populated `exam_event_id`; the new grid turned that line into the module's main path.
  - **Students → Exams redesigned + ABC bands → Exams (new tab), one component.** The landing was
    class tiles over a flat feed: you picked a class, then picked your subject *again* inside the
    capture form from a dropdown of every subject in the school — most of which the server now
    refuses. Now **class → subject → record**, with the subject **pinned** into `ExamCapture`
    (`fixedSubjectId`), and the feed below filtered to that pair and **paginated**
    (`ExamService.feed_page`, `GET /assessments/exams/page`) — the old `limit`-capped list left the
    31st test of a term unreachable from any screen. `components/school/exam-workbench.tsx` is
    mounted twice: Students (every class-subject she teaches, from `/planner/my-subjects`) and ABC
    bands (only **monitored** class-subjects, type pinned to `band_test`). Deliberately the same
    screen — a band test IS an exam (`D-76`), and a band-specific capture surface would be a second
    place for a child's mark to live. ⚠️ Recording there still **does not move a band**: the letter
    moves from a *locked* test in Manage bands with the moves reviewed first (`D-70`/`S-184`/`Q-81`).
  - New: `services/main_exams.py`, `schemas/main_exams.py`, `endpoints/main_exams.py` (`/main-exams`),
    `components/school/{main-exam-board,exam-workbench}.tsx`, `/plan/exams`, `/bands/exams`.
    `test_myclass_exams.py` (11) — the two syllabus scopes pinned in **both** directions, because a
    scope test that only checks what is present cannot tell a block from an empty screen.
