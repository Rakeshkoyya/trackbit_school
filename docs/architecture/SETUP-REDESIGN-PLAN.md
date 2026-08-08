# Setup redesign — one pack, one operator, one handover

**Status:** proposed, awaiting founder confirmation · drafted 2026-08-07
**Supersedes:** the 10-step wizard (`SPRD2 §5.1`, `web/src/app/(wizard)/setup/wizard/page.tsx`)
**Reference the founder supplied:** `docs/reference/Updated SHANA_Syllabus_ Tracker 2026-27.xlsx`

---

## 1. What is being asked

> Only the operator sets a school up. The school admin gets no setup screen at all —
> after handover, changes come back to us. Collect everything a school needs in **one
> template pack** the client fills in. Download templates → upload filled files →
> admin logins created → hand the school its keys.

Three separable changes:

| # | Change | Nature |
|---|---|---|
| A | Setup becomes **operator-only**, on both the screen and the wire | permissions |
| B | Ten typed steps become **one pack in, one review screen** | product surface |
| C | Syllabus stops being one file per class-subject and becomes **one sheet** | importer |

---

## 2. What the codebase already has (do not rebuild)

The direction is already half-built — the founder decision of 2026-07-20 is quoted in
`web/src/app/(app)/setup/layout.tsx`: *"schools no longer self-onboard; the TrackBit
operator runs setup and hands over credentials."*

| Already there | Where |
|---|---|
| Operator creates org + first admin (temp password, forced change) + operator membership | `services/platform.py::create_school` |
| Operator enters any school with a scoped session | `services/platform.py::enter_org` |
| Readiness report — 11 checks, each naming its **consequence** | `services/readiness.py` |
| `handed_over_at` stamp + `POST /platform/orgs/{id}/handover` | `endpoints/platform.py:80` |
| Shared analyse → confirm → commit ingestion envelope | `services/ingest.py` |
| Blank templates generated **from the importer's own field list** | `services/templates.py` |
| Three importers (students, staff, syllabus) + timetable import | `roster_import` · `staff_import` · `syllabus_import` · `timetable.py:293` |
| Whole-school timetable generator | `timetable.py::generate_year_grid` |
| Platform observance catalogue + annual xlsx import (holidays) | `observance_import.py` |

**So this is a consolidation, not a green field.** The work is: one workbook instead of
23 files, one validator across sheets, one screen instead of ten, and a real guard.

---

## 3. What the reference file teaches us

`SHANA_Syllabus_Tracker` — a real school's real working sheet — is worth more than the
spec here, because it is what schools actually produce.

| Observation | Consequence for us |
|---|---|
| **One sheet per class, all subjects in it** (`Subject` column) | Confirms the founder's call: one syllabus sheet is enough. We go one better — `Class` column too, so it is **one sheet for the school**. |
| **There is no `Topic` column.** Rows are chapters: `Ch # · Chapter Name · Est. Periods · Difficulty` | 🔴 Our importer *requires* `topic_title`. A school filling our template the way it already keeps its data would import nothing. **Topic must become optional** — a chapter with no topics becomes one topic named for the chapter. |
| `Est. Periods` per chapter, weighted by length & difficulty | Matches `SyllabusTopic.est_periods`. Blank = not sized (already correct in `rows_to_units`). |
| `Mentor` column repeats the teacher on every chapter row | Ignore it on the syllabus sheet. The teacher is owned by `Teaching Assignments` — one fact, one store (the `D-89` reasoning). |
| `Difficulty` (Light/Medium/Heavy) | ✅ **Dropped from the pack** (decided 2026-08-07). Correction to an earlier draft of this doc: `SyllabusUnit.difficulty` **does** exist as a nullable column — the reason to drop it is not storage but that the reference's own Read Me says `Est. Periods` is *"weighted by length & difficulty"*. The weight is already inside the number the planner uses, so a second column is one more thing the school must keep consistent for no gain. The column stays; the pack simply does not ask. |
| A Chapter-End Test planned after **every** chapter | Not an `exam_block`. Out of scope for setup; note it as a product question. |
| `Planned Week` / `Planned Start` pre-computed by the school | We *generate* this (`plan_schedule.py`). Do not import it — it would be a second planner. |
| A `Read Me` sheet with pacing rules, assumptions and a status legend | Copy the idea. Our pack gets a `Read Me` the school actually reads. |
| `Books & Coverage Flags` — "chapter not scanned", "confirm optional chapters" | This is the school's own gap list. Our validation report should read like this. |

---

## 4. The template pack

One workbook: **`TrackBit-Setup-Pack-<School>.xlsx`**. Generated from the same specs the
parser reads, so it cannot drift (`templates.py` already establishes this rule and
`test_setup_onboarding.py` already asserts the round trip).

Required sheets are marked ●, optional ○.

| # | Sheet | Columns | Feeds |
|---|---|---|---|
| 0 | `Read Me` | prose: what to fill, date format (dd/mm/yyyy), blank-means-not-known, who to ask | — |
| 1 | ● `School` | key/value: School name · Address · State · Board · Academic year label · Year starts · Year ends · **Tracking starts from** · Working days · Periods per day · First period starts · Period length (min) · Lunch after period · Lunch length · Parent portal (Yes/No) | `Organization`, `AcademicYear` (incl. `tracking_start_date` — the mid-year case, G1b), `period_times` |
| 2 | ● `Terms` | Term name · Exam name · Exam starts · Exam ends — **the term's own dates are derived** (D-10) | `Term` + its `exam_block` `CalendarEvent` |
| 3 | ● `Classes` | Class · Section · Class teacher (name) | `SchoolClass`, `class_teacher_member_id` |
| 4 | ● `Staff` | Name · Employee ID · Email · Phone · Date of birth · Role (Teacher/Admin) | `User` + `Membership` |
| 5 | ● `Teaching Assignments` | Class · Section · Subject · Teacher name · Periods per week | `Subject`, `ClassSubject` (teacher + weekly budget) |
| 6 | ● `Syllabus` | Class · Section · Subject · Term · Ch # · Chapter · Est. periods — **no Topic** (D-12) | `SyllabusUnit` + one `SyllabusTopic` per chapter |
| 7 | ● `Students` | Name · Admission No · Roll No · Class · Section · Date of birth · Category · Father name · Father phone · Mother name · Mother phone | `Student` + guardians |
| 8 | ○ `Timetable` | Class · Section · Day · Period · Subject | `TimetableSlot` |
| 9 | ○ `Calendar` | From · To · Name · Type (Holiday/Event — exams live on `Terms`) · Classes | `CalendarEvent` |
| 10 | ○ `Fees` | Class · Category · Total · Installment no · Installment name · Due date · Amount | `FeeStructure` |

**Changes from today's three templates**

- Staff loses the `Subjects Taught` packed string (`"6-A Mathematics x6; 7-A Mathematics x6"`)
  — a syntax schools mistype. Sheet 5 carries one assignment per row instead.
- Syllabus gains `Class · Section · Subject` and loses its per-class-subject file. **20
  files today for the 4-class test school** (`test_doc/new_org/syllabus_*.xlsx`) → 1 sheet.
- `Section` blank means *every section of that class* — so a school with 6-A/6-B fills
  the syllabus once.
- Every sheet's blank cell has one meaning: **not known yet**, never zero, never 1
  (the existing `est_periods` rule, generalised).

---

## 5. The mechanism

```
Operator                                                  School
────────                                                  ──────
Platform → New school
  name, address, state, board, admin name + email
        │
        ├─► Download blank pack ───────────────────────────►  fills it in
        │                                                     (Read Me guides)
        │◄──────────────────────────────── returns the pack ──┘
        │
   Upload pack
        ▼
  ┌─────────────────────────────────────────┐
  │ VALIDATE — nothing is written           │  per-sheet, per-row, cross-sheet
  │ 47 rows ready · 3 blocked · 2 warnings  │  reads like Books & Coverage Flags
  └─────────────────────────────────────────┘
        │  (fix the sheet, re-upload — as often as needed)
        ▼
   Import everything (one transaction)
        ▼
  ┌─────────────────────────────────────────┐
  │ READINESS — 11 checks, consequences     │  services/readiness.py, unchanged
  └─────────────────────────────────────────┘
        ▼
   Generate & lock plans
        ▼
   Hand over ──► credential sheet (admin email, temp password, school code)
                 handed_over_at stamped; setup route closes
```

One screen for the operator: `/platform/orgs/{id}/setup`. Download · Upload · Validate ·
Import · Readiness · Handover — in that order, on one page, re-runnable.

---

## 6. Gaps and open questions — read this part

These are the things that will bite. Marked 🔴 blocking (need a decision or the plan
cannot be built as stated), 🟡 design call, ⚪ noted.

### ✅ G1 — DECIDED: the operator owns *structure*, the school owns *people*

> *"initially to migrate we setup once; once setup is done we give the school owner
> option to add or remove any staff or students as well, and for new year we can have
> bulk upload — usually in the new year start admission will happen one by one so admin
> will enter them. My expectation is after handover the school should run smoothly:
> admin should be able to see all the data, and teacher login and check their data, so
> from the next day the operation would work properly."* — founder, 2026-08-07

| Frozen to the operator (structure) | Kept by the school admin (people + operations) |
|---|---|
| Academic year, terms, tracking start | Admit / transfer / exit a student, one at a time |
| School timings, periods per day | Bulk student upload at each new year |
| Classes, sections, subjects | Add / remove / deactivate a staff member |
| Teaching assignments, periods/week | Fix a DOB, add a guardian phone |
| Class teacher assignment | Fee collection (already theirs) |
| Syllabus, plan approval and lock | Mark attendance, log homework — all daily capture |
| Timetable | |

Two consequences that shape the build:

1. **The school admin keeps READ on everything.** Only the write affordance goes. `/setup`
   Academics stays visible with `canEdit=false` — the admin can see the year, the classes,
   who teaches what, the timetable. "Admin should be able to see all the data."
2. **These routes stay `require_admin`** and must NOT be swept into the re-guard (G5):
   `POST/PATCH/DELETE /students/*`, `POST /students/import/*`, `POST /org/members/invite`,
   `DELETE /org/members/{user_id}`, `POST /org/members/{user_id}/reset-password`,
   `POST /org/members/bulk`, `GET /org/members/import/*`. The re-guard is **structure only**.

### 🔴 G1b — Mid-year onboarding and half-planned syllabus are first-class

> *"we might enter the school in the middle — if school starts June-26→Apr-27 we might
> enter from August, so we should be able to enter and work on it. And sometimes the
> syllabus planning is only done for half the year; we should accept it and let the school
> flow, and later they add more data."*

**Mostly already built** — the V3 mid-year work landed this. Do not rebuild it:

| Need | Already there |
|---|---|
| Year started in June, we arrive in August | `AcademicYear.tracking_start_date` — `readiness._year` renders "tracking from 12 Aug" |
| Only Term 2 planned and locked | `Plan.status = 'partial'` counts as ready in `readiness._plans` and complete in `wizard._complete` — *"a school locking only Term 2 is READY — the mid-year case, not a gap"* |
| Chapters listed but not yet sized | `rows_to_units` writes `est_periods = None` — *"blank means 'not sized', never 1"* |
| Term named on the sheet files the chapter for per-term locking | `syllabus_import` `Term` column + `_term_map` |

What this **does** change in this plan:

- The pack's `School` sheet needs a **`Tracking starts from`** row — the date we begin
  capturing, distinct from the year's start. Blank = the year's start date.
- **The validator must not require a full year.** A syllabus sheet covering only Terms 1–2
  of three is a *state*, not an error. It reports "Term 3 not planned yet" as a **note**,
  never a blocker — the same rule as an unmarked register: not-captured is a word, never a
  zero and never red.
- **Re-upload must be additive by default** (see G6). "Later they add more data" is the
  normal path, not an exception, so appending Term 3 must never require a destructive
  replace of Terms 1–2 that already have teaching logged against them.
- Readiness must pass a mid-year school. It already does — but the handover gate must not
  add a stricter check on top of it.

### 🔴 G1c — The new-year rollover is a separate flow, not this one

"For new year we can have bulk upload" — at the year boundary the school needs: a new
`AcademicYear`, classes rolled forward, students promoted a class, and a fresh syllabus.
The **students** half is covered (admin keeps bulk upload). The **structure** half — new
year, promoted classes, next year's assignments and syllabus — is operator work and needs
its own screen.

**Scoped OUT — deferred by founder decision 2026-08-07, to be implemented later.** Not
cancelled: when it comes, build it as the same pack uploaded against a new year (the pack
is year-scoped anyway). The sheet specs therefore carry an academic-year key from day one
so it is not a retro-fit.

### ✅ G2 — DECIDED: `Topic` becomes optional

`syllabus_import.SPECS` marks `topic_title` **required**. A school that fills our sheet
the way SHANA keeps theirs — chapters only — imports zero rows. Fix: `Topic` optional; a
chapter with no topic rows becomes one topic titled for the chapter, sized by the
chapter's `Periods`. Downstream (`core/coverage.py`, `taught_weight`) is topic-weighted
and keeps working, because one topic carrying the chapter's periods is arithmetically
the chapter.

### ✅ G3 — RESOLVED in P3, without changing either importer

- `SyllabusImporter.commit(class_subject_id=…)` — one class-subject per call.
- `TimetableService.import_commit(class_id=…)` — one class per call.

One sheet needs a **resolver**: `(Class, Section, Subject) → class_subject_id`, with a
blank section fanning out to every section.

**How it was actually solved:** the resolver lives in `commit._assignments`, which returns
that map as it creates the class-subjects, and `commit._syllabus` / `commit._timetable`
consume it — calling the single-target importer once per class-subject. No multi-target
commit was needed, and neither existing importer was modified, so the screens built on
them cannot regress. It was not the largest piece of work; the validator was.

### 🔴 G4 — `require_super_admin` lifts the RLS org scope

`core/dependencies.py:152` sets `app.current_org_id` to `''` — correct for cross-org
platform reads, **wrong** for an operator editing inside one school. Guarding
`POST /academics/classes` with it would turn RLS off for that request.

Needs a new dependency — `require_operator(member)` — that asserts `user.is_super_admin`
and **keeps** the org GUC set. Small, but it is a security-surface change: it must be
tested in `test_rls.py`, and that suite only tells the truth on the LOCAL database (prod
runs as `doadmin`, `rolbypassrls = true`).

### 🟡 G5 — The wire is still open to school admins

Every setup route is `require_admin` (or the admin aliases). The frontend hides the
Wizard tab; the API does not. ~48 routes need re-guarding — years, terms, classes,
subjects, class-subjects, allocation, timetable slot/config/import, syllabus units and
topics, exam portions, wizard state. `scripts/route_map.py` is the checklist and can
become the test.

### 🟡 G6 — Re-upload semantics

The operator *will* upload the pack three times. Every sheet needs a natural key and an
upsert rule, or the second upload doubles the school:

| Sheet | Natural key | On re-upload |
|---|---|---|
| Classes | (class, section) | update |
| Staff | email, else employee id | update, never re-invite |
| Assignments | (class, section, subject) | update teacher + periods |
| Syllabus | (class-subject, term, chapter) | **append** new chapters; update matched ones |
| Students | admission no | update |
| Timetable | (class, day, period) | replace the class's grid |

**Syllabus re-upload is ADDITIVE by default (G1b).** "Later they add more data" is the
normal path for a mid-year school: it hands over Terms 1–2 in August and Term 3 in
December. A chapter already present under the same (class-subject, term, chapter) key is
updated in place; a chapter not present is appended. Nothing is deleted.

Destructive replace stays available but becomes a **deliberate, named action** —
`Replace this class-subject's syllabus` — and after a plan is approved it must state its
consequence before it runs: *if teaching has been logged against a topic, deleting that
topic orphans the log.* `SyllabusImporter.commit` already takes a `replace` flag; the
change is making `replace=False` the pack's default and gating `replace=True` behind
approval state.

### ✅ G7 — DECIDED: the pack carries a `Fees` sheet

`readiness._fees` warns when there is no fee structure, but nothing generates or parses a
fees template. Sheet 10 closes it: `Class · Category · Total · Installment no · Installment
name · Due date · Amount`, feeding `FeeStructureCreate` (which already takes
`class_name`, `total_amount`, `num_installments` and an installment list). A school hands
over its fee circular anyway. New work: a small importer, Phase 7.

### 🟡 G8 — Nothing delivers the credentials

`create_school` returns the temp password in the API response, and `handed_over_at` gets
stamped, but there is no artefact to send. Recommendation: on handover, generate a
one-page **Welcome sheet** (school code, portal URL, admin email, temp password, "change
it on first login") the operator can print or email. `email_templates.py` is the place.

### ⚪ G9 — `test_doc/new_org/generate.py` emits the old shape

It writes 20 syllabus files + roster + staff. It also holds the four invariants that make
imports land 100% (periods sum to weekly capacity · one teacher per class-subject and
nobody overloaded · every topic sized · each syllabus fits the year). Those invariants are
exactly what the new validator should enforce, so the generator and validator should be
built against the same rule list, and the generator updated to emit the single pack.

### ⚪ G10 — The wizard's dependency chain does not disappear

`schemas/wizard.py` documents *why* the ten steps are ordered as they are (syllabus hangs
off class-subject; exam portions point at syllabus topics; timetable needs timings). One
upload does not remove those dependencies — it moves them into the **commit order** inside
one transaction. That docstring is the spec for the committer.

### ⚪ G11 — Chapter-End Tests

The reference plans a CET after every chapter, with `CET Avg %`. TrackBit models exams as
`exam_block` calendar events with portions. A per-chapter test is neither a minor nor a
major exam today. Out of scope for setup; flagging it as a product question because the
school clearly runs its academic life on it.

### ⚪ G12 — The wizard page is 1,602 lines

Deleting it removes ten step components, and `OnboardingState` / `services/wizard.py` /
`schemas/wizard.py` / the wizard endpoints go with it. Keep `WizardProgress`'s derived
counting — the readiness report duplicates a lot of it and one of the two should own it.

---

## 7. Phases

| Phase | Work | Complexity |
|---|---|---|
| **P0** | ✅ **Done** — G1, G1b, G2, G7 and `Difficulty` decided 2026-08-07 (§9). | — |
| **P1** | ✅ **Done** — `services/setup_pack/` (`specs · workbook · parse`). Blank pack ships headers-only; `build_pack(sample=True)` is the fixture. 22 tests. | M |
| **P2** | ✅ **Done** — `services/setup_pack/validate.py`. Per-row + cross-sheet referential checks + the `new_org` capacity invariants. A half-planned year, an unsized chapter and an unassigned subject are **notes**; only structural breakage blocks. 25 tests. **No writes.** | L |
| **P3** | ✅ **Done** — `services/setup_pack/commit.py`. One transaction (flush only, the request owns the boundary), `COMMIT_ORDER`, upsert by natural key, **syllabus additive by default** (G6). **Reuses the existing importers unchanged**: `val(row, field)` in both `RosterImporter.commit` and `StaffImporter.commit` reads `row[mapping[field]]`, so an identity mapping over the pack's own field names drives them — the pack's `Students` columns were named to match `roster_import.TARGET_FIELDS` exactly, and `employee_id` maps to staff's `username`. The pack's `Role` column is applied on top, since `StaffImporter` only ever made teachers. 19 tests. | L |
| **P4** | ✅ **Done, and differently than planned.** G3 and G2 are solved **in the committer, without touching either existing importer.** The plan assumed `SyllabusImporter.commit` and `TimetableService.import_commit` would grow multi-target signatures; instead the committer resolves `(class, section, subject) → class_subject_id` itself, fans a blank section out to every section, and calls the single-target importer once per class-subject. `Topic` optional (G2) lives in `commit._units_from_rows`, not in `syllabus_import.SPECS`. **This is better than the plan**: the per-class-subject importer behind the existing Syllabus screen keeps its exact behaviour, so nothing that works today can regress. `syllabus_import.SPECS` still marks `topic_title` required — correct, because that path is a single sheet for a single subject where a topic column genuinely is the data. | M |
| **P5** | ✅ **Done, minus one deliberate omission.** `/platform/orgs/{orgId}/setup` — download · upload · review · import · readiness link, reached from a **Setup** button on each school card. Backend: `services/school_setup.py` + three super-admin routes (`setup/template`, `setup/review`, `setup/import`), 12 tests. **The 10-step wizard is NOT deleted yet** — see below. | M |
| **P6** | ✅ **Done, minus the wizard deletion.** `require_operator` (G4) guards **39 structure routes** across academics, planner and timetable; `/setup` renders read-only with an explaining banner once the school is live; `route_map.py` learned the new guard and a test pins the whole split. **The gate is handover, not role — see D-9 below.** The 10-step wizard is still **not deleted**. | M |
| **P7** | ✅ **Done** — `setup_pack/welcome.py` + `GET /platform/orgs/{id}/setup/welcome`, offered on the setup screen's handover step. One page: sign-in addresses, the school code, the parent-login rule, a first-day checklist, and the D-1 split of what the school changes versus what it asks us for. **Carries no passwords** — they are hashed and unreadable, so it says how to reset one instead of pretending to hold it. The fee importer landed back in P3. | S |
| **P8** | ✅ **Done** — `test_doc/new_org/generate.py` emits **one** `TrackBit-Setup-Pack-<school>.xlsx` instead of 22 files, validates `ready` with zero findings, and `--messy` produces exactly six blockers plus the unsized-chapter note. Its generated walkthrough was rewritten for the operator flow. It also now gives every student a **date of birth** — the old generator had no such column, so every school it produced handed over with the readiness report's loudest warning ("N parents cannot log in") on synthetic data. | S |
| **P9** | ✅ **Done** — the 10-step wizard is retired: `endpoints/wizard.py`, `services/wizard.py`, `schemas/wizard.py`, `tests/test_wizard.py` and the `(wizard)` route group (1,602-line page + layout) deleted; the router no longer mounts `/api/v1/wizard/*` (423 → 419 routes); the Setup area's Wizard tab now points operators at **Schools**. `web/src/components/wizard/` **stays** — `exam-portions` and `year-calendar` are used by `/plan`. `OnboardingState` and its table stay too, with a retirement note: prod migrates *before* code deploys, so the drop belongs in a follow-up migration once this release is out. | S |

Backend green bar per phase: `uv run pytest -q` + `uv run ruff check app tests`.
Frontend: `npx tsc --noEmit` + `npm run lint` + `npm run build`.

---

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| A partial import leaves a half-built school | High | Whole pack in **one transaction**; validate-then-commit, never commit-as-you-parse |
| Re-guarding ~48 routes breaks a screen a teacher uses | Medium | `route_map.py` diff before/after; the full suite is the gate |
| RLS regression from a new operator dependency (G4) | Medium | Test on the **local** DB only — prod's `doadmin` bypasses RLS and would pass a broken policy |
| Syllabus replace orphans logged teaching | Medium | Block re-upload after first plan lock (G6) |
| Schools return the pack with merged cells, colours, extra header rows | High | The reference file has all three. Parser must skip banner rows and read merged cells as blank-continues-above (already the `rows_to_units` convention) |
| `.env` is in **PRODUCTION** mode — a test import writes to the real DB | High | Switch to LOCAL before running any import end to end |

---

## 9. Decisions — taken 2026-08-07

| # | Decision | Effect |
|---|---|---|
| **D-1** | Operator owns **structure**; the school owns **people**. The admin can add and remove students and staff after handover, bulk-upload students at each new year, and enter one-by-one admissions during the year. | G1 · shapes the P6 re-guard: structure routes only |
| **D-2** | The school admin **sees everything, edits structure nothing**. After handover the school runs from the next day — admin reads all data, teachers log in and see theirs. | G1 · `/setup` stays visible at `canEdit=false` |
| **D-3** | **Mid-year onboarding is first-class.** A Jun-26→Apr-27 school onboarded in August must work. Already supported by `tracking_start_date` and `Plan.status='partial'` — the job is to make sure the pack and validator do not demand what such a school cannot yet know. | G1b · `Tracking starts from` on the `School` sheet; validator reports, never blocks |
| **D-4** | **A half-planned syllabus is accepted.** The school hands over what it has planned and adds the rest later. | G1b · syllabus re-upload is **additive by default**; destructive replace is a named action, gated after plan approval |
| **D-5** | **`Topic` becomes optional.** A chapter with no topics becomes one topic named for the chapter, carrying the chapter's periods. | G2 · `syllabus_import.SPECS` change, P4 |
| **D-6** | **The pack carries a `Fees` sheet.** | G7 · new importer, P7 |
| **D-7** | **`Difficulty` is dropped.** `Est. Periods` already carries the weight — the reference's own Read Me says so. | §3 |
| **D-8** | The **new-year rollover** (new year, promoted classes, next year's syllabus) is a **separate flow**, out of scope here — but the pack's sheet specs carry an academic-year key from day one so it is not retro-fitted. | G1c |
| **D-10** | **A term IS its exam.** Superseded the earlier separate `Exams` sheet the same day it was built. The school states one date range per term — when the term exam runs — and everything else is derived: the term **ends on the exam's last day** and starts the day after the previous term's exam; an `exam_block` sits on the exam dates (so the planner already treats them as non-teaching); and the portion is **every chapter filed under that term**, needing no separate statement. Terms sheet = `Term · Exam · Exam starts · Exam ends`; the `Exams` sheet is gone and `Exam` is removed from the Calendar types. **Why:** terms and exams were two tables linked only by date overlap, so a school could read "2 terms" beside "5 exams" and both be right. Because all **31 modules that consume `Term`** read it unchanged, every downstream calculation follows for free. | founder, 2026-08-08 |
| **D-12** | **No `Topic` column in the pack.** Syllabus is `… Ch # · Chapter · Est. periods`. Schools plan by chapter — the founder's reference tracker has no topic column at all — and asking for one produced blank cells or the chapter name typed twice. Each chapter becomes one topic internally carrying its periods, so `core/coverage.py` weights exactly as before and `SyllabusTopic` stays in the model for the syllabus board. | founder, 2026-08-08 |
| **D-11** | **Setup generates and approves the plans.** A freshly imported school opened on a dashboard full of *"has no plan yet"* — setup was finished and the school was being told it was not. The wizard's tenth step did this; one upload has to too. Per **term**, so a school that planned only Term 1 gets Term 1 locked and the rest left open (`Plan.status='partial'`, D-4). Refused **only** on a `capacity` or `coverage` violation — an `unsized` chapter is the normal mid-year state and `approve_plan` locks what *is* scheduled. | founder, 2026-08-08 |
| **D-9** | **Handover is the gate, not the role** (taken during P6, 2026-08-08). `require_operator` allows the operator always, and the school's own admin **only while `handed_over_at` is null**. This is the founder's sentence read literally — *"there will be no setup screen … **once we handed over**"* — and it is why `handed_over_at` already existed. | G5 |

### Still open

- **G11** — the reference plans a Chapter-End Test after every chapter with a `CET Avg %`.
  TrackBit has no per-chapter test today. Not a setup question, but the school clearly runs
  its academic life on it. Worth a brainstorm session of its own.
