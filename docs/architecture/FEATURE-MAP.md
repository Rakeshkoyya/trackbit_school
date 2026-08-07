# Feature map — what exists, where it lives, who can see it

The as-built inventory of TrackBit School. Extracted from the running app on
**2026-08-07**: 420 routes across 36 endpoint modules, 92 services, 42 Lucy
tools, 80 web routes.

**This file is state, not history.** It answers "where does X live and who may
use it". For *why* a design is the way it is, see
[`docs/logs/packet-log.md`](../logs/packet-log.md).

Built for two jobs on the roadmap:

- **The MCP server** — §8 is the tool surface that already exists and the gap
  between it and the full API.
- **Package tiers (basic/gold/platinum)** — §9 is the feature-ID list a tier
  would reference, plus an honest account of what the current billing code can
  and cannot express.

### Regenerating the route facts

```bash
cd api && uv run python scripts/route_map.py          # human-readable
cd api && uv run python scripts/route_map.py --json   # machine-readable
```

It imports the FastAPI app and walks each route's dependency tree, so the guard
column is what the server actually enforces — not what a doc claims.

---

## 1. The access model

### 1.1 The two real roles

`memberships.org_role` has exactly two values, `admin` and `teacher`
(`api/app/core/roles.py`; CHECK-constrained). v1's `coordinator` and `office`
were migrated into `admin`, and their guards survive only as **admin-only
aliases**:

| Guard | Resolves to | Routes |
|---|---|---|
| `require_academic` | admin **or** teacher | 168 |
| `require_admin` | admin | 100 |
| `get_current_member` (alone) | any member | 54 |
| `require_coordinator_up` | admin *(alias)* | 37 |
| `require_office_up` | admin *(alias — the fee fence)* | 19 |
| *(none)* | public | 16 |
| `require_super_admin` | platform operator (`users.is_super_admin`) | 15 |
| `get_current_parent` | parent portal session | 8 |
| `get_current_principal` | member **or** parent | 3 |

Totals are exact and sum to 420 — regenerate them with
`uv run python scripts/route_map.py`, which prints this table as
`### guard totals`.

> When you touch a file using an alias, consolidate it to `require_admin`.
> Do not add new uses of `require_coordinator_up` / `require_office_up`.

### 1.2 The three derived roles

These are **not** role values. They are relationships, computed per request,
and surfaced on `GET /auth/me` so the nav can branch:

| Derived role | Truth lives in | Flag on `/auth/me` | Grants |
|---|---|---|---|
| **Class teacher** | `school_classes.class_teacher_member_id` | `is_class_teacher` | the **My Class** area; `student_notes` write; report cards for the homeroom |
| **Band owner** | an active `interventions` row assigned to them | `has_band_scope` | the **ABC bands** area and `/bands/my-students` |
| **Subject teacher** | `class_subjects.teacher_member_id` | *(implicit)* | that class-subject's plan, exam column, syllabus rows |

`D-89` is load-bearing: **class teacher is a derived role and must never become
a third `org_role`**. The same fact in two stores diverges on the first
reassignment. The Staff → People screen offers "Class teacher" in a Role
dropdown, and picking it writes `school_classes.class_teacher_member_id` — not
the role column.

### 1.3 The one class-visibility rule

`api/app/services/periods.py::visible_class_ids(db, m)` — **the** answer to
"which classes may this member read":

- admin → `None` (unrestricted)
- teacher → **subjects she teaches ∪ the homeroom she owns**

The union's second half was missing everywhere until AT-1, so a warden or
primary homeroom teacher who taught none of her own class's subjects was
refused her own class's exam feed and report cards. `ExamService` and
`ReportCardService` now delegate here. **Do not re-derive this from
`class_subjects` alone.**

### 1.4 Two rules that hold on every surface

- **Teachers never see fees.** `/fees` has 20 routes; **19 are
  `require_office_up`** (admin). The 20th is `D-83`'s single deliberate
  exception: `GET /fees/followup/{task_id}` (`require_academic`), guarded on
  being that task's assignee, rendering one student's fee detail *inside that
  task only* — never a fees nav item, never a class list or collection figure,
  never a fee field on any academic surface or Lucy tool.
- **Bands (A/B/C) never reach a parent or guardian.** P4. The parent projection
  is an allowlist built field by field in `services/parent_portal.py` — never a
  spread — and `test_parent_portal.py` asserts the absence of bands, skills,
  raw observations and check flags.

### 1.5 Where scoping is actually enforced

The guard on a route gives you the **role**. The finer scoping — is this your
class, your subject, your student, your support child — lives in the
**service**, not the route. `require_academic` on `/attendance/mark` does not
mean any teacher may mark any class; `AttendanceService` asks
`assert_can_take_class` first.

**This matters for the MCP server and for tiering:** neither can be built by
reading the route table alone. A tool that calls the service inherits the
scoping for free; a tool that queries tables directly does not.

---

## 2. Platform & tenancy — the operator

Schools do not self-onboard. The operator (super-admin) creates each school,
runs setup from data the school hands over, then hands over credentials.

| Feature | ID | Services | API | Web |
|---|---|---|---|---|
| School creation, stats, enter-org | `platform.orgs` | `platform.py`, `readiness.py` | `/platform/orgs*` | `/platform` |
| Enquiries desk (demo requests) | `platform.enquiries` | `marketing.py` | `/marketing/demo-requests*` | `/platform/enquiries` |
| Observance catalogue (India, by state) | `platform.catalogue` | `observances.py`, `observance_import.py` | `/platform/observances*` | `/platform/catalogue` |
| Billing / subscription | `platform.billing` | `billing.py` | `/billing*` | *(no dedicated screen)* |

Platform tables (`observances`, `demo_requests`) are **deliberately org-less**:
no `org_id`, no RLS policy, `require_super_admin` on every read and write.

`GET /marketing/demo-requests` is deliberately **unfiltered** so the screen's
own status counts cannot lie. `POST /marketing/demo-requests` is the only
public write on the platform surface (the marketing site's lead form).

---

## 3. Setup, master data & onboarding

| Feature | ID | Services | API | Web | Who |
|---|---|---|---|---|---|
| Academic years, terms, tracking start | `setup.years` | `academics.py` | `/academics/years`, `/academics/terms` | `/setup` | admin writes · all read |
| Classes, sections, subjects, class-subjects | `setup.structure` | `academics.py` | `/academics/classes`, `/subjects`, `/class-subjects` | `/setup` | admin writes · all read |
| Teacher allocation to class-subjects | `setup.allocation` | `academics.py` | `/academics/classes/{id}/allocation` | `/setup` | admin |
| Members: invite, roles, bulk import | `setup.members` | `member.py`, `org.py`, `staff_import.py` | `/org/members*` | `/setup/members` | admin |
| Org settings (timings, policies, state/board) | `setup.settings` | `org.py` | `/org/settings` | `/setup/settings` | admin writes · all read |
| Guided 9-step setup wizard | `setup.wizard` | `wizard.py` | `/wizard/*` | `/setup/wizard` | **operator only** |
| Student directory + guardians | `students.directory` | `students.py`, `roster_import.py` | `/students*` | `/students/directory` | admin writes · teacher reads own |
| Skill areas, student categories | `setup.taxonomy` | `assessments.py`, `students.py` | `/assessments/skill-areas`, `/students/categories` | `/setup` | admin |

Wizard progress is **derived from the real tables**, write-through — there is no
parallel store that can disagree with what was actually created.

---

## 4. Planning

| Feature | ID | Services | API | Web | Who |
|---|---|---|---|---|---|
| Year calendar, holidays, working days | `plan.calendar` | `calendar.py` | `/academics/calendar/*` | `/plan` (Year) | admin writes · all read |
| Syllabus units & topics (+ xlsx/text import) | `plan.syllabus` | `syllabus_import.py`, `planner.py` | `/planner/syllabus*` | `/plan/syllabus` | admin writes · subject teacher edits own |
| The chapter board (class × subject × term) | `plan.board` | `syllabus_board.py`, `coverage.py` | `/planner/syllabus/board` | `/plan/syllabus` | admin = school · teacher = own subjects |
| Plan draft / generate / approve / extend | `plan.plans` | `planner.py`, `plan_validate.py` | `/planner/plan/{cs}/*` | `/plan/week` | admin approves · teacher comments |
| Teacher's own plan + reschedule | `plan.my_subjects` | `my_syllabus.py`, `plan_schedule.py` | `/planner/my-subjects`, `PUT /plan/{cs}/schedule` | `/plan/my-subjects` | teacher (own only) |
| Timetable grid, clash validation, import | `plan.timetable` | `timetable.py` | `/timetable/*` | `/plan/timetable` | admin writes · teacher reads own week |
| Exam calendar & portion mapping | `plan.exams` | `main_exams.py`, `exam_map.py` | `/main-exams`, `/planner/exam-map` | `/plan/exams` | admin writes · teacher reads |
| Hostel session blocks | `plan.hostel` | `sessions.py` | `/sessions` | `/plan/hostel` | admin creates · teacher runs |

**P2 — the plan is the baseline, the log is the actual.** The approved plan is
locked; re-forecast is *computed* from baseline + logs + remaining effective
periods, never stored as mutated plan rows. `plan_entries.baseline_week_start`
is frozen at approve so a teacher rescheduling her own chapters can never move
the promise she is measured against.

---

## 5. Daily capture — the teacher's loop

Everything here obeys **P1v2 (capture by exception)**: confirm the norm in one
tap, record only deviations. Budgets: quick-log ≤ 3 taps / 25s; period card
≤ 5 taps / 30s; a 15-student session ≤ 60s.

| Feature | ID | Services | API | Web | Who |
|---|---|---|---|---|---|
| My Day (today's periods + evening) | `capture.my_day` | `classroom.py` | `/classroom/my-day` | `/my-day` | teacher |
| Period card (the capture surface) | `capture.period` | `periods.py`, `classroom.py` | `/periods/card`, `/periods/*` | `/my-day/period/[classId]/[no]` | teacher of that class |
| Attendance (register + exceptions) | `capture.attendance` | `attendance.py` | `/attendance/*` | `/attendance`, `/attendance/[classId]` | any teacher of the class |
| Lesson log + topic coverage | `capture.lesson_log` | `classroom.py` | `/classroom/lesson-logs` | period card | subject teacher |
| Deep log / observations (per student) | `capture.observations` | `classroom.py` | `/classroom/observations` | period card | subject teacher |
| Class log (deliberate per-student note) | `capture.class_log` | `student_records.py` | `/classroom/class-log` | `/students/academics/class-logs` | teacher |
| Homework: assign, check, verdicts | `capture.homework` | `classroom.py`, `homework.py` | `/classroom/homework*`, `/homework/*` | `/homework` | teacher · admin sees overview |
| Daily checks (recommendations) | `capture.checks` | `recommendations.py` | `/checks`, `/checks/{id}/confirm` | period card | teacher |
| Hostel session capture (study/homework/activity) | `capture.sessions` | `sessions.py` | `/sessions/meetings/*` | `/sessions/[id]` | assigned teacher |

**Attendance is once per day, not once per period** (`D-91`). `mark` lands on
the day's existing register wherever it was taken, and `roster` reads the same
one — otherwise period 5 shows a blank sheet and saves it over the morning's
absences. The first marked period of the day is the only one that alerts
guardians.

**`not_checked` is not zero.** A `homework_checks` row means the teacher went
through it; its absence means nobody has, which is the *teacher's* gap and may
never render as a child's miss — parent surfaces included.

---

## 6. The record the school makes

| Feature | ID | Services | API | Web | Who |
|---|---|---|---|---|---|
| Student growth report | `record.growth` | `growth.py` | `/students/{id}/growth` | `/students/[id]` | admin all · teacher own students |
| Student timeline (computed join) | `record.timeline` | `timeline.py` | `/students/{id}/timeline` | `/students/[id]` | admin · teacher own |
| Report card (numbers) + analysis | `record.report_card` | `report_card.py`, `exam_analysis.py` | `/students/{id}/report-card`, `/analysis` | `/students/[id]` | admin · teacher own |
| Class academics roster | `record.academics` | `student_records.py` | `/students/records` | `/students/academics` | admin all · teacher own |
| Exams: capture, scripts, verify & lock | `exam.capture` | `exams.py`, `score_capture.py`, `score_match.py` | `/assessments/exams*`, `/captures/*` | `/students/academics/exams` | subject teacher · admin unlocks |
| Exam types (school's own vocabulary) | `exam.types` | `exam_types.py` | `/assessments/exam-types` | `/setup/settings` | admin |
| Exam report (distribution, questions) | `exam.report` | `exam_report.py` | `/assessments/exams/{id}/report` | exam page | teacher |
| Class analytics & trends | `record.analytics` | `analytics.py` | `/assessments/classes/{id}/trends`, `/analysis` | `/students/academics/analytics` | teacher · admin |
| Student notes (class teacher's log) | `record.notes` | `my_class.py` | `/my-class/students/{id}/notes` | `/students/[id]` | class teacher + admin write · wider read |

**Minor and major exams never pool** (`core/exams.py`). `ScaleTally` has no
method returning a blended number, so a caller who wants one must write the
addition where a reviewer can see it. A locked exam is the record: both
`ExamService.save` and `AssessmentService.save_scores` refuse it.

---

## 7. Programmes, staff, money and the boards

### 7.1 ABC bands / the support programme

| Feature | ID | API | Web | Who |
|---|---|---|---|---|
| Band distribution & programme board | `bands.board` | `/bands/distribution`, `/bands/programme` | `/bands` | admin |
| File / assess bands per class | `bands.assess` | `/bands/class`, `/bands/class/file` | `/bands/manage` | teacher of a **monitored** class-subject |
| Promote a locked exam to a band test | `bands.promote` | `/bands/promote/{cycle_id}` | exam page | teacher (guard is `locked`, not role) |
| Owner allocation | `bands.allocation` | `/bands/allocation*`, `/bands/owner` | `/bands/allocation` | admin |
| My students + weekly check-in | `bands.support` | `/bands/my-students`, `/bands/support/*` | `/bands/my-students`, `/support/[id]` | band owner |
| Support assessments (marks/rating/other) | `bands.assessments` | `/bands/assessments*` | `/bands/assessments` | band owner |
| Descriptors & monitored subjects | `bands.setup` | `/bands/setup*` | `/setup/settings` | admin |

**The band is per subject; there is no overall letter** (`D-75`). Rows with
`subject_id IS NULL` are the retired letter — kept as history, read by nothing.
The chip never renders without its sentence.

### 7.2 Staff

| Feature | ID | Services | API | Web | Who |
|---|---|---|---|---|---|
| Staff attendance (admin-marked, exception-shaped) | `staff.attendance` | `staff_attendance.py` | `/staff/attendance` | `/staff` | admin |
| Staff directory & profiles | `staff.directory` | `staff_directory.py` | `/staff/directory*` | `/staff/directory` | admin writes · member reads own |
| Timesheet (non-teaching periods) | `staff.timesheet` | `timesheet.py` | `/staff/timesheet/*` | `/timesheet` | teacher own · admin `today` |
| Leave: apply, approve, balance, policy | `staff.leave` | `leave.py` | `/staff/leave*` | `/staff/leave`, `/timesheet/leave` | member applies · admin decides |
| Month summary (days worked / leave left) | `staff.month` | `staff_month.py` | `/staff/month` | `/staff/month` | member own · admin all |
| Substitutions / cover | `staff.cover` | `substitution.py` | `/insights/substitutions*` | `/staff/today` | admin |
| Personal record (day, month, categories) | `staff.record` | `staff_record.py` | `/insights/staff/{id}/record` | `/staff/member/[id]` | member own · admin all |

🔴 **It is a record, not an appraisal, and that is enforced** (`D-25`/`S-67`):
no score, no rank, no completeness percentage, no path to pay. The AI summary's
prompt forbids appraisal language *in the negative*, and the suite greps the
payload for it.

### 7.3 Fees — admin only

`fees.collection` · `fees.structures` · `fees.ledger` · `fees.reminders` ·
`fees.notes` — all `require_office_up`, all under `/fees`, web at `/fees`,
`/fees/[id]`, `/fees/structures`.

`CollectionService.board()` is the one computation every fee screen renders.
`Collection` deliberately has **no `outstanding` property**: pending is a
forecast, overdue is a phone call, and the blend has no name. Years never pool
— `opening_dues` is its own labelled line outside this year's totals.

### 7.4 Tasks, boards & Lucy

| Feature | ID | API | Web | Who |
|---|---|---|---|---|
| Boards, tasks, event-sourced state | `tasks.core` | `/boards*`, `/tasks*`, `/me/*` | `/tasks`, `/boards/[id]` | any member |
| Recurring templates | `tasks.recurring` | `/recurring*` | `/recurring/[id]` | any member |
| Lucy (staff agent chat) | `lucy.chat` | `/lucy/*` | `/lucy` | any member (role-filtered tools) |

**Law 5:** admins do **not** see private boards they aren't members of.
Visibility is centralised in `core/visibility.py`; endpoints never inline it.

### 7.5 Admin insights & reporting

`/dashboard` is a 7-tab area, all `require_admin`, served by
`services/insights/` (`overview`, `presence`, `attendance`, `syllabus`,
`homework`, `exams`, `workload`, `daybook`, `tasks`, `bands`, `reach`,
`actions`) plus `daily_report.py`.

IDs: `insights.overview` · `insights.presence` · `insights.attendance` ·
`insights.syllabus` · `insights.homework` · `insights.exams` ·
`insights.staff` · `insights.tasks` · `insights.actions` · `report.daily`.

Every insights service **composes** existing module roll-ups rather than
recomputing. That is what makes the overview block and the tab it links to
incapable of disagreeing.

### 7.6 Events & calendar

`events.whats_on` (`/events/whats-on`, `require_academic`) ·
`events.suggestions` / `events.cost` (admin) — the observance corpus scoped by
the school's `state` + `board`.

### 7.7 Parent portal — read-only

| Feature | ID | API | Web |
|---|---|---|---|
| Login: code → class → section → child → DOB | `parent.auth` | `/parent/auth/*` (public) | `/parent/login` |
| OTP recovery path | `parent.otp` | `/parent/auth/request-otp`, `/verify-otp` | `/parent/login/otp` |
| Today, progress, report | `parent.child` | `/parent/children/{id}/today`, `/report` | `/parent` |
| School calendar | `parent.calendar` | `/parent/children/{id}/calendar` | `/parent/calendar` |
| Notifications inbox | `parent.notifications` | `/parent/notifications` | `/parent/notifications` |

A parent is a `User` with **no membership**; the session carries `role="parent"`
and revocation is the live guardian-link check. Everything they see goes
through the curated allowlist projection. **The only write a parent makes is
marking a notification read** — session bookkeeping, never content. No replies:
a notification a parent can answer is a messaging product.

---

## 8. The MCP surface

> This section is the summary of **what exists today**. The agreed design — one shared
> tool pool behind both Lucy and MCP, the ~95 read + ~75 write target catalogue, the
> change-set approval engine, PAT credentials and the fences — lives in
> [`MCP-SERVER-PLAN.md`](MCP-SERVER-PLAN.md). ⚠️ Its `D-96` supersedes the "add read
> tools freely… that gap is a choice, not a backlog" framing below: the gap is now a
> **backlog**, and safety comes from scoped toolsets plus human approval of every
> write, not from omission.

`api/app/services/lucy/registry.py` is explicitly built as the MCP seed —
"transport-agnostic: a `ToolSpec` knows nothing about FastAPI, SSE or widgets,
so the same registry can later back an MCP server 1:1".

**42 tools today — 36 read, 6 write.** All 6 writes carry `confirm=True`: the
agent files a `lucy_pending_actions` row and a human confirms before the
service write runs.

| Role | Read | Write |
|---|---|---|
| `academic` | 22 | 6 (`mark_attendance`, `log_lesson`, `assign_homework`, `confirm_check`, `create_task`, `add_plan_comment`) |
| `admin` | 14 | 0 |

The three rules that make the registry safe, and which an MCP server must keep:

1. **Tools wrap services, never tables.** Every handler calls a real service
   method with the real `CurrentMember`, so org scoping (law 1), teacher
   scoping (`not_your_student` / `not_your_class`) and the fee fence ride along
   for free.
2. **Role filtering happens at schema time.** A teacher's model never sees the
   admin-only tools — cheaper than erroring and nothing to jailbreak.
3. **Business errors return to the model as data.** An `AppError` becomes a
   tool result the model can correct course on; only genuine bugs propagate.

### The gap, stated honestly

42 tools against ~420 routes. The uncovered areas are, roughly: fees beyond
`get_fee_collection`, staff/leave/timesheet, the parent portal, events, wizard
and all platform routes. **That gap is a choice, not a backlog** — each new
tool widens what an agent can do unsupervised. When adding tools:

- Add read tools freely; they inherit scoping from the service.
- Every write tool must be `confirm=True`. There is no second pattern.
- Never add a tool that reaches a table directly.
- The fee fence is asserted by a word-boundary regex over the whole teacher
  tool surface, not by tool name — renaming will not silently retire it.

---

## 9. Package tiers — what exists and what does not

### What exists today

`api/app/core/plans.py` implements a **two-tier Free/Pro** model inherited from
the `task_management2` seed. It is real, wired and enforced — but it predates
every school module:

```python
FREE = PlanLimits(boards=2, members=8, report_days=14,
                  report_card=False, attachments=False, critical=False)
PRO  = PlanLimits(boards=None, members=None, report_days=365,
                  report_card=True, attachments=True, critical=True)
```

- `organizations.plan` — `CHECK (plan IN ('free', 'pro'))`
- `organizations.plan_status` — `CHECK (plan_status IN ('none','active','grace'))`
- `services/billing.py` — Razorpay, ₹500/month flat per org, webhook-driven,
  stub mode without keys
- Enforcement points: `enforce_board_quota`, `enforce_member_quota`,
  `enforce_critical_allowed`, `enforce_attachments_allowed`, plus
  `jobs.py:210` and `services/org.py:49`

### What a basic/gold/platinum move actually requires

Recorded so next session starts from facts rather than a survey:

1. **A migration.** `plan_valid` is a CHECK constraint — three new tier names
   cannot be written until it is widened. `plan_status_valid` likely too.
2. **`PlanLimits` knows nothing about school features.** Its six fields are
   task-management concepts. Every ID in §2–§7 of this file is a candidate
   field, and the dataclass is the natural place for them.
3. **Enforcement is only at four call sites.** There is no general "is this
   feature enabled for this org" helper and no route-level or nav-level gate.
   Both the API and the sidebar would need one.
4. **`PlanLimitError` already exists** and the UI turns it into an upgrade
   prompt — "every breach raises a structured `PlanLimitError` the UI turns
   into an upgrade prompt, never a silent failure". Keep that contract: a
   gated feature must fail loudly with the tier that would unlock it.
5. **The pricing in `CLAUDE.md` and the pricing in the code disagree.**
   Marketing says ₹100/student/month with a 500-student minimum; `billing.py`
   charges ₹500/month flat per org. One of them is wrong and it should be
   settled before tiers are built on top.
6. **Lucy tools need the same gate.** A tool is a door into a service. If
   `insights.exams` is platinum-only, `get_exams_board` must be filtered out of
   the tool schema for a basic org — at schema time, like the role filter, not
   by erroring.
7. **Do not gate the core loop.** The current design paywalls breadth and
   premium surfaces, never capture. Attendance, the lesson log and homework are
   what make the data exist at all; a school that stops capturing has nothing
   to upgrade *for*.

### Feature IDs

The IDs in §2–§7 (`plan.syllabus`, `capture.attendance`, `insights.presence`,
`fees.collection`, …) are proposed as the stable vocabulary a tier definition
would reference. They are **documentation only today** — nothing in the code
reads them yet. If they become real, they belong in one module
(`core/features.py`) beside `PlanLimits`, so a tier, a nav gate and a Lucy tool
filter all name a feature the same way.

---

## 10. Frontend map

```
web/src/
  app/(app)/      the staff shell — role-guarded, sidebar + tabs
  app/parent/     the parent portal — its own mobile-first shell, no staff nav
  app/(wizard)/   the operator's setup wizard
  app/auth/       login, register, password reset · join/[token] · reset/[token]
  components/     21 domains (school, insights, students, staff, parent, charts, ui, …)
  lib/            typed API clients + shared computation
```

Load-bearing frontend rules, each of which has already been broken once:

- **`components/charts/` is the one chart kit.** `palette.ts` is validated for
  CVD and both themes. There is no second charting path and no hand-picked hex.
- **`lib/format.ts` owns calendar dates** — `dayKey`, `todayKey`, `shiftDay`,
  `shiftMonth`, `thisMonth`. Never serialise a local-midnight `Date` through
  `toISOString()`: east of UTC it returns the previous day, which broke day
  navigation, cover sheets and absence reasons in four separate files.
- **Theme is the `.dark` class, not `prefers-color-scheme`.** Review in both.
- **Percentages are divided server-side.** Two of the five historical
  definitions of "syllabus covered" were `.reduce()` calls in React, which no
  test could catch.
- **Nav is `components/layout/nav-items.ts`** — `navForRole` /
  `bottomNavForRole` / `menuNavForRole` / `landingForRole`, branching on role
  plus `is_class_teacher` and `has_band_scope`.

`web/CLAUDE.md` → `web/AGENTS.md` carries a standing warning: this Next.js
version has breaking changes from training data — read
`node_modules/next/dist/docs/` before writing framework code.

---

## 11. Known gaps

Carried forward so they are not rediscovered:

- **~31 GET routes have no web caller.** Three groups: not web surfaces
  (`/billing/webhook`, `/ops/*`); reached through Lucy (whose tools call the
  service, not the route); and genuinely superseded, which should be deleted
  but are each covered by a test. See `docs/v1/PROGRESS.md`.
- 🔴 **`topic_progress` in `services/planner.py` is a sixth coverage
  definition** — it decides done/in-progress/pending on its own rules instead
  of `core/coverage.py`. Fix before the MCP server widens its reach.

  ⚠️ **Corrected 2026-08-07 — this entry used to say "No screen calls it; Lucy
  does". That is wrong, and the fix is bigger than it implied.** Verified
  callers: `endpoints/planner.py:242` (the route), **`services/classroom.py:816`
  — the period card**, and Lucy's `get_topic_progress`. Its status words are
  baked into `web/src/lib/school-types.ts:1306` and `:1584`, and
  `tests/test_periods.py:236` asserts `{"done", "in_progress", "pending"}`
  exactly.

  🔴 **And there is a second, duplicated copy of it.** `services/growth.py:179`
  (`topic_row`) computes topic status again, with byte-for-byte the same rule —
  `done` if any full log, else `in_progress` if any log, else `pending` — and no
  import of `core/coverage.py`. It feeds the growth report **and the parent
  report** (`GrowthTopic` → `ParentTopic` in `web/src/lib/parent-api.ts:128`,
  rendered at `web/src/app/parent/(portal)/report/page.tsx:13`).

  *(An earlier draft of this entry blamed `services/parent_portal.py`. That was
  wrong — `parent_portal.py`'s own coverage figures already come from
  `core.coverage`; it is `growth.py` the parent report borrows the topic rows
  from.)*

  The real defect in both is not the wording — it is that **neither has a
  `not_scheduled` state**, so a topic nobody ever planned renders as *pending*.
  That is exactly what `CHAPTER_NOT_SCHEDULED` exists to prevent, and on the
  parent surface it is `S-54`: the school reads as behind on work it never
  promised. `core/coverage.py::chapter_status(topics=1, …)` is the fix for a
  single topic — a group of one — but adding the fourth state changes a union
  the **parent portal** renders, so this is a cross-stack packet, not a
  contained service fix.
- 🔴 **Production runs as `doadmin`** (`rolbypassrls = true`), so law 2 is
  decorative in the one environment that matters.
  `scripts/provision_app_role.py` exists; the swap is the last v1 release item.
- **`PATCH /fees/installments/{id}/due-date`** has no web caller, though it is
  the only way to resolve an `unscheduled` instalment.
