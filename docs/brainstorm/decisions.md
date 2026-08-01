# Decision log

Founder decisions, newest session last. Each is `D-nn`, dated, with the module it belongs to.
**Status** is one of `DECIDED` (build to it), `SUPERSEDED` (a later decision replaced it — the
row stays), `PARKED` (deliberately deferred).

---

## Session 1 — 2026-07-30 (attendance, class teacher, staff, payroll)

### D-01 · Attendance capture frequency is an org setting
**Module:** attendance · **Status:** DECIDED

The school chooses **how often attendance is taken**, in Organisation settings. Three options:

1. **Every period** — a mark per timetabled period (today's only behaviour).
2. **First period only** — one roll call a day.
3. **Twice a day** — first period, and the first period after lunch.

The whole system behaves according to the selected mode: what teachers are asked for, what the
capture heatmap expects, what the denominators mean, and what "absent today" is computed from.

> Claude's note: option 3 is the most interesting one and nobody else builds it. Present in the
> morning and gone after lunch is the single fact a school most wants and cannot currently see —
> mode 3 makes that a *first-class signal*, not a rounding error. See `S-05`.

### D-02 · Absence reason, then a RAG-coloured follow-up
**Module:** attendance · **Status:** DECIDED

The flow:

1. The teacher marks a student absent (capture stays exception-only — unchanged).
2. The absence appears on the admin's screens.
3. **Admin *or* teacher can add a reason** afterwards — the reason is entered later, by staff,
   never required at the moment of capture.
4. **Colour rules:**
   - reason recorded (parent informed the school) → **yellow**
   - absent **more than 3 days with no reason** → **red**
5. **Red rows carry two actions:** inform the parents, and assign a teacher to follow up with
   the parents.

> Claude's note: this is a *state machine on the absence*, not a colour rule in a component.
> See `S-22` — the status should be computed once server-side and merely painted by the UI, or
> the three screens that render it will drift apart, exactly as the three definitions of "absent
> for a day" already have (see `modules/attendance.md`, "The three definitions").

### D-03 · Class teacher is assigned by the admin and gets her own dashboard
**Module:** class-teacher · **Status:** DECIDED

The admin decides which teacher owns which class + section, configured in **Setup**. Once
assigned, that teacher gets a **dedicated dashboard for her class** — attendance, syllabus, and
a few other modules (which ones: `Q-10`).

*(verified)* The backing field already exists and is already read in four places
(`school_classes.class_teacher_member_id`, `PATCH /academics/classes/{id}` accepts it) — but
**no UI ever sets it**, so it is null everywhere and the "class teacher: —" on the admin's
absence list is always blank. The assignment half of this decision is a frontend-only job.

### D-04 · Staff half-day leave and late marking
**Module:** staff-attendance-leave · **Status:** DECIDED · **supersedes SF-1's "no late tier for staff"**

- The admin marks staff attendance (exists today, present/absent only).
- A teacher can apply for **full-day or half-day leave**; the admin approves.
- The admin can also mark someone **late**.
- The backend keeps a running count of **days actually present**, which is what feeds `D-05`.

### D-05 · Payroll — salary is calculated from days present
**Module:** payroll · **Status:** DECIDED · **supersedes the §11 fence "payroll/HR is OUT"**

Days present drive a salary calculation. Configuration lives in **Organisation settings**:

- total leaves allowed per year
- grace period per leave
- how many days per month a person may apply for

> ⚠️ **This is a fence change, and the biggest one in the session.** SPRD2 §11 lists payroll and
> HR under "Still OUT", and SF-1 shipped explicitly as *"operational only: who covers period 4,
> not payroll or HR"*. That line is now void. Recorded here so nobody later reads the fence and
> reverts the work. Consequences that need answers before building: `Q-05` (estimate vs payable
> record), `Q-06` (who may see salary), `Q-07` (salary structure), `Q-08` (what actually deducts
> pay). See `S-15`–`S-17`.

### D-06 · A Salary tab under the Staff menu, with two views
**Module:** payroll · **Status:** DECIDED

- **Admin view** — a dashboard-style screen: days present per staff member and their estimated
  salary.
- **Teacher view** — her own page: her own days and her own month's record. A teacher sees only
  herself.

### D-07 · No student login — students are data
**Module:** attendance (and product-wide) · **Status:** DECIDED

This is school-level management software. Students never authenticate. Everything a student
would need to see reaches them through their parent's portal or through a teacher.

Confirms the recommendation from the session-1 review. Closes the question permanently — it
should not be re-raised for hostellers or seniors without an explicit reversal here.

---

## Session 2 — 2026-07-30 (notifications channel, syllabus)

### D-08 · No WhatsApp in this version — notifications are in-app, with a parent notifications tab
**Module:** notifications (cross-cutting) · **Status:** DECIDED

Guardian messaging does **not** go out over WhatsApp in this version. Notifications are
delivered inside the product, and the parent portal gains a **Notifications tab** where a parent
can see them.

*(verified)* Today `notify_guardian.py` is a WhatsApp stub that logs to the console when no keys
are set, and it is what the absence alert, the homework notification and the Saturday summary
all call. Those three now need an in-app destination instead.

> ⚠️ Two consequences that need answers before this is built, both in `open-questions.md`:
> **`Q-21`** — an in-app notification only reaches a parent who opens the app; an absence alert
> nobody sees is not an alert. Web push already exists in the codebase for staff — do parents
> get it? **`Q-22`** — parent login is phone-OTP, and OTP delivery currently tries WhatsApp
> first with an SMS fallback. If WhatsApp is out, parents need SMS or handed-over credentials,
> or **nobody can log in to see the notifications tab at all.**

### D-09 · Admin syllabus: coverage school / class / subject-wise, with charts and best/worst
**Module:** syllabus · **Status:** DECIDED — **largely already built**

The admin sees how much of the syllabus is covered school-wide, class-wise and subject-wise,
visually (charts/graphs), plus which subject is ahead and which is worst, and which class is
best and worst.

*(verified)* `/dashboard/syllabus` already does all of this — school/class/subject **and
teacher** pivots, RAG donut, coverage bars, `ahead` and `needs_support` top/bottom-3 lists, and
a per-exam checkpoint. The work here is not building it; it is fixing what it gets wrong (`S-51`
coverage is defined two different ways) and adding what it lacks (`S-41` *why* something is
behind, `S-42` unlogged ≠ behind, `S-40` a trend).

### D-10 · Teacher syllabus views split by capability
**Module:** syllabus · **Status:** DECIDED

- **Class teacher** — the entire class view (all subjects) *and* the subject view.
- **Subject teacher** — her own subjects only.

### D-11 · Parents see progress, never pace
**Module:** syllabus · **Status:** DECIDED

Parents see **what is being taught and how far it has got**. They never see that the syllabus is
lagging, behind, or missed.

*(verified)* `/parent/progress` already honours this — coverage meter per subject, no RAG, no
weeks-behind. Two things need a ruling against it: a coverage % measured against *planned*
topics **goes down** when the next term is sized (`S-54`), and the growth report's *"topics
taught while your child was absent"* is about the child rather than the school (`Q-19`).

### D-12 · Quick actions on the syllabus board — three, not a rail
**Module:** syllabus · **Status:** SUPERSEDED by `D-16`

The founder asked whether quick actions make sense here at all. Claude's answer: most syllabus
problems are **not** one-tap solvable — unlike attendance, which produces "call this parent".
Three are real: **"Size these chapters"** (a deep link, highest yield), **"Ask for a catch-up
plan"** (creates a task on the teacher — the action an admin actually takes), and **"Schedule
new chapters"** (`extend_plan`, already built, currently buried). Nothing that merely marks a
row as seen. Full reasoning in `modules/syllabus.md` §6.

### D-13 · Parent login is school code → class → section → student → date of birth
**Module:** parent portal / auth · **Status:** DECIDED · **answers `Q-22`, supersedes phone-OTP as the primary path**

Every school has its own **school code**. The parent enters the code to pick their school, then
the class, the section and their child, and enters the child's **date of birth as the password**.
The session **persists until they log out**.

*(verified — two fields do not exist yet)* `organizations` has **no school code / slug**, and
`students` has **no date of birth** — nor does the roster importer's column map
(`TARGET_FIELDS` = full_name, admission_no, roll_no, class_name, section, category…). So this
login cannot work until DOB is collected for every student. See `Q-24`.

> ⚠️ **Two security consequences, recorded so they are accepted deliberately rather than
> discovered.** They do not block the design — the pattern is common in Indian school apps — but
> each has a cheap fix that keeps the UX identical.
>
> 1. **The picker is a roster leak.** Code → class → section returns *every child's name* in that
>    section, before any password is entered. Anyone with a school code can harvest the school's
>    student list. Fix: `S-55` — type-to-search instead of a browsable list.
> 2. **A date of birth is roughly 5,500 guesses.** With no lockout it falls in minutes, and the
>    student picker tells the attacker exactly who to target. Fix: `S-56` — reuse the OTP
>    module's existing 5-attempt lock and hourly throttle, keyed per student.
>
> Also unresolved: siblings (`Q-25`), whether the school code is secret (`Q-26`), what happens to
> the guardian-phone link the whole PC-1 model is built on (`Q-27`), and whether a parent can
> ever change the password (`Q-28`).

### D-14 · Web push for notifications
**Module:** notifications · **Status:** DECIDED · **answers `Q-21`**

Parents get **web push**. That is what makes `D-08`'s in-app notifications actually arrive rather
than waiting for someone to open the app. Push already exists in the codebase for staff.

### D-15 · Syllabus visibility, precisely
**Module:** syllabus · **Status:** DECIDED · **answers `Q-17` and `Q-20`; refines `D-10`**

- **Subject teacher** — her **own subjects only**. Blocked from others, not merely defaulted away
  from them.
- **Class teacher** — **all subjects and all teachers' pace, but only for her own class.** Not
  school-wide.
- A teacher who is not a class teacher sees only her own subject.

> Claude had recommended *not* blocking (`Q-17`) on the grounds that hiding a coverage figure
> between colleagues invites the belief it is being used against them. **Overruled — build to
> `D-15`.** `S-52` marked REJECTED.

### D-16 · Quick actions: "Ask for a catch-up plan" only — admin never reschedules directly
**Module:** syllabus · **Status:** DECIDED · **replaces the proposal in `D-12`**

**Approved:** *"Ask for a catch-up plan"* — the admin presses it, the teacher is asked to come
and discuss, they meet, and **the reschedule follows the conversation**.

**Rejected:** the admin directly scheduling new chapters from the dashboard (`S-44c`). Founder's
reasoning: a plan change should come out of a discussion between the teacher and the principal,
not from a button on a board.

> This makes the button a **meeting request, not a directive** — which changes its copy and its
> lifecycle. See `S-60`. It also means the row on the syllabus board clears when the **outcome**
> is recorded, not when the task is created — the same shape as attendance's `S-21`. Two modules
> now need the same primitive: see `S-59`.

**`S-44b` ("Size these chapters") is still open** — it is a deep link, not an action, and it does
not schedule anything. Claude's recommendation is to keep it.

### D-17 · The login hardening is accepted
**Module:** parent access · **Status:** DECIDED

`D-13`'s flow stands, with the three fixes that keep it identical for a real parent:

- **`S-55`** — the child step is **type-to-search** (3+ characters), never a browsable list, so
  the roster is not exposed to anyone holding a school code.
- **`S-56`** — **lock after 5 attempts, throttle per hour**, keyed per student. Reuses the OTP
  module's existing machinery, which already survives request rollback.
- **`S-57`** — the school code is **random 6–8 characters**, handed to parents, never published.

Everything else about parent access — where the DOB comes from, siblings, what the "account" is
now, whether the password can change, whether OTP survives as a recovery path — is **explicitly
deferred** to session 3. See `Q-24`–`Q-29`.

---

## Session 3 — 2026-07-31 (teacher load — the period module)

Five decisions from the founder's opening statement. The module is
[`modules/teacher-load.md`](modules/teacher-load.md).

### D-18 · The teacher gets a calendar section — month, week and day
**Module:** teacher-load · **Status:** DECIDED

A new section in the teacher's login showing her classes in a calendar: **per month, per week,
and a complete day view.** Each day shows the periods the timetable already assigned her, and any
gap can be blocked out for a piece of work.

*(verified)* `/timesheet` already renders the **week** — periods down, days across, teaching cells
locked from `timetable_slots`, free cells tappable. **Month and day views do not exist.**

> Claude's note: give the three altitudes three different jobs rather than three renderings of
> one grid (`S-64`). A month of 8 periods × 25 days is 200 cells and is unusable on a phone — but
> a month of *one cell per day*, carrying the day's state and the school calendar (holidays,
> leave, exam days), is the best pattern-reading surface in the module. **Month = shape · week =
> edit · day = do.**

### D-19 · Work categories start fixed and become org-configurable
**Module:** teacher-load · **Status:** DECIDED

Notebook checking, exam-related, event-related and the rest ship as a set; a school can then
enable, disable and add its own in **Organisation settings**.

*(verified)* `core/work_types.py` is a hardcoded dict of 8, **but the column has no CHECK
constraint** and `normalize()` deliberately keeps a school's own word rather than flattening it to
`other`. The storage is already ready; only the picker is hardcoded. See `S-69` for the four rules
that stop a rename orphaning last term's rows.

### D-20 · The timesheet may be written the night before, that morning, or as the day goes
**Module:** teacher-load · **Status:** DECIDED

All three, with no mode switch.

*(verified)* Already true — `set_entry` upserts and `clear_entry` deletes, with no lock and no
horizon. Two consequences worth being deliberate about: a sheet written the night before is a
**plan**, not a record (which is fine for cover, and is what `S-61`'s day-confirm turns into a
record), and a period back-filled three weeks later is weaker evidence than one written at 11:58
— `S-71` marks it instead of blocking it. `Q-34`.

### D-21 · The admin sees the day as a grid, a busy-at-a-time chart, and a filterable detail tab
**Module:** teacher-load · **Status:** DECIDED

- A **teacher × period grid** for the day.
- A **chart of how many teachers are busy at a given time.**
- A tab with more detail and filtering.

*(verified)* The grid exists **twice** — `/staff/today` and the day strip on `/dashboard/staff` —
computed by two different services that disagree: `/staff/today` ignores staff absence and
substitutions, so **a teacher who is away today shows eight free periods on the screen the admin
opens to find cover** (`S-72`). The detail tab largely exists on `/dashboard/staff`; filters do
not. The **chart is genuinely new** (`S-66`).

> ⚠️ The chart is only honest if `Q-31` is answered first. With no way to distinguish a free
> period from an unfilled one, "how many are busy at 11:20" is measuring how many teachers use the
> app, not how busy the school is.

### D-22 · A teacher's daily job is exactly two things
**Module:** teacher-load (product-wide) · **Status:** DECIDED

**Maintain the timesheet, and log the class.** Nothing else.

> Claude's note: recorded as a **fence**, not a summary — it is the strongest constraint anyone
> has put on this product. It means every future module that wants "just one quick thing from the
> teacher" has to take something away first.

---

## Session 3, continued — 2026-07-31 (the founder's answers + substitution)

Both blocking questions answered, two Claude proposals rejected, and the module extended into
substitution and teacher–class mapping.

### D-23 · An unfilled period is free. There is no "not captured" state.
**Module:** teacher-load · **Status:** DECIDED · **answers `Q-31`; rejects `S-61`**

If a teacher has not filled in a period, the system treats her as **free**. No day-confirm row, no
third state, no chasing.

> Claude had recommended the opposite (`S-61`) and was overruled. Recorded properly, because there
> is a real argument **for** this decision that is worth having in writing: for the question this
> module exists to answer — *who can take 7-A at 11:20* — **free is the correct default bias.**
> The failure mode of assuming free is that you ask someone who says "actually I'm doing X"; the
> failure mode of assuming busy is a class with nobody in it. One is a ten-second conversation,
> the other is an incident.
>
> Two consequences to accept deliberately:
> 1. **"Free periods unlogged" stops being a meaningful figure** and should be deleted, not fixed
>    (`S-76`). Under `D-23` there is no such state to count.
> 2. **The `D-21` chart's free band means "free or unrecorded"** and should say so once, in the
>    hint (`ux-principles` §4 — a figure carries its denominator). One line of copy; the decision
>    stands.

### D-24 · The timesheet stays its own section, away from the daily capture
**Module:** teacher-load · **Status:** DECIDED · **rejects `S-63`**

Teachers update the timesheet in a **separate section**, so it does not get mixed into the daily
class capture — attendance, topic log, homework. Two surfaces, deliberately.

> `S-63` (fold the free periods into My Day so the day is one list) **REJECTED.** Founder's
> reasoning: the daily capture flow is the sharpest, most time-pressured thing in the product and
> nothing else belongs in it. Claude accepts the reasoning — the counter-argument was adoption
> (a separate route is a route people forget), and the answer to that is `S-75` and `S-70`, not
> merging the screens.

### D-25 · The timesheet never touches pay
**Module:** teacher-load / payroll · **Status:** DECIDED · **answers `Q-30`; narrows `Q-08`**

**Payroll is computed purely from present/absent on the day, plus half-day leave.** Nothing in
`timesheet_entries` reaches a salary figure, an appraisal, or any ranking of people.

> This is the most important line in the module. It is what keeps the data true: a teacher who
> knows her timesheet cannot cost her money has no reason to write anything but what happened.
> It also confirms the input to `D-05` is **staff attendance only** — a clean separation that
> already exists in the code and must stay.

### D-26 · The substitution screen is two panels
**Module:** teacher-load · **Status:** DECIDED

When staff attendance marks someone absent, the admin opens a screen with **the absent teacher's
periods on one side** and, for each period, **who is available at that time on the other**, and
assigns.

*(verified)* This is largely built — `CoverSheet` lists each period the absent teacher was due to
take with ranked candidates and an **Assign** button. What it is missing is `S-74` (it never reads
the timesheet, so it offers a teacher who recorded "exam work" as free), `D-29` (syllabus signal),
and `D-27` (it only ever opens for **today**).

### D-27 · Approving a leave hands the admin the cover flow
**Module:** teacher-load / leave · **Status:** DECIDED

Admin approves a leave request → **immediately gets the option to arrange substitutes** for the
days it covers.

*(verified — this is a real gap)* `CoverSheet` opens only from a *"away today"* row on
`/dashboard/staff`, driven by **today's** staff attendance. An approved leave for Friday has no
path to arranging cover until Friday morning — which is the morning nobody has a spare minute.
The service already accepts any date (`SubstitutionService.create` takes `body.date`), so this is
a UI change plus one parameter. See `S-80`, `S-81`, and 🔴 `S-82`.

### D-28 · A teacher → classes screen, so the mapping is proper data
**Module:** teacher-load / setup · **Status:** DECIDED

The admin maps a teacher to the classes and subjects they take — *teacher 1 → classes 3, 4, 5
Hindi; teacher 2 → classes 6, 7, 8* — so the substitution logic has real data to reason over.

*(verified)* The mapping itself already exists and is already the basis of everything —
`class_subjects.teacher_member_id`, set through `/setup` → Assignments. There are already **two
lenses over it**: by class (editable) and **by teacher** (`ByTeacherView` — the teacher's classes,
subjects, periods/week, class-teacher badge, and an *"N subjects have no teacher"* warning).

**The by-teacher lens is read-only.** Its own empty state says *"Nothing assigned yet — assign
subjects from the class view."* So `D-28` is not a new screen: it is **making that view
writable** (`S-77`), which is the smallest change in this session with the largest effect on
setup time.

### D-29 · Substitute suggestions consider syllabus pending — and stay suggestions
**Module:** teacher-load · **Status:** DECIDED

The system suggests who could cover, informed by **syllabus pending**, and may suggest teachers
from other classes. **The admin decides and assigns** — the system never auto-assigns.

*(verified)* Ranking today is: teaches this subject elsewhere → teaches this class → lightest
teaching load. Syllabus is not consulted. See `S-79` for the two complementary readings of
"pending" (can this cover be a *real lesson*, and is this substitute already behind in her own
subjects) and `S-78` for what the panel should say.

---

## Session 4 — 2026-07-31 (homework)

Three decisions. The module is [`modules/homework.md`](modules/homework.md) — and the short
version is that **all three are already built**, so the session's value is in the four live
defects it found.

### D-30 · The teacher sets homework for a class, and marks it the next day
**Module:** homework · **Status:** DECIDED — **already built**

An option on the teacher's own page to set homework for a class; the next day she goes through it
and marks who did it and who did not.

*(verified)* Both halves exist. Setting: the My Day class card and the period card's Homework
section (class-wide or per-student), and posting it notifies guardians immediately (P3). Checking:
the My Day block *"Yesterday's homework — mark completion"* — **"Everyone did it"** in one tap,
*"Some didn't…"* opens a roster where a tap cycles **did it → didn't → partly**.

> 🔴 But *(verified)* the checking queue looks at **exactly one day** — `date == today - 1`. So
> **Friday's homework never appears on Monday**, and any day skipped loses that homework from the
> screen permanently. `due_date` is ignored by the queue entirely. See `S-83`; it is the most
> important fix in the module and it also means the admin's *"unchecked, overdue"* column is
> currently blaming teachers for a query.

### D-31 · Admin sees school / class / subject, and drills to one student's detail
**Module:** homework · **Status:** DECIDED — **mostly built; the drill-down is unreachable**

School-wide, class-level and subject-level completion; and where the admin wants detail, one
student's record of which homework was missed and when.

*(verified)* `/dashboard/homework` has the roll-ups, plus *"Students who keep missing it"* named
with streaks, subjects and the responsible teacher, and a per-teacher checking table.

**The student drill-down exists as an endpoint** — `GET /homework/student/{id}` returns exactly
"which homework and when" — **and `schoolApi.studentHomework` exists in the web client, and
nothing calls it.** It is a component away from being delivered (`S-86`).

### D-32 · A screen for marking homework done
**Module:** homework · **Status:** DECIDED

A dedicated screen for marking homework — *"for yesterday's homework, we need to mark them"*.

*(verified)* This exists today as a **block on My Day** rather than a screen, and that block is
correctly placed: she is already on that screen, and one tap is the whole interaction (P1v2).

> Claude's reading, `S-84`: build the screen, but give it the job the block cannot do — **the
> backlog.** My Day keeps yesterday at one tap; the new screen holds *everything unchecked, oldest
> first, with its age* — Friday's, the two she skipped, the project due today. Two surfaces, two
> jobs. It needs `S-83` first, or it has nothing to list.

---

## Session 4, continued — 2026-07-31 (the founder's answers)

All five questions answered, plus three new mechanics: late completion, the absent child's
carried homework, and a homework screen that replaces the My Day block.

### D-33 · Late completion, on a working-day clock
**Module:** homework · **Status:** DECIDED · **supersedes the "yesterday only" queue**

- A teacher can mark homework done **at any point in time**. Nothing expires off her screen.
- Past a **long gap — 3 days** — it can only be recorded as **late completion**.
- Inside the gap she simply marks it done, or optionally marks it late.
- **Sundays and holidays are dropped** from the gap; it is a working-day count.

*(verified)* This kills the Friday-on-Monday defect (`S-83`) by design rather than by patch. The
working-day arithmetic already exists three times over — `leave.py::_working_days`,
`calendar.py::expand_blocked_dates`, and the planner's effective-teaching-days engine. **Use one
of them** (`S-96`); a fourth definition of "working days between two dates" is this codebase's
signature bug.

> ⚠️ Claude's caveat, `S-95` — **there are two different latenesses here and only one of them is
> about the child.** A teacher who collected the notebooks on Tuesday and got round to recording
> it on Friday produces a "late" that is hers, not the student's. Forcing every student to "late
> completion" because the *teacher* was slow is precisely the mistake `not_checked` was invented
> to avoid. Recommendation: past the threshold the default wording is **"recorded late"** (a fact
> about the record), the teacher can still say a specific child genuinely handed it in late, and
> `checked_at` vs the deadline continues to carry the teacher's side separately. Both go to the
> admin, which is what `D-38` asks for anyway. `Q-44`.

### D-34 · An absent child's homework is not a miss — it is carried
**Module:** homework · **Status:** DECIDED · **answers `Q-38`**

Neither of Claude's two options. The founder's answer is a third state:

- The days are **dropped** for a child who was absent — it never counts as a miss.
- The homework becomes **pending** for that child.
- **When he returns, the teacher checks whether it is done** and marks it.
- Resolution is **the teacher's call**: make him do the backlog, or set him fresh work instead.

> This needs a **waive** (`S-98`). "Give him new work instead" is a real outcome, and without a
> way to record it the pending items — and the parent's yellow (`D-35`) — never clear.
>
> And the pending state must be excluded from the streak and the *"keeps missing it"* list
> (`S-102`), the same way `not_checked` already is.

### D-35 · The parent sees an absent child's homework as yellow, pending
**Module:** homework / parent portal · **Status:** DECIDED

Shown, not hidden — **yellow** — so the parent knows class was missed and there is work
outstanding. Not red: nothing was refused.

> Consistent with `D-02`'s colour language, where yellow already means *known and being handled*
> and red is reserved for *nobody has explained this*. Worth noting the coherence — the parent is
> now reading one palette across attendance and homework.

### D-36 · My Day loses the homework block; a button opens a Homework screen
**Module:** homework · **Status:** DECIDED · **supersedes `S-84`**

Yesterday's classes are **not** shown on My Day. Instead a **button** opens a Homework screen
listing her classes and the homework given — **which day, and what it was** — with **per-student
and per-day views** a step below.

*(verified)* This removes the current My Day block, whose one-tap *"Everyone did it"* was the
P1v2 win. **The founder's own workflow description justifies it:** *"she collects the notebooks
and after the class completes she checks and marks as done in the app."* Checking is a sit-down
activity at a desk with a stack of books — not a between-classes tap — so a dedicated screen is
the better surface. Recorded so nobody later "optimises" it back onto My Day.

> ⚠️ **One thing decides whether this works: the button must carry a count** (`S-100`) —
> *"Homework · 4 to check"*. An unlabelled button is how a daily habit becomes a monthly one.

### D-37 · Homework load analytics: admin and class teacher only
**Module:** homework · **Status:** DECIDED · **answers `Q-42`; accepts `S-87`**

Homework load per class per day is shown to the **admin** and the **class teacher**. A subject
teacher sees nothing. Informational — no cap, no rota.

### D-38 · Deadline defaults to the next day, is configurable, and both latenesses reach the admin
**Module:** homework · **Status:** DECIDED · **answers `Q-41`**

- Default deadline is the **next day**; the teacher can set it further out (two days, a week).
- *"Maybe the student did it late, maybe the teacher didn't check"* — **capture both, show the
  admin.**

*(verified)* `due_date` already exists on the assignment and the teacher can already set it; what
was missing was any consequence — the queue ignored it entirely.

### D-39 · The two fences are accepted
**Module:** homework · **Status:** DECIDED · **accepts `S-91` and `S-92`**

**No marks or grades on homework** — done / didn't / partly, and quality goes in the observation
log that already exists. **No homework quota or "expected" count** — nothing that turns setting
homework into a target.

---

## Session 5 — Tasks (2026-07-31)

### D-40 · Rail-assigned tasks land on one shared board, scoped to the assignee
**Module:** tasks · **Status:** DECIDED · *(already built exactly this way)*

Every task the admin creates from an action rail goes to **one** board — **Follow-ups** — with
`task_scope='assigned'`: **a teacher sees only the rows assigned to her; the admin sees all.**

*(verified)* This is shipped: `ensure_followups_board` (`services/insights/actions.py:51`), the
`task_scope` column (`models/board.py:31`), the visibility rule (`core/visibility.py:67`) and its
server-side enforcement (`services/task.py:265`). Assignment already notifies the teacher
(`task.py:491`); claiming is off on such a board (`task.py:536`); only the owner/admin can
reassign (`task.py:575`).

> The board is **public with scoped rows**, not private — and that is load-bearing. Law 5 says an
> admin does not see private boards they aren't in, so a private per-teacher board would be one the
> admin could fire tasks into and never track again. Recorded because "make it private" is the
> obvious first instinct and it is wrong.

### D-41 · My Day gains a tasks section, below the periods
**Module:** tasks · **Status:** DECIDED · **bounded by `D-24`; consistent with `D-36` (see below)**

Under the period list, a rule, then the tasks assigned to her — **tickable in place**.

*(verified)* `MyDayOut` carries no tasks today (`schemas/classroom.py:66`), but
`HomeService.my_tasks` (`services/home.py:117`) already computes precisely this list — every task
assigned to the caller across all boards, board name included, sorted overdue → soonest → undated,
with today's completions. It is built and simply unreachable from My Day.

> ⚠️ **This is the third session to move a block on My Day, and it moves one *on* after two moved
> blocks *off*** (`D-24` kept the timesheet out; `D-36` removed homework). The rule that makes all
> three the same decision:
>
> **If the work happens on another screen, put a counted button on My Day. If the work *is* the
> row, put the row on My Day.**
>
> Homework's work is a forty-name check sheet — the block was a shortcut to a screen. A task's work
> is one checkbox; the row *is* the destination. `D-24`'s real clause survives untouched:
> **nothing goes above the periods.**
>
> Corollary: if tasks ever grow subtasks, attachments or a required note, the test flips and they
> become a counted button too.

### D-42 · Today, undated and admin-assigned in the main section; future dates collapse
**Module:** tasks · **Status:** DECIDED · *(Claude proposes one amendment — `S-108`)*

The main section holds **tasks due today**, **tasks with no due date**, and **anything the admin
assigned from an action rail**. Future-dated tasks sit under a collapsed **Upcoming** dropdown.

*Claude's amendment (`S-108`): **overdue is not "today".*** Three groups rather than two —
overdue (named, with how late) → today + undated → Upcoming. Merging late work into today's list
is how the one row that has been waiting a week vanishes into the one due at 4pm, and the admin's
Friday question is exactly about those rows. Also unaccepted: `S-109` (cap the section),
`S-110` (all boards, not just Follow-ups), `S-106` (badge who asked).

> **Amended within the session by `D-43`.** The founder's second pass narrows the section further
> than either version above: no overdue backlog and no *Upcoming* at all. `D-42`'s surviving clause
> is *"anything due today"*.

### D-43 · My Day shows a narrow window of tasks, not her whole list
**Module:** tasks · **Status:** DECIDED · **amends `D-42`; answers `Q-46` and `Q-47`**

The section holds exactly two kinds of row:

- **assigned from an action rail within the last 3 days**, and
- **anything due today**, whatever board it came from.

Everything else — older follow-ups, future-dated work, undated tasks she wrote for herself — lives
on `/tasks`, which is the module's home page and already renders all of it
(`HomeService.my_tasks`, `services/home.py:117`).

**Founder's reasoning:** *"lets not put all the overdues and all pending tasks… making it less
clutter, because we have a home page in the task module."* Correct, and it is the same instinct as
`D-36`: My Day is a prompt, not an inbox.

**What this amends:**

- **The *Upcoming* dropdown goes** (`D-42`). A future-dated task is neither due today nor, past
  three days, recent — it is precisely what "we have a home page for all the tasks" means.
- **`S-108` is accepted as a state, not a group.** No overdue *section* — the backlog is exactly
  what is being removed. But a row **inside** the window that is late still says *"due yesterday"*
  and still reads red. Late is a fact about the row; it is not a place.
- **`S-109` (cap 3–5) stands as a backstop.** The window will normally do the work; the cap stops
  a bad day from pushing her evening sessions off the screen.
- **`S-110` is narrowed and its point survives.** The list is still **not** board-scoped — "due
  today" is honoured whatever board it came from — it is *rule*-scoped. Board tabs still have no
  place on My Day.

> ⚠️ **The rule this creates: a task can leave My Day without being done.** On day four a rail
> follow-up drops off whether or not it was closed. That is the decluttering working as intended —
> and it is a silent memory hole unless the section says so. **It ends with one line:
> *"4 older tasks →"***, linking to `/tasks`. Same discipline as `D-44`'s date filter: a window
> with no way to see past it is data loss from the user's side.
>
> *Detail worth settling at build time: count the 3 days in **working days**, so a Friday
> follow-up survives the weekend. Calendar days reproduce, exactly, the bug session 4 found in the
> homework queue — Friday's work invisible on Monday.*

### D-44 · The Follow-ups board windows its read; it does not archive
**Module:** tasks · **Status:** DECIDED · **answers `Q-45`; accepts `S-103`**

`board_table` returns **open rows always**, **done rows from the last 7 days**, and everything
older behind a **date filter on the same board**. No archive state, no nightly job, nothing moved.

*(verified)* Today it returns every non-cancelled instance ever — no window, no limit, oldest first
(`services/task.py:267-271`) — while `HomeService.my_tasks` already windows done to today
(`home.py:128-135`). The board table is the outlier.

> ⚠️ **The date filter ships with the window, never after it.** A window with no way to look
> further back is data loss from the user's side, and the first time an admin asks *"what did we
> follow up on in October"* and can't find it, they stop trusting the board.

### D-45 · Stale open follow-ups get their own group — and are never auto-closed
**Module:** tasks · **Status:** DECIDED · **accepts `S-104`**

Untouched open rows are grouped — *"Stale · 6 items nobody has touched in 3 weeks"* — with exactly
two actions: **close it** or **give it a new date**.

**Never auto-close.** Silently closing *"Call Kabir Shah's parent"* asserts that a child's parent
did not need calling, and writes "handled" into an append-only history when nobody handled it.
A stale row is a true statement; a false close is not.

*This is the half of `Q-45` the founder's original question didn't cover, and it is the half that
actually kills the board: once the open list is untrustworthy the teacher stops reading it, and the
admin's whole assign-and-check loop dies without any dashboard reporting it.*

### D-46 · A follow-up carries its subject, and completing it records what happened
**Module:** tasks · **Status:** DECIDED · **answers `Q-48`; accepts `S-105`; rejects auto-close**

The task links to what it is about — student · member · period. Then the row reads
*"Kabir Shah — absent 4 days"* instead of a title string (ux-principles §3), the student's timeline
shows a follow-up was raised, and **completion asks one optional question: *what happened?***

*"Spoke to the father — fever, back Monday"* is the fact the admin wanted when they pressed the
button. Today we record the press and never the outcome (§8).

*(verified)* The link runs one way only: `followup_actions.detail` carries the `task_id`
(`actions.py:235`), but the `TaskInstance` is a title string with no reference back.

**Smallest change with the largest reach in this session** — it also gives `D-45` something to
close on and `D-47` a key to dedupe on.

### D-47 · The action rail dedupes on the open task, not on the calendar day
**Module:** tasks · **Status:** DECIDED · **accepts `S-107`**

In `_assign_followup`: if an **open** follow-up already exists for this subject, **extend or nudge
it** and report *"already assigned — due date moved"*, rather than creating a second.

*(verified)* Today the key is *(kind, subject)* **for today only** (`done_today`,
`actions.py:92-109`), so three days of absence produce three identical open rows in one teacher's
list. The daily window stays exactly as it is for `guardian_reminded`, where it is correct — the
rule differs because a message is an event and a task is a state.

### D-48 · Two verified defects are accepted for fixing as-is
**Module:** tasks · **Status:** DECIDED · **accepts `S-111` and `S-112`**

- **`S-111`** — delete the client-side re-filter on `/tasks` (`page.tsx:156`) and let the server's
  visibility answer through. It is why an **admin sees none of the follow-ups they assigned**. If
  the Today tab wants "just mine", that is a server parameter, not a second rule in a component.
- **`S-112`** — the rail's default due date becomes **org-local end of day, `all_day=True`**.
  Today it is midnight **UTC** (`actions.py:231`), so a Monday follow-up is overdue at 05:30
  Tuesday.

Also accepted: **`S-106`** — badge the rows the admin asked for (*"Priya asked · this morning"*).
No new data; `task_events` already records `assigned` with the actor.

---

## Session 6 — Exams & scores (2026-08-01)

### D-49 · One place for every test the school runs, readable at four levels
**Module:** exams · **Status:** DECIDED · *(substantially built — SC-5, 2026-07-12)*

Every test — slip test, CET, chapter test, objective, unit test, term exam — is recorded **by the
teacher who marked it**, either by **form** or by **photo**, and is afterwards readable at
**school · class · subject · student** level.

*(verified)* Built: 9 exam types on `assessment_cycles.type`; `/students/scores/[classId]` with
**Whole class | Few students**; photo → `ai/scores.py` transcribes → `score_match.py` decides
identity → review grid → `ExamService.save` writes cycle + scores + evidence in one transaction;
`growth.py` for the student, `class_analysis` for the class, `insights/exams.py` for the school.

> **The division of labour inside the photo flow is load-bearing and must survive `D-50`:**
> the model **transcribes**, deterministic code **decides**. `ai/scores.py`'s prompt says
> *"Transcribe what is printed — never invent"*, and `score_match.py` exists so a hallucinated name
> can never write a score.

### D-50 · The photo does two jobs, and only the first is required
**Module:** exams · **Status:** DECIDED · **scoped by `S-116`/`S-117`; fence open at `Q-51`**

**Required:** extract **names and scores** plus the paper's basic details. **Optional and
secondary:** check the paper. The second never blocks or alters the first.

*Claude's scoping, unaccepted:* ship the optional half as a **marking check** (`S-116`) — two
claims, both about the **teacher's paper** rather than the child's answer, both with a ground
truth: *the marks don't add up* and *a question looks unmarked*. Anything judging the answer itself
stays behind a flag, is shown only while a human is looking at the paper, and is **never stored**
(`S-117`).

> ⚠️ **Why this needs a line drawn.** Every other AI call in the product either transcribes or
> proposes a mapping a deterministic validator then checks against real data — a column list, a
> roster. **There is no roster to check "is this answer right" against.** It is the model's opinion,
> about a child, with nothing behind it. Stored once, it is one join from a report card and two from
> a parent.
>
> SPRD2 §11 fences *test authoring/conducting*; evaluation is neither, so the letter does not block
> it. `Q-51` asks the founder to decide it explicitly rather than let it drift.

---

## Session 7 — Events & dates (2026-08-01)

### D-51 · One card: today's specials, then the next seven days
**Module:** events-and-dates · **Status:** DECIDED · *(nothing built — see the defects below)*

The admin dashboard and the teacher's dashboard each get a **card**: what is special **today** on
top, **the next 7 days** under it, with a fuller view behind. The purpose is stated in the
founder's own words — *"so the school can get prepared for it"* — which makes **lead time**, not
awareness, the thing the module is measured on (`S-126`).

*(verified)* The read side does not exist. The **write** side has existed for a year:
`calendar_events` (`models/academics.py:153-180`) already holds dated rows typed `holiday` ·
`exam_block` · `event` · **`celebration`**, and Plan → Year already paints them
(`plan/page.tsx:43-48`). Its **only** consumer is the effective-days engine. An admin paints
*"Diwali"* in April and the product never mentions Diwali again.

### D-52 · Three sources feed it: birthdays, the school's calendar, the outside world
**Module:** events-and-dates · **Status:** DECIDED · **sourcing open at `Q-54`/`Q-55`**

**Student birthdays** · **the school's own calendar** · **festivals and observances from outside
the school** (Diwali, Holi, Guru Purnima, International Mother's Day).

*Claude's scoping, unaccepted:* one feed, three sources, and **one new column** (`S-121`). A
birthday is **derived** from a DOB, not stored as an event; the school's dates are
`calendar_events`, which already exists; observances are **reference data**, not org data. If this
module ends up with three new tables, it was designed wrong.

> 🔴 **Two things must be true before any of it renders, and neither is true today.**
>
> **1 · `students.date_of_birth` does not exist** — not on `students`, not on `users`, not on
> `memberships`, and not in the roster importer's synonym list
> (`services/roster_import.py:23-48`). A birthday card with no birthdays is not an empty state, it
> is a broken screen (`Q-59`).
>
> **2 · Recording a festival currently shrinks the teaching year.**
> `CalendarEventCreate.affects_teaching` defaults to `True` (`schemas/calendar.py:17`) and the
> paint UI **never sends the field** (`plan/page.tsx:82-90`). Painting *"Celebration — Guru
> Purnima"* on a day the school is **open** silently removes a teaching day from every
> class-subject forecast in the school. This is a live defect independent of the module — and the
> module makes it worse, because its whole purpose is to give schools a reason to record more
> dates.

> **The fence this module needs (`S-122`).** An **observance** is informational and never
> subtracts a teaching day; a **holiday** is the admin's declaration and does. A festival
> catalogue must therefore **never write `calendar_events`**. The bridge between the two is an
> explicit *"Add to school calendar"* button that opens the normal event sheet and forces the
> open/closed choice. If a pack ever auto-creates rows, it rewrites the denominator behind every
> plan forecast in the product, unattended.

---

## Session 6 (second pass) — Exams & scores, continued (2026-08-01)

### D-53 · The teacher verifies the scan and **locks** it; a locked exam is the record
**Module:** exams · **Status:** DECIDED · **gives `verified_by` a meaning it never had**

After the scan is reviewed, the teacher **verifies and locks**. The locked exam is the trusted
record — for the analytics, for the report card, and (per `D-54`) as the training label.

*(verified)* There are **two** notions of "confirmed" in the code today and neither does this job:

- `score_captures.confirmed_by_member_id` / `confirmed_at` **are** set — by `finalize_for_exam`
  and `confirm` (`services/score_capture.py:246,275`). That records *the photos were reviewed*.
- `assessment_scores.verified_by` is **never set by the exam flow** (`services/exams.py:275`), so
  the scores feed's *"· verified"* badge cannot light up for any SC-5 exam. Session 6 filed this as
  defect §4.5 with no obvious owner. **`D-53` is the owner.**

> ⚠️ **The lock has a second job the first one hides** (`S-136`). `ExamService.save` is a **full
> delete-and-reinsert** of a cycle's scores (`exams.py:270-279`). So today a mark corrected in
> November silently replaces the mark confirmed in July, with no record that it ever differed.
> That is survivable for a report card and **fatal for `D-54`** — the "human truth" half of every
> training pair would keep changing after the fact. The lock is what freezes it.

### D-54 · Store the images **and** the validation data, as a future training corpus
**Module:** exams · **Status:** DECIDED · **future use, present capture**

Every scan keeps: **the page images**, **what the model read**, and **what the human corrected it
to**. Explicitly for training our own model later — not a feature of this version, but the data has
to start accumulating now, because it cannot be recovered retrospectively.

*(verified)* Two of the three are already there and survive:

- images — `score_capture_pages`, R2 object keys, kept forever as evidence (P5);
- the model's read — `parsed_rows` (transcription + match confidence + candidates) and
  `parsed_meta`, and **nothing clears them on confirm** (only re-uploading a page does,
  `score_capture.py:167`).

**The missing third is the human's answer.** The corrected marks go to `assessment_scores`, which
is a different table with a different lifecycle, re-written in full on every edit. So the pair
exists only by inference, and the inference decays. See `S-136`/`S-137`.

> ⚠️ **This is the first data in the product whose purpose is not running the school.** Every other
> byte serves the school that entered it; this serves us. It is children's handwriting with their
> names on it, and it belongs to the school. That does not make it wrong — it makes it a thing to
> ask for rather than assume. See `S-138` and `Q-61`.

### D-55 · Exam types are the school's own, in a new column
**Module:** exams · **Status:** DECIDED · **answers `Q-49`**

A school records the exam types it actually runs — *CET*, *pre-board*, *cycle test* — stored in a
**new column** rather than by widening the existing nine-value list.

*(verified)* `assessment_cycles.type` is a CHECK constraint over 9 values
(`models/assessments.py:57,84`), so "CET" cannot be saved today.

**Keeping `type` and adding beside it is the right shape**, and better than session 6's proposal to
drop the constraint: existing code branches on `type` (`diagnostic` routes to the skill grid,
`band_test` is admin-only, `grid_only` in the feed), so `type` stays the **system kind** the code
reads, and the new field is the **school's word** that people see and filter by.

> **One rule keeps that from becoming two sources of truth** (ux-principles §9): the school's word
> is what every screen **displays and groups by**; the system kind is read **only by code**, never
> rendered. If an analytic ever groups by `type`, the two have diverged.
>
> *Claude recommends the new field be a small `exam_types` **table** rather than a bare text column
> (`S-135`) — the exam type is the grouping key for a year of trend lines, and free text drifts in
> spelling ("CET" / "C.E.T" / "Cet") in a way a timesheet bucket never has to. It also carries
> `scale` (`S-114`) for free, so the teacher picks one thing instead of two. This contradicts the
> "three nullable columns" line from session 6 — the table is worth it; the bare column still
> works if the cheaper build is preferred.*

---

## Session 7 (second pass) — Events & dates: DOB, suggestions, locking (2026-08-01)

Closes `Q-57` and `Q-59`, reshapes `Q-54`, and replaces the module's centre of gravity: the
calendar is no longer *a thing the school records*, it is **a stream of suggestions the school
approves**.

### D-56 · Student DOB at setup; staff DOB optional and self-entered; guardian DOB not yet
**Module:** events-and-dates · **Status:** DECIDED · **closes `Q-59` and `Q-57`**

- **Students** — `date_of_birth` is **captured during setup**, with the rest of the roster. It is
  part of the data the school hands over, not something chased later.
- **Staff** — the columns exist but are **nullable and optional**. Filled later, or by the teacher
  from their own profile screen. Nobody is blocked on it and nobody is nagged for it.
- **Guardians** — **not captured in this version.** Later, if ever.

*Claude's note:* this is the right split, and the asymmetry is the point. A student DOB has a
second job — the admission register and board registration need it anyway — so asking for it at
setup costs the school nothing it wasn't already doing. A staff DOB has exactly one job, which is
to be wished, so it can only ever be volunteered. `S-133` still holds on both: **day and month on
shared surfaces, never an age.**

### D-57 · The calendar is a stream of **suggestions**; approval is the commit
**Module:** events-and-dates · **Status:** DECIDED · **this is the module's spine**

> *"In the setup stage a brief version of the calendar is decided. No matter how well the year is
> planned it keeps on changing."*

So the product stops treating the year calendar as something fixed in April. Dates arrive
continuously as **suggestions for that day** — from the catalogue, from the school's own calendar,
from birthdays — and **nothing they imply happens until the admin approves it**. On approval the
date is **locked into the school's own calendar** and becomes real.

This retires the *"Add to school calendar"* button from `S-122` and replaces it with something
better: the fence is no longer a button somebody must remember to press, it is **the only path
that exists**. A suggestion cannot become a `calendar_events` row by any other route.

### D-58 · Approval has three levels, and the admin picks one
**Module:** events-and-dates · **Status:** DECIDED

1. **Lock the whole day** — school closed.
2. **Lock specific periods** — e.g. periods 1–2 for a function, teaching resumes after.
3. **School runs as usual** — celebrations at **assembly or prayer time**, no teaching lost.

> ✅ **All three already exist in the schema, and the engine already prorates them**
> *(verified)* — this is a UI over V2-P7, not new data (`S-142`):
>
> | Level | Fields | What `effective_periods` does (`services/calendar.py:84-131`) |
> |---|---|---|
> | Whole day | `affects_teaching=True`, `blocks_periods=NULL` | day drops out of the week entirely |
> | Specific periods | `affects_teaching=True`, `blocks_periods=[1,2]` | day contributes `1 − lost/periods_per_day` |
> | Runs as usual | `affects_teaching=False` | full teaching day, nothing lost |
>
> **And this approval sheet is the fix for the module's live defect.** The reason painting a
> "Celebration" silently deletes a teaching day today is that the paint UI never sends
> `affects_teaching`. `D-58` makes that choice the *central act* of the flow, so the bug cannot
> survive the feature.

### D-59 · No plan adjustment in this version — the teacher marks the class instead
**Module:** events-and-dates · **Status:** DECIDED · **scope fence for v1**

Approving a lock does **not** redistribute anybody's plan. What happens instead:

- the **admin** locks the day or the periods;
- the **teacher** blocks that class, or that timesheet cell, **against that reason** — so the
  record says *why* the period didn't happen rather than showing a hole.

Rewriting a year plan around a newly approved holiday — *"given classes and teachers, year plan
adjusted"* — is deliberately a **later version**.

> ⚠️ **Two halves are being conflated here, and only one of them is deferrable (`S-143`, `S-144`).**
>
> **The forecast half is not optional and already happens.** `effective_periods` is computed live,
> so the moment three days are locked for Diwali, every class-subject's remaining capacity shrinks
> and **RAG colours move across the school** — with no explanation on the syllabus board. A
> principal who locks three days and watches six subjects turn amber will believe the system
> broke. **Therefore the approval sheet must show the cost before it is approved** (`S-143`).
>
> **The plan-rewriting half is already forbidden by P2** — *"the approved plan is locked;
> re-forecast is computed from baseline + logs + remaining effective periods, never stored as
> mutated plan rows."* So this deferral costs nothing and should be recorded as **permanent, not
> "next version"** (`S-144`). What a later version can legitimately add is a *proposal* the admin
> approves — never an automatic rewrite.

### D-60 · The catalogue is fetched from the internet and **stored in our database**
**Module:** events-and-dates · **Status:** DECIDED · **sourcing open at `Q-63`**

We fetch and store: **general calendar data**, **state-wise school holidays**, **international
observance days**, and **dates for all religions**. Every school reads the same catalogue; the
school's own calendar is only ever written by `D-57`'s approval.

**This supersedes `S-123`'s "a checked file in the repo."** The founder is right and the reason is
scale: 28+ states × per-year × multiple traditions is too much for a hand-edited file, and it must
be updatable without a code deploy.

*Claude's reconciliation (`S-149`):* store it as **platform-level data, not org data** — no
`org_id`, no RLS, `require_super_admin` on every write, exactly the `demo_requests` / EN-1 shape
from V3-P0. The dev curates once a year for everybody; a third tab joins **Schools · Enquiries**
on `/platform`. That keeps the human review `S-123` was protecting, drops the deploy, and means
one correction fixes every school at once.

> ⚠️ **Storing it in a database does not make it true.** Whatever fills the table still has to be
> right, and a wrong Diwali date is a school decorating on the wrong day *because our screen said
> so*. Hence `Q-63`, and hence `S-150` — every suggestion carries **where it came from**, so the
> admin approving it can see whether it is a state gazette or an internet list.

---

### D-61 · The catalogue is narrowed by what setup already asks the school
**Module:** events-and-dates · **Status:** DECIDED · **closes `Q-55`, narrows `Q-63`**

At setup the school gives its **school code**, **address**, and **board** (CBSE / state board).
Those three narrow the catalogue: **address → state** picks the state holiday list, **board**
picks the academic calendar convention. A school never chooses a "region" as a separate question.

*Claude's note — this is the right answer for the reason `Q-55` was worried about.* The draft
question was going to ask a school to declare a region or a tradition, and *"asking a school to
declare its religion at setup is a question with a cost."* `D-61` avoids it entirely: the scoping
falls out of **facts the school is already giving for other reasons**. Address and board are
administrative, unloaded, and already needed.

Consequences to build to:
- `S-150`'s provenance line becomes concrete — *"Suggested · Telangana state holiday list"* is
  derivable, not hand-waved.
- Faith-specific dates are still **suggestions, never assumptions**. A CBSE school in Hyderabad
  gets the Telangana list plus the major national/religious set; it approves what it observes and
  dismisses the rest (`S-148`, permanently).
- **Research timing:** `Q-63` is deliberately **deferred to implementation** — the founder will
  say when. It is scoped, not scheduled, and it blocks only the catalogue (build-order step 7).

---

## Session 8 — Fee collection (2026-08-01)

### D-62 · This module is read + remind. The collection system is not touched.
**Module:** fees · **Status:** DECIDED

> *"We already have a perfect fee collection system, and upon that I need a section for admin."*

So nothing in this module writes money. No new payment capture, no gateway, no receipt redesign,
no change to `/fees/[id]`. What gets built is **the read side for the person who answers for the
money**, plus two actions that produce phone calls.

*(verified)* The system genuinely is built: 5 tables, ported money math, append-only
`fee_transactions` where undo is a compensating row (law 3), and a per-student counter screen that
works. The gap is entirely above it.

### D-63 · Only the admin sees fee data
**Module:** fees · **Status:** DECIDED · **standing fence, restated**

Unchanged from `CLAUDE.md` and `ux-principles.md`'s hard-fence table. Not a summary, not a total,
not a chart, not a Lucy tool, not a widget.

*(verified)* Holds today — `/fees` endpoints are admin-only, the dashboard's fee card is gated on
`m.is_admin`, and the web fees block is computed client-side so the figures never reach a
teacher's payload at all.

> 🔴 **`D-65` collides with this decision.** See the warning under it.

### D-64 · The admin gets a collection board: quarter-wise, by class, by student
**Module:** fees · **Status:** DECIDED

Due collection and pending fee, analysed the way the school actually collects — **quarterly**.
`QTR1 collected / pending`, then **which class** is behind, then **which student has not paid**.

*(verified)* Two of the three levels are missing and one is unreachable:

- `FeeSummary` is **4 year-wide scalars** — no quarter, no class, no trend;
- 🔴 **`GET /fees/overdue-students` already returns the named list** — student, class, amount,
  earliest due date, oldest first — **and nothing in the web app has ever called it.** The
  founder's *"which student has not given yet"* is computed on the server today and is invisible.

*Claude's scoping:* the board **replaces the `/fees` landing page** rather than becoming a ninth
dashboard tab (`S-152`) — `/fees` exists, its landing page is the weakest screen in the product,
and a second fee screen would immediately disagree with the first. And a **quarter is a due-date
window**, not an instalment number and not a label (`S-153`, `Q-67`) — schools give juniors 2
instalments and seniors 4, so *"instalment 1"* is a different quarter for different classes and
the school-wide figure would be nonsense.

> 🔴 **Defect that changes what this board can honestly say (`Q-68`).** `student_fees.opening_dues`
> — last year's unpaid balance — is **excluded from `total_fee`, from `collected`, from
> `overdue_amount`, and from `status`**, which the model states outright: *"status is still driven
> by instalments only."* So a student carrying ₹20,000 from last year with this year's instalments
> paid reads **`paid`**, and the defaulter list silently omits the worst defaulters. For a module
> whose entire purpose is *what is owed*, this is the defect that matters most.

### D-65 · Two actions on a defaulter: remind the parent, assign a teacher to follow up
**Module:** fees · **Status:** DECIDED · 🔴 **fence collision at `Q-66`**

The admin either messages the family directly, or hands the family to a teacher — normally the
class teacher, who has the relationship.

*(verified)* The mechanism exists and needs no new table: `followup_actions` is append-only with a
free `kind` / `subject_type` / `subject_id` (`models/insights.py:106-128`), and it was built for
exactly this — so every row can render *"reminded 9:12am · Priya"* and the same family is not rung
three times in a morning (ux §7).

> 🔴 **This decision and `D-63` cannot both be taken literally.** If the task says *"Call Kabir's
> father — ₹12,000 overdue"*, the teacher now sees fee data and the non-negotiable is broken by the
> feature built on top of it. `Q-66` decides it.
>
> *Claude recommends `S-154`(a): **the task names the family and the subject, never the amount.***
> The parent already knows the number; the teacher does not need it to make the call. And the
> reason for the fence is not confidentiality for its own sake — **a teacher who knows which
> families are behind on fees treats those children differently**, and every child on that list has
> done nothing wrong.

Also required, from `ux §8`: the follow-up records **what the family said**, not that a button was
pressed. *"Spoke to the mother — paying after the 15th"* is what makes the row go away; *"reminded"*
just re-asks next week (`S-161`).

### D-66 · The parent gets a notification and a reminder on their portal home
**Module:** fees · **Status:** DECIDED · **first fee surface a parent has ever had**

A notification, and a **block on the parent's Today screen** — the founder's *"shown on their
homepage dashboard as a reminder"*.

*(verified)* There is **nothing** today: no fee field anywhere in `parent_portal.py`,
`schemas/parent.py` or `parent-api.ts`, and `NOTIF_TYPES` is a CHECK constraint with no fee value,
so this needs a migration widening it — the `substitute` precedent.

*Claude's constraints (`S-156`, `S-160`), because this is a money message to a family:*

- **one line, a date, and what's already paid.** Not a ledger — that is the office's screen.
- **the block does not render when nothing is due.** A parent who owes nothing must never see a
  fee section; its presence alone reads as a demand.
- **at most one reminder per instalment per week**, however many staff press the button; **quiet
  hours** 8am–8pm; **it stops the instant the payment lands**; `notify_opt_out` honoured like every
  other guardian message.
- **never red, never a warning icon, never the word defaulter.**

> A parent reminded three times in a morning about money will not read the fourth message about
> their child's attendance. Getting the manners wrong here damages every other channel the school
> has.

**Still out:** any online payment or parent write — `PC-1` is read-only and `D-62` is read + remind.

---

## Session 9 — Bands, the A/B/C support programme (2026-08-01)

### D-67 · A band is a programme, not a label — and the measure is movement
**Module:** bands · **Status:** DECIDED

> *"the whole purpose of this module is to track student growth and improve his performance … this
> is like a program"*

Assess → group → assign an owner → work → re-assess → **move**. Every screen in the module answers
*did anybody move*, and the distribution — how many are in C — goes underneath, because it is a
photograph of a decision already made and it looks identical in a school where nothing has changed
for a year (`S-169`).

*(verified)* The tier itself is built and correct: `student_bands` is append-only with `set_by` and
a `note`, term-scoped, never updated in place (`models/assessments.py:117-137`), and
`/students/[id]` already renders the history as *"C (12 Jul) → B (30 Jul)"*. **What does not exist
is any notion of a lifecycle** — see `D-71` and the two red defects under it.

### D-68 · The band is per **subject**; English, Hindi and Maths to start; the set is configuration
**Module:** bands · **Status:** DECIDED · **the module's biggest change**

> *"right now I want only English Hindi Math subjects to be monitored and in the config setting we
> can add or more subjects"*

*(verified)* Today a child has **one overall letter**. `categorize_from_cycle` sums every score in
a cycle into a single percentage and writes one tier (`assessments.py:339-353`), and every read
path — `_current_tiers`, `current_band_map`, `band_board`, `recommendations._current_tier` — filters
`scope_skill_area_id IS NULL`, the overall row.

> 🔴 **This is not only a missing feature, it is live wrong behaviour.** A child who reads two years
> below grade and is fine at arithmetic gets one letter that describes neither — and the daily check
> generator then hands him easier *maths* he doesn't need while his English goes untouched.
>
> The scope column **already exists** (`student_bands.scope_skill_area_id`) and has never been
> written by any code path. `S-173`: this is a rewrite of the read path, not an added column, and
> the overall letter should be **retired** rather than kept beside the per-subject ones — two
> definitions of "Kabir's band" is the defect this folder has found in five consecutive modules
> (`Q-71`).

### D-69 · Each band has a written descriptor, per subject — the help doc *is* the standard
**Module:** bands · **Status:** DECIDED

> *"there will be a guide of characteristics of each band like a help doc, so each B band child
> should have this ability"*

*(verified)* **Nothing like this exists anywhere** — no table, no column, no seeded text. Today a
tier means *"scored under 50% on whatever the last test happened to be"*, which is why two teachers
in one school band the same child differently and neither is wrong.

*Claude's constraints:* the descriptor renders **wherever the letter renders** (`S-166`) — a letter
alone is a label, which is exactly what P4 says a band must not become — and it opens **beside the
control** on the assessment screen, not in a help menu. And ship it **pre-written and editable**
(`S-175`): 3 subjects × 3 bands is nine texts; per grade it is seventy-two, and nobody writes
seventy-two.

### D-70 · Two routes into a band: a test's marks, or the teacher's own assessment
**Module:** bands · **Status:** DECIDED

> *"grouping is based on marks of an assignment or by teacher manual observations"*

Both are first class, and **which one produced a row is recorded on it** — *"band test: Term 2
Diagnostic"* or *"teacher assessment: Priya"*.

*(verified)* Both mechanisms exist: `categorize_from_cycle` (one tap from a band test) and a manual
`set…` dropdown per child. What is missing is the descriptor to assess *against* (`D-69`) and the
record of which route was used.

> 🔴 **One of the two existing routes is dangerous and should be scoped or dropped.**
> `apply_band_suggestions` re-bands a whole class from `_latest_pcts`, which takes each student's
> **most recent cycle with scores — whatever it is** (`assessments.py:224-249`). A five-mark Hindi
> slip test on Tuesday can move eleven children between support tiers with one tap. Same family as
> `S-114`.

### D-71 · Every C-band child has an assigned teacher who owns moving them to B
**Module:** bands · **Status:** DECIDED · 🔴 **already implemented as a dead link**

> *"for every C band child there will be a teacher assigned, and it is her responsibility to make
> the child come to B band"*

> 🔴 **Verified defect 1 — every intervention in every real school is created unassigned.**
> `create_intervention` takes its assignee from `school_classes.class_teacher_member_id`
> (`assessments.py:546-551`), and **no screen in the product sets that field** — `createClass`
> doesn't send it and `updateClass` doesn't exist (`class-teacher.md` §1, verified 2026-07-30). The
> checklist tasks are created, land on a board with no assignee, and nobody is responsible. The
> founder's decision is already in the code, and it has never once worked.
>
> 🔴 **Verified defect 2, and it is the one that matters most — an intervention can never be
> finished.** `Intervention.status` allows `active|achieved|dropped`; there are exactly two
> intervention endpoints, `POST` and `GET` (`endpoints/assessments.py:249-271`), and **nothing
> anywhere updates the status.** Worse, `recommendations._intervention_students` filters
> `status == 'active'` (`recommendations.py:102-107`), so **a goal achieved in July keeps injecting
> a targeted daily check into the period card in March.** The single loop this module exists to
> close is the one thing the code cannot do.
>
> 🔴 **Verified defect 3 — fourth instance of "built, wired into the client, called by nothing".**
> `schoolApi.studentInterventions` exists (`school-api.ts:415`) and no component calls it. The
> report card shows the tier and the tier history and never the plan attached to them. After
> `S-86`, `S-74` and the fees defaulter list, this pattern is now a standing packet-close check.

*Claude's scoping:* the owner is per **(child × subject)**, defaulting to the subject teacher of his
class (`S-168`) — "assign a teacher to a C child" is ambiguous the moment a child is C in both
English and Maths (`Q-72`). And the owner is assigned **at the moment the C list first exists**,
straight after a class is filed, because that is the only moment anyone is thinking about it.

### D-72 · The owner logs progress per child, and the child is periodically re-assessed
**Module:** bands · **Status:** DECIDED · **cadence open at `Q-73`**

> *"for each student she can enter the logs today they did this and that and maybe weekly or
> sometime we evaluate and access them to improve"*

> ⚠️ **The daily log is the highest-risk thing in this module, and it will be dead by week three
> unless the page opens already written.** A free textarea per child per day is a compliance chore,
> and P3 says a capture surface must give before it asks.
>
> **`S-164` is the answer, and it costs nothing:** a C child's week is *already recorded* by
> teachers doing their normal work — `lesson_observations` (needs_work / excellent + note,
> exception-only), `check_results`, `homework_results`, `attendance_exceptions` and
> `session_student_logs`. The child's page **opens with the week filled in** and asks only for what
> she alone knows: one line about what she actually did.
>
> **`S-165`:** make the **weekly check-in** the unit — *worked on · what changed · what's next ·
> ready to re-test* — and let the daily note be the exception. Six children × 40 seconds on a
> Friday. It is also the only thing that produces the movement evidence `D-73` reports on. *The
> founder said "maybe weekly or sometime"; making that choice now decides whether this module is
> open in November* (`Q-73`).

**`S-167`, required:** the **exit criterion is written when the child enters**, not judged at term
end — *"moves to B when he reads 60 wpm with ≤ 3 errors, twice running."* Without it the owner is
scored on a judgement she also makes, and no child ever formally exits.

### D-73 · The admin sees the programme by class and by subject, with reports
**Module:** bands · **Status:** DECIDED

> *"there will be report and capturing the data in admin tab for each class and the subject"*

*(verified)* `/students/bands` today is three columns of names and a count
(`students/bands/page.tsx:73-112`). It cannot say who moved, who owns a child, or who has been C
since April — which are the four questions the programme is about.

*Claude's scoping:* it **replaces the bands landing page** rather than becoming a ninth dashboard
tab — same reasoning as the fee board (`S-152`): a second screen about the same subject will
immediately disagree with the first. The admin overview gets **one named row**, not a chart.
Headline order is `S-169`: *moved up · slipped · **stuck** · not yet assessed*.

> **`S-170`, and it is a fence, not a preference: do not rank teachers by children moved.** It is
> the `D-25` timesheet rule again — a support log that can cost a teacher an appraisal becomes a
> support log that flatters her, and the children handed to the best teacher are by construction
> the hardest ones.

### D-74 · Settings holds the rules — monitored subjects, descriptors, thresholds, per subject
**Module:** bands · **Status:** DECIDED

> *"in the config setting we can add or more subjects and rules and assessment test and condition
> for each band of each subject can be added there"*

*(verified)* Today the thresholds are **two numbers for the whole school** —
`organizations.band_a_min` / `band_b_min`, default 75 / 50 (`assessments.py:269-280`) — so English
and Maths are assumed to be marked on the same scale. Per-subject rules mean that pair moves onto a
per-subject row (or onto the descriptor itself).

**Still out of this module:** any parent-facing tier (P4, restated because this module multiplies
the surfaces a letter could leak — `Q-75` asks whether *"extra support"* may ever be said at all) ·
IEP / diagnostic framing · test authoring (`S-171` — the re-assessment is a `band_test`, a cycle
type that already exists) · per-student photo evidence (P5) · a second daily-work generator
(`S-172` — the period card already differentiates by band with zero setup).

---

## Session 9 (second pass) — Bands: the three answers (2026-08-01)

Closes `Q-71`, `Q-72` and substantially `Q-74` — the three blockers named at the end of the first
pass. The module is **finalised**; what remains are small questions that don't block a build.

### D-75 · The band is per subject, and there is no overall letter
**Module:** bands · **Status:** DECIDED · **closes `Q-71`, option (a)**

> *"this categorization is based on subject so child good at math will be in A band in math but
> poor at Hindi will be assigned to C"*

A child has an English band, a Hindi band and a Maths band. **No fourth number.** Nothing computes
or displays a blended tier, because a child who is A in Maths and C in Hindi would carry an overall
B that describes no part of him — and it would land on the directory chip, the most-seen band
surface in the product.

*Consequence, `S-186`:* where one chip is genuinely all there is room for, render **"C · Hindi"** —
the lowest band with the subject that earned it — never an average and never a bare letter.

> **This is cheaper than it looks.** `categorize_from_cycle` already refuses org-wide cycles and
> runs on a class-scoped test; SC-5 exams are already class × subject. The change is that it writes
> the band **scoped to the cycle's subject** instead of overall — and where a cycle carries several
> subjects (a term exam), it groups the scores by `subject_id` and writes **one band row per
> subject in one pass**. A term exam re-bands a child in every subject at once, which is exactly
> what a school means by it.

### D-76 · Re-banding happens on a test — a dedicated band test, or any test the teacher promotes
**Module:** bands · **Status:** DECIDED · **closes `Q-74`; reshapes `D-70`**

> *"for the band evaluation there will be separate test and based on that test the reband should
> occur and also teacher can consider one of the normal CET or slip test to mark as band exam test
> and its upto her choice"*

Two clean halves, and the second one is the good idea:

- **Entry into the programme** may be a test *or* the teacher's own assessment against the
  descriptors (`D-70` stands) — in week two of the year there is no test to read.
- **Movement between bands is always a test.** Either a test set for the purpose, or an ordinary
  CET / slip test / chapter test that the teacher **promotes** to be the band-deciding test for
  that subject. Her choice, on the test she thinks is representative.

> **This defeats the objection I raised against test-only rebanding in `Q-74`.** The reason
> test-only looked weak was rigidity — a child who plainly reads fluently would sit in C until the
> term's exam. Promotion removes that entirely: the teacher marks next Tuesday's slip test as the
> band test and the move happens. And it makes every band row **evidenced by construction**, which
> is what `S-178` was trying to achieve procedurally.

*Claude's constraints, because promotion is a real mechanism and not a checkbox:*

- **`S-182` — promotion is a flag, never a type change.** Re-typing a slip test to `band_test`
  would delete it from the exam analytics that already count slip tests. It must be a separate
  mark on the cycle recording **who promoted it and when**, leaving `type` alone. *(Note for
  whoever builds it: this lands in the same column region as `D-55`/`S-135`'s school-owned exam
  types — do them together or they will fight.)*
- **`S-183` — delete `apply_band_suggestions`.** 🔴 With explicit promotion, the implicit route —
  re-band the class from *each child's most recent cycle, whatever it happened to be* — is
  redundant **and** is defect 5 of the first pass. Two paths to the same outcome, and the one
  nobody chose is the dangerous one. This decision is what makes deleting it safe.
- **`S-184` — a promoted test must be locked, and its size must be on screen.** `D-53` gives an
  exam a verify-and-lock; an unverified transcription must not move a child between support tiers.
  Show **what it was out of and how many sat it** at the moment of promotion, and *warn — never
  block* — on a five-mark test or a half-empty room. Same shape as SF-1's leave policy: flag it and
  let the teacher decide, because a validator that refuses a legitimate case is a rule staff route
  around.
- **`S-187` — a promoted test re-bands one subject.** Promoting 7-A's Maths slip test moves Maths
  bands and nothing else. Obvious, and it must be written down or someone will re-tier the child.

> ⚠️ **One permission detail, found while verifying the above.** `ExamService.save` today refuses a
> `band_test` from anyone below admin — *"`if body.type == 'band_test' and not m.is_coordinator_up`"*
> (`services/exams.py:212`) — and every band write is admin-only (`require_coordinator_up` on
> `/bands` and `/bands/apply-suggestions`). The founder's *"it's up to her choice"* therefore
> **changes who may move a band**: promotion is a teacher's action. Either the promotion flag is
> deliberately teacher-allowed while the dedicated band test stays admin-only, or the module quietly
> keeps doing what it does now, which is nothing. Decide it when step 3 is built — it is one guard,
> but it is the guard that decides whose product this is.
>
> *(Also verified: `save` lets an edit rewrite `cycle.type` outright, `exams.py:251` — a second
> reason promotion must be its own flag rather than a type change.)*

### D-77 · One owner per subject
**Module:** bands · **Status:** DECIDED · **closes `Q-72`, option (a)**

> *"one owner per subject is the best way to go"*

The owner is per **(child × subject)**, defaulting to the subject teacher of his class. Kabir C in
English and C in Maths has two owners, and each one knows exactly what hers is — rather than a
class teacher filing a weekly check-in that says *"spoke to the English teacher"*.

*Consequences to build to:*

- A child appears on **two** `/support` lists, grouped by subject on each.
- **`S-188` — every row that reports a stuck child must name the subject**, or two owners will each
  assume the other is handling him. *"Kabir Shah — Hindi, owner Priya"*, never *"Kabir Shah —
  owner Priya"*.
- The daily check generator gets **more accurate for free**: `_generate` already runs per
  class-subject, so reading the band **for that subject** means the English period finally gives
  the easier route to the children who can't read, instead of to whoever the blended letter caught.

**The module is finalised.** Remaining questions — `Q-75` (does a parent ever hear anything),
`Q-76` (descriptor grain), `Q-77` (now trivially (a): subject, not skill), `Q-78` (what band A
gets), `Q-79` (narrowed to the **entry** assessment only), `Q-80`, `Q-81` — none of them block the
build order in [`modules/bands.md`](modules/bands.md) §10.

---

## Session 10 — v1 scope decisions (2026-08-01)

Answers to `docs/v1/BLOCKERS.md`. These are **scope and fence** decisions rather than module
design — they say what lands in v1 and, in two cases, they move a standing fence.

### D-78 · Payroll is deferred; the staff **month summary** is not
**Module:** payroll / staff · **Status:** DECIDED · **defers `D-05` `D-06`; keeps their input**

> *"I agree lets defer payroll but I want proper attendance and leave system capturing so I have
> number of days the teacher worked out of working days, so I have information of the staff month."*

No salary figure, no money on any screen. What v1 **does** ship: half-day (AM/PM) and late on
staff attendance (`D-04`), and a **per-member month summary** — days worked out of the month's
working days, leave used, leave balance — for the admin (all staff) and the teacher (herself).

That figure is the entire input a payroll would be computed from, so v2's payroll is a small
packet rather than a restart. `Q-05`–`Q-08` stay unanswered and stay deferred.

### D-79 · The observance catalogue **is** in v1 — because the date is editable at approval
**Module:** events-and-dates · **Status:** DECIDED · **overrules the v1 recommendation to cut it**

> *"Don't worry about wrongly displaying the Diwali date from our side, because it is just a
> reminder. Once they approve they can change the date as needed or fix it — usually Christmas will
> be given as a holiday but the celebration is done way before. We will have that kind of
> flexibility… I just want this feature so the product feels alive."*

This defeats the objection that killed it in the plan's first draft, and it does so structurally
rather than by accepting risk: **a suggestion is never a date, it is a prompt to pick a date.**

Consequences to build to:

- The *Approve this date* sheet (`D-58`) gains an **editable date** — the observance's date is the
  default, not the commitment. Christmas the *holiday* and the Christmas *celebration* are two
  approvals on two dates from one suggestion.
- Each suggestion carries **which type it is becoming** — holiday · celebration · event — and the
  three lock levels stay exactly as `D-58` defines them.
- **Provenance stays on the row** (`S-150`), so an admin can see whether a date came from a state
  gazette or an internet list before they commit to it.
- `Q-63`'s research still happens, **before this module is implemented**, not before v1 starts.
  The founder's words: *"we will have intense research before implementing this module."*

### D-80 · The exam module is **photo-first, per student**, with two tabs
**Module:** exams · **Status:** DECIDED · **replaces `D-50`'s "optional second job" framing**

> *"After the teacher conducts the exam and corrects the papers, she opens our app and takes a
> picture of each student's paper. Once all the photos are added we analyse with AI and write down
> the marks for each detected student, and the teacher can adjust them — or else enter manually one
> by one. For unreadable papers we give the option to enter and map details for that photo."*

The flow, and **all of it is v1**:

1. **Capture** — a photo per student's marked script, added over the course of a sitting.
2. **AI reads** — the marks, and the identity, from the paper it is already looking at.
3. **The teacher adjusts** — the review grid, which already exists and already works this way.
4. **Manual is first class** — one-by-one entry is a path, never a degraded fallback.
5. **Unreadable page → map it by hand** — the page is kept and the teacher attaches the student and
   the marks herself. A page we cannot read must never become a page we discard.

Then, on an exam: **two tabs**.

| Tab | What it is |
|---|---|
| **Score** | Just the numbers. The roster and their marks. |
| **Report** | The analysis — topics covered, who is strong and who is struggling, which questions were most often wrong, per-subject summary. |

> **The division of labour from `D-49` survives and is not negotiable:** the model **transcribes**,
> deterministic code **decides**. `score_match.py` is what stops a hallucinated name writing a
> score, and it stays in the path.

### D-81 · Two levels of report — the report card, and the analysis
**Module:** exams · **Status:** DECIDED · **answers the second half of `Q-53`**

> *"One is a general report like a standard report card of the school — subjects and exams of a
> student, showing just the numbers. The other is a detailed analysis — per topic and skill
> abilities and per subject summary, generated using the AI summaries."*

- **Level 1 — the report card.** Standard, familiar, numbers only. Per student, and the class
  version is the same thing for everybody.
- **Level 2 — the analysis.** Per topic, skill abilities, per-subject narrative written by the
  model over figures the product already computes.

> **This is not the report-card *designer* SPRD2 §11 fences.** A fixed, well-made report card is an
> output; a designer is a layout tool with a template editor. We ship the output.

### D-82 · Per-student exam paper photos — **supersedes P5 for exam capture**
**Module:** exams · **Status:** DECIDED · **fence change**

P5 says evidence is batch and per-student photos are out; `HS-2` already made one explicit
exception for hostel session media. `D-80` makes a second, and it is a bigger one: **a photo per
student's marked script is the capture mechanism itself**, not decorative evidence.

Recorded loudly because the fence is written in `CLAUDE.md`, in `ux-principles.md`'s hard-fence
table and in SPRD2 §11, and all three now need the exception. The narrow reading holds everywhere
else: a *classroom activity* photo is still batch-only.

### D-83 · An assigned fee follow-up carries the **full** fee detail to the teacher
**Module:** fees · **Status:** DECIDED · **narrows `D-63`; answers `Q-66`, against the recommendation**

> *"The assigned teacher for that student will get all the details — the fee history, the instalment
> date, the pending amount, and the conversation history regarding that fee payment. This will be
> written in the task description and notes, so once the task is assigned the teacher knows
> everything. Mostly the follow-up person will be the admin anyway."*

`Q-66` option **(b)**, deliberately, with the reasoning that the person making the call cannot make
it usefully while blind to the number.

**What still holds** — and it must, or the fence has no meaning left:

- Only for the **specific student on an assigned task**. Never a class list, never a collection
  figure, never another family.
- **No fees nav item for a teacher**, no fee chip on any academic surface — not the report card, not
  growth, not the timeline, not the daily report, not a Lucy tool.
- The general rule in `CLAUDE.md` and `ux-principles.md` changes from *"teachers never see fee
  data"* to **"teachers see fee data only for a student they have been assigned to follow up, and
  only inside that task."**

### D-84 · Every fee conversation is recorded, per student, append-only
**Module:** fees · **Status:** DECIDED · **new requirement**

> *"Yes, I know — conversation history. I want you to maintain this in the fee management system for
> every student."*

An append-only log per student: who spoke to whom, when, and **what the family said**. It renders
on the student's fee page, and it travels into the follow-up task so the next caller is not the
fourth person to ask the same question this month.

Same shape as `demo_request_notes` / `leave_request_events` (law 3) — the newest row is the current
state, nothing is ever edited. This is also `ux §8` satisfied properly: *"spoke to the mother —
paying after the 15th"* is what makes a row go away; *"reminded"* just re-asks next week.

### D-85 · Homework: no gap threshold. Late is a status, and teacher-delay is derived.
**Module:** homework · **Status:** DECIDED · **supersedes `D-33`'s 3-day rule; answers `Q-44`**

> *"If the teacher didn't enter even one student's homework at all for 3 days, we understand the
> teacher has delayed checking. If she entered on the intended day (given date + 1) then she checked
> and some students gave it late. Let's remove the 3-day threshold… marking late is simply a status.
> The teacher can mark them done or mark as late at any time — no hard limit, editable any time.
> Simple for v1."*

This is **simpler and more honest than the design it replaces**, and it dissolves `Q-44` rather than
answering it. The two latenesses stop being one field to disambiguate and become two facts read from
different places:

| Fact | Where it comes from |
|---|---|
| **The child was late** | the teacher set the status `late`. Her judgement, her word, no threshold. |
| **The teacher was late** | derived — **nothing checked on this assignment for 3 days**. Never written into a child's record. |

Consequences:

- No working-day gap arithmetic anywhere in homework. The deadline stays *"the next day"* by
  default (`D-38`) and drives only the admin's notification.
- **Nothing ever locks.** Any homework is editable at any time, forever.
- The **admin is notified** on both signals: *this teacher has not checked anything for 3 days*, and
  *this class checked, and 9 children missed it*.
- `not_checked` keeps its existing meaning and keeps being excluded from every completion figure — a
  teacher who checks nothing must never read as a class with perfect completion.

### D-86 · Absence colour: a recorded reason is the difference
**Module:** attendance · **Status:** DECIDED · **refines `D-02`**

> *"Once the reason is added and the absent dates are allocated we show them in orangish-red,
> otherwise red… so the admin can understand how many are absent, and whether the teacher followed
> up and noted it in the system or not."*

The colour answers *"has anybody dealt with this?"*, not *"how bad is it?"*:

- **absent, reason recorded** → **amber / orange-red** — known, handled, noted by a human
- **absent, no reason** → **red** — nobody has explained this

A long streak with no reason stays red and sorts to the top; it does not get a third colour. On the
admin dashboard and every attendance screen, this doubles as a read on **staff follow-up
discipline**, which is what the founder is actually looking at.

### D-87 · The weekly check-in is the unit of the support programme
**Module:** bands · **Status:** DECIDED · **closes `Q-73`, option (a) — the module's last blocker**

> *"Yes agreed, let's make it weekly check-in. There will be a separate screen to record the
> performance of each C-band child — for each teacher, in a given subject, there will be a group of
> students assigned, and when she opens it she sees the list; clicking one gives the detailed
> report on that student: what is missing, what needs to improve, growth so far, tests taken, and
> the student's weekly logs."*

The founder's description **is** `/support` and `/support/[studentId]` as designed in
`screens/teacher.md`: her students grouped by subject → one child's page opening **already
written** from capture other teachers already did (`S-164`) → the four-field weekly check-in
(`S-165`). A daily note exists but nothing ever asks for one. This feeds the admin's movement
report (`D-73`) and the teacher-screen roll-ups.

### D-88 · Fee years never pool; the year switcher is the route to old dues
**Module:** fees · **Status:** DECIDED · **closes `Q-68`**

> *"Yes, I agree — every year should be separate. And maybe we can show the previous by giving the
> option to switch the academic year."*

- Every roll-up — `summary`, `overdue_students`, `student_fee_status` — is computed **within one
  academic year**, and all three move together (ux §9).
- The **global year switcher** (already built) is how last year's dues are seen: switch to 2025-26
  and its board shows what that year is still owed.
- A student carrying dues from a previous year is **never silently invisible**: the current-year
  board may carry a neutral, labelled line — *"carries dues from 2025-26 →"* — linking to that
  year, but the amount never enters this year's totals or status.

This replaces today's behaviour, where `opening_dues` is excluded from every figure and nothing on
screen admits it.

---

## Standing decisions from before this folder existed

Carried in from `CLAUDE.md` / SPRD2 because they constrain everything above. Not re-litigated.

| Ref | Decision |
|---|---|
| **P1v2** | Capture-by-exception. The teacher confirms the norm in one tap and records only deviations. Any feature needing per-student entry for a whole class is mis-designed. |
| **P4** | Bands (A/B/C) are private intervention tiers. They never reach a parent or guardian on any surface. |
| **PC-1** | Parents get a **read-only** portal. No parent writes of any kind. (Tension with the heading of `D-02` — see `Q-01`.) |
| **Law 3** | Append-only history. "Who did it" data is append rows; undo is a compensating row, never a delete. |
| **Two roles** | `admin` and `teacher` only. Class teacher (`D-03`) is a **capability on a membership**, not a third role. |
