# Session 3 — 2026-07-31

**Topic:** teacher load — the period module. What every teacher does with every period, and who is
free right now.
**Outcome:** 5 decisions (`D-18`–`D-22`), 14 proposals (`S-61`–`S-74`), 7 open questions
(`Q-30`–`Q-36`), one module file, **three verified bugs**.

---

## The finding: this is mostly built, and one of the two admin screens is wrong

SF-1 shipped the capture two days ago; DASH3 shipped the admin side the same day. Against the
founder's description:

| Asked for | Status |
|---|---|
| Teacher sees her pre-assigned classes | ✅ `/timesheet` week grid, cells locked from the timetable |
| Teacher blocks the gaps with a category | ✅ 8 categories, tap a free cell |
| Night before / that morning / as she goes | ✅ nothing prevents any of the three |
| Categories configurable per org | ❌ hardcoded — but the **column has no CHECK constraint**, so the storage is already ready |
| Calendar: month / week / day | 🟡 **week only** |
| Admin day grid, teacher × period | ✅ built **twice**, and the two disagree |
| Chart: how many busy at a given time | ❌ the one genuinely new thing |
| Detail tab with filters | 🟡 detail yes, filters no |

So — as in session 2 — the useful conversation was not *what to build* but *what is wrong with it*.

## 🔴 Three verified bugs, all in the cover flow

**1 · `/staff/today` says an absent teacher has eight free periods.**
It renders `TimesheetService.org_day`, which reads the timetable and the timesheet and nothing
else — no staff absence, no substitutions. `/dashboard/staff` renders the same grid from
`WorkloadInsights`, which knows about both. On the screen whose subtitle is *"who is teaching, who
is on other work, who is free"*, the two worst possible candidates sort to the top.

**Third instance of *one fact, several computations*** — three definitions of "absent for a day"
(session 1), two of "syllabus covered" (session 2), now two of "who is free". This is no longer a
recurring observation; it is the product's characteristic defect.

**2 · The cover picker ignores the timesheet — the module ignores its own data.**
`SubstitutionService.busy_reason` refuses someone teaching, already covering, or marked away.
It never reads `timesheet_entries`. `AttendanceInsights._candidates` ranks by subject fit and
*teaching* load and labels the rest `"free · N periods today"`. So a teacher who recorded *"exam
work — Class 10 scripts"* for period 4 is offered to the admin, in writing, as **free**. The one
moment the timesheet exists for is the one moment nothing reads it.

**3 · The "free periods unlogged" tile is reddest when nothing could have been logged.**
It counts every free period of today, including periods that have not happened yet. At 8:30am it
shows the whole day. `ux-principles` §5, and specifically its corollary: *an admin who marks staff
attendance at 10am must not see a red tile every morning.*

## 🔴 The structural gap: "free" and "didn't fill it in" are the same thing

Every other capture surface in this product has a marker saying a human was here —
`class_periods.attendance_marked_at`, `staff_attendance_days`, and `homework_checks`, whose
**absence** means `not_checked` and never "everyone did it". **The timesheet has none.**

An empty cell renders as `free`. It means *"she had nothing on"* or *"she has never opened this
screen"*, and nothing in the product can tell them apart. Which means:

- the "free periods unlogged" tile is an adoption rate wearing a workload figure's costume;
- **`D-21`'s chart would measure app usage**, not how busy the school is;
- the live board says four people are free when two of them never told us.

`S-61` fixes it the way the rest of the product already does: a one-tap **"That's my day"**, one
row per member × date. This is `Q-31`, and nothing else in the module is honest until it is
answered.

## The three ideas worth keeping

**`S-63` — the teacher's day is ONE list.** `D-22` says her job is exactly two things: the
timesheet and the class log. Today those are two routes for the same day — `/my-day` holds the
periods she teaches, `/timesheet` holds the ones she doesn't. My Day already lists today's
periods; **the free ones are simply missing from it.** Put them in and the second chore stops
existing — there is no "go fill in your timesheet", there is just her day with gaps in it. The
week grid stays for the two things a day list can't do: planning next week, back-filling Tuesday.

**`S-65` — the admin can push work into a free period, and it is already built for one case.**
Half the work in a school is handed out, not chosen: invigilation, ground duty, an event. Today
the timesheet is purely self-reported, so the school's rota lives in a WhatsApp group. And
`period_substitutions` **is** the general shape — the admin putting a named teacher into a named
period, with a busy check and an append-only cancel. A `source = self | assigned` flag turns the
admin's screen from *"who is free"* into *"who is free — give it to her"* (`Q-32`).

**`S-62` + `S-61` together — capture-by-exception for the timesheet.** A teacher's free periods
are the same work most weeks. Let her set the pattern once; each week arrives pre-proposed and she
records only the deviations. Alone this is a fiction generator — a sheet that fills itself in. With
the day-confirm it isn't: the pattern **proposes**, the confirmation **records**. Baseline and
actual, the same distinction P2 already draws for the plan.

## The fence worth arguing for

**`S-67` / `Q-30` — this must never become a scoreboard, and it must never touch pay.**

`D-05` (eight days ago) made days-present drive salary. This module records what a teacher did
with every period of every day. The syllabus module already wrote the argument down: *the moment
coverage % scores a teacher, lesson logs stop being honest, and every downstream number is built
on them.* It applies harder here, because this is about a person's hour rather than a class's
chapter.

If timesheet completeness ever reaches pay or an appraisal, every free period becomes "exam work"
within a month, and the chart, the cover picker and the fairness view are all built on fiction.
Recommended: no leaderboard, no completeness % per teacher, no export that names and ranks, and no
path from `timesheet_entries` to any salary calculation. Staff attendance already feeds `D-05`;
that separation is clean and should stay.

## Smaller things found

- **The warden's evening does not exist.** `sessions` carry `owner_member_id`, `weekdays`, `time`,
  `end_time` — a staffed recurring block — and no load surface reads them. In a hostel school the
  teacher running prep six nights a week reads as lightly loaded (`S-68`, `Q-35`).
- **A one-off working Sunday cannot be recorded** — `TimesheetService.week` drops any weekday
  outside `working_weekdays`, so sports day and exam Sundays have nowhere to go.
- **`updated_at` is never bumped**, so a period back-filled in March is indistinguishable from one
  recorded at 11:58 (`S-71`).
- **Non-teaching staff are counted as teachers** in `/staff/today`'s tiles; `WorkloadInsights` is
  careful about this for the mean and for nothing else.
- **Nothing in this module gives the teacher anything** (P3, `ux-principles` §12). She types what
  she did and it appears on the principal's dashboard. That is a chore, and chores are filled in
  for three weeks. `S-70` gives her the number back — *"27 taught · 6 recorded · 3 covered for
  colleagues"* — which is what she points at when asked to take a fourth cover.

## Decisions

| # | Decision |
|---|---|
| `D-18` | Teacher calendar section — month, week and day; classes pre-filled, gaps blockable |
| `D-19` | Work categories ship fixed, become org-configurable in Settings |
| `D-20` | Fill the timesheet the night before, that morning, or as the day goes |
| `D-21` | Admin: teacher × period day grid + a busy-at-a-given-time chart + a filterable detail tab |
| `D-22` | **A teacher's daily job is exactly two things: maintain the timesheet, log the class** |

`D-22` is recorded as a **fence**, not a summary. It means any future module wanting "one quick
thing from the teacher" has to take something away first.

## Where session 4 starts

**Blocking, in order:**

1. **`Q-31`** 🔴 — is an empty period *free* or *not captured*? Blocks the data model, the chart,
   and whether any figure in this module means anything.
2. **`Q-30`** 🔴 — does timesheet data ever reach pay or an appraisal? Blocks the fence, and
   through teachers' behaviour, the data itself.
3. **`Q-32`** — can the admin assign work into a teacher's period? Blocks the shape of the entry.
4. `Q-33` (out-of-period work) · `Q-34` (back-fill horizon) · `Q-35` (hostel sessions as load) ·
   `Q-36` (who may read a timesheet).

**Cheap and worth doing regardless of the above:** `S-72` (one grid — deletes a live bug in the
cover flow) and `S-74` (cover picker reads the timesheet). Neither needs a decision; both are
corrections.

**Still overdue:** `Q-24` `Q-25` `Q-27` (parent access, session 2) · `Q-01` `Q-02` `Q-03`
(attendance, session 1) · `Q-05`–`Q-08` (payroll — and `Q-30` now leans on `Q-08`).

**Next module in the backlog:** the founder's call. Homework and Students are the natural
neighbours; the admin dashboard and notifications stay last.

---

# Session 3, continued — the founder's answers

Both blockers answered, two Claude proposals rejected, and the module extended into substitution
and teacher–class mapping. Seven decisions: `D-23`–`D-29`.

## The two answers

**`D-23` — an unfilled period is free. There is no "not captured" state.** `S-61` rejected.

Claude argued the opposite and was overruled, but there is a real argument *for* this decision
worth recording: for the question this module exists to answer — *who can take 7-A at 11:20* —
**free is the correct default bias.** Assuming free costs you a ten-second conversation with
someone who says "actually I'm doing X". Assuming busy costs you a class with nobody in it.

Two consequences accepted with it: the "free periods unlogged" tile is **deleted rather than
fixed** (`S-76` — which also disposes of the 8:30am-red bug), and the chart's free band means
*"free or unrecorded"* and should say so once. And `S-62` (the pre-filled weekly pattern) had to
go, because its safety rail *was* the day-confirm — a self-filling sheet with no confirmation step
is a record the teacher never wrote. `S-75` keeps the labour saving by pre-*selecting* in the
picker and writing nothing until she saves.

**`D-25` — the timesheet never touches pay.** Payroll is present/absent on the day plus half-day
leave, full stop. This closes `Q-30`, the highest-stakes question in the module, in the direction
that keeps the data true: a teacher who knows her timesheet cannot cost her money has no reason to
write anything but what happened. It also confirms `D-05`'s only input is staff attendance.

## `D-24` — the timesheet stays its own section

`S-63` (fold the free periods into My Day) **rejected**: the daily capture flow is the sharpest,
most time-pressured surface in the product and nothing else belongs in it. Accepted — the
adoption problem it was solving is real, and now falls to `S-75` (one tap per period) and `S-70`
(the week's totals belong to her, not the principal).

## Substitution — `D-26`, `D-27`, `D-29`

The founder described the cover flow: absent teacher's periods on one side, who is available on
the other, admin assigns; suggestions informed by syllabus pending; and **approving a leave should
hand you the cover options.**

**Most of the two-panel screen is built** — `CoverSheet` already lists each period with ranked
candidates, shows the reason for each rank, assigns, notifies, and puts the period in the
substitute's My Day. Three things are missing, and the third is a bug waiting to happen:

1. **It never reads the timesheet** (`S-74`) — so a teacher who recorded *"exam work — Class 10
   scripts"* is offered to the admin, in writing, as *"free · 3 periods today"*.
2. **It never reads the syllabus** (`D-29`, `S-79`) — which cuts two ways and both are useful:
   *positive*, a substitute who teaches that subject can push the class's **next planned topic**
   forward, so the period is a lesson rather than a holding pen; *negative*, don't hand an extra
   period to someone already two weeks behind. The positive one needs no downstream plumbing — the
   period card credits the class-subject, so the topic lands in the class's log and the forecast
   picks it up on its own. P2 holds.
3. 🔴 **It only ever opens for today** (`D-27`, `S-80`) — an approved leave for Friday has no path
   to cover until Friday morning, which is the morning nobody has a minute. The service already
   takes any date; this is an entry point plus a parameter.

## 🔴 The bug that ships with `D-27` unless it is caught

`busy_reason` refuses a substitute who is teaching, already covering, or has a `staff_absences`
row **for that date**. For a future date **there is no staff-attendance row** — nobody has marked
Friday yet — and it never looks at `leave_requests`.

**So the moment cover can be arranged in advance, an admin can assign Friday's cover to a teacher
who is herself on approved leave that Friday, and nothing objects.** One clause fixes it
(`S-82`). It must ship *with* `D-27`, not after.

## `D-28` — the teacher→classes screen is a switch, not a screen

The founder asked for a screen mapping *teacher 1 → classes 3, 4, 5 Hindi*, so substitution has
proper data to reason over.

*(verified)* The mapping is `class_subjects.teacher_member_id` and it is already the basis of
everything. `/setup` → Assignments already has **two lenses**: by class (editable) and **by
teacher** — that teacher's classes, subjects, periods/week, class-teacher badge, and an *"N
subjects have no teacher"* warning. **The by-teacher lens is read-only**; its own empty state says
*"assign subjects from the class view."*

So `D-28` is that view with save on it (`S-77`): pick a teacher, tick their class-subjects, save
many at once, instead of opening five classes and setting five dropdowns. `PATCH
/academics/class-subjects/{id}` already accepts the field. **Smallest change in the session, and
it is the one that feeds every suggestion the cover sheet makes.**

## One more thing found, on the teacher's side

**Covering a period does not appear on the substitute's own timesheet** (`Q-37`, verified). She
covered three periods this morning and her week grid shows three free cells — the mirror image of
the `/staff/today` bug, and it means `S-70`'s *"3 covered for colleagues"*, the one line on that
screen that is for her, has nothing to read. Same fix, same union, other screen.

---

# Session 3 — CLOSED (2026-07-31)

## What this session settled

| # | Decision |
|---|---|
| `D-18` | Teacher calendar — month, week, day |
| `D-19` | Work categories fixed, then org-configurable |
| `D-20` | Fill it the night before, that morning, or as you go |
| `D-21` | Admin day grid + busy-at-a-given-time chart + filterable detail |
| `D-22` | **A teacher's daily job is exactly two things** |
| `D-23` | **An unfilled period is free** — no "not captured" state |
| `D-24` | The timesheet is its own section, clear of the daily capture |
| `D-25` | **The timesheet never touches pay** — payroll is present/absent + half-day leave |
| `D-26` | Substitution is a two-panel assign screen |
| `D-27` | Approving a leave hands back the cover flow |
| `D-28` | A teacher→classes mapping screen *(= make the existing by-teacher view writable)* |
| `D-29` | Suggestions consider syllabus pending, and stay suggestions |

**Rejected and kept:** `S-61` (day-confirm row) · `S-62` (pre-filled week, superseded by `S-75`) ·
`S-63` (fold the timesheet into My Day).

## Ship-order, short version

**Corrections first — no decision needed, all small, all live defects:**
`S-72` (one grid — `/staff/today` shows absent teachers as free) · `S-74` (cover picker reads the
timesheet) · `Q-37` (cover shows on the substitute's own week) · `S-76` (delete the unlogged
tile).

**Then the founder's substitution flow:** `S-77`/`D-28` (writable by-teacher assignment — it feeds
everything) → `D-26`/`S-78` (the two-panel sheet) → `D-29`/`S-79` (syllabus in the ranking) →
`S-82` **+** `D-27`/`S-80` (leave → cover, **together**) → `S-81` (rail).

**Then the teacher's side:** `D-18`/`S-64` (month + day) → `S-75` + `S-70` → `D-19`/`S-69`
(categories in Settings).

## Still open on this module — all small, none blocking

`Q-32` (non-cover duty — invigilation, ground duty) · `Q-33` (out-of-period work) · `Q-34`
(back-fill horizon) · `Q-35` (do hostel sessions count as load — a warden currently reads as
idle) · `Q-36` (who besides the admin may read a timesheet) · `Q-37` (cover on the substitute's
own timesheet — Claude recommends yes).

## The idea to carry forward

**A capture surface needs a row that says a human was here.** `class_periods.attendance_marked_at`,
`staff_attendance_days` and `homework_checks` all have one; the timesheet deliberately does not
(`D-23`), and that is a legitimate choice **for this module** because free is the safe default
here. But the question should be asked explicitly of every new capture table, because in
attendance and homework the answer went the other way and getting it wrong there is how a teacher
who checks nothing reads as a class with perfect completion.

## Where session 4 starts

Nothing in teacher load blocks it. **Overdue:** `Q-24` `Q-25` `Q-27` (parent access) · `Q-01`
`Q-02` `Q-03` (attendance) · `Q-05`–`Q-08` (payroll — `Q-08` is now narrowed by `D-25`: the
divisor question is about days present and half-days only).

**Next module:** founder's call. Homework and Students are the natural neighbours; the admin
dashboard and notifications stay last.
