# TrackBit School — SPRD v2.0 — "The School's Daily OS"

July 2026 · Supersedes SPRD v1.0 where they conflict; v1 remains the reference for carried
modules (fees §4.6/§5.6, tasks §5.5, assessments §5.3, sessions, master data §4.2).
Cite as `SPRD2 §x.y`. Conflict order: **SPRD2 > architecture doc v1.1 > SPRD v1** (the v2
redesign is an explicit founder decision, including the fence changes in §11).

> **Status at time of writing:** phases P0–P3 of SPRD v1 are complete (162 backend tests).
> Packet **V2-P0-A (roles) is ALREADY DONE** — see §2. Start at V2-P0-B.

---

## §0. How to use this document

1. Work packet-by-packet (§10) with the same Done-when discipline as v1 (§0 of SPRD v1):
   backend green = `uv run pytest -q` + ruff; frontend green = tsc + eslint + `next build`.
2. The six architectural laws in `CLAUDE.md` are unchanged and binding for every new table
   (org_id from token, RLS, append-only history, template/instance, central visibility,
   thin endpoints / fat services).
3. Product principles P2–P5 are unchanged. **P1 is restated for v2:**

   **P1v2 — One-minute budget via capture-by-exception.** The teacher confirms the norm in
   one tap and records only deviations. Attendance = "all present" minus tapped absentees.
   Checks = "class did it" minus tapped exceptions. Any feature requiring per-student entry
   for the whole class is mis-designed — redesign or cut.

## §1. Vision v2

TrackBit is **the school's daily operating system**: it plans the academic year down to the
period, captures each day with near-zero teacher effort, knows what every student is doing
during school + hostel hours, and writes the school's reports itself.

The core loop v2: **Wizard compiles the year (plan + timetable) → teachers confirm each
period by exception (attendance · topic · checks · homework) → the system joins it into
per-student, per-class, per-subject truth → the daily report tells the admin what needs
attention at 8:00 AM → detected gaps become tasks.**

Positioning change (deliberate, founder-decided): v1 said "we sit beside your ERP." v2 says
"this is how your school runs every day." The remaining fences (§11) matter more, not less.

## §2. Roles v2 — ✅ IMPLEMENTED (do not redo)

Two roles only (migration `e9fab0c1d2e3_two_roles`, applied):

| Role | Who | Can |
|---|---|---|
| `admin` | whoever registers the org + anyone they promote (principal, coordinator-type staff, accountant) | everything: setup/wizard, plan edit+approve, timetable, bands, fees, dashboard/reports, members |
| `teacher` | all academic staff incl. wardens | My Day capture, sessions, view plans/timetable, students of their classes, tasks |

What was done in V2-P0-A (reference for agents; all green):
- `core/roles.py`: role set = admin|teacher; groups `COORDINATOR_UP`/`OFFICE_UP` → {admin},
  `ACADEMIC` → {admin, teacher}. Group names kept so ~30 endpoint guards didn't churn —
  `require_coordinator_up` / `require_office_up` are now **admin-only aliases**; consolidate
  to `require_admin` opportunistically when touching a file, never in a bulk rename.
- `models/org.py` CHECK + migration (data remap coordinator/office → admin), seed, tests
  (162 passing), web `types.ts` (`OrgRole`), nav, all 13 page guards. Role labels: "Admin"/"Teacher".
- Hard rules kept: teachers never see fees; bands never reach guardians (P4).

## §3. Information architecture v2 (fixes "scattered")

**Teacher sidebar (5):** `My Day` (landing) · `Sessions` · `Plan` · `Students` · `Tasks`.
**Admin sidebar (6+1):** `Dashboard` (landing) · `Plan` · `Students` · `Fees` · `Tasks` · `Setup` (· `Members` lives inside Setup).

Consolidations from v1 (V2-P0-B):
- `Home` + `Boards` + `Done` → one **Tasks** item (internal tabs: Today / Boards / Done).
- `Planner` + `planner/plan` + syllabus + timetable → one **Plan** area (tabs: Year · Syllabus · Week plan · Timetable).
- `Setup` absorbs `/academics`, skill areas, `Members`, org settings, and hosts the **wizard**.
- `Assessments` moves under **Students** (tabs: Directory · Scores · Bands · Trends) — the
  admin thinks "students", not "assessment cycles".
- `/insights` becomes **Dashboard**; `/classroom` becomes **My Day**; `classroom/compliance`
  page dies — compliance lives inside the daily report + Dashboard.

Mobile bottom tabs = the same five (teacher) / first five (admin).

## §4. Domain model deltas (all org-scoped + RLS + laws 1–3)

- **Timetable:** `timetable_slots` — class_id, weekday (0–6), period_no, class_subject_id,
  effective_from (date), effective_to (date, null = current). Editing mid-year closes the old
  row and opens a new one (append, never overwrite — history keeps old joins truthful).
  Period timing config on `academic_years`: `periods_per_day`, `period_times` (JSON list of
  HH:MM start/end incl. breaks).
- **Attendance (capture-by-exception):** `attendance_marks` — class_id, date, period_no,
  class_subject_id?, marked_by_member_id, marked_at. One row per class-period actually taken.
  `attendance_exceptions` — mark_id, student_id, status (`absent` | `late`), late_minutes?.
  Present = on the roster of a marked period, minus exceptions. **No per-student present rows.**
- **Daily checks (recommendations):** `daily_checks` — class_subject_id, date, description,
  source (`ai` | `teacher`), band_scope (`all` | `C` | `B`...). `check_results` — check_id,
  student_id, status (`not_done` | `note`), note?. **Exception rows only**; "class did it" is
  the check row itself, confirmed via `confirmed_at`/`confirmed_by` on `daily_checks`.
- **Per-student homework:** `homework_assignments.student_id` (nullable FK; null = whole class).
- **Wizard:** `onboarding_state` — org_id (unique), current_step, payload (JSON per-step
  answers/extractions), status (`in_progress` | `done`). Resumable; wizard WRITES THROUGH to
  the real tables at each confirmed step (no parallel store).
- **Daily report:** `daily_reports` — org_id, for_date (unique together), generated_at,
  content_md, highlights (JSON: risks/ambiguities/wins), status (`draft` | `final`).
  Regeneration replaces a `draft`, never a `final` the admin has annotated.
- **Student timeline: NO TABLE.** It is a computed join: timetable_slots × attendance ×
  lesson_logs × sessions × homework/checks → "what was student S doing period-by-period".

## §5. Module specs v2

### §5.1 V2-M1 — Setup Wizard & smart ingestion (admin)

Steps (each: ask → (optionally) upload doc → AI extracts → human confirms → write-through):
1. Academic year: start/end, working weekdays, terms.
2. Exam calendar: term exams, major exam blocks, recurring patterns ("chapter-end test every
   Friday" → recurring calendar rule).
3. School timings: periods/day + period times (+ breaks).
4. Classes & subjects: list classes/sections; subjects per class. Upload accepted: any doc.
5. Syllabus: per class-subject chapters→topics. Upload accepted: syllabus PDF/doc/photo.
6. Teachers: names/phones/roles + subject assignments. Upload accepted: staff list.
7. Students: roster + guardians. Upload accepted: xlsx/CSV/photo (extends P0-C importer).
8. Timetable: **import-first** — photo/xlsx of the existing timetable → parsed grid → confirm;
   or "draft one for me" (§5.3). 
9. Generate the year plan (§5.2) → review → lock. **Wizard complete.**

Done-when: a fresh org reaches a locked plan without ever visiting a module screen; every
step is resumable after logout; every extraction lands in a confirm surface before persisting;
skipping any upload and typing manually always works.

### §5.2 V2-M2 — Plan generation pipeline (the agentic system)

Levels generated: **chapter→month** (per class-subject), **topic→week**, and (with §5.3)
**period-aware teacher plan**. Pipeline (all AI drafts, never AI-approves):

```
proposer (LLM: syllabus + effective days + periods/wk + exam calendar)
   → deterministic validators (code, not LLM):
       V1 capacity: Σ est_periods ≤ effective periods per week/term
       V2 coverage: every topic placed exactly once, exam-block weeks respected
       V3 ordering: unit/topic order preserved
       V4 (with timetable) teacher load: no week where a teacher's plan exceeds her slots
   → repair loop (violations fed back to proposer, max N iterations)
   → human review board (drag-adjust; teacher change-requests: "chapter 4 needs more days"
     as comment threads on plan entries, admin applies manually or clicks "ask AI to adjust")
   → admin approves → baseline locked (P2 unchanged: forecast is computed, never mutated)
```

Done-when: validators have unit tests each; a syllabus that cannot fit (over capacity) is
reported as a human decision ("trim topics or add periods"), never silently squeezed; teacher
change-request → adjust → re-approve round-trip works.

### §5.3 V2-M3 — Timetable (fence moved: import-first, assisted draft)

- Grid editor per class (weekday × period), assign class_subject; conflicts highlighted live.
- **Import**: photo/xlsx → `timetable_parse` AI → confirm grid.
- **Assisted draft**: proposer LLM + deterministic validators (teacher clash, periods/week
  satisfied, subject spacing) + repair loop → ~90% grid, admin finishes by drag. NOT a
  guaranteed solver; "could not satisfy" is a legitimate output listing the conflicts.
- Effective-dated edits mid-year (§4). Teacher view: her own week grid.

Done-when: clash validator provably rejects a teacher in two places; a real school timetable
photo imports to ≥90% correct cells; My Day (§5.4) renders from timetable_slots.

### §5.4 V2-M4 — My Day v2 (the teacher product)

One screen: today as a **timeline of period cards** from the timetable (+ her sessions).
Period card anatomy (top→bottom, one thumb-flow):
1. **Attendance**: "All present ✓" one tap; or tap students → absent/late+minutes (exceptions).
   First marked period of the day triggers guardian absence alerts (§7).
2. **Topic**: planned topic pre-filled → "Covered ✓" / partial / different (unchanged from CL-2).
3. **Checks**: today's recommended checks (§5.5) → "Class did it ✓" one tap → tap exceptions.
4. **Homework**: class homework (text/voice/photo) + optional per-student additions.
Budget: routine period ≤ 5 taps / ≤ 30s. Sessions keep SS-2 capture, now with the same
exception-attendance component.

Done-when: the 4-step card is operable one-handed at 360px; every step optional except
attendance-or-skip; a fully-confirmed day writes: 1 attendance_mark + exceptions, 1 lesson_log,
confirmed daily_checks + exceptions, homework rows — verified by an end-to-end test.

### §5.5 V2-M5 — Recommendations engine

Nightly job (+ on plan/band change): for each class-subject×tomorrow, generate `daily_checks`
from (planned topic × band distribution): e.g. topic "Fractions intro" → all: "5 practice
sums checked"; C-band: "one-on-one: reads the worked example aloud". AI-drafted, deterministic
fallback templates when AI is off. Teacher sees them on the period card; admin can edit
templates in Setup. Interventions (v1 §5.3) now consume these instead of hand-written checklists.

Done-when: checks appear on My Day with zero teacher setup; C-band students get the richer
check; volume capped (≤2 class-wide + ≤1 per intervention student per period).

### §5.6 V2-M6 — Daily report agent

19:00 org-local: assemble the day — attendance anomalies (absences, repeat absentees, unmarked
periods), unlogged classes, plan deviations/pace, homework given/checked, session records,
check exceptions, fee collections (admin section only) — deterministic aggregation first, then
`report_write` AI turns it into a short narrative + flagged **risks/ambiguities** ("6-B had no
Science log but had an attendance mark — was the period held?"). Stored in `daily_reports`.
06:00: regenerate if late data arrived (draft only). 08:00 surface: Dashboard leads with it +
WhatsApp/email summary to admins.

Done-when: report renders from seed data with ≥3 sections; ambiguity rules have unit tests
(attendance-without-log, log-without-attendance, plan-red streaks, repeat absentee ≥3 days);
job is idempotent + org-TZ correct like existing jobs; AI-off mode still produces the
deterministic report.

### §5.7 V2-M7 — Student timeline & tracking

Student profile gains **Timeline**: day/week view assembled from the §4 join — period-by-period
what the student did (subject, topic, present/late, checks, homework, sessions incl. hostel).
Class view: syllabus completion % vs plan (existing forecast, surfaced per class on Dashboard).
Bands (existing M3) + timeline + checks history = the per-student progress story.

Done-when: timeline for a seeded student renders school+session hours with zero new capture
tables; absent periods show as gaps; loads < 2s.

### §5.8 Carried modules (unchanged specs, new homes)

Fees (v1 §5.6; admin-only now) · Tasks (v1 §5.5; + report/check integrations) · Assessments &
Bands (v1 §5.3; admin marks-image intake stays; lives under Students) · Sessions (v1 §5.2;
hostel/evening blocks are sessions — wardens are teachers) · Guardian notifications (§7).

## §6. UX notes for the shell (V2-P0-B)

Existing design tokens stay. New components: `PeriodCard`, `ExceptionPicker` (roster grid,
tap-to-toggle), `TimetableGrid` (editor + read views), `WizardFrame` (steps, progress,
resume), `ReportView` (daily report with expandable sections). Kill: compliance page, insights
naming, separate Home/Boards/Done nav. Every landing is role-aware: teacher → My Day,
admin → Dashboard (leads with today's/yesterday's report).

## §7. Notifications v2 (channel-adapter unchanged; WhatsApp stub until keys)

| Trigger | To | When |
|---|---|---|
| **Absence** (student absent in first marked period; no later mark flips it) | guardians | immediate |
| Homework logged (class or per-student) | guardians | immediate |
| Daily report ready | admins | 08:00 |
| Unmarked/unlogged classes | the teacher | 16:00 |
| Saturday guardian summary (homework + attendance week) | guardians | Sat |
| Fee events / task notifications | as v1 | unchanged |

Cron wiring for ALL jobs (incl. v1's deferred ones) lands in V2-P4. P4 privacy rule unchanged:
bands never appear in any guardian message.

## §8. AI services v2 (extend `services/ai/`, same env-gated fixture-stub pattern)

`doc_ingest` (any wizard upload → structured fields; per-step schemas) · `timetable_parse`
(photo/xlsx → grid) · `timetable_draft` (+ validators/repair) · `plan_generate` (replaces v1
plan_draft; multi-level) · `checks_generate` · `report_write`. Models via env as v1 §8;
drafting = sonnet-class, parsing = haiku-class. Every output → confirm surface. No chat UI.

## §9. Explicitly finish (v1 debt folded into v2)

Cron wiring (16:00 reminder, Sat summary, daily report replaces Monday-digest delivery — keep
digest builder as the report's weekly rollup) · fees-mode xlsx import (fold into wizard step 7
as optional "import fee history") · PL-6 day suggestions (unchanged spec, lands with wizard
calendar step or V2-P5, low priority) · DB-3 growth profile stays v-next.

## §10. Packets

| Packet | Scope | Done-when highlight |
|---|---|---|
| **V2-P0-A** ✅ | Roles admin/teacher (§2) | DONE — 162 tests green, migration applied |
| **V2-P0-B** | IA reshell (§3, §6): nav consolidation, Tasks/Plan/Students grouping, route renames (`/insights`→`/dashboard`, `/classroom`→`/my-day`, `/academics`→`/setup`), kill compliance page | both role sidebars match §3; all old routes redirect; build green |
| **V2-P1** | Timetable (§5.3): model + grid editor + import + validators (+ assisted draft behind a flag) | clash tests; My Day reads timetable |
| **V2-P2** | Attendance + absence alerts + My Day v2 timeline (§5.4, §7) | period-card e2e test; exception model only |
| **V2-P3** | Recommendations + daily checks + per-student homework (§5.5) | checks on card, C-band richer, caps enforced |
| **V2-P4** | Daily report agent (§5.6) + student timeline (§5.7) + **cron wiring for all jobs** (§9) | 8AM report on dashboard; ambiguity unit tests; timeline from join |
| **V2-P5** | Wizard + smart ingestion + plan generation pipeline (§5.1, §5.2) | fresh org → locked plan, no module screens |

Sequencing: P1 before P2 (attendance hangs off periods); wizard last (it writes into
everything the earlier packets build). Teacher-facing regression gate: after every packet,
the v1 flows (quick log, sessions, fees, tasks) still pass their tests.

## §11. Fences v2 (binding; updates architecture doc v1.1 §8)

**Moved IN (founder decision, July 2026):** per-period attendance (capture-by-exception only);
timetable (import-first + assisted draft with deterministic validation — still no guaranteed
solver); daily report generation; per-student homework.

**Still OUT:** payroll/HR/library/transport/inventory/visitor tracking/social media ·
report-card designer · test authoring/conducting · parent app or login (notifications only) ·
chat UI / AI orchestrator surface · mandatory per-student capture (exception-only, always) ·
per-student evidence photos (batch only) · LMS + teacher training (Playground's lane).

## §12. Screen migration map (v1 → v2)

| v1 | v2 |
|---|---|
| `/classroom` (My Day CL-1/2/3) | `/my-day` — period-card timeline (§5.4) |
| `/classroom/compliance` | deleted — daily report + dashboard |
| `/insights` | `/dashboard` — leads with the daily report |
| `/planner`, `/planner/plan` | `/plan` tabs: Year · Syllabus · Week plan · Timetable |
| `/academics` | `/setup` (+ wizard, + members, + org settings) |
| `/assessments` | `/students` tabs: Directory · Scores · Bands · Trends |
| `/home`, `/boards`, `/done` | `/tasks` tabs: Today · Boards · Done |
| `/students` | `/students` (Directory tab) + Timeline on profile |
| `/fees/*`, `/sessions/*` | unchanged paths, admin-only / teacher-scoped as before |
