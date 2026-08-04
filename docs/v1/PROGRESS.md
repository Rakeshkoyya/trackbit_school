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
| **V1-5** · Homework | ✅ **DONE** | `8e67390` + frontend | Migration `c5d6e7f8a9b0` (`homework_results.status` widened to `late`/`carried`/`waived`) on **dev + test; NOT yet on prod**. Done: `core/homework_verdict.py` (the one vocabulary + arithmetic + `miss_streak`) · D-85 late-as-status + the two derived admin signals (`delayed_teachers`, `rough_classes`) · D-34/S-98/S-102 carried & waived · D-36/S-100 `queue()` + `to_check` · S-85/S-89/S-97 on the sheet · D-37 `daily_load()` · growth + parent-portal readers fixed (S-94/D-35). `test_homework_v1_5.py` (11). **Frontend (session 4):** `/homework` = `D-36`'s three levels (queue → sheet → by student) with a **Homework** nav item · `components/school/homework-check-sheet.tsx` = the five-verdict cycle + `S-85` absentee badge (shown, never preselected) + `S-97` carried-pending + `S-89` streak · `components/school/student-homework-history.tsx` built **once** and mounted on both `/students/[id]` (`S-86`) and the admin drill-down (`D-31`) · My Day's yesterday-homework block **deleted** and replaced by `S-100`'s counted button · `/dashboard/homework` gains `delayed_teachers` + `rough_classes` as named rows and reports `late`/`carried` **beside** completion · `D-37` daily load on My Class · parent verdicts extended (`carried` renders **yellow, never red** — `D-35`). |
| **V1-6** · Syllabus, planning & mid-year | ✅ **DONE** | see git log | **No migration.** `S-51` the one coverage computation — the phrase was computed in **five** places, no two alike (two of them in the browser); `core/coverage.py` now owns the arithmetic + the three named bases and `services/coverage.py` the batched read (3 queries, any school size) · `Q-16`/`S-54` parent = whole syllabus (the only denominator that cannot fall), admin sees both · `S-42` `rated_status` makes an unlogged class-subject **`unknown`** on every surface (board + overview), never red, never ranked · `S-41` `attribute_cause` — four causes, four sentences, shared by the board and the class-teacher block · `S-45` `rank_reason` replaces the 60/40 composite · `S-50` headline + always-on next exam (needed the new batched **`exam_fit_org`**) · `S-40` coverage-over-time vs baseline, built from the snapshot with no extra query · `S-43` section compare · `D-16`/`S-60` `catchup_requested` — a meeting request that clears on the recorded **outcome** · `S-46`/`D-15` `/planner/my-subjects` + `/planner/class-syllabus/{id}`. `test_syllabus_v1_6.py` (12); full suite green; web tsc/eslint/build clean. |
| **V1-7** · Events, dates & birthdays | ✅ **DONE** | see git log | Migration `d6e7f8a9b0c1` (`observances` platform table · `event_decisions` append-only · `class_periods.not_held_event_id`) on **dev + test; NOT yet on prod**. Defect 1 closed — `calendar_events` had a write side for a year and **no reader**; `/events/whats-on` is one computation over three sources (`S-121`: birthdays are DERIVED from DOB, never stored). Defect 2 was already fixed in the paint UI, and `D-58`'s approval sheet now makes the open/closed choice structural. `D-57`/`D-79` approve-this-date: editable date + three lock levels, so **one suggested row yields two approvals** · `S-143` cost preview off a new `forecast_org(extra_events=…)` · `S-148` dismissal append-only + keyed on the stable `key` · `S-149`/`S-150` catalogue is platform data with required provenance, `/platform/catalogue` tab + annual import · **`S-145` the one `day_lock()`** now removes locked periods from My Day, the 16:00 reminder, the capture heatmap and the daily report (`Q-65`: from what is *expected*, never from what was *recorded*) · `S-147` not-held references the event · `D-56` staff DOB self-entered on Account. `test_events_v1_7.py` (10). 🔴 **`Q-63` is still open, so the catalogue ships EMPTY** — see the session log. |
| **V1-8** · Exams, scores & reports | ✅ **DONE** | see git log | Migration **`e7f8a9b0c1d2`** (`exam_types` · `exam_lock_events` · `scale`/`exam_event_id`/`locked_at` on cycles · `question_marks` on scores · `mode`/`locked_rows`/`corrections` on captures · `student_id` on capture pages · `training_data_opt_in`) — **on dev + test; prod is 3 behind** (see the migration note below). **`core/exams.py` is THE exam vocabulary**: `minor`/`major` that cannot be pooled (`ScaleTally` has no blended-average method by construction), `ScoreFigure` that cannot render without its denominator, per-question mark normalisation, and `sum_mismatch`. `D-55`/`S-135` the school's own exam type (a school running **CET** could not record one) carrying the `scale`, so the teacher picks **one** thing · `S-114`/`Q-50` never-pool applied to the admin board (`standing` vs `trajectory`, `scale_basis` **named** on screen), `class_analysis` (movers compare like with like), growth and the report card · `S-118` every average carries its denominator, and a few-students test the child never sat is out of it · `D-53`/`Q-62` verify-&-lock: locking stamps `verified_by` (the badge could not light up before), refuses edits on **every** write path, and unlock is admin-only, reasoned and **appended** · `D-80`/`D-82` per-student script capture — an unreadable page is **kept** as its own row and mapped by hand, the confirmed grid files each paper against its child · `S-119` the paper is one tap from the mark on the exam page, the report card and growth · `S-115` `exam_event_id` · `D-80` the **Report** tab (`services/exam_report.py`) · `D-81` **both report levels** (`services/report_card.py`: the card is numbers only, the analysis is narrative over the same figures) · `D-54`/A-4 the training pair written **only at lock, only on opt-in**, no export path. New: `services/exam_marks.py` (the one batched marks read, shared by growth and the report card), `services/exam_corpus.py`, `services/ai/exam_analysis.py`. `test_exams_v1_8.py` (11) + 37 regression green; web tsc/eslint/build clean; no-dead-ends grep clean. |
| **V1-9** · Bands / support programme | ✅ **DONE** | see git log | Migration **`f8a9b0c1d2e3`** (`band_descriptors` · `support_checkpoints` · `subjects.band_monitored` · `student_bands.subject_id`/`source`/`cycle_id` · `assessment_cycles.band_promoted_at`/`by` · `interventions.subject_id`/`owner_member_id`/`exit_criterion`/`closed_at`/`outcome_note`) — **dev + test; prod is now 4 behind.** **Step 0's four fixes first** (`S-180`): an intervention can finally be **closed**, which stops the targeted daily check a goal achieved in July kept injecting in March · the owner defaults to the **subject teacher** (every intervention in every real school was created unassigned) · `studentInterventions` is **wired** to the report card at last · **`apply_band_suggestions` and `categorize_from_cycle` are DELETED** (`S-183`) — a Tuesday slip test could re-band eleven children. Then: **`core/bands.py`** is the vocabulary (per-subject placements, `chip()` → *"C · Hindi"* `S-186`, `movement`, `size_warnings`, the pre-written descriptors) · `D-75` per-subject bands, **no overall letter** — the read-path rewrite through `BandService.placements`, so the directory chip, the class donut, the daily-check generator and growth cannot disagree · `D-69`/`D-74` descriptors carrying each subject's **own** threshold, seeded pre-written, and `S-166` the letter never renders without its sentence · `D-70`/`S-185` entry may be judgement, **movement is a test** · `D-76`/`S-182`/`S-184`/`Q-81` *"use this as the band test"* — a flag never a type change, **locked only**, size shown, warns-never-blocks, one subject, and the moves **reviewed before they commit** · `D-77`/`D-87`/`S-164`/`S-165` one owner per subject + `/support` and `/support/[id]` **opening already written** from five other teachers' capture + the four-field weekly check-in · `D-73`/`S-169`/`S-188` the programme board where **movement is the headline** and every stuck row names its subject. New: `services/bands.py`, `services/support.py`, `api/.../bands.py`, `schemas/bands.py`; web `/support`, `/support/[id]`, the rewritten `/students/bands` + `[classId]`, `band-assess.tsx`, `band-promote.tsx`, `support-block.tsx`, Settings → Support programme. `test_bands_v1_9.py` (11); web tsc/eslint/build clean; no-dead-ends grep clean. |
| **V1-10** · Fees | ✅ **DONE** | see git log | Migration **`a9b0c1d2e3f4`** (`fee_notes` append-only · `notifications.notif_type` gains `fee_reminder`) — dev + test. **No new fee tables**, which is the point of `D-62`: read + remind only, the money math and the counter screen untouched. **`core/collection.py`** is the vocabulary — a quarter is a **due-date window** (`Q-67`/`S-153`: `installment_number` breaks across differing structures and `label` is free text), and `Collection` has **no `outstanding` property**, so `collected`/`pending`/`overdue` cannot be summed by accident (`S-163`). **`services/collection.py::board()` is the one computation** every fee screen renders (`S-152`) — quarter strip, collection curve vs the previous quarter (`S-155`), class table with **both denominators** (`S-159`), and **the named defaulter list that has existed since P0-D and was called by nothing** (defect 1, closed). `S-158` a full concession is never a defaulter (the list is built from what is *owed*) · `S-157` the row names the **family** and gives you the number · `D-88` dues carried from a previous year are their own labelled line and never inside this year's totals (they used to be silently absent from every roll-up) · `D-84` the append-only **fee conversation history** — what the family *said* — on `/fees/[id]` and travelling into the task · `S-156` the reminder's manners: one per week however many staff press it, quiet hours, **primary guardian only** (`Q-70`), and it **stops the moment the payment lands** · `D-83` the assigned teacher gets the full detail **inside that task only**, asserted by tests both ways · `Q-69` the parent gets **one line**, only when something is due. New: `core/collection.py`, `services/collection.py`, `schemas/collection.py`; web `components/school/collection-board.tsx`, `fee-conversation.tsx`, `fee-followup-card.tsx`, the rewritten `/fees` landing, and the parent's fee line. `test_fees_v1_10.py` (7); web tsc/eslint/build clean; no-dead-ends grep clean. |
| **V1-11** · Parent portal | ✅ **DONE** | see git log | Migration **`b0c1d2e3f4a5`** (`parent_login_attempts` platform-level like `otp_codes` · `guardian_messages` org-scoped + RLS) — **dev + test + prod** (see the migration note). **`D-13` the front door**: school code → class → section → child → date of birth, because `D-08` removed WhatsApp and a login that depends on message delivery is a login the school cannot hand out. `S-55` the child step is **type-to-search** (min 3 chars, capped, rate-limited) so a section is never a browsable roster; `S-56` the lock is keyed **per student** (that is what is being guessed) and bumps in its **own committed session**, so it survives the rollback of the request that raised the error — the test proves the *correct* DOB is refused after five wrong ones. `Q-24` no-DOB-on-record **burns no attempt** and points at `Q-29`'s recovery door (phone-OTP kept, moved to `/parent/login/otp`, never deleted — it is the only way in for the family the school has no DOB for). `Q-25` (b) *"Add another child"*: one proof buys **exactly one child**, even when siblings share a phone — deliberately narrower than the OTP path, where the phone *is* the proof. **`D-08`/`D-14` messaging**: `notify_guardian.py` was a WhatsApp stub that logged to a file — the absence alert, homework and the Saturday note all ended their life in a log line. `guardian_messages` is the destination, all five callers rewritten, delivered by web push (parents now reach `/push/subscribe` via `get_current_principal`; `dispatcher.push_to_user` is the **one** push path). **`S-62` is the honest half**: push is best-effort and the absence alert is not, so `push_sent_at`/`unreachable_reason` are recorded and `services/insights/reach.py` turns them into **named rows with the phone number** on the attendance tab and the overview rail. An opted-out family is counted **apart** and never joins the list the office is told to clear. `Q-56` the calendar — read-only, zero new capture, **own child's birthday only** (`whats_on.py` is NOT reused: it lists every student's and every colleague's). `S-61` Today is the delivery surface, **Updates** is the archive. Also shipped: `S-94`'s **missed** list, which the server has returned since V1-5 and no page rendered; `late`/`carried` counts (`S-99`/`D-35`); and three drifted TS types repaired. **Defect found and fixed**: `register_org` never minted a `school_code`, so every self-registered org had a parent portal that could not be entered. `test_parent_v1_11.py` (9, incl. the D-35 parent-side proof that a carried item shows as pending and a waiver clears it — V1-5 asserted only the teacher half); web tsc/eslint/build clean. |
| **V1-12** · Dashboard visual layer + Lucy | ✅ **DONE** | see git log | **No migration.** §7 audit: Overview, Attendance, Staff and Syllabus already led with a computed sentence; **Homework, Exams and Tasks opened on a static subtitle and went straight to charts.** All three now carry a server-composed `headline`, following V1-6's precedent and for its reason — composed once so the tab, the overview block and Lucy cannot describe the same week differently. The sentences hold their modules' own rules: homework never renders an unchecked set as **0% done** (HW-1 — `not_checked` is the teacher's gap, and a percentage with nothing behind it blames children for a teacher who hasn't opened the notebooks), exams **names the scale its figure came from** and needs two rated classes before it claims a weakest (`S-114`/`S-118`), tasks names **who** the overdue work is sitting with (nine across nine people is a busy week; nine with one person is a conversation). **Lucy reconcile:** the real find was `get_fee_summary`/`get_overdue_fees` still reading the OLD `FeeService` roll-up — no quarter windows, and `opening_dues` missing from every figure (`B-2`) — so *"how much of Q2 is in?"* got a year total that silently dropped the school's worst debtors while `/fees` beside it showed both. Replaced by one **`get_fee_collection`** on `CollectionService.board()`, the same computation the screen renders (`S-152`); the old pair is subsumed because the board already carries the named defaulter list. Registry 43 → 42, still admin-only. Verified: all 42 tool→service calls resolve (nine packets rewrote the services under Lucy), V1-9 had already made the band tool per-subject, and `overview.py` was already on `services/coverage.py` from V1-6. Charts: **no change was correct** — every chart on those tabs is one §7 explicitly prescribes, and the palette grep is clean (no hardcoded hex outside `components/charts/palette.ts`). The fee-fence test was **strengthened from two tool names to the whole teacher surface** (word-boundary regex, so `get_exam_feed` still passes) — the rename is exactly how a fee tool would otherwise have slipped past it. `test_dashboard_v1_12.py` (7), incl. a mechanised reconcile that fails if any Lucy tool calls a method that no longer exists. |
| **V1-13** · Hardening & release | ✅ **DONE** (except the prod app-role swap — needs the founder) | see git log | **No migration.** Full suite **492 passed** on real local Postgres; ruff/tsc/eslint/`next build` clean. **The no-dead-ends grep now passes on the client side: 30 orphan methods → 0.** Four of them were not dead code but **missing UI**, and one was load-bearing: `createTerm`/`deleteTerm` had no caller anywhere, so **terms could only ever come from the seed** — and `BandService.assign_owner` refuses with *"Set up a term first"*, `syllabus_units.term_id` files every chapter under one, and `approve`/`draft` take one. A school set up through the wizard could not plan term by term at all. Also wired: guardian add/remove/opt-out on the student sheet (they could only be set at creation, and every parent-facing message keys on them), the timetable **clash banner** (`/timetable/validate` has existed since V2-P1 and returned its verdict to nobody), and clearing an exam portion. 19 superseded client methods deleted with their reasons recorded. **Seed fixed:** the demo grid double-booked teachers (Anil in three rooms at once on Mon P4 — the known V1-4 defect, deferred to this packet); each class now has its own pair of teachers, 6 teaching staff, and `/timetable/validate` returns `[]`. New **`scripts/seed_midyear.py`** = §5's acceptance fixture, and it passes: no red rows, no data claimed before `tracking_start_date`, carried dues on their own line. **Verified by driving the running server**, not by inspection: 131 routes swept per role — admin 117×200/0×404/0×5xx, teacher 38×403, **0 `/fees` routes reachable by a teacher**. |

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

- **2026-08-02 (session 4) — V1-5's frontend built; the packet is now CLOSED.**
  - The five-verdict sheet and the by-student history are **components, not pages**
    (`components/school/homework-check-sheet.tsx`, `student-homework-history.tsx`),
    because each is mounted twice. The by-student view in particular answers the
    same question for a teacher and for an admin — two components would have been
    two answers, which is the `S-51` defect wearing a different hat.
  - **My Day's homework block is gone on purpose** (`D-36`), replaced by a counted
    button. Recorded here so nobody optimises it back: checking homework is a desk
    activity, and the old block met a teacher walking between rooms with thirty
    seconds and asked her to go through thirty names.
  - Client types were still V1-4-era and would have **crashed the parent page at
    runtime** the first time the API sent `carried` — `HW_STATUS[hw.status]` was
    undefined. `HomeworkStatus`, `HomeworkSheetRow`, `StudentHomeworkHistory`,
    `HomeworkScopeRow` and `HomeworkOverview` all gained the V1-5 fields.
  - Deleted one genuine dead end the packet gate caught: `schoolApi.homeworkOverview`
    had no caller — the dashboard reads the same data through
    `insightsApi.homework()` (`/insights/homework` wraps the overview).
  - 🔴 **Still outstanding for this packet: prod is at `b4c5d6e7f8a9` and needs
    `c5d6e7f8a9b0`.** Not run from here — `api/.env` is in PROD mode, and pointing
    alembic at the live database is a deploy decision, not a build step. Run it
    when you deploy; the migration is additive (it widens
    `homework_results.status` to accept late/carried/waived).

- **2026-08-02 (session 5) — V1-7 built and shipped.** Notes for later packets:
  - **`calendar.day_lock(db, org_id, date)` / `day_locks(...)` is THE answer to "is
    this period still expected?"** — import it, never re-derive. Before it, four
    surfaces each had their own idea of what a school holiday means and three had
    none at all: on 15 August a teacher saw eight unlogged period rows, was pushed
    at 16:00 about a day the school itself cancelled, and appeared in the daily
    report as the worst capture failure of the year. My Day, `run_teacher_reminder`,
    the capture heatmap and `DailyReportService._assemble` now all read it.
  - ⚠️ **Locking removes a period from what is ASKED FOR, never from what was
    RECORDED** (`Q-65`, answered (b)). A school that closed at 11am genuinely did
    teach period 1. The period card still opens on a locked period and still shows
    what is in it — it just stops asking. Anyone "tidying" this into a delete is
    committing a law-3 violation and a data loss in one move.
  - **`PlannerService.forecast_org` gained `extra_events`** — the same computation
    against the calendar the school *would* have. That is the whole cost preview
    (`S-143`); there is no second engine, and there must not be one.
  - `S-146` is a rule, not a preference: **if the admin locked it, the teacher is
    never asked.** Both recording it would subtract the day from capacity twice.
    That is why the period card carries `locked` and hides "Period not held?".
  - 🔴 **`Q-63` is unanswered, so the catalogue table ships EMPTY, and that is the
    correct state.** Every mechanism is built and tested — the platform table, the
    scoping by `state`+`board` (`D-61`), the curation tab, the annual bulk import,
    provenance-required. What is missing is the *data*, and filling it by asking a
    model when Diwali is would be exactly `S-123`'s rejected row: an unverifiable
    claim, stored, that a school then decorates on. An empty catalogue means "no
    suggestions", which is honest; the school's own dates and birthdays carry the
    module on their own (build-order steps 1–6). The seed adds three obviously-fake
    demo rows whose `source` says so.
  - Deviation from the brainstorm's build order: **`Q-60` answered (a)+(b)** as
    Claude recommended — the suggestion feed and approval sheet live on **Plan →
    Year**, beside the calendar an approval writes to, and the card is an agenda
    list on the dashboard. No third month view was built.
  - `Q-64` answered **(a)**: the teacher's strip shows approved dates only.
    `/events/suggestions` is `require_admin`, so provisional rows cannot reach her
    even by accident.
  - Staff DOB (`D-56`) rides on the **existing** `PATCH /auth/me`, not a new
    profile module. It needs `set_date_of_birth: true` to write — otherwise every
    name change would silently clear it.
  - Fixed en route: `tests/conftest.py`'s `cleanup` now tracks `observances`.
    Platform tables have no `org_id`, so deleting the org does not take them with
    it, and `UNIQUE(key, date)` collides on the next run. Any future platform-level
    table needs the same line.
  - 🔴 **Outstanding: prod is at `b4c5d6e7f8a9` and now needs BOTH `c5d6e7f8a9b0`
    (V1-5) and `d6e7f8a9b0c1` (V1-7).** Both are additive. Not run from here —
    `api/.env` is in PROD mode and pointing alembic at the live database is a
    deploy decision.

- **2026-08-02 — V1-8 built and shipped** (in parallel with V1-7; its migration
  `e7f8a9b0c1d2` chains off `d6e7f8a9b0c1`). Notes for later packets:
  - **`core/exams.py` is THE exam vocabulary.** Import it; do not decide again
    what `minor`/`major` is worth, or render an average without its denominator.
    `ScaleTally` deliberately has **no method that returns a blended number** —
    a caller who wants one has to write the addition in the open. That is the
    fix for the defect where *"Maths is at 61%"* was the mean of an April
    diagnostic, twelve slip tests and one final.
  - **`services/exam_marks.py::load_class_marks` is the one batched marks read**
    (4 queries for a whole class). The growth report and both report-card levels
    go through it, which is what makes `test_exams_v1_8.py` able to assert that
    two screens' payloads agree. Any new marks surface reads it too.
  - **The lock is a write-path guard, not a UI state.** `ExamService.save` AND
    `AssessmentService.save_scores` both refuse a locked cycle. A third write
    path into `assessment_scores` must add the same guard or the lock is
    decorative.
  - `assessment_cycles.type` stays the **system kind** the code branches on;
    `exam_types.name` is what every screen displays and groups by (`D-55`). If
    an analytic ever groups by `type`, the two have diverged.
  - V1-9 is now unblocked: `D-76`'s "use this as the band test" needs
    `locked_at`, which exists, and `S-184`'s "a promoted test must be locked"
    reads `ExamDetail.locked`.
  - Deviations worth knowing: the exam-type picker **seeds the nine on first
    read** (a write on a GET, the `RecommendationsService.ensure` shape) so
    nobody configures vocabulary before recording a test; `S-116`'s marking
    check ships as **deterministic arithmetic only** (the per-question marks
    don't sum to the total) — `Q-51`'s answer-judging half stays out, and
    nothing about a child's answer is stored or shown; and the training corpus
    has **capture but no export**, deliberately (A-4).
  - **Caught in self-review, and it is the fence lesson worth repeating:**
    `ParentReportSubject.scores` was typed `list[GrowthScore]`. V1-8 added
    `paper_url` — a link to the child's photographed script — to that **staff**
    schema, so the parent portal would have started serving it with nobody
    deciding it should. PC-1's *"field by field, never a spread"* only holds if
    the projection names **fields, not types**: `ParentScore` now spells the
    shape out, `test_exams_v1_8.py` asserts `paper_url` stays staff-only, and
    `scale`/`type_label` are let through deliberately (without them a parent's
    report draws one line through a 5-mark slip test and an 80-mark final).
    **Any schema a parent surface borrows from a staff surface is this bug
    waiting.**
  - 🔴 **Outstanding: prod is at `b4c5d6e7f8a9` and now needs THREE** —
    `c5d6e7f8a9b0` (V1-5), `d6e7f8a9b0c1` (V1-7), `e7f8a9b0c1d2` (V1-8). All
    additive. Not run from here: `api/.env` is in PROD mode and pointing alembic
    at the live database is a deploy decision, not a build step.

- **2026-08-02 — V1-9 built and shipped.** Notes for later packets:
  - **`core/bands.py` is the vocabulary; `services/bands.py` is the only place a
    band is read or written.** Before this, four methods in `AssessmentService`
    each filtered `scope_skill_area_id IS NULL` for the *overall* letter. If a
    new surface needs a child's band, call `BandService.placements` — do not
    query `student_bands` directly.
  - **There is no overall band any more** (`D-75`). Rows with `subject_id IS
    NULL` are the retired letter: kept as history, read by nothing. A chip is
    `chip(placements)` → **"C · Hindi"**, never a bare letter and never an
    average across subjects.
  - **Two write paths were deleted, not deprecated** (`S-183`):
    `apply_band_suggestions` and `categorize_from_cycle`. Movement goes through
    `promote_preview` → `promote`. If a future screen wants "one tap to
    re-band", it is asking for the defect back.
  - **`interventions.status` is load-bearing.** `RecommendationsService` filters
    on `active`; closing a plan is what stops the targeted daily check. Any new
    consumer of interventions must respect the status or a finished goal starts
    injecting work again.
  - Promotion is deliberately **teacher-allowed** while the dedicated band test
    stays admin-only (the module's own ⚠️ note): the guard that matters is
    `locked`, not the role. `ExamService.save` still refuses a `band_test` from
    a non-admin, and that is unchanged.
  - Deviations worth knowing: the old `/assessments/bands?class_id=` board and
    the intervention sheet's **task-board dropdown** are gone (§4.6 — the
    school's data model in the middle of a conversation about a child);
    `board_id` on `InterventionCreate` is now optional, so a plan can exist
    without spawning tasks. `test_exams.py`, `test_assessments.py` and
    `test_recommendations.py` were updated to the new contract — those three
    were asserting the behaviour this packet removes, not regressions.
  - Not built, and deliberately (the plan's V1-9 list stops before them):
    `S-179`'s A-band harder checks, `S-176`'s effort figure from
    `timesheet_entries.student_id`, and `S-177`'s support groups as sessions.

- **2026-08-02 — V1-10 built and shipped.** Notes for later packets:
  - **`services/collection.py::board()` is the only fee read a screen may use.**
    The quarter strip, the curve, the class table, the defaulter list and the
    dashboard's small block are all renderings of it, so they cannot disagree.
    `FeeService.summary` survives for the counter screen; **do not add a second
    roll-up beside `board()`** — that is the `S-134`/`S-152` trap.
  - **`Collection` has no `outstanding` property, deliberately** (`S-163`), the
    same device `ScaleTally` (V1-8) and per-subject bands (V1-9) use: a caller
    who wants a blended number has to write the addition where a reviewer sees
    it. Three of the last three packets needed this shape — it is the house
    pattern now.
  - **A quarter is a computed window, not a column.** `Q-67`(d) — a school
    declaring its own uneven quarters — is a later refinement and needs no
    migration: every consumer takes the window list rather than computing one.
  - **`D-83`'s narrowing is asserted, not reviewed.** `test_fees_v1_10.py` pins
    both halves: the assignee sees her student's detail, and a 403 for the board,
    for another family, and for a task she was not assigned. A second test walks
    `growth`, `report-card`, `timeline` and `analysis` asserting no fee word
    appears at all. **Any new academic payload must stay out of that grep.**
  - The reminder is a **human press** every time. No scheduler job was added and
    none should be: money messages that fire themselves will eventually reach a
    family in the week of a bereavement (the `S-129` reasoning).
  - ⚠️ **Two sessions shared the tree again.** V1-11 (parent portal) began in
    parallel and correctly chained its migration `b0c1d2e3f4a5` off this one, so
    the chain stays linear. Its `notify_guardian.py` rewrite replaced the
    `(phone, opt_out)` stub with an inbox row + web push and a new keyword
    signature; it also ported this packet's fee reminder to it, and its
    `GUARDIAN_MESSAGE_KINDS` already carries `fee_reminder`. Two consequences
    to know when resuming:
    - **the test DB must be at `b0c1d2e3f4a5`** or any suite touching guardian
      notification fails on a missing `guardian_messages` — applied here;
    - at V1-10 close the full suite was **474 passed, 2 failed**, and both
      failures (`test_attendance.py::test_opt_out_guardian_not_alerted`,
      `test_classroom.py::test_homework_notifies_guardians`) are **V1-11's own
      contract change** — `notified` now counts a guardian with no parent login
      as reached-but-unreachable — asserting the old stub's counting. They are
      that packet's to reconcile; nothing in V1-10 touches either path, and all
      49 tests across the suites this packet touches are green.

- **2026-08-02 — V1-13 built. v1 is feature-complete; one release item is left and it
  needs the founder.** Notes:
  - **The client half of the no-dead-ends gate is closed (0 orphan methods) and the
    server half is not, deliberately.** 31 GET routes have no web caller. They fall in
    three groups and only the third is debt: **(a) not web surfaces at all** —
    `/billing/webhook` (Razorpay), `/ops/run/{job}`, `/ops/metrics`; **(b) reached
    through Lucy, whose tools call the SERVICE not the route** — `topic_progress`,
    `skill_profile`, `band_history`, plan comments; **(c) genuinely superseded** —
    `/fees/summary`, `/fees/overdue-students`, `/fees/installments/{id}/mark-paid`,
    `/classroom/compliance`, `/assessments/bands/config`, `/sessions/records`,
    `/homework/overview`, `/insights/attendance/streaks`, `/wizard/reset` and the rest.
    Group (c) should be deleted, but every one of them is covered by a test, so it is a
    ~17-route change touching 8 test files — worth doing deliberately, not at the end of
    a session. They are invisible at runtime.
  - ⚠️ **`topic_progress` is a SIXTH coverage definition** (`planner.py`: "a topic with
    any full-coverage log is done; only partial logs → in progress") and it does not go
    through `core/coverage.py`. No screen calls it — **but Lucy does**, so she can report
    a topic's progress on rules the coverage screens do not share. That is the `S-51`
    defect with a tool for a hat. It is the first thing to fix in v1.1.
  - **`api/.env` was switched from PRODUCTION back to LOCAL** so this session's clicking
    could not write to a live school. The `PROD_*_BACKUP` comments are intact; flip the
    banner back before running Alembic against DigitalOcean.
  - **The demo seed's timetable was genuinely unrunnable** and every staff screen
    inherited it. Root cause was not the rotation (V1-4 already offset it) but the
    subject→teacher map: the three classes are always on three different subjects, so one
    teacher owning two subjects collides by construction. Fixed structurally — each class
    has its own pair of teachers, so a teacher never appears in two classes.
  - `scripts/seed_midyear.py` is the §5 fixture. **Do not "tidy" it by sizing Term 1 or
    Term 3** — the three coexisting states (pre-tracking unplanned · sized+approved ·
    known-but-unsized) are the test.
  - 🔴 **Outstanding, and it is a founder decision, not a build step: the production app
    role.** Prod `DATABASE_URL` is still `doadmin` (`rolbypassrls = true`), so every RLS
    policy is inert in the one environment that matters. `scripts/provision_app_role.py`
    exists. Also unverified from here: whether prod is at head `b0c1d2e3f4a5`.

## Standing reminders

- ✅ Fence propagation (plan §12.4) is **done**: `D-82` (per-student exam photos) and `D-83`
  (teacher fee detail inside an assigned task) are noted in `CLAUDE.md`, in
  `ux-principles.md`'s hard-fence table (rows *Per-student photos* / *Teachers and fees*) and
  in SPRD2 §11's 2026-08-01 addendum. Verified at V1-8 close.
- Test DB: local `trackbit_school_test` only; full suite ~4.5 min. Mid-work, run the touched
  file + ruff/tsc only (user preference).
- Migration head at V1-0 close: `e0f1a2b3c4d5`. **Now `a9b0c1d2e3f4`** (V1-10) — on dev + test,
  with V1-11's `b0c1d2e3f4a5` already chained behind it on test. **Prod is still at
  `b4c5d6e7f8a9`** and needs, in order: `c5d6e7f8a9b0` (V1-5), `d6e7f8a9b0c1` (V1-7),
  `e7f8a9b0c1d2` (V1-8), `f8a9b0c1d2e3` (V1-9), `a9b0c1d2e3f4` (V1-10). All additive;
  run them at deploy.
- Two packets were built in parallel on 2026-08-02 (V1-7 and V1-8) against the **same** local
  dev + test databases. If that happens again: chain the second migration off the first
  (`alembic heads` before writing one), and expect an occasional `deadlock detected` when a
  migration's `ALTER TABLE` meets the other session's running suite — retry, don't diagnose.

---

## V1-16 — the day-book (staff time, seen) · 2026-08-02

**No migration.** The category colour rides on the existing `organizations.work_categories`
JSONB; everything else is a read over tables SF-1 and V1-4 already fill.

The gap: the timesheet has existed since SF-1 and the admin could only ever read it **one
person at a time** (`/timesheet`) or **one period at a time** (`/staff/today`). Nobody could
see the school's day. So:

- **`services/insights/daybook.py`** — people down, periods across, one cell each. It
  **composes**: `TimesheetService.org_day` is the three-query batch that already unions the
  timetable, the timesheet, the cover board and staff attendance (`S-72`/`Q-37`), so the
  day-book and the timesheet cannot disagree about the same Tuesday (`S-51`). Adds only the
  tally and the sentence. `GET /insights/daybook` (any date) + `/daybook/glimpse` (the
  overview's block — *the same payload*, trimmed, with `rows_total` so the block can say "and
  6 more" instead of showing a partial school as if it were the whole one).
- **`services/staff_record.py`** + `GET /insights/staff/{id}/record` (and `/staff/me/record`,
  so the self-access the service already allowed has a door) — one person's day, month,
  categories and the SF-1/V1-4 attendance and leave figures, plus a written summary
  (`ai/staff_record.py`, env-gated, deterministic floor).
  🔴 **It is a record, not an appraisal, and that is enforced rather than intended** (`D-25`/
  `S-67`): no score, no rank, no completeness percentage, no path to pay — and the model's
  system prompt forbids appraisal language *in the negative*, because a model asked to
  "summarise a teacher's month" reaches for it unprompted. `test_daybook_v1_16.py` greps the
  whole written payload for it.
- **The five-colour budget** (`core/work_types.py::CATEGORY_COLORS`). A category needed a
  colour, so it got one from a **fixed validated list, never a hex an admin types** — the five
  were run through the dataviz six-checks against both surfaces, in the ring order they are
  assigned in, together with the teaching ink they sit beside. There are five because a sixth
  fails a check: categories past the fifth render slate and are read by name, which makes the
  colour budget the short-picker rule with teeth. `other` is pinned to gold so it means the
  same thing in every school. Settings → Timesheet categories gains the swatch row.

### Four defects, three of them found by looking at the screen

The suite was green before any of these. A screenshot at 1440px found all four.

1. 🔴 **The board manufactured 43 free periods on a Sunday** — it said "not a school day,
   nothing was expected of anybody" and then drew a full grid of FREE cells and a ring reading
   "4% spoken for". Both halves are the mistake `day_lock` exists to prevent (`S-145`): a
   locked period leaves the denominator entirely, it does not become capacity the school
   failed to use. New cell kind **`closed`**, `occupied_pct` is **None** rather than a share
   of nothing, and anything actually recorded on a closed day still shows (`Q-65`).
2. 🔴 **`TimesheetService.month` zeroed every non-working day** — V1-4 fixed exactly this in
   `week` (a period genuinely worked on a sports Sunday could not be seen OR recorded) and
   never carried the fix to `month`. So a warden's Sunday evening prep and a Saturday exam
   duty vanished from the month's totals while sitting plainly in `timesheet_entries`. **This
   fix also lands on the teacher's own `/timesheet/month`.**
3. 🔴 **The record counted the future as worked** — `TimesheetMonth` totals the whole month
   including days that have not happened (right for the teacher's planning grid), so on the
   2nd of August the record read *"Teaching — 38 of 38 periods (100%)"*. Combined with (2) the
   ring's slices and the totals beside them came from two different day sets and the page
   showed **109%**. Totals now stop at today, and the slices use the same window.
4. **`away` was a dashed hairline** and at 84px in dark mode was indistinguishable from an
   empty cell — the two facts the board exists to separate. It is a hatch now.

Also: "FREE"/"AWAY" typed into forty cells was deleted (texture + tooltip + the row's own
one-line summary carry it), the `Donut` legend **wraps instead of truncating** ("Notebook
checki…" names nothing), and the record's month line needs **5 points** before it draws —
not-enough-data is a word, never a chart with three points on it.

`test_daybook_v1_16.py` (9). Web: `components/insights/daybook.tsx` (grid · strip · legend ·
ring · day nav, one component at two densities), `components/staff/record-view.tsx`,
`/staff/member/[memberId]` (tabs hidden — it is a detail page, and it is open to its own
subject as well as to an admin). The Staff tab's old "The day, teacher by teacher" strip
column is **deleted**: the day-book above it is the same fact at full size, and two renderings
of one day on one screen only raise the question of which is authoritative.

---

## V1-17 — homework: the funnel · 2026-08-03

**No migration, no new capture.** Founder call after walking the shipped board: the information
was there and the presentation could not carry it.

### What was actually wrong

The tab opened on four stat tiles and then drew the **same measure three times** — completion
over the window, completion by class, completion by subject. Three charts, one number. Nothing
on the screen said *how much homework there was* or *whether anyone had looked at it*, and the
two bar charts each collapsed a whole axis, so *"6-B is low"* and *"Hindi is low"* could never
resolve into *"6-B Hindi is where it happens"* — the only version an admin can act on.

Underneath it, the three figures that matter were **in two different units**: `assigned` and
`checked` counted **sets of homework** while `done` counted **students**. That is why they could
not be drawn on one track and did not read as one story.

### The device

`HomeworkFunnel` — everything in *student-homeworks*, one row per student a homework was given
to, so the stages **nest** and each gap is a length:

```
GIVEN    1,240  ########################################
CHECKED    922  ##########################//////////////
DID IT     806  #######################...//////////////
```

The two gaps are two findings and are never the same colour. `//////` is nobody having gone
through it — HW-1's rule, the **teacher's** gap: the no-record hatch (V1-14's unmarked cell,
V1-16's away cell), in the same right-hand zone on both bars so the eye reads how much of the
page is simply unknown; never a colour, never a zero. `...` is the part that IS about the
children, and the only part that may carry a judgement. Between `checked` and `graded` sit
`carried` + `waived` (`D-34`/`S-98`), reported in words rather than absorbed into either side.

**`completion` divides by `graded`, never by `given`.** A school that checked nothing can never
read as a school that did nothing.

### 🔴 The defect this turned up

The daily series was a **second walk over the window with its own arithmetic**. It re-ran
`HomeworkService._load` (ten queries to draw one board, against a docstring promising five),
counted `status == "done"` literally so **`late` was dropped from the numerator**, kept
`carried`/`waived` **in** the denominator, and never ran the absent→carried rewrite. So the
chart read lower than the sentence printed directly above it, and a child off sick pulled the
line down. Now accumulated inside `overview()`'s single pass through `core/homework_verdict` —
`S-51` closed for the third time in this module.

### Also fixed, all pre-existing

- **`waived` was missing from `HomeworkScopeRow` entirely**, so waived work was invisible on the
  by-class and by-subject tables while the student history reported it.
- The improvement delta was **written over `streak`**, so a row claimed a miss streak it did not
  have and the screen printed *"N fewer misses"* out of a field named for the opposite thing.
  It has its own `improvement` now — any second consumer would have inherited the lie.
- **`homework:unchecked` had been rendering twice** on the dashboard since DASH3: once on the
  rail as something to go and do, once in the alert feed as something to file a task about.

### ⚠️ Found by looking at the built screen

The new overview block printed a **14-day sentence over a 7-day funnel** — *"430 given"* above
stage bars reading 205 — because the server composes that sentence over
`HomeworkInsights.WINDOW_DAYS` and the client asked for its own window. The same
two-computations defect this packet exists to remove, reintroduced in the block that summarises
it, and invisible to every gate: tsc, eslint, ruff and the suite were all green. One exported
`OVERVIEW_WINDOW_DAYS`, the strip's label read off the payload, and a test asserting the
section's metrics equal the board's funnel.

The stage ramp also cleared every validator check and still read as one colour at the size it is
actually drawn. It was widened and re-validated; the light end is pinned by the 2:1 surface
floor, so the separation had to come from pushing the far end.

### Deliberate

- **Best/worst goes to classes and subjects only.** Ranking teachers by their children's
  completion would make a person's standing a function of forty other people's evenings. The
  checking ledger rates a teacher on **her own act** — did she go through what she set — and
  that is the only thing on the screen that rates her at all (`D-39`/`S-92`).
- **No `opened_at` "teacher started checking" capture**, which was asked about. A
  `homework_checks` row already means *she went through it*, and its absence meaning
  `not_checked` is the load-bearing rule of the module; a second, weaker definition would let a
  teacher who merely opened the sheet count as having checked.

`test_homework_v1_17.py` (12). Range filter Week · Month · Term · Year; the endpoint's 60-day
clamp is gone (400) and the series buckets weekly past 21 days. Reviewed at 1440px and 360px in
both themes against a month of seeded homework.

---

## V1-18 — fees: collection against the calendar · 2026-08-04

**No migration, no new capture.** Founder call after walking the shipped board: the fee UI did
not feel good and could not be read.

### What was actually wrong

A collection percentage cannot be read on its own. **45% is excellent in May and alarming in
February**, and every fee figure in the product was printed without the date that makes it
readable: `/fees` opened on four bare numbers on one line, then a strip of quarter buttons each
carrying a percentage. `QuarterRow` has carried `billed / collected / pending / overdue / pct`
for every quarter since V1-10 — the UI rendered the pct as a button label and discarded the rest.

### The missing number

`Collection.due_by_today` — everything the school has **asked for** by today, paid or not.
Deliberately **not** `overdue`, which is only the *unpaid* part of it: confusing the two makes a
school that collected every rupee on time look like it was never asked for anything. It costs one
extra accumulator on a loop that already had `inst.due_date` and `today` in hand.

The identity worth remembering, and the reason the pace figure adds something the old four-figure
line could not express:

```
shortfall = overdue − prepayments
```

With nobody paying early the two agree exactly. With prepayments the school is *less* behind than
its overdue figure alone suggests.

### The device

V1-15's, reused so fees reads with the habit the syllabus board already taught — arc = what came
in, tick = where the schedule says you should be, gap = the finding.

**The year is ONE ring, not three.** The three figures the founder asked for share one
denominator, so three rings would draw the same track three times and the "total billed" one
would be a full circle saying nothing. And `collected` can *exceed* `due_by_today` when families
pay in advance — a marker expresses that; stacked arcs would read as an error. **Quarters get one
ring each**, because those genuinely are independent scopes.

### 🔴 Two defects found

1. **The dashboard fee block was the last surface on the old fee arithmetic.** `FeeService.summary()`
   — four fields, no quarters, `opening_dues` excluded — while `/fees` rendered
   `CollectionService.board()`. That contradicts `collection.py`'s own docstring and repeats
   exactly what V1-12 fixed for Lucy. It also computed `outstanding = total − collected` **in the
   browser**, merging pending with overdue — the blend `Collection` has no `outstanding` property
   in order to prevent (`S-163`).
2. **`PATCH /fees/installments/{id}/due-date` 500'd on every call** — routed to
   `FeeService.update_due_date` since P0-D, and the method never existed. V1-13's no-dead-ends
   sweep hunted orphan *client methods* and orphan *GET* routes; this was neither, so nothing
   surfaced it. It matters now because an instalment with no due date is `unscheduled`, and this
   route is the only way to resolve the state the new board names — a board that names a problem
   whose only fix is a 500 has made the admin's day worse. Implemented.
   ⚠️ **It still has no web caller.** Deliberately left: the founder deferred fee-module
   gap-filling to a later deep pass, and building the editor now would be scope creep against
   that. Wire it then.

### Rules kept

Not-due-yet is **neutral, dashed and a word**, never a bold 0% and never red. `shortfall` floors
at zero. `carried` stays its own line (`D-88`). `collected / pending / overdue` are still three
figures that nothing adds. The fee fence holds: `/fees/collection` is admin-only and the
dashboard page is `AuthGuard allow={["admin"]}`, so a teacher never reaches the component, let
alone the request — asserted in both directions.

### Also

`TrendLine` gains `yFormat` (the curve's y-axis was rendering clipped as `)0₹` — a rupee figure
plus a suffix is wider than the 44px gutter) · `by_class` was an unsorted, uncoloured text table
of seven numeric fields and is now ranked rows with bars, both denominators intact · `shortMoney`
is the lakh/crore form for ring centres.

Found by looking: the year ring and its ledger were side by side at 360px, leaving the ledger
~150px — labels wrapped one word per line and the amounts collided with them. They stack below
`sm` now.

`test_fees_v1_18.py` (11). Reviewed at 1440px and 360px in both themes against a seeded year with
all four quarter states present (settled / behind / not-due / not-due).
