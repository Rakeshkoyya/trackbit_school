# Open questions

Numbered `Q-nn`. Each names what it blocks, so a session can be spent on the ones that matter.
Answered questions move to `decisions.md` as a `D-nn` and are marked here `→ D-nn`.

> **Session 10 (2026-08-01) — the v1 scope pass.** `docs/v1/BLOCKERS.md` answered the blocking set
> and accepted its 38 recommended defaults wholesale (see that file's §C for which questions those
> are — each is now decided as written there). Closed here: **`Q-73` → `D-87`** · **`Q-66` →
> `D-83`** · **`Q-68` → `D-88`** · **`Q-44` → dissolved by `D-85`** (no gap threshold exists any
> more) · **`Q-01` → staff-only, `D-86`** · **`Q-61` → capture yes / use deferred** (org setting
> default off, no export in v1) · **`Q-51` → reshaped by `D-80`** (the photo's second job is
> per-question transcription + analytics; answer-judging stays out). `Q-05`–`Q-08` (payroll) and
> `Q-63` (catalogue sourcing research) remain genuinely open, deferred by `D-78`/`D-79`.

**Blocking first** — these change the shape of a table or a screen, so guessing wrong means
rework.

---

## Attendance

### Q-01 · Does a parent ever *submit* an absence in the app? 🔴 blocking
Your heading said *"absent request from parents"*, but the flow you described is: teacher marks
absent → admin or teacher adds the reason. Those are different products.

- **(a)** Reason always arrives out-of-band (phone call to the office) and **staff type it in**.
  Zero parent writes — the PC-1 read-only fence holds untouched.
- **(b)** The parent taps *"my child will be absent tomorrow — fever"* in the portal, and it
  lands as a pending note the office confirms. **This is a parent write** and reverses a
  standing founder decision.

*Claude recommends (a) for now, with a `tel:`/WhatsApp deep link on the parent's absence card
("tell the school why") so the loop closes without a write. (b) is the single parent write worth
reconsidering later — it is the one that saves the office real time.*

**Blocks:** the whole `D-02` follow-up flow, the parent portal screen, and whether a
`pending_parent_note` state exists at all.

### Q-02 · In `first_period` / `twice_daily` mode, what happens to the rest of the period card? 🔴 blocking
`D-01` changes how often **attendance** is taken. Does it also change the topic log, homework
and checks — which are per-period today?

- **(a)** Mode affects **attendance only**. Teachers still open every period to log the topic.
- **(b)** Mode affects **the whole day's capture** — in first-period mode My Day is one card,
  not eight.

*Claude recommends (a): the syllabus forecast is built on per-period lesson logs, and collapsing
them would break the planner's actual-vs-baseline arithmetic (P2). But it is worth being
explicit, because (b) is what a school that picks "first period only" may be expecting.*

**Blocks:** My Day, the period card, the capture heatmap, the 16:00 reminder.

### Q-03 · In `twice_daily` mode, what is "present AM, absent PM"? 🔴 blocking
Half day? Absent? A distinct state? A school that chooses this mode chose it precisely to see
this — so it needs its own answer, not a fallback to "partial".

*Claude recommends a named state, `left_after_lunch`, that is **not** counted as a full absence
in the register but **is** its own row on the admin's board and its own signal to the parent.
See `S-05`.*

**Blocks:** the day-status function, the register, the parent view, the RAG rules in `D-02`.

### Q-04 · Minimum-attendance rule (the 75% question)
Do schools want a configurable minimum attendance threshold — computed, shown, and warned on?
To whom: admin only, or the parent too?

**Blocks:** an org setting, the parent portal's headline, a monthly notification.

### Q-11 · What happens to history when the attendance mode changes mid-year?
A school starts on "every period" in June and switches to "first period only" in October.
Does the register re-interpret the June data, or does each day keep the mode it was captured
under?

*Claude recommends: the day row records the mode it was captured under, and the register never
re-interprets. Otherwise a school's own history changes under them when they flip a setting.*

**Blocks:** the day-status function and whether the mode is stored per-day.

### Q-13 · Is there a school-wide "no school today" that is not a calendar holiday?
Sudden closure — rain, a bandh, an exam day with no regular periods. Today `not_held` is
per-period and a teacher must set it on each card.

*Claude suggests an admin one-tap "school closed today, reason" that stops every downstream
consequence: no capture expected, no absence alerts, no red rows, no dip in the pulse.*

---

## Class teacher

### Q-09 · Does the class teacher dashboard replace My Day for her, or sit beside it?
She is also a subject teacher with her own periods. Two entry points, or one screen with a
class-teacher section on top?

*Claude recommends: a separate area (a nav item that appears only when she owns a class), so My
Day stays the same product for every teacher. Mixing them makes My Day different for different
people, which makes it harder to explain and to support.*

**Blocks:** the nav, the route, and the shape of the screen.

### Q-10 · Which "few other modules" belong on the class teacher's dashboard?
Attendance and syllabus are named. Candidates: homework completion for her class, exam scores,
fee status *(no — teachers never see fees, hard rule)*, bands *(allowed — she is staff, P4 only
fences parents)*, her assigned follow-ups, hostel session records for her students.

**Blocks:** the screen design. Not blocking the data model.

### Q-14 · Can a class have more than one class teacher, or a teacher more than one class?
Co-class-teachers are common in large sections; and a teacher owning two sections happens in
small schools. Today the field is a single nullable FK on the class, so: one teacher per class,
one-to-many the other way.

*Claude recommends leaving it as-is (one owner per class) — a single named owner is what makes
"assign the follow-up" unambiguous.*

---

## Staff, leave and payroll

### Q-05 · Payroll: an estimate, or a payable record? 🔴 blocking, highest stakes
- **(a) Estimate.** A number the admin reads to decide what to pay. No payslip, no lock, no
  statutory deductions. Nobody is paid *by* the system.
- **(b) Payable record.** Month lock, payslip PDF, arrears, PF/ESI/professional tax/TDS, bank
  transfer file, and a compliance surface.

The distance between these is enormous — (b) is a product, not a tab, and it carries legal
liability the rest of TrackBit does not.

*Claude strongly recommends (a) for v1 and naming it that way on the screen — "estimated, based
on days present" — with (b) as a separate, later, explicitly-decided product. See `S-15`.*

**Blocks:** everything in `modules/payroll.md`.

### Q-06 · Who is allowed to see salary? 🔴 blocking
`require_admin` is not a good enough answer. A school has several admins — the principal, the
correspondent, an office clerk. Salary is the most sensitive column that would exist in the
database, and every current admin screen would expose it.

- **(a)** Any admin.
- **(b)** A new capability flag on the membership (`can_view_payroll`), granted by the operator
  or the founding admin.

*Claude recommends (b). Also see `S-17`: salary must be explicitly excluded from Lucy's tool
registry, the daily report, and every widget — none of those have a concept of "this field is
different".*

**Blocks:** the data model, the guard on every payroll endpoint, and the Lucy registry.

### Q-07 · What is the salary structure, and where is the amount entered?
- Single monthly gross per member? Or components (basic / HRA / allowances / deductions)?
- Entered where — Setup → Members? A new Staff → Salary setup screen?
- Does it change mid-year, and is the history kept? *(Law 3 says: append rows, never overwrite —
  a pay revision must be a new row with an effective date, or you can never explain last
  month's figure.)*

**Blocks:** the data model.

### Q-08 · What actually reduces pay? 🔴 blocking
Every school answers this differently and the answer is the whole calculation:

- Unapproved absence only, or approved leave beyond the balance too?
- Half-day = 0.5 day deducted?
- Late — deducted at all, or only tracked? After how many lates does it become half a day?
- Is the divisor calendar days, working days, or a fixed 26/30?
- What about Sundays and holidays inside a leave span?

*The `leave_requests.days` field already counts **working days** (year `working_weekdays` minus
holidays) — that decision is made and should be reused, not re-litigated.*

**Blocks:** the calculation, and therefore the screen.

### Q-12 · Does covering someone else's period count for anything?
A substitute takes 3 extra periods. Recorded today (`period_substitutions`). Does it earn
anything, or is it purely operational?

*Claude recommends: purely operational for now. The moment cover earns money, the substitution
record becomes a financial document and needs approval and dispute handling.*

### Q-15 · Half-day: which half, and does the admin or the teacher choose?
*(staff — kept in place; see the staff section above for context)*
A half-day leave is either the morning or the afternoon, and that determines which periods need
cover. Does the leave request carry AM/PM, or is it just "0.5 days"?

*Claude recommends AM/PM on the request — otherwise the substitution board cannot tell which
periods to cover, which is the whole reason SF-1 exists.*

---

## Syllabus (session 2)

### Q-16 · What denominator does a parent's "syllabus covered" use? 🔴 blocking
Today the admin board and the parent portal compute it **differently** — admin against
*planned* topics with partial counted as a half, parent against *all* topics with partial
counted as whole. Same phrase, two numbers, same day.

*Claude recommends: parents see coverage of the **whole syllabus**, because that denominator
only ever grows. Coverage against planned topics **falls** when the school sizes the next term's
chapters — nothing was un-taught, but a parent will read it as the school going backwards
(`S-54`). The admin should see both numbers side by side.*

**Blocks:** `S-51` (one coverage function), and every screen that renders a coverage %.

### Q-17 · Can a subject teacher see other teachers' pace? → **ANSWERED, `D-15`**
*No. Her own subjects only, blocked not merely defaulted. Claude's recommendation below was overruled.*

`D-10` says a subject teacher sees "her own subjects". Does that mean she is *blocked* from the
class-wide or school-wide view, or just that it isn't her default?

*Claude recommends: not blocked, but not surfaced. There is nothing confidential about a
coverage figure between colleagues, and hiding it invites the belief that it's being used
against them. But her landing screen should be her own subjects (`S-46`).*

### Q-18 · Is "not enough data yet" acceptable to an admin?
The board refuses to rank a class with fewer than 3 rated class-subjects, or a teacher with
fewer than 10 logged periods. That is honest — and in a small school or in week two it means the
ranking lists the admin was promised are **empty**.

*Claude recommends keeping the guard and changing the copy: say what is missing and how close it
is — "ranking starts once 3 subjects have plans (2 so far)" — so it reads as a countdown rather
than a broken screen (`ux-principles` §13).*

### Q-19 · Does "missed while absent" stay on the parent's report?
`D-11` says parents never see missed syllabus. But the growth report currently shows, per
chapter, **the topics taught while their child was away** — which is about the *child*, not the
school being behind, and is arguably the most useful line on any parent screen: it turns an
absence into an academic consequence a parent understands.

*Claude recommends keeping it, and wording it as catch-up rather than loss: "taught while Diya
was away — worth catching up" (`S-49`).*

**Blocks:** the parent report, and the wording of `D-11`.

### Q-20 · Does the class teacher see per-teacher pace for her class? → **ANSWERED, `D-15`**
*Yes — all subjects and all teachers' pace, but only for her own class.*

Her class's Maths is 3 weeks behind. Does the screen name the Maths teacher?

*Claude recommends yes — she cannot act on it otherwise, and she is staff. But it should carry
the same honesty guard as the admin board: the numbers beside the name, framed as needs support,
never a rank.*

---

## Notifications (session 2)

### Q-21 · How does an in-app notification actually reach a parent? → **ANSWERED, `D-14`**
*Web push.*

`D-08` moves guardian messaging in-app. But an in-app notification only reaches a parent who
*opens the app* — and an absence alert nobody sees is not an alert. The absence alert, the
homework message and the Saturday summary are all currently WhatsApp-stub calls.

Options: **web push** (already built for staff — `push.py`, notification channel `push`) ·
email · SMS · accept that the portal is pull-only and the school phones anyone who matters.

*Claude recommends web push for parents, plus designing the portal so the Today tab **is** the
notification surface — a parent who opens it once a day sees everything without a separate tab.*

**Blocks:** the parent notifications tab, and whether the absence alert is meaningful at all.

### Q-22 · If WhatsApp is out, how does a parent log in? → **ANSWERED, `D-13`**
*School code → class → section → student → date of birth. Neither OTP nor SMS. New questions `Q-24`–`Q-28` fall out of it.*

Parent login is phone-OTP. *(verified)* `otp_delivery.py` tries the WhatsApp auth-template
first, falls back to MSG91 SMS, and logs to the console when neither is configured. With
WhatsApp out, OTP needs **SMS**, or parents get handed-over username/password credentials
(`/parent/auth/credentials` already exists).

Without one of those, **nobody can log in to see the notifications tab.**

**Blocks:** the entire parent portal in this version.

### Q-23 · Do staff notifications change too, or only guardian ones?
`D-08` was stated about parents. Staff already receive in-app + push notifications (teacher
16:00 reminder, daily report ready, substitute assigned). Presumably unchanged — worth
confirming so the notifications module isn't half-migrated.


---

## Parent login by school code + DOB (`D-13`)

> **Deferred to session 3 by the founder (2026-07-30).** The flow and its hardening are settled
> (`D-13`, `D-17`); everything below is the unfinished half and is where the next parent-access
> conversation starts.

### Q-24 · Where does the date of birth come from? 🔴 blocking
*(verified)* `students` has **no DOB column**, and the roster importer does not map one. So:

- the importer needs a DOB column and a date parser (Indian sheets mix `dd/mm/yy`, `dd-mm-yyyy`
  and Excel serial numbers — this is a real source of wrong logins, not a formality)
- schools already onboarded must backfill
- **a student with no DOB has a parent who can never log in** — so the screen needs an answer for
  that parent, and the admin needs a list of students missing one

*Claude recommends: admin can set a per-student override credential for the gaps, and Setup shows
a "42 students have no date of birth" row until it is cleared.*

### Q-25 · Siblings — one login or three? 🔴 blocking
*(verified)* Today one phone number links **every** guardian row it matches, so siblings roll up
into one session with a switcher. Per-student DOB login breaks that: a parent of three children
logs in three times, and the sibling switcher has nothing to switch between.

Options: **(a)** accept it — one login per child, no switcher · **(b)** after login, offer "add
another child" and keep the switcher, each child added with their own DOB · **(c)** keep the
guardian phone as the account and DOB only as the first-time claim.

*Claude recommends (b): the parent proves each child once, and the session then behaves exactly
as it does today.*

### Q-26 · Is the school code secret or public?
It decides whether the student picker is a roster leak. A guessable code (`DPS2024`) plus a
browsable class list exposes every child's name in the school to anyone.

*Claude recommends: a random 6–8 character code, handed to parents, never shown on the marketing
site — combined with `S-55` so the roster is never browsable regardless.*

### Q-27 · What happens to the guardian phone link?
The whole PC-1 model hangs off it: `guardians.user_id` is claimed at first OTP login,
`notify_opt_out` is per guardian row, and revocation is the live guardian-link check in
`get_current_parent`. If login no longer involves a phone, what is the account, what is revoked
when a child leaves, and who receives the web push — a guardian row, or a device?

**Blocks:** the auth model and the notification target.

### Q-28 · Can the password ever be changed?
DOB as a permanent password means a credential the school printed in a register is the
credential forever. Can a parent set their own? Can a school force it? Is there a reset?

*Claude recommends: DOB is the **first-time** credential; the parent is invited (not forced) to
set a password after first login. `/parent/auth/credentials` already exists for this.*

### Q-29 · Is phone-OTP removed, or kept as an alternative?
`D-13` says "another plan", not necessarily "instead of". Keeping both doubles the auth surface;
removing OTP throws away working, more secure code. *Claude recommends keeping OTP available but
not the default — it is the recovery path when a DOB is missing or wrong.*

---

## Teacher load / the period module (session 3)

### Q-30 · Does timesheet data ever reach pay or an appraisal? → **ANSWERED, `D-25`**
*No. Payroll is computed purely from present/absent on the day plus half-day leave. Nothing in the
timesheet reaches a salary figure. This also confirms `D-05`'s only input is staff attendance, and
narrows `Q-08`.*

`D-05` (eight days earlier) made **days present drive salary**. This module records what a teacher
did with every period of every day. The moment those two touch — completeness affecting a figure,
or "periods recorded" appearing in a performance conversation — the data stops being true. Every
free period becomes "exam work" within a month, and the busy-chart, the cover picker and the
fairness view are all then built on fiction.

*Claude recommends a hard no, written into the module as a fence (`S-67`): no leaderboard, no
completeness % per teacher shown school-wide, no export that names and ranks, and no path from
`timesheet_entries` to any salary calculation. Staff attendance (SF-1) is what feeds `D-05`; that
separation is already clean and should stay that way.*

**Blocks:** the fence, what appears on `/dashboard/staff`, and — through teachers' behaviour —
whether any number in this module is worth reading.

### Q-31 · Is a period with nothing recorded *free*, or *not captured*? → **ANSWERED, `D-23`**
*Free. Option (a). No day-confirm row, no third state. Claude's recommendation of (b) was
overruled — and there is a good argument for the decision, written up in `D-23`: for the "who can
cover 11:20" question, **free is the correct default bias.** Consequences: the "free periods
unlogged" tile is deleted rather than fixed (`S-76`), the chart's free band is labelled "free or
unrecorded", and `S-62` is replaced by `S-75` because a pre-filled week would now be a record
rather than a proposal.*

There is no way to tell today (`modules/teacher-load.md` §4.1). Every other capture surface in the
product has a marker that says a human was here — `class_periods.attendance_marked_at`,
`staff_attendance_days`, `homework_checks` — and the timesheet has none.

- **(a)** Empty means free. Simple, and the "free periods unlogged" tile and the `D-21` chart both
  quietly measure app adoption instead of the school.
- **(b)** A one-tap **"that's my day"** confirmation (`S-61`, `timesheet_days`), so *free* and
  *never told us* are different states.

*Claude strongly recommends (b): one tap for the whole day, the same shape the rest of the product
already uses, and it is what makes every figure in `D-21` mean something. It also unlocks `S-62`
safely, because a pre-filled weekly pattern can then be a proposal rather than a fabricated
record.*

**Blocks:** the data model, the chart, the live board's honesty, and `S-62`.

### Q-32 · Can the admin assign work into a free period — beyond cover? *(narrowed by `D-26`)*
**Cover is settled**: `D-26` has the admin assigning a substitute into someone else's period, and
`period_substitutions` already does it. What is still open is the **rest** of the assigned work —
invigilation, ground duty, an event, receiving a visitor.

Invigilation, ground duty, an event, a visitor — half the work in a school is handed out, not
chosen, and today the timesheet is purely self-reported so the school's rota lives in a WhatsApp
group.

*(verified)* The general case is **already built for one special case**: `period_substitutions`
is the admin putting a named teacher into a named period, with a real busy check and an
append-only cancel.

*Claude recommends yes, as a `source = self | assigned` flag on the entry (`S-65`) rather than a
new table — it is what turns the admin's screen from "who is free" into "who is free, give it to
her". Needs a conflict rule: one entry per period is what makes every total meaningful, so an
assignment onto an occupied period is a replace-with-warning, never a second row.*

**Blocks:** the data model, the admin detail tab, and what the teacher's day view can show.

### Q-33 · Does the timesheet cover work outside the periods?
A 4pm parents' meeting, an 8am briefing, a Saturday event have no `period_no` — and `period_no` is
exactly what makes *"who is free in period 4"* answerable.

*Claude recommends keeping entries period-indexed for v1 and giving the day a small day-level
**extra duty** line for what happens outside the bell (`S-73`). A second time model should wait
until a school actually asks for it.*

### Q-34 · How far back can a day be filled in?
`D-20` says whenever. A hard lock would stop it being filled at all; no marker at all means a
period back-filled in March reads exactly like one recorded at 11:58.

*Claude recommends no lock, but bump `updated_at` (it exists and is never bumped today) and let
the admin's detail view distinguish recorded-that-day from back-filled (`S-71`).*

### Q-35 · Do hostel sessions count as teaching load?
*(verified)* `sessions` carry `owner_member_id`, `weekdays`, `time` and `end_time` — evening prep,
homework class, Saturday yoga, each staffed by a named teacher — and **no load surface reads
them**. A warden running prep six evenings a week appears on every board as lightly loaded.

*Claude recommends yes, read-only, unioned in from the session grid the way teaching periods are
unioned in from the timetable (`S-68`). The open sub-question is whether an evening block counts
toward the same mean as a school period, or is reported beside it — Claude suggests beside it,
since an hour of prep and a taught period are not the same work.*

### Q-36 · Who other than the admin may read a teacher's timesheet?
There are exactly two roles. Today `_resolve_member` lets any admin read anyone and refuses a
teacher who asks for a colleague's. Does a class teacher (`D-03`) see the timesheets of the people
who teach her class? Does a senior teacher who is not an admin?

*Claude recommends leaving it as-is — admin and self only. Widening it is a one-line change later;
narrowing it after people have seen each other's days is not.*

### Q-37 · Does covering a period show up on the substitute's own timesheet?
*(verified)* It does not. `TimesheetService._build_day` reads the timetable and
`timesheet_entries` only, so a teacher who covered three periods this morning sees three **free**
cells on her own week grid — the mirror image of the bug on `/staff/today` (`S-72`), on the
teacher's side.

It matters for two reasons: her week's totals are wrong, and `S-70`'s *"3 covered for
colleagues"* — the one line on the screen that is **for her** — has nothing to read.

*Claude recommends yes: union `period_substitutions` into the timesheet day the same way teaching
periods are unioned in from the grid — read-only, no new table, one source of truth per period.
This is the same fix as `S-72` applied to the other screen, and it should ship with it.*

*(`Q-12` already settled the money side: covering a period earns nothing. This is purely about
the record being complete.)*

---

## Homework (session 4)

### Q-38 · A student who was absent — auto-excluded, or the teacher's call? → **ANSWERED, `D-34`**
*Neither. A third state: the days are **dropped**, the homework becomes **pending** for that
child, and when he returns the teacher checks whether it is done — with the choice to make him do
the backlog or set him fresh work instead. It never counts as a miss. Needs a **waive**
(`S-98`), or the pending items and the parent's yellow never clear; and the pending state must be
excluded from the streak and the red list (`S-102`).*

*(verified)* Today the check sheet lists the whole roster with no idea who was in the room. A
child off sick on Tuesday is flagged `not_done` on Wednesday, lands on *"Students who keep missing
it"*, and their guardian is reminded about work they were never given.

- **(a) Auto-exclude.** Attendance says absent → the row is excluded from the sheet and from every
  completion figure.
- **(b) Show it, don't preselect it.** The row reads *"Kabir — absent Tuesday"* and is simply not
  pre-flagged; the teacher decides.

*Claude recommends (b). She may know a friend passed it on, or that it was set a week earlier — a
hard exclusion cannot be overridden, and this module's whole design is "the human confirms, the
system pre-fills the norm". Either way the completion figure must exclude it, the same way
`not_checked` already does.*

**Blocks:** the check sheet, the completion denominator, and who the red list names.

### Q-39 · Does a parent hear about a miss — and at what threshold?
Today the parent is told homework was **set** and never that it was **not done**; they have to
open the portal. `homework_results` names the child, so the message is possible.

*Claude recommends: never for a single miss — that makes the school a nag and trains parents to
mute it. Notify at **two consecutive homework days missed** (`S-90`), the same threshold the red
list already uses and the same shape as `D-02`'s absence rule.*

*Delivery is settled by `D-08`/`D-14` — in-app plus web push, not WhatsApp. Note that
`add_homework`'s existing notify call is one of the three WhatsApp stubs that need re-pointing.*

### Q-40 · Is "partial" worth half, or nothing?
*(verified)* `HomeworkService` computes `completion = done / (done + not_done + partial)` — a
child who did most of it scores **identically to one who did nothing**. Meanwhile
`insights/syllabus.py` counts a partially covered topic as **0.5**. Same word, two arithmetics,
one product.

*Claude recommends 0.5 in both — it is what "partly" means. Whichever way it goes, the screen has
to say it (`ux-principles` §4).*

### Q-41 · Should homework carry a deadline by default? → **ANSWERED, `D-38`**
*Next day by default, configurable by the teacher — she can set it two days out or further. And
both latenesses are captured and shown to the admin: the student who did it late, and the teacher
who didn't check. Option (a), plus the explicit override.*

`due_date` is optional and *(verified)* the teacher's checking queue ignores it completely — a
project due next Monday is offered for checking tomorrow, and the real due date passes with no
prompt.

- **(a)** Keep it optional; default the deadline to the next school day when it is blank
  (`coalesce(due_date, date)`, which is what `S-83` needs anyway).
- **(b)** Ask for a due date every time.

*Claude recommends (a) — one more field at the moment the class is packing up is exactly the tax
P1v2 exists to prevent, and "tomorrow" is the honest default in a school.*

### Q-42 · Who owns a class's total daily homework load? → **ANSWERED, `D-37`**
*The **admin** and the **class teacher**. A subject teacher sees nothing. Informational — no cap,
no rota, exactly as recommended.*

`S-87` makes the total visible — *"8-B, Tuesday: 5 subjects set homework"* — for the first time.
Six teachers each made a reasonable decision; nobody could see the sum.

---

### Q-43 · Does a late completion count toward the completion figure?
`D-33` creates a verdict the analytics have never had. Three ways to treat it and they tell the
admin three different stories:

- **(a) Counts as done.** Honest to the child, and hides a real pattern — a class where everything
  arrives four days late reads as a class with 100% completion.
- **(b) Counts as a miss.** Punishes a child who did the work.
- **(c) Counts as done, reported separately** — *"82% done · 6 of them late"*.

*Claude recommends (c), which is the discipline this module already uses for `not_checked`: the
figure stays true and the second fact is not buried inside it. A **waived** item (`S-98`) should
leave the denominator entirely, again like `not_checked`.*

**Blocks:** the admin board's completion column, the student report card, and the parent's
per-subject figure.

### Q-44 · Past the 3-day gap, is "late" a fact about the child or about the record? 🔴
`D-33` says that past the threshold it *"can only be marked as late completion"*. But two very
different things produce a long gap:

- the **child** handed it in late — a fact about the child;
- the **teacher** collected it on time and recorded it on Friday — a fact about the record.

Today the system cannot tell them apart, and forcing the first when it was the second writes
something untrue about a student into their history — the exact mistake `not_checked` exists to
prevent.

*Claude recommends: past the threshold the default verdict is worded **"recorded late"**, the
teacher can still mark a specific child as genuinely late, and `checked_at` vs the deadline keeps
carrying the teacher's side separately. Both reach the admin, which is what `D-38` asks for.*

*Also worth deciding: is the 3-day threshold an org setting (`S-96`)? A boarding school and a day
school will not agree on it. Default 3, configurable in Settings, working days only.*

**Blocks:** the wording on the check sheet, what goes into a student's record, and `Q-43`.

---

## Session 5 — Tasks (2026-07-31)

### Q-45 · Ninety days in, what happens to the completed tasks on the Follow-ups board? → **ANSWERED, `D-44` + `D-45`**
*Window the read — **(b)** — with the date filter shipping alongside it. And the harder half
accepted too: stale **open** rows get their own group, closed or re-dated by a human, never
auto-closed.*

*The founder's own question, and the answer matters more than it looks — this board is the only
place the admin's "go do this" ever lands.*

*(verified)* `TaskService.board_table` (`services/task.py:267-271`) returns **every** non-cancelled
instance on the board — no date window, no limit, ordered oldest-first — and the client renders all
of them. At five follow-ups a day that is ~450 rows by day 90.

Three answers:

- **(a) Archive completed tasks after N days.** A new state, a nightly job to maintain it, and a
  second place a task can be — so *"where is that task"* becomes a question that did not exist.
- **(b) Window the read** (`S-103`). Open rows always; done rows from the last 7 days; everything
  older behind a date filter on the same board. No migration, no job, nothing moved, nothing lost —
  and it is the discipline `HomeService.my_tasks` already uses (done = today only,
  `home.py:128-135`). The board table is the outlier that never got it.
- **(c) Nothing.** Defensible for a year, indefensible for two.

*Claude recommends **(b)**, with one condition that decides whether it works: **the date filter
must ship with the window, never after it.** A window with no way to look further back is data
loss from the user's side, and the first time an admin asks "what did we follow up on in October"
and can't find it, they stop trusting the board.*

> **And the completed rows are the easier half.** A done row is at least a true statement about the
> past. What breaks the board is the **open** rows nobody ever closed — a *"Call Kabir Shah's
> parent"* from March sitting above today's work. See `S-104` (a **Stale** group, with *close* or
> *re-date*, and **never** auto-close: silently closing that row asserts a child's parent did not
> need calling).

**Blocks:** the board screen, and how far back `/dashboard/tasks` can look.

### Q-46 · How many tasks can appear on My Day before it stops being My Day? → **ANSWERED, `D-43`**
*Answered by narrowing the **contents** rather than capping the count: rail-assigned within 3 days
∪ due today. The cap (`S-109`, 3–5 then "+n more") stays as a backstop. The undated-task worry
below is resolved by the same rule — an undated task she wrote herself never enters the section at
all, and an undated rail follow-up ages out after three days.*

`D-42` sets no cap. A teacher carrying nine open tasks would push her evening hostel sessions off
the bottom of the most-opened screen in the product, on a 360px phone.

*Claude recommends a cap of 3–5 with **"+4 more →"** (`S-109`). The section is a prompt, not an
inbox — the inbox is `/tasks`.*

Related: a task with **no due date** is *"anytime until done"* (`models/task.py:109`) and therefore
never leaves the main section on its own. Twenty of those and the section is dead weight. Does an
undated task age out of My Day after N days while staying open on `/tasks`?

**Blocks:** the My Day packet.

### Q-47 · Does My Day show all her tasks, or only the ones the admin assigned? → **ANSWERED, `D-43`**
*Neither of the two options as posed — the filter is by **rule**, not by board or by author:
rail-assigned within 3 days, **plus** anything due today from any board. `S-110`'s point survives
(no board tabs on My Day, she has one head); its "all of them" is dropped in favour of a window.*

`D-41` was described in terms of the rail. But a teacher can create tasks on any public board, and
those are equally hers.

*Claude recommends **all of them, one list** (`S-110`): a teacher has one head, and "which board is
this on" is our concept, not hers. `HomeService.my_tasks` already returns exactly this, with the
board name available for a subtitle — so this recommendation is also the cheaper build. The
distinction the founder actually wants is preserved by **badging who asked** (`S-106`), not by
excluding rows.*

**Blocks:** which service My Day calls — `my_tasks` (all boards) or a new Follow-ups-only query.

### Q-48 · What closes a follow-up that reality already closed? → **ANSWERED, `D-46` + `D-45`**
*Options **(a) + (c)**, exactly as recommended: the task carries its subject and completion records
what happened; stale rows are surfaced for a human to close or re-date. **(b) auto-close is
rejected** — the child returning does not mean the call was made.*

The admin assigns *"Call Kabir Shah's parent"* on Monday. Kabir walks in on Wednesday. Nothing
closes the task — it sits open until someone tidies up, and then it is `Q-45`'s stale row.

*(verified)* The task cannot know: `followup_actions.detail` carries the `task_id`
(`actions.py:235`) but the link runs one way only — the `TaskInstance` is a **title string** with
no reference to Kabir Shah.

Three ways out, and they are not exclusive:

- **(a) Link the task to its subject** (`S-105`) — then the row can render *"Kabir Shah — absent 4
  days"*, the student's timeline shows the follow-up, and completion can ask one optional question:
  ***what happened?*** *"Spoke to the father — fever, back Monday"* is the fact the admin wanted
  when they pressed the button (ux-principles §8).
- **(b) Auto-close when the condition clears.** **Claude recommends against**: the child returning
  does not mean the call was made, and writing "handled" into an append-only history when nobody
  handled it is worse than a stale row.
- **(c) Surface it, let a human decide** (`S-104`) — *"Kabir has been back 2 days; close this?"*

*Claude recommends **(a) + (c)**. (a) is the smallest change with the largest reach in this session:
it also gives `S-104` something to close on and `S-107` a key to dedupe on.*

**Blocks:** `S-104`, `S-107`, and whether a follow-up ever appears on a student's timeline.

---

## Session 6 — Exams & scores (2026-08-01)

### Q-49 · Is the exam type a fixed list, or the school's own word? → **ANSWERED, `D-55`**
*The school's own word, in a **new column** beside the existing `type` rather than by dropping its
constraint — which is the better shape, since code branches on `type` today. `type` becomes the
system kind (code-only), the new field is the vocabulary (screen-only). Claude recommends making it
a small `exam_types` table so `scale` rides along and spellings can't drift — see `S-135`.*

*(verified)* `assessment_cycles.type` is a **CHECK constraint over 9 values**
(`models/assessments.py:57-58, 84-88`). The founder named **CET**, which is not one of them — so a
school running a weekly CET either cannot save it, or files it as `class_test`, after which no
analytic can separate it again.

**Three weeks ago the same question was answered the other way**, and the reasoning was written
down. `core/work_types.py`:

> *"the column is plain Text with **no CHECK constraint**: a school that renames its work must never
> lose rows to a database error… an unknown value titles itself instead of vanishing."*

*Claude recommends the `work_types` answer (`S-113`): keep the nine as a **picker**, drop the
constraint, let an unrecognised value title itself. The staffroom's vocabulary — CET, cycle test,
revision test, pre-board — is exactly what the analytics need to keep.*

**Blocks:** the capture form, the feed's type badge, and every filter downstream.

### Q-50 · Does any screen blend exam types into one number? 🔴
*(verified)* Today, yes, and it is the default. `ExamInsights.board` computes `tot_s / tot_x` over
all cycles in scope and `by_subject` pools raw marks (`insights/exams.py:126-164`); `class_analysis`
and `growth` do the same; `GrowthScore` does not even carry the type (`schemas/growth.py:55`). So
*"Maths is at 61%"* is the mean of an April diagnostic, twelve slip tests and one final — and a
student's report card draws one line through a 5-mark slip test and an 80-mark final.

Three answers:

- **(a) Weights per type** — "slip test 10%, term exam 60%". **Claude recommends against**: this is
  a **report-card designer**, which SPRD2 §11 fences. Every school wants different weights, the
  composite is checkable against nothing, and the argument about the weights becomes the product.
- **(b) Never blend** (`S-114`): one nullable `scale` column, two values — `minor` (slip, class,
  CET, chapter) and `major` (unit, term, pre-board). **Trajectory is drawn from minor** — frequent
  tests are what show movement. **Standing is read from major.** The two are never added.
- **(c) Leave it, filter manually.** The filter exists and defaults to none, so the number everyone
  reads first stays the blended one.

*Claude recommends **(b)** — it is one field, it fixes the admin board and the student's report card
together, and it gets the honesty of weighting without any of the policy.*

**Blocks:** `/dashboard/exams`, `/students/[id]`, and the class analytics.

### Q-51 · How far does the paper check go — arithmetic, or judging answers? 🔴
`D-50` makes checking optional. The question is what "checking" is allowed to claim.

- **(a) Marking check only** (`S-116`) — *the per-question marks sum to 23 but the header says 25*
  · *Q4 has no mark beside it*. Both are about the **teacher's paper**, both have a ground truth the
  school can verify in three seconds, and neither needs the model to know the subject.
- **(b) Also judge the answers** — *"Q4 is wrong"*. This is the model forming an opinion about a
  child's work with **no deterministic backstop** — unlike every other AI call in the product,
  which is either a transcription or a proposal checked against real data (a column list, the
  roster).
- **(c) Judge the answers, but never store it** (`S-117`) — shown only while a human has the paper
  open, phrased as *"Q4 may need a second look"*, never as a verdict, never persisted.

*Claude recommends **(a) now, (c) behind a flag, never (b) as written**. And note the fence: SPRD2
§11 puts test authoring/conducting out of scope; evaluation is neither, so this is a decision to
make deliberately rather than a line already drawn.*

**Blocks:** the capture screen's second pass, and whether anything new is stored about a student.

### Q-52 · Does a recorded exam link to its planned exam block and portion?
*(verified)* V2-P7's `exam_portions` ties a `calendar_events` **exam block** to a class-subject and
the topic the portion runs up to (`models/exams.py`), and the syllabus board asks *"will the Term-1
portion be finished before the Term-1 exam?"* from it. **`assessment_cycles` has no
`exam_event_id`** — so the planned exam and the marked exam are two unrelated objects, and nobody
can ask *"we covered 70% of the portion; what did it cost?"*

*Claude recommends yes — **one nullable FK** (`S-115`), nullable because a Tuesday slip test has no
calendar block and never will. It is the join the two modules were both built for.*

**Blocks:** the syllabus↔results question, on both dashboards.

### Q-53 · Per-question capture for objective tests — in, or a later module?
The founder listed **objectives** as an exam type. For an MCQ paper the analytic that matters is
**per question** — *"nineteen of thirty got Q7 wrong"* — which a total mark can never yield, and
which points straight back at a topic.

It is also a **new table, a new capture surface and a real scope increase**, and it is the only idea
in this session that needs one.

*Claude recommends scoping it out of this module and naming it as its own thing, rather than letting
it arrive quietly as "one more field on the exam". If it is wanted soon, it deserves its own
session.*

**Blocks:** nothing today — but it should be answered before anyone widens the capture form.

---

## Session 7 — Events & dates (2026-08-01)

### Q-54 · Where do festival dates come from, and who signs them off each year? 🔴
The founder said *"from the internet"*. That phrase hides the module's only hard problem: Diwali,
Holi, Guru Purnima, Eid, Onam and Pongal are **lunisolar** — they move every year and regional
reckonings differ.

- **(a) Ask a model.** A model asked *"when is Diwali in 2027"* answers confidently and can be
  wrong, and **there is nothing in the product to check it against** — no roster, no column list.
  Every other AI call here either transcribes or proposes a mapping a deterministic validator
  checks against real data. This is the `Q-51` shape: an unverifiable claim, rendered as fact.
- **(b) A live third-party API.** A network dependency, a key to rotate and a vendor to outlive,
  for data that changes **once a year** and is knowable a year in advance.
- **(c) A checked file in the repo, per academic year** (`S-123`) — reviewed by a human once,
  diffable in a PR, works offline, identical in every environment, free.

*Claude recommends **(c)**, strongly. The failure mode of (a) is a school that decorates on the
wrong day because our screen told it to — and it will be our screen it blames. AI's job in this
module is **phrasing** — the assembly note, the wish — never dates.*

**Blocks:** the entire observance half of the module. Birthdays and the school's own calendar can
ship without this answered.

### Q-55 · Is the catalogue regional or faith-scoped, and who picks for a school? 🔴
A school in Kerala, one in Punjab and one in Hyderabad do not keep the same festivals, and a
Christian minority school does not keep the same list as a state-board school next door. Showing
every school every festival is the fastest way to make the card unreadable (`S-125`).

- **(a)** One national list, tiered, and the school hides what it doesn't keep — one tap per row,
  once.
- **(b)** The school picks a region/tradition at setup and gets a pre-filtered list.
- **(c)** Both — (b) picks the default, (a) is always available.

*Claude recommends **(c)**, but shipping (a) first: hiding a row is one control and needs no
taxonomy, whereas getting a region taxonomy wrong is a data migration. And be careful with (b) —
asking a school to declare its religion at setup is a question with a cost. Ask about **the
festivals it observes**, never about what it is.*

**Blocks:** the catalogue file's shape, and the setup wizard if (b) lands.

### Q-56 · Do parents see the school calendar?
*"Is school open on Monday?"* is the single most-asked parent question in a school office, and the
rows that answer it already exist and are already maintained. It is read-only, needs **no new
capture**, and goes through the same curated allowlist as everything else in `parent_portal.py`.

*Claude recommends yes — it is probably the cheapest win available to the parent portal. Two hard
constraints: field-by-field projection like every other parent surface, and **a parent sees only
their own child's birthday**. A list of classmates' birthdays is a roster leak wearing a party
hat.*

**Blocks:** nothing in this module — it is a parent-portal decision recorded here so it isn't
reinvented there.

### Q-57 · Staff birthdays — in or out, and on whose screen? → **ANSWERED, `D-56`**
**In, nullable, optional, self-entered from the teacher's own profile — never imported.** Exactly
the recommendation, including the fence: a staff DOB never sits next to anything payroll-shaped.
The founder said students. An admin wishing a teacher by name on the morning of costs nothing and
is felt for a year, and staff turnover is the school's most expensive problem (`S-127`).

Neither `users` nor `memberships` has a DOB, so this is one more nullable column — but a
**self-entered** one, in the person's own profile, not imported from a spreadsheet.

*Claude recommends yes, self-entered, opt-in, visible to the admin and to nobody's parent. And one
fence to state out loud: a staff DOB must never sit next to anything payroll-shaped — the `D-25`
principle that a teacher's own data can never cost her money.*

**Blocks:** whether `memberships.date_of_birth` exists at all.

### Q-58 · Is the birthday wish an outbound guardian message, or in-school only?
Two very different products. In-school: the class sings, the name is read at assembly, nothing is
sent. Outbound: a WhatsApp reaches the guardian.

The outbound version is the obvious feature and carries the risks (`S-129`) — it will eventually
fire at a family that has just lost someone, or for a child who left in March, or twice because
two guardians share a phone. It also costs a message per student per year.

*Claude recommends **in-school first**, and if outbound ships: human-pressed never automatic,
`notify_opt_out` honoured, `status='left'` students never in the feed, and a record that it fired
so nobody is wished twice by two different people. This is the `followup_actions` shape from
DASH3 (ux §7), not a new mechanism.*

**Blocks:** whether `NOTIF_TYPES`' CHECK constraint needs widening, and whether this module sends
anything at all.

### Q-59 · Is DOB in the setup pack schools hand over, in a form we can parse? → **ANSWERED, `D-56`**
**Student DOB is captured at setup, with the roster.** The parsing problem below still has to be
solved — `dd/mm/yyyy` and Excel serials — but it is now a build detail, not an open decision.
*(verified)* `students` has **no** `date_of_birth`, and the roster importer has no synonym for one
(`services/roster_import.py:23-48`). The module renders nothing until this is filled.

Schools do hold it — board registration requires it, and it is on every admission form — but the
question is whether it reaches the xlsx they hand over at setup, and in what format.
`dd/mm/yyyy` dominates in Indian school registers, Excel serial dates are common, and a
`mm/dd` misread silently moves 40% of a school's birthdays.

*Claude recommends adding the column and the synonyms regardless, treating a DOB the importer
cannot confidently parse as **unresolved** rather than guessing — the `unresolved` surface already
exists in the importer — and showing coverage with its denominator everywhere the card is empty
(`S-124`).*

**Blocks:** the birthday half of the module, which is most of it.

### Q-60 · One calendar or two?
Plan → Year **is already a year calendar**. If this module adds a month grid, the school has two
calendar screens that disagree about what a calendar is for (`S-134`).

- **(a)** The card links to Plan → Year, which gains a read mode. One calendar.
- **(b)** A new screen that is an **agenda** — dates in order with what each one needs — which is
  not a calendar and so does not compete.

*Claude recommends **(a) for the grid and (b) for the card**, and no third month view. The worst
outcome is a new route rendering the same grid as `/plan` with a different brush set — and that is
the default outcome if nobody decides.*

**Blocks:** the route, and whether Plan → Year is reopened.

---

## Session 6, second pass — the training corpus (2026-08-01)

### Q-61 · Is the training corpus opt-in per school, and what does the school get back? 🔴
`D-54` starts storing children's exam papers — images, the model's read, the human's correction —
for a purpose that is **not running that school**. It is the first data in the product like that,
and it belongs to the school, not to us.

This is not a blocker on building the capture (the pair should be recorded either way — it cannot
be recovered later). It is a blocker on **using** it.

- **(a) Silent.** Everything is already stored as evidence; treat training as an internal use of
  data we hold anyway. Cheapest, and the one that reads worst if a school ever asks.
- **(b) Org setting, default off**, agreed at onboarding — the operator turns it on when the school
  says yes. Fits the existing shape (`parent_portal_enabled`, `band_a_min` live in
  `organizations` already).
- **(c) Opt-in *and* something back** — the school that contributes gets the improved recognition
  first, or a line in their pricing.

*Claude recommends **(b)** now and **(c)** as the honest version. Also: the export must be
de-identified, and note that **de-identification cannot happen at capture** — the matcher needs the
name to verify the row, and the child's name is written on the image itself in their own hand.
So the corpus is PII until it is cropped or redacted on the way out, and that step has to exist
before the first export, not before the first row.*

**Blocks:** using the corpus. Not building it.

### Q-62 · Can a locked exam be edited, and by whom?
`D-53` makes the lock the trusted record and `D-54` makes it the training label. So "edit anyway"
now costs more than it used to.

- **(a) Nobody.** Wrong: a real mis-typed mark must be fixable, and a system that refuses is one
  people work around by keeping a parallel register.
- **(b) The teacher, freely.** Then the lock means nothing.
- **(c) Admin unlocks, with a reason; the unlock is an appended row, never a mutation** (law 3),
  and the affected training pair is flagged rather than silently rewritten (`S-139`).

*Claude recommends **(c)**. Note this is the same shape three other modules already use —
`plan_approvals`, `demo_request_notes`, `leave_request_events` — where the status is a derived
cache of the newest appended event. There is a well-worn pattern to copy.*

**Blocks:** the lock's UI, and whether `S-137`'s stored diff can be trusted.

---

## Session 7 (second pass) — Events & dates (2026-08-01)

`D-56`–`D-60` closed `Q-57` and `Q-59` and reshaped `Q-54`. Three new ones.

### Q-63 · What are the real sources for the catalogue, and what is the annual cycle? 🔴
**The research task, and the last thing standing between this module and a build.** `D-60` decided
the *storage* (fetch, store in our database, platform-owned per `S-149`). It did not decide the
*source*, and the four kinds of date asked for do not come from one place:

| What | Likely source | Shape |
|---|---|---|
| **State-wise school holidays** | each state's annual gazetted holiday list | PDF, per state, published late in the preceding year |
| **All-religion dates** | almanacs / panchang | regionally **disagreeing** — two schools 200km apart can keep Ugadi on different days |
| **International days** | the UN observances list | stable, machine-readable, the easy one |
| **General calendar** | national gazetted holidays | stable, several free APIs cover it |

What the research must come back with, concretely:

1. Is there any **single machine-readable feed** covering Indian *state* school holidays? *(Claude
   expects no — `S-151`.)*
2. For each source: licence, update cadence, how far ahead it publishes, and how it is keyed.
3. Which religious dates are **safe to state as a single date** and which must be shown as
   *"observed 12–13 Oct depending on region"* — because a confidently wrong single date is worse
   than an honest range.
4. Cost and rate limits, if any source is commercial.
5. **The annual cycle**: who re-runs this each year, in which month, and what the super-admin sees
   when a new year's dates land.

*Claude's expectation, stated so the research can prove it wrong: this ends as **a small importer
per source plus one annual human review**, not "an API we call". Designing for one clean API and
discovering the fragmentation in month three is the expensive order to find out.*

**Blocks:** the catalogue only — steps 1–6 of the build order run on the school's own dates and
birthdays without it.

### Q-64 · Do teachers see suggestions, or only approved dates?
`D-57` puts approval in the admin's hands. It doesn't say whether a teacher's My Day strip shows
*"Guru Purnima (suggested)"* before anyone approves it.

- **(a) Approved only.** The teacher's surface never shows anything provisional. Simple, and it
  means the strip is always true.
- **(b) Suggestions too, marked.** More useful on a day the admin hasn't got to yet — a teacher
  can still mention it at assembly.

*Claude recommends **(a)**. The strip's whole value is that it costs zero attention and is never
wrong; a provisional row makes her decide whether to trust it, which is more expensive than the
information is worth. The admin's screen is where provisional belongs.*

**Blocks:** the My Day strip's query, and whether `D-57`'s decision row is read on the teacher
path at all.

### Q-65 · Locking a past or current day — what happens to what was already captured?
`D-57` is written for future dates: a suggestion arrives, the admin approves, the day locks. But
holidays are also declared **at 7am the same morning** (a bandh, a flood, a death), and the record
for that day may already contain marked attendance, a logged topic, or set homework.

- **(a)** Locking is future-only; today and the past are corrected some other way. Clean rule,
  refuses the most common real case.
- **(b)** Locking any day is allowed, and existing capture for it is **kept and shown**, not
  deleted — the day is closed but the record stays honest (law 3).
- **(c)** Locking deletes/voids the capture for that day.

*Claude recommends **(b)**, and strongly against (c) — a school that closed at 11am genuinely did
teach period 1, and destroying that is both a data loss and a law-3 violation. `blocks_periods`
already expresses "periods 3–8 are gone, 1–2 happened", which is exactly the half-day case.*

**Blocks:** the approval sheet's date rules, and `S-145`'s "locked periods vanish from capture" —
which must mean *vanish from what's still expected*, never *erase what was recorded*.

---

## Session 8 — Fee collection (2026-08-01)

### Q-66 · Does a teacher assigned a fee follow-up see the amount? 🔴
**The fence, and it runs straight through `D-65`.** `D-63` says only admins see fee data; `D-65`
hands the chase to a teacher. Both cannot be taken literally.

- **(a) Family and subject, never the amount.** *"Fee follow-up — Kabir Shah (8-B). Please speak to
  the family and record what they say."* The fence holds exactly as written.
- **(b) She sees amounts for her own students.** A deliberate breach, narrowly scoped.
- **(c) Only admins can be assigned fee follow-ups.** Fence intact, but it wastes the one person
  who has a relationship with the family.

*Claude recommends **(a)**, strongly. The reason the fence exists is not confidentiality for its
own sake — it is that **a teacher who knows which families are behind on fees treats those children
differently**, and every child on that list has done nothing wrong. (a) keeps the relationship and
drops the number. The parent already knows what they owe.*

*If (a): also block the inference routes — no sorting her tasks by amount, no "large / small"
badge, no count of how many families are behind in her class.*

**Blocks:** the follow-up task's content, and therefore whether the teacher half of `D-65` can be
built at all.

### Q-67 · How is a quarter defined?
`D-64` analyses collection quarterly. Three candidate keys, and two break:

- **(a) `installment_number`** — breaks when structures differ. Juniors on 2 instalments and
  seniors on 4 means *"instalment 1"* is a different quarter per class, and the school-wide figure
  is nonsense.
- **(b) `label`** — free text. *"Q1"*, *"Quarter 1"*, *"1st term"*, *"April"* — one school will
  produce all four and the grouping fragments.
- **(c) The instalment's `due_date` falling inside a computed quarter window** over the academic
  year.
- **(d) The school declares its quarters explicitly in settings.**

*Claude recommends **(c)**, with (d) as a later refinement if a school's quarters aren't even.
(c) works across differing structures, aligns every class to one calendar, needs no new column,
and matches what the admin means — "money due Jul–Sep". An instalment with **no due date** becomes
`unscheduled`, a word, never silently bucketed into Q1 (ux §10).*

**Blocks:** the read service, and every figure on the collection board.

### Q-68 · Do arrears count as pending? 🔴
*(verified)* `student_fees.opening_dues` carries last year's unpaid balance and is **excluded from
every roll-up**: not in `total_fee`, not in `collected_fee`, not in `overdue_amount`, and not in
`student_fee_status`, which the model states outright — *"status is still driven by instalments
only."*

Consequence today: **a student carrying ₹20,000 from last year, with this year's instalments paid,
reads `paid`** — and is absent from the defaulter list. The school's worst debtors are the ones the
screen cannot see.

- **(a) Arrears count.** `summary`, `overdue_students` and `status` all include them.
- **(b) Arrears stay separate** but are shown as their own figure and their own list — *"₹3.2L in
  arrears from 2025-26, 22 families"*.
- **(c) Leave as is.** The board reports current-year collection only, and says so.

*Claude recommends **(b)**. (a) is tempting but it mixes two different collection problems — this
year's cash flow and last year's bad debt need different conversations and often different people.
(c) is defensible only if the board's headline says "this year" out loud, every time. What is not
defensible is today's behaviour, where the number is silently incomplete and nothing on screen
admits it.*

**Whichever is chosen, all three reads move together** — `summary`, `overdue_students` and
`student_fee_status` — or the screens will disagree with each other (ux §9).

**Blocks:** what the collection board is allowed to claim, and whether the defaulter list is
complete.

### Q-69 · Does the parent get a full fee view, or only a reminder?
`D-66` says notification + a reminder block on the portal home. It doesn't say whether there is
more behind it.

- **(a) Reminder only** — one line, a date, what's paid. No tab.
- **(b) A small fee page** — the year's instalments and their status, still read-only.

*Claude recommends **(a)** for this version. A parent's two questions are "how much" and "by when",
and both fit on one line; a fee tab invites the ledger, and the ledger invites "why was I charged
this", which is a counter conversation, not a screen. Ship (a), and let the number of parents who
ring asking for more decide whether (b) is ever needed.*

**Blocks:** the parent projection's allowlisted fields.

### Q-70 · Who receives the reminder — every guardian, or the primary only?
`guardians` allows several per student, each with a phone and an `is_primary` flag, and siblings
roll up to one parent login.

- **(a) Primary only.** One message, one family.
- **(b) Every guardian on the record.** Nobody misses it — and two parents may get the same
  money message, which in some families is a problem the school just created.
- **(c) Primary, with the others visible to the admin to ring manually.**

*Claude recommends **(c)**. Money is the one topic where messaging both parents can land badly, and
the admin is already looking at the row — give them the second number rather than sending a second
message. Note this differs from the absence alert, which deliberately reaches everyone (`SPRD §7`),
and the difference should be deliberate rather than inherited.*

**Blocks:** the reminder's recipient list and the throttle's key (`S-156` throttles per instalment
— per instalment per *family*, not per guardian).

---

## Session 9 — Bands, the support programme (2026-08-01)

### Q-71 · With per-subject bands, is the **overall** letter retired or kept? → **ANSWERED, `D-75`**
**Retired — option (a).** *"This categorization is based on subject."* A child has an English band,
a Hindi band and a Maths band, and no fourth number. Where one chip is all there is room for, it
reads **"C · Hindi"** — the lowest band with the subject that earned it, never an average
(`S-186`). Every read site listed below changes; the recommendation was taken as written.

<sub>Original question, kept for the reasoning:</sub>
`D-68` makes the band per subject. Today there is exactly one letter per child, written by
`categorize_from_cycle` from the sum of every score in a cycle, and read by `_current_tiers`,
`current_band_map`, `band_board`, `recommendations._current_tier`, the students directory chip, the
class-analytics donut and `growth.py`.

- **(a) Retire it.** A child has an English band, a Hindi band and a Maths band, and no fourth
  number. Every read site above changes.
- **(b) Keep both** — per-subject bands plus a computed overall letter for the directory chip and
  the report card headline.
- **(c) Keep the overall letter as the only one, and treat per-subject as a later phase.**

*Claude recommends **(a)**, without much hesitation. (b) creates two answers to "what band is
Kabir in" — a child who is A in Maths and C in English would carry an overall B that describes no
part of him, and it would appear on the directory chip, which is the most-seen surface of the
three. This folder has found the same class of defect in five consecutive modules: one fact
computed two ways. Do not add a sixth deliberately. Where a single chip is genuinely needed, render
**"C · English"** — the worst band with its subject — not an average.*

**Blocks:** the data model, and the size of the read-path rewrite (`S-173`).

### Q-72 · Who owns a C child — one owner, or one per subject? → **ANSWERED, `D-77`**
**One owner per subject — option (a).** *"One owner per subject is the best way to go."* A child C
in two subjects has two owners and appears on two `/support` lists. The cost named below is
accepted: that is two people doing the work, not one person doing it twice. **Every stuck row must
name the subject** (`S-188`) or two owners will each assume the other is handling him.

<sub>Original question, kept for the reasoning:</sub>
`D-71` gives every C child an assigned teacher. A child who is C in both English and Maths makes
the question unavoidable.

- **(a) Per (child × subject).** Kabir has an English owner and a Maths owner; each knows exactly
  what hers is. Two rows, two check-ins a week for that child.
- **(b) One owner per child**, normally the class teacher, who coordinates across subjects.
- **(c) One owner per child, per term**, chosen by the admin — sometimes the class teacher,
  sometimes the subject teacher.

*Claude recommends **(a)**. The whole value of the programme is that someone can answer "is he
closer to B", and only the person who teaches that subject can. (b) puts a class teacher in charge
of moving a child in a subject she may not teach, which produces a check-in that says "spoke to the
English teacher" every week. The cost of (a) is real — a child in two subjects gets two check-ins —
but that is two people doing the work, not one person doing it twice.*

**Blocks:** the owner column, `/support`'s grouping, and the admin's reassign action.

### Q-73 · Is the log daily, or is the weekly check-in the unit? 🔴
The founder said *"logs today they did this and that"* and *"maybe weekly or sometime we
evaluate"*. Both are on the table and they produce very different products.

- **(a) Weekly check-in is the unit** (`S-165`); a daily note exists but nothing ever asks for one.
- **(b) Daily log is the unit**; the weekly evaluation is a roll-up of the week's notes.
- **(c) Cadence is per-subject configuration** (`D-74` already contemplates a settings row).

*Claude recommends **(a)**, and considers this the single decision that determines whether the
module is still in use in November. Six children × a daily note = thirty entries a week from one
teacher who is also teaching a full timetable; the first week it will be done, the third week it
will be "did flashcards" thirty times, and by then the data is worse than nothing because the
admin's report is built on it. (c) is a fine refinement later, but shipping a configurable cadence
before anyone has written a single check-in is configuring a habit that doesn't exist yet.*

*Whichever is chosen, `S-164` holds: the page opens with the week already filled in from capture
that already happened. That is what makes even (b) survivable.*

**Blocks:** the check-in table's grain, the reminder job, and the `/support` row states.

### Q-74 · Who may declare that a child has moved C → B? → **ANSWERED, `D-76`** — *a test does*
**Option (c), with the rigidity removed.** *"There will be a separate test and based on that test
the reband should occur — and the teacher can consider one of the normal CET or slip tests to mark
as the band exam test, and it's up to her choice."*

My objection to (c) below was that a child who plainly reads fluently would sit in C until the
term's exam, and that the decision would be handed to whichever paper happened to be set.
**Promotion removes both.** The owner who thinks a child is ready marks next Tuesday's slip test as
the band test for that subject, and the move happens on evidence. Every band row is now evidenced
by construction — which is what `S-178` was trying to get to procedurally.

What the owner does at `/support` is therefore **propose readiness**, not press the final button;
the test presses it. Three guards ride along: promotion is a **flag, not a type change** (`S-182` —
re-typing a slip test deletes it from the exam analytics), a promoted test must be **locked**
(`D-53` — an unverified transcription must not move a child between tiers) with its total marks and
how many sat it on screen (`S-184`), and it re-bands **one subject** (`S-187`).

<sub>Original question, kept for the reasoning:</sub>
- **(a) The owner**, from the child's page, with the evidence sheet (`S-178`).
- **(b) The admin only** — the owner proposes, the admin files.
- **(c) Only a band test** — the tier moves when `categorize_from_cycle` says so, never by hand.

*Claude recommends **(a) with the evidence shown**, and the admin able to override. (c) sounds
rigorous and is actually the weaker option: it means a child who plainly reads fluently stays in C
until the term's test, and it hands the decision to whichever paper happened to be set. (b) adds a
queue to a school that already has one. What makes (a) safe is not who presses the button but that
the resulting `student_bands` row **carries what it stood on** — the exit criterion, the last test
percentage, the check-in trend — the way `categorize_from_cycle` already writes "band test: …".*

*(verified)* Today `set_band` is `require_coordinator_up` (admin-only) and takes a free `note` that
nothing fills in from the UI, so (a) needs both a permission change and the evidence sheet.

**Blocks:** the move action's permission, and the note the band row carries.

### Q-75 · Does a parent ever hear anything about this?
P4 says the tier never reaches a parent, and *(verified)* it holds today — `parent_portal.py` drops
bands and band history explicitly, and `test_parent_portal.py` asserts it.

- **(a) Nothing, ever.** Status quo.
- **(b) The school's effort, never the tier** — *"Kabir is in extra reading practice with
  Ms Priya on Tuesdays."* A fact about what the school is doing, with no letter, no tier name, no
  comparison and no count.
- **(c) A summary at term end** written by the owner, reviewed by the admin before it is sent.

*Claude recommends the founder decide this deliberately rather than by omission. (a) is safe and is
also a real problem: a child in a support programme whose family is never told means the school is
doing work it gets no credit for, and the parent finds out from the child. (b) is the smallest
honest step and does not touch the fence — the fence is about the **letter**, which is a private
tier the school uses to organise teaching, not about the fact that a child is getting help. (c) is
where this ends up eventually, and it needs a review step because a teacher writing to a parent
about a struggling child is the highest-stakes text in the product.*

*If anything is ever sent: never a letter, never "Band C", never a count of C children in the
class, never a comparison, and never on a screen beside another child's name.*

**Blocks:** nothing being built now. Blocks the parent projection later.

### Q-76 · Are descriptors per subject × band, or also per grade?
`D-69` gives each band a written descriptor per subject. Nine texts. Per grade group it is 27–72.

- **(a) Per subject × band only.** Nine texts, one meaning of "Band B in English" school-wide.
- **(b) Per subject × band, with optional grade-group overrides** (`S-175`) — the nine are the
  default, a school that wants "Band B in English for classes 1–3" writes it.
- **(c) Per grade × subject × band**, required.

*Claude recommends **(b)**. (c) is correct pedagogically and will not be filled in — a setup screen
with 72 empty textareas gets abandoned, and a descriptor nobody wrote is worse than a slightly
imprecise one everybody reads. (a) is what to ship; (b) is one nullable scope column that costs
nothing to add now and is very expensive to retrofit.*

**Blocks:** the descriptor table's key, and the setup screen's shape.

### Q-77 · Is a band ever scoped to a **skill** rather than a subject? → **effectively (a)** via `D-75`
`D-75` says the band is per subject and there is no other letter, so the skill scope is not used by
bands. Left open only to record the disposal of `student_bands.scope_skill_area_id`: drop it, or
leave it unused. *Claude: leave the column, stop pretending it is a band scope — `skill_areas` keeps
its real job, the diagnostic radar on the report card.*

<sub>Original question, kept for the reasoning:</sub>
`student_bands.scope_skill_area_id` exists, points at `skill_areas` (seeded Reading / Writing /
Speaking / Math), and has **never been written by any code path** — while subjects are English /
Mathematics / Science / Social Studies / Hindi. Two overlapping vocabularies, one unused.

- **(a) Subject only.** The skill scope is dropped from bands and `skill_areas` keeps its existing
  job — the diagnostic radar on the report card.
- **(b) Both** — a child can be banded in English *and* in Reading.
- **(c) Skill only**, and "English" bands become "Reading + Writing" bands.

*Claude recommends **(a)**. The founder said subject, schools timetable subjects, and teachers own
subjects — the owner in `D-71` is a subject teacher. (b) is the two-definitions defect wearing a
different hat, and "is Kabir in the reading programme or the English programme" is a question
nobody should have to ask.*

**Blocks:** whether the migration adds a subject scope beside the skill scope or replaces it.

### Q-78 · What does Band A get?
As described, the programme does a great deal for C, a little for B, and nothing for A.

- **(a) Nothing.** A means "not our problem", which is honest about where the effort goes.
- **(b) The harder version of the same work.** *(verified)* This costs nearly nothing:
  `daily_checks.band_scope` already accepts `'A'` and the generator already writes band-scoped
  checks — it simply never generates one for A today.
- **(c) An enrichment programme with its own owners and check-ins**, mirroring C.

*Claude recommends **(b)**. Under (a) the letters quietly become good/average/bad, teachers read
the whole thing as remedial-only, and the tier drifts into being the label P4 exists to prevent.
(b) changes what the letter means for one line of generator code. (c) is a second programme and
should not be decided until the first one has moved anybody.*

**Blocks:** nothing. Worth deciding before the letters harden into a reputation.

### Q-79 · The test says B and the teacher says C — which wins, and is the disagreement kept?
**Narrowed by `D-76` to the *entry* assessment only.** Movement between bands is now always a test,
so the disagreement can only arise when a class is first filed — where the marks pre-fill each row
and the teacher moves the ones she disagrees with. The recommendation below is unchanged and now
costs even less.

`D-70` makes both routes first class at entry, so they will disagree.

- **(a) The teacher wins, silently.** Her judgement replaces the suggestion.
- **(b) The teacher wins, and the disagreement is recorded** on the band row — *"teacher assessment
  (test suggested B)"*.
- **(c) The test wins**; a teacher override needs the admin.

*Claude recommends **(b)**. The shape already exists — `band_board` returns `current_tier` **and**
`suggested_tier` side by side, and the UI shows both — so the honest version costs one string in a
note. It also produces the only signal that would ever tell a school its thresholds are wrong: a
subject where teachers override the test in one direction, every time.*

**Blocks:** the assessment screen's save payload, and the band row's note.

---

## Session 9, second pass — promotion and per-subject owners (2026-08-01)

### Q-80 · A promoted test only some children sat — what happens to the rest?
`D-76` lets a teacher promote an ordinary slip test, and slip tests are sat by whoever was in the
room. 12 of 38 present is normal.

*(verified)* **The code already does the right thing.** `categorize_from_cycle` walks the class
roster, and a student with no score in that cycle is counted into `no_score` and **skipped** — his
band is not touched, not reset, not defaulted. The question is therefore only about the **screen**:

- **(a) Silent.** The 26 keep their band and nothing says so.
- **(b) Stated.** *"12 re-banded · 26 didn't sit this test and keep their current band."*
- **(c) Blocked** below some participation threshold.

*Claude recommends **(b)**, and it is close to free. (a) is how a teacher ends up believing the
whole class was re-assessed on Tuesday — which is exactly the not-captured-is-not-a-zero rule
(ux §5) applied to a band instead of an attendance cell. (c) is the validator-that-refuses problem
again; `S-184`'s warning already covers the case where the room was too empty to mean anything.*

**Blocks:** one line of copy on the promotion sheet. Nothing structural.

### Q-81 · Does filing a re-band show the moves for review first?
*(verified)* `categorize_from_cycle` is **one tap and it commits** — it appends a band row for
every student whose tier changed, with no preview. Under `D-76` that same tap can now be fired off
a slip test, and `student_bands` is append-only, so a mistaken re-band is **permanent** in a
child's record; the only correction is another row saying he moved back.

- **(a) Review first.** *"3 moving up, 1 moving down, 8 unchanged, 26 didn't sit it"* → Confirm.
- **(b) One tap, as today**, with an undo that appends a reversal.
- **(c) One tap for a dedicated band test, review for a promoted one.**

*Claude recommends **(a)**, for every route. It is one screen between a teacher and a permanent row
in a child's history, it is where the down-moves get noticed (a child slipping B → C is the most
consequential thing this module ever does and it currently happens without anyone reading his
name), and the product's own doctrine already says so — every AI proposal lands in a human-confirm
surface, and this is a bigger claim about a child than any transcription.*

**Blocks:** the promotion flow's step count. Worth deciding before it is built, not after.
