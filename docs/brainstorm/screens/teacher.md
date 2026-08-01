# Screens — Teacher

Everything a teacher sees, in nav order, plus the **class teacher** area which appears only for
a teacher who owns a class (`D-03`).

**Nav (desktop):** My Day · Lucy · Sessions · Plan · Students · My time · Tasks
**Mobile bottom bar (4):** My Day · Tasks · Students · Lucy

**Who the teacher is — two different people at two different times:**

| | The 9:02 teacher | The 4pm teacher |
|---|---|---|
| Where | standing, class in front of her | sitting, staffroom or home |
| Device | phone, one hand, 360px | phone or laptop |
| Budget | **seconds** | minutes |
| Wants | to record what just happened and get back to teaching | to catch up, see her class, apply for leave |
| Screens | My Day, period card, attendance | class teacher board, timesheet, students |

Almost every failure in a teacher product comes from designing the 9:02 screens for the 4pm
teacher. **Hard rule (P1v2):** routine period card ≤ 5 taps / 30s. Anything needing per-student
entry for a whole class is mis-designed.

---

# My Day

## `My Day` — `/my-day`
**Status:** CHANGING · **Refs:** `D-01` `D-22` `Q-02` `S-39` `S-63`

**Arrives asking:** *"What's next, and what haven't I recorded?"*
**Leaves having:** opened the period she is about to teach, or cleared yesterday's homework.

**Context:** all day, phone, between classes. Opened more than any other screen in the product.

### What's on it *(verified)*
Yesterday's homework to check (one-tap "everyone did it") → today's periods as tappable rows →
classes not on today's timetable → this evening's hostel sessions.

### Session 1 change
In `first_period` / `twice_daily` mode, only the marking period(s) ask for attendance. **Open
question `Q-02`:** does the mode change only attendance, or the whole period card? *Claude
recommends attendance only — the syllabus forecast is built on per-period lesson logs, and
collapsing them breaks the planner's actual-vs-baseline arithmetic (P2).*

### Session 3 — deliberately unchanged (`D-24`)

`D-22` says a teacher's job is exactly two things: **maintain the timesheet, and log the class.**
Claude proposed folding the free periods into this screen so the day is one list (`S-63`).

**REJECTED — `D-24`: the timesheet stays its own section.** The daily capture flow is the
sharpest, most time-pressured surface in the product, and nothing else goes in it. So My Day keeps
exactly the periods she teaches, and the timesheet lives under **My time**.

The adoption problem `S-63` was solving is still real — a separate route is a route people forget
— and now falls to `S-75` (the picker pre-selects her usual category, so a period costs one tap)
and `S-70` (the week's totals belong to *her*, not the principal).

### Session 4 — the homework block is **removed** (`D-36`)

*(verified)* Today the top block is *"Yesterday's homework — mark completion"*, with a one-tap
**"Everyone did it"**. **It goes.** Yesterday's classes are not shown on My Day; in its place a
single button:

```
  [ 📓 Homework · 4 to check ]        → /homework
```

**The count is not decoration** (`S-100`) — it is the entire reason the button gets pressed.
*"Homework"* alone is how a daily habit becomes a monthly one.

*Why removing the one-tap is right:* checking is not a between-classes act. The founder's own
description — *"she collects the notebooks and after the class completes she checks and marks as
done in the app"* — is a desk activity with a stack of books. Optimising it for a thumb between
periods was solving a problem that does not exist. Recorded so nobody moves it back.

### Session 5 — a **tasks section** is added, below the periods (`D-41` `D-43`)

The screen gains a third block, under a rule: **the work that isn't a class.**

**It is a window, not her task list** (`D-43`). Exactly two kinds of row:

- **assigned from an action rail in the last 3 days**, and
- **anything due today**, from any board.

```
  ────────────────────────────────────────
   Tasks · 3
```

Rows she can **tick in place** — no navigation. No *Upcoming*, no overdue backlog, no undated
tasks she wrote for herself: all of that is `/tasks`, which is the module's home page and already
renders it. **My Day is a prompt, not an inbox** — the same call `D-36` made about homework.

> ⚠️ **A task can leave this section without being done.** On day four a rail follow-up drops off
> whether or not it was closed. That is the point — and it is a silent memory hole unless the
> section admits it, so it ends with one line: **`4 older tasks →`**. Same discipline as `D-44`'s
> date filter on the board.

*Build-time detail: count the 3 days in **working days**, or a Friday follow-up is invisible on
Monday — the exact bug session 4 found in the homework queue.*

**Why this doesn't break `D-24` / `D-36`.** Two sessions running we took blocks *off* this screen.
The rule that makes all three consistent:

> **If the work happens on another screen, put a counted button on My Day** *(homework — a
> forty-name check sheet)*.
> **If the work *is* the row, put the row on My Day** *(a task — one checkbox)*.

Sending a teacher to `/tasks` to tick a box she could have ticked here adds a navigation and
returns no information. And `D-24`'s real clause holds untouched: **nothing goes above the
periods.** This sits below them, out of the 9:02 thumb path, where the 4pm teacher finds it.

*(If tasks ever grow a body of work — subtasks, attachments, a required note — the test flips and
they become a counted button too. Written down so the flip is a decision, not a drift.)*

**Claude's four additions — all accepted, two of them narrowed by `D-43`:**

- **`S-108` — overdue is not "today"** → **a state, not a group.** There is no backlog on this
  screen to group any more, but a row *inside* the window that is late still reads *"due
  yesterday"*, in red. Late is a fact about the row; it is not a place.
- **`S-109` — cap at 3–5, then *"+4 more →"*** → kept as a backstop. The window normally does the
  work; the cap stops one bad day pushing her evening sessions off the screen. It shares its line
  with `D-43`'s **`n older tasks →`**.
- **`S-110` — the list is *hers*, not *a board's*** → narrowed to **rule-scoped, not
  board-scoped**: "due today" is honoured whatever board it came from. The surviving point is that
  **board tabs have no place on My Day** — she has one head. `HomeService.my_tasks`
  (`services/home.py:117`) is still the computation; `D-43` is a filter over it.
- **`S-106` — badge the rows the admin asked for** → accepted. *"Priya asked · this morning"*. A
  task I wrote for myself and one the principal handed me are not the same object socially, and she
  triages by that before she triages by date. No new data — `task_events` records `assigned` with
  the actor.

### Suggestion `S-39` — still standing
The period row should say **what's missing**, not what's done. A row that reads *"attendance ✓
topic ✓"* is a receipt; a row that reads *"topic not logged"* is a to-do. The screen's job at 4pm
is to show her the gaps.

One addition under `D-27`: a period she has been **assigned to cover** appears here like any other
period, marked as cover. That already works — `ClassroomService.my_day` unions today's
substitutions and `assert_can_take_class` lets her open the card. It will need to hold for a
**future** date once cover can be arranged in advance.

### Sketch — the whole screen after sessions 4 and 5

```
┌──────────────────────────────────────────────┐
│  My Day                     Thursday, 31 Jul │
│  4 periods · 2 not recorded                  │   ← sentence, not a number (§2)
│                                              │
│  [ 📓 Homework · 4 to check ]          →     │   ← D-36. The count is the reason
│                                              │      it gets pressed (S-100)
│  TODAY'S PERIODS                             │
│  P1  6-B · Maths            28/30 · topic ✓  │
│  P2  7-A · Maths            topic not logged │   ← S-39: say what's missing
│  P4  6-B · Maths       ⟳ cover for Anil      │   ← D-27
│  P6  8-C · Science          not marked       │
│                                              │
│  ──────────────────────────────────────────  │   ← the rule (D-41)
│                                              │
│  TASKS · 3                                   │
│  ⚠  Kabir Shah — absent 4 days          [ ]  │   ← D-46 names the person,
│     Priya asked · due yesterday               │      S-106 names who asked
│  ○  Collect lab key from office         [ ]  │
│     due today                                 │
│  ○  Kavya Nair — 3rd homework miss      [ ]  │   ← assigned this morning
│     Priya asked · due tomorrow                 │
│  4 older tasks →                             │   ← D-43: the window admits itself
│                                              │
│  THIS EVENING                                │
│  Study block · 7:00–8:30 · 24 students   →   │
└──────────────────────────────────────────────┘
```

### States — the tasks section

| State | What she sees |
|---|---|
| Empty (new school) | The section and the rule **do not render at all**. An empty "Tasks · 0" on the busiest screen in the product is a permanent reminder that a feature exists, which is not the same as value. |
| Nothing in the window, 6 open on `/tasks` | Just the footer: **`6 older tasks →`**. The window is never silent about what it hid (`D-43`). |
| Everything ticked today | The rows stay, struck through, until tomorrow — `my_tasks` already returns today's completions for exactly this (`home.py:128-135`). Seeing what you cleared is the point. |
| A rail follow-up from last week, still open | **Not here.** It is on `/tasks`, and it is `D-45`'s Stale group on the admin's board that makes sure somebody deals with it. |

### Deliberately not here

Her overdue backlog and her future-dated work — both are `/tasks`' job (`D-43`) · board names as
tabs or filters — hers is one list (`S-110`) · task creation from this screen; the `+` lives on
`/tasks` · anyone else's tasks, ever · a completion percentage for her own work (`D-25`'s fence:
the moment a rate ranks people, the rate is what gets managed).

### Session 7 — a **What's on today** strip (`D-51`, `S-132`)

One line at the very top of My Day. Not a section, not a card with a header — a strip.

```
🎂  Aarav Sharma (6-B) — birthday today · 🪔 Guru Purnima
```

**This is the only thing on this screen that asks her for nothing.** Every other block on My Day
wants attendance, a topic, a homework verdict. This one hands her a five-second moment with a
child — *"class, it's Aarav's birthday"* — and that is precisely its value (P3, `S-132`). So:

- **it is never a to-do row**, never has a tick, never turns amber for being unread;
- **it shows only her classes' birthdays** — she teaches 6-B, so she sees 6-B. A school-wide list
  of forty names is the admin's screen, not hers;
- **day and month, never an age** (`S-133`) — this line gets read out to a room;
- **it does not render at all** when there is nothing on. An empty *"Nothing special today"* at
  the top of the most-opened screen in the product is the `D-43` mistake again.

**Class teacher gets the fuller version** on `My Class` — her own class's birthdays for the month,
because she is the one who will be asked to organise something.

### States

| State | What she sees |
|---|---|
| Empty (no DOB in the roster) | Nothing. The strip is absent — she is not the person who can fix that, and telling her about missing data she can't fill is noise. |
| Birthday, child is absent | Still shown, marked *(absent today)* — so she doesn't ask the class to sing for an empty chair. `S-128`'s logic, applied to the day rather than the calendar. |
| Birthday falls on Sunday | Shown on the Friday, labelled *"birthday on Sunday 17th"* (`S-128`). |
| Observance only, no birthdays | One line, just the observance. |

---

## `Period card` — `/my-day/period/[classId]/[no]`
**Status:** EXISTS, minor changes · **Refs:** `Q-02` `D-59` `S-145` `S-146` `S-147`

**Arrives asking:** *"Let me record this period."*
**Leaves having:** marked attendance, logged the topic, and saved the session.

Attendance row → topics (picked from the syllabus, grouped by chapter) → homework → today's
checks → test capture → the optional deep log → *Save session*.

The order is the thumb-flow from SPRD2 §5.4 and is not up for redesign. Only attendance's
availability changes with the mode.

### Session 7 — *"not held, because"* (`D-59`)

`D-59` says the plan does **not** rearrange itself around an approved holiday. Instead the record
says why the period didn't happen. *(verified)* `not_held_reason` already exists
(`services/classroom.py:470`); what changes is that it can **point at the approved event** rather
than being free text (`S-147`) — so *"what did Diwali cost us in periods?"* and *"which classes
lost the most to functions this term?"* become answerable, and the timesheet's work-type bucket
lines up with the same event.

**Two scopes, and they must not be merged (`S-146`):**

| | Who decides | Reach | Who records it |
|---|---|---|---|
| **Lock** | admin, in advance | school-wide or period-wide, every class | nobody — it is already in the calendar |
| **Block** | teacher, on the day | **this class, this period** — 8-A went to the rehearsal, 8-B kept teaching | the teacher |

Merging them double-counts: a locked day is already out of the capacity calculation, and a teacher
also marking it removes it twice.

> 🔴 **`S-145` — if the admin locked it, the teacher is never asked.** A locked period must not
> appear on My Day as pending, must not count in any denominator, must not reach the 16:00
> unmarked-teacher reminder (`jobs.run_teacher_reminder`), and must not trip the daily report's
> attendance-without-log rule. Showing a teacher eight red *"not logged"* rows on a holiday the
> school itself declared is the fastest way to make her stop trusting the whole surface — `ux §5`,
> *not captured is never a failure*.
>
> And per `Q-65`, "vanish" means **vanish from what is still expected**, never *erase what was
> already recorded*. A school that closed at 11am genuinely taught period 1.

---

## `Homework` — `/homework` · **NEW**
**Status:** NEW · **Refs:** `D-32` `D-33` `D-34` `D-36` `D-38` `D-39` `S-95`–`S-102` `Q-43` `Q-44`

**Arrives asking:** *"What have I got to check?"*
**Leaves having:** gone through the stack of notebooks on her desk and recorded it.

**Context:** she has just finished a class and collected the books; she is sitting down with them.
Minutes, not seconds — this is the **4pm teacher**. Phone or laptop.

### Level 1 — what she has given, and what is waiting

Her classes and the homework given, **which day and what it was** (`D-36`), waiting items first,
oldest first.

```
Homework · 4 to check

  Fri 26   6-B Maths      Revision sheet, Ch 7          ⚠ 3 school days — late only    [open]
  Tue 29   7-A Maths      Ex 4.2, sums 1–10             4 to check                     [open]
  Tue 29   7-A Science    Diagram of the eye            ✓ checked  ·  2 didn't
  Wed 30   6-B Maths      Ex 5.1                        due tomorrow

              [ by student ]   [ by day ]
```

**Nothing ever expires off this list** (`D-33`). Past the working-day gap the row simply says so
and the verdict narrows — Sundays and holidays dropped (`S-96`). This is what closes the
Friday-on-Monday hole by design instead of by patch.

### Level 2 — one homework: the check sheet

Roster, capture-by-exception — tap only the ones who didn't. Absentees carry a badge and are
**not** pre-flagged (`S-85`, `D-34`), and a child returning from absence carries his pending items
on his own row (`S-97`):

```
Ex 4.2, sums 1–10 · 7-A Maths · set Tue 29, due Wed 30

  [ Everyone did it ]                                        checked by you, 4:15pm

   1. Aarav Shah                                              did it
   2. Diya Nair            didn't  ·  4th miss in 5      ←  S-89
   3. Kabir Shah           absent Tue · 2 pending        ←  S-97 → done / done late / not required
   4. Ishaan Rao           partly
```

Past the gap the verdict reads **"recorded late"**, not *"did it late"* — a fact about the record,
not a permanent claim about a child (`S-95`, `Q-44`). She can still say a specific student
genuinely handed it in late.

### Level 3 — by student, and by day
- **By student** — this child across every homework: date, subject, what it was, verdict. This is
  *(verified)* the endpoint that already exists and nothing calls (`S-86`), so **the teacher's
  view and the admin's `D-31` drill-down are one component**.
- **By day** — everything she gave on a date.

### Actions — two, at every level
- **Everyone did it** → one tap, row clears.
- **Some didn't…** → the sheet. Flags, and on a carried item: done · done late · **not required**
  (`S-98` — without the third, the parent's yellow never clears).

### States
| State | What she sees |
|---|---|
| Empty (new school) | *"Homework you set appears here on the day it's due."* |
| Nothing to check | *"All caught up."* A clear stack should read as an achievement, not a blank screen. |
| Never set any | *"You haven't set homework in this window."* A statement, **not** a prompt — there is no quota (`D-39`). |
| Long overdue | *"3 school days — can be recorded as late completion."* Still fully recordable; nothing is ever locked. |

### Deliberately not here
Marks or grades (`D-39`) · a completion score for her · anyone else's classes · **any load
analytics** — those are for the admin and the class teacher only (`D-37`).

## `Roll call` — `/my-day/period/[classId]/[no]/attendance`
**Status:** CHANGING · **Refs:** `D-02` `S-12`

**Arrives asking:** *"Who's here?"* · **Leaves having:** the class marked, in seconds.

**Context:** the sharpest moment in the product. Standing, one hand, forty children waiting.

### The problem *(verified)*
Two roll-call screens exist with **opposite defaults**: this one starts every box **unchecked**
(untick = absent, so you tick who answers, with a "Tick everyone" shortcut), while
`/sessions/[id]/attendance` starts **everyone present** and you tap the exceptions. Same teacher,
same act, two habits — and SPRD2 §5.4 specifies *"All present ✓ one tap"*, which neither does.

### Proposed (`S-12`)
**One component, one default.** Everyone present, tap the exceptions — the P1v2 budget and the
spec. A **"call the roll"** toggle preserves the name-by-name flow for teachers who prefer it.
Frontend unification only; no migration.

### Session 1 addition
An **optional** reason at capture time (`D-02`). Optional is doing all the work in that sentence
— the moment entering a reason becomes a step in this flow, the design has failed.

---

# Class teacher area — NEW

Appears only for a teacher who owns a class. Route and placement pending `Q-09` (own area, or
folded into My Day — *Claude recommends its own, so My Day stays the same product for every
teacher*).

## `My Class` — route TBD
**Status:** NEW · **Refs:** `D-03` `S-26` `S-27` `S-28` `S-29` `S-30`

**Arrives asking:** *"Is my class alright, and who do I need to chase?"*
**Leaves having:** made a call, or recorded why someone is away.

**Context:** 4pm teacher. Sitting down, has a few minutes, feels responsible for these
particular children.

### What's on it, in order
1. **Needs attention** — 🔴 red (3+ days, no reason) then 🟡 yellow (reason on file), each with
   the student, how long, and what's already been tried
2. **Drifting** — the 60–85% band, trending down
3. **This month** — the attendance grid (`S-26`), students × school days
4. **My class's syllabus** — coverage across **all** subjects, not just hers (`S-28`, `D-10`).
   **`D-15`: she sees all subjects and all teachers' pace — but only for her own class**, never
   school-wide. Names the subject teacher beside each row, with the same honesty guard as the
   admin board: numbers beside the name, framed as *needs support*, never a rank. **No pace
   figure reaches a parent from here** (`D-11`).
5. **My follow-ups** — what the admin assigned her (`S-29`)
6. **Tonight's homework load** (`D-37`, `S-87`) — *"5 subjects set homework today"*, with the
   subjects named. Six teachers each made a reasonable decision and **no screen in any school
   product adds them up**; she is the one person responsible for that child's evening. Needs no
   new capture — `homework_assignments` grouped by class × date. Informational, **never a cap**:
   a limit becomes "whose turn is it to set homework", which is worse than the problem.
   **`D-37`: this block is for her and the admin only** — a subject teacher never sees load
   analytics, here or anywhere.

Order is deliberate: people who need something today, then people who will next week, then the
record, then the class's academic position. **Nothing above the fold is a chart.**

### Why the grid is the centrepiece (`S-26`)
It is the one grid of cells in the product that is genuinely a decision surface, because a row's
**shape** reads faster than any number:

```
              M T W T F  M T W T F  M T W T F
Aarav  ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✓ ✓    100%
Diya   ·····  ✓ ✗ ✓ ✓ ✓  ✓ ✗ ✓ ✓ ✓  ✓ ✗ ✓ ✓ ✓     80%  ← every Tuesday
Kabir  ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✗ ✗ ✗  ✗ ✗ ✓ ✓ ✓     67%  ← a block, then back
Ishaan ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✗ ✓  ✗ ✓ ✗ ✗ ·     73%  ← fading
```

Three different problems, three different conversations, one glance — and none of them
expressible as "attendance %". Cells carry the `D-02` colour.

### Actions — exactly two (`S-27`)
- **Record an informed absence** with a reason → red becomes yellow
- **Log a parent call** with its outcome → the row stops re-asking (`S-21`)

Everything else on the screen links to where that work already lives.

### Note
She is staff, so **bands are permitted here** — P4 fences bands from parents, not from teachers
(`S-30`). But that should be a deliberate call, not an accident of what got put on the page.

---

# My time

Three altitudes of the same day, with **three different jobs** — not three renderings of one grid
(`D-18`, `S-64`). Month reads the shape, week is where you edit, day is where you do.

**This area stays separate from the daily class capture** (`D-24`) — the timesheet never appears
inside attendance, the topic log or homework. And **an unfilled period is simply free** (`D-23`):
no nag, no completion %, no "you haven't finished your timesheet". Nothing on these screens asks
her to account for a blank.

## `My week` — `/timesheet`
**Status:** EXISTS, small changes · **Refs:** `D-18` `D-20` `D-23` `D-24` `S-70` `S-75` `Q-37`

**Arrives asking:** *"What does my week look like, and what am I doing in the gaps?"*
**Leaves having:** blocked out next week, or filled in the days she missed.

**Context:** Sunday evening or a free period. Phone or laptop, minutes — this is the **4pm
teacher**, not the 9:02 one. The 9:02 version of this screen is My Day (`S-63`).

### What's on it *(verified)*
Week arrows → three counters (teaching / recorded / still open) → the grid: periods down, days
across. Teaching cells are green and locked and carry subject + class; recorded cells show the
work label and note; open cells show `+`. Tap → a sheet with the categories, a free-text name for
*Other*, and a note. Everything editable all day (`D-20`).

### Changes
1. **The counters become her record, not her score** (`S-70`) — *"27 taught · 6 recorded · 3
   covered for colleagues · 4 evenings"*. That is a sentence she can point at when she is asked to
   take a fourth cover, and it is the only thing on this screen that is for **her**.
2. **Cover shows up** (`Q-37`) — *(verified)* it does not today. A teacher who covered three
   periods this morning sees three **free** cells on her own grid, because the day is built from
   the timetable and her own entries only. Union in `period_substitutions`, read-only, exactly the
   way teaching periods come from the grid. Without it, item 1 has nothing to count.
3. **The picker pre-selects her usual** (`S-75`) — tap Tuesday P3 and "Notebook checking" is
   already highlighted, because that is what has been there for six weeks. One tap instead of two,
   and **nothing is written until she saves**. *(This replaces `S-62`'s pre-filled week: under
   `D-23` there is no day-confirm step, so a self-filling sheet would be a record she never
   wrote.)*
4. **A one-off working Sunday can be recorded.** *(verified)* `TimesheetService.week` drops any
   weekday outside `working_weekdays`, so sports day and exam Sundays are currently unrecordable.

### Actions
- **Tap a gap** → name the work. Two taps, and one once `S-75` lands.
- **Change week** → the arrows. That is all; this screen has no third action.

### States
| State | What she sees |
|---|---|
| Empty (new school) | *"Your school hasn't set its timings yet…"* — already correct, and it names who fixes it (an admin, in Plan → Timetable). |
| Nothing recorded | An open cell is `+`. **Never red, never a zero, and never chased** (`D-23`). |
| A good week | *"Nothing open"* is a statement, not a warning. A week she chose to leave blank is a valid week. |

### Deliberately not here
Her colleagues' weeks · **any completeness %** · any reminder to fill it in · anything that reads
as a target (`S-67`) · her salary — that figure comes from staff attendance and half-day leave
only, and this screen does not feed it (`D-25`).

## `My month` — `/timesheet` (month view) · **NEW**
**Refs:** `D-18` `D-23` `S-64`

**Arrives asking:** *"What did my month actually look like?"*
**Leaves having:** seen the shape of it — and tapped into a day she wants to fill in.

**Context:** end of a month, or the day the admin asks about a Tuesday three weeks ago.

*Framed as her record, not a hole-finder.* Under `D-23` an unrecorded day is not a debt, so a
sparse month is a sparse month — the view shows it without scoring it.

### What's on it
**One cell per day**, not 8 periods × 25 days — 200 cells is unreadable on a phone and this view
is for *pattern*, not entry (`ux-principles` §15). Each day is a three-mark bar: taught ·
recorded · open, plus the calendar state.

```
        M   T   W   T   F   S
   1                ▓▓▌ ▓▓▌ ▓░░       ▓ taught   ▌ recorded   ░ open
   2   ▓▓▓ ▓▓▌ ███ ▓▓▓ ▓░░ ·H·        L leave    H holiday    E exam day
   3   ▓▓▓ ▓▓▓ ·L· ·L· ▓▓▌ ▓▓▓        ·  nothing recorded
   4   ▓░░ ▓▓▌ ▓▓▓ ▓▓▓ ███ ·E·
```

Holidays, leave and exam days come from `CalendarEvent` and `leave_requests` — **read, not
re-derived** (§9). A month view that shows "gaps" on Diwali teaches people to ignore it.

### Actions
- **Tap a day** → the day view, ready to fill.

### Deliberately not here
Editing. This view navigates; the week and day views edit.

## `My day` — `/timesheet/[date]` · **NEW**
**Refs:** `D-18` `D-20` `D-24` `S-75`

**Arrives asking:** *"Record what I just did."*
**Leaves having:** one period named, in one or two taps.

**Context:** standing, between classes, phone — or that evening, catching up on yesterday. The
week grid is hard to hit accurately on a 360px screen; a day is a list.

### What's on it
A vertical timeline of the real school day — periods **and breaks** (`school_clock.breaks_of`
already returns them) — classes locked and labelled, gaps tappable, cover marked as cover
(`Q-37`). Nothing at the bottom: there is no day to submit (`D-23`).

### Deliberately not here
A second copy of the period card — a class row links to My Day's card, it does not embed it. And
nothing from the daily class capture (`D-24`).

## `Leave` — `/timesheet/leave`
**Status:** CHANGING · **Refs:** `D-04` `Q-15`
*"How much leave do I have, and can I take Friday off?"* Balance, apply, own history.
**Gains half-day** with AM/PM — *which* half decides which periods need cover.

## `My salary` — `/timesheet/salary` · **NEW**
**Refs:** `D-06` `S-16` `S-37` · **Blocked on** `Q-05`–`Q-08`

**Arrives asking:** *"What am I getting this month, and is it right?"*
**Leaves having:** understood the figure — or knowing exactly which day to query.

### What's on it
1. Her month: days present, leave used, balance
2. **The line-by-line calculation** (`S-16`) — not just the total
3. **The days behind the numbers, clickable** (`S-37`) — *"absent 3 days"* must open to *which*
   three, or the first dispute becomes a manual reconciliation in a notebook

### Fenced
**She sees only herself.** No colleague's figure, no school total, no ranking.

---

# Plan / syllabus

## `My subjects` — route TBD (new landing for `/plan`)
**Status:** NEW · **Refs:** `D-10` `S-46` `Q-17`

**Arrives asking:** *"Where am I in my own subjects, and what's next?"*
**Leaves having:** decided what to teach this week, or knowing she needs to catch up.

**Context:** planning the week — Sunday evening or a free period. Phone or laptop.

### The problem *(verified)*
`/plan/*` is open to teachers but the screens are **admin-shaped**: pick a year, pick a class,
pick a subject, then look at one plan. A teacher with six class-subjects picks her way to each
one, every time. There is **no "my subjects" screen anywhere**, and `?mine=true` — which already
exists on the classes endpoint — isn't used by any plan screen.

### What's on it (`S-46`)
One row per class-subject she teaches — five to eight rows, which is **a list, not a selector**:

```
6-B · Maths     ▓▓▓▓▓▓▓░░  on track    next: Fractions — multiplication
7-A · Maths     ▓▓▓▓░░░░░  2w behind   next: Integers — word problems
8-C · Maths     ▓▓▓▓▓▓▓▓░  ahead       next: Mensuration — surface area
```

Each row: where she is, whether she's on pace, and **what to teach next** — the last of which is
the reason she opened the screen at all. Tapping a row opens today's plan detail.

### Visibility — settled (`D-15`)
**A subject teacher sees her own subjects only** — blocked, not merely defaulted. She has no
class-wide or school-wide syllabus view.

*(Claude had recommended not blocking, on the grounds that hiding a coverage figure between
colleagues invites the belief it is being used against them. Overruled; build to `D-15`.)*

## `Plan` tabs — `/plan` (Year · Syllabus · Week · Timetable · Hostel) · **EXISTS**
Editing is admin-only (`canEdit = org_role === "admin"`); teachers get read views. Unchanged for
now — the change is the landing (`S-46`), not the tabs.

---

# Tasks

## `Tasks` — `/tasks` (Today · Boards · Done) · **EXISTS**
**Status:** CHANGING · **Refs:** `D-40` `D-43` `D-48` `S-110`

**Arrives asking:** *"What am I still carrying?"*
**Leaves having:** cleared what she can and seen what's left.

**Context:** 4pm, desk. The 9:02 teacher never opens this — she gets the urgent slice on My Day
(`D-41`).

> **`D-43` gives this screen a job it did not have before.** My Day now shows a 3-day window, so
> **everything outside it is only here**: her overdue backlog, her future-dated work, her undated
> tasks. This is the module's home page, and the `n older tasks →` footer on My Day links straight
> to it. It has to be complete, because nothing else is.

### What's on it *(verified)*
A tab bar of **My tasks + one tab per board**, a day-progress bar, then a Monday-style table on
desktop / a checkable list on mobile.

### Session 5 — the changes are small and the screen is mostly right

- **`D-48`/`S-111` — the client-side filter goes.** *(verified defect)* `page.tsx:156` re-filters
  board rows to `!assignee || assignee.id === me`, discarding the visibility answer the server
  already computed. Harmless for a teacher on a `task_scope='assigned'` board — she'd see the same
  rows either way — and it is what makes the **admin's** Follow-ups tab show nothing (see
  `admin.md`). Two implementations of one rule (ux-principles §9); delete the second.
- **`S-110`** makes *My tasks* the one that matters and the board tabs secondary. She has one head;
  which board a task lives on is our concept.

### Deliberately not here
Her periods — those are My Day's, and the two lists must not both claim to be "today" ·
anyone else's tasks on a privacy board (`core/visibility.py:80`) · a completion rate for her.

---

# Exams & scores

## `Scores` — `/students/scores` · **EXISTS**
**Status:** EXISTS, small changes · **Refs:** `D-49` `S-113` `S-114`

**Arrives asking:** *"Let me get these marks in."*
**Leaves having:** opened the class she is about to record, or reopened an exam to fix a mark.

**Context:** **evening, at a desk, with a stack of marked papers.** Not a between-classes screen —
the same call `D-36` made for homework checking, and for the same reason.

### What's on it *(verified)*
Class cards (teacher sees only classes she teaches, via `/academics/classes?mine=true`; admin all),
then a **feed of previous exams** — name, type, class, subject, topic, out-of, author, photo count,
`scored/roster` and the class average. Each card reopens the exam.

### Changes
- **`D-55`/`S-135`** — the type badge shows **the school's own word**. Today `type` is a 9-value
  CHECK constraint, so a school running *CET* cannot file it as a CET (see `modules/exams.md` §4.1).
- **`S-114`** — the feed groups **minor** and **major** tests rather than interleaving them by
  date. A slip test and the term finals are not the same event and should not read as one stream.
- **`D-53`** — a locked exam reads as locked in the feed, so she can see at a glance what is settled
  and what is still hers to finish.

### States
| State | What she sees |
|---|---|
| Empty (new school) | Her class cards, and *"Exams you record appear here."* Never an empty feed presented as a school with no results. |
| Exam saved, no marks yet | *"no marks yet"* beside it — **not** 0%. A recorded exam nobody has marked is not a failed class (ux-principles §5). |
| Marks recorded, no photos | Reads exactly like any other exam. Form entry is a first-class path, not a degraded one. |
| Her first exam of the year | No trajectory anywhere — *"a single point is not a trajectory"* is already the rule (`exams.py:169`). |

### Deliberately not here
Any class she does not teach (admin sees all; she sees her own via `?mine=true`) · bands or tiers
(P4) · a school-wide average — that is the admin's board, and a subject teacher comparing herself to
a school figure is the ranking `D-25` fences.

---

## `Exam capture` — `/students/scores/[classId]` · **CHANGING**
**Status:** CHANGING · **Refs:** `D-49` `D-50` `S-116` `S-117` `Q-51`

**Arrives asking:** *"Forty papers, marked. Now what?"*
**Leaves having:** the whole class's marks stored, without typing forty names.

### What's on it *(verified)*
**Whole class | Few students** tabs (few = pick who sat it first). Then the capture: **drop the
photos before any typing** → the AI reads the header (title, subject, total, topic, date) and the
student rows → the deterministic matcher attaches identities (roll → exact → fuzzy → unmatched with
candidates; one student can never be claimed twice) → **a review grid the teacher confirms** →
`POST /assessments/exams` writes cycle + scores + files the photos as evidence, in one transaction.

**The division of labour is already right and must survive `D-50`:** the model **transcribes**, the
deterministic matcher **decides**. A hallucinated name cannot write a score.

### Session 6, second pass — **verify and lock** (`D-53` `D-54`)

The review grid gains a real end. Not *Save* — **Verify & lock**:

```
   38 of 40 read · 2 need a look
   ┌────────────────────────────────────────┐
   │  ✓ Verify & lock                        │
   └────────────────────────────────────────┘
   Locking makes this the record. An admin can unlock it.
```

**Three things happen at that tap, and only one of them is visible:**

1. the marks become the trusted record — this is what `assessment_scores.verified_by` was always
   for and has never been set by this flow (`services/exams.py:275`);
2. the **corrections are frozen** — what the model read, what the teacher changed it to, and why
   (`D-54`, `S-137`, `S-140`);
3. nothing about the child changes.

> ⚠️ **Why the lock is load-bearing and not a nicety.** `ExamService.save` full-deletes and
> re-inserts a cycle's scores on every edit (`exams.py:270-279`). Without a lock, a mark corrected
> in November silently replaces the one confirmed in July and **the training pair changes after the
> fact** — a corpus with drifting labels is worse than none, because you can't tell which rows
> moved. See `S-136`.

**What the teacher is told, and what she isn't.** She is told the exam is now the record and that
an admin can unlock it. She is **not** shown anything about model training on this screen — that is
an org-level agreement (`S-138`, `Q-61`), not a per-exam consent prompt she has to read forty times
a term.

### Session 6 — the paper check (`D-50`)
A second, **optional** pass over the same photos. `S-116` scopes it to two claims, both about the
**teacher's paper** rather than the child's answer, and both with a ground truth:

```
  ⚠ Page 3 · marks total 23, header says 25
  ⚠ Page 7 · Q4 has no mark beside it
```

It appears **beside the review grid, never inside it** — it does not change a mark, and it does not
block saving. `S-117`: anything that judges an *answer* stays behind a flag, is shown only while
the human is looking at the paper, and is **never stored**.

### States
| State | What she sees |
|---|---|
| AI off (no key) | Photos still upload and are still kept as evidence; the form is manual. Already the behaviour (`ai/scores.py` returns `None`). |
| Page unreadable | *"Couldn't read page 3"* — never a blank grid presented as a read. |
| A row matched `fuzzy` | Flagged for a second glance, with the candidates one tap away. |
| Two students with the same name | Both left unmatched, with each other as candidates — a human's call. |
| Locked | Read-only, with who locked it and when. *"Ask an admin to unlock"* — never a dead grid with no explanation (`Q-62`). |
| Unlocked by an admin | The reason is shown on the exam, the unlock is an appended row (law 3), and the frozen corrections are **flagged**, not rewritten (`S-139`). |

### Deliberately not here
Marks for a student outside this class (`ExamService.save` rejects it) · a band anywhere (P4) · a
rank · a computed final grade (`S-114`'s warning) · any per-exam consent prompt for `D-54` — that
is an org agreement, not something a teacher reads forty times a term.

---

## `Exam` — `/students/scores/exam/[cycleId]` · **EXISTS, CHANGING**
**Status:** CHANGING · **Refs:** `D-53` `S-119` `S-139` `Q-62`

**Arrives asking:** *"How did they do — and is this right?"*
**Leaves having:** confirmed the marks, or fixed one.

**Context:** later. Reopened from the scores feed by whoever recorded it, or by the admin.

### What's on it *(verified)*
The saved exam: header (name, type, class, subject, topic, out-of, date), the roster with each
mark, the class average, and **the photo evidence pages**. Editing re-sends the whole grid — full
replace, so a removed row really goes away. Org-wide and diagnostic cycles fall back to the score
grid instead.

*A student who has a mark but has left the class or the subset **still shows** — a saved mark never
silently disappears from the review (`exams.py:172`). That is already right and worth keeping.*

### Changes
- **`D-53`** — this is where a locked exam is *seen* as locked: read-only, with **who locked it and
  when**, and *"ask an admin to unlock"* rather than a dead grid with no explanation.
- **`S-139`** — an unlock shows its reason here, appended (law 3), with the frozen corrections
  **flagged** rather than rewritten.
- **`S-119`** — the evidence pages are already on this screen and **only** this screen; the same
  pages should be reachable from the child's report card, which is where a parent asks for them.

### States
| State | What they see |
|---|---|
| Not locked | Editable, with *Verify & lock* at the end. |
| Locked | Read-only + who/when. The average and the evidence still render — locking hides nothing. |
| Unlocked again | The reason, and who unlocked it, on the exam. |
| Marks recorded, no photos | Perfectly normal — form entry is a first-class path, not a degraded one. |

### Deliberately not here
A band, a rank, a composite grade · another class's marks · the training-corpus diff (`D-54`) —
it is written at lock and read by nobody in the product.

---

# Fees

Exactly one fee-related thing ever reaches a teacher, and what it may say is an open fence.

## `Fee follow-up` task — on `/tasks` · **NEW** 🔴

**Role:** teacher (usually the class teacher) · **Status:** NEW — **blocked on `Q-66`**
**Refs:** `D-63` `D-65` `S-154` `S-161`

**Arrives asking:** *"Who am I ringing, and what do I say?"*
**Leaves having:** made the call and recorded **what the family said**.

**Context:** her Follow-ups board, between classes. She was given this because she is the one with
a relationship with the family — which is the entire reason for handing it to a teacher rather
than the office.

> 🔴 **This screen cannot be built until `Q-66` is answered, because the fence runs straight
> through it.** `D-63` says only admins see fee data; `D-65` hands the chase to a teacher. A task
> reading *"Call Kabir's father — ₹12,000 overdue"* breaks the non-negotiable in `CLAUDE.md` and in
> `ux-principles.md`'s hard-fence table.
>
> **`S-154` recommends the family and the subject, never the amount:**
>
> ```
>   Fee follow-up · Kabir Shah (8-B)
>   Please speak to the family and record what they say.
>   father Ramesh · 98xxx xxxxx                    [ Call ]  [ Done ]
> ```
>
> The parent already knows the number. She does not need it to make the call. And the reason the
> fence exists is not confidentiality for its own sake — **a teacher who knows which families are
> behind on fees treats those children differently**, and every child on that list has done
> nothing wrong.

### Actions

- **Call** → `tel:`, and it records that contact happened (`followup_actions`, `S-156`) so the
  admin's board shows *"Priya spoke to them"* rather than re-listing the family tomorrow.
- **Done, with an outcome** → *"spoke to the mother — paying after the 15th"* (`S-161`, ux §8).
  **"Reminded" is an event; the outcome is what makes the row go away.** Without it the same
  family is rung every week by a different person, and the school looks disorganised to exactly
  the people it is asking for money.

### Deliberately not here

The amount (pending `Q-66`) · any other family's fees · the class's collection figures · a list of
who else is behind · anything that would let her infer the amount from context — which includes
**sorting her tasks by amount** or badging them *"large"* / *"small"*.

---

# The support programme (bands)

Two screens, both for the **4pm teacher** — the owner of a handful of C-band children (`D-71`).
The 9:02 teacher touches none of this: her band-aware surface is the checks section of the period
card, which already exists and already differentiates by tier (`recommendations.py:131-158`).

## `My support students` — `/support` · **NEW**
**Status:** NEW · **Refs:** `D-67` `D-71` `D-72` `D-77` `S-165` `S-170` `S-188` `Q-73`

**Arrives asking:** *"Who am I responsible for, and who needs me this week?"*
**Leaves having:** written this week's check-in for the one or two children who needed it.

**Context:** Friday afternoon or twice a week, standing at her desk with her bag packed. Phone.
**Six children, five minutes, total.** If this screen takes longer than that it will be open twice
and never again.

### What's on it, in order

1. **Headline** — a sentence about *her* week, not the programme: *"3 of your 6 checked in. Kabir
   hasn't been checked in 3 weeks."*
2. **Her children**, grouped by subject — ownership is **per subject** (`D-77`), so a child who is
   C in Hindi and C in Maths sits on two teachers' lists and neither is guessing whose he is. Each
   row: class, when he entered, how the thread is going, and one button.
3. **Moved to B** — the children who left the programme, kept visible for the term · *why: this is
   the only place the work pays off, and a list that only ever grows is a list nobody opens.*
4. **More** — the descriptors, and the band history of each child.

```
My support students                                    Term 2 · week 6

  3 of your 6 checked in this week.  Kabir hasn't in three.

  ENGLISH · C → B                                          4 children
   Kabir Shah      6-B   in since 12 Jul · no check-in, 3 weeks   🔴  [ check in ]
   Diya Nair       6-B   in since 12 Jul · 4 check-ins · improving     [ check in ]
   Ishaan Kumar    6-A   in since 2 Aug  · new this week              [ check in ]
   Aarav Rao       6-B   ready to re-test · 60 wpm, ≤3 errors         [ re-test ]

  MOVED TO B                                              this term
   Sara Iqbal      6-B   C → B on 30 Jul · band test, 58%
```

### Actions
- **Check in** → the weekly sheet on the child's page (`S-165`). The row's amber clears.
- **Ready to re-test** → the child is flagged as ready. **The move itself happens on a test**
  (`D-76`) — either the school's band test, or the next ordinary test she promotes from the exam
  screen. She never builds a test here (`S-171`).

### States
| State | What she sees |
|---|---|
| Empty (nobody assigned) | *"No children are assigned to you yet. The admin assigns them after a class is banded."* — and nothing else; this is not her failure. |
| Everyone checked in | *"All six checked in this week."* A finished week must read as finished. |
| Never checked in anyone | *"Check-ins appear here once you write one."* No streak, no compliance score. |
| A child left / changed class | The row stays with *"now in 7-A"* until the admin reassigns — a child does not silently vanish from the person responsible for him. |

### Deliberately not here
Other owners' children · the whole class's bands (that is the admin's screen) · **any comparison of
her against other owners** (`S-170`) · marks for subjects she doesn't own · a completion percentage
for her check-ins.

## `Support child` — `/support/[studentId]` · **NEW**
**Status:** NEW · **Refs:** `D-72` `S-164` `S-165` `S-166` `S-167` `S-178` `Q-73` `Q-74`

**Arrives asking:** *"What's happened with Kabir, and what do I do next?"*
**Leaves having:** written four short fields — or nothing at all, and still learned something.

**Context:** 60 seconds. This is the screen the whole module lives or dies on, because it is the
only one that asks a teacher to type about one child, by hand, repeatedly.

> **`S-164` is the design.** The page **opens already written**. Everything in the top block is
> read from capture that other teachers already did — `lesson_observations`, `check_results`,
> `homework_results`, `attendance_exceptions`, `session_student_logs` (module §3.4). She is never
> asked to record what the product already knows, and she gets value before giving data (P3).

### What's on it, in order

1. **Headline** — *"Band C in English since 12 July. Moves to B when he reads a grade-level
   passage at 60 wpm with ≤ 3 errors, twice running."* The exit criterion is on the screen from day
   one (`S-167`), because a goal decided at the end is a judgement, not a target.
2. **His week, already recorded** — the pre-filled ledger · *why: `S-164`; it is also the honest
   answer to "what did he do this week" when she wasn't in the room.*
3. **This week's check-in** — four fields (`S-165`).
4. **Before this** — the thread, newest first · *why: the movement is only visible as a sequence.*
5. **More** — the C and B descriptors side by side (`S-166`), his English marks, his band history.

```
← Kabir Shah · 6-B                                       English · Band C

  Band C since 12 Jul (band test, 34%).  Owner: you.
  Moves to B when: reads a grade-level passage at 60 wpm, ≤3 errors, twice running.

  ┌ His week, already recorded ──────────────────────────────┐
  │ Mon 28   absent                                           │
  │ Tue 29   English P2 — needs work, "Reading aloud" (Anil)  │
  │ Tue 29   homework not done — Ex 4.2                       │
  │ Wed 30   C-band check missed — "read the worked example"  │
  │ Thu 31   evening study — "finished 2 pages without help"  │
  │ Fri 01   —                                                │
  └──────────────────────────────────────────────────────────┘
     nothing here was typed twice — it is his week as his teachers already recorded it

  ┌ This week's check-in ────────────────────────────────────┐
  │ What we worked on   [ flashcards, 10 min daily        ]   │
  │ What changed        [ read a full paragraph unaided   ]   │
  │ What's next         [ move to the Ch 5 passage        ]   │
  │ Ready to re-test?   ( ) not yet   ( ) yes                 │
  │                                        [ Save check-in ]  │
  └──────────────────────────────────────────────────────────┘

  ┌ Before this ─────────────────────────────────────────────┐
  │ Wk 5   sight words → "still stalls on 4-letter words"     │
  │ Wk 4   flashcards  → "no change"                          │
  └──────────────────────────────────────────────────────────┘

  what C means · what B means                  [ show descriptors ]
```

### Actions
- **Save check-in** → one append row (law 3), the thread grows, the `/support` row clears.
- **Ready to re-test** → `S-178`: the sheet shows what the claim rests on — the exit criterion, the
  last band-test percentage, the trend of check-ins. **She proposes readiness; a test moves the
  band** (`D-76`). This is the honest division: the owner is the person who knows he is ready, and
  she is also the person with an interest in him being ready.

---

## `Use this as the band test` — on `/students/scores/exam/[cycleId]` · **NEW**
**Status:** NEW · **Refs:** `D-76` `S-182` `S-184` `S-187` `Q-80` `Q-81` — *session 9, second pass*

**Arrives asking:** *"This slip test told me exactly what I needed to know — can it count?"*
**Leaves having:** re-banded the children who sat it, in that subject, on evidence she chose.

**Context:** she is already on the exam she just verified and locked. One action at the bottom of a
screen she is on anyway — **not** a new place to go, and not a decision she has to remember to make.

```
Ex 4.2 slip test · 7-A Maths · 12 Aug            locked by you, 4:12pm

  … the scores …

  ┌ Use this as the band test for 7-A Maths ─────────────────┐
  │ out of 10 marks · 24 of 38 children sat it                │
  │ ⚠ a 10-mark test is a small basis for moving a child      │
  │                                                           │
  │ Moves:  Kabir C → B     Diya B → C     2 others up        │
  │         20 unchanged · 14 didn't sit it, bands unchanged   │
  │                                            [ Confirm ]    │
  └──────────────────────────────────────────────────────────┘
```

### The four rules on this one action
- **A flag, never a type change** (`S-182`) — this stays a slip test in every exam roll-up. Re-typing
  it would trade the test for the band.
- **Locked only** (`S-184`, `D-53`) — an unverified transcription must not move a child between
  support tiers.
- **The size is shown, and a small test warns but does not block** (`S-184`) — SF-1's leave-policy
  shape. A teacher who knows the test was small can still be right about the child.
- **One subject** (`S-187`) — 7-A Maths, nothing else.

### States
| State | What she sees |
|---|---|
| Not locked yet | The action is present and disabled: *"Verify and lock this exam first."* |
| Some children absent | *"14 didn't sit it — their bands are unchanged"* (`Q-80`). *(verified)* the code already skips them; the screen has to say so, or she will believe the class was re-assessed. |
| Subject not monitored | The action is absent (`D-68`). |
| Already the band test | *"This is 7-A Maths's band test for Term 2 — filed 12 Aug."* Re-filing appends; it never overwrites (law 3). |
| Nobody moves | *"Everyone is already in the band this test suggests."* A test that confirms the grouping is a useful result, not a failed action. |

### Deliberately not here
Any automatic promotion · a suggestion that she promote something · promotion of an exam she did
not mark — and no path that re-bands a child **down** without her reading his name (`Q-81`).

### States
| State | What she sees |
|---|---|
| Entered today | *"He joined the programme today. Write what you plan to do — there is nothing to review yet."* |
| **No signals this week** | *"Nothing recorded for him this week."* — a **statement about the record**, never *"no progress"* and never red (ux §5, §10). A week where his teachers logged nothing is not a week where he did nothing. |
| He was absent all week | The ledger says so, and the check-in prompt changes to *"absent all week — nothing to review."* |
| Exit criterion never set | 🔴 *"No exit criterion — nobody can tell when he's done."* The one thing on this page that should nag. |

### Deliberately not here
His fees · his bands in subjects she doesn't own (one link to the report card, not a column) ·
**a photo of his work** (P5) · any field that reads as a diagnosis (module §7) · a rating of the
child by her — the ratings that exist are per-lesson exceptions, made in the room, by the teacher
who was there.

---

# Not yet brainstormed

`Lucy` `/lucy` · `Sessions` `/sessions` (+ meeting capture, per-student pages) ·
`Students` `/students` (directory + profile, restricted to her students).
