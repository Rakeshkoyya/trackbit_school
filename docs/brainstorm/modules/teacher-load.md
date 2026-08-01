# Module — teacher load (the period module)

What every member of staff is doing with every period of the day: the classes the timetable
already gave them, the work they choose for the gaps, the duty the school puts on them — and,
out of all that, the one answer the office needs twenty times a week: **who is free right now.**

**Sessions:** 3 (2026-07-31)
**Related:** [`staff-attendance-leave.md`](staff-attendance-leave.md) ·
[`payroll.md`](payroll.md) · [`attendance.md`](attendance.md) *(the cover board)*

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Teacher** | Sunday night / the night before | phone or laptop, minutes | *"What does my week look like, and what am I doing in the gaps?"* |
| **Teacher** | 8:40am, staff room | phone, **seconds** | *"What's my day?"* |
| **Teacher** | as it happens, between classes | phone, one hand, **seconds** | *"I just spent period 5 on the exam papers — record it."* |
| **Teacher** | 4pm | phone, minutes | *"I never filled in Tuesday."* |
| **Admin** | 9:12am, a teacher has phoned in sick | desktop, **under a minute** | *"Who can take 7-A Maths at 11:20 — and is that person genuinely free?"* |
| **Admin** | planning a staff meeting / exam duty | desktop, minutes | *"When is the whole staff free at the same time, and who has the room to take this on?"* |
| **Admin** | end of month | desktop | *"Is the load fair? Who is carrying the invisible work?"* |

Two of these are the module. The 9:12am admin is why it exists at all; the as-it-happens teacher
is the one who has to be persuaded to feed it.

## 2 · What they must be able to decide

- **Who covers this period.** Named, ranked, and *actually* free — not free-looking.
- **When to put a whole-staff thing in the calendar** — a meeting, an assembly, a training.
- **Who to hand a duty to** — invigilation, an event, a visitor — without pulling someone out of
  something.
- **Whether the load is fair** — before a teacher says it isn't, in a room, in front of others.
- *(teacher)* **What her own week is**, including the parts nobody timetabled.

## 3 · Where it stands today *(verified in code, 2026-07-31)*

**Far more of this is built than the founder's description assumes.** SF-1 (2026-07-29) shipped
the whole capture side and DASH3 shipped most of the admin side. What is missing is a calendar,
a configuration screen, one chart — and a distinction that has never existed (§4.1).

### The capture — `timesheet_entries` (SF-1)

- One row per **(member, date, period_no)** — `api/app/models/staff.py:119`. Unique-constrained,
  so a period is *free*, *teaching*, or **exactly one** piece of work.
- **Teaching periods are never stored here.** `TimesheetService._teaching`
  (`api/app/services/timesheet.py:85`) reads them straight off `timetable_slots` and renders them
  locked; `set_entry` refuses an entry under a taught period with the class named. One source of
  truth per period, deliberately (`timesheet.py:9-20`).
- `period_no` means the same thing everywhere in the product, because
  `services/school_clock.py` is the only place that maps a wall clock to a number: the 1-based
  index among `period_times` entries with `kind == 'period'`, so a lunch break shifts nothing.
- **Editable all day, forever, with no lock** — `set_entry` upserts, `clear_entry` deletes.

### The categories — `core/work_types.py`

Eight buckets: notebook checking · exam work · event work · student support · lesson preparation ·
meeting · administrative · other. **No CHECK constraint on the column** and `normalize()`
deliberately keeps a school's own word rather than flattening it to `other`, so *the storage is
already ready for `D-19`* — only the picker is hardcoded.

### The teacher's screens

| Route | What it is |
|---|---|
| `/timesheet` | **Week grid.** Periods down, days across. Teaching cells locked and green; free cells show `+`; tap → a sheet with the eight buckets, an optional free-text name for *Other*, and a note. Week arrows. Three counters: teaching / recorded / still open. |
| `/timesheet/leave` | Balance, apply, own history. |

**There is no month view and no day view.** The week grid is the only altitude.

### The admin's screens

| Route | What it is |
|---|---|
| `/staff/today` | **The teacher × period grid** the founder described — one row per staff member, one column per period, cell = subject / work label / `—`. Plus three tiles. One payload, three queries. |
| `/dashboard/staff` | The analytical tab: four tiles, the **live "right now" board** (teaching · on other work · free · away, *every list named*), away-today rows with periods-due-vs-covered and an **Arrange cover** sheet, the leave queue, teaching-periods-vs-mean bars, a **what non-teaching periods went on** bucket chart, and a day strip per teacher. |

`WorkloadInsights.now()` (`services/insights/workload.py:203`) already degrades honestly —
`before` / `period` / `break` / `after` / `holiday` / `unset` — rather than claiming "Period 4" on
a Sunday.

### So, against the founder's list

| Asked for | Status |
|---|---|
| Teacher sees pre-assigned classes | ✅ built (`/timesheet`, and My Day) |
| Teacher blocks the gaps with a category | ✅ built |
| Fill the night before / morning / as-you-go | ✅ built — nothing prevents any of the three |
| Categories configurable per org | ❌ hardcoded dict; storage already allows it |
| **Calendar view — month / week / day** | 🟡 week only |
| Admin day grid, teacher × period | ✅ built twice, and the two disagree (§4.2) |
| Chart: how many are busy at a given time | ❌ **the one genuinely new chart** |
| A tab with detail + filters | 🟡 `/dashboard/staff` has the detail, no filters |

## 4 · What's wrong with it

### 4.1 ~~🔴 The module cannot tell "free" from "didn't fill it in"~~ → **CLOSED by `D-23`**

> **Decided: an unfilled period is free.** No day-confirm row, no third state. Claude's `S-61` was
> rejected — see `D-23` for the argument *for* the decision (free is the correct default bias for
> the cover question) and the two consequences that follow: the "free periods unlogged" tile is
> **deleted rather than fixed** (`S-76`, which also disposes of §4.4), and the chart's free band is
> labelled *"free or unrecorded"* once, in the hint.
>
> The analysis below is kept because it explains why those two copy changes exist.

This was the structural finding of the session and everything else followed from it.

Every other capture surface in this product carries a marker that says *the human was here*:

| Module | The "somebody actually looked" row |
|---|---|
| Student attendance | `class_periods.attendance_marked_at` |
| Staff attendance | `staff_attendance_days` — one row per org × date |
| Homework | `homework_checks` — its **absence** means `not_checked`, never "everyone did it" |
| **Timesheet** | **nothing** |

An empty cell on the timesheet is rendered as `free`. It means either *"she genuinely had nothing
on"* or *"she has never opened this screen"*, and no screen, service or figure in the product can
distinguish them. Consequences, all live today:

- `/dashboard/staff`'s **"Free periods unlogged"** tile is the school's adoption rate wearing the
  costume of a workload figure.
- The founder's requested **busy-at-a-given-time chart would measure app usage**, not the school.
- The live board tells the admin four people are free when the true answer may be *"two are free
  and two never told us."*
- It breaks `ux-principles` §5 — *not-captured is never a failure and never a zero* — which the
  rest of the product spent three modules getting right.

→ **`S-61`**, and it is the one thing that must be settled before any of this is built (`Q-31`).

### 4.2 🔴 The same grid is computed twice, and the two versions disagree

`/staff/today` renders `TimesheetService.org_day` (grid + timesheet entries). `/dashboard/staff`
renders `WorkloadInsights.week().teachers[].today` (grid + entries **+ substitutions + staff
absence**).

So on `/staff/today` — the screen whose subtitle is literally *"Who is teaching, who is on other
work, who is free"* — **a teacher who is absent today shows eight free periods**, and a teacher
covering three of someone else's periods shows free in all three. The admin looking for cover is
shown the two worst possible candidates at the top of the list.

Third instance of *one fact, several computations* (session 1: three definitions of "absent for a
day"; session 2: two definitions of "syllabus covered"). → **`S-72`**.

### 4.3 🔴 The cover picker ignores the timesheet — the module ignores its own data

`SubstitutionService.busy_reason` (`services/substitution.py:116`) refuses a substitute who is
*teaching*, *already covering*, or *marked away*. It does not look at `timesheet_entries` at all.
`AttendanceInsights._candidates` (`insights/attendance.py:453`) ranks candidates by subject fit
and **teaching** load, and labels the rest `"free · N periods today"`.

So a teacher who recorded *"exam work — Class 10 answer scripts"* for period 4 is offered to the
admin, in writing, as **free**. The one moment the timesheet was built for is the one moment
nothing reads it. → **`S-74`**.

### 4.4 The unlogged tile is at its reddest when nothing could have been logged

`WorkloadInsights.week()` counts a free cell as unfilled for **every period of today**, including
periods that have not happened yet (`workload.py:353-355`). At 8:30am the tile shows the whole
day's free periods as "unlogged". `ux-principles` §5 again, and the corollary spelled out there:
*an admin who marks staff attendance at 10am must not see a red tile every morning.*

### 4.5 Non-teaching staff are counted as though they were teachers

`org_day` lists every active membership, so `/staff/today`'s **"Free periods"** tile includes the
principal's eight and the office clerk's eight. `WorkloadInsights` is careful about this for the
*mean* (`workload.py:326-328` — "the mean is over people who teach at all") and not for anything
else.

### 4.6 The warden's evening does not exist

`sessions` carry `owner_member_id`, `weekdays`, `time`, `end_time` (`models/sessions.py:39`) —
evening prep, homework class, Saturday yoga, all staffed by a named teacher. **No load surface
reads them.** In a hostel school — the product's own positioning, *"school + hostel hours"* — the
teacher who runs prep six evenings a week appears on every board as somebody with a light load.
→ **`S-68`**.

### 4.7 Smaller, verified

- `TimesheetEntry.updated_at` has a server default and **is never bumped** by `set_entry`, so
  today there is no way to tell a period recorded at 11am from one back-filled in March
  (`S-71`).
- `TimesheetService.week` drops any weekday not in `working_weekdays`, so a one-off working Sunday
  — sports day, an exam — **cannot be recorded at all**.
- An entry sitting under a period that later becomes a teaching period is ignored rather than
  surfaced. Deliberate and documented; worth remembering when the grid is edited mid-term.

### 4.8 And the human problem, which is bigger than all of the above

**Nothing in this module gives the teacher anything.** She types what she did, and the output
appears on the principal's dashboard. That is a compliance chore, and `ux-principles` §12 (P3 —
*value before data*) exists precisely because chores get filled in for three weeks and then stop.
The module's failure mode is not a bug; it is a blank grid in November. → `S-70`, `S-62`, `S-63`.

## 5 · Ideas and directions

### Decided — `D-18`–`D-29`
See [`../decisions.md`](../decisions.md). In short: a teacher calendar at three altitudes ·
org-configurable categories · fill it whenever you like · an admin day grid plus a
busy-at-a-time chart plus a filterable detail tab · **the teacher's daily job is exactly two
things, forever** · an unfilled period is **free** · the timesheet is **its own section** ·
**it never touches pay** · substitution is a two-panel assign screen, reachable **from a leave
approval**, suggesting by **syllabus pending** · and the teacher→classes mapping becomes editable.

### Proposed — `S-nn`

**`S-61` — give the day a row: `timesheet_days`.**
**REJECTED — `D-23`: an unfilled period is free and the school does not care about the
"not filled" case.** The proposal was a one-tap *"That's my day"* so that *free* and *never told
us* were different states, matching `staff_attendance_days` and `homework_checks`. Kept because
two live consequences hang off the rejection (`S-76`), and because the next capture table that
gets designed should still be checked against this question.

**`S-62` — the week repeats: a pre-filled weekly pattern.**
**SUPERSEDED by `S-75`.** The idea was sound but its safety rail was `S-61`: a pattern could
*propose* while a confirmation *recorded*. With `D-23` there is no confirmation step, so a
pre-filled week would be a **record the teacher never wrote** — the fiction generator the original
note warned about. `S-75` keeps the labour saving without the fabrication.

**`S-63` — the teacher's day is ONE list, not two screens.**
**REJECTED — `D-24`: the timesheet stays its own section**, so it does not get mixed into the
daily class capture. Founder's reasoning: the daily capture flow is the sharpest, most
time-pressured surface in the product and nothing else belongs in it. Kept with the reason,
because the adoption problem it was solving (`§4.8`) is still real and now falls to `S-75` and
`S-70` instead.

**`S-64` — month = shape · week = edit · day = do. Three jobs, not three renderings.**
A month of 8 periods × 25 days is 200 cells; on a phone it is unreadable and unfillable. But
`ux-principles` §15 says *shape beats number for patterns* — so give the month **one cell per
day** carrying a day's state, and let it be a navigator rather than an editor:

```
        M   T   W   T   F   S
   1                ▓▓▌ ▓▓▌ ▓░░
   2   ▓▓▓ ▓▓▌ ███ ▓▓▓ ▓░░ ·H·      ▓ taught  ▌ recorded  ░ open
   3   ▓▓▓ ▓▓▓ ·L· ·L· ▓▓▌ ▓▓▓      L leave   H holiday   E exam day
   4   ▓░░ ▓▓▌ ▓▓▓ ▓▓▓ ███ ·E·      · nothing recorded
```

Leave, holidays and exam days come from `CalendarEvent` / `leave_requests` — **reused, not
re-derived** (§9), or the teacher sees "gaps" on Diwali. Tap a day → the day view. The day view is
a vertical timeline including breaks (`school_clock.breaks_of` already returns them) and is the
one people actually fill in. The week grid stays the best *editing* surface and is already built.

**`S-65` — the admin can push work into a free period. `period_substitutions` is already this.**
Half the work in a school is not chosen, it is assigned: invigilation, ground duty, an event,
receiving a visitor. Today the timesheet is purely self-reported, so the school's *rota* lives in
a WhatsApp group and the module cannot see it. And the general case is already built for one
special case — a substitution *is* the admin putting a named teacher in a named period
(`services/substitution.py`, with a live-rows-only partial index and a real busy check).

Proposal: a timesheet entry gains a **`source`** — `self` | `assigned` — and the admin can create
an assigned one from the same cover sheet. The teacher sees it on her day, coloured differently,
and can flag a clash rather than silently delete it.

This is the difference between a diary and a load module: the admin's screen stops answering
*"who is free"* and starts answering *"who is free — give it to her."*

⚠️ Needs `Q-32` first, and it needs a conflict rule: one entry per period is what makes every
total meaningful, so an assignment onto an occupied period must be a *replace with a warning*, not
a second row.

**`S-66` — the slack profile, and what it is for.**
The founder's chart. One stacked bar per period across the day:

```
      P1   P2   P3   P4   P5   P6   P7   P8
     ███  ███  ███  ███  ██▓  ██   █▓   █
      12   12   11   12   9    8    6    4     teaching
      0    0    1    0    2    2    3    2     other work (recorded)
      1    1    1    1    2    3    4    7     free
      ↑ nothing can be scheduled              ↑ this is the slack
```

Its job is **finding slack**, not surveillance: *when can the whole staff meet · which period
should invigilation come out of · is period 8 dead time across the school*. Frame it that way on
the screen and add one derived line — *"Period 7 on Thursday is the only slot where 11 of 14 are
free"* — because that sentence is the decision, and the bars are its evidence (§2).

Honest only if `S-61` lands; otherwise the "free" band is measuring the app.

**`S-67` — the fence: this must never become a scoreboard. → ACCEPTED on the money half (`D-25`).**

> **`D-25`: payroll is computed purely from present/absent on the day plus half-day leave. The
> timesheet never touches pay.** That closes `Q-30` and the highest-stakes half of this fence. The
> no-leaderboard half is Claude's and remains a recommendation.

A per-teacher record of what was done with every period, visible to the principal, is one design
decision away from a performance-monitoring tool — and the syllabus module already wrote the
argument down: *the moment coverage % scores a teacher, lesson logs stop being honest, and every
downstream number in the product is built on them.* Exactly the same applies here, harder, because
this data is about a person's hour rather than a class's chapter.

Recommended non-goals, stated as fences rather than preferences:

- **No leaderboard.** No "periods recorded" ranking, no completeness % per teacher shown school-
  wide, no export that names and orders people.
- **No path to money.** `D-05` made days-present drive salary *eight days before this session*.
  If timesheet completeness ever touches pay, every free period becomes "exam work" within a
  month and the module is worthless from that day on. `Q-30`, and it is the highest-stakes
  question here.
- **Load is compared to the mean, never ranked** — `WorkloadInsights` already does this correctly
  (`over` / `balanced` / `under` against the org mean, mean computed over people who teach at
  all). Keep that framing everywhere: *needs support / carrying more*, never 1st–14th.

**`S-68` — hostel sessions are load.**
`sessions.owner_member_id` + `weekdays` + `time`/`end_time` is a staffed, recurring, timetabled
block that no load surface reads. A warden running evening prep six nights a week is invisible on
the load board, on the mean, and on the fairness question. Union them in — read-only, like the
timetable, since the session grid owns them.

**`S-69` — configurable categories, done so old rows survive.**
`D-19`. Four rules, all cheap, all painful to retrofit:

1. **Stable key, mutable label.** A school renaming "Event work" to "Programmes" must not orphan
   last term's rows. `label_for()` already folds an unknown key into a titled label rather than
   dropping it — build on that.
2. **Retire, never delete.** A disabled category keeps rendering on historical entries.
3. **Keep the list short.** ~10 visible, maximum. A long picker makes a teacher think, and a
   teacher who thinks about a dropdown stops filling it in — `work_types.py` says this in its own
   docstring and it is right.
4. **"Other + type it" is always present**, and what people type there is the school telling you
   what its real ninth category is. Surface the top free-text values to the admin in Settings.

**`S-70` — give her the number back (P3).**
The teacher's own week, on her own screen, in her own words: *"27 periods taught · 6 recorded ·
3 covered for colleagues · 4 evenings."* That is a record she can point at when she is asked to
take a fourth cover this week, which makes it hers rather than the principal's. It costs one line
of UI and it is the difference between a filled sheet and an empty one.

**`S-71` — mark back-filled entries; do not block them.**
`D-20` says fill it whenever. A hard lock would just stop it being filled at all. But an entry
written three weeks later is weaker evidence than one written at 11:58, and the column to say so
already exists — `updated_at`, currently never bumped. Bump it, and let the admin's detail tab
distinguish *recorded that day* from *back-filled*. Cheap honesty with zero friction.

**`S-72` — one grid, one computation.**
Fix §4.2 by deleting one of them. `WorkloadInsights` is the correct one (it knows about absence
and cover); `/staff/today` should render it. Then the absent teacher stops being offered as cover
and the two screens can never drift again (§9).

**`S-73` — keep the timesheet period-indexed; out-of-hours work is a different shape.**
A 4pm parents' meeting, a Saturday event, an 8am staff briefing have no `period_no`, and
`period_no` is exactly what makes *"who is free in period 4"* answerable. Recommendation: keep
entries period-indexed for v1 and give the day a small **extra duty** line (a day-level note, not
a period) for what happens outside the bell. Resist a second time model until a school actually
asks. `Q-33`.

**`S-74` — the cover picker must read the timesheet.**
Fix §4.3, but do **not** turn a timesheet entry into a hard block — an entry is a plan, and
covering a class beats checking notebooks on any morning. Instead: rank, and say why.

```
Meera    teaches Maths in 8-B          free                     ← best
Anil     teaches this class            free
Priya    free                          notebook checking 6-A    ← still pickable, now visible
Ramesh   free                          nothing recorded
```

Two lines of ranking, and the admin stops pulling someone out of work they had already committed
to. It also gives the teacher a reason to fill the sheet in — `S-70`'s point, made structurally.

---

*The proposals below came out of the founder's answers: `D-23`–`D-29`.*

**`S-75` — the pattern pre-*selects*, it never pre-*fills*.** (replaces `S-62` under `D-23`)
The labour saving that survives without a confirmation step: when she taps Tuesday P3, the picker
opens with **"Notebook checking"** already highlighted, because that is what she has recorded in
that slot for six weeks. One tap instead of two, and **nothing is written until she taps save**.
No row exists that a human did not put there — which is the property `D-23` removed the ability to
guarantee any other way.

Same idea, second place it pays: the **most-used category first** in the picker rather than a
fixed alphabetical eight.

**`S-76` — delete the "free periods unlogged" tile; don't fix it.**
Under `D-23` there is no such state. A tile counting it is counting nothing the school has agreed
is a problem, and *(verified)* it also counts periods that have not happened yet, so it is at its
reddest at 8:30am. Deleting it resolves §4.4 outright.

**Then say what the free band is, once.** On `D-21`'s chart, *free* now legitimately means "free
**or** unrecorded". One line in the hint (`ux-principles` §4 — every figure carries its
denominator) keeps the chart honest without reopening the decision.

**`S-77` — `D-28` is a switch, not a screen: make the by-teacher view writable.**
*(verified)* `/setup` → Assignments already has **two lenses** over `class_subjects`: by class
(editable — a teacher `<select>` per subject row) and **by teacher** (`ByTeacherView` — the
teacher's classes, subjects, periods/week, a class-teacher badge, and an *"N subjects have no
teacher"* warning). The by-teacher lens is **read-only**, and its own empty state says *"Nothing
assigned yet — assign subjects from the class view."*

So the founder's *"teacher 1 → classes 3, 4, 5 Hindi"* screen is that view with save on it: pick
the teacher, tick the class-subjects, save many at once — instead of opening five classes and
setting five dropdowns. `PATCH /academics/class-subjects/{id}` already accepts
`teacher_member_id`.

Two things to fix while it is open: it fires **one query per class** (`useQueries` over every
class) — batch it before it becomes an editor; and the periods/week total already turns red past
48, which is the beginning of a real load validator and should be stated as one rather than left
as a badge colour.

**`S-78` — the cover panel's right side should say what is given up and what is gained.**
`D-26`'s two panels, with `S-74` and `D-29` folded into the candidate rows so the admin is
choosing between comparable things:

```
7-A · Period 4 · Maths          next planned topic: Fractions — multiplication

  Meera    teaches Maths in 8-B    free            → can teach the next topic   [Assign]
  Anil     teaches this class      free                                         [Assign]
  Priya    free                    notebook checking 6-A                        [Assign]
  Ramesh   free                    his own 7-C Maths is 2 weeks behind          [Assign]
```

Every row still assignable — the rank is a suggestion and the admin knows things the system does
not. But *"can teach the next topic"* and *"is 2 weeks behind himself"* are the two sentences that
change the decision, and neither is on the screen today.

**`S-79` — "syllabus pending" cuts two ways, and both are useful.**
`D-29` can be read two ways; they are complementary, not alternatives:

- **(a) Positive — will this cover be a real lesson?** The planner already knows the class's next
  planned topic. A substitute who teaches that subject elsewhere can move the syllabus forward
  instead of supervising a study period. **This is the strongest reason to prefer a candidate**
  and it should be the top tier, replacing the current bare *"teaches this subject elsewhere"*.
- **(b) Negative — don't rob Peter to pay Paul.** A teacher who is behind in her own subjects is
  the worst person to give an extra period to. Use it as a warning on the row, never a block.

Worth knowing: **(a) needs no new plumbing downstream.** The period card credits the class-subject,
not the person, so a topic taught by a substitute lands in the class's lesson log and the
forecast picks it up automatically. P2 holds — the plan is still the baseline, the log is still
the actual.

**`S-80` — the leave→cover bridge is a date parameter and an entry point.**
*(verified)* `CoverSheet` opens only from an *"away today"* row driven by today's staff
attendance, and its query is anchored to today. `SubstitutionService.create` already takes any
date, and `busy_reason` already takes a date. So `D-27` is: a **Arrange cover** action on an
approved leave request, opening the same sheet with the leave's dates — one per day of the leave.

**`S-81` — an approved leave should *create* the cover work, not wait to be remembered.**
The moment leave is approved, the periods that will be uncovered are known. Put them on the
admin's action rail dated to that day — *"Friday: Anil away, 5 periods to cover"* — rather than
relying on someone reopening the leave screen. The rail already exists and already works this way
for everything else, and `followup_actions` already stops the same item being actioned twice.

**`S-82` — 🔴 the busy check does not know about future leave.**
*(verified)* `busy_reason` refuses a substitute who is teaching, already covering, or **has a
`staff_absences` row for that date**. For a future date **there is no staff attendance row yet** —
nobody has marked Friday. And it never looks at `leave_requests`.

So the moment `D-27` ships, **an admin can assign Friday's cover to a teacher who is herself on
approved leave on Friday**, and the system will accept it without a word. The fix is one clause —
check for an approved leave spanning that date — and it must ship *with* `D-27`, not after it.

### Rejected

- **`S-61`** — the day-confirm row. `D-23`: an unfilled period is free; the "not filled" case is
  not a case.
- **`S-62`** — the pre-filled weekly pattern. Superseded by `S-75`, because `D-23` removed the
  confirmation step that made pre-filling safe.
- **`S-63`** — folding free periods into My Day. `D-24`: the timesheet stays its own section,
  clear of the daily class capture.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `/my-day` | teacher | UNCHANGED by this module (`D-24`) | *"What's next?"* — the timesheet stays out of it |
| `/timesheet` (week) | teacher | EXISTS, small changes | *"What does my week look like?"* |
| `/timesheet` month view | teacher | NEW (`D-18`, `S-64`) | *"Where are the holes in my month?"* |
| `/timesheet` day view | teacher | NEW (`D-18`) | *"Record today as it happens."* |
| `/staff/today` | admin | CHANGING (`S-72`) | *"Who is free right now?"* |
| `/dashboard/staff` | admin | CHANGING (`D-21`) | *"Who is missing, is it covered, and where is the slack?"* |
| **Cover sheet** (from `/dashboard/staff` **and `/staff/leave`**) | admin | CHANGING (`D-26`, `D-27`, `D-29`) | *"Who takes 7-A at 11:20 — and what does that cost?"* |
| `/setup` → Assignments, by-teacher | admin | CHANGING (`D-28`, `S-77`) | *"Which classes does this teacher take?"* — **read-only today** |
| `/setup/settings` | admin | CHANGING (`D-19`) | *"What work do we track?"* |

## 7 · What we deliberately don't build

- **No link to pay. Settled** — `D-25`: payroll is present/absent on the day plus half-day leave,
  and nothing else. The timesheet reaches no salary figure and no appraisal.
- **No leaderboard, no completeness ranking, no per-teacher score.** (`S-67`, Claude's half of the
  fence, still a recommendation.)
- **No chasing the unfilled.** `D-23`: an unfilled period is free. No nag, no compliance %, no
  "you have not completed your timesheet" — and therefore no tile counting it (`S-76`).
- **Nothing in the daily capture flow.** `D-24`: the timesheet is its own section and never
  appears inside attendance / topic log / homework.
- **No clock-in / clock-out, no minutes.** The period is the unit. Staff attendance (SF-1) already
  answers *did they come in*; this answers *what the day was spent on*.
- **No second time model** for out-of-hours work in v1 (`S-73`).
- **No auto-assignment.** `D-29`: the system suggests, the admin assigns. Same fence the timetable
  module holds (SPRD2 §11: deterministic validators, no guaranteed solver).
- **Nothing new on the teacher's daily plate.** `D-22`: two things, and adding a third means
  removing one.

## 8 · Open questions

**Answered:** ~~`Q-30`~~ → `D-25` (never touches pay) · ~~`Q-31`~~ → `D-23` (unfilled = free).

**Still open, all small:** `Q-32` can the admin assign *non-cover* duty into a period *(cover
itself is settled by `D-26`)* · `Q-33` out-of-period work · `Q-34` back-fill horizon · `Q-35` do
hostel sessions count as load · `Q-36` who besides the admin may read a timesheet · `Q-37` does
covering show on the substitute's own timesheet *(verified: it does not)*.
Full text in [`../open-questions.md`](../open-questions.md).

## 9 · Data implications

Shapes only. Everything here is additive; nothing existing changes meaning.

**Strikingly little is needed — `D-23`, `D-24`, `D-26`, `D-27` and `D-28` all land on tables that
already exist.**

```
timesheet_entries                   (exists)
  + source        self | assigned   (S-65, only if Q-32 says yes for NON-cover duty;
                                     cover itself stays in period_substitutions)
  ~ updated_at    actually bumped   (S-71)

organizations / a small child table (D-19, S-69)
  work_type_config: [{key, label, active, order}]
  keys stable, labels mutable, retired not deleted.

~~timesheet_days~~   REJECTED — D-23
~~timesheet_patterns~~ dropped — S-75 pre-selects in the picker, writes nothing
```

**Read-side only, no new tables:**
`/staff/today` re-pointed at `WorkloadInsights` (`S-72`) · the cover picker joining
`timesheet_entries` (`S-74`) and the class's next planned topic (`D-29`, `S-79`) · cover unioned
into the substitute's own timesheet day (`Q-37`) · hostel sessions unioned into the load board
(`S-68`) · the slack profile derived from the day payload already assembled (`S-66`) · the
by-teacher assignment view gaining a save (`S-77` — `PATCH /academics/class-subjects/{id}` already
takes `teacher_member_id`).

**One behavioural fix that is not additive and must not be missed:** `busy_reason` must consider
**approved leave on the target date**, not only a `staff_absences` row — which does not exist for
a future date. Without it `D-27` lets an admin assign Friday's cover to someone on leave that
Friday (`S-82`).

## 10 · Rough build order

Reordered after `D-23`–`D-29`. The corrections come first because they are live defects in the
flow the founder just designed around.

**Corrections — no decision needed, all small**
1. **`S-72`** — one grid. `/staff/today` stops showing absent teachers as eight free periods.
2. **`S-74`** — the cover picker reads the timesheet.
3. **`Q-37`** — cover shows on the substitute's own week. Same union, other screen; ship with 1.
4. **`S-76`** — delete the "free periods unlogged" tile; label the chart's free band honestly.

**Substitution — the founder's flow, in dependency order**
5. **`S-77` / `D-28`** — make the by-teacher assignment view writable. *Setup feeds everything
   below; do it first.*
6. **`D-26` / `S-78`** — the two-panel cover screen: what is given up, what is gained.
7. **`D-29` / `S-79`** — syllabus-pending in the ranking (positive tier + behind-warning).
8. **`S-82`** 🔴 + **`D-27` / `S-80`** — leave approval → arrange cover, **with** the
   approved-leave clause in `busy_reason`. These two ship together or not at all.
9. **`S-81`** — approved leave puts the cover work on the action rail.

**The teacher's side**
10. **`D-18` / `S-64`** — month + day views on `/timesheet`.
11. **`S-75`** — the picker pre-selects her usual category; **`S-70`** — give her the number back.
12. **`D-19` / `S-69`** — categories configurable in Settings.

**Then**
13. **`D-21` / `S-66`** — the slack profile and the filterable detail tab.
14. **`S-68`** — hostel sessions on the load board (`Q-35`).
15. **`S-65`** — non-cover assigned duty, if `Q-32` says yes.
