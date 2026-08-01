# Module — Events & dates

The school's social calendar: whose birthday it is, what the school has planned, and which
festival or observance is coming — on one card, in time to do something about it.

**Sessions:** 7 (2026-08-01)
**Related:** [`syllabus.md`](syllabus.md) *(the same `calendar_events` rows drive the
effective-days engine)* · [`parent-access.md`](parent-access.md) *(`S-130`)* ·
[`class-teacher.md`](class-teacher.md) *(whose class the birthday is in)*

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Admin** | ~8am, before assembly | desktop, a 10-second glance | *"Is there anything today — or coming — that I should already be prepared for?"* |
| **Teacher (subject)** | 9:02, forty children in front of her | phone, 3 seconds | *"Is it anybody's birthday in this room?"* |
| **Class teacher** | morning roll call, her own class | phone | *"Whose birthday is it in my class — and is she even in today?"* |
| **Admin (setup)** | once, at roster import | desktop | *"Where do the birthdays come from?"* |
| **Parent** | any evening | phone, weak connection | *"Is school open on Monday?"* — see `S-130`, `Q-56` |

The admin and the teacher want the **same feed at different depths**. That is a card and a page,
not two modules.

## 2 · What they must be able to decide

- Whether **today** needs anything done — an assembly mention, a wish, decorations out.
- Whether a **coming** date needs lead time. Rehearsal for Independence Day is three weeks; a
  birthday is the morning of.
- Whether to **declare a school holiday** for a festival — and this is the *only* decision in the
  module that is allowed to touch teaching days (`S-122`).
- Who to **wish**, today, and through which mouth (assembly, the class, a message to the guardian).

## 3 · Where it stands today *(verified)*

**Three of the module's four pieces are already in the building. None of them can be seen.**

| Piece | Status |
|---|---|
| A school calendar with dated entries | ✅ `calendar_events` — `models/academics.py:153-180`. Types `holiday` · `exam_block` · `event` · **`celebration`**, `start_date`/`end_date`, `affects_teaching`, `blocks_periods`, `notes`. |
| A UI to put a festival on it | ✅ Plan → Year paints it — `web/src/app/(app)/plan/page.tsx:43-48`. **"Celebration" is already one of the four brushes.** |
| Anything that reads it back to a human | 🔴 **Nothing.** Its only consumer is the effective-days engine (`services/calendar.py` — `expand_blocked_dates`, `teaching_days`, `effective_periods`). |
| A date of birth | 🔴 **Does not exist.** Not on `students` (`models/students.py:39-64`), not on `users` or `memberships` (`models/org.py`). |
| DOB in the roster importer | 🔴 Not in `FIELDS` or `SYNONYMS` — `services/roster_import.py:23-48`. |
| A festival / observance catalogue | 🔴 Does not exist in any form. |
| **`D-58`'s three lock levels** | ✅ **All three already exist**, and `effective_periods` already prorates a partial day — *"an event eating 3 of 8 periods leaves 5/8 of that day (V2-P7)"* (`services/calendar.py:84-131`). See `S-142`. |
| **`D-59`'s teacher-side block** | ✅ `not_held_reason` exists on the period (`services/classroom.py:470`); the timesheet side is a `core/work_types.py` bucket, which has **no CHECK constraint** by design. What's missing is the link to the event (`S-147`). |
| **`S-143`'s cost preview** | ✅ `PlannerService.forecast_org(m, year_id)` batches the whole school's forecast in one pass — built for DASH3 PR-6. A second caller, not a new engine. |
| **A platform-level catalogue's home** | ✅ V3-P0's platform layer exists — `require_super_admin`, `/platform` tabbed area (Schools · Enquiries), and `demo_requests` is a working example of a table with **no `org_id` and no RLS** (`S-149`). |

Two more facts that constrain the design:

- **`NOTIF_TYPES` is a CHECK constraint** (`models/notification.py:18-25`). Any birthday
  notification needs a migration widening `ck_notifications_notif_type_valid` — the `substitute`
  precedent from DASH3.
- **Name collision.** `CelebrationProvider` (`web/src/components/celebration/`) is the
  **task-completion confetti layer**. It has nothing to do with this module (`S-131`).

## 4 · What's wrong with it

### 🔴 Defect 1 — the school calendar is write-only

An admin paints *"Diwali"* on the year calendar in April. The product never mentions Diwali again.
The row exists, is correct, is org-scoped, and is read by exactly one function whose job is to
**subtract it from the teaching total**. The single most-asked question about a calendar — *what is
on it this week* — has no surface anywhere in the product.

The founder is not asking for a new capability here. He is asking for the **read side of a table
that has had a write side for a year**.

### 🔴 Defect 2 — you cannot record a festival without shrinking the year

`CalendarEventCreate.affects_teaching` defaults to `True` (`schemas/calendar.py:17`), and the paint
UI **never sends the field** (`plan/page.tsx:82-90`). So:

> Painting *"Celebration — Guru Purnima"* on the day the school is **open** silently removes a
> teaching day from every class-subject forecast in the school.

There is no way, in the UI, to say *"this is on the 9th and we are open"*. Which means the moment
this module gives schools a reason to record more dates, it gives them a way to corrupt the
planner. **The read side cannot ship before this is fixed** — every forecast, every RAG colour and
every "will we finish the portion" answer in the product is denominated in effective teaching days.

### Defect 3 — the module is dead until DOB exists, and DOB has no way in

A birthday card with no birthdays is not an empty state, it is a broken screen. DOB is on every
admission form in India (board registration requires it), so schools *have* it — but it arrives in
the xlsx the school hands over at setup, and the importer does not look for it (`S-124`).

## 5 · Ideas and directions

### Decided — `D-nn`

- **`D-51`** — the module exists, and it is a **card**: *today's specials* on top, *the next 7
  days* under it, on both the admin dashboard and the teacher's. A fuller half-page/month view
  behind it. Founder's shape, verbatim.
- **`D-52`** — three sources feed one feed: **student birthdays** · **the school's own calendar**
  · **festivals and observances from outside the school** (Diwali, Holi, Guru Purnima,
  International Mother's Day).
- **`D-56`** — **student DOB is captured at setup**; **staff DOB is nullable, optional and
  self-entered** from the profile screen; **guardian DOB is not captured** in this version.
  *(Closes `Q-59` and `Q-57`.)*
- **`D-57`** — 🔑 **the calendar is a stream of suggestions, and approval is the commit.** Setup
  fixes only a brief version of the year; it keeps changing. Dates arrive as suggestions for the
  day and **nothing they imply happens until the admin approves**. On approval the date locks into
  the school's own calendar. *(This retires `S-122`'s button and makes the fence structural — a
  suggestion cannot reach `calendar_events` by any other route.)*
- **`D-58`** — approval has **three levels**: lock the whole day · lock specific periods · school
  runs as usual with celebrations at assembly/prayer time.
- **`D-59`** — **no plan adjustment in this version.** The admin locks; the **teacher blocks the
  class or the timesheet cell against that reason**. Redistributing a year plan is a later
  version.
- **`D-60`** — the catalogue is **fetched from the internet and stored in our database** —
  general calendar data, **state-wise school holidays**, international observance days, and dates
  for **all religions**. Sourcing method is a research task (`Q-63`). *(Supersedes `S-123`.)*

### Proposed — `S-nn`

<!-- Second pass (D-56…D-60) first: these are the ones that matter now. -->

**`S-142` · ✅ The three lock levels already exist, and the engine already prorates them.**
*(verified)* `D-58` describes, from the product side, exactly the schema V2-P7 shipped:

| `D-58` level | Fields on `calendar_events` | `effective_periods` (`services/calendar.py:84-131`) |
|---|---|---|
| Lock whole day | `affects_teaching=True`, `blocks_periods=NULL` | the day leaves the week entirely |
| Lock specific periods | `affects_teaching=True`, `blocks_periods=[1,2]` | day contributes `1 − lost/periods_per_day` |
| Runs as usual | `affects_teaching=False` | full teaching day |

So the whole locking feature is **a UI over fields that exist and are already tested**. And it is
also **the fix for the module's live defect** — the paint UI silently drops `affects_teaching`
today; `D-58` makes that choice the central act of the flow, so the bug cannot survive the
feature. Build the approval sheet and the defect closes with it.

**`S-143` · 🔴 The approval sheet must show the cost *before* the admin approves.**
`D-59` defers "adjusting the plan", but half of that adjustment is **not deferrable and already
happens**: `effective_periods` is computed live, so the instant three days are locked for Diwali,
every class-subject's remaining capacity shrinks and **RAG colours move across the school** — with
nothing on the syllabus board explaining why. A principal who locks three days and then watches six
subjects turn amber concludes the system is broken.

So the sheet says it first, in a sentence:

> *"Locking 15 Aug (whole day) removes **8 periods**. 6-B Maths and 9-A Science move from green to
> amber. 14 other class-subjects are unaffected."*

`PlannerService.forecast_org(m, year_id)` already batches exactly this computation for the whole
school in one pass — it was built for DASH3's PR-6. This is a second caller, not a new engine.

**`S-144` · The half of `D-59` that is deferred is already forbidden — record it as permanent.**
Rewriting approved plan entries around a new holiday isn't a "later version" feature, it is a **P2
violation**: *the approved plan is locked; re-forecast is computed from baseline + logs +
remaining effective periods, never stored as mutated plan rows.* Writing "v2 will adjust the plan"
into a roadmap invites somebody to implement it literally in eighteen months.

What a later version *can* legitimately add is a **proposal the admin approves** — "these 4 topics
no longer fit; move them to Term 2?" — which lands as a new baseline through the existing
`extend_plan` / approve path. Never an automatic rewrite.

**`S-145` · 🔴 A locked period must vanish from the teacher's capture surface, not sit there red.**
If the admin locks 15 August and every teacher still sees eight period rows on My Day saying
*"not logged"*, the product has invented work on a holiday and made the capture rate lie. A locked
period should not appear as pending, must not count in any denominator, and must not reach the
16:00 unmarked-teacher reminder job (`jobs.run_teacher_reminder`) or the daily report's
attendance-without-log ambiguity rule. This is `ux §5` — *not captured is never a failure* — applied
to a day the school itself cancelled.

**`S-146` · The teacher's block and the admin's lock are different scopes. Don't merge them.**
`D-59` gives the teacher a block, but the case it actually serves is **not** the school-wide one:

- **admin locks** → school-wide or period-wide, every class, decided in advance;
- **teacher blocks** → *this* class, *this* period — 8-A went to the Independence Day rehearsal
  while 8-B carried on teaching.

Merging them double-counts: the day is already gone from the capacity calculation, and a teacher
also marking it removes it twice. Rule: **if the admin locked it, the teacher is never asked. If
the admin didn't, the teacher's block is per-class and the only record that exists.**

*(verified)* The teacher side already has a home — `not_held_reason` on the period
(`services/classroom.py:470`), and the timesheet side is a `core/work_types.py` bucket, which
deliberately has no CHECK constraint so a school's own word survives.

**`S-147` · The reason points at the event, not at free text.**
*"Not held — Independence Day rehearsal"* typed by forty teachers in forty spellings answers
nothing. If the block references the approved event row, the school can ask **"what did Diwali
cost us in periods?"** and **"which classes lost the most to functions this term?"** — and the
timesheet's work-type bucket lines up with the same event. Free text stays available as a note; it
is not the key.

**`S-148` · Dismissal is append-only and permanent (law 3).**
*"We don't observe this"* must survive the year, and next year. A dismissal is a row, not a
delete — same shape as `plan_approvals` and `demo_request_notes`. Otherwise the same suggestion
returns every week and the admin learns to ignore the feed, which kills the module.

**`S-149` · The catalogue is platform data, not org data.**
`D-60` stores it in our database; the question it leaves open is *whose*. Answer: **no `org_id`,
no RLS policy, `require_super_admin` on every write** — the `demo_requests` / EN-1 shape from
V3-P0, which already exists and is already proven. One curation serves every school, one
correction fixes every school, and `/platform` gains a third tab beside **Schools · Enquiries**.
This keeps the human review `S-123` was protecting while dropping the code deploy.

**`S-150` · Every suggestion carries its provenance, and the admin can see it.**
*"Suggested · Telangana state holiday list 2026"* and *"Suggested · international observance"* ask
for very different amounts of trust, and the admin approving them is the last human in the chain.
An unattributed date is one they will either approve blindly or ignore entirely — both bad. Show
the source on the row; store it on the catalogue entry.

**`S-151` · Design for "several sources plus a human", because that is what the research will
find.**
Worth saying before `Q-63` is investigated: for India there is very likely **no single
authoritative, machine-readable feed** covering state-wise school holidays *and* all religions
*and* international days. State holiday lists are gazette PDFs published per state, late in the
preceding year; religious dates come from almanacs that disagree regionally; international days
are a UN list. So the realistic architecture is **a small importer per source + an annual
super-admin review**, not "an API we call". Building for one clean API and discovering this later
is the expensive version.

---

<!-- First pass (D-51/D-52). Still standing except where superseded above. -->

**`S-121` · Three sources, one feed, one new column.**
Do not build an `events` table. `calendar_events` already holds the school's own dates; a birthday
is **derived** from a DOB, not stored as an event; observances are **reference data**, not org
data. The whole module is one nullable `students.date_of_birth`, one shipped catalogue file, and
one read service that unions three sources into a dated list. One computation, many renderings
(ux §9). If this module ends up with three new tables, it was designed wrong.

**`S-122` · 🔴 The catalogue must never write `calendar_events`, and never eat a teaching day.**
→ **ACCEPTED and strengthened by `D-57`.** The principle stands untouched; the *mechanism*
changed. It is no longer a button somebody must remember to press — **approval is the only route
that exists**, and `D-58` makes the open/closed choice the central act of it. Kept in full because
the reasoning is the reason `D-57` is shaped the way it is.
The most severe trap in the module, and it is a two-line mistake to make. *Holi is on the 14th* and
*the school is closed on the 14th* are different facts:

- an **observance** is informational — it renders, it never subtracts;
- a **holiday** is the admin's declaration — it subtracts, and only a human creates it.

If a festival pack ever auto-creates rows, it silently rewrites the effective-days denominator
behind every plan forecast in the product — the same defect as §4.2, but at scale and unattended.
The bridge between the two is an explicit **"Add to school calendar"** button on the observance
row, which opens the normal event sheet with the date prefilled and makes the admin choose
*holiday / open*. One tap, fully auditable, never automatic.

**`S-123` · The dates come from a versioned file in the repo, not from a model and not from a
live API.**
→ **SUPERSEDED by `D-60`** — the founder chose *fetch and store in our database*, and is right:
28+ states × per-year × multiple traditions is too much for a hand-edited file, and it must be
correctable without a code deploy. **What survives, and must:** the "ask a model for dates" row of
the table below stays rejected, and the human review the file gave us is preserved by `S-149`
(platform-owned, super-admin curated) and `S-150` (every suggestion shows its source).
This is the load-bearing decision hiding inside *"or from the internet"*. Diwali, Holi, Guru
Purnima, Eid, Onam, Pongal are **lunisolar** — they move every year, and regional reckonings
differ. Three ways to source them:

| Source | Verdict |
|---|---|
| Ask the model | ❌ **No.** A model asked *"when is Diwali in 2027"* answers confidently and can be wrong, and **there is nothing in the product to check it against** — no roster, no column list. This is exactly the shape `Q-51` fenced in session 6: an unverifiable claim, stored. A wrong Diwali date is a school that decorates on the wrong day. |
| A live third-party API | ❌ Not for this. A network dependency, a key to rotate and a vendor to outlive, for data that changes **once a year** and is knowable a year ahead. |
| A checked file, per year, in the repo | ✅ **Yes.** `app/data/observances/2026-27.json`. Dates for the year, each with a tier and a region; reviewed by a human once, versioned with the code, diffable in a PR, works offline, identical in every environment, and free. |

AI's legitimate job in this module is **phrasing, not dates** — drafting the assembly note or the
wish, which is a human-confirm surface like every other AI output in the product.

**`S-124` · DOB arrives at the roster import or it never arrives.**
Add `date_of_birth` to the importer's `FIELDS` with the synonyms schools actually use — *"dob",
"d.o.b", "date of birth", "birth date", "birthday", "b'day"* — plus the messy-real-world formats
(`dd/mm/yyyy` dominates in Indian school registers; `dd-mm-yy`; Excel serial dates). Then **show
the coverage figure with its denominator** (ux §4) wherever the card is empty: *"Birthdays known
for 41 of 486 students — add DOB to the roster"*, linking to the import. That sentence is the
difference between a screen that looks broken and a screen that tells you how to fill it.

**`S-125` · Tier the catalogue, or the card becomes wallpaper.**
There is an international day for almost everything. A card that has something on it *every single
day* stops being read inside a week — the exact failure mode DASH3-OV was built to fix. Ship each
observance with a tier:

- **major** — the school will do something (Diwali, Independence Day, Holi, Guru Purnima) → on the
  card by default;
- **minor** — nice to know, often a themed assembly (International Mother's Day, World Book Day) →
  folded under *More*, promotable per school;
- **off** — never shown.

The school's own `calendar_events` and its own students' birthdays are **always** major. Default
on the card: today's birthdays + today's major observances + the school's own events. Nothing else.

**`S-126` · Horizon by kind, not one "next 7 days".**
The founder's 7 days is right for a birthday and wrong for Independence Day — flag hoisting,
rehearsals and a parent notice need two to three weeks. Give each catalogue entry a **lead time**
(`prep_days`), and let a big date surface early while a birthday surfaces the day before. The card
still *reads* as "Today / This week", with a third line — **"Coming up"** — for anything whose lead
time has started but whose date is further out. *"Independence Day — 15 Aug, in 12 days"* is the
line that makes the module worth opening.

**`S-127` · Staff birthdays are the cheapest goodwill in the product.**
The founder said students. But an admin who wishes a teacher by name on the morning of costs
nothing and is felt for a year — and staff turnover is the school's most expensive problem. Neither
`users` nor `memberships` has a DOB either, so this is one more nullable column, filled by the
person themselves in their profile rather than imported. **Fence check:** a teacher's DOB must
never reach a parent surface, and it must never sit next to anything payroll-shaped (`Q-57`).

**`S-128` · The vacation birthday.**
A child born in mid-May never gets wished, every year, for their whole time at the school —
because the school is shut. Real schools handle this by wishing them on the last working day
before the break. The calendar already knows which days are teaching days
(`calendar.is_teaching_day`), so the feed can roll a birthday that lands on a holiday or in a
vacation block forward/back to the nearest working day and label it honestly: *"Aarav Sharma —
birthday on Sunday 17th"*. Small, and it is the kind of thing a parent notices.

**`S-129` · The wish is human-confirmed, never automatic.**
An automatic birthday WhatsApp to every guardian is the obvious feature and the wrong one. It will
eventually fire at a family that has just lost someone, or for a child who left in March, or twice
because two guardians share a phone. Rules if it ships (`Q-58`):

- the admin or class teacher **sees the list and presses send** — the same confirm doctrine as
  every AI output and every Lucy write;
- `guardians.notify_opt_out` honoured (SPRD §7), as every guardian message already is;
- `status = 'left'` students never appear in the feed at all;
- it records that it fired, so nobody is wished twice by two different people — the
  `followup_actions` shape from DASH3 (ux §7), not a new mechanism.

**`S-130` · The parent's version of this card answers the most-asked parent question in schools.**
*"Is school open on Monday?"* — holidays, the exam block, the annual day. It is a projection of
rows the school already maintains, it is read-only, and it needs **no new capture whatsoever**. It
is probably the cheapest single win available to the parent portal. Two constraints: it goes
through the curated allowlist in `parent_portal.py` field-by-field like everything else, and a
parent sees **only their own child's** birthday — a list of classmates' birthdays is a roster leak
wearing a party hat. Scope note: this belongs to the **parent portal** module, and is recorded
here only so it isn't reinvented there (`Q-56`).

**`S-131` · Do not call this module "celebrations" in code.**
`CelebrationProvider` / `useCelebration` is the task-completion confetti layer
(`web/src/components/celebration/`). Two unrelated things called the same word in one frontend is
how a six-month-later bug gets written. The `calendar_events.type` value `celebration` already
exists and stays; the module is **events & dates**, and the new surface is a *calendar* / *what's
on*.

**`S-132` · This is the teacher's P3 payoff, and it should be treated as one.**
Almost every teacher-facing surface in the product asks a teacher for something — mark attendance,
log the topic, check homework. This one **gives** without asking: it costs the teacher zero taps
and hands her a moment with a child. It is the one card in My Day with nothing to capture, and it
should be visibly that — small, warm, and never a to-do row.

**`S-133` · Show the day, not the age.**
Teachers need *"birthday today"*, not *"turns 12 today"* — and certainly not a DOB on a class
list. Render day-and-month on shared surfaces; keep the full DOB on the student's own record where
it belongs, for the register and board registration. It costs nothing to be careful here and the
alternative is a child's age on a screen that gets shown to a room.

**`S-134` · Beware of shipping the school a second calendar.**
Plan → Year **is already a year calendar** — a paintable grid of every dated row the school owns.
If this module adds `/dashboard/calendar` as a month view, the school has two calendar screens
that disagree about what a calendar is for: one where you *paint* dates and one where you *read*
them. Two candidates, and the choice should be made deliberately:

- **(a)** the card links to **Plan → Year**, which gains a read/"what's on" mode. No new screen,
  one calendar, and the observance layer renders as a fourth kind of mark on the grid it already
  draws;
- **(b)** a genuinely different screen — an **agenda list**, not a grid: *what is coming, in
  order, with what it needs done*. Which is not a calendar at all, and so does not compete.

Claude's preference is **(a) for the grid + (b) for the card**, and *no* third month view. The
worst outcome is `/dashboard/calendar` rendering the same grid as `/plan` with a different brush
set — and that is the default outcome if nobody decides (`Q-60`).

### Rejected

- **A new `events` table.** REJECTED — `calendar_events` is exactly this table and already has
  types, ranges, notes and RLS. A second one forks the truth and would make the effective-days
  engine read two sources (`S-121`).
- **Auto-importing a public holiday feed into the school's calendar.** REJECTED — `S-122`. The
  holiday list a school actually observes is a school-by-school decision (schools in the same city
  differ), and getting it wrong silently rewrites every plan forecast.
- **A social feed / wall of wishes.** REJECTED — that is a social module, fenced by SPRD2 §11, and
  it needs moderation the moment it exists.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `What's on` card — `/dashboard` | admin | **NEW** | *"Anything today I should have prepared for?"* |
| **`Approve this date` sheet** | admin | **NEW** — `D-57` `D-58` | *"Are we closing for this, and what does it cost?"* |
| `What's on` strip — `/my-day` | teacher | **NEW** | *"Is it anyone's birthday in this room?"* |
| **Period card — "not held"** | teacher | **CHANGING** — `D-59` | *"This class didn't happen, and here's why."* |
| `What's coming` — route TBD (`Q-60`) | admin | **NEW** | *"What's coming, and what does it need?"* |
| **Catalogue** — `/platform` 3rd tab | super-admin | **NEW** — `S-149` | *"Are next year's dates right?"* |
| `Plan → Year` — `/plan` | admin | **CHANGING** | needs the open/closed choice — §4 defect 2, fixed by `D-58` |
| `Setup` / roster import | admin | **CHANGING** | must capture DOB at setup (`D-56`) |
| `Student record` — `/students/[id]` | admin, class teacher | **CHANGING** | DOB belongs on it |
| Teacher profile | teacher | **CHANGING** | self-entered DOB (`D-56`) |

## 7 · What we deliberately don't build

- **An event-planning tool.** Budgets, committees, task lists for the annual day. If preparing for
  an event needs work tracked, that work is a **task on a board** — the Tasks module already does
  this, and "Add as task" is the link between them.
- **RSVP, invitations, ticketing, a photo gallery of the event.** Social module, fenced.
- **A holiday-policy engine.** The school declares its own holidays; we never infer them.
- **Anything that writes to the calendar without a human pressing something** (`S-122`).
- **Age-based anything** — no "students turning 13 this term" cohort lists. That is a report
  nobody asked for and a privacy surface we don't need.

## 8 · Open questions

- **`Q-54`** — where do festival dates come from? → **reshaped by `D-60`** into `Q-63`: the
  *storage* is now decided, the *source* is not.
- **`Q-55`** 🔴 — is the catalogue regional/faith-scoped, and who picks for a given school?
  Sharpened by `D-60`'s *"state-wise school holidays"* — state is now an explicit axis.
- **`Q-56`** — do parents see the school calendar? (Cheapest portal win — `S-130`.)
- **`Q-57`** — staff birthdays → **ANSWERED, `D-56`**: in, nullable, self-entered, never imported.
- **`Q-58`** — is the birthday wish an outbound guardian message at all, or in-school only?
- **`Q-59`** — is DOB in the setup pack? → **ANSWERED, `D-56`**: captured at setup, with the roster.
- **`Q-60`** — one calendar or two? Does the card link to Plan → Year, or to a new screen
  (`S-134`)?
- **`Q-63`** 🔴 — **the research task.** What are the real sources for state-wise school holidays,
  all-religion dates and international days — and what is the annual curation cycle?
- **`Q-64`** — do teachers see suggestions, or only what the admin has approved?
- **`Q-65`** — locking a **past or current** day vs a future one: what happens to attendance,
  homework and logs already captured against it?

## 9 · Data implications

Deliberately almost nothing — if this section grows, re-read `S-121`.

- **`students.date_of_birth`** — `DATE NULL`. The only column the module truly needs. Nullable
  forever: a school will always have some students without one, and that is *not captured*, not an
  error (ux §5, §10).
- **`memberships.date_of_birth`** — `DATE NULL`, self-entered from the profile screen, never
  imported (`D-56`).
- **`calendar_events`** — **still no change to the table.** `D-58`'s three lock levels are
  `affects_teaching` + `blocks_periods`, both of which exist and are already prorated by
  `effective_periods` (`S-142`). The UI must expose them (§4 defect 2); `type='celebration'`
  finally gets a reader.
- **The catalogue** — now a **platform-level table**, not a file (`D-60`): no `org_id`, no RLS,
  `require_super_admin` on write, the `demo_requests` shape (`S-149`). Each entry: `date` ·
  `name` · `tier` · `prep_days` · `region`/`state` · `tradition` · **`source`** (`S-150`) ·
  `note`.
- **The suggestion's decision row** — append-only (`S-148`): one row per (org, catalogue entry,
  year) recording **approved** (with which lock level) or **dismissed**, and by whom. This is the
  one genuinely new org-scoped table, and it is the `plan_approvals` / `demo_request_notes` shape
  the codebase already uses three times. An approval also creates the `calendar_events` row —
  that row is the *effect*, this one is the *record of the decision*.
- **The teacher's block** — `not_held_reason` exists (`services/classroom.py:470`); it gains an
  optional **reference to the event** rather than free text (`S-147`), so *"what did Diwali
  cost?"* is answerable. Timesheet side is an existing `core/work_types.py` bucket.
- **`NOTIF_TYPES`** — widen the CHECK only if a birthday notification actually ships (`Q-58`).

## 10 · Rough build order

Ordered so nothing renders before it can be truthful. Reordered after the second pass — the
approval flow moved to the front, because it now *is* the module.

1. **`students.date_of_birth` at setup** (`D-56`) + importer synonyms + date-format handling
   (`dd/mm/yyyy`, Excel serials) + the coverage sentence with its denominator. Nothing below this
   line renders anything until this exists.
2. **The suggestion → approval flow** (`D-57`, `D-58`) — the sheet with the three lock levels,
   writing `affects_teaching` / `blocks_periods`, plus the append-only decision row (`S-148`).
   **This closes live defect 2 as a side effect** (`S-142`), so it also stands alone as a bug fix.
3. **The cost preview on that sheet** (`S-143`) — a second caller of `forecast_org`. Ship it
   *with* step 2, not after: step 2 without it moves RAG colours across the school unexplained.
4. **The teacher side** (`D-59`) — `not_held` referencing the event (`S-147`), and locked periods
   disappearing from the capture surface, the reminder job and every denominator (`S-145`).
5. **The read service** — one function, three sources, one dated feed with a horizon. Everything
   else is a rendering of it (ux §9).
6. **The two cards** — admin overview section, teacher My Day strip.
7. **The catalogue** (`D-60`, `Q-63`) — the platform table, the importer(s), tiering (`S-125`),
   and the super-admin curation tab. **Blocked on the research**, which is why it is this late;
   steps 1–6 work with the school's own dates and birthdays alone.
8. **The month/agenda view**, then **wishes** last, because it is the only piece that sends
   anything to a human being.
