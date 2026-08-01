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
| V1-5 · Homework | not started | — | Needs V1-3. Simplified by D-85. |
| V1-6 · Syllabus, planning & mid-year | not started | — | |
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

## Standing reminders

- Fence propagation (plan §12.4): `D-82` (per-student exam photos) + `D-83` (teacher fee detail
  inside an assigned task) are already noted in `CLAUDE.md`; ux-principles.md + SPRD2 §11 still
  need the same note **before V1-8 / V1-10 start**.
- Test DB: local `trackbit_school_test` only; full suite ~4.5 min. Mid-work, run the touched
  file + ruff/tsc only (user preference).
- Migration head at V1-0 close: `e0f1a2b3c4d5`.
