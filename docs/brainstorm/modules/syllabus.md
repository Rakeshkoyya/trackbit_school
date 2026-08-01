# Module — syllabus coverage

Is the portion being taught, how far along is it, and — when it isn't — *why not*.

**Sessions:** 2 (2026-07-30)
**Related:** [`class-teacher.md`](class-teacher.md) (her all-subject view),
[`attendance.md`](attendance.md) (the capture-vs-reality distinction repeats here exactly)

---

## 1 · Who this is for, and when

| Role | The moment | Device / budget | The question they arrive with |
|---|---|---|---|
| **Admin** | weekly, and hard before every exam | desktop, a few minutes | *"Will we finish the portion, and who is falling behind?"* |
| **Class teacher** | when a parent asks, or before a meeting | phone or laptop, 4pm | *"Is my class behind in anything?"* |
| **Subject teacher** | when planning the week | phone, between classes | *"Where am I in my own subjects?"* |
| **Parent** | evening, curious or worried | phone, one minute | *"What are they learning, and how far have they got?"* |

## 2 · What they must be able to decide

- **Admin:** who to talk to this week · whether a subject needs extra periods before an exam ·
  whether the plan itself was unrealistic
- **Class teacher:** what to raise with which subject teacher · what to tell a parent
- **Subject teacher:** what to teach next, and whether to catch up
- **Parent:** nothing — this is reassurance and context, not a decision surface

---

## 3 · Where it stands today *(verified 2026-07-30)*

### The admin board already exists, and it already does most of the ask

`/dashboard/syllabus` shipped with DASH3 (§4.2), backed by `services/insights/syllabus.py`.
It has:

| Asked for | Already built |
|---|---|
| coverage school-wide | ✅ `school` node — coverage %, topics taught / planned |
| coverage class-wise | ✅ `scope=class` pivot |
| coverage subject-wise | ✅ `scope=subject` pivot |
| **also** teacher-wise | ✅ `scope=teacher` — a re-pivot of the same rows, not a child of subject |
| visual representation | ✅ RAG donut, coverage row-bars per node, 4 stat tiles — all through `components/charts` |
| which subject is ahead | ✅ `ahead` — top 3 ranked nodes |
| which is worst | ✅ `needs_support` — bottom 3 |
| which class is best / worst | ✅ same two lists, with `scope=class` |
| **also** per-exam checkpoint | ✅ *"can each subject finish its portion before this exam?"* — short / tight / fits |

It also carries two honesty rules that must not be lost in any redesign:

- **States are never colours.** `unplanned` (nothing scheduled), `unallocated` (no periods/week)
  and `unestimated` (not sized yet) render as neutral words. V2-P11 exists *because* treating
  them as green made an unplanned year look healthy.
- **Nothing is ranked below a minimum sample.** A class needs ≥3 rated class-subjects; a teacher
  also needs ≥10 logged periods, or the node reads "not enough data yet". Framing is *needs
  support / ahead of plan* — deliberately not a league table of people, because pace carries
  timetable disruption and class composition at least as much as teaching.

### The teacher side is thin

`/plan/*` is open to both roles, but the screens are **admin-shaped**: a class dropdown, then a
subject dropdown, then one subject's plan. A teacher with six class-subjects has to pick her way
to each one. There is **no "my subjects" screen** anywhere.

### The parent side already exists

`/parent/progress` shows *"Syllabus covered — 34/58 topics"* with a meter bar per subject, and
deliberately shows **no pace, no RAG, no lag**. That already matches `D-11`.

### 🔴 The defect: two different "syllabus covered" percentages

The same phrase means two different things depending on who is reading it.

| | Admin board | Parent portal |
|---|---|---|
| Denominator | **planned** topics (only what's scheduled) | **all** topics in the syllabus |
| Numerator | distinct logged topics, partial counted as **0.5** | topics with any log, partial counts as **1** |
| Source | `insights/syllabus.py` ← `PlannerService.forecast_org` | `GrowthService` chapter roll-up |

So a parent and a principal can look at the same subject on the same day and read different
percentages, and neither number is wrong on its own terms. **This is the same defect class as
the three definitions of "absent" found in session 1** — and it will keep happening until
"one computation, many renderings" is treated as a build rule rather than a principle.

---

## 4 · What else is wrong

1. **No trend.** Everything is "as of today". Nobody can see whether 6-B Maths has been slipping
   for a month or just had one bad week — which is the difference between a problem and a blip.
2. **Behind and unrecorded look identical.** A subject whose teacher never logs topics reads as
   *behind*. `logged_periods` is already computed and used **only** as a ranking guard; it is
   never surfaced as a finding. This is exactly the distinction the attendance capture heatmap
   draws, and the syllabus board has no equivalent.
3. **No "why".** *"6-B Maths is 3 weeks behind"* is where the screen stops and where the
   admin's actual work starts.
4. **The rank score is unexplainable.** `on_track_share × 60 + coverage × 40`. Nobody can
   reconstruct it, so nobody can argue with it — which is a problem when it is about a person.
5. **The best thing in the module is buried.** The exam checkpoint answers *"can this subject
   finish its portion before the exam?"* — the question schools actually manage against — and it
   sits behind a tab most people won't press.

---

## 5 · Ideas and directions

### Decided — session 2

- **`D-09`** — admin sees coverage school-wise, class-wise and subject-wise, with charts, plus
  which subject/class is ahead and which is worst. *(Largely already built — see §3.)*
- **`D-10`** / **`D-15`** — **subject teacher: her own subjects only**, blocked from others.
  **Class teacher: all subjects and all teachers' pace, but only for her own class** — not
  school-wide. A teacher who is not a class teacher sees only her own subject.
- **`D-16`** — one quick action: **"Ask for a catch-up plan"**. The admin never reschedules
  chapters directly from the board.
- **`D-11`** — parents see **what is being taught and how far it has got. Never** that the
  syllabus is lagging, behind, or missed.

### Proposed — `S-nn`

#### `S-51` · One coverage definition 🔴
Mirror of `S-01` from session 1. One function computes coverage; the admin board, the parent
portal, the class teacher view and the growth report all call it. Decide once whether the
denominator is *planned* or *the whole syllabus* — and whether partial counts as a half.

*Claude's view: the admin should see both (**"34 of 58 in the syllabus · 34 of 41 planned so
far"**), and the parent should see coverage of the **whole syllabus**, because that is the
number that only ever goes up. See `S-54`.*

#### `S-41` · Say **why** it's behind — the biggest idea in this module
A subject is behind for one of four reasons, and they need four different responses:

| Cause | How we'd know | What the admin does |
|---|---|---|
| **Periods were lost** | scheduled slots vs `class_periods` held / `not_held` / substituted | nothing — nobody's fault; consider extra periods |
| **Nothing was logged** | `logged_periods` ≈ 0 while attendance was marked | talk to the teacher about *recording*, not teaching |
| **Chapters were never sized** | `unestimated_topics` > 0 | a setup gap — send them to size it |
| **Genuinely slower than planned** | periods held, topics logged, still behind | the real teaching conversation |

*"6-B Maths is 3 weeks behind"* becomes *"6-B Maths lost 8 periods to the exam week and two
holidays"* — a completely different conversation, and often one where **nobody is at fault**.
Almost all the data exists. This is what turns the board from a scoreboard into a diagnosis.

#### `S-42` · Unlogged is not behind
Give the board the equivalent of attendance's capture heatmap: a subject with no lesson logs is
**unknown**, not behind, and must never be ranked, coloured red, or put on a "worst" list. Same
rule, same reasoning, and it is the rule most likely to be broken by a redesign that leads with
charts.

#### `S-40` · The missing chart — coverage over time
Every chart on the board is a snapshot. The one that answers *"is this getting better or
worse"* is coverage plotted against the term, with the **baseline plan as a reference line** —
so the gap between planned and actual is visible as a widening or closing band. Lesson logs are
dated; the data is there. `PulseArea` and reference lines already exist in `components/charts`.

#### `S-43` · Compare sections of the same grade
6-A Maths vs 6-B Maths is the fairest comparison in a school — same syllabus, same weeks,
different teacher — and it is the comparison a principal actually makes. The pivot exists;
nothing draws this specific view.

#### `S-45` · Make the ranking explainable
Replace the composite score with the sentence behind it: *"3 of 4 subjects on track · 68%
covered"*, sorted on something a person can name. If a rank cannot be explained to the teacher
it is about, it should not be on the screen.

#### `S-50` · Lead with the exam checkpoint
Schools manage against exams, not against April-to-March. *"Second Terminal is in 24 days · 4
subjects short of portion"* is a stronger headline than any coverage percentage, and it is
already computed.

#### `S-46` · Teacher: "my subjects", not a dropdown maze
One screen, one row per class-subject she teaches, each with where she is and what's next. Five
to eight rows — that's a list, not a selector. `?mine=true` already exists on the classes
endpoint and the plan screens don't use it.

#### `S-48` · Parent: name the chapter, not just the percentage
*"This week in Maths: Fractions — addition and subtraction"* beats *"58% covered"* for a parent,
because it is the thing they can ask their child about at dinner. Derivable from lesson logs
today.

#### `S-54` · Never show a parent a percentage that can go down
Coverage against *planned* topics **falls** when the school sizes the next term's chapters —
the denominator grows, nothing was un-taught. An admin can be told why; a parent will read it
as the school going backwards. Parent-facing coverage must use a denominator that only grows.

### Rejected

#### ~~`S-52`~~ · Don't block a subject teacher from the class-wide view — **REJECTED** (`D-15`)
Claude argued that a coverage figure is not confidential between colleagues, and that hiding it
invites the belief it is being used against them; her own subjects should be her *default*, not
a wall. **Overruled.** A subject teacher sees her own subjects only. Kept here so the argument is
not re-made in a later session.

#### ~~`S-44c`~~ · Admin schedules new chapters from the board — **REJECTED** (`D-16`)
A plan change should come out of a discussion between the teacher and the principal, not a button
on a dashboard. `extend_plan` stays in the plan screen, used *after* the conversation.

### Still proposed

#### `S-49` · "Missed while absent" is not "the syllabus is behind"
`D-11` says parents never see lag. The growth report currently shows, per chapter, **topics
taught while their child was away**. That is about *the child*, not the school — and it is
arguably the single most useful thing on any parent screen, because it converts an absence into
an academic consequence a parent understands. Worth an explicit ruling rather than being caught
by the blanket rule → `Q-19`.

---

## 6 · Quick actions — the founder's open question, answered

> *"we would give any quick action in UI (because im not getting any ideas should we have quick
> action in this case)"*

**The honest answer first:** the reason no action came to mind is that **most syllabus problems
are not one-tap solvable.** Attendance produces "call this parent" — a complete action. A
subject three weeks behind produces a conversation and a re-plan. A fake quick action here would
be worse than none, because it would imply the problem is closed when it isn't.

**But three real ones exist**, and one of them is genuinely the action:

### `S-44a` · "Ask for a catch-up plan" — the real one
Creates a task on that teacher, prefilled with the class-subject, the gap and the exam it
threatens, due in a few days. This *is* what the admin does in real life — asks the teacher what
they intend to do about it. It reuses the existing one-tap **alert → task** pattern from the
dashboard, and unlike a status change it produces a reply.

### `S-44b` · "Size these chapters" — a deep link, and the highest-yield one
For `unestimated` / `unplanned` rows the blocker is concrete and the fix is concrete. This is
not really a quick action; it is removing three clicks from the one thing that unblocks a whole
subject's forecast.

### ~~`S-44c` · "Schedule new chapters"~~ — **REJECTED** (`D-16`)
Founder's reasoning: a plan change should come out of a discussion between the teacher and the
principal, not from a button on a dashboard. `extend_plan` stays where it is, in the plan screen,
used *after* the conversation.

**And one that is not an action but belongs beside them:** *"nothing logged for 3 weeks"* should
nudge the teacher to log (`S-42`), because half of what looks like a syllabus problem is a
recording problem.

**Outcome (`D-16`):** *"Ask for a catch-up plan"* is approved. Direct admin rescheduling is
rejected. `S-44b` ("Size these chapters") is still open — it is a deep link, not an action, and
schedules nothing; Claude recommends keeping it.

### `S-60` · The catch-up button is a **meeting request**, not a directive
`D-16` changes its shape. It should read *"Discuss 6-B Maths catch-up"*, carry the gap, the exam
it threatens and the **cause** (`S-41`), and it is **not finished when the task is created** —
it is finished when the meeting's outcome is recorded and the plan is re-drafted by the people
who met. The row on the board should clear on the **outcome**, not on the press.

### `S-59` · Two modules now want the same primitive
Attendance's *"assign a follow-up → record what the parent said"* (`S-21`) and syllabus's *"ask
for a catch-up plan → record what was decided"* are the same shape: **a request that becomes a
conversation that produces an outcome.** `followup_actions` already exists (append-only, DASH3
PR-5) and currently records only the press. Worth generalising **once**, rather than building it
twice with different words.

---

## 7 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `/dashboard/syllabus` | admin | CHANGING | *"Will we finish the portion, and who's behind?"* |
| My Class → syllabus block | class teacher | NEW | *"Is my class behind in anything?"* |
| `/plan/*` → "My subjects" | teacher | CHANGING | *"Where am I in my own subjects?"* |
| `/parent/progress` | parent | CHANGING | *"What are they learning, how far have they got?"* |

Detail in [`../screens/`](../screens/).

## 8 · What we deliberately don't build

- **No pace, lag, RAG or "missed" on any parent surface** (`D-11`).
- **No league table of teachers.** The board says *needs support*, with the sample size beside
  it, and refuses to rank thin data at all.
- **No automatic re-planning.** The plan is a baseline and stays locked (P2); the system
  proposes and a human approves. Nothing here silently rewrites a plan.
- **No "syllabus completion" targets or scores** for teachers. The moment coverage % becomes a
  performance metric, lesson logs stop being honest — and every downstream number in the product
  is built on them.

## 9 · Open questions

`Q-16` (parent coverage denominator) · `Q-18` (is "not enough data yet" acceptable, or does it
read as broken?) · `Q-19` ("missed while absent" — keep it for parents?) · `S-44b` sign-off.
**Answered:** `Q-17` and `Q-20` → `D-15`. Full text in
[`../open-questions.md`](../open-questions.md).

## 10 · Data implications

Very little is needed — this module is mostly a **read** problem.

```
NO new tables.

one coverage function                     (S-51) — the only correctness-critical item
cause attribution for "behind"            (S-41) — reads class_periods (held / not_held /
                                                   substituted) vs timetable slots; nothing stored
coverage-over-time series                 (S-40) — lesson_logs are already dated
"nothing logged" signal                   (S-42) — logged_periods already computed, just unused
```

The one thing worth watching is cost: `forecast_org` is already one batched pass (PR-6, added
because the old per-class loop cost ~80 round-trips for one card). A time series must not
reintroduce a per-week loop.

## 11 · Rough build order

| Step | Contents |
|---|---|
| 1 | `S-51` one coverage definition · `S-42` unlogged ≠ behind |
| 2 | `S-41` the why · `S-45` explainable rank · `S-50` lead with the exam checkpoint |
| 3 | `S-44b` then `S-44a` quick actions · `S-40` coverage over time · `S-43` section compare |
| 4 | `S-46` teacher "my subjects" · class-teacher syllabus block (`S-28`) |
| 5 | `S-48` parent chapter names · `S-54` safe denominator |
