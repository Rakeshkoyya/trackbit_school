# Screens — Admin

Everything the admin sees, in nav order. Screens brainstormed in a session get a full entry;
everything else is a stub until its module comes up.

**Nav (desktop, in order):** Dashboard · Lucy · Plan · Students · Staff · Fees · Tasks · Setup
**Mobile bottom bar (4):** Plan · Tasks · Students · Lucy

**Who the admin is:** the person who runs the school — principal, correspondent, or director.
Desktop, usually at a desk, usually in the morning. Arrives with *"what needs me today?"* and
leaves having delegated or decided. They are interrupted constantly, so anything that takes more
than a glance to understand doesn't get read.

---

# Dashboard

Seven tabs. The overview is the front door; each tab answers one question the admin arrives with.

## `Overview` — `/dashboard`

**Status:** CHANGING · **Refs:** `D-02`

**Arrives asking:** *"What needs me today?"*
**Leaves having:** cleared the action rail, or delegated the items on it.

**Context:** 8–9am, desktop, two minutes before the first interruption.

### What's on it, in order
1. **The written briefing** — 2–3 sentences over the day's figures, AI-written at generate time
   with a deterministic fallback so it exists offline. *(exists, unchanged, and it is the right
   shape — this is the model for every other screen.)*
2. **Action rail** — what is waiting, each item linking to the screen that clears it
3. **One block per module** — headline sentence, 2–3 supporting figures, named rows underneath
4. **Fees block** — admin-only, client-side (teachers never receive fee figures at all)

### Changes from session 1
- The attendance block gains the yellow/red split from `D-02` — *"6 absent, 4 explained"* is a
  different morning from *"6 absent, none explained"*.
- The staff block gains half-day and late (`D-04`).
- **No payroll block** (`S-38`) — a salary figure on a screen that gets shown on a projector in
  a staff room is a different kind of accident.

### Session 7 — a **What's on** block (`D-51`)

A new block, and the only one on this screen that is not about something going wrong. Two lines
plus a fold:

```
🎂  Today · Guru Purnima — school open · 2 birthdays
    Aarav Sharma (6-B) · Diya Nair (9-A)                      [ Wish ] [ Assembly note ]
    This week · Fri 8 — Raksha Bandhan · Mon 11 — Priya (teacher)
    Coming up · Independence Day, 15 Aug — in 12 days              [ Add to calendar ]
```

Placement: **below** the modules that report problems, above Fees. It is not an alert and must
never be styled as one — nothing here is wrong, and a warm row in a column of red rows reads as
red (`S-132`).

**The one action that matters is `Approve`** — and it is the *only* thing on this screen allowed
to change a teaching day (`S-122`, made structural by `D-57`). It opens the **Approve this date**
sheet below, which forces the three-level choice from `D-58`. Until it is pressed, a suggestion
has changed nothing.

*(Second pass: the row states are now **suggested → approved → dismissed**, and a dismissal is
permanent and append-only (`S-148`) — the same suggestion must not return next week or next year.)*

**Empty state is a sentence with a denominator, not a blank block:** *"Birthdays known for 41 of
486 students — add DOB to the roster →"* (`S-124`, ux §4). If the school has no DOB and no
upcoming events at all, the block does not render — an empty card on the busiest screen is a
permanent advertisement for a feature (the `D-43` lesson from My Day's task window).

---

## `Attendance` — `/dashboard/attendance`

**Status:** CHANGING — the biggest single redesign from session 1
**Refs:** `D-01` `D-02` `S-05` `S-06` `S-07` `S-08` `S-09` `S-14` `S-22`

**Arrives asking:** *"Is the record trustworthy, and who needs a phone call today?"*
**Leaves having:** made or delegated a set of phone calls, and nudged whoever didn't mark.

**Context:** mid-morning, desktop. This is the screen the whole attendance module points at.

### Today *(verified)*
Four stat tiles → period capture heatmap → 14-day pulse area → by-class bars → staff strip →
"absent 3+ school days" red list with a working action rail. The heatmap and the red list are
genuine decision surfaces; **everything above them is numbers**, and they are above the fold.

### What's on it, redesigned

1. **Headline** — *"428 of 470 in today. 6 need a call. 13 periods still unmarked in 3 classes."*
2. **Needs a call** — the red list, at the top where it belongs.
   - 🔴 **red** — absent 3+ days, **no reason recorded** (`D-02`)
   - 🟡 **yellow** — absent, but a reason is on file
   - each row names the student, the class, the streak, the last day present, **who owns the
     follow-up** (the class teacher), and whether anyone has already been contacted today
   - *why: this is the only block on the screen that produces a phone call*
3. **Drifting** (`S-07`) — 60–85% and trending down. *why: the red list catches people at three
   days; nobody catches the slow fade from 95% to 78% over a term, which is where intervention
   is cheapest.*
4. **Left after lunch** (`S-05`) — only in `twice_daily` mode, where it is the *reason the school
   chose that mode*. *why: present in the morning and gone by afternoon is the single fact a
   school most wants and currently cannot see at all.*
5. **Chronic late** (`S-06`) — *why: `late_minutes` is captured today and then ignored everywhere.*
6. **Is the record complete** — the capture heatmap, pivoted **by teacher** as well as by class
   (`S-09`). *why: the decision this block produces is "who do I talk to", and a class grid makes
   the admin work that out for themselves.*
7. **More** — the 14-day pulse, the by-class bars, staff strip. *why: nobody arrives at this
   screen for a chart.*

### Actions
- **Remind guardian** → messages the guardians, records that it fired, row shows "reminded"
- **Assign follow-up** → puts it on the class teacher, appears in **her** inbox (`S-29`)
- **Record a reason** → red row becomes yellow (`D-02`, `S-21`)
- **Nudge teacher** → from a heatmap row, deep-links them to the unmarked periods (`S-10`)

### States
| State | Shows |
|---|---|
| Empty | *"No attendance captured yet. It appears here as teachers mark periods."* |
| Not captured | Neutral, never red, never 0% (`S-14`). *"6-B has marked nothing today"* is a gap in the record, not a class with nobody in it. |
| Nothing wrong | *"Everyone accounted for. All 44 periods marked."* — a good day should read as a good day, not as an empty screen. |

### Deliberately not here
Per-student period-by-period detail *(that's the student's own page)* · staff detail *(its own
tab)* · anything a teacher could act on themselves.

---

## `Staff` — `/dashboard/staff`

**Status:** CHANGING · **Refs:** `D-04` `D-21` `D-22` `Q-15` `Q-30` `Q-31` `Q-32`
`S-61` `S-66` `S-67` `S-68` `S-72` `S-74`

**Arrives asking:** *"Who is missing, is their teaching covered, and where is the slack?"*
**Leaves having:** arranged cover, decided a leave request, or found the slot to put something in.

**Context:** 9:12am, a teacher has phoned in sick, and the admin has under a minute before the
bell. Later in the week, the same screen answers a slower question about fairness.

### Already there *(verified)*
Four tiles (in today · periods uncovered · leave waiting · free periods unlogged) → the **live
board** (teaching · on other work · free · away, *every list named*, degrading honestly to
before / break / after / holiday / unset) → away-today rows with periods-due-vs-covered and an
**Arrange cover** sheet with ranked candidates → the leave queue carrying SF-1's policy warnings →
teaching-periods-vs-mean bars → a **what non-teaching periods went on** bucket chart → a per-teacher
day strip.

`D-21`'s grid and detail tab are, in substance, already this screen.

### What changes

1. **The slack profile** (`S-66`) — `D-21`'s chart, and the only genuinely new thing here. One
   stacked bar per period across the day: teaching / cover / own work / free / away. Its headline
   is a sentence, not the bars: *"Period 7 on Thursday is the only slot where 11 of 14 are free."*
   **Its job is finding slack** — when the staff can meet, which period invigilation comes out of
   — not watching people (`S-67`).
2. **The free band says what it is** — under `D-23` an unfilled period *is* free, so the band
   legitimately means **"free or unrecorded"** and the hint should say so once (`S-76`,
   `ux-principles` §4). One line of copy, and the decision stands.
3. **The "free periods unlogged" tile is deleted, not fixed** (`S-76`). `D-23` says there is no
   such state; and *(verified)* it counts periods that have not happened yet, so it was reddest at
   8:30am.
4. **Filters** on the detail table: by teacher, by category, by load flag.
5. **Hostel evenings appear** (`S-68`) — a warden running prep six nights a week currently reads
   as lightly loaded on every figure here.
6. **Half-day and late** (`D-04`) — and half-day must say **which half**, or the cover board
   cannot act on it (`Q-15`).

### Actions — two
- **Arrange cover** → the two-panel sheet below (`D-26`).
- **Decide leave** → links to `/staff/leave`; the queue arrives with its warnings attached, and an
  approval now hands back the cover flow (`D-27`).

### States
| State | Shows |
|---|---|
| Empty (new school) | *"No timetable yet — this board fills in from the grid."* |
| Not captured | "Staff attendance not taken — 'away' may be incomplete" *(already correct on the live board)*. |
| Nothing wrong | *"Everyone in, every period covered."* |

### Deliberately not here
**Any ranking of people** — load is compared to the org mean, framed *carrying more / has room*,
never 1st–14th (`S-67`). **No completeness score per teacher**, and no nag about unfilled
timesheets (`D-23`). **No salary** (`S-38`), and **no path from this data to pay at all** —
`D-25`: payroll is present/absent plus half-day leave, nothing here touches it.

---

## `Arrange cover` — sheet, from `/dashboard/staff` **and `/staff/leave`**

**Status:** CHANGING — the centre of the session-3 substitution flow
**Refs:** `D-26` `D-27` `D-29` `S-74` `S-78` `S-79` `S-80` `S-81` `S-82` `Q-12`

**Arrives asking:** *"Who takes 7-A at 11:20 — and what does that cost me?"*
**Leaves having:** every uncovered period assigned to a named person, who has been notified.

**Context:** 9:12am with the bell about to go, or — once `D-27` lands — calmly on Tuesday for
Friday's approved leave. The second is the version worth designing for; the first is the one that
happens when the second doesn't exist.

### Already there *(verified)*
One block per period the absent teacher was due to take: class, subject, covered/uncovered badge,
ranked candidates each with **the reason shown**, an Assign button, and Cancel cover afterwards.
Ranking is *teaches this subject elsewhere → teaches this class → lightest teaching load*.
Assigning notifies the substitute and puts the period in their My Day, and they can open the
period card. An absent **admin's** blast radius is their tasks, not their periods.

That is `D-26`'s two panels, already built. What is missing is what makes the choice a good one.

### What changes

1. **Say what the class gains** (`D-29`, `S-79a`) — the planner knows the class's **next planned
   topic**. A substitute who teaches that subject elsewhere can move the syllabus forward instead
   of supervising a study period, and that is the strongest reason to prefer anyone. It needs no
   plumbing downstream: the period card credits the class-subject, so the lesson lands in the
   class's log and the forecast picks it up. P2 holds.
2. **Say what the substitute gives up** (`S-74`) — *(verified)* `busy_reason` never reads
   `timesheet_entries`, so a teacher who recorded *"exam work — Class 10 scripts"* is offered as
   *"free · 3 periods today"*. Don't block on it; show it.
3. **Warn if she is behind herself** (`S-79b`) — pulling a teacher who is two weeks behind in her
   own subjects makes two problems out of one.

```
7-A · Period 4 · Maths            next planned topic: Fractions — multiplication

  Meera    teaches Maths in 8-B    free            → can teach the next topic   [Assign]
  Anil     teaches this class      free                                         [Assign]
  Priya    free                    notebook checking 6-A                        [Assign]
  Ramesh   free                    his own 7-C Maths is 2 weeks behind          [Assign]
```

Every row stays assignable — the rank is a suggestion and the admin knows things the system does
not (`D-29`). But those two right-hand sentences are what change the decision, and neither is on
the screen today.

4. **It opens for a future date** (`D-27`, `S-80`) — *(verified)* today it opens only from an
   *"away today"* row driven by today's staff attendance, so an approved leave for Friday has no
   path to cover until Friday morning. `SubstitutionService.create` and `busy_reason` both already
   take a date; this is an entry point on the leave request plus one parameter.

5. 🔴 **The busy check must learn about approved leave** (`S-82`) — *(verified)* it refuses
   someone teaching, already covering, or carrying a `staff_absences` row **for that date**. There
   is no staff-absence row for a future date, and it never reads `leave_requests`. **So the moment
   4 ships, an admin can assign Friday's cover to a teacher who is herself on leave that Friday,
   and nothing objects.** One clause. Ships *with* 4, not after it.

6. **Approved leave puts the work on the rail** (`S-81`) — *"Friday: Anil away, 5 periods to
   cover"*, dated to that day, rather than relying on someone reopening the leave screen.

### Actions — two
- **Assign** → substitution created, teacher notified, period appears in their My Day.
- **Cancel cover** → appends `cancelled_at`; the row stays, so "we moved it twice this morning" is
  still readable at 4pm. The period can be re-covered (the unique index is partial, live rows
  only).

### States
| State | Shows |
|---|---|
| Nobody free | *"Nobody is free this period. The class will need merging or a study period."* — already the copy, and it is the right answer rather than a blank list. |
| No lessons | *"No lessons on today's timetable for them."* |
| All covered | Every block green with the name on it. |

### Deliberately not here
**Auto-assignment** — `D-29`: the system suggests, the admin assigns. **Any payment for cover** —
`Q-12`: covering is operational, and the moment it earns money the substitution record becomes a
financial document needing approval and dispute handling.

## `Syllabus` — `/dashboard/syllabus`

**Status:** CHANGING — but far less than expected; most of it is already built
**Refs:** `D-09` `D-12` `S-40` `S-41` `S-42` `S-43` `S-44` `S-45` `S-50` `S-51`

**Arrives asking:** *"Will we finish the portion, and who is falling behind?"*
**Leaves having:** asked one teacher for a catch-up plan, or sent someone to size their chapters.

**Context:** weekly, desktop, and *hard* in the fortnight before an exam.

### Already there *(verified)*
Scope switcher **by class / by subject / by teacher** (+ a school node), checkpoint switcher
**whole year / term / next exams**, four stat tiles, a RAG donut, coverage row-bars per node,
**ahead** (top 3) and **needs support** (bottom 3) lists, and a per-exam checkpoint saying which
subjects are short of portion. `D-09` is substantially satisfied by what exists.

Two honesty rules already baked in and **not to be broken by a redesign**: `unplanned` /
`unallocated` / `unestimated` are **words, never colours**; and nothing is ranked below a
minimum sample (≥3 rated class-subjects, ≥10 logged periods for a teacher).

### What changes
1. **Headline becomes the exam** (`S-50`) — *"Second Terminal in 24 days · 4 subjects short of
   portion"* is a stronger opening than any coverage %, and it is already computed.
2. **Every "behind" row says why** (`S-41`) — periods lost · nothing logged · chapters never
   sized · genuinely slower. *why: "6-B Maths is 3 weeks behind" is where the screen stops and
   the admin's work starts; "6-B Maths lost 8 periods to exam week and two holidays" is a
   different conversation in which nobody is at fault.*
3. **Unlogged is separated from behind** (`S-42`) — a subject with no lesson logs is **unknown**,
   never red, never on a "worst" list. Same rule as attendance's capture heatmap.
4. **Coverage over time** (`S-40`) — the one chart the board lacks; actual vs the baseline plan
   as a reference line, so the gap is visible as a widening or closing band.
5. **Section comparison** (`S-43`) — 6-A Maths vs 6-B Maths, the fairest comparison in a school.
6. **Ranking explained in words** (`S-45`) instead of a composite score nobody can reconstruct.
7. **One coverage definition** (`S-51`) — the admin's % and the parent's % are computed
   differently today.

### Actions — one, plus a link (`D-16`)
- **Ask for a catch-up plan** ✅ — a **meeting request, not a directive** (`S-60`). Reads
  *"Discuss 6-B Maths catch-up"*, carries the gap, the exam it threatens and the **cause**
  (`S-41`), and lands as a task on that teacher. They meet, they agree a plan, and **the
  reschedule follows the conversation.** The row clears on the recorded **outcome**, not on the
  press.
- **Size these chapters** — deep link for `unestimated` / `unplanned` rows. Still open (`S-44b`);
  it schedules nothing, so it survives `D-16`.
- ~~Schedule new chapters~~ — **REJECTED** (`D-16`). The admin never reschedules from the board;
  `extend_plan` stays in the plan screen, used after the discussion.

*Nothing that merely marks a row as seen.* Most syllabus problems are not one-tap solvable, and
a fake action implies a problem is closed when it isn't.

### States
| State | Shows |
|---|---|
| Empty | *"No plans yet — coverage appears once chapters are sized and a plan is approved."* |
| Not enough data to rank | A countdown, not a blank: *"ranking starts once 3 subjects have plans (2 so far)"* (`Q-18`). |
| Nothing behind | *"Every subject on track. Nearest exam is comfortable."* |

### Deliberately not here
A teacher league table · automatic re-planning (the plan is a baseline and stays locked, P2) ·
coverage as a performance target — *the moment coverage % scores a teacher, lesson logs stop
being honest, and every downstream number in the product is built on them.*

## `Homework` — `/dashboard/homework`

**Status:** CHANGING — mostly small, one of them a correction to a figure about people
**Refs:** `D-30` `D-31` `S-83` `S-85` `S-87` `S-88` `Q-40` `Q-42`

**Arrives asking:** *"Is homework being done — and is anyone actually checking it?"*
**Leaves having:** reminded a guardian, assigned a follow-up, or spoken to a teacher.

### Already there *(verified)*
Four tiles → completion over the window → **by class** → **by subject** → **"Students who keep
missing it"**, named, with streak, subjects, the responsible teacher, and working *Remind
guardian* / *Follow up* actions → **"Is homework being checked?"** per teacher (set / checked /
overdue unchecked / rate) → perfect record and most improved. Five queries for all of it.

`D-30` and the roll-up half of `D-31` are satisfied by what exists. The hint text already carries
the module's central rule: *"Unchecked homework never counts against a student."*

### What changes

1. 🔴 **"Overdue, unchecked" is currently blaming teachers for a bug** — *(verified)* the
   teacher's own checking queue only ever shows her **yesterday's** homework, so Friday's is
   counted against her on Monday having never been offered to her. `D-33` fixes it at the source
   (nothing expires off her screen), and both sides must then share **one** definition of overdue,
   on the same working-day clock (`ux-principles` §9, `S-96`).
2. 🔴 **The red list is naming children who were absent** (`S-85`, `S-102`) — a child off sick
   when the homework was set is flagged `not_done`, appears here, and their guardian gets
   reminded. `D-34` makes it **carried**, and carried must be skipped by the streak and excluded
   from the completion figure, exactly as `not_checked` already is.
3. **A new column: late** (`D-33`, `S-99`, `Q-43`) — recommend *"82% done · 6 of them late"*.
   Folding late into done hides a class where everything arrives four days after the deadline;
   counting it as a miss punishes a child who did the work. Same discipline as `not_checked`.
   **And `D-38` asks for both latenesses** — the child's, and the teacher's (`checked_at` vs the
   deadline, already computed). Keep them in separate columns; they are separate conversations
   (`S-95`).
4. **The student drill-down becomes reachable** (`D-31`, `S-86`) — the row already links to
   `/students/{id}`; what is missing is the homework history *on* that page. Endpoint, schema and
   client method all exist and nothing calls them. **Same component as the teacher's by-student
   view** (`S-101`) — built once.
5. **Daily load per class** (`D-37`, `S-87`) — *"8-B had 5 subjects set homework on Tuesday"*. Six
   teachers each made a reasonable decision and no screen adds them up. Shown to the admin and the
   class teacher, **never to a subject teacher**, and **never a cap**.
6. **Say what a partial is worth** (`S-88`) — it currently counts as zero here and as half a topic
   on the syllabus board (`Q-40`).

### Actions — two, both already built
- **Remind guardian** → records that it fired, so the row says "already reminded" (`followup_actions`).
- **Follow up** → lands on the class teacher.

### States
| State | Shows |
|---|---|
| Empty | *"No homework set yet — this fills in as teachers set and check it."* |
| Not checked | Counted and reported **separately**, never as a student's miss. Already correct, and it is the module's load-bearing rule. |
| Nothing wrong | *"Nobody is repeatedly missing homework. That is the good case."* — already the copy. |

### Deliberately not here
Marks or grades (`S-91`) · **any "homework should have been set" expectation** (`S-92`) — a target
on setting produces homework set for a dashboard, the same failure the syllabus board is careful
to avoid · a teacher league table.

## `Tasks` — `/dashboard/tasks` · **EXISTS**
*"What work is open and what's overdue?"*

**Session 5 — unchanged, and it is already the right screen for the admin's second moment.**
`services/insights/tasks.py` gives open / overdue / completed **by assignee**, red rows named,
each carrying *Reassign · Extend · Nudge*. That is *"did the things I asked for get done"*
answered. The admin does not need the Follow-ups board as a list — they need this. What the
session changes is that the board itself must stop lying to them (below).

## `Follow-ups board` — `/boards/[id]` · **EXISTS, CHANGING**
**Status:** CHANGING · **Refs:** `D-40` `D-44` `D-45` `D-46` `D-47` `D-48` · *(closes `Q-45`
`Q-48`)*

**Arrives asking:** *"What have I asked for, and is any of it moving?"*
**Leaves having:** closed what's done, re-dated or dropped what has gone stale.

**Context:** Friday afternoon, desktop, minutes. Not a daily screen — the daily answer is the
overview's action rail.

### What's on it *(verified)*
One shared board named **Follow-ups**, created by `ensure_followups_board`
(`services/insights/actions.py:51`) and shipped in the seed. `visibility='public'`,
`task_scope='assigned'` — a teacher sees only her own rows, the admin sees all
(`core/visibility.py:67`, enforced server-side in `services/task.py:265`). **This is exactly the
board the founder described; it already exists** (`D-40`).

Public rather than private **deliberately**: law 5 says an admin does not see private boards they
aren't a member of, so a private per-teacher board would be one the admin could fire tasks into
and then never track (`actions.py:53-58`).

### The four things wrong with it *(all verified — see `modules/tasks.md` §4)*

1. **It is a ledger, not a list.** `board_table` (`task.py:267-271`) returns every non-cancelled
   instance ever, no window, no limit, oldest first. ~450 rows by day 90 — the founder's own
   worry, and the **open** rows are the worse half: a *"Call Kabir Shah's parent"* from March
   sitting above today's work is what makes a teacher stop reading the board, and once she does,
   the admin's whole loop is dead. → **`D-44`** (window the read, don't archive) + **`D-45`** (a
   **Stale** group with *close* / *re-date*, never auto-close).
2. **The admin's own Today tab shows them none of it.** `/tasks` re-filters board rows on the
   client to "mine or unassigned" (`page.tsx:156`), throwing away the server's correct answer. The
   admin has to know to come to `/boards/[id]` instead. → **`D-48`**.
3. **Every row is due at 05:30.** The rail defaults `due_at` to midnight **UTC**
   (`actions.py:231`), so a Monday follow-up is overdue before Tuesday assembly. → **`D-48`**.
4. **Three days of absence make three identical rows.** The rail dedupes per calendar day
   (`actions.py:92`) — right for *"don't message this parent twice"*, wrong for a task that is
   still open. → **`D-47`**.

**This board carries more weight after `D-43`.** My Day now shows the teacher a 3-day window; a
follow-up older than that is only here and on her `/tasks`. So `D-45`'s Stale group is not
housekeeping — it is the **only** mechanism that stops a dropped follow-up staying dropped.

### Actions — two

- **Close it, with what happened** (`D-46`) → *"Spoke to the father — fever, back Monday"*. The
  task knowing its subject is what gives the outcome somewhere to go; without it the row keeps
  re-asking (ux-principles §8).
- **Re-date or drop a stale row** (`D-45`) → the only two honest answers to a three-week-old
  follow-up. **Never a third one that closes it automatically.**

### States

| State | What the admin sees |
|---|---|
| Empty (new school) | *"Follow-ups you assign from the dashboard land here."* The board exists before the first task — it is created lazily on first use, so until then this is a promise, not a bug. |
| Nothing stale | No Stale group at all. A clean board should look clean. |
| 400 done rows | They aren't shown. Last 7 days, then a date filter (`D-44`) — and **the filter ships with the window, never after it**. |
| Same student absent 4 days running | **One** row, its due date moved (`D-47`) — not four. |

### Deliberately not here
A per-teacher completion league table (`D-25`'s fence) · auto-closing anything (`D-45`) · a
second board per source module — `category` carries the source if we ever want to group by it.

## `Exams` — `/dashboard/exams` · **CHANGING**
**Status:** CHANGING · **Refs:** `D-49` `S-113` `S-114` `S-115` `Q-50`

**Arrives asking:** *"Which class and which subject need attention?"*
**Leaves having:** picked the one class-subject worth a conversation this week.

### What's on it *(verified)*
Recent exams with `avg_pct` + `scored/roster`, by-class and by-subject roll-ups, per-subject
trajectories, and a five-bucket score distribution — **bucketed in Postgres**, so a 40-exam year
returns five rows rather than forty thousand (`insights/exams.py:184`). **Participation sits beside
every average** and that is the module's stated honesty rule.

### Session 6 — the headline number is currently a fact about nothing

🔴 **Every kind of test pools into one average.** `board` computes `tot_s / tot_x` across all
cycles, and `by_subject` pools raw marks the same way (`insights/exams.py:126-164`). A 5-mark slip
test and an 80-mark term exam are added into one fraction. A `type_filter` exists — and **defaults
to none**, so the first number the admin reads is the blended one. *"Maths is at 61%"* is then the
mean of an April diagnostic, twelve slip tests and one final.

**`S-114` fixes it with one field, not with weights:** `scale` = `minor` | `major`. **Trajectory is
drawn from minor** (frequent tests are what show movement); **standing is read from major**; the
two are **never added**. Weighted composites are the report-card designer SPRD2 §11 fences — every
school wants different weights and the result is checkable against nothing.

**`S-115`** links a recorded exam to its planned exam block, so this tab and
`/dashboard/syllabus` can finally be asked one question together: *"we covered 70% of the Term-1
portion — what did it cost?"* Today `assessment_cycles` has no `exam_event_id` and the two modules
cannot meet.

**`S-113`** lets the type filter offer the school's own words — *CET*, *pre-board* — instead of
nine fixed ones.

### States
| State | What the admin sees |
|---|---|
| No exams yet | *"Exams appear here as teachers record them."* Never a 0% school. |
| Exam recorded, half the class marked | The average **with `9/42` beside it**, always. Already correct. |
| One exam in a subject | No trajectory — *"a single point is not a trajectory"* is already the rule (`exams.py:169`). |

### Deliberately not here
A composite/final grade · a student ranking · any band or tier (P4 — `band_test` cycles count as
**marks**, and no tier is returned anywhere in this module) · teacher league tables.

---

## `Approve this date` — sheet, from the overview card **and `What's coming`** · **NEW**

**Status:** NEW · **Refs:** `D-57` `D-58` `D-59` `S-142` `S-143` `S-148` `S-150` `Q-65`

**Arrives asking:** *"Are we closing for this — and what does it cost me?"*
**Leaves having:** locked the date into the school's calendar at one of three levels, or dismissed
it for good.

**Context:** seconds, from a suggestion row. Often mid-morning, often after a phone call from the
management. This is the **single most consequential sheet in the module** — it is the only place a
teaching day can be created or destroyed.

### What's on it, in order

1. **Headline** — *"Independence Day · Fri 15 Aug"*, with **where the suggestion came from**
   underneath: *"Suggested · Telangana state holiday list"* (`S-150`). An unattributed date is one
   the admin either approves blindly or ignores.
2. **The three levels** (`D-58`) — one choice, radio not checkbox:
   - **School closed** — the whole day
   - **Some periods only** — a period picker; teaching resumes after
   - **Runs as usual** — celebration at assembly / prayer time, nothing lost
3. **🔴 The cost, before they commit** (`S-143`) — recomputed as they change the level:
   *"Removes 8 periods. 6-B Maths and 9-A Science move green → amber. 14 class-subjects
   unaffected."* Without this block a principal locks three days for Diwali and watches six
   subjects turn amber with no idea why.
4. **Note** — optional, free text, goes on the calendar row.

### Actions

- **Approve** → writes the `calendar_events` row with `affects_teaching` / `blocks_periods` set
  from the level (`S-142`), plus an append-only decision row. The date is now the school's.
- **Dismiss** → append-only and **permanent** (`S-148`). *"We don't observe this"* must survive
  the year and the next one, or the admin learns to ignore the whole feed.

### States

| State | What the admin sees |
|---|---|
| Runs as usual selected | The cost block reads *"Nothing lost — teaching continues."* **Not a zero, a sentence.** |
| No plan approved yet for this year | The cost block says *"No approved plans yet — nothing to recalculate."* Never a blank panel, never a fake zero. |
| The date is in the past or is today (`Q-65`) | Existing capture for that day is **shown and kept**, never erased. *"Periods 1–2 were taught and recorded; locking 3–8."* |
| Already approved | Reopens showing the current level, and changing it is a **new** decision row, not an edit. |

### Deliberately not here

Rescheduling anybody's syllabus (`D-59` — and the plan-rewriting half is a P2 violation, `S-144`)
· picking which teachers are affected (that is `D-59`'s teacher-side block) · a recurring rule
(*"every second Saturday"*) — that is the academic year's `working_weekdays`, and it already
exists.

### Sketch

```
┌────────────────────────────────────────────────┐
│  Independence Day                Fri 15 Aug    │
│  Suggested · Telangana state holiday list      │
│                                                │
│  ○ School closed — whole day                   │
│  ● Some periods only   [1][2][3]▪▪▪▪▪          │
│  ○ Runs as usual — assembly / prayer only      │
│                                                │
│  ── What this costs ─────────────────────────  │
│  Removes 3 periods.                            │
│  6-B Maths   green → amber                     │
│  9-A Science green → amber                     │
│  14 class-subjects unaffected.                 │
│                                                │
│  Note (optional) [__________________________]  │
│                                                │
│           [ Dismiss ]        [ Approve ]       │
└────────────────────────────────────────────────┘
```

---

## `What's coming` — route TBD · **NEW**

**Status:** NEW · **Refs:** `D-51` `D-52` `S-121`–`S-126` `S-128` `S-134` `Q-54`–`Q-56` `Q-60`

**Arrives asking:** *"What's coming up, and what does it need from me?"*
**Leaves having:** put one date on the school calendar, or handed one thing to somebody as a task.

**Context:** not a daily screen. Opened at the start of a month, or when someone asks *"what are
we doing for Independence Day?"* — desktop, unhurried. Everything urgent already reached them on
the overview card.

> **`Q-60` first.** Plan → Year is already a year calendar. This screen earns its existence only
> if it is an **agenda** — dates in order, each with what it needs — rather than a second grid
> (`S-134`). Written below as an agenda.

### What's on it, in order

1. **Headline** — *"Three dates in the next month need something: Independence Day (rehearsal),
   Annual Day (parent notice), and 14 birthdays."*
2. **This week** — day-grouped rows. Each row: the date, what it is, where it came from
   (*school calendar* / *observance* / *birthday*), and its one action.
3. **This month** — same shape, folded to major only (`S-125`); a *Show minor observances* toggle
   underneath, never on by default.
4. **Birthdays this month** — grouped by class, so a class teacher can be handed the list.
   Day-and-month only, never an age (`S-133`).
5. **More** — the full observance catalogue for the year, with each school's promote/hide.

### Actions

- **Add to school calendar** → opens the event sheet, date prefilled, **open/closed forced**. The
  only teaching-day path in the module (`S-122`).
- **Add as task** → the preparation becomes a task on a board, assigned to a person, with a due
  date. This is the whole answer to *"event planning"* (§7 of the module) — we don't build a
  second work tracker, we hand it to the one that exists.

### States

| State | What the admin sees |
|---|---|
| Empty (new school) | *"Your school's dates will appear here once the year calendar is set up. Birthdays appear once the roster has dates of birth."* — with both links. Never a blank month. |
| DOB missing for most students | The birthdays section renders the coverage sentence with its denominator, not zero birthdays (`S-124`, ux §5). |
| Nothing coming up | *"Nothing in the next three weeks."* — a quiet month is a fact, not an empty screen. |
| An observance the school doesn't observe | It is a **row**, not a warning, and *Hide* is one tap. A school in Kerala should not be told about a festival it doesn't keep (`Q-55`). |

### Deliberately not here

Event budgets, committees or checklists — that is Tasks · a photo gallery of the annual day
(social module, fenced) · RSVP or invitations · a holiday-policy engine — the school declares its
own holidays and we never infer them · **anything that writes to the calendar without a press**
(`S-122`).

### Sketch

```
What's coming                                        [ This week | Month ]

Three dates in the next month need something.

TODAY · Thu 1 Aug
  🎂  Aarav Sharma (6-B), Diya Nair (9-A)                  [ Wish ]
  🪔  Guru Purnima — observance · school open              [ Add to calendar ]

THIS WEEK
  Fri 8   Raksha Bandhan — observance                      [ Add to calendar ]
  Mon 11  Priya Menon (teacher) — birthday                 [ Wish ]

COMING UP · lead time started
  Fri 15  Independence Day — school calendar · closed      [ Add as task ]
          flag hoisting, rehearsal from the 11th
  Sat 30  Annual Day — school calendar                     [ Add as task ]
          parent notice not sent

                                      ▸ Show minor observances (6)
```

---

# Staff area

## `Staff attendance` — `/staff`
**Status:** CHANGING · **Refs:** `D-04` `S-18` `S-34`
**Arrives asking:** *"Who came in today?"* · **Leaves having:** marked the day.

Everyone opens ticked present; untick who's away; save. Full replace, so reopening and
correcting needs no undo path. Approved leave pre-unticks and says why.

**Session 1 changes:** adds **half-day (AM/PM)** and **late** (`D-04`). Stays exception-only —
present is still derived, and there is still no per-person row for the people who came in.

⚠️ Once this feeds payroll, an unmarked day must never silently read as "absent, unpaid"
(`S-34`). The display rule becomes a financial rule.

## `Leave` — `/staff/leave`
**Status:** CHANGING · **Refs:** `D-04` `D-27` `Q-15` `S-32` `S-80` `S-81` `S-82`
**Arrives asking:** *"Who's asked for leave, and can I say yes?"*
**Leaves having:** decided — **and, now, arranged the cover** (`D-27`).

Append-only history timeline; over-policy applications are **flagged, not blocked** — the admin
decides. *(A validator that refuses an emergency is one staff route around by phone.)*
**Gains half-day** with AM/PM.

### Session 3 change — approval hands back the cover flow (`D-27`)

Approving is currently the end of the interaction. It should be the middle of it: the approval is
the exact moment the school learns that five periods on Friday have nobody in them, and it is the
only moment when there is time to do something about it calmly.

- **Approve → "Arrange cover for 3 days"**, opening the same sheet per day (`S-80`).
- The uncovered periods land on the **action rail dated to that day** (`S-81`), so nothing depends
  on the admin remembering to come back here.
- 🔴 **The candidate list must exclude people on approved leave that day** (`S-82`) — it does not
  today, and for a future date there is no staff-absence row to catch it.

Half-day matters here for the same reason it matters everywhere (`Q-15`): *which* half decides
which periods need covering.

## `Today` — `/staff/today`
**Status:** CHANGING · **Refs:** `D-21` `S-72` `S-61`
**Arrives asking:** *"Who is free right now?"* · **Leaves having:** picked someone.

The teacher × period grid of `D-21`, and it exists. One row per staff member, one column per
period, cell = subject / work label / `—`. One payload, three queries regardless of headcount.

> 🔴 **It is wrong today, on the one question it exists to answer.** *(verified)* It renders
> `TimesheetService.org_day`, which reads the timetable and the timesheet and **nothing else** —
> no staff absence, no substitutions. So a teacher who is **away today shows eight free periods**,
> and a teacher already covering three of someone else's shows free in all three. The two worst
> candidates sort to the top of the admin's list. `/dashboard/staff` computes the same grid
> correctly from `WorkloadInsights`, which knows about both.
>
> **Third instance of *one fact, several computations*** (three definitions of "absent for a day";
> two of "syllabus covered"). Fix by deleting one of them — `S-72`.

Also: the tiles count every active membership, so the principal's and the clerk's eight free
periods are in the school's "free periods" total. `WorkloadInsights` already excludes non-teachers
from the *mean* and from nothing else.

Reads the new half-day/late states (`D-04`), and the *free* / *not told us* split (`S-61`).

## `Salary` — `/staff/salary` · **NEW**
**Refs:** `D-05` `D-06` `S-15` `S-16` `S-17` `S-38` · **Blocked on** `Q-05` `Q-06` `Q-07` `Q-08`

**Arrives asking:** *"What do I owe each person this month?"*
**Leaves having:** a figure per person they trust enough to pay from.

**Context:** month-end, desktop, alone. The most sensitive screen in the product.

### What's on it
1. **Headline** — *"July · 14 staff · ₹4,12,000 estimated"* — and the word **estimated** is not
   decoration (`S-15`).
2. **Month selector**
3. **One row per staff member** — days present, leave used vs balance, unapproved absence,
   estimated amount
4. **A row opens into the line-by-line calculation** (`S-16`) — base, working days, present,
   leave within balance, deductions, total. *why: any figure the person being paid cannot
   reconstruct becomes a dispute that lands on the admin.*

### Deliberately not here
Payslips, statutory deductions, bank files — unless `Q-05` says otherwise, this is an estimate a
human pays from, not a payment system.

### Fenced
Behind its own capability, not plain `require_admin` (`Q-06`). Excluded from Lucy, the daily
report and every widget (`S-17`). Not on the overview (`S-38`).

---

# Fees

Admin only, always (`D-63`). Three screens exist; **one changes**, and it is the weak one.

## `Fees` — `/fees` · **CHANGING — becomes the collection board**

**Status:** CHANGING · **Refs:** `D-62` `D-64` `D-65` `S-152`–`S-163` `Q-66`–`Q-68`

**Arrives asking:** *"How much of this quarter is in, and who do I chase?"*
**Leaves having:** picked a class to push this week, and started 3–6 calls — either by reminding
the parents themselves or by handing the families to a class teacher.

**Context:** the week an instalment falls due, and the first week of a quarter. Desktop, a few
minutes, usually with the correspondent or the accountant beside them. This is a **money screen
looked at by the person who answers for the money**, so every figure has to survive being read
aloud in a trustee meeting.

> **Why here and not `/dashboard/fees` (`S-152`):** `/fees` already exists and its landing page is
> the weakest screen in the product — four bare tiles over a list. The founder's "section in the
> dashboard" **replaces that landing page**. A ninth dashboard tab would give the school two fee
> screens that disagree, which is the `S-134` trap in a different module.

### What's on it, in order

1. **Headline — a sentence** (ux §2). *"Q2 is 62% collected — ₹6.1L behind where Q1 stood in its
   fifth week. 14 families are overdue."* Never *"₹42,10,000"* as the first thing on the screen.
2. **The collection curve** (`S-155`) — cumulative collected across the quarter's days, with the
   **previous quarter as a reference line**. This is the block that answers *on track or behind*,
   and it answers it in one glance because it is a shape, not a number (ux §15). Same device
   `class-analytics` already uses for its first-test reference line, drawn with
   `components/charts` — **no second charting path**.
3. **The quarter strip** — one row per quarter of the year, current one expanded:

   `Q1 ▓▓▓▓▓▓▓▓▓░ 94%` · `Q2 ▓▓▓▓▓▓░░░░ 62%` · `Q3 — not due` · `Q4 — not due`

   A quarter that has not fallen due is **"not due"**, a word, never 0% and never red (ux §5,
   §10). Three states per quarter, never merged into one "outstanding" figure (`S-163`):
   **collected · pending (due later) · overdue (due, unpaid)**.
4. **By class** (`S-159`) — the table that decides *what to do this week*. Every row carries
   **both denominators**, because ₹1.4L is one big defaulter or fourteen small ones and those need
   opposite actions:

   *"8-B — 14 of 38 families pending · ₹1.4L overdue"*

   Sortable by **families**, not just rupees — a morning of phone calls is denominated in calls.
5. **Who hasn't paid** (`D-64`) — the named list, oldest due first. **This is `overdue_students`,
   which has existed on the server since P0-D and has never once been called by the web app**
   (module §4 defect 1). Each row: student, class, **the guardian to ring and their number**
   (`S-157` — the person who owes is the person you call), amount, how long overdue, and whether
   anyone has already been in touch today (`S-156`).
6. **More** — the existing enrolment list, search, status filter, and the link to
   `/fees/structures`. Nobody arrives for these; they are the second visit.

### Actions

Two, on the row (ux §6, §7):

- **Remind** → sends the parent notification (`D-66`), records a `followup_actions` row, and the
  row immediately re-renders as *"reminded 9:12am · you"*. Throttled, quiet-hours-bound, and it
  **stops the moment the payment lands** (`S-156`).
- **Assign follow-up** → creates a task on the **Follow-ups** board for the class teacher.
  🔴 **What that task may say is `Q-66`** — `S-154` recommends the family and the subject, **never
  the amount**.

Everything else on this screen is a link to where the work actually lives — `/fees/[id]` for
taking a payment, `/fees/structures` for the schedule.

### States

| State | What the admin sees |
|---|---|
| Empty (no structures yet) | *"Set up a fee structure to start tracking collection."* → `/fees/structures`. Never a screen of ₹0 tiles. |
| Structures set, nobody enrolled | *"No students are enrolled in a fee structure yet — 0 of 486."* With its denominator (ux §4). |
| Quarter not yet due | The strip says **"not due"** and the curve has not started. **Not 0%, not red** — this is the single easiest place in the module to invent a crisis that doesn't exist. |
| Everything collected | *"Q2 is fully collected. Nothing outstanding."* A good quarter should feel like one, not like an empty screen. |
| A student on 100% concession | **Never appears** in the defaulter list or the class counts (`S-158`). Filter on amount owed, never on enrolment. |
| Arrears carried from last year | 🔴 Today: **invisible everywhere** — excluded from `total_fee`, `collected`, `overdue_amount` and from `status`, so a student owing ₹20,000 from last year reads `paid` (module §4 defect 2). What this screen shows depends on `Q-68`. |

### Deliberately not here

Taking a payment — that is `/fees/[id]`, and it is the good screen (`D-62`) · a transaction ledger
· the fee structure editor · **any teacher-visible surface whatsoever** (`D-63`) · a per-child fee
chip that could travel to an academic screen (`S-157`) · automatic dunning (every reminder is a
human press).

### Sketch

```
┌───────────────────────────────────────────────────────────────────────┐
│  Fees                                              Year 2026-27  ▾    │
│                                                                       │
│  Q2 is 62% collected — ₹6.1L behind where Q1 stood in its 5th week.   │
│  14 families are overdue.                                             │
│                                                                       │
│  ┌─ Collection · Q2 ──────────────────────────────────────────────┐   │
│  │  ₹                                          ·············· Q1  │   │
│  │                                    ______────                  │   │
│  │                      _____────────                             │   │
│  │        ____─────────                                           │   │
│  │  ──────                                                        │   │
│  │  Jul 1                                                Sep 30   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Q1 ▓▓▓▓▓▓▓▓▓░ 94%   Q2 ▓▓▓▓▓▓░░░░ 62%   Q3 not due   Q4 not due     │
│     collected ₹42.1L  ·  pending ₹19.4L  ·  overdue ₹6.1L            │
│                                                                       │
│  ── By class ──────────────────────────  [ families ▾ | rupees ]     │
│   8-B    14 of 38 families pending      ₹1.4L overdue                │
│   9-A     9 of 41                       ₹0.9L                        │
│   6-C     6 of 36                       ₹0.6L                        │
│   … 11 more                                                          │
│                                                                       │
│  ── Who hasn't paid ─────────────────────────  oldest first          │
│   Kabir Shah      8-B   father Ramesh · 98xxx   ₹12,000   41 days    │
│                                          [ Remind ] [ Assign ]        │
│   Aarti Rao       9-A   mother Sunita · 97xxx   ₹ 8,500   28 days    │
│                                     reminded 9:12am · Priya           │
│   …                                                                   │
│                                                       ▸ More          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## `Overview` fees block — `/dashboard` · **CHANGING**

**Status:** CHANGING · **Refs:** `D-64` `S-152` `S-155`

*(verified)* Today the overview carries a fees block, admin-only and client-side, computed off
`DashboardService` — teachers never receive the figures at all, which is correct and stays.

**What changes:** it becomes a sentence with two figures and a link, in the `OverviewSection`
shape every other module block already uses — **not a second collection board**.

```
💰  Fees · Q2 is 62% collected, ₹6.1L overdue
    14 families overdue · 8-B has the most (14 of 38)      [ Open fees → ]
```

The action rail may carry **one** fee row when something is genuinely waiting — *"14 families
overdue, none reminded this week"* — and it links to `/fees`. It never carries a per-family row;
that list belongs on the board.

### Deliberately not here
The curve, the class table, the named list. The overview says **whether** to go and look; `/fees`
is where you look (`S-152`).

---

## `Student fee` — `/fees/[id]` · **EXISTS, unchanged**

**Status:** EXISTS · **Refs:** `D-62`

The counter screen — instalments, pay / mark-paid / undo, discount, and the append-only ledger.
**Explicitly out of scope.** It is the part of the module that already works, it is where a payment
is actually taken, and the founder's own framing was *"we already have a perfect fee collection
system"*. Recorded here so no session redesigns it by accident.

The one thing it should gain, and only if `Q-68` says arrears count: `opening_dues` rendered
somewhere a human reads it, since it is already on `StudentFeeDetail` and is the number the
summary is missing.


---

# Setup

## `Academics` — `/setup`
**Status:** CHANGING · **Refs:** `D-03` `D-28` `S-20` `S-77`
Years, classes, subjects, class-subjects, teacher load.

**+ Class teacher assignment.** *(verified)* The API has accepted `class_teacher_member_id`
since P0-C and no UI has ever set it — so it is null in every school and the admin's absence
list has always said "class teacher: —". A select on the class row fixes four existing screens.

**+ The by-teacher view becomes writable** (`D-28`, `S-77`). *(verified)* Assignments already has
two lenses over `class_subjects`: **by class** (editable — a teacher `<select>` per subject row)
and **by teacher** (`ByTeacherView` — that teacher's classes, subjects, periods/week, a
class-teacher badge, and an *"N subjects have no teacher"* warning). The by-teacher lens is
**read-only**, and its own empty state says *"assign subjects from the class view."*

So the founder's *"teacher 1 → classes 3, 4, 5 Hindi"* screen is that view with save on it: pick
the teacher, tick the class-subjects, save many at once, instead of opening five classes and
setting five dropdowns. `PATCH /academics/class-subjects/{id}` already accepts the field.

Two things to fix while it is open: it fires **one query per class**, which should be batched
before it becomes an editor; and the periods/week badge already turns red past 48 — that is the
beginning of a real load validator and should be stated as one rather than left as a colour.

> This screen is what makes substitution work. Every suggestion in the cover sheet is derived from
> `class_subjects.teacher_member_id`, so a school that skipped half of it gets a cover list that
> cannot tell who teaches Hindi.

## `Settings` — `/setup/settings`
**Status:** CHANGING · **Refs:** `D-01` `D-05` `D-19` `Q-04` `S-69`
Today: band thresholds, parent portal toggle, leaves per year/month, report hour.
**Adds:** attendance mode (`D-01`) · minimum-attendance threshold (`Q-04`) · payroll policy —
grace period, monthly application cap, what deducts pay (`Q-08`) · **work categories** (`D-19`):
enable, disable, rename and add the school's own.

> On the categories (`S-69`): **stable key, mutable label** — renaming "Event work" must not
> orphan last term's rows; **retire, never delete**, so history keeps rendering; **keep the list
> to ~10** — a long picker makes a teacher think, and a teacher who thinks about a dropdown stops
> filling it in; and show the admin the **top free-text values people typed into *Other***, which
> is the school telling you what its real ninth category is.

> This screen is quietly becoming the most consequential in the product — one dropdown here
> changes what every teacher is asked for every period. Worth its own brainstorm: settings that
> reshape behaviour should preview what they will do before they are saved.

## `Members` — `/setup/members`
**Status:** CHANGING · **Refs:** `Q-06` `Q-07`
Add/remove members, set role. **May gain** the salary amount per member and the payroll-view
capability — both pending their questions.

---

## `Plan → Year` — `/plan` · **CHANGING (live defect)**
**Status:** CHANGING · **Refs:** `D-52` `S-122` — *session 7*

The year calendar: four brushes — Exam · Holiday · **Celebration** · Event — painted onto a grid
(`plan/page.tsx:43-48`).

> 🔴 **Verified defect, and it is live today.** `CalendarEventCreate.affects_teaching` defaults to
> `True` (`schemas/calendar.py:17`) and **the paint UI never sends the field**
> (`plan/page.tsx:82-90`). So painting *"Celebration — Guru Purnima"* on a day the school is
> **open** silently removes a teaching day from every class-subject forecast in the school. There
> is no way on this screen to say *"this is on the 9th and we are open."*
>
> **Fix before the events module ships anything**, because the module's whole purpose is to give
> schools a reason to record more dates. One control on the paint bar: **school open / closed**.

---

## `Bands` — `/students/bands` · **CHANGING — becomes the programme board**
**Status:** CHANGING · **Refs:** `D-67` `D-68` `D-71` `D-73` `D-75` `D-77` `S-169` `S-170` `S-173`
`S-188` — *session 9, both passes*

**Arrives asking:** *"Is this programme working?"*
**Leaves having:** found the children nobody has moved, and either given one an owner or asked for
a check-in.

**Context:** Monday morning, desktop, and again at term end. Minutes.

> *(verified)* Today this screen is **three columns of names and a count**
> (`students/bands/page.tsx:73-112`). It can answer *how many are in C* and nothing else — not who
> moved, not who owns them, not who has been C since April. `D-67` makes movement the headline;
> the distribution goes under **More** (`S-169`).

### What's on it, in order

1. **Headline** — movement, as a sentence: *"11 children moved up this term, 3 slipped. 4 have been
   Band C since April with no movement."*
2. **Stuck** — the four, **named**, with **the subject**, the owner, and how long since the last
   check-in (ux §3) and the action on the row (ux §7). *The subject is not optional:* under `D-77`
   a child can have two owners, and *"Kabir Shah — owner Priya"* lets each of them assume the other
   is on it (`S-188`).
3. **By class and subject** — the founder's *"for each class and the subject"* (`D-73`), one grid,
   `↑` moved to B and `↓` slipped beside the C count.
4. **Not assessed yet** — class-subjects with no band test this term · *why: ux §5 — a class nobody
   assessed is a gap in the record, a **word**, never a zero and never red.*
5. **More** — the A/B/C distribution, band-test history, the descriptors, who owns whom.

```
Bands · support programme                     Term 2 · English, Hindi, Maths

  11 children moved up this term, 3 slipped.
  4 have been Band C since April with no movement.            [ see the 4 ]

  ┌ Stuck ───────────────────────────────────────────────────┐
  │ Kabir Shah   6-B  English  C since 12 Apr · owner Priya   │
  │                   last check-in 3 weeks ago               │
  │                   [ reassign ]   [ ask for a check-in ]   │
  │ Meera Das    7-A  Maths    C since 12 Apr · no owner   🔴 │
  │                   [ assign a teacher ]                    │
  └──────────────────────────────────────────────────────────┘

  ┌ By class and subject ────────────────────────────────────┐
  │            English          Hindi           Maths         │
  │   6-A    4C  ↑2 ↓0       2C  ↑1 ↓0       7C  ↑0 ↓1       │
  │   6-B    6C  ↑3 ↓1       3C  ↑0 ↓0       5C  ↑2 ↓0       │
  │   7-A    9C  ↑0 ↓0 🔴    4C  ↑1 ↓0       6C  ↑1 ↓1       │
  │          ↑ moved to B this term   ↓ slipped               │
  └──────────────────────────────────────────────────────────┘

  ┌ Not assessed yet ────────────────────────────────────────┐
  │ 8-A Hindi (34 children) — no band test recorded this term │
  └──────────────────────────────────────────────────────────┘

  More ▸   distribution · band tests · descriptors · who owns whom
```

### Actions — two
- **Assign / reassign an owner** → the child gets a name against him and appears on that teacher's
  `/support` page the same afternoon.
- **Ask for a check-in** → a follow-up on the owner, through `followup_actions`, which already
  remembers it fired so the same teacher isn't chased twice in a week (ux §7).

### States
| State | What the admin sees |
|---|---|
| Empty (new school) | *"Nobody has been banded yet. Start with a band test, or assess a class against the descriptors."* — with both routes as buttons (`D-70`). |
| Bands set, no programme yet | *"38 children are in Band C and none has an owner."* The single most useful sentence this screen can say in week one. |
| Nothing stuck | *"Every C child has an owner and a check-in in the last fortnight."* |
| A subject not monitored | Absent from the grid entirely — not an empty column (`D-68`). |

### Deliberately not here
**Any ranking of teachers by children moved** (`S-170`) · individual marks (the exams module owns
those) · a child's name on any surface a parent can reach (P4) · the distribution as the headline.

## `Assess a class` — `/students/bands/[classId]` · **CHANGING**
**Status:** CHANGING · **Refs:** `D-68` `D-69` `D-70` `D-75` `D-76` `S-166` `S-171` `S-185` `Q-79`
— *session 9, both passes*

**Arrives asking:** *"Which band is each child in, for this subject?"*
**Leaves having:** filed a whole class into A/B/C for one subject, with the source on every row.

**Context:** twice a year, sitting down, 20 minutes for a class. Admin, or the subject teacher.

> **This is the one screen in the product that legitimately touches every child in a class**, and
> it does not break P1v2 — the budget rule is about *daily* capture. It still defaults: the test's
> marks pre-fill every row and she only **moves the ones she disagrees with** (`Q-79`). Assessment
> by hand, with nothing pre-filled, is the `D-70` fallback for a school with no test yet.
>
> **This screen is for ENTRY only.** `S-185`: *entry may be judgement; movement is a test.* Once a
> class is filed, a child changes band on a **band test or a promoted test** (`D-76`) — which is a
> teacher's action on the exam screen, not an admin's slider here. That split is what makes every
> subsequent band row evidenced without anyone having to remember to attach evidence.

```
Assess 6-B · English                                              Term 2

  ( ) From a test        (•) My own assessment

  Band test — "Term 2 English Diagnostic", 12 Aug              [ change ]
  Suggested from marks:  A ≥ 75%   B ≥ 50%           [ what B means ▾ ]

   Aarav Shah        82%    A  ────●────
   Diya Nair         61%    B  ───●─────     ← you moved this from A
   Kabir Shah        34%    C  ─●───────
   Ishaan Rao         —     ?  not assessed  (absent for the test)

                A: 9    B: 18    C: 7    not assessed: 2
                                                   [ File these bands ]
```

The descriptor opens **beside the slider**, not in a help menu — *"B — reads a grade-level passage
aloud with ≤ 3 errors; writes four sentences unaided"* (`S-166`, `D-69`). It is the only way two
teachers band the same child the same way.

### Actions — two
- **File these bands** → append rows (law 3), each carrying its source: *"band test: Term 2
  Diagnostic"* or *"teacher assessment: Priya"* (`D-70`).
- **Assign owners for the C children** → offered **immediately after filing**, because that is the
  moment the C list exists and the only moment anyone is thinking about it (`D-71`). *(verified)*
  Today the equivalent step assigns tasks to `school_classes.class_teacher_member_id`, which **no
  screen sets**, so every intervention in every real school is created unassigned (module §4.3).

### States
| State | What she sees |
|---|---|
| No test recorded | The **My own assessment** route: descriptors, everyone unassessed, nothing pre-filled. |
| Absent for the test | **not assessed** — a word, never C, never a zero (ux §5). |
| Subject not monitored | The class picker doesn't offer it (`D-68`). |
| Already filed this term | The current bands, with *"filed 12 Aug from Term 2 Diagnostic"* — and re-filing appends, it never overwrites. |

### Deliberately not here
A class total or rank · other subjects' bands as columns · marks entry — this screen **reads** a
test the exams module captured (`S-171`); it never becomes a second place to type marks.

## `Band setup` — `/setup/settings` → Bands · **NEW**
**Status:** NEW · **Refs:** `D-68` `D-69` `D-74` `S-175` `Q-76` — *session 9*

**Arrives asking:** *"What does Band B mean in my school, and what are we monitoring?"*
**Leaves having:** turned on three subjects and read (rarely edited) nine descriptors.

```
Setup → Bands

  Monitored subjects   [✓] English   [✓] Hindi   [✓] Maths
                       [ ] Science   [ ] Social Studies
                       A subject that isn't monitored has no bands and no support
                       programme. Nothing else about it changes.

  ENGLISH                                        [ per-grade overrides ▸ ]
   Band A   from 75%   "Reads unfamiliar text fluently; writes a short
                        paragraph unaided."                        [ edit ]
   Band B   from 50%   "Reads a grade-level passage aloud with ≤3 errors;
                        writes four sentences unaided."            [ edit ]
   Band C   below      "Decodes three-letter words; copies but does not
                        compose."                                  [ edit ]
   Re-assess with      [ Band test ▾ ]  every [ term ▾ ]
   Check-in cadence    [ weekly ▾ ]

  HINDI …     MATHS …
```

> *(verified)* Today the thresholds are **two numbers for the entire school** —
> `organizations.band_a_min` / `band_b_min` (`assessments.py:269-280`) — so English and Maths are
> assumed to be measured on the same scale. `D-74` makes the rule per subject; `S-175` says ship
> the nine descriptors **pre-written and editable**, because 27 empty boxes get filled in by nobody
> and 72 (with grades) by no one at all.

### Deliberately not here
Per-child anything · the owner assignments (they belong where the C list is) · a global threshold
that pretends every subject grades alike.

---

# Not yet brainstormed

`Lucy` `/lucy` · `Plan` `/plan` (Syllabus · Week · Timetable · Hostel — Year has an entry above)
· `Students` `/students` (Directory · Scores · Trends · profile — **Bands has entries above**) ·
`Tasks` `/tasks` · `Schools` `/platform` (super-admin only).

Stubs on purpose — each gets a full entry when its module comes up.
