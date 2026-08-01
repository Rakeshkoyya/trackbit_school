# TrackBit — brainstorm workspace

Where the product gets thought through, module by module, **UI/UX first**, before anything is
built. Sessions started 2026-07-30 and run until every module in the backlog is laid out.

**The goal of this folder:** when it is finished, reading it should let you *see* the product —
screen by screen, role by role — and describe any screen out loud without opening the app.

**This is not a spec.** `docs/` holds the build specs; conflict order there is
SPRD2 > architecture > SPRD v1. This folder outranks nothing. A decision graduates into the spec
when it is ready to build, and this folder records that it graduated.

---

## Start here

| File | What it is |
|---|---|
| **[`HOW-WE-BRAINSTORM.md`](HOW-WE-BRAINSTORM.md)** | The session ritual, the tags, the module backlog. Read this first. |
| **[`ux-principles.md`](ux-principles.md)** | The checklist every screen is designed against. Fifteen rules and the hard fences. |
| **[`decisions.md`](decisions.md)** | The spine — every founder decision, `D-nn`, dated. |
| **[`open-questions.md`](open-questions.md)** | Everything unresolved, `Q-nn`, blocking ones marked 🔴. |

## The two layers

Each module is written down twice, deliberately — once as **thinking**, once as **the thing you
can see**.

### `screens/` — the visualization layer
One file per role. Every screen: the question the user arrives with, what's on it block by block
in order, the actions, the empty states, and what is deliberately kept off it.

- [`screens/admin.md`](screens/admin.md)
- [`screens/teacher.md`](screens/teacher.md) — includes the class-teacher area
- [`screens/parent.md`](screens/parent.md)
- [`screens/_template.md`](screens/_template.md)

*(No `screens/student.md`. Students have no login — `D-07`.)*

### `modules/` — the thinking layer
One file per module: who it's for and when, what they must be able to decide, what exists today,
what's wrong with it, every idea including the rejected ones, and a short data sketch **last**.

- [`modules/attendance.md`](modules/attendance.md)
- [`modules/class-teacher.md`](modules/class-teacher.md)
- [`modules/staff-attendance-leave.md`](modules/staff-attendance-leave.md)
- [`modules/payroll.md`](modules/payroll.md)
- [`modules/syllabus.md`](modules/syllabus.md)
- [`modules/parent-access.md`](modules/parent-access.md)
- [`modules/teacher-load.md`](modules/teacher-load.md)
- [`modules/homework.md`](modules/homework.md)
- [`modules/exams.md`](modules/exams.md)
- [`modules/events-and-dates.md`](modules/events-and-dates.md)
- [`modules/fees.md`](modules/fees.md)
- [`modules/bands.md`](modules/bands.md)
- [`modules/_template.md`](modules/_template.md)

### Also
- [`role-screen-map.md`](role-screen-map.md) — the one-page matrix; every screen × role × status,
  and the list of facts that get rendered on more than one screen
- [`sessions/`](sessions/) — the raw record of each session, in date order

---

## The tags

| Tag | Means | Owner |
|---|---|---|
| **`D-nn`** | **Decided.** Build to this. | founder |
| **`S-nn`** | **Suggestion.** Claude's, not yet accepted or rejected. | Claude |
| **`Q-nn`** | **Open question.** Blocks something. | founder |

Numbers are global and never reused. An accepted `S-nn` becomes a `D-nn`; a rejected one is
marked `REJECTED — <reason>` and **kept**, so it doesn't come back in session six.

Statements about current behaviour are marked *(verified)* with a file reference. Everything
else is intent.

---

## Where we are — start here next session

**Last session:** 9 (2026-08-01) — **bands, the A/B/C support programme, two passes and
FINALISED.** 11 decisions (`D-67`–`D-77`), 25 proposals (`S-164`–`S-188`), 11 questions
(`Q-71`–`Q-81`) of which **four were closed in the second pass**, **five verified defects** — three
of them inside the founder's own sentence *"for every C band child there will be a teacher
assigned."* Read [`sessions/2026-08-01-s9-bands.md`](sessions/2026-08-01-s9-bands.md) — the second
pass is at the bottom. *(Session 8 — fees, `D-62`–`D-66` — is
[here](sessions/2026-08-01-s8-fees.md); session 7 — events & dates, two passes — is
[here](sessions/2026-08-01-s7-events-and-dates.md); session 6 — exams — is
[here](sessions/2026-08-01-s6-exams.md).)*

> **Session 10 (2026-08-01) closed the blockers.** The v1 scope file `docs/v1/BLOCKERS.md` was
> answered end to end and recorded as **`D-78`–`D-88`**: `Q-73` → `D-87` (weekly check-in) ·
> `Q-66` → `D-83` (full fee detail, inside the assigned task only) · `Q-68` → `D-88` (years never
> pool) · `Q-44` → dissolved by `D-85` (no gap threshold; late is a status, teacher-delay is
> derived) · `Q-01` → staff-only writes, `D-86` colour rule · payroll deferred (`D-78`) · the
> catalogue is IN with an editable date at approval (`D-79`) · exams became photo-per-student with
> two report levels (`D-80`–`D-82`). The 38 section-C defaults were accepted wholesale. **The
> build now follows `docs/v1/IMPLEMENTATION-PLAN.md`.** The paragraph below is kept as the
> pre-session-10 state.

**Blocking, in order (pre-session-10):** `Q-73` 🔴 (bands — **daily log or weekly check-in?** decides whether the
module survives a real term; the module's only remaining blocker) · `Q-66` 🔴 (fees — **may a teacher see the amount?**
`D-63` and `D-65` collide) · `Q-68` 🔴 (fees — arrears are invisible in every roll-up, so today's
"pending" is silently wrong) · `Q-67` (fees — how a quarter is defined) · `Q-63` (events — the
sourcing research, **deferred to implementation by the founder**) · `Q-50` (exams — three screens
show a blended number that means
nothing) · `Q-51` (the exam-paper AI fence) · `Q-61` `Q-62` (the exam training corpus — consent,
and what a lock means) · `Q-24` `Q-25` `Q-27` (parent access — all three change the data model) ·
`Q-01` `Q-02` `Q-03` (attendance, session 1) · `Q-05`–`Q-08` (payroll — `Q-08` narrowed by
`D-25`). **Teacher load, homework and tasks block nothing.**

> **`D-61` closed `Q-55`** — the catalogue is scoped by **school code, address (→ state) and
> board**, all of which setup already collects, so no school is ever asked to declare a region
> or a religion.
>
> **Events is now buildable without its blocker.** `D-56`–`D-60` closed the DOB questions and
> reframed the calendar as a suggestion stream. Steps 1–6 of its build order — DOB at setup, the
> approval sheet with three lock levels, the cost preview, the teacher's *not held*, the read
> service and the two cards — need **none** of `Q-63`. Only the catalogue does.

**Fix regardless of any decision** — live defects found in sessions 3 and 4, all small:

| | |
|---|---|
| 🔴 `S-72` | `/staff/today` shows an absent teacher as eight free periods — on the screen used to find cover |
| 🔴 `S-82` | `busy_reason` can't see approved leave, so `D-27` would let cover be assigned to someone on leave |
| 🔴 `S-85` `S-102` | A child absent when homework was set is flagged not-done and their guardian is reminded about work they never received. `D-34` fixes it; the carried state must also be invisible to the streak |
| `S-74` | The cover picker never reads the timesheet |
| `S-86` | The per-student homework history is built, wired into the client, and called by nothing — `D-36`'s by-student view is the same component |
| `S-93` | A substitute can't check homework, though the column recording who checked was added for that case |
| `Q-37` | Covering a period doesn't appear on the substitute's own timesheet |
| 🔴 `D-48` / `S-111` | `/tasks` re-filters board rows on the client, so an **admin sees none of the follow-ups they assigned** — the server's answer was already correct. **Accepted for fixing.** |
| `D-48` / `S-112` | Rail follow-ups default to midnight **UTC**, so a task assigned Monday is overdue at 05:30 Tuesday. **Accepted for fixing.** |
| `D-47` / `S-107` | The rail dedupes per calendar day, so three days of absence create three identical open tasks. **Accepted for fixing.** |
| 🔴 `D-55` / `S-113` | `assessment_cycles.type` is a 9-value CHECK constraint, so a school running **CET** cannot record one — the opposite of the answer `core/work_types.py` gave three weeks earlier, with its reasoning written down. **Decided:** a new field beside `type`, `S-135` recommends a small `exam_types` table |
| 🔴 `D-53` / `S-136` | `ExamService.save` full-deletes and re-inserts a cycle's scores on every edit, so a mark corrected in November silently replaces the one confirmed in July with no record they differed. Survivable for a report card; **fatal for `D-54`'s training corpus** — the lock is what freezes the label |
| 🔴 `S-114` | Slip tests and term exams pool into one average on `/dashboard/exams`, the class analytics **and** the student report card — and the type filter defaults to off |
| `S-115` | `assessment_cycles` has no `exam_event_id`, so V2-P7's exam portions and the recorded marks can never be joined |
| `S-119` | Exam photos are kept forever as evidence and rendered on the exam screen, but `/students/[id]` shows a mark with no way back to the paper |
| exams §4.5 | `ExamService.save` never sets `verified_by`, so the *"· verified"* badge on the scores feed can never light up for an SC-5 exam |
| 🔴 events §4.2 | **Painting a "Celebration" on Plan → Year silently removes a teaching day**, even when the school is open — `affects_teaching` defaults to `True` (`schemas/calendar.py:17`) and the paint UI never sends the field (`plan/page.tsx:82-90`). Every plan forecast is denominated in effective teaching days. **Live now, unrelated to whether the events module is ever built.** ✅ **`D-58`'s approval sheet closes this as a side effect** — the open/closed choice becomes the central act of the flow (`S-142`), so building step 2 of the events module *is* the fix. |
| events §4.1 | `calendar_events` has had a write side for a year and **no read side** — its only consumer is the effective-days engine, so a school's own calendar can never be seen |
| 🔴 fees §4.2 | **Arrears are invisible in every fee roll-up.** `student_fees.opening_dues` is excluded from `total_fee`, `collected_fee`, `overdue_amount` **and** `status` — so a student carrying ₹20,000 from last year with this year's instalments paid reads `paid` and never appears on the defaulter list. The school's worst debtors are the ones the screen cannot see (`Q-68`). |
| 🔴 fees §4.1 | `GET /fees/overdue-students` returns the named defaulter list and **`school-api.ts` never calls it** — the founder's "which student hasn't paid" is computed on the server today and invisible. *Third instance of this pattern after `S-86` and `S-74`.* |
| fees §4.4 | `overdue_students` runs `db.get(SchoolClass, …)` **per student** — 200 overdue students is 200 remote round trips for one list (`S-162`) |
| 🔴 bands §4.4 | **An intervention can never be finished.** `Intervention.status` allows `achieved`, and there are exactly two intervention endpoints — `POST` and `GET`. Nothing updates it. And `recommendations._intervention_students` filters `status == 'active'`, so **a goal achieved in July keeps injecting a targeted daily check into the period card in March.** The single loop the bands module exists to close is the one thing the code cannot do (`S-180`) |
| 🔴 bands §4.3 | **Every intervention in every real school is created unassigned** — `create_intervention` assigns to `school_classes.class_teacher_member_id`, which **no screen sets** (session 1's `S-20`, still unbuilt). The founder's "a teacher is responsible for this child" is already in the code as a dead link |
| 🔴 bands §4.1 | `categorize_from_cycle` writes **one overall letter** from the sum of every score in a cycle, so a child who reads two years below grade and is fine at arithmetic gets a tier describing neither — and the check generator then gives him easier *maths*. `student_bands.scope_skill_area_id` exists for this and **has never been written by any code path** (`D-68`) |
| 🔴 bands §4.2 | `apply_band_suggestions` re-bands a whole class from each child's **most recent cycle, whatever it is** — a five-mark Hindi slip test can move eleven children between support tiers with one tap. Same family as `S-114`. ✅ **Decided: delete it** (`S-183`) — `D-76`'s explicit test promotion replaces it, so this is a removal rather than a patch |
| bands §4.5 | `schoolApi.studentInterventions` is wired into the client and **called by nothing** — the report card shows the tier and never the plan attached to it. **Fourth instance** after `S-86`, `S-74` and the fees defaulter list |

*(`S-83` — the yesterday-only homework queue — is now fixed by design rather than by patch: `D-33`
means nothing ever expires off the teacher's screen.)*

**One question to answer before homework is built:** `Q-44` 🔴 — past the late threshold, is
"late" a fact about the **child** or about the **record**? A teacher who recorded on Friday what
she collected on Tuesday must not write "did it late" into a student's history.

**Next module:** founder's call. **Students** is the natural next one — six sessions have now
added blocks to `/students/[id]` without anyone designing the page: session 7 adds a date of birth
and session 9 adds the support-programme block. Dashboard and notifications stay last.

## Progress

| Module | Thought through | Screens written | Blocked on |
|---|---|---|---|
| Attendance | ✅ session 1 | ✅ | `Q-01` `Q-02` `Q-03` |
| Class teacher | ✅ session 1 | ✅ | `Q-09` `Q-10` |
| Staff attendance / leave | 🟡 partial | 🟡 partial | `Q-08` `Q-15` |
| Payroll | 🟡 decisions only | 🟡 outline | `Q-05` `Q-06` `Q-07` `Q-08` |
| **Syllabus** | ✅ session 2 | ✅ | `Q-16` · `S-44b` sign-off |
| **Parent access** (login + reach) | ✅ session 2 | ✅ | `Q-24` `Q-25` `Q-27` 🔴 |
| Notifications delivery | ✅ `D-08` `D-14` | ✅ | — |
| **Teacher load** (the period module) | ✅ session 3 | ✅ | — *(closed; `Q-32`–`Q-37` are small)* |
| **Substitution / cover** | ✅ session 3 | ✅ | — *(`S-82` is a bug, not a question)* |
| **Homework** | ✅ session 4 | ✅ | `Q-44` 🔴 *(one word, permanent record)* · `Q-39` `Q-40` `Q-43` small |
| **Tasks** | ✅ session 5 *(board + My Day only; internals not reopened)* | ✅ | — *(closed — `Q-45`–`Q-48` all answered in-session)* |
| **Exams & scores** | ✅ session 6 *(+ a second pass: verify-and-lock, the training corpus)* | ✅ | `Q-50` 🔴 *(live wrong data)* · `Q-51` 🔴 *(fence)* · `Q-61` 🔴 *(corpus consent)* · `Q-52` `Q-53` `Q-62` |
| **Events & dates** | ✅ session 7 *(two passes)* | ✅ | `Q-63` 🔴 *(the sourcing research — blocks the catalogue only)* · `Q-55` 🔴 · `Q-65` *(locking a past day)* · `Q-56` `Q-58` `Q-60` `Q-64` — *(`Q-57` `Q-59` closed by `D-56`; `Q-54` reshaped into `Q-63` by `D-60`)* |
| **Fees** | ✅ session 8 | ✅ | `Q-66` 🔴 *(the fence: may a teacher see the amount)* · `Q-68` 🔴 *(arrears — live wrong data)* · `Q-67` `Q-69` `Q-70` |
| **Bands** (the support programme) | ✅ session 9, **two passes — FINALISED** | ✅ | `Q-73` 🔴 *(log cadence — decides if it's used)* · `Q-75` `Q-76` `Q-78` `Q-80` `Q-81` *(copy and grain, none blocking)* — *(`Q-71` `Q-72` `Q-74` `Q-77` closed by `D-75`–`D-77`; `Q-79` narrowed to entry)* |
| Students · Planner · Timetable · Sessions · Parent portal · Dashboard · Setup · Lucy | — | — | — |

**Second recurring defect, new in session 6:** *the same design question answered opposite ways in
two modules, weeks apart.* `core/work_types.py` deliberately has **no CHECK constraint** — *"a
school that renames its work must never lose rows to a database error"* — while
`assessment_cycles.type` is a 9-value CHECK, so a school running **CET** cannot record one
(`S-113`). Both were written by us; only one wrote its reasoning down, which is why only one is
right. **Checklist item: when a new column enumerates a school's vocabulary, cite the module that
already made that choice.**

**Recurring defect worth naming:** all five sessions have found the *same* class of bug — one fact
computed several different ways in different places (three definitions of "absent for a day"; two
of "syllabus covered"; two of "who is free right now", one of which offers absent teachers as
substitutes; two of what a "partial" is worth; and now, in session 5, a **visibility rule decided
correctly on the server and then re-decided in a React component** — `S-111`). This is now beyond a
preference. *One computation, many renderings* (`ux-principles` §9) should be a build rule with a
checklist item: **when you add a figure or a rule, name the existing function that computes it, or
say why a second one is correct.** Session 5 extends it past figures to **authorization**, where a
second implementation is not a discrepancy but a leak or a blackout.

**Second pattern, newly visible:** a capture surface needs a row that says *a human was here*.
`class_periods.attendance_marked_at`, `staff_attendance_days` and `homework_checks` all have one;
the timesheet does not. For the timesheet that is now a **deliberate** choice (`D-23` — free is
the safe default when the question is "who can cover 11:20"), but the question must be asked
explicitly of every new capture table, because in attendance and homework the answer went the
other way.

Full backlog and ordering advice in [`HOW-WE-BRAINSTORM.md`](HOW-WE-BRAINSTORM.md).

---

## Rules for this folder

1. **No code during a brainstorm session.** No migrations, no packets, no branches.
2. **Ground every module in the real code first**, and mark those statements *(verified)*.
3. **Nothing gets deleted** — rejected ideas are marked, not removed.
4. **The data model comes last** in every module file, and stays short. If that section is
   longer than the ideas section, the session drifted into building.
