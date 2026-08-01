# v1 build progress

Tracks packet-by-packet progress against `IMPLEMENTATION-PLAN.md` (rev 1, `D-78`–`D-88`).
Updated at the close of every working session. **Read this first when resuming v1 work.**

## Packet status

| Packet | Status | Commit | Notes |
|---|---|---|---|
| **V1-0** · Foundation: one computation | ✅ **DONE** | `c14daf6` | 5 facts unified (day status · partial weight · who-is-free · homework verdict · working days) + defect sweep. Backend 381 passed. Also pre-landed V1-1's FIX items: S-111 client re-filter deleted, S-112 org-local rail due dates, D-47 open-task dedupe. |
| **V1-1** · Tasks & the action rail | ✅ **DONE** | see git log | Migration `e1f2a3b4c5d6` (subject/outcome on task_instances) applied to **prod+dev+test**. D-46 subject+outcome (rail sets it, dedupe keys on it, timeline shows it, complete asks "what happened?") · D-44 board 7-day done window + date filter + hidden count · D-45 stale group (never auto-closed) · D-41/D-43 My Day task window (3 working days ∪ due today, cap 5, older-count footer) · S-106 asked-by. `test_tasks_v1_1.py` (7) + 64 regression green; web tsc/eslint/build clean. |
| **V1-2** · Setup, onboarding & handover | ✅ **DONE** | see git log | Migration `f2a3b4c5d6e7` (school_code + address/state/board + attendance_mode + thresholds + work_categories + handed_over_at + student/staff DOB) applied to **prod+dev+test**, school codes backfilled. Template downloads generated from importers' own fields (round-trip tested) · DOB parser (day-first, never guesses, unresolved reported) · class-teacher picker (D-03) · writable batched by-teacher lens (D-28/S-77) · readiness report + handover (§6 ⑤) · settings: D-01 mode, thresholds, D-19 work categories (stable key/retire-never-delete) · wizard counts partial plans (mid-year). `test_setup_onboarding.py` (7) + 89 regression green; web gates clean. |
| **V1-3** · Attendance + class teacher | ✅ **DONE** | see git log | Migration `a3b4c5d6e7f8` (exception reasons · `student_absence_notes` append-only · `students.enrolled_on` · `organizations.phone`) applied to **prod+dev+test**. D-01 mode drives the marking slots (`school_clock.marking_period_nos`), the heatmap denominator (new `not_expected` cell), My Day / the period card and the 16:00 reminder · D-02/D-86 reason → amber, none → red, computed server-side · S-24 informed absence suppresses the alert · Q-03 `left_after_lunch` is its own state with its own PM alert · D-03 My Class month register + `is_class_teacher` nav signal · S-08 the admin tab as questions (charts behind More) · S-12 one roll-call component (everyone present, "Call the roll" preserved) · S-11/S-25 parent month strip, reason, tel: link. `test_attendance_v1_3.py` (7) + 68 regression green; web tsc/eslint/build clean. |
| **V1-4** · Staff, leave, cover & time | ✅ **DONE** | see git log | Migration `b4c5d6e7f8a9` (`staff_absences.status`/`portion` · `leave_requests.days`→numeric + `is_half_day`/`portion`). D-04 half-day (AM/PM) + late, `present_value` the one day→days-worked function · D-27/S-80/S-81 approve→cover_dates→one sheet per day + the rail item · D-29/S-79 next-planned-topic tier + behind-warning · D-78/S-34 the month summary (`/staff/month`, no money, `not marked` its own count) · D-18/S-64 Day·Week·Month on `/timesheet` · S-75 pre-select-never-write · S-70 her own counters · S-68 hostel evenings beside the periods · D-21/S-66 the slack profile · S-76 the unlogged tile deleted. New: `services/staff_month.py`, `calendar.org_working_days`, `school_clock.periods_before_lunch`/`half_day_periods`. `test_staff_v1_4.py` (11). |
| **V1-5** · Homework | 🟡 **BACKEND DONE, frontend to do** | `8e67390` | Migration `c5d6e7f8a9b0` (`homework_results.status` widened to `late`/`carried`/`waived`) on **dev + test; NOT yet on prod**. Done: `core/homework_verdict.py` (the one vocabulary + arithmetic + `miss_streak`) · D-85 late-as-status + the two derived admin signals (`delayed_teachers`, `rough_classes`) · D-34/S-98/S-102 carried & waived · D-36/S-100 `queue()` + `to_check` · S-85/S-89/S-97 on the sheet · D-37 `daily_load()` · growth + parent-portal readers fixed (S-94/D-35). `test_homework_v1_5.py` (11). **Remaining: the whole frontend** — see the session log. |
| **V1-6** · Syllabus, planning & mid-year | ✅ **DONE** | see git log | **No migration.** `S-51` the one coverage computation — the phrase was computed in **five** places, no two alike (two of them in the browser); `core/coverage.py` now owns the arithmetic + the three named bases and `services/coverage.py` the batched read (3 queries, any school size) · `Q-16`/`S-54` parent = whole syllabus (the only denominator that cannot fall), admin sees both · `S-42` `rated_status` makes an unlogged class-subject **`unknown`** on every surface (board + overview), never red, never ranked · `S-41` `attribute_cause` — four causes, four sentences, shared by the board and the class-teacher block · `S-45` `rank_reason` replaces the 60/40 composite · `S-50` headline + always-on next exam (needed the new batched **`exam_fit_org`**) · `S-40` coverage-over-time vs baseline, built from the snapshot with no extra query · `S-43` section compare · `D-16`/`S-60` `catchup_requested` — a meeting request that clears on the recorded **outcome** · `S-46`/`D-15` `/planner/my-subjects` + `/planner/class-syllabus/{id}`. `test_syllabus_v1_6.py` (12); full suite green; web tsc/eslint/build clean. |
| V1-7 · Events, dates & birthdays | not started | — | Needs V1-2 (DOB). Q-63 research runs before this packet. |
| V1-8 · Exams, scores & reports | not started | — | Largest packet. Corrections + lock ship first; photo flow + report levels follow. |
| V1-9 · Bands / support programme | not started | — | Needs V1-2 + V1-8's lock. Step 0 = four fixes. |
| V1-10 · Fees | not started | — | Needs V1-1. Migration: fee_notes. |
| V1-11 · Parent portal | not started | — | Needs V1-2, V1-3, V1-5, V1-10. |
| V1-12 · Dashboard visual layer + Lucy | not started | — | Needs all module packets. |
| V1-13 · Hardening & release | not started | — | Prod app-role swap (RLS) is the 🔴 item. |

## Packet-close gate (every packet)

- backend `uv run pytest -q` green + `ruff check app tests` clean
- frontend `npx tsc --noEmit` + `eslint` + `next build` clean
- **the no-dead-ends grep**: no exported client API method with no caller; no endpoint with no client
- the packet's own Done-when from the plan

## Session log

- **2026-08-01 (session 1)** — V1-0 shipped + committed (`c14daf6`). Backend 381 passing.
- **2026-08-01 (session 2)** — this tracker created; **V1-1 built and shipped** (backend +
  frontend + tests). Also fixed en route: the rail lost its default title when an explicit
  assignee was picked for a student follow-up. Note: `api/.env` was in PROD mode, so the
  migration went to DO prod first (additive, safe), then test+dev were migrated via
  `ALEMBIC_DATABASE_URL`.
- **2026-08-01 (session 2, cont.)** — **V1-2 built and shipped.** Deviations worth knowing:
  the readiness report is a Sheet on `/platform` org cards (not its own route); copy-handover-
  credentials stays at create time (the temp password is never stored); staff DOB is collected
  by the staff importer only (no member-edit UI yet — V1-7 can add if needed). `work_types.
  label_for(key, org)` is now org-aware — new render sites must pass the org.
- **2026-08-01 (session 2, cont.)** — **V1-3 built and shipped.** Notes for later packets:
  `classify_day` gained `am_absent`/`pm_absent` and `classify_marked_day` is now THE per-day
  classifier (register, parent strip, timeline all render it — never re-derive). `day_matrix`
  in `services/attendance.py` is the batched period-level read behind them. `PeriodTime.kind`
  now accepts any lowercase word, not just `period|break`, so twice_daily can find "lunch".
  Deviations: the drifting/chronic-late lists are read-only rows (no rail actions yet — they
  belong to V1-9's support programme); `CallStrip` in class-register.tsx is exported but not
  yet mounted (the register's own red squares cover today). Next up: **V1-4 (staff, leave,
  cover & time)** or any of V1-5…V1-10 — they are independent once V1-0/1/2 landed.
- **2026-08-02 — V1-4 built and shipped.** Notes for later packets:
  - `calendar.org_working_days(db, org_id, a, b)` is now THE org-level working-days read and
    returns dates, not a count. **Use it** — do not add a fifth implementation. `LeaveService`,
    the month summary, the cover horizon and the call board all read it.
  - `school_clock.periods_before_lunch` / `half_day_periods` are the one midday cut. Anything
    that needs "morning vs afternoon" goes through them.
  - `staff_attendance.present_value(status)` is the one day→days-worked function. When payroll
    arrives in v2 it reads this and `StaffMonthService`, not a new calculation.
  - `leave_requests.days` is **numeric** now — `float()` it, never `int()`, or every half-day
    rounds away. Two places already made that mistake before the type changed.
  - Two pre-existing Sunday-only defects fixed en route (the suite only ever ran Mon–Sat, so
    neither had been seen): `CallBoard` anchored on the raw calendar today, and
    `TimesheetService.week` dropped non-working days that had work on them.
  - **Known, out of scope:** the demo timetable can still double-book a teacher (3 classes ×
    5 subjects over 4 staff has no clash-free solution), so the seeded cover sheet may list one
    teacher in two rooms at once. Real schools import a validated grid; the seed writes rows
    directly and bypasses `TimetableService`'s clash validator. Worth fixing when V1-13 re-seeds.
  - The repo-wide no-dead-ends grep shows **24 orphan client methods**, all pre-existing and all
    owned by later packets (homework → V1-5, events → V1-7, bands/interventions → V1-9,
    fees → V1-10). V1-4's own surface is clean, and it wired `insightsApi.substitutions` (an
    orphan since DASH3) onto `/staff/today` as "who is covering for whom".

- **2026-08-02 (session 2) — V1-5 backend built and committed (`8e67390`). The packet is NOT
  closed: the entire frontend remains.** Read this before resuming.

  **What is already true on the server** (all tested, don't rebuild it):
  - `core/homework_verdict.py` is THE vocabulary and arithmetic. Every new surface must import it
    rather than deciding again what `late`/`carried`/`partial` is worth. It also owns
    `miss_streak`, so one number appears beside a name everywhere.
  - `GET /homework/queue` → the backlog (unchecked first, oldest first) + `to_check` for `S-100`'s
    button. `GET /homework/load` → `D-37`'s per-class evening. `GET /homework/student/{id}` has
    existed since HW-1 and is **still called by nothing** — wiring it is `S-86` and it delivers
    `D-31` from the same component as the teacher's by-student view (`S-101`).
  - The check sheet (`/classroom/homework/{id}/sheet`) rows now carry `absent_when_set`,
    `carried_pending` and `miss_streak`; `HomeworkResultIn.status` accepts the five verdicts.

  **What is left — all frontend:**
  1. `/homework` — `D-36`/`S-101`'s three levels: her classes × what was given → the check sheet →
     by student / by day. The by-student view is ONE component shared with the admin's `D-31`
     drill-down; build it once.
  2. `S-100` — the counted button on My Day (*"Homework · 4 to check"*), and **remove My Day's
     yesterday-homework block** (`D-36` — checking is a desk activity, not a between-classes tap;
     recorded so nobody optimises it back).
  3. The check sheet UI: the five-verdict cycle, the absentee badge (shown, **not** preselected),
     the carried-pending badge, and the streak on the row (`S-89`).
  4. `/students/[id]` — mount the homework history block (`S-86`).
  5. `/dashboard/homework` — `delayed_teachers` + `rough_classes` as named rows; `late` and
     `carried` reported beside completion, never inside it.
  6. Class-teacher + admin daily load (`D-37`), and the parent's `pending` / `missed` split
     (`S-94`) with carried rendering **yellow, never red** (`D-35`).
  7. Then the gates: full `pytest`, `tsc`/`eslint`/`next build`, the no-dead-ends grep,
     **migrate prod** (`c5d6e7f8a9b0` is on dev+test only), and re-seed so the screens have data.

  Watch for: `homework_gap_days` (org setting, default 3) drives the delayed-teacher signal — do
  not hardcode 3 in the UI. And `not_checked` must never render as a student miss on any surface,
  parent-facing included; that is the module's load-bearing rule and the thing most likely to be
  broken by someone tidying the copy.

- **2026-08-02 (session 3) — V1-6 built and shipped.** Notes for later packets:
  - **`core/coverage.py` is now THE syllabus vocabulary**, not just the partial
    weight: `taught_weight` · `better_coverage` (best log per topic wins — a topic
    taught across two periods is taught *once*) · `coverage_pct` · `CoverageFigure`
    (a number that cannot be rendered without its denominator) · `rated_status`
    (`S-42`) · `attribute_cause` (`S-41`). **Import it. Do not compute coverage
    again**, in Python or in the browser — the packet found five rival definitions
    and two of them were `.reduce()` calls in React that no test could have caught.
  - **`services/coverage.py::CoverageReader`** is the batched read behind every
    coverage figure: 3 queries for any number of class-subjects, and it excludes
    pre-tracking terms from the numerator **and** the denominator (pinned by
    `test_midyear.py`). `snapshot()` also returns the per-topic detail so `S-40`'s
    weekly series costs nothing extra.
  - **`ForecastOut.logged_periods`** now rides along with the pace. The forecast
    still returns green/amber/red — its arithmetic is plan-against-calendar and is
    valid with zero logs — and every *screen* runs the pair through `rated_status`.
    That split is deliberate: `test_term_planning.py` and `test_midyear.py` pin the
    forecast's RAG, and `unknown` is a rendering decision, not a planning one.
  - **`PlannerService.exam_fit_org`** is the batched exam fit (the PR-6 move again).
    The per-class form ran a units query *per class-subject*; `S-50` put the exam in
    the headline on every load, so it had to stop. `exam_fit` now delegates to it.
  - `task_instances.subject_type` accepts **`class_subject`** (free-text column, no
    migration); `TaskService._subject_map` resolves it to "6-B Maths". That is what
    lets the board read back whether the catch-up meeting has happened.
  - **Three founder calls were made from the documented recommendation, not from an
    explicit decision — worth confirming:** `Q-16` (parent denominator = whole
    syllabus, admin sees both), `Q-18` (the rank guard stays, copy becomes a
    countdown), and `S-44b` (the "Size these chapters" deep link is kept — it
    schedules nothing, so it survives `D-16`). `Q-19` is untouched: "missed while
    absent" still stands as it was.
  - Deviation worth knowing: **`S-46`'s "landing" is the nav**, not the tab order —
    `SubTabs` treats `tabs[0]` as the exact-match area root, so putting My subjects
    first would have lit up the wrong tab on every nested plan route. `navForRole`
    points a teacher's Plan item at `/plan/my-subjects` instead.
  - Not done, and deliberately: `S-49`/`Q-19` (the wording of "missed while absent"
    on the parent report) was left alone, and the class-teacher block does not read
    `class_periods`, so it never claims "periods were lost" — it has not counted
    them, and claiming it anyway would be worse than saying "slower".

## Standing reminders

- Fence propagation (plan §12.4): `D-82` (per-student exam photos) + `D-83` (teacher fee detail
  inside an assigned task) are already noted in `CLAUDE.md`; ux-principles.md + SPRD2 §11 still
  need the same note **before V1-8 / V1-10 start**.
- Test DB: local `trackbit_school_test` only; full suite ~4.5 min. Mid-work, run the touched
  file + ruff/tsc only (user preference).
- Migration head at V1-0 close: `e0f1a2b3c4d5`. **Now `c5d6e7f8a9b0`** — on dev + test;
  **prod is at `b4c5d6e7f8a9`** and needs `c5d6e7f8a9b0` when V1-5 closes.
