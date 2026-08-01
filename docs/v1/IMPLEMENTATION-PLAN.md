# TrackBit School — v1 implementation plan

**Written 2026-08-01.** Built from nine brainstorm sessions (`docs/brainstorm/`), verified against
the code at migration head `e0f1a2b3c4d5`.

> ## Revision 1 — 2026-08-01, after the founder's answers
>
> `BLOCKERS.md` is answered. **Three of the six scope calls were reversed**, two fences moved, and
> one packet got materially simpler. The decisions are recorded as `D-78`–`D-88` in
> `docs/brainstorm/decisions.md`; this document has been updated to match them. Summary of what
> changed from the first draft:
>
> | | Change |
> |---|---|
> | **A-2 → `D-79`** | The observance catalogue is **IN**. The objection is defeated structurally: **the date is editable at approval**, so a suggestion is never a date — it is a prompt to pick one. Christmas the holiday and the Christmas celebration are two approvals from one suggestion. |
> | **A-3 → `D-80`** | The exam photo flow is **IN and larger** — a photo **per student's marked script**, AI reads the marks, teacher adjusts, manual entry stays first-class, unreadable pages are mapped by hand. Then two tabs per exam: **Score** and **Report**. |
> | **A-6 → `D-81`** | Per-question *capture* stays out, but **two report levels are in**: the standard report card (numbers) and the AI analysis (per topic, skill abilities, per-subject summary). |
> | **B-1 → `D-83`** | Reversed: a teacher assigned a fee follow-up **does** see the full detail — history, instalment, pending amount, and the conversation log. |
> | **B-1 → `D-84`** | **New requirement:** an append-only **fee conversation history per student**, rendered on the fee page and carried into the task. |
> | **B-2 → `D-88`** | Fee years **never pool** — every roll-up is computed within one academic year, and the existing year switcher is the route to old dues. Carried dues get a neutral labelled link, never a silent omission. |
> | **B-3 → `D-87`** | Confirmed: **the weekly check-in is the unit** of the support programme — her students grouped by subject, one child's page opening already written, four fields. |
> | **B-4 → `D-85`** | **Simpler than my design.** No working-day gap arithmetic. Late is a status the teacher sets any time; teacher-delay is *derived* from "nothing checked for 3 days". |
> | **A-1 → `D-78`** | Payroll deferred as recommended, **plus** a staff **month summary** — days worked out of working days, leave used, balance. |
> | **A-5 → `D-86`** | No parent writes, and the absence colour answers *"has anybody dealt with this?"* — reason recorded → amber, no reason → red. |
>
> **Two fences moved and need updating in `CLAUDE.md`, `ux-principles.md` and SPRD2 §11:**
> per-student photos (`D-82`, for exam scripts) and teachers-and-fees (`D-83`, inside an assigned
> task only).

**Section C stands as written** — all 38 defaults accepted without objection.

---

## 1 · What v1 is

**One sentence:** the school's daily operating system, complete enough that a real school can be
onboarded mid-year, run entirely on it for a term, and find that **every number on every screen is
true and every red row has somewhere to go.**

Three things it explicitly is **not**: a bigger feature list than we have, a payroll system, or a
product with clever screens that quietly read from computations nobody fixed.

### The one rule that outranks the rest

> **Nothing renders that isn't computed, and nothing computed is unreachable.**

Your words were *"whatever is displayed and promised in the product should work seamlessly"*. That
rule is not aspirational here — the brainstorm found **five separate features that are fully built
on the server, wired into the web client, and called by nothing**: the homework-by-student history,
the fee defaulter list, the intervention plan, the cover picker's timesheet read, and the whole
read side of the school calendar. A school using v1 would never see any of them.

So this plan has a **packet-close check** that is not optional: for every packet, grep the client
for exported API methods with no caller, and grep the server for endpoints with no client. A packet
does not close with either list non-empty.

---

## 2 · Where we actually are

Better than it looks, and worse in one specific way.

**Built and working:** the full v1 SPRD (fees, tasks, assessments, sessions, master data), the
entire v2 redesign (timetable, capture-by-exception attendance, recommendations, daily report
agent, student timeline, wizard), term-scoped planning, mid-year adoption, the platform/super-admin
layer, the parent portal, Lucy, and — uncommitted on `main` right now — SF-1 (staff attendance,
timesheet, leave), HW-1 (per-student homework) and DASH3 (the seven-tab admin board).

**The specific way it's worse:** the brainstorm found the *same class of defect in all nine
sessions* — **one fact computed several different ways in different places.** Three definitions of
"absent for a day". Two of "syllabus covered". Two of "who is free right now", one of which offers
absent teachers as substitutes. Two of what a "partial" is worth. Four separate implementations of
"working days between two dates". And in session 5, a **visibility rule decided correctly on the
server and then re-decided in a React component**, which is why an admin currently sees none of the
follow-ups they assigned.

That is not a backlog of bugs. It is a structural property of how the code grew, and it is why
**packet V1-0 is a foundation packet with no new features in it.**

### Before anything starts

`git status` shows ~60 uncommitted files — SF-1, HW-1 and DASH3, all complete, all tested.
**Commit that first.** Building v1 on top of an uncommitted tree means the first thing that goes
wrong is unbisectable.

---

## 3 · The five rules this plan is built on

| # | Rule | Where it came from |
|---|---|---|
| **1** | **One computation, many renderings.** When you add a figure or a rule, name the existing function that computes it, or write down why a second one is correct. This extends past figures to **authorization**, where a second implementation is not a discrepancy — it is a leak or a blackout. | `ux-principles` §9; the defect found in all nine sessions |
| **2** | **Not-captured is never a failure, and never a zero.** A class nobody marked is a gap in the record. `unplanned`, `unestimated`, `not_checked`, `not_marked` stay **words** and stay neutral in colour. | `ux-principles` §5, §10 |
| **3** | **Lead with a sentence; every figure carries its denominator; every red row carries its next step.** `78%` tells nobody what to do. *"31 of 44 periods marked — 6-B has marked nothing since period 2"* does. | `ux-principles` §2, §4, §7 |
| **4** | **Capture by exception, always.** Confirm the norm in one tap, record only deviations. Any feature needing per-student entry for a whole class is mis-designed. The one legitimate exception is banding a class, which happens twice a year. | P1v2; `D-22` |
| **5** | **Append-only for anything that says who did it.** Undo is a compensating row. Status is a derived cache of the newest appended event — the `plan_approvals` / `leave_request_events` / `demo_request_notes` shape, now used four times and worth copying a fifth. | Law 3 |

---

## 4 · Scope

### In

Attendance · class teacher · staff attendance, leave & cover · timesheet · homework · syllabus &
planning · events, dates & birthdays *(school's own only)* · exams & scores · bands / the support
programme · fees *(read + remind)* · tasks & follow-ups · parent portal · the admin dashboard ·
setup, onboarding & handover · Lucy *(reconciled, not extended)*.

### Out — deferred to v2, deliberately

| Cut | Why | Cost of cutting |
|---|---|---|
| **Payroll** (`D-78`) | Four unanswered questions, real legal liability, and every school answers the calculation differently | **Near zero.** v1 ships the **staff month summary** — days worked out of working days, leave used, balance — which is payroll's entire input. v2 payroll is a small packet, not a restart. |
| **Per-question objective *capture*** (`Q-53`) | The only idea in the brainstorm needing a new table **and** a new capture surface | Low — **and mostly recovered anyway**, see the note below. |
| **Training-corpus export** (`D-54` use) | The de-identifying step must exist before the first export, not the first row | None — v1 still **captures** the pair at lock, which is the part that can't be recovered later. |
| **Parent writes** (`Q-01`, `D-86`) | One write turns the portal into a messaging product with moderation and a pending state | Low — a `tel:` link closes the same loop, and staff record the reason. |

> ### One reconciliation I had to make — and it costs nothing
>
> `D-80` asks the exam **Report** tab for *"which questions were most often wrong"*. `Q-53` puts
> per-question **capture** out of scope. Read literally these contradict: you cannot report per
> question without per-question data.
>
> **The resolution:** the model is already reading a **marked script** — a paper with marks written
> beside each question. So it transcribes the per-question marks *as part of the read it is already
> doing*, and we store them as a JSON column on the existing score row. **No new table, no new
> capture surface, nothing extra asked of the teacher** — which is what `Q-53` was actually
> protecting against.
>
> The honest consequence, and it goes on the screen: the question-level analysis exists for exams
> captured **by photo** and is simply **absent** for exams typed in by hand. Absent as a word, never
> as a zero — *"question-level analysis needs a photo of the marked paper."*

Full reasoning and your decision boxes: `BLOCKERS.md` §A.

---

## 5 · Mid-year adoption — the guarantee

You asked that a school be adoptable **in the middle of a running year**, with **only part of the
year planned**, and that everything still works. This is the single most-tested property of v1, so
here is exactly what it means module by module.

**The mechanic already exists and is correct** — `academic_years.tracking_start_date` (V3-P0) plus
term-scoped planning (V2-P11) plus `extend_plan`. What v1 adds is making it *reachable, explained
and honest on every screen*.

### The scenario v1 is built against

> A school signs in **November**. Term 1 is over and was never in the system. They hand over a
> roster, a staff list, and **Term 2's syllabus only**. They want to start capturing tomorrow. In
> February they will size Term 3 and carry on.

| Module | What happens | Status |
|---|---|---|
| **Academic year** | `tracking_start_date = 2026-11-15`. Every denominator in the product starts there. | Built |
| **Planner** | Term 2's chapters are sized and its plan is approved. Term 1 is **`unplanned`** — a word, never a RAG colour, never a red row, never an alert. Forecast rates **the planned portion only**. | Built (V3-P0) — needs surfacing |
| **Adding Term 3 later** | `extend_plan` appends the newly sized chapters **after** the locked Term 2 entries. **The approved baseline never moves** (P2). | Built — currently buried; v1 puts it on the plan screen as *"Schedule new chapters"* |
| **Attendance** | Nothing before the start date exists, and the register never implies it does. The 14-day pulse and every % is denominated from the start date and **says so**. | Needs the denominator work in V1-0 |
| **Syllabus board** | Pre-tracking terms are excluded from every number. A school 2 months in does not read as a school 60% behind. | Built (V3-P0) |
| **Exams** | Exams sat before tracking started simply don't exist. A school that wants its Term 1 result in can record it as a marks-only exam with no evidence — a first-class path, not a degraded one. | Built |
| **Bands** | Entry is `D-70`'s **teacher's own assessment** against the descriptors — which exists precisely because *"in week two of the year there is no test"*. | Packet V1-9 |
| **Fees** 🔴 | **The one real gap.** A November school has students who already paid two instalments elsewhere. Recording that must not invent fake transactions, and `opening_dues` — the field built for exactly this — is currently excluded from **every** roll-up. | **Fixed in V1-10 per `D-88` — years never pool; the year switcher reaches old dues** |
| **Daily report** | Aggregates only what was captured. The ambiguity rules never fire on pre-tracking gaps. | Built |

### The three rules that make this hold

1. **A term nobody planned is `unplanned`, not behind.** It shows as a word, in neutral grey, with
   *"Size these chapters →"* beside it. It never enters a RAG count, a "worst subject" list, or an
   alert. The one exception, already built: a **currently running** term with no plan at all raises
   one alert, because that is genuinely a problem.
2. **Every denominator names its window.** Not *"82% attendance"* but *"82% of school days since
   15 Nov"*. Applies to the parent portal too, where it matters most.
3. **Sizing a chapter later never rewrites history.** `extend_plan` appends; approved entries are
   immutable; the forecast is recomputed, never stored.

**Acceptance test for v1:** seed a school with `tracking_start_date` two months into the year and
**only the second term sized**, then walk every screen in all three roles. No red rows, no zeros,
no empty charts presented as failure, and the plan screen offers the route to size the next term.

---

## 6 · Onboarding & handover — how a school actually starts

You asked specifically: *what data do we need, how does the super-admin hand templates over, how do
we import them, and how does each role work after handover.*

Today: `/platform` creates the school and its admin with a temp password; the 9-step wizard exists
and is operator-only; three importers exist (roster, staff, syllabus); `test_doc/new_org/generate.py`
generates a **filled example pack**. What's missing is the part the school touches — **blank
templates with the exact columns** — and any notion of *"is this school ready to hand over?"*

### The five phases

```
  ①  CREATE          ②  COLLECT          ③  IMPORT           ④  COMPILE          ⑤  HAND OVER
  super-admin        school fills        operator runs       wizard generates    credentials +
  makes the org      3 spreadsheets      the importers       and locks plans     the readiness
  + the admin        we handed them      + reviews gaps      + timetable         report
```

### ① Create — super-admin, 2 minutes

`/platform` → New school. Name, **address** (→ state), **board** (CBSE / state), timezone. Creates
the org, the admin membership, a temp password with forced change, and — new in v1 — a **random
6–8 character school code** (`D-13`, `S-57`) which is what parents will use to log in.

### ② Collect — the school, a few days

The operator downloads three **blank .xlsx templates from inside the product** and emails them.
Each is generated from the importer's own `TARGET_FIELDS`, so the template can never drift from
what the importer accepts — a header row, a comment on each column, and three example rows.

| Template | Columns | Required | Notes |
|---|---|---|---|
| **Students** | name · admission no · roll no · class · section · **date of birth** · category · father name/phone · mother name/phone | name, admission no | **DOB is new in v1** — it is the parent's password (`D-13`) and the birthday feed (`D-56`). Parsed for `dd/mm/yyyy`, `dd-mm-yy` and Excel serials; anything ambiguous lands in **unresolved**, never guessed. |
| **Staff** | name · email · phone · role · subjects taught · classes taught | name, email | Feeds `class_subjects.teacher_member_id`, which is what the whole cover flow reasons over. |
| **Syllabus** — one per class-subject | chapter · topic · estimated periods · **term** | chapter | `est_periods` **may be blank** — that is `unsized`, and it is the mid-year case, not an error. |

Plus four things typed, not imported: the academic year and its terms, school timings and periods
per day, working weekdays, and the **class → subject → periods-per-week** grid.

### ③ Import — operator, ~30 minutes

Each importer already reports `errors` / `skipped` / `unresolved` and asks a gap question when it
can't place a column. v1 adds: the DOB parser, a **Term** column on the syllabus importer that
reports names it can't resolve rather than inventing them, and one screen that shows all three
import results together.

### ④ Compile — the wizard

The existing 9 steps, with progress **derived from the real tables** (already true — an admin who
deletes every class sees the step go incomplete again). v1 changes two things:

- **It must not demand a full year.** A school handing over Term 2 only completes the wizard, locks
  Term 2's plans, and the year-level steps report *"Term 1 not planned"* as a state, not a blocker.
- The final step generates and locks plans **per term**, not per year.

### ⑤ Hand over — the readiness report *(new)*

The one genuinely new screen in onboarding, and the reason handovers go wrong without it. A single
page the operator reads before giving the school its password:

```
  Ready to hand over — Nalanda Public School                    9 of 11 ✓

  ✓  Academic year and terms          2026-27 · Term 2 from 15 Nov (tracking starts here)
  ✓  Classes and subjects             12 classes · 5 subjects · 48 of 48 periods allocated
  ✓  Teachers assigned                18 staff · every class-subject has a teacher
  ✓  Timetable                        576 slots · no clashes
  ✓  Students                         486 imported · 0 errors
  ⚠  Dates of birth                   441 of 486 — 45 parents cannot log in     [ list → ]
  ✓  Syllabus                         Term 2 sized for 60 of 60 class-subjects
  ✓  Plans approved                   60 of 60 locked
  ⚠  Class teachers                   7 of 12 assigned — absence follow-ups
                                       have no owner in 5 classes               [ assign → ]
  ✓  Fee structures                   4 structures · 486 enrolled
  ✓  Parent portal                    enabled · school code NPS4K2M

  [ Copy handover credentials ]                      [ Mark handed over ]
```

Every warning is a **link to the screen that clears it**, and each one names the consequence rather
than the missing field — *"45 parents cannot log in"*, not *"45 nulls"*.

### After handover — what each role gets

| Role | Lands on | Their job |
|---|---|---|
| **Admin** | `/dashboard` | *"What needs me today?"* — clear the action rail, arrange cover, decide leave, chase fees, approve dates. |
| **Teacher** | `/my-day` | `D-22`: exactly two things — **log the class, maintain the timesheet.** Plus homework checking at a desk, and check-ins if she owns support students. |
| **Class teacher** | `/my-day` + **My Class** | Her children: who to call, who is drifting, her class's syllabus across all subjects. |
| **Parent** | `/parent` | *"Was my child in school, and is there anything to do tonight?"* Read-only. |
| **Super-admin** | `/platform` | Schools, enquiries, readiness. Never inside a school's day-to-day. |

---

## 7 · The dashboard — a decision surface, not a report

Your framing: *"by looking at the analytics user should immediately know what action or decision
should be taken."* That is exactly right, and it means **more charts is not the goal** — the right
*form* for each question is.

### The shape of every block, everywhere

```
   SENTENCE          "Q2 is 62% collected — ₹6.1L behind where Q1 stood in its 5th week."
   ↓
   SHAPE             the one chart that shows the pattern behind that sentence
   ↓
   NAMED ROWS        "8-B — 14 of 38 families pending · ₹1.4L"      ← people, not counts
   ↓
   ACTION            [ Remind ]  [ Assign follow-up ]               ← on the row, not in a menu
```

A chart that produces no decision goes behind **More**. A chart with no sentence above it does not
ship.

### Picking the form — by the question, not by taste

| The question the user arrived with | The right form | Where it lands in v1 |
|---|---|---|
| *Is this unusual? Which way is it moving?* | **sparkline** in the metric; **area/line with a reference line** on the tab | attendance 14-day pulse · **fee collection curve vs last quarter** · **syllabus coverage vs the baseline plan** |
| *Where is the problem concentrated?* | **sorted horizontal bars, named** | by-class attendance · by-subject homework · teacher load vs the org mean |
| *Is the record even complete?* | **heatmap grid**, four states, not-captured neutral | attendance capture — class × period. The one thing that separates *"attendance is bad"* from *"attendance was never taken"* |
| *What is this one child's pattern?* | **cell grid** — student × school day | **the class teacher's month grid.** A row's shape says *"every Monday"* or *"a block in October"* or *"slowly fading"* faster than any percentage — three different problems, three different conversations, one glance |
| *How is the population split?* | **donut**, only at ≤4 categories | RAG status · support-tier distribution |
| *Where is the slack in the week?* | **stacked bar per period** | the staff slack profile — *"Period 7 Thursday is the only slot where 11 of 14 are free"* |
| *How far along are we?* | **meter bar with its denominator** | syllabus coverage · the fee quarter strip |
| *How did the class do on this test?* | **histogram**, bucketed in Postgres | exam distribution |
| *What is this child good and bad at?* | **radar** | the diagnostic skill profile on the report card |
| *Did anybody move?* | **delta chips on a grid** — `↑2 ↓0` beside the count | the bands board by class × subject |

### Three hard rules on every chart

1. **Colour comes from `components/charts/palette.ts`, and nowhere else.** One chart kit, one lazy
   chunk, already dataviz-validated. Red / amber / green are **reserved** for a server-computed
   status and are never used as a series colour.
2. **Not-captured is a neutral grey band with a word.** Never a zero in the series, never a dip in
   the line. A class that marked nothing must not draw as a class where nobody came.
3. **Every axis and legend carries its denominator and its window.** *"% of marked periods, since
   15 Nov"*.

### What goes where

| Tab | Leads with | Its shape | Its action |
|---|---|---|---|
| **Overview** | The written briefing (2–3 sentences, AI at generate time, deterministic fallback) | **No big charts** — one block per module: sentence, 2–3 figures with sparklines, named rows | **The action rail** — every item links to the screen that clears it |
| **Attendance** | *"428 of 470 in today. 6 need a call. 13 periods unmarked in 3 classes."* | capture heatmap → pulse area → by-class bars | Remind guardian · Assign follow-up · Record a reason · Nudge teacher |
| **Staff** | *"Anil away — 9 of 9 periods uncovered."* | **slack profile** (stacked, per period) → load vs mean | Arrange cover · Decide leave |
| **Syllabus** | *"Second Terminal in 24 days · 4 subjects short of portion."* | **coverage over time vs baseline** → RAG donut → per-node bars | Ask for a catch-up plan · Size these chapters |
| **Homework** | *"82% done · 6 late · 4 sets unchecked."* | completion trend → by-class bars → daily load | Remind guardian · Follow up |
| **Exams** | *"6-B Maths is the one class-subject worth a conversation."* | trajectories **from minor tests** → distribution histogram | Open the exam |
| **Tasks** | *"9 open, 3 overdue, all with Priya."* | open/overdue by assignee | Reassign · Extend · Nudge |
| **Fees** *(on `/fees`, not a 9th tab)* | *"Q2 is 62% collected — 14 families overdue."* | **collection curve vs last quarter** → quarter strip → by-class table | Remind · Assign follow-up |
| **Bands** *(on `/students/bands`)* | *"11 moved up this term, 3 slipped. 4 have been C since April."* | class × subject grid with `↑↓` deltas | Assign owner · Ask for a check-in |

> **Why fees and bands replace their own landing pages rather than becoming dashboard tabs:** both
> already have a landing page, both landing pages are weak, and a second screen about the same
> subject **will** disagree with the first. That is the defect this whole plan exists to stop.

---

## 8 · The packets

Fourteen. Each is labelled **FIX** (a live defect), **WIRE** (built on the server, unreachable in
the UI) or **BUILD** (genuinely new) — because a surprising amount of v1 is the first two.

Every packet closes on: backend `uv run pytest -q` green + `ruff` · frontend `tsc --noEmit` +
`eslint` + `next build` green · **the no-dead-ends grep** · and its own done-when below.

---

### V1-0 · Foundation: one computation *(no new features)* — **FIX**
**Migration:** no · **Depends on:** nothing · **This is the packet that makes every later number
trustworthy.**

Create the single source of truth for the five facts currently computed several ways, delete the
duplicates, and fix the defect sweep from `BLOCKERS.md` §"proceeding regardless".

| Function | Replaces | Consumers |
|---|---|---|
| `attendance.day_status(student, date)` | **three** definitions of "absent for a day" | admin tab · class-teacher grid · parent Today · daily report · report card · Lucy |
| `syllabus.coverage(scope, checkpoint)` | **two** definitions, with different numerator *and* denominator | admin board · parent progress · report card |
| `workload.is_free(member, date, period)` | **two** that disagree — one offers absent teachers as substitutes | `/staff/today` · `/dashboard/staff` · the cover picker · the slack profile · Lucy |
| `homework.verdict(...)` | `done` / `late` / `carried` / `waived` / `not_checked` meaning the same thing on all six surfaces | check sheet · by-student · admin red list · report card · daily report · parent Today |
| `calendar.working_days(a, b)` | **four** implementations | leave · homework gap · task window · planner |

Plus the defect sweep: the `affects_teaching` paint bug, `/staff/today`, `busy_reason` vs approved
leave, the client-side task re-filter, UTC due dates, the rail's per-day dedupe, `_working_days`
crashing on ORM rows, `overdue_students`' N+1, and the absent-child homework flag.

**Done when:** each of the five facts has exactly one implementation, every duplicate is deleted
(not deprecated), and a test asserts two different screens' payloads agree for the same input.

---

### V1-1 · Tasks & the action rail — **FIX + BUILD**
**Migration:** small · **Depends on:** V1-0 · **Why this early:** every module's red row creates a
task. If the board lies, every action rail built after it lies too.

- **FIX** `D-48` — delete the client re-filter (an admin currently sees **none** of the follow-ups
  they assigned); org-local end-of-day due dates.
- **FIX** `D-47` — dedupe on the **open task**, not the calendar day.
- **BUILD** `D-46` — the task carries its **subject** (student · member · period), so a row reads
  *"Kabir Shah — absent 4 days"*, and completion asks one optional question: **what happened?**
- **BUILD** `D-44` — window the board read (open always · done 7 days · older behind a date filter
  that **ships with it**). `D-45` — a **Stale** group, close or re-date, **never auto-close**.
- **BUILD** `D-41`/`D-43` — the My Day tasks section: rail-assigned within **3 working days** ∪ due
  today, tickable in place, cap 3–5, and a `n older tasks →` footer so the window is never silent.

**Done when:** an admin sees their own assigned follow-ups; three days of absence produce **one**
row; a completed follow-up carries its outcome; and the board is readable at day 90.

---

### V1-2 · Setup, onboarding & handover — **BUILD**
**Migration:** yes (`school_code`, `students.date_of_birth`, `memberships.date_of_birth`) ·
**Depends on:** V1-0 · **Unblocks:** parent login, birthdays, bands ownership, absence follow-ups.

- Blank .xlsx **template downloads** generated from the importers' own `TARGET_FIELDS`.
- DOB on the roster + Indian date parsing + **unresolved, never guessed** + the missing-DOB list.
- **Class teacher assignment UI** (`D-03`/`S-20`) — the API has accepted it since P0-C and **no
  screen has ever set it**, which is why every intervention in every real school is unassigned and
  every absence row says *"class teacher: —"*.
- **Make the by-teacher assignment lens writable** (`D-28`/`S-77`) — pick a teacher, tick their
  class-subjects, save many at once. Smallest change in the brainstorm with the largest effect on
  setup time. Batch its per-class queries while it's open.
- The **readiness report** (§6 ⑤) and the wizard's per-term completion.
- Settings gains: attendance mode (`D-01`), minimum-attendance threshold, homework gap threshold,
  work categories (`D-19` — stable key, mutable label, retire never delete).

**Done when:** a fresh school goes create → templates → import → wizard → handover with **only one
term planned**, and the readiness report is honest about what's missing.

---

### V1-3 · Attendance + the class teacher — **BUILD**
**Migration:** yes · **Depends on:** V1-0, V1-1, V1-2 · **All gates answered** — `Q-02` mode
affects attendance only · `Q-03` `left_after_lunch` · `D-86` colour: reason recorded → amber, no
reason → red

- `D-01` capture mode (every period / first only / twice daily) driving what is asked, what the
  heatmap expects, and what "absent today" means.
- `D-02` the **absence status machine**, server-computed: reason recorded → yellow · 3+ days no
  reason → **red**. Colour is a rendering of a status, never logic in a component.
- `Q-03` `left_after_lunch` as a first-class state — the reason a school picks twice-daily mode.
- The admin tab rewritten **as questions**: needs-a-call at the top, drifting, chronic late, then
  *is the record complete*, then charts behind **More**.
- **My Class** — the class teacher's area (`D-03`), centred on the **month attendance grid**.
- Parent Today gains the **pattern** — a month strip, *"present 18 of 21 school days"*, the reason
  if one was recorded, and a `tel:` "tell the school why" link.
- `S-12` — one roll-call component, one default (everyone present, tap the exceptions). Two screens
  currently have **opposite defaults** for the same act.

**Done when:** "absent for a day" gives the same answer on six surfaces, an unmarked class never
renders red or as 0%, and every red row has a working action that remembers it fired.

---

### V1-4 · Staff, leave, cover & time — **FIX + BUILD**
**Migration:** small · **Depends on:** V1-0, V1-2

- `D-04` half-day (**AM/PM**) and late on staff attendance and on leave requests.
- `D-27` **leave approval hands back the cover flow** — *"Arrange cover for 3 days"*, one sheet per
  day, uncovered periods on the rail **dated to that day**. Ships with the approved-leave clause in
  `busy_reason` or not at all.
- `D-29` the cover picker says **what the class gains** (the next planned topic and who can teach
  it) and **what the substitute gives up** (her timesheet), and warns if she is behind herself.
- `D-18` timesheet **month** (one cell per day, not 200) and **day** (a vertical timeline with
  breaks) views. `S-75` the picker pre-selects her usual. `S-70` the counters become **her** record.
- `D-21`/`S-66` the **slack profile** — the genuinely new chart, for finding the meeting slot.
- `S-68` hostel evenings count, reported **beside** teaching periods, not added to the same mean.
- **`D-78` the staff month summary** — per member: **days worked out of the month's working days**,
  leave used, leave balance, unapproved absence. Admin sees everyone; a teacher sees herself. **No
  money anywhere on it**, and the working-days denominator is `calendar.working_days` from V1-0, not
  a fifth implementation.

> ⚠️ **One display rule on the month summary is really a future financial rule** (`S-34`): a day
> nobody marked must **never** silently read as *absent*. It reads as **not marked**, a word, with
> its own count. The moment this figure informs pay in v2, that distinction is the difference
> between a clerical gap and an unpaid day.

**Fenced, and it is load-bearing:** no ranking of people, no completeness % per teacher, no nag
about unfilled timesheets, and **no path from the timesheet to pay** (`D-25`). A teacher who knows
her timesheet cannot cost her money has no reason to write anything but the truth.

---

### V1-5 · Homework — **FIX + WIRE + BUILD**
**Migration:** small · **Depends on:** V1-0, V1-3 · **Simplified by `D-85`**

> **`D-85` made this packet smaller than the first draft.** There is **no working-day gap
> arithmetic** anywhere in homework now. Nothing locks, nothing expires, and the ambiguity
> `Q-44` was wrestling with dissolves — the two latenesses come from two different places instead
> of one overloaded field.

- **Late is a status the teacher sets, any time, editable forever.** `done · late · not_done ·
  partial`, her judgement, no threshold. This still kills the Friday-invisible-on-Monday defect,
  because the queue stops filtering on `date == today - 1` and simply lists everything unchecked,
  oldest first.
- **Teacher-delay is *derived*, never written into a child's record**: nothing checked on an
  assignment for **3 days** → the admin is notified. The child's history says nothing about it.
- The admin's second notification is the other signal: *this class was checked, and 9 children
  missed it.*
- `D-34` an absent child's homework is **carried**, not missed — with a **waive**, or the pending
  items and the parent's yellow never clear. Excluded from the streak and the red list.
- `not_checked` keeps its meaning and keeps being excluded from every completion figure. **A teacher
  who checks nothing must never read as a class with perfect completion** — this is the module's
  load-bearing rule and the thing most likely to be broken by someone tidying the copy.
- **BUILD** `/homework` (`D-36`) — three levels: her classes × what was given → the check sheet →
  by student / by day. **WIRE** the by-student view to the endpoint that already exists and
  delivers the admin's `D-31` drill-down from the same component.
- **FIX** a substitute can check homework.
- `D-37` daily load per class — admin and **class teacher only**, never a subject teacher, never a
  cap.

---

### V1-6 · Syllabus, planning & the mid-year proof — **FIX + BUILD**
**Migration:** no · **Depends on:** V1-0

- `S-51` one coverage definition (the admin's and the parent's currently differ in numerator *and*
  denominator). `S-42` unlogged ≠ behind — a subject with no logs is **unknown**, never on a worst
  list.
- `S-41` **every "behind" row says why** — periods lost · nothing logged · chapters never sized ·
  genuinely slower. *"6-B Maths lost 8 periods to exam week and two holidays"* is a completely
  different conversation from *"6-B Maths is 3 weeks behind"*.
- `S-50` lead with the exam checkpoint. `S-40` **coverage over time vs the baseline** — the one
  chart the board lacks. `S-43` section comparison (6-A vs 6-B Maths — the fairest comparison in a
  school).
- `D-16` **Ask for a catch-up plan** — a *meeting request, not a directive*; the row clears on the
  recorded **outcome**, not the press. The admin never reschedules from the board.
- `S-46` the teacher's **My subjects** landing — five to eight rows, each saying where she is and
  **what to teach next**.
- **The mid-year surfacing** from §5: `unplanned` as a neutral word everywhere, *"Schedule new
  chapters"* (`extend_plan`) reachable on the plan screen, every denominator naming its window.

---

### V1-7 · Events, dates & birthdays — **FIX + WIRE + BUILD**
**Migration:** small + one platform table · **Depends on:** V1-2 (DOB) · **Scope: the catalogue is
IN** (`D-79`)

> **Why the wrong-date risk is gone.** My objection was that a wrong Diwali date makes a school
> decorate on the wrong day *because our screen said so*. `D-79` removes it structurally rather
> than by accepting it: **a suggestion is never a date, it is a prompt to pick one.** The approval
> sheet's date field is **editable**, pre-filled from the suggestion. So Christmas the *holiday*
> and the Christmas *celebration* are two approvals, on two dates, from one suggested row — which
> is how schools actually behave, and which the first draft could not express at all.
>
> **`Q-63`'s research runs before this packet is implemented**, not before v1 starts. Everything in
> steps 1–4 below is buildable now and independent of it.

- **FIX** the live defect: painting a Celebration silently removes a teaching day. The `D-58`
  approval sheet makes the open/closed choice the **central act**, so the bug cannot survive the
  feature.
- **BUILD** *Approve this date* — three levels (**school closed** / **some periods** / **runs as
  usual**), which are `affects_teaching` + `blocks_periods`, both already prorated by
  `effective_periods`. Plus 🔴 **the cost, before they commit**: *"Removes 8 periods. 6-B Maths and
  9-A Science move green → amber."* Without it a principal locks three days for Diwali and watches
  six subjects turn amber with no idea why.
- **WIRE** the read side of `calendar_events` — a year old, and its only consumer is the
  effective-days engine.
- `D-59` the teacher's *"not held, because"* **references the approved event**, so *"what did Diwali
  cost us in periods?"* is answerable. `S-145`: a locked period leaves her capture surface, every
  denominator and the 16:00 reminder — *leaves* meaning **no longer expected**, never *erase what
  was recorded* (`Q-65`).
- The two cards: admin *What's on*, teacher My Day strip. **The strip is the only thing on My Day
  that asks her for nothing** — never a tick, never amber, absent entirely when there's nothing on.
- **BUILD the catalogue** (`D-79`, `D-60`, `S-149`) — **platform-level data**: no `org_id`, no RLS,
  `require_super_admin` on every write, exactly the `demo_requests` / EN-1 shape. One curation tab
  joins Schools · Enquiries on `/platform`, so one correction fixes every school at once and needs
  no deploy. Scoped per school by **address → state** and **board** (`D-61`), both of which setup
  already collects — a school is never asked to declare a region or a religion.
- Each suggestion carries **provenance** (`S-150`) — *"Suggested · Telangana state holiday list"* —
  and becomes **holiday · celebration · event** on approval, at whatever date the admin sets.
  **Dismissal is append-only and permanent** (`S-148`): the same suggestion must not return next
  week or next year, or the admin learns to ignore the whole feed.

**Done when:** an admin can approve *"Christmas — school closed, 25 Dec"* and *"Christmas
celebration — runs as usual, 22 Dec"* from one suggested row; the cost preview fires on both; and
no path exists that writes `calendar_events` without a human press.

---

### V1-8 · Exams, scores & reports — **FIX + BUILD**
**Migration:** yes · **Depends on:** V1-0 · **The largest packet in v1** (`D-80`, `D-81`, `D-82`)

> **This grew the most from the first draft.** It is now three things: the corrections below, the
> **photo-per-student capture flow**, and the **two report levels**.

**The capture flow (`D-80`)** — much of it exists and works; the shape changes to per student:

1. A **photo per student's marked script**, added across a sitting. `score_captures` /
   `score_capture_pages` already store pages as R2 keys; `D-82` makes per-student explicit and
   supersedes P5 here.
2. The model **transcribes** — identity, total, **and the per-question marks it can already see on
   the marked paper** (stored as JSON on the score row; no new table, see §4's reconciliation).
3. `score_match.py` **decides** identity — roll → exact → fuzzy → unmatched-with-candidates. A
   hallucinated name can never write a score. **This division is not negotiable.**
4. The teacher **adjusts** in the review grid.
5. **Manual one-by-one entry is a first-class path**, never styled as a degraded one.
6. An **unreadable page is kept and mapped by hand** — the teacher attaches the student and the
   marks herself. A page we cannot read must never become a page we discard.

**The two tabs on an exam (`D-80`)** — **Score** (the roster and their marks, nothing else) and
**Report** (topics covered, who is strong and who is struggling, most-missed questions where a
photo gave us them, per-subject narrative).

**The two report levels (`D-81`)** — the **report card**: standard, familiar, numbers only, per
student and per class; and the **analysis**: per topic, skill abilities, AI-written per-subject
summary over figures the product already computes. *This is a report card **output**, not the
report-card **designer** SPRD2 §11 fences.*

**Then the corrections** *(all gates answered: `Q-50` never blend · `Q-52` the nullable FK · `Q-62`
admin unlock, appended · A-4 capture at lock, default off, no export)*:

- `D-55`/`S-135` a small **`exam_types` table** beside the system `type` — a school running **CET**
  cannot record one today. The school's word is what every screen displays and groups by; `type`
  stays code-only.
- `D-53` **Verify & lock** — gives `verified_by` the meaning it has never had, and stops
  `ExamService.save`'s full delete-and-reinsert silently replacing July's confirmed mark in
  November. Unlock is admin-only, with a reason, **appended** (`Q-62`).
- `S-114` **`scale` = minor | major, never pooled.** Trajectory from minor, standing from major.
  Fixes the same wrong average on three screens at once.
- `S-115` the nullable `exam_event_id`, so syllabus and results can be asked one question together.
- `S-118` the student's average carries its denominator; `S-119` **the paper is one tap from the
  report card** — the photos are kept forever and there is currently no way back to them from the
  screen where a parent asks.
- **A-4:** write the model-read-vs-human-locked **diff at lock**, org setting default off, **no
  export path in v1**.

---

### V1-9 · Bands / the support programme — **FIX + BUILD**
**Migration:** yes · **Depends on:** V1-2 (class teachers), V1-8 (the lock) · **`Q-73` answered (`D-87`)** —
the weekly check-in is the unit

**Step 0 — the four fixes, and nothing below is honest until they land:**
an intervention can currently **never be finished** (a goal met in July keeps injecting a daily
check in March) · every intervention is created **unassigned** · `studentInterventions` is wired
and called by nothing · **delete `apply_band_suggestions`**, where a five-mark Hindi slip test can
move eleven children between support tiers with one tap.

Then:
- `D-74`/`D-69` **descriptors, monitored subjects, per-subject thresholds** in Settings — nine
  texts, **shipped pre-written and editable**. Everything downstream renders **the sentence, not
  the letter**, because a letter alone is the label P4 exists to prevent.
- `D-75` **per-subject bands, no overall letter** — the read-path rewrite. Today one letter is
  written from the sum of every score in a cycle, so a child who reads two years below grade and is
  fine at arithmetic gets a tier describing neither — and the check generator then hands him easier
  *maths*. A single chip becomes **"C · Hindi"**, never an average.
- `D-76` **promotion** — *Use this as the band test* on an exam she has just locked. A **flag, never
  a type change**; locked only; size shown; small tests **warn, never block**; one subject; and the
  moves reviewed before they commit (`Q-81`).
- `D-77` **one owner per subject** + the weekly check-in, on a page that **opens already written**
  from capture other teachers already did.
- `D-73` the admin board: **movement is the headline**, distribution goes under More.

**Fenced:** no ranking of teachers by children moved. The children handed to the best teacher are
by construction the hardest ones.

---

### V1-10 · Fees — **FIX + WIRE + BUILD**
**Migration:** yes (`fee_notes`) · **Depends on:** V1-1 · **All gates answered** — `D-83`, `D-84`,
`B-2` (year-separate), `Q-67` (quarter = due-date window)

- **The read service first** — one function producing quarter × class × student, batched, with
  `collected / pending / overdue` **kept apart**, quarters as **due-date windows**, and **each
  academic year kept separate** (`B-2`), reachable through the global year switcher that already
  exists. Every screen below is a rendering of this one computation.
- **`D-84` the fee conversation history** — append-only, per student: who spoke to whom, when, and
  **what the family said**. Renders on `/fees/[id]`, and travels into the follow-up task so the next
  caller is not the fourth person this month to ask the same question. Same shape as
  `demo_request_notes` (law 3), newest row is the current state, nothing is ever edited.
- **`D-83` the follow-up task carries the full detail** — history, instalment date, pending amount,
  and that conversation log, in the task description. **This narrows the teachers-and-fees fence and
  the narrowing must be exact:** only the assigned student, only inside the task. No fees nav item
  for a teacher, no class collection figures, no other family, and **no fee chip on any academic
  surface** — not the report card, not growth, not the timeline, not the daily report, not Lucy.
- **`/fees` becomes the collection board** (replacing the landing page, not a 9th tab): sentence →
  **collection curve vs last quarter** → quarter strip → by-class **with both denominators**
  (*"14 of 38 families · ₹1.4L"* — because ₹1.4L is one big defaulter or fourteen small ones, and
  those need opposite actions) → **WIRE** the named defaulter list that has existed since P0-D and
  has never been called.
- Two actions: **Remind** (records that it fired, so nobody is chased twice) and **Assign
  follow-up** (carrying the full detail per `D-83`), each recording **what the family said**, not
  that a button was pressed.
- **Mid-year:** recording what a school already collected before joining, without inventing
  transactions.
- The parent reminder **last**, because it is the only piece that goes to a family: one line, a
  date, what's already paid, a `tel:` link. **It does not render when nothing is due.** Never red,
  never the word defaulter. One per instalment per week, quiet hours, stops the instant payment
  lands.

**The rule that outranks the screen:** no fee status ever reaches an academic surface — not the
report card, not growth, not the timeline, not the daily report, not a Lucy tool.

---

### V1-11 · Parent portal — **BUILD**
**Migration:** small · **Depends on:** V1-2 (code + DOB), V1-3, V1-5, V1-10

- `D-13` login: **school code → class → section → child → date of birth**, with `S-55`
  **type-to-search** on the child step (a browsable list hands the whole roster to anyone with a
  code) and `S-56` **5-attempt lock + hourly throttle**, reusing the OTP module's machinery, which
  already survives request rollback.
- `Q-25` siblings — *"Add another child"*, then the existing switcher works unchanged.
- `D-08`/`D-14` in-app notifications + **web push**, with the Today tab **as** the notification
  surface and the tab as the archive. `S-62`: push is best-effort and the absence alert is not — so
  the admin's board shows **who was not reachable**, and the office phones those few.
- Today gains the pattern, the reason, the fee reminder, and **yellow-pending homework** for days
  the child was absent (`D-35`) — which must be able to **clear** when the teacher waives it.
- `Q-56` the school calendar, read-only, **own child's birthday only**.

**Every field goes through the curated allowlist, field by field, never a spread** — so a new staff
field cannot reach a parent by accident. Never a band, never per-period detail, never another child.

---

### V1-12 · The dashboard visual layer + Lucy reconcile — **BUILD**
**Migration:** no · **Depends on:** all module packets

Apply §7 across the seven tabs: every block gets its sentence, its shape, its named rows and its
action; charts that produce no decision move behind **More**; one chart kit, one palette. Then
reconcile Lucy: her 43 read tools must return the **new** computations (per-subject bands, the
homework verdict set, the attendance status machine) or she becomes a 44th place a fact is computed
differently. Fees stay fenced from her registry.

---

### V1-13 · Hardening & release — **FIX**
**Migration:** no

- 🔴 **Swap production onto the restricted app role.** Prod runs as `doadmin`, so `rolbypassrls =
  true` and **every RLS policy is inert there.** `scripts/provision_app_role.py` exists; this is the
  outstanding piece, and it is a law-2 violation sitting in production.
- Re-seed the demo org against every v1 screen, plus a **mid-year school** fixture (§5's acceptance
  test).
- Full suite green on a real Postgres; the no-dead-ends grep across the whole repo; a walk of all
  three roles at 360px.

---

## 9 · Sequencing

```
  V1-0  Foundation ────────────────────────────────────────────────  everything depends on this
    │
    ├── V1-1  Tasks & the rail ──────────────┐  every module's red row lands here
    │                                        │
    ├── V1-2  Setup & handover ──────────────┼──┬── V1-7  Events & birthdays
    │         (school code · DOB ·           │  │
    │          class teachers)               │  └── V1-11 Parent portal
    │                                        │           ▲
    ├── V1-3  Attendance + My Class ─────────┼───────────┤
    ├── V1-4  Staff · leave · cover · time   │           │
    ├── V1-5  Homework ──────────────────────┼───────────┤
    ├── V1-6  Syllabus · plan · mid-year     │           │
    ├── V1-8  Exams ──── V1-9  Bands ────────┤           │
    └── V1-10 Fees ──────────────────────────┴───────────┘
                                        │
                                  V1-12  Dashboard visual layer + Lucy
                                        │
                                  V1-13  Hardening & release
```

**Three sequencing rules that matter more than the order itself:**

1. **V1-0 ships alone, first, with no features in it.** Every packet after it either reads one of
   those five functions or adds a sixth definition. There is no version of this plan where the
   foundation comes second.
2. **V1-2 before anything parent- or band-shaped.** School code and DOB block the portal entirely;
   class-teacher assignment blocks band ownership and every absence follow-up.
3. **V1-8 before V1-9.** Band promotion requires a locked exam. Building bands first means building
   it twice.

Packets V1-3 through V1-10 are independent of each other once V1-0/1/2 land, so they can be
sequenced by whatever the first customer needs soonest.

---

## 10 · What "production ready" means here

A packet is not done because it compiles. v1 is done when all of the following are true:

| | |
|---|---|
| **No dead ends** | Zero exported client methods with no caller; zero endpoints with no client. Grepped, not assumed. |
| **No second definitions** | Each of the five foundation facts has exactly one implementation, asserted by a test comparing two screens' payloads. |
| **No invented failure** | Not-captured never renders red, never renders zero, never enters a denominator. Tested on a school two weeks old and a school that joined in November. |
| **Every red row acts** | Every row reporting a problem names the person, names the owner, carries an action, and the action remembers it fired. |
| **Mid-year holds** | The §5 acceptance test passes: two months into the year, one term planned, all three roles walked, nothing red that shouldn't be. |
| **The fences hold** | Teachers never see fee data. Bands never reach a parent. The parent projection is field-by-field. The timesheet never touches pay. Asserted by tests, not by review. |
| **RLS is real in production** | The app role swap is done. Until then law 2 is decorative in the one environment that matters. |
| **Mobile is real** | 360px, thumb reach, no horizontal scroll, sticky primary action — walked, not assumed. Teachers use this standing up in front of a class. |

---

## 11 · The risks worth naming now

| Risk | Why it's real | What this plan does |
|---|---|---|
| **The support programme is unused by November** | It is the only feature asking a teacher to type about one child, repeatedly, by hand | `D-87` makes the weekly check-in the unit — four fields, Friday, six children, five minutes — and the page **opens already written** from capture that already happened. A daily note exists but nothing ever asks for one. |
| **A sixth definition gets added during v1** | It has happened in all nine sessions, including twice in code written weeks apart with the reasoning written down only once | Rule 1 becomes a packet-close check, not a preference: name the existing function or say why a second is correct. |
| **The dashboard becomes charts again** | "More visual" is the easiest instruction to over-deliver on | §7's shape is mandatory: a chart with no sentence above it does not ship, and one that produces no decision goes behind More. |
| **Setup takes a week per school** | Three spreadsheets, a wizard and a timetable | The templates come from the importers' own field lists, the by-teacher lens becomes writable, and the readiness report tells the operator exactly what is left. |
| **Payroll comes back mid-build** | It is decided in principle (`D-05`) and it is the most requested school feature there is | v1 ships the **month summary** — days worked out of working days — so the input is captured and correct. Saying yes later is a packet; saying yes now is a different product. |
| **V1-8 (exams) is now the biggest packet and sits late in the order** | `D-80`/`D-81` turned it from corrections into a capture flow **plus** two report levels, and V1-9 (bands) depends on its lock | It is split so the corrections and the lock ship **first** and independently — bands is unblocked by the lock alone. The photo flow and the report levels follow as their own sub-packets. |
| **The catalogue's dates are wrong in year two** | `D-79` accepts wrong dates as survivable because the admin edits them at approval — but that only holds while somebody is *reading* them | Provenance on every row, an editable date, permanent dismissal, and **`Q-63`'s research before the packet is implemented**. The annual re-curation is a named super-admin job, not a hope. |
| **The teachers-and-fees narrowing widens by accident** | `D-83` is the first crack in a fence stated in three documents, and the natural next request is *"let her see her class's list"* | The narrowing is asserted by **tests**, not review: a teacher's payload carries fee data for an assigned student and for nobody else, and no academic surface carries a fee field at all. |

---

## 12 · Immediate next steps

*(Revision 1 — sections A and B are answered; everything above reflects them.)*

1. ~~Answer `BLOCKERS.md` A and B~~ — **done**, recorded as `D-78`–`D-86` in `decisions.md`.
2. **Commit the working tree** — SF-1, HW-1 and DASH3, 77 files, all tested. Building on an
   uncommitted tree makes the first regression unbisectable.
3. **V1-0 starts now** — unaffected by every answer above, the largest single improvement to
   trustworthiness in the product, and it contains no new features to disagree about.
4. **Propagate the two fence changes** into `CLAUDE.md`, `ux-principles.md` and SPRD2 §11 — `D-82`
   (per-student exam photos) and `D-83` (teachers and fees, inside an assigned task only). Do this
   *before* V1-8 and V1-10, or the next person to read the fence will revert the work.
