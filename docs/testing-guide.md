# TrackBit School — Testing Guide

*For the testing team. Covers environment setup, seeded test data, and scenario-by-scenario
test cases with expected results. Scope = implemented phases P0–P3 (see "Out of scope" at the end).*

Report bugs with: **scenario ID · steps taken · expected · actual · screenshot · browser/viewport**.
Severity: **S1** data loss/security · **S2** flow blocked · **S3** wrong behavior with workaround · **S4** cosmetic.

---

## 1. Environment setup

Backend (from `api/`, Python 3.12 + uv; needs PostgreSQL — see `CLAUDE.md` for the local
docker option on port 5434):

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run python -m scripts.seed        # loads the demo school below (idempotent — safe to re-run)
uv run uvicorn app.main:app --port 8000
```

Frontend (from `web/`): `npm install`, `.env.local` → `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`,
`npm run dev` → http://localhost:3000.

> **Watching notifications:** WhatsApp/guardian messages are a **console stub** — the exact
> message prints in the uvicorn terminal. That terminal output IS the expected result for
> notification scenarios. Email uses the same stub unless a Resend key is configured.
> After backend code changes the server must be restarted (it runs without --reload).

### Demo logins (all password `demo1234`)

| User | Email | Role | Landing after login |
|---|---|---|---|
| KC | kc@demo.trackbit.app | Director (admin) | Dashboard (`/insights`) |
| Priya | priya@demo.trackbit.app | Coordinator | Home (`/home`) |
| Ramesh | ramesh@demo.trackbit.app | Teacher | My Day (`/classroom`) |
| Anil | anil@demo.trackbit.app | Teacher | My Day (`/classroom`) |

**No office user is seeded.** Create one for T-ROLE/T-FEES: as KC → Members → invite with role
**Office** → open the invite link in an incognito window → set password.

### Seeded school (org "SHANA Ops (demo)", year 2026-27, Terms 1 & 2)

- **Classes:** 6-A (class teacher Ramesh), 6-B (Anil), 7-A (Priya).
- **Subjects/periods per week:** English 6, Mathematics 6, Science 5, Social Studies 4, Hindi 4.
  Ramesh teaches Math + Science; Anil teaches the rest (all classes).
- **Calendar:** Independence Day 15 Aug · Teachers' Day (celebration) 5 Sep ·
  Half-yearly Exams 21–30 Sep · Dussehra Break 19–23 Oct.
- **Plan:** 6-A Science has a full syllabus (Food & Nutrition / The Living World / Matter)
  with an **approved** baseline plan → the forecast view renders.
- **Students:** roster in 6-A/6-B, admission numbers from A601, each with a guardian.
- **Session:** "Homework Class 6A" (owner Ramesh) with roster + past meeting records.
- **Assessments:** "Term-start diagnostic" cycle (5 Apr) with scores; skill areas seeded.
- **Fees:** structure for class 6 with installment templates; students enrolled with payments.
- **Boards:** Daily Ops (public), Admissions (private), Maintenance, Housekeeping (templates).

---

## 2. Authentication — T-AUTH

**T-AUTH-01 Login ok.** Login as each demo user → lands on the role's landing page (table above).
**T-AUTH-02 Login bad password.** → clear error, no crash, stays on login.
**T-AUTH-03 Invite → set password.** KC → Members → invite (any role) → open link incognito →
forced to set password before entering the app → after set, lands per role.
**T-AUTH-04 Forgot/reset.** Request reset for ramesh@ → link (console stub in dev) → set new
password → old one no longer works.
**T-AUTH-05 Logout.** Account menu → logout → deep links redirect to `/auth/login`.

## 3. Roles & access — T-ROLE (security-critical: any failure is S1)

Sidebar per role must be exactly:

| Role | Sidebar items |
|---|---|
| Director | Home, Boards, Done, My Day, Sessions, Planner, Students, Assessments, Fees, Dashboard, Setup, Members |
| Coordinator | Home, Boards, Done, My Day, Sessions, Planner, Students, Assessments, Dashboard, Setup |
| Teacher | Home, Boards, Done, My Day, Sessions, Planner, Students, Assessments |
| Office | Home, Boards, Done, Fees |

**T-ROLE-01** Verify the table above for all four roles (mobile bottom tabs = first 5 items).
**T-ROLE-02 Teacher must not reach fees.** As ramesh@, navigate directly to `/fees` and
`/fees/structures` → blocked (redirect or error screen), AND API calls return 403 (check
network tab). Repeat for `/insights`, `/members`, `/academics` (Setup).
**T-ROLE-03 Office must not reach academics.** As office user: direct-URL `/classroom`,
`/planner`, `/students`, `/assessments`, `/insights` → all blocked, API 403.
**T-ROLE-04 Coordinator: no Fees, no Members.** Direct-URL `/fees`, `/members` → blocked.
**T-ROLE-05 Org isolation (RLS).** Register a brand-new org via `/auth/register` → it must see
zero SHANA data anywhere (students, boards, fees, dashboard). Any leak = S1.
**T-ROLE-06 Bands never on parent surfaces.** Trigger homework notify (T-CLASS-04) and inspect
the stubbed guardian messages in the console: no mention of tier/band anywhere.

## 4. Setup / master data — T-SETUP (as KC, on Setup screen)

**T-SETUP-01** Create subject; rename; it appears in class-subject assignment.
**T-SETUP-02** Create class 8-A with class teacher → appears in Students filter + Planner.
**T-SETUP-03** Assign subjects to 8-A with periods/week; edit a periods value → persists.
**T-SETUP-04** Skill areas: add "Grammar", rename, verify it appears in a new diagnostic cycle grid.
**T-SETUP-05** Terms: dates edit; invalid range (end before start) → validation error, not saved.

## 5. Students & roster — T-STU

**T-STU-01** Add student manually (admission no, name, class 6-A) + guardian with phone →
appears in directory, searchable.
**T-STU-02** Duplicate admission number → clear error.
**T-STU-03 Roster import.** Prepare a small xlsx (name / admission no / class / guardian phone
columns with slightly odd headers). Students → Import → mapping preview shows the heuristic's
guesses → correct one mapping manually → commit → students exist. Nothing saved before commit.
**T-STU-04 Import bad file.** Upload a random non-roster xlsx / a .png → graceful error.
**T-STU-05 Profile.** Open a seeded 6-A student → Overview (class, guardians), skill/band info
renders from the diagnostic; session attendance visible for Homework Class 6A members.

## 6. Planner — T-PLAN

**T-PLAN-01 Effective days.** Note the effective-teaching-days figure → add a 3-working-day
event ("Sports Meet", affects teaching) → figure drops accordingly; delete it → restores.
**T-PLAN-02 Syllabus entry.** For 6-B Science, add a unit; paste a multi-line chapter text →
split into topics → edit one → save.
**T-PLAN-03 Draft.** 6-B Science → Draft → topics distributed across weeks, respecting
holidays/exam blocks (no topics placed in the Sep 21–30 exam block weeks beyond capacity).
**T-PLAN-04 Adjust + approve.** Move a topic to another week → Approve → baseline locked
banner; entries no longer freely editable as draft.
**T-PLAN-05 Forecast honesty (P2).** On seeded 6-A Science (approved + some logs): forecast
shows baseline vs projected. Log two more topics as covered (T-CLASS-02) → projection improves
WITHOUT any plan rows changing.
**T-PLAN-06 Event absorption.** Add a week-long event overlapping upcoming 6-A Science
periods → forecast worsens/re-dates; baseline unchanged.

## 7. Classroom — T-CLASS

**T-CLASS-01 My Day.** As ramesh@: today's classes listed with this week's planned topic
pre-filled; log state visible without scrolling at 360px width.
**T-CLASS-02 Quick log paths.** (a) Tap Covered on the pre-filled topic — count taps: ≤ 3.
(b) "Partially". (c) "Different topic" → picker → ≤ 2 extra taps. Each writes a log entry
visible in the class history.
**T-CLASS-03 Duplicate log.** Log the same class/topic/date twice → second attempt is
rejected or merged gracefully (no duplicate rows in history).
**T-CLASS-04 Homework → guardian stub.** Enter homework text on a 6-A class → save → uvicorn
console prints one stubbed WhatsApp message **per guardian** of 6-A with subject + text.
Opt-out guardian (if flagged on a student) receives none.
**T-CLASS-05 Homework check.** Next day (or same day) enter "did it" count via stepper →
shows on the class card and later on the dashboard homework health.
**T-CLASS-06 Compliance.** As priya@ → Classroom → Compliance: pick yesterday → un-logged
class-periods show as gaps; today's logged ones (from T-CLASS-02) show as done.

## 8. Sessions — T-SESS

**T-SESS-01 Create.** As anil@ create session "Reading Club 6B", weekdays + time, add 5
students from 6-B → appears in his Sessions list; NOT in ramesh@'s.
**T-SESS-02 Capture ≤ 60s.** As ramesh@ open Homework Class 6A → today's meeting → tap
through 10+ students (present / late+minutes / absent), homework ticks, ONE batch photo →
Done. Time it: a practiced run must be under 60 seconds.
**T-SESS-03 Evidence.** The batch photo attaches to the meeting (not per student); reopening
the meeting shows the saved record read-only or editable-with-audit.
**T-SESS-04 Director view.** As kc@ next: Dashboard shows the session record (attended /
late / homework counts) for that date.

## 9. Assessments & bands — T-ASSESS

**T-ASSESS-01 Cycle + grid.** As kc@ or priya@: create unit-test cycle for Term 1 →
score grid (students × subjects) → enter marks for 6-A → save as pending verification.
**T-ASSESS-02 Verify.** As priya@ verify the cycle → scores locked; edits after verify are
blocked or audited.
**T-ASSESS-03 Bands.** Bands tab for 6-A: suggestions derived from scores; override one
student's tier with a note → saved. Change it again → **history shows both entries**
(append-only — no overwrite). Any silent overwrite = S2.
**T-ASSESS-04 Intervention → tasks.** Create an intervention for a C-tier student (goal +
2 checklist items) → recurring tasks appear for the class teacher (ramesh@ sees them on
Home/Boards) → complete one → completion reflects back on the intervention view.
**T-ASSESS-05 Trends + weak-subject.** Enter a second cycle with clearly lower Math averages
for 6-A → Trends shows the drop → a weak-subject alert appears on the Dashboard alert feed.
**T-ASSESS-06 Skill profile.** Student profile → skills from the seeded diagnostic render
(radar/progress); re-test cycle adds a second point.

## 10. Fees — T-FEES (as kc@ and the created office user)

**T-FEES-01 Structure archive-on-replace.** Create a new structure for class 6 + category
already having one → old one becomes archived/inactive (still viewable), new one active.
**T-FEES-02 Enrol — 3 modes.** Enrol three students: (a) from structure (installments scale
proportionally), (b) custom schedule — must sum to net fee, wrong sum rejected, (c) lump.
**T-FEES-03 Payment math.** Record a partial payment on an installment → status partial;
complete it → paid; an unpaid installment with due date in the past shows **overdue**
(computed — change nothing, just reload after due date logic).
**T-FEES-04 Undo = compensating entry.** Undo the payment from T-FEES-03 → installment
paid amount reverts AND the ledger shows BOTH the original payment and an `undo` row.
The original row must never disappear. Violation = S1.
**T-FEES-05 Discount rescale.** On a student with one paid + several unpaid installments,
apply a discount → only UNPAID installments re-scale; the paid one is untouched; totals
reconcile to net fee.
**T-FEES-06 Opening dues.** Set opening dues on a student → total payable = net fee + dues;
installment statuses unaffected by dues alone.
**T-FEES-07 Year switcher.** Switch academic year in the header → fee list scopes to that
year (empty for a fresh year).
**T-FEES-08 Ledger integrity.** Export/inspect a student ledger after T-FEES-02..05: every
money event (payment / undo / discount / edit) present, chronological, no gaps.

## 11. Tasks (regression) — T-TASK

**T-TASK-01** Create board + task, assign, complete → celebration fires; undo within toast.
**T-TASK-02** Recurring task (daily) on Daily Ops → appears on Home today; complete →
tomorrow's instance materializes (or trigger via ops endpoint).
**T-TASK-03** Maintenance board: create repair task with photo → photo persists.
**T-TASK-04** Private board (Admissions): teacher not a member sees nothing of it — including
as admin KC if not a member (deliberate rule) — verify per existing behavior.
**T-TASK-05** Alert→task: from a Dashboard alert press Create task → task pre-filled with
context lands on a board → completing it clears/updates nothing retroactively (alert history intact).

## 12. Dashboard — T-DASH (as kc@)

**T-DASH-01 RAG truthfulness.** 6-A Science (has logs) shows a plausible pace status; a
class-subject with an approved plan and NO logs shows behind/red as the term progresses.
**T-DASH-02 Cards.** Homework health reflects T-CLASS-05 counts; session card reflects
T-SESS-02; fees card shows collection summary — and is **absent for coordinator** (login as
priya@ → no fees card).
**T-DASH-03 Digest preview.** Open the Monday digest preview → contains top issues consistent
with the alert feed.
**T-DASH-04 Drill-down.** Click a RAG cell → class-subject detail (pace, logs, homework, marks).

## 13. UX budgets & general — T-UX

**T-UX-01** Teacher screens at 360×740 viewport: My Day, Quick log, Session capture — no
horizontal scroll, primary action reachable without scrolling.
**T-UX-02** Empty states: fresh org (from T-ROLE-05) — every module shows a helpful empty
state, never a blank screen or error.
**T-UX-03** Optimistic UI: with devtools network throttled/offline, tap Covered → UI responds
instantly; on failure the change rolls back with an error toast (no silently lost taps).
**T-UX-04** All lists paginate/scroll sanely with seeded volume; no layout break on the
students directory.

---

## 14. Out of scope for this round (deferred — do NOT file as bugs)

| Item | Status |
|---|---|
| Real WhatsApp delivery to guardians | Console stub only until WhatsApp Business keys are configured |
| 4 pm unlogged reminder, Saturday guardian summary, Monday digest **delivery** | Builders/previews exist; cron wiring not done |
| Fees-mode xlsx import (payment histories) | Deferred; roster (students) import IS in scope |
| Day-celebration suggestions (PL-6) | Not built yet |
| Teacher growth profile (DB-3) | v1.5 |
| Flutter mobile app | Out of scope — test the web app incl. 360px viewport |
