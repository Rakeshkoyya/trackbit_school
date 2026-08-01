# Module — Tasks

The one place work that isn't a class gets written down and handed to a person. Everything else in
the product captures what *happened*; this captures what somebody has been **asked to do**.

**Sessions:** 5 (2026-07-31)
**Related:** [`teacher-load.md`](teacher-load.md) · [`homework.md`](homework.md) ·
[`attendance.md`](attendance.md) · [`class-teacher.md`](class-teacher.md)

> This session did **not** redesign the task module. It is the most complete module in the product
> and its internals are settled. The session covered exactly two things: **where an
> admin-assigned task lands and who can see it**, and **how a teacher meets it inside My Day**.

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Admin** | 8:40am, reading the overview, sees a red row | desktop, seconds | *"Who do I hand this to?"* |
| **Admin** | 4pm, or Friday | desktop, minutes | *"Did the things I asked for get done?"* |
| **Teacher** | 9:02, between classes, My Day open | phone, **seconds** | *"What's next, and what haven't I recorded?"* |
| **Teacher** | 4pm, desk | phone or laptop | *"What am I still carrying?"* |
| **Class teacher** | when a follow-up is about one of her students | phone | *"What am I supposed to do about Kabir?"* |

The admin's two moments are one loop: **press a button on a red row → find out later whether it
worked.** Everything in this module either serves that loop or serves the teacher's ability to see
what landed on her without leaving the screen she already lives in.

## 2 · What they must be able to decide

- **Admin, on a red row:** who this belongs to, and hand it over in one press without leaving the
  board.
- **Admin, later:** whether it was done, by whom, and what actually happened — *not* just whether
  a checkbox was ticked.
- **Teacher, at 9:02:** whether anything has been asked of her that changes what she does next.
- **Teacher, at 4pm:** what is still open, what is late, and what she can close now.

## 3 · Where it stands today *(verified)*

**The board the founder described already exists, with the exact semantics described.**

| Thing | Where | State |
|---|---|---|
| The board | `services/insights/actions.py:48` — `FOLLOWUPS_BOARD_NAME = "Follow-ups"`, created lazily by `ensure_followups_board` and shipped in the seed | ✅ built |
| "Only their own tasks" | `boards.task_scope = 'assigned'` (`models/board.py:31`) | ✅ built |
| "Admin sees all" | `core/visibility.py:67` `can_view_all_tasks` — `is_admin or board.owner_id == user_id` | ✅ built |
| Row-level enforcement | `services/task.py:265,275` — `board_table` adds `assignee_id == member.user_id` when `not sees_all` | ✅ built, server-side |
| Public, not private | deliberate: law 5 says admins do **not** see private boards they aren't in, so a private per-teacher board would be one the admin could fire into and never track (`actions.py:53-58`) | ✅ and the reasoning is written down |
| Teacher is told | `services/task.py:491` `enqueue_instant(notif_type="assigned")` on every assignment to someone else | ✅ built |
| Claiming is off there | `services/task.py:536` — a privacy board has no open claim pool | ✅ correct |
| Reassign is owner/admin only | `services/task.py:575` | ✅ correct |
| Admin's "did it get done" | `/dashboard/tasks` → `services/insights/tasks.py` — open/overdue/completed, **by assignee**, red rows by name, with *Reassign · Extend · Nudge* on each | ✅ built |
| Every press is logged | `followup_actions`, append-only (`models/insights.py:106`) | ✅ built |

**And one thing that is built and simply not wired to the screen that needs it:**

`HomeService.my_tasks` (`services/home.py:117`) already returns **every task assigned to the
caller across all boards**, with the board name, sorted overdue → soonest due → undated, including
today's completions so a ticked row can render struck-through. That is, almost line for line, the
list the founder wants on My Day. It is currently rendered only on `/tasks`.

**My Day has no tasks at all** — `MyDayOut` is `{date, classes, periods, homework_pending}`
(`schemas/classroom.py:66`). So the teacher half of this session is genuinely new UI over an
existing computation.

## 4 · What's wrong with it

Five things, all verified. Two are the founder's questions; three nobody had noticed.

### 4.1 The board is a ledger, not a list *(the founder's 90-day worry — and it is worse than stated)*

`TaskService.board_table` (`services/task.py:267-271`) selects **every** non-cancelled one-time
instance on the board — no date window, no limit, ordered by `created_at` — and the client renders
all of them. At five follow-ups a day that is ~450 rows by day 90, oldest first.

But the completed rows are the *easier* half of the problem. A **done** row is at least a true
statement about the past. The rows that actually break the board are the **open** ones nobody ever
closed: a *"Call Kabir Shah's parent"* from March, still open, sitting above today's work. That is
what makes a teacher stop reading the list — and once she stops reading it, the admin's whole
loop is dead. See `S-103` / `S-104`.

### 4.2 The Today screen hides from the admin the tasks the admin assigned

`web/src/app/(app)/tasks/page.tsx:156-157` filters board-tab rows **on the client**:

```ts
rows = (boardTable.data?.rows ?? []).filter((r) => !r.assignee || r.assignee.id === myId)
```

The server already decided this correctly and told the truth (`sees_all`); the client throws it
away. So an admin who opens the Follow-ups tab on `/tasks` sees **none of the tasks they assigned
to teachers** — they have to know to go to `/boards/[id]` instead. This is ux-principles §9 in a
single line: two implementations of one visibility rule, and the second one wins. See `S-111`.

### 4.3 A follow-up is due at 5:30 in the morning

`ActionService._assign_followup` (`services/insights/actions.py:231-232`) defaults the due date to:

```python
due_at=body.due_at or datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
```

Midnight **UTC** — 05:30 IST. `TaskService.create` stores it verbatim with `all_day=False`
(`task.py:471-472`), and overdue is `due_at < now`. So a follow-up the admin assigns on Monday is
**already overdue when the teacher opens My Day on Tuesday**, and the UI shows it with a time
nobody chose. Every other date in this product goes through org-local day bounds. See `S-112`.

### 4.4 The same absence produces a new task every day

The rail's idempotence key is *(kind, subject_id)* **for today only** — `done_today` windows on
`created_at >= start of today` (`actions.py:92-109`). That is exactly right for *"don't message
this parent three times this morning"*, which is what it was built for.

It is wrong for tasks. On day two the same absent student produces a **second** open
*"Call Kabir Shah's parent"* while the first is still open; three days of absence is three
identical rows in one teacher's list. See `S-107`.

### 4.5 The task doesn't know what it's about, so the outcome has nowhere to go

`followup_actions.detail` carries the `task_id` (`actions.py:235`), but the link runs one way
only — the `TaskInstance` is a **title string**. *"Call Kabir Shah's parent"* is not connected to
Kabir Shah.

Three consequences: the teacher can't tap through to the student; the student's timeline never
shows that a follow-up was raised; and when the child walks back in on Wednesday, nothing closes
the task — it just goes stale (4.1). This is ux-principles §8 — *record the outcome, not just the
press.* Today we record only the press. See `S-105`.

## 5 · Ideas and directions

### Decided — `D-40` … `D-48`

- **`D-40`** One shared **Follow-ups** board, `task_scope='assigned'`: a teacher sees only her own
  rows, the admin sees all. *(Already built exactly this way — see §3.)*
- **`D-41`** **My Day gains a tasks section**, below the periods, separated by a rule.
- **`D-42`** ~~Today's + undated + admin-assigned in the main section; future dates under
  *Upcoming*.~~ → **amended by `D-43`** within the session; the surviving clause is *"anything due
  today"*.
- **`D-43`** **The section is a window, not a list**: rail-assigned within **3 days**, ∪ **due
  today**. Everything else is `/tasks`' job. *Upcoming* goes; overdue becomes a state, not a group;
  the section ends with **"4 older tasks →"** so the window is never silent.
- **`D-44`** The board **windows its read** — open always, done for 7 days, older behind a date
  filter that **ships with the window**. No archive, no job.
- **`D-45`** **Stale open rows get their own group**, closed or re-dated by a human. **Never
  auto-closed.**
- **`D-46`** A follow-up **carries its subject**, and completing it records **what happened**.
- **`D-47`** The rail **dedupes on the open task**, not on the calendar day.
- **`D-48`** `S-111` (delete the client-side visibility filter) and `S-112` (org-local end of day)
  are accepted as straight fixes; `S-106` (badge who asked) accepted.

**Every open question this session raised is answered.** The module is closed for design.

### The tension `D-41` has to survive, and why it does

Two sessions ago we took a block **off** this screen and last session we took another one off:

> **`D-24`** *(session 3)* — REJECTED folding the timesheet into My Day: *"the daily capture flow
> is the sharpest, most time-pressured surface in the product, and **nothing else goes in it**."*
>
> **`D-36`** *(session 4)* — the homework block is **removed** from My Day and replaced by a
> button carrying a count.

`D-41` puts a block back. That needs an argument, not a shrug, or in session eight someone deletes
it citing `D-24`.

**The test is where the work happens.** Homework's work is a forty-name check sheet — the My Day
block was a *shortcut to a screen*, so replacing it with a counted button cost nothing and moved a
desk activity to a desk. A task's entire work is **a checkbox on the row**. The row *is* the
destination. Sending a teacher to `/tasks` to tick a box she could have ticked in place adds a
navigation and returns no information.

So `D-41` and `D-36` are the same rule applied to two different things, not a reversal:

> **If the work happens on another screen, put a counted button on My Day.
> If the work is the row, put the row on My Day.**

And `D-24` still holds in the form that mattered: **nothing goes above the periods.** The tasks
section sits below them, out of the 9:02 thumb path, where the 4pm teacher finds it.

*Corollary worth writing down now: if tasks ever grow a body of work — subtasks, attachments, a
required note — the test flips and they become a counted button too.*

### Proposed — `S-103` … `S-112` · **all accepted, most now `D-nn`**

| | → | Note |
|---|---|---|
| `S-103` window the read | **`D-44`** | with the date filter, never without |
| `S-104` stale group | **`D-45`** | never auto-close |
| `S-105` subject + outcome | **`D-46`** | answers `Q-48` |
| `S-106` badge who asked | **`D-48`** | no new data |
| `S-107` dedupe on open | **`D-47`** | |
| `S-108` overdue split | **amended** by `D-43` | survives as a *state*, not a group — there is no backlog on My Day to group |
| `S-109` cap the section | **kept** by `D-43` | a backstop; the window does the work |
| `S-110` all boards | **narrowed** by `D-43` | rule-scoped, not board-scoped; "no board tabs on My Day" survives |
| `S-111` delete the client filter | **`D-48`** | |
| `S-112` org-local due date | **`D-48`** | |

The original text of each follows.


**`S-103` · Don't archive. Window the read.**
The founder asked archive-or-not; the honest answer is neither. `board_table` returns **open rows
always**, plus **done rows from the last 7 days**, with everything older reachable behind a date
filter on the same board. No migration, no nightly job, nothing moved, nothing lost — and it is
the discipline `HomeService.my_tasks` already uses (done = today only, `home.py:128-135`). The
board table is the outlier that never got it.

*Archiving loses this comparison on every axis:* it invents a state that means "old", needs a job
to maintain it, and creates a second place a task can be — so "where is that task" becomes a
question. A window is a rendering decision; an archive is a write.

⚠️ **One thing decides whether this works:** the date filter must exist *before* the window ships.
A window without a way to look further back is data loss from the user's side, and the first time
an admin asks *"what did we follow up on in October"* and can't find it, they stop trusting the
board.

**`S-104` · The stale **open** rows need this more than the done ones.**
Surface them as their own group — *"Stale · 6 items nobody has touched in 3 weeks"* — with exactly
two actions: **close it** or **give it a new date**. **Never auto-close.** A system that quietly
closes *"Call Kabir Shah's parent"* has decided a child's parent didn't need calling, which is not
a decision software gets to make (and would be law-3-hostile: a silent close writes a false
"handled" into the history).

**`S-105` · A follow-up should carry its subject.**
The task links to what it is about (student · member · period). Then the row on My Day reads
*"Kabir Shah — absent 4 days"* instead of a title string (§3 name the people), the student's
timeline shows a follow-up was raised, and **completing it can ask one optional question:
*what happened?*** — which is the fact the admin actually wanted when they pressed the button.
*"Spoke to the father — fever, back Monday"* is what makes the row go away for good (§8).

*Note this is the smallest change with the largest reach in this session: it fixes 4.5, gives
`S-104` something to close on, and gives `S-107` a key to dedupe on.*

**`S-106` · Mark the rows the admin asked for.**
*"Priya asked · this morning"* on an admin-assigned row. A task I wrote for myself and a task the
principal handed me are not the same object socially, and a teacher triages by that before she
triages by date. One badge, no new data — `task_events` already records `assigned` with the actor.

**`S-107` · Dedupe the rail on the open task, not on the calendar day.**
In `_assign_followup`: if an **open** follow-up already exists for this subject, **extend or nudge
it** and report *"already assigned — due date moved"*, rather than creating a second. The daily
`followup_actions` window stays exactly as it is for `guardian_reminded`, where it is correct.

**`S-108` · Overdue is not "today".**
`D-42`'s main section merges them. Recommend three groups, not two: **overdue** (named, with how
late) → **today + undated** → **Upcoming** (collapsed, count in the label). Merging late work into
today's list is how a teacher loses track of the one row that has been waiting a week — and the
admin's Friday question is precisely about those rows.

**`S-109` · Cap the section.**
Show at most 3–5, then *"+4 more →"*. `D-42`'s design has no cap, and a teacher carrying nine open
tasks would push her evening sessions off the bottom of the screen. My Day must stay My Day.

**`S-110` · The list is *her tasks*, not *the Follow-ups board*.**
One list across all boards. A teacher has one head; "which board is this on" is our concept, not
hers. `HomeService.my_tasks` already computes exactly this, board name included, correctly
sorted — see §3. *(This turns most of `D-41` into a frontend packet.)*

**`S-111` · Delete the client-side filter on `/tasks`** (`page.tsx:156`) and let the server's
answer through. Fixes 4.2. If the Today tab genuinely wants "just mine" on a board, that is a
`scope=mine` parameter the server applies — not a second visibility rule in a component.

**`S-112` · The rail's default due date should be org-local end of day, `all_day=True`.**
Fixes 4.3. *"Tomorrow"* should mean tomorrow, all of it.

### Rejected

- **Per-teacher private boards for follow-ups** — REJECTED (already, in the code): law 5 means the
  admin could not see a board they aren't a member of, so they would be firing tasks into a place
  they could never track. `task_scope='assigned'` on **one public board** gets the same privacy
  with none of the blindness. Recorded here because it is the obvious first idea and it is wrong.
- **A separate board per source** (attendance follow-ups, homework follow-ups, …) — REJECTED for
  now: it multiplies boards on a screen that already has a tab per board, and the teacher does not
  care which module generated her task. `category` on the task already carries the source if we
  want to group by it. Revisit only if one source floods the board.
- **Auto-closing stale tasks** — REJECTED, see `S-104`.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `My Day` — `/my-day` | teacher | **CHANGING** (`D-41` `D-43`) | *"What's next, and what haven't I recorded?"* |
| `Tasks` — `/tasks` | both | CHANGING (`D-43` `D-48`) | *"What am I still carrying?"* — and after `D-43`, the **only** place her older and future work exists |
| `Follow-ups board` — `/boards/[id]` | admin | CHANGING (`D-44` `D-45` `D-46` `D-47`) | *"What have I asked for, and is it moving?"* |
| `Tasks` — `/dashboard/tasks` | admin | EXISTS | *"What work is open and what's overdue?"* |

## 7 · What we deliberately don't build

- **No second task system.** Every module that wants to hand out work goes through
  `TaskService.create` and the action rail — never its own table of to-dos. The rail is *a shortcut
  through the app, not a second way into the database* (`actions.py:5-9`), and that stays true.
- **No task-completion league table.** Same fence as the timesheet (`D-25`) and homework (`S-92`):
  the moment a completion rate ranks people, the rate is what gets managed instead of the work.
  `/dashboard/tasks` shows per-assignee counts so the admin can *help*, and that is the line.
- **No priority inflation.** The model has four priorities and `is_critical`; the rail should not
  set critical on anything automatically. Critical is a human saying so.
- **Nothing above the periods on My Day** (`D-24`, still binding).
- **No parent-facing anything.** A follow-up about a student is staff work and stays staff-side.

## 8 · Open questions — **none. All four were answered in the session.**

| | Answer |
|---|---|
| `Q-45` — archive or window? | **`D-44` + `D-45`** — window, with the date filter; and the stale *open* rows matter more than the done ones |
| `Q-46` — how many tasks on My Day? | **`D-43`** — answered by narrowing the contents, not capping the count |
| `Q-47` — all her tasks or only the admin's? | **`D-43`** — neither: rule-scoped (3 days ∪ due today) |
| `Q-48` — what closes a follow-up reality closed? | **`D-46` + `D-45`** — the subject link and the outcome note; auto-close rejected |

**One detail to settle at build time, not a blocker:** is the 3-day window in `D-43` counted in
**working days**? Claude recommends yes — calendar days make a Friday follow-up invisible on
Monday, which is precisely the bug session 4 found in the homework queue.

## 9 · Data implications

**Almost none, which is the point of this session.** In rough order of how much they change:

- **Nothing at all** for `D-40` (built), `D-41`/`D-43` (a filtered read over
  `HomeService.my_tasks`), `D-48`.
- **A read-side window** for `D-44`: `board_table` grows a `since` / `include_done` parameter.
  No schema change.
- **One nullable pair on `task_instances`** for `D-46`: `subject_type` + `subject_id`, the same
  shape `followup_actions` already uses. Optional third: the outcome note, which can live as an
  existing `Attachment(kind='note')` rather than a new column.
- **`D-45`** is a query over `task_events` — the last event per instance is already there,
  append-only. Nothing new.
- **`D-47`** is a lookup, not a table.

**One nullable pair on one existing table is the entire data cost of this module.** If this list
ever grows a table, the session drifted.

*Note for `D-43`: "assigned from an action rail" needs no new marker — the Follow-ups `board_id`
identifies them today, and once `D-46` lands the subject link is a better one. `created_at` already
carries the 3-day window (`models/task.py`, `CreatedAtMixin`).*

## 10 · Rough build order

1. **`D-48`** — `S-111` + `S-112`. Two small fixes that make the existing board tell the truth. Do
   these first; there is no point designing on top of a board that shows the admin nothing and
   calls Tuesday breakfast overdue.
2. **`D-41`/`D-43`** — the My Day section: a filtered read over `my_tasks`, plus the
   `"n older tasks →"` footer. Visible half, cheap, and the founder's decluttering rule makes it
   *smaller* than the version designed an hour earlier.
3. **`D-44`** — the board window **and** the date filter, together. Never the window alone.
4. **`D-46`** — the subject link and the outcome note. The one migration in the module.
5. **`D-47`** then **`D-45`** — dedupe on the open task, then the stale group. Both read better
   once `D-46` gives them a subject to key on.
