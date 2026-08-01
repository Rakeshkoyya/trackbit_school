# Admin Dashboard v3 — the school's operating board

**Status:** revision 2 — reconciled with the code, in build.
**Date:** 2026-07-29 (rev 1) · revised 2026-07-29 after SF-1 + HW-1 shipped · **Cite as** `DASH3 §x.y`
**Conflict order:** founder decision > this doc > `SPRD2` > architecture doc > SPRD v1.

---

## 0. What this is

Today `/dashboard` is a *briefing*: it reads well and tells the admin how the day
went. It is not yet a place to **work**. This plan turns it into the admin's daily
operating board — six modules, each with the same three layers:

1. **The shape** — the module as charts, at school level.
2. **The drill-down** — school → class → subject → teacher/student, so a red number
   resolves to a name.
3. **The action rail** — every red row carries a button that *does the thing*, in
   the app, without leaving the board.

The briefing stays and stays first. It is what an admin reads in ten seconds; the
modules are where they go when it says something is wrong.

---

## 0.1 Revision 2 — what changed, and why

Rev 1 was written **before** `SF-1` (staff attendance · timesheet · leave) and
`HW-1` (per-student homework) shipped on 2026-07-29. Three of its seven
prerequisites were then built — two of them **differently and better** — and one
whole module it had fenced out (leave) now exists. Building rev 1 as written would
have produced a second staff-attendance table, a second homework capture surface,
and a workload board inferred from task categories when real timesheet capture is
sitting right there.

So this revision reads the code first. The table is the honest delta:

| Rev-1 item | Reality in the code | What this revision does |
|---|---|---|
| **PR-1** `staff_attendance` — teacher **self check-in**, `status in/late/absent/leave`, `source self/admin/derived` | **Built differently (SF-1).** `staff_attendance_days` (org × date, "it was taken") + `staff_absences` (absentees only). **Admin-marked, no self check-in. Present/absent only — no late tier** (founder call). Approved leave pre-unticks. | Drop `POST /staff/check-in` entirely. The staff donut becomes **present · absent · on leave · not marked yet** — `not marked` is information, not a failure, and there is no "hasn't tapped yet" state to model. |
| **PR-3** `homework_results` | **Built (HW-1)**, plus `homework_checks.checked_by_member_id` + `UNIQUE(assignment_id)`, plus the whole read side: `services/homework.py` already does class/subject roll-ups, repeat non-doers with the responsible teacher, teacher checking discipline, perfect-week, most-improved. | M4 stops re-implementing §4.4 and becomes a **thin wrapper**: delegate to `HomeworkService.overview`, add only the daily time series it cannot give. Two sets of homework numbers that could disagree is the failure mode being avoided. |
| **PR-4** work types **over task categories** | **Obsolete.** `core/work_types.py` exists, but over `timesheet_entries` — real capture, not inference. | §4.3 reads the timesheet. A free period with no entry is `unfilled`, which is itself the finding, and something task categories could never have told us. |
| **PR-7** school clock | **Built (SF-1)** — `services/school_clock.py`: `periods_of` · `breaks_of` · `current_period_no` · `phase` · `today_in`. | Reuse as-is. |
| **§11 "Leave system — out of scope"** | **Built (SF-1).** `leave_requests` + append-only `leave_request_events`, org policy (`leaves_per_year`/`leaves_per_month`), working-day counting, over-policy **flagged not blocked**. | Leave is **in**, on the Staff tab: who is away and why, the pending queue, and leave pressure over the term. |
| **PR-0** Follow-ups board · **PR-2** `period_substitutions` · **PR-5** `followup_actions` · **PR-6** batched forecast | Not built. | Build all four. These are the only genuinely new pieces. |
| **§8** migration: 4 new tables | Two of the four already exist. | **One migration, two tables**: `period_substitutions` + `followup_actions`. |
| **§10.5** "do admin staff check in too?" | Moot — the admin marks everyone, teachers and office alike. | Question removed. |

**Two structural changes that follow from the above.**

- **Staff moves out of the Attendance tab.** Rev 1 §4.1 layer 3 put staff absence
  under Attendance. With SF-1 there is now a whole staff domain — presence, leave,
  timesheet, load — so Attendance is **students**, and **Staff** is the people tab:
  presence, the absence blast radius with the substitute rail, the leave queue, the
  live period board and week load. Attendance keeps a one-line staff strip that
  links across.
- **The dashboard does not duplicate the `/staff` area.** `/staff` (mark
  attendance), `/staff/leave` (approve) and `/staff/today` (the period grid) are
  the *operational* screens and stay exactly as they are. The dashboard's Staff tab
  is the *analytical + decision* surface — who is free right now, is the load
  balanced, what breaks today because someone is out — and links to those screens
  rather than re-rendering them.

---

## 1. Where it lands

`/dashboard` becomes a route-based tab area, exactly like `/plan`, `/students`,
`/tasks` and `/setup` already are (`components/layout/sub-tabs.tsx` + a per-area
`layout.tsx`):

| Tab | Route | What it is |
|---|---|---|
| Overview | `/dashboard` | Today's briefing (unchanged) + one summary card per module, each linking into its tab |
| Attendance | `/dashboard/attendance` | **Students**: pulse, period-capture heatmap, absence streaks + action rail |
| Syllabus | `/dashboard/syllabus` | Coverage against plan: year / term / exam checkpoint × school / class / subject / teacher |
| Staff | `/dashboard/staff` | Presence · leave · live period board · load balance · absence blast radius + substitute rail |
| Homework | `/dashboard/homework` | Completion by class + subject, checking discipline, repeat non-doers |
| Tasks | `/dashboard/tasks` | Assigned-task health + daily classroom duties |
| Exams | `/dashboard/exams` | Test results: school → class → subject, across cycles |

Admin-only (`AuthGuard allow={["admin"]}`), as `/dashboard` is now.

**Why tabs and not one long page.** The overview must stay openable-in-ten-seconds.
Six modules of charts on one scroll destroys that, and it is also the wrong
information architecture: the admin arrives with a *question* ("who's out today?"),
and a tab is an answer to a question. The overview's summary cards keep the "I
don't know what to look at" path working.

---

## 2. Reality check — what the schema can and cannot answer

| Module | Capture that exists | What was missing |
|---|---|---|
| **Attendance — students** | `class_periods` + `attendance_exceptions` (exception-shaped, P1v2); `DashboardService._attendance_pulse` rolls 14 days + per-class today | Daily per-student roll-up, consecutive-absence streaks, the period-capture heatmap, the action rail |
| **Attendance — staff** | **SF-1**: `staff_attendance_days` + `staff_absences`, `leave_requests` | Nothing in capture. Only the *reads*: blast radius, and cover |
| **Syllabus** | `PlannerService.forecast` per class-subject; `exam_fit` per class; `ExamPortion.upto_topic_id`; actuals in `lesson_logs.topic_id` + `coverage` | Batched org-wide forecast (PR-6); roll-up by **teacher**; ranking with guards |
| **Staff load** | **SF-1**: `timesheet_entries` + `services/school_clock.py`; `timetable_slots` | Org-wide teacher-week; the live board; work-type buckets |
| **Homework** | **HW-1**: `homework_results` (exception rows) + `homework_checks` (with `checked_by`), and `services/homework.py` on top | Only the daily time series |
| **Tasks** | `task_instances` + `task_events` + `ClassroomService.compliance` | An aggregate service; per-teacher duty completion |
| **Exams** | `assessment_cycles` + `assessment_scores` + `ExamService.feed` + `AssessmentService.class_analysis` | School-level and cross-class roll-ups |
| **Cover for an absent teacher** | nothing | `period_substitutions` (PR-2) |
| **"Did we already remind them?"** | nothing | `followup_actions` (PR-5) |

---

## 3. Prerequisites — the four that are actually left

### PR-0 — Where a follow-up task goes

One seeded org board **"Follow-ups"** — public, `task_scope='assigned'`, so each
teacher sees only their own rows while the admin sees all. Every action-rail task
lands there, assigned to a real person.

**Why not a personal board per teacher:** a private personal board collides with
architectural law 5 — *admins do NOT see private boards they aren't members of* —
so the admin would be firing tasks into a board they could never then track.
`services/home.py` filters Today by `assignee_id`, so the teacher's experience is
identical either way.

Created on demand by `ensure_followups_board`, and seeded for the demo org.

### PR-2 — Period substitutions (new table)

`period_substitutions` — `(org_id, date, class_id, period_no, class_subject_id,
absent_member_id, substitute_member_id, created_by_member_id, note, cancelled_at)`,
**unique on the live rows only** (`WHERE cancelled_at IS NULL`), so a cancelled
cover never blocks a re-cover.

Exactly the P2 shape: **the substitution is the plan,
`class_periods.teacher_member_id` is the actual.** Assigning cover does not claim
the period happened — it puts the period in someone's day so it can.

Three read-side changes, all small and all necessary or the feature is a lie:
- `ClassroomService.my_day` unions today's cover into the teacher's periods, tagged
  `substituting` + `covering_for`.
- `assert_can_take_class` accepts `(on_date, period_no)` and passes a live
  substitute — otherwise the period appears in My Day and refuses to open.
- The substitute is notified through the existing dispatcher (`substitute` type,
  **push-only**: cover is decided minutes before the bell and an email arriving
  after the period is worse than nothing).

The service refuses a substitute who is already teaching, already covering, or
marked away — with the reason, because the admin needs to know which.

### PR-5 — The action audit trail (new table)

`followup_actions` — append-only (law 3), one row per rail button press:
`(org_id, kind, subject_type, subject_id, actor_member_id, target_member_id,
detail JSONB, created_at)`.

`kind` ∈ `guardian_reminded · followup_assigned · substitute_assigned ·
task_reassigned · task_extended · nudged`.

This exists for one reason above all others: **so the same parent is not reminded
three times in one morning** by three people looking at the same red row. Each rail
row reads today's history for its own subject and renders "already reminded". Same
discipline as `class_periods.alerted_at`.

### PR-6 — Batched org-wide forecast *(performance, load-bearing)*

`DashboardService._rag_rows` called `PlannerService.forecast(m, class_id)` **in a
loop over every class** — one calendar read, two `IN()` queries and a term read per
class, each a round-trip to a remote Postgres. ~80 round-trips for one card in a
20-class school.

`PlannerService.forecast_org(m, year_id)` does the identical computation with the
loop inside a single query set. `_rag_rows` is now a one-line call to it, so the
existing overview gets faster as a side effect, and the syllabus module is
affordable at all.

---

## 4. The six modules

Every metric is a **computed join over existing capture** (P5) — nothing here
stores a derived number, so an edit anywhere shows up immediately and can never go
stale.

### 4.1 — Attendance (students)

**Layer 1 — the picture.**
- Present % over 14 days — area (`DashboardService.attendance_pulse`, reused so the
  overview and this tab can never disagree)
- Attendance by class today — row bars
- **Period capture heatmap** — class × period for today. The single most useful
  thing on the tab: it separates "attendance is bad" from "attendance was never
  taken". Four cell states, and the distinction between them is the whole point:
  `free` (nothing scheduled) · `pending` (scheduled, not marked) · `marked` ·
  `not_held` (the teacher said the class did not happen — captured, not missing).
- A staff strip (present / absent / on leave / not marked) linking to the Staff tab.

**Layer 2 — the red list: students absent 3+ days.** Stated precisely, because it
decides who gets a phone call:
- A student is **day-absent** only when absent in *every marked period* of that day.
  Absent in some but not all is **partial** (came late, left early) and never counts
  toward a streak — the same rule `services/timeline.py` and the parent portal use,
  so the parent portal and this board can never disagree.
- A streak counts consecutive **school days**, walked over *that class's* marked
  days. Days the class marked nothing are **skipped, not counted as present**: the
  school's gap in capture is not evidence the child came in. Non-working days and
  holidays are skipped via the calendar, so Friday–Monday is a 2-day streak, not 4.
- Threshold ≥3 → red row. Constant in code, not a setting (§10.4).

Each row carries **Remind guardian** (plain text, **never band information** — P4)
and **Assign follow-up** (to the class teacher, pre-titled). Both go through the
rail, so both render "already done today" instead of firing twice.

**New backend:** `services/insights/attendance.py`.

### 4.2 — Syllabus tracker

**Checkpoint (vertical):** whole year · term · **per exam**. The exam checkpoint is
the one schools manage against, and `PlannerService.exam_fit` already computes it
per class; this merges it school-wide.

**Scope (horizontal):** school → class → subject → teacher. Note the shape: one
subject may have several teachers across classes, so **teacher is not a child of
subject** — it is a *re-pivot of the same class-subject rows*. The UI is a scope
switcher, not a nested tree.

**Per node:** topics planned · topics taught (`lesson_logs` with `topic_id`,
`coverage='partial'` weighted at half) · % complete · RAG · weeks behind ·
projected finish. States `unplanned` / `unallocated` / `unestimated` are shown **as
themselves, never folded into a colour** — hard-won in V2-P11 and it must not
regress.

**Ranking, with guards.** A class is ranked only with ≥3 rated class-subjects; a
teacher only with ≥3 **and** ≥10 logged periods. Below that the node reads *"not
enough data yet"* and carries its numbers without a rank. The framing is **"needs
support" / "ahead of plan"**, never a league table: a pace number reflects timetable
disruption, syllabus size and class composition at least as much as it reflects the
teacher, and the sample size is shown next to every rank.

**New backend:** `services/insights/syllabus.py`. **Prerequisite:** PR-6.

### 4.3 — Staff (presence · leave · load · cover)

This is the tab that changed most in revision 2, because SF-1 gave it real capture.

**Right now** — the live board off the school clock:
> Period 4 · 11:20–12:00 — **9 teaching · 4 free · 2 absent**

with every list named, and what the free ones are doing read from
`timesheet_entries` (not inferred from tasks). It degrades honestly: `before` /
`after` school, `break` between periods, `holiday` on a closed day, and `unset`
when the school never entered its timings — never a guessed period.

**Who is out, and what it breaks.** For each absent member, from today's timetable:
- the periods they were due to teach, with class + subject
- for each, **free teachers at that period**, ranked: teaches the same subject
  elsewhere > teaches this class > lightest teaching load today — with the reason
  shown, because the rank is a suggestion and the admin still chooses
- **Assign substitute** → `period_substitutions` (PR-2), notifies them, and the
  period appears in their My Day

For an absent **admin**, the blast radius is their work: tasks due today or already
overdue, criticals first, with *Reassign* / *Extend*.

**Leave** (new since rev 1): the pending queue with its policy warnings, who is on
approved leave today, and leave pressure this month. Deciding still happens on
`/staff/leave` — this surfaces it and links across.

**The week:** teaching periods per teacher against the org mean (computed over
people who teach at all, so office staff don't drag it to zero and flag everyone as
overloaded), with over/under flags at ±20%. Work-type buckets across the week. A
per-teacher day strip of period cells (class / work / free / substituting /
absent), and `unfilled_free_periods` — free periods today with no timesheet entry,
which is the timesheet's own adoption number.

**New backend:** `services/insights/workload.py`, `services/substitution.py`.

### 4.4 — Homework

**Delegates to `HomeworkService` (HW-1).** Completion today and over the window, by
class and by subject; teacher checking discipline (`unchecked_overdue` counts only
past-deadline homework, so homework set an hour ago is not a failure); repeat
non-doers with the responsible teacher; perfect-week and most-improved.

This module adds only the **daily series** — the shape over time a roll-up cannot
give — and the action rail on the red rows.

`not_checked` rides all the way through: a missing `homework_checks` row means the
teacher never went through it, is counted separately, is excluded from every
completion figure, and is **never rendered as a student's miss**.

**New backend:** `services/insights/homework.py` (thin).

### 4.5 — Tasks

**Assigned work:** open / completed / overdue at school level; completion over 14
days; by board and by assignee. Overdue and `is_critical` rows listed red,
criticals first, each with *Reassign* / *Extend* / *Nudge*.

**Daily classroom duties** — My Day *is* a task list. Per teacher, the four duties
period capture implies: **attendance marked · lesson logged · homework set · checks
confirmed**, as a completion percentage, denominated by *periods they were actually
due to teach* — a teacher whose classes were all cancelled cannot read as 0%. A
period covered by a substitute counts toward the **substitute's** duties, not the
absent teacher's (§10.3): the substitute did the work.

This block is read-only. The fix for an unlogged period is the teacher opening My
Day, not the admin creating a task about it; *Nudge* is the right escalation.

**New backend:** `services/insights/tasks.py`.

### 4.6 — Exams

School average → class average → subject average, per cycle and across cycles.
`AssessmentCycle` already carries the types (`chapter_test`, `class_test`,
`slip_test`, `objective`, `band_test`, term exams), so *weekly CET* vs *main exam*
is a filter, not a schema change.

Per exam: average %, participation (scored / roster), best and worst class and
subject. Across cycles: subject trajectory lines. Reuses the marks in
`components/school/class-analytics.tsx` so the two screens read as one system.

**Bands stay staff-only (P4)** throughout.

**New backend:** `services/insights/exams.py`.

---

## 5. The shared spine — the action rail

One module, `services/insights/actions.py`. Each action does two things: calls the
**existing** service (never re-implements a write), and appends a `followup_actions`
row.

| Action | Existing service it calls | Guard |
|---|---|---|
| Remind guardian | `notify_guardian.notify_guardians` | admin; plain text; never band info (P4) |
| Assign follow-up | `TaskService.create` | admin; Follow-ups board (PR-0) |
| Assign substitute | `SubstitutionService.create` | admin; refuses a substitute who is teaching / already covering / away |
| Reassign task | `TaskService.reassign` | admin |
| Extend due date | `TaskService.edit` | admin |
| Nudge | `NudgeService.nudge` | admin; already dedupes within 4h |

**Idempotence:** each rail row reads its own `followup_actions` history for today —
in **one query for the whole list**, not one per row — and renders "already
reminded / already assigned" rather than firing twice.

---

## 6. Backend architecture

```
api/app/services/insights/
    __init__.py
    attendance.py     M1 — student roll-ups, capture heatmap, streaks
    syllabus.py       M2 — coverage across both axes, ranked with guards
    workload.py       M3 — live board, presence, teacher week, work buckets
    homework.py       M4 — thin wrapper over HomeworkService + daily series
    tasks.py          M5 — task health + per-teacher duty compliance
    exams.py          M6 — result roll-ups
    actions.py        the shared rail (§5) + the Follow-ups board
api/app/services/substitution.py        PR-2
api/app/models/insights.py              PR-2 + PR-5 tables
api/app/schemas/insights.py
api/app/api/v1/endpoints/insights.py    → /insights/*
```

Already in the codebase and **reused, not rebuilt**: `services/school_clock.py`,
`core/work_types.py`, `services/staff_attendance.py`, `services/leave.py`,
`services/timesheet.py`, `services/homework.py`.

`DashboardService` is **not touched** except for PR-6 swapping `_rag_rows` onto the
batched forecast and exposing `attendance_pulse` publicly. The overview, its alerts
and its charts keep working exactly as they do.

**Endpoints** (all `require_admin`):

```
GET  /insights/cards                 overview summary cards
GET  /insights/attendance            students: pulse + capture grid + staff strip
GET  /insights/attendance/streaks    students absent ≥N school days, with rail state
GET  /insights/staff                 presence + leave queue + live board + week load
GET  /insights/staff/{member_id}/impact   affected periods + ranked substitutes + tasks
GET  /insights/syllabus              scope=school|class|subject|teacher, checkpoint=year|term|exam
GET  /insights/homework              roll-ups + daily series
GET  /insights/tasks                 task health + per-teacher duty compliance
GET  /insights/exams                 roll-ups, filterable by cycle type
GET  /insights/actions/history       the audit trail
POST /insights/actions/{kind}        the rail (§5)
POST /insights/substitutions/{id}/cancel
```

**Query discipline.** Every roll-up is grouped SQL with `IN()` batching — no
per-class or per-teacher loops. The one deliberate exception is the exam checkpoint
(`exam_fit` walks each class's own syllabus ordering and cannot be one grouped
query); it is computed only when that checkpoint is selected.

**Lucy.** Each new read is registered in `services/lucy/registry.py` as a read tool,
so "which students have been absent three days?" works in chat on day one.

**Daily report.** `services/daily_report.py` gains two ambiguity rules now that the
capture exists: *staff absent with periods uncovered* and *homework not-done
streaks*.

---

## 7. Frontend architecture

```
web/src/app/(app)/dashboard/
    layout.tsx          SubTabs (7 tabs)
    page.tsx            Overview — briefing + module summary cards
    attendance/page.tsx  syllabus/page.tsx  staff/page.tsx
    homework/page.tsx    tasks/page.tsx     exams/page.tsx
web/src/components/insights/
    module-card.tsx     the overview summary card
    action-rail.tsx     red row + buttons + "already done today" state
    period-heatmap.tsx  class × period capture grid
    now-board.tsx       live period board
    scope-switcher.tsx  school / class / subject / teacher
```

**Charts go through `components/charts` — no exceptions and no new chart library.**
That kit is the dataviz-validated palette plus `ChartCard` / `StatTile` /
`MeterBar`, lazily loaded as one shared chunk. A second charting path would fork the
visual language across screens that must read as one system. A missing mark gets
added *to the kit*.

---

## 8. Migration

One migration, `e0f1a2b3c4d5`, on head **`d8e9f0a1b2c3`** (HW-1):

| table | purpose |
|---|---|
| `period_substitutions` | PR-2 |
| `followup_actions` | PR-5 |

Plus an `org_isolation` RLS policy on each (law 2) and the usual `org_id` FK with
`ondelete='CASCADE'`. Rev 1's `staff_attendance` and `homework_results` are already
in the schema (SF-1 / HW-1) and are **not** recreated.

**No column is dropped.**

---

## 9. Build order

| # | Packet | Contents | Done when |
|---|---|---|---|
| 0 | **DASH3-P0** | Migration (2 tables + RLS) · PR-6 batched forecast · PR-2 substitutions + My Day/period-card read-side · PR-0 Follow-ups board · the rail | Migration applies; `test_planner` + `test_dashboard` still green; a substitute sees and can open the period |
| 1 | **DASH3-P1** | Six insight services + schemas + `/insights/*` endpoints | `ruff` clean; every endpoint answers on the demo org |
| 2 | **DASH3-P2** | Tab shell + overview module cards | tsc + eslint + build clean; overview unchanged |
| 3 | **DASH3-P3** | Attendance tab — heatmap, streaks, rail | guardian reminder is idempotent within a day |
| 4 | **DASH3-P4** | Staff tab — live board, presence, leave, load, substitute rail | correct outside school hours and on a holiday |
| 5 | **DASH3-P5** | Syllabus tab — both axes, exam checkpoints, guarded ranks | `unplanned`/`unallocated` never render as a colour |
| 6 | **DASH3-P6** | Homework · Tasks · Exams tabs | duty denominator = periods actually due |
| 7 | **DASH3-P7** | Lucy tools · daily-report rules · tests · seed enrichment | touched suites green; every tab populated on the demo org |

---

## 10. Decisions

**10.1 — Follow-up destination.** One seeded **"Follow-ups"** board
(`task_scope='assigned'`). *Settled — §3 PR-0 explains the law-5 problem with
personal boards.*

**10.2 — Teacher ranking.** Framed **"needs support / ahead of plan"**, with the
numbers and the sample size always visible, and a minimum-sample guard. *Settled —
a league table of people invites decisions the data cannot support.*

**10.3 — Does a substitution stick?** **Yes.** Capture by a substitute counts toward
*their* duties and away from the absent teacher's. The substitute did the work.

**10.4 — Thresholds.** Constants in code for v1: absence streak 3 school days,
homework streak 2 consecutive, low completion 60%, attendance red <80%, load
over/under ±20% of the org mean. Promote to settings once there is real usage to
tune against.

**10.5 — ~~Staff attendance for admin staff~~.** Moot: SF-1 has the admin mark
every active member, teaching or not.

---

## 11. Deliberately out of scope

- **C-band mentor assignment** — the "every C student is assigned to a teacher" link
  does not exist yet. Its own small packet before it can appear on the staff board.
- **Parent-facing anything** — the portal is read-only and stays that way. No band
  tier, no ranking, no teacher performance data goes near it (P4, and the §11 fences
  in `CLAUDE.md`).
- **Payroll / HR / biometric attendance devices** — fenced out. SF-1 records
  presence and leave for *operational* reasons (who covers period 4); it is not the
  start of an HR module.
- **Report-card designer, test authoring** — fenced out.
