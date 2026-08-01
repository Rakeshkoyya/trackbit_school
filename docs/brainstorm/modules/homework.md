# Module — homework

Set it, check it the next day, and know by name who keeps not doing it — without a teacher ever
touching forty names to record three facts.

**Sessions:** 4 (2026-07-31)
**Related:** [`attendance.md`](attendance.md) *(absent ≠ didn't do it)* ·
[`teacher-load.md`](teacher-load.md) *(who checks, and who covers)* ·
[`class-teacher.md`](class-teacher.md) · [`parent-access.md`](parent-access.md)

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Teacher** | end of the period, class packing up | phone, **seconds** | *"Tell them tonight's work and get out."* |
| **Teacher** | next morning, before the bell | phone, **seconds** | *"Who didn't do it?"* |
| **Teacher** | Monday, having not checked Friday's | phone, minutes | *"What have I still not gone through?"* |
| **Class teacher** | 4pm | phone | *"Is my class drowning — how much did they get today, from how many subjects?"* |
| **Admin** | weekly | desktop | *"Is homework being done — and is anyone actually checking it?"* |
| **Admin** | a parent has phoned | desktop, **under a minute** | *"Which homework did Kabir miss, and when?"* |
| **Parent** | evening | phone | *"What does my child have tonight, and did they do yesterday's?"* |

The 8:55am teacher is the design constraint. Everything else is a read.

## 2 · What they must be able to decide

- *(teacher)* **Who to speak to today** — by name, not a count.
- *(teacher)* **What she has not yet gone through**, so nothing quietly disappears.
- *(class teacher)* **Whether her class is being over-set** — six subjects, one evening.
- *(admin)* **Which teacher sets homework and never looks at it.**
- *(admin)* **Which child needs a conversation, and with which parent.**
- *(parent)* **What is due tonight.**

## 3 · Where it stands today *(verified in code, 2026-07-31)*

**The whole module described in the brief is built.** HW-1 shipped on 2026-07-29 (migration
`d8e9f0a1b2c3`, on production). What follows is what exists, then §4 is what is wrong with it.

### Capture — exception-shaped, like everything else

| Table | Meaning |
|---|---|
| `homework_assignments` | class-subject × date × text, optional `due_date`, optional `student_id` (NULL = whole class), `notified_at` |
| `homework_checks` | **the teacher went through it.** One row per assignment (UNIQUE). Its *absence* is `not_checked`, which is emphatically not "everyone did it". `done_count`/`total_count` are derived caches; `checked_by_member_id` names who looked. |
| `homework_results` | **only the students who did NOT do it** — `not_done` \| `partial`, plus a note. Roster minus these = done. |

`ClassroomService.add_homework` notifies guardians immediately (P3 — the teacher's payback) with
plain text only, never band data (P4). `check_homework` is a **full replace** of the exception
set, the same contract as `AttendanceService.mark`.

### The teacher's screens

- **Set:** My Day class card → *"Set homework"*; and the period card's Homework section
  (class-wide or per-student).
- **Check:** My Day, top block — *"Yesterday's homework — mark completion"*. One row per unchecked
  assignment, **"Everyone did it"** as a single tap, *"Some didn't…"* opens a roster where a tap
  cycles **did it → didn't → partly**. Exactly the founder's flow, already built to the P1v2
  budget.

### The admin's screen — `/dashboard/homework`

Four tiles → completion over the window → **by class** → **by subject** → **"Students who keep
missing it"** (named, with streak, subjects, the responsible teacher, and *Remind guardian* /
*Follow up* actions) → **"Is homework being checked?"** per teacher (set / checked / overdue
unchecked / rate) → perfect record + most improved.

`HomeworkService` computes all of it in **five queries** regardless of school size.

### The parent

`yesterday` (the last homework day and its verdict) and `pending`, through the curated allowlist.
*(verified — and this one holds)*: `not_checked` renders neutrally, worded as the teacher's
pending action, and its badge is suppressed in the pending list. HW-1's rule that a missing check
is never a child's miss survives into the parent UI.

### Against the brief

| Asked for | Status |
|---|---|
| Teacher sets homework for a class | ✅ two surfaces |
| Next day, mark who did / didn't | ✅ one tap + exception sheet |
| Admin: school / class / subject level | ✅ |
| Admin: drill to one student — which homework, when missed | 🔴 **built, wired, and unreachable** (`S-86`) |
| A screen to mark yesterday's homework | ✅ as a block on My Day — and the *real* gap is elsewhere (`S-84`) |

## 4 · What's wrong with it

### 4.1 🔴 Friday's homework cannot be checked on Monday

*(verified)* `ClassroomService.my_day` builds the pending list from **exactly one day**:

```python
yest = today - timedelta(days=1)
... .where(HomeworkAssignment.date == yest)
```

So:

- Homework set on **Friday** never appears on **Monday** — `yesterday` is Sunday. It is
  permanently invisible to the only surface that offers to check it.
- Miss a day for any reason — a trip, illness, a busy morning — and that homework is gone from the
  teacher's screen **forever**.
- **`due_date` is ignored entirely.** A project set today and due next Monday appears for checking
  *tomorrow*, and the actual due date passes with no prompt at all.

And the consequence lands on the admin's board as a judgement about a person: `unchecked_overdue`
counts homework the teacher was **never shown**. The single most likely reason a school's
checking rate looks bad is this bug, not the teachers.

### 4.2 🔴 A student who was absent is marked as not having done it

The check sheet lists the whole roster with no idea who was in the room when the homework was set.
Attendance knows — it is captured per period, on that date, in the same database. So a child off
sick on Tuesday is flagged `not_done` on Wednesday, lands on *"Students who keep missing it"*, and
their guardian gets a reminder for work they were never given.

This is the same family as *not-captured is never a zero* (`ux-principles` §5), pointed at a
child: **absent is not a refusal.**

### 4.3 🔴 The founder's drill-down is built and unreachable

`GET /homework/student/{id}` returns exactly *"which homework and when he missed"* — every item
with date, subject, text, status, and the note. `schoolApi.studentHomework` exists in the web
client. *(verified)* **Nothing calls it.** The student report card shows per-subject counts, not
the item list.

`D-31`'s detailed report is a link and a component away from existing.

### 4.4 A substitute cannot check homework — though the model expects them to

*(verified)* `HomeworkCheck.checked_by_member_id` was added with the comment *"a substitute may
check a colleague's homework"*. But `_can_capture` allows only **an admin or the class-subject's
assigned teacher** — it never consults `period_substitutions`, unlike `assert_can_take_class`,
which was extended for exactly this in DASH3.

So the teacher covering 7-A can take the register and log the topic, and cannot mark the homework
in front of her. Right after session 3 made cover a first-class flow, this is the loose end.

### 4.5 "Partial" is worth nothing here and half a topic next door

`HomeworkService` computes `completion = done / (done + not_done + partial)` — **a child who did
most of it scores identically to one who did nothing.** `insights/syllabus.py` counts a partially
covered topic as **0.5**.

Same word, two arithmetics, in one product. Third instance of the pattern the last two sessions
found (three definitions of "absent for a day", two of "syllabus covered", two of "who is free").

### 4.6 Nobody can see what a class was given in one evening

Six teachers each set thirty minutes of work, independently, and no screen anywhere adds them up.
The child has three hours; the school has six reasonable decisions. The class teacher — the one
person responsible for that child's day — has no view of it, and the admin cannot see that 8-B got
homework from five subjects on Tuesday.

Every parent in India complains about this and no school product shows it. The data is already
there.

### 4.7 Checking gives the teacher nothing back

Setting homework pays her immediately: parents notified, P3 satisfied. **Checking pays her
nothing** — and checking is the expensive half, one sheet per assignment. What she gets is a
statistic on the principal's dashboard. That is the shape of a feature that is used enthusiastically
for a month.

### 4.8 The parent is told homework was set, never that it was not done

`add_homework` notifies. A miss notifies nobody; the parent must open the portal. And *(session 2,
`D-08`)* the notify path is `notify_guardians`, the **WhatsApp stub** — one of the three callers
that now needs an in-app + web-push destination (`D-14`).

### 4.9 Smaller, verified

- A **per-student** homework still renders *"Everyone did it"* over a roster of one.
- The parent's **"still to do"** keeps a `not_done` item with no due date for the whole eight-day
  window, so work that is simply missed sits in the same list as work that is upcoming.

## 5 · Ideas and directions

### Decided — `D-30`–`D-39`
See [`../decisions.md`](../decisions.md). The teacher sets and checks · the admin sees school /
class / subject and drills to one student · **checking moves off My Day onto its own screen behind
a button** (`D-36`) · **late completion on a working-day clock, 3-day gap** (`D-33`) · **an absent
child's homework is carried, not missed, and the teacher decides how it resolves** (`D-34`) ·
**the parent sees it yellow and pending** (`D-35`) · **load analytics for admin and class teacher
only** (`D-37`) · **next-day deadline, configurable, both latenesses captured** (`D-38`) · **no
marks, no quota** (`D-39`).

**The shape this settles on is worth naming.** Homework now has the same three-layer honesty the
rest of the product uses:

| Layer | Fact | Never means |
|---|---|---|
| `homework_checks` exists | the teacher went through it | *(absence)* everyone did it |
| `homework_results` row | this child didn't, or did it partly / late | *(absence)* nothing — done is derived |
| absent-carried | this child wasn't there | a miss, a zero, or a red |

### Proposed — `S-nn`

**`S-83` — 🔴 the pending list is "everything unchecked past its deadline", not "yesterday".**
One change, and it is the most important line in the module:

```
pending = assignments where no check exists
          and coalesce(due_date, date) < today
          ordered oldest first
```

Friday's homework survives the weekend. A due date finally does something. A day missed is a day
recovered instead of a record lost. And `unchecked_overdue` on the admin board starts measuring
teachers rather than a query bug — the two now share **one definition of overdue**, which is the
`ux-principles` §9 rule the last three sessions kept finding broken.

**`S-84` — `D-32`'s screen is the backlog; My Day keeps "yesterday" at one tap.**
**SUPERSEDED by `D-36`.** The founder took the other half: **My Day loses the block entirely** and
a button opens the Homework screen. Claude's argument was the P1v2 one-tap; the founder's answer
is that checking is not a between-classes act at all — *"she collects the notebooks and after the
class completes she checks and marks as done"*. That is a desk activity with a stack of books, so
a dedicated screen is the right surface and the one-tap was solving a problem that does not exist.
Kept, because the backlog *ordering* it argued for survives inside `D-36`'s screen.

**`S-85` — 🔴 the check sheet must know who was absent.**
Attendance already recorded it, on that date, in the same database. Three small consequences:

1. The row reads *"Kabir — absent Tuesday"* and is **not preselected as a miss**.
2. `homework_results` for an absent student is excluded from the completion figure, the same way
   `not_checked` already is.
3. *"Students who keep missing it"* stops naming children who were off sick, which is currently
   sending their guardians a reminder about work they never received.

Shape question in `Q-38`: auto-exclude, or show it and let the teacher decide? *Claude recommends
show-and-don't-preselect* — she may know he was given it by a friend, and a hard exclusion cannot
be overridden.

**`S-86` — make the student drill-down reachable.** *(the cheapest thing in this session)*
The endpoint, the schema and the client method all exist. Add the block to `/students/[id]` —
the item list with date, subject, text and verdict — and `D-31` is delivered. It also gives the
admin's *"Students who keep missing it"* row somewhere useful to land, and gives the class teacher
the evidence for a parent conversation.

**`S-87` — homework load per class per day.** *(the idea worth keeping from this session)*
One computed row: for each class and date, how many subjects set homework. Then:

- **the class teacher** sees her class's evening: *"Tuesday — 5 subjects set homework"*;
- **the admin** sees the outliers: *"8-B has had 5+ subjects on three days this week"*;
- nobody is blamed — each teacher made a reasonable decision, and the point is that no one could
  see the total.

It needs no new capture at all: `homework_assignments` grouped by class × date. It answers the
single most common parent complaint about Indian schools, and no product shows it.

⚠️ Deliberately **not** a cap or a rota. A limit turns into "whose turn is it to set homework",
which is worse than the problem. Show the number; let the staff room handle it.

**`S-88` — decide what "partial" is worth, once.**
`0` here, `0.5` in syllabus. *Claude recommends `0.5` in both* — it is what "partly" means, and a
child who did most of it should not read the same as one who did nothing. Whichever way it goes,
the screen must say it: *"completion counts a partial as half"* (`ux-principles` §4). `Q-40`.

**`S-89` — checking should hand her the intervention, not file a statistic.**
As she taps a name on the sheet, the row says *"Kabir — 4th miss in 5"*. She is holding the
notebook and standing in front of the child; that is the cheapest intervention moment in the
entire product, and today the information exists only on the principal's dashboard.

This is P3 for the expensive half of the loop, and it costs one number already computed by
`HomeworkService._streak`.

**`S-90` — tell the parent about a *pattern*, never a single miss.**
A message every time a child forgets one worksheet makes the school a nag and trains parents to
mute it. A message at **two consecutive homework days missed** is the same threshold the red list
already uses, and it mirrors `D-02`'s absence rule — a school that speaks up only when it matters
gets listened to.

Delivery is `D-08`/`D-14`: in-app + web push, not WhatsApp. And `add_homework`'s existing notify
call is one of the three stubs that need re-pointing. `Q-39`.

**`S-91` — do not grade homework.**
There will be a pull toward marks — the teacher is holding the notebook and can see the work.
Resist it: it turns a 30-second sweep into a grading session and breaks the one-minute budget for
the one capture teachers actually do daily. **The place for "did it, but all wrong" already
exists** — `lesson_observations`, exception-only, per student, already feeding the growth report.
Point the teacher there instead of widening this table.

**`S-92` — do not set a homework quota.**
There is no "homework should have been set" expectation in the system today, and there should not
be one. A target on *setting* produces homework set to satisfy a dashboard — the same argument the
syllabus module already made about coverage as a performance target, and the reason lesson logs
are still honest.

**`S-93` — a substitute should be able to check the homework in front of her.**
`_can_capture` should consult `period_substitutions` the way `assert_can_take_class` already does.
The column that records who checked was added for this case.

**`S-94` — separate "still to do" from "missed" on the parent's screen.**
Work whose deadline has passed and was not done is not *pending*; it sits in the parent's
"still to do" list for eight days looking like something that can still be handed in. Two lines,
clearly worded, and the *"missed"* one carries no red — it is a fact, and the child may well have
finished it since.

---

*The proposals below came out of the founder's answers: `D-33`–`D-39`.*

**`S-95` — 🔴 two latenesses, and only one of them is about the child.**
`D-33` forces "late completion" past a 3-working-day gap. But a long gap has two very different
causes:

| Cause | Whose fact | Already computable |
|---|---|---|
| the child handed it in late | the child's | needs the new verdict |
| the teacher collected on time, recorded on Friday | the **record's** | `checked_at` vs deadline — exists today |

Writing the second as the first puts something untrue about a student into their permanent record
— the exact mistake `not_checked` was invented to prevent, and this module's best existing idea.

Recommendation: past the threshold the default verdict reads **"recorded late"**, a fact about the
record; the teacher can still say a specific child genuinely handed it in late; and the teacher's
own lateness keeps flowing to the admin separately, which is what `D-38` asks for anyway. `Q-44`.

**`S-96` — the working-day clock already exists three times. Use one.**
`D-33` needs "3 working days, Sundays and holidays dropped". *(verified)* the codebase already
computes exactly this in `leave.py::_working_days`, in `calendar.py::expand_blocked_dates`, and in
the planner's effective-teaching-days engine. A fourth would be the fifth instance of this
codebase's signature bug.

Also suggest the threshold is an **org setting, default 3** — a boarding school and a day school
will not agree on it, and it sits naturally beside the leave policy in Settings.

**`S-97` — where a returning child's pending homework lives.**
`D-34` says *"the next day he comes to school we check that pending or not"*. That needs a
surface, and it should not be a new screen: put a badge on his row **on the next check sheet for
that class** — *"Kabir · 2 pending from while away"* — tapping to resolve each. She is already
opening that sheet, holding those notebooks. Nothing new to remember.

**`S-98` — "waive" is not optional; without it the yellow never clears.**
`D-34` explicitly allows *"teacher might give new homework for him"* instead of the backlog. That
is a real outcome and it needs somewhere to go, or pending items accumulate for every absence in
the year and `D-35`'s parent-facing yellow becomes permanent.

Three resolutions on a carried item: **done** · **done late** · **not required**. The third leaves
the completion denominator entirely, exactly as `not_checked` does.

**`S-99` — how a late completion counts, and how it reads.**
Recommendation: **done, reported separately** — *"82% done · 6 of them late"*. Folding late into
done hides a class where everything arrives four days late; counting it as a miss punishes a child
who did the work. Same discipline the module already applies to `not_checked`. `Q-43`.

**`S-100` — the button must carry a count. This is what decides whether `D-36` works.**
*"Homework"* is a button nobody presses. *"Homework · 4 to check"* is a to-do. Moving a daily
habit behind an unlabelled button is how it becomes a monthly one — and the count is already
computed by the same query that fills the screen.

**`S-101` — the Homework screen's three levels, and the one component that serves two roles.**
`D-36` asks for classes × homework by day, then per-student and per-day views. Concretely:

```
Homework · 4 to check
  ┌ Tue 29  7-A Maths   Ex 4.2, sums 1–10        4 to check   [open]
  │ Tue 29  7-A Science Diagram of the eye       ✓ checked
  └ Fri 26  6-B Maths   Revision sheet           ⚠ 3 days — late only
      ↓ open one          → the check sheet (roster, exceptions, absentee badges)
      ↓ by student        → this child across every homework
      ↓ by day            → everything given on that day
```

The **by-student** view is the same data as `GET /homework/student/{id}` — *(verified)* built,
wired into the web client, and called by nothing (`S-86`). So the teacher's per-student view and
the admin's `D-31` drill-down are **one component**, built once.

**`S-102` — the carried state must be invisible to the streak and the red list.**
*(verified)* `HomeworkService._streak` skips `not_checked` days deliberately — *"the teacher's gap
is not the student's"*. `D-34`'s carried state needs the identical treatment: skipped, not counted
as a clean day and not counted as a miss. Otherwise a child off sick for a week lands at the top
of *"Students who keep missing it"*, and their guardian is reminded — which is defect §4.2 coming
back through a different door.

### Rejected

- **`S-84`** — keep the one-tap block on My Day and add a backlog screen. **Superseded by
  `D-36`:** the block goes entirely, because checking is a desk activity, not a between-classes
  tap. The backlog ordering survives inside the new screen.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| My Day — set homework | teacher | EXISTS | *"Tell them tonight's work."* |
| ~~My Day — yesterday's check block~~ | teacher | **REMOVED** (`D-36`) | — replaced by the button |
| **Homework** — `/homework`, behind a counted button | teacher | NEW (`D-32`, `D-36`, `S-100`, `S-101`) | *"What have I got to check?"* |
| **↳ one homework** — the check sheet | teacher | CHANGING (`S-85`, `S-89`, `S-97`, `S-98`) | *"Who didn't do it?"* |
| **↳ by student** | teacher | NEW — same component as the admin's drill-down (`S-101`) | *"What has Kabir missed?"* |
| **↳ by day** | teacher | NEW (`D-36`) | *"What did I give on Tuesday?"* |
| Period card — Homework section | teacher | EXISTS | *"Set it for this class / this child."* |
| Class teacher board — today's load | class teacher | NEW (`D-37`, `S-87`) | *"How much did my class get tonight?"* |
| `/dashboard/homework` | admin | CHANGING (`D-37`, `S-87`, `S-88`, `S-99`) | *"Is it being done — and is anyone checking?"* |
| `/students/[id]` — homework history | admin / teacher | **DEAD → NEW** (`D-31`, `S-86`) | *"Which homework did Kabir miss, and when?"* |
| `/parent` — last homework + still to do | parent | CHANGING (`D-35`, `S-90`, `S-94`) | *"What's due tonight, and did they do yesterday's?"* |

## 7 · What we deliberately don't build

- **No marks, no grades, no rubric** — `D-39`, accepting `S-91`. Done / didn't / partly / late.
  Quality goes in the observation log, which already exists and already reaches the growth report.
- **No homework quota or "expected" count** — `D-39`, accepting `S-92`. A target on setting
  produces homework that exists for a dashboard.
- **No cap on the daily load** (`D-37`) — show the number to the admin and the class teacher, and
  legislate nothing. A subject teacher sees none of it.
- **No expiry.** `D-33`: homework can be marked at any point, forever. What changes past the gap
  is the *verdict available*, never the ability to record.
- **No penalty for an absence.** `D-34`: dropped days, carried homework, and the teacher decides
  whether the backlog is even required.
- **No submission, upload, or file handling.** The notebook is the artefact; this module records
  whether it came back.
- **No per-student marking as the default path.** One tap for the norm, flags for the exceptions
  (P1v2), forever.
- **No parent writes** — a parent cannot mark homework done, dispute a verdict, or message about
  it. PC-1 holds.
- **No nagging** (`S-90`). Patterns, not incidents.

## 8 · Open questions

**Answered:** ~~`Q-38`~~ → `D-34` (carried, not excluded) · ~~`Q-41`~~ → `D-38` (next day,
configurable) · ~~`Q-42`~~ → `D-37` (admin + class teacher only).

**Still open:** `Q-39` does a parent hear about a miss, and at what threshold · `Q-40` is
"partial" worth half or nothing *(it is 0 here and 0.5 in syllabus today)* · `Q-43` does a late
completion count toward completion *(recommend: yes, reported separately)* · `Q-44` 🔴 past the
gap, is "late" a fact about the child or the record.
Full text in [`../open-questions.md`](../open-questions.md).

## 9 · Data implications

Still small. `D-33`–`D-39` land almost entirely on the existing `homework_results` row, because
its `status` column is already the exception vocabulary — widening it keeps done-on-time as *no
row*, which is the property the whole module rests on.

```
homework_results        (exists)
  ~ status   not_done | partial | late | carried | waived
      late     — did it, after the deadline (D-33)
      carried  — was absent when it was set; pending, not a miss (D-34)
      waived   — teacher decided the backlog isn't required (S-98)
  → "done on time" remains the absence of a row. Nothing else changes.

homework_checks         (exists — no change)
  checked_at vs coalesce(due_date, date) already carries the TEACHER's lateness (S-95).
  Do not overwrite it with the student's.

homework_assignments    (exists — no change; due_date already there, D-38)

organizations
  + homework_late_after_days      int, default 3    (D-33, S-96 — working days)
  + homework_miss_notify_streak   int, default 2    (S-90, only if Q-39 says yes)
```

**Explicitly not a column:** *"was absent when it was set"*. Attendance already knows, on that
date; a second copy would drift. `S-85` is a join.

Read-side and guard-side: the queue keyed on `coalesce(due_date, date)` with the working-day gap
(`D-33`, reusing an existing working-day function — `S-96`) · the check sheet joining attendance
(`S-85`) · carried items skipped by `_streak` and the red list (`S-102`) · `_can_capture`
consulting `period_substitutions` (`S-93`) · one grouped query for class × date load (`D-37`) ·
one definition of *partial* (`S-88`) · one component serving both per-student views (`S-101`).

## 10 · Rough build order

Reordered after `D-33`–`D-39`. `D-36` replaces the My Day block, so the screen is no longer a
later addition — it is the surface everything else hangs on.

**1 · The verdict model — everything depends on it**
1. **`D-33` + `S-96`** — the working-day gap and the `late` verdict, reusing an existing
   working-day function. This is `S-83`'s fix by design: nothing expires off her screen.
2. **`D-34` + `S-98` + `S-102`** — carried and waived; skipped by the streak and the red list.
   Fixes defect §4.2 at the root rather than papering it.
3. **`Q-44` / `S-95`** — decide *"recorded late"* vs *"did it late"* **before** any of this is
   built. It is one word on a screen and a permanent fact in a child's record.

**2 · The screen `D-36` asks for**
4. **`S-100`** — the counted button. Without it the rest is optional.
5. **`D-36` / `S-101`** — the Homework screen: by class × day → the check sheet → by student → by
   day. **The by-student view is `S-86`'s unreachable endpoint**, so this delivers `D-31` too.
6. **`S-85` + `S-97`** — absentee badges on the sheet, and the returning child's pending items on
   his row.
7. **`S-89`** — the streak on the row, at the moment she is holding the notebook.

**3 · Corrections that don't wait for any of the above**
8. **`S-93`** — a substitute can check homework.

**4 · Then**
9. **`D-37` / `S-87`** — daily load per class, for the admin and the class teacher only.
10. **`Q-43` / `S-99`** — how a late completion reads on the admin board · **`S-88`** (`Q-40`) one
    definition of partial · **`S-94`** missed vs still-to-do · **`D-35`** the parent's yellow ·
    **`S-90`** (`Q-39`) pattern notification over `D-08`/`D-14`.
