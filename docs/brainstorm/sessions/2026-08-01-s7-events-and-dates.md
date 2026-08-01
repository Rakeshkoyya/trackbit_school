# Session 7 — 2026-08-01

**Topic:** events & dates — birthdays, the school's own calendar, and the festivals and
observances a school prepares for. A card on the admin and teacher dashboards; *"so the school can
get prepared for it."*
**Outcome (both passes):** 7 decisions (`D-51`–`D-52`, `D-56`–`D-60`), 24 proposals
(`S-121`–`S-134`, `S-142`–`S-151`), 10 open questions (`Q-54`–`Q-60`, `Q-63`–`Q-65`) of which 2
closed in-session, one module file, **three verified defects** — one of which is live, unrelated
to this module, and corrupting plan forecasts today.

> **Read the second pass at the bottom before acting on the first.** The founder's follow-up
> reframed the module: the calendar is a **stream of suggestions**, not a plan fixed in April, and
> **approval is the commit** (`D-57`). That supersedes `S-123` and turns `S-122`'s discipline into
> a structure. The first pass is kept in full because its reasoning is why the second pass is
> shaped the way it is.

---

## The finding: the school's calendar has had a write side for a year and no read side

The founder described this as *"a very simple module"*, and structurally he is right — it needs
**one new column**. But the reason it feels simple is that three of its four pieces are already in
the building:

| Piece | Status |
|---|---|
| Dated school events, typed, org-scoped, RLS'd | ✅ `calendar_events` — `models/academics.py:153-180` |
| A UI to record a festival | ✅ Plan → Year, and **"Celebration" is already one of the four brushes** (`plan/page.tsx:43-48`) |
| Anything that reads it back to a human | 🔴 **nothing** — its only consumer is `services/calendar.py`, whose job is to *subtract* it from the teaching total |
| A date of birth | 🔴 **does not exist** — not on `students`, `users` or `memberships` |

So an admin paints *"Diwali"* on the year calendar in April, the row is correct and org-scoped and
survives forever, and **the product never mentions Diwali again**. The founder is not asking for a
new capability. He is asking for the **read side of a table that has only ever been written to**.

## 🔴 Three verified defects

**1 · The calendar is write-only.** Above. The most-asked question about any calendar — *what is on
it this week* — has no surface anywhere in the product.

**2 · Recording a festival silently shrinks the teaching year. This is live today.**
`CalendarEventCreate.affects_teaching` defaults to `True` (`schemas/calendar.py:17`) and the paint
UI **never sends the field** (`plan/page.tsx:82-90`). Painting *"Celebration — Guru Purnima"* on a
day the school is **open** removes a teaching day from every class-subject forecast in the school.
There is no control on that screen to say *"this is on the 9th and we are open."*

This is not an events-module bug — it is shipped, and it is wrong now. It becomes the events
module's problem because **the entire point of this module is to give schools a reason to record
more dates.** Fix it first.

**3 · The module is dead until DOB exists, and DOB has no way in.** Schools hold it — board
registration requires it, it is on every admission form — but it arrives in the xlsx handed over at
setup and the importer does not look for it (`roster_import.py:23-48`). `dd/mm/yyyy` dominates in
Indian registers and a `mm/dd` misread silently moves 40% of a school's birthdays.

## Three things wearing one word

The ask merged three objects that behave differently, and keeping them merged is how this module
grows tables it doesn't need (`S-121`):

| | What it is | Where it lives | Does it eat a teaching day? |
|---|---|---|---|
| **Birthday** | **derived** from a person's DOB | one nullable column | never |
| **The school's dates** | org data the admin owns | `calendar_events` — exists | **only if the admin says so** |
| **Festival / observance** | **reference data**, identical for every school | a versioned file | **never** |

The whole module is one column, one shipped file, and one read service that unions three sources
into a dated feed. One computation, many renderings (ux §9).

## The trap, named before anyone builds it

> **A festival catalogue must never write `calendar_events`.**

*Holi is on the 14th* and *the school is closed on the 14th* are different facts, and only the
second one is the admin's to declare. If a pack ever auto-creates rows, it rewrites the
effective-days denominator behind **every plan forecast in the product** — defect 2, but at scale
and unattended.

The bridge is an explicit **"Add to school calendar"** button on the observance row: opens the
normal event sheet, date prefilled, forces the open/closed choice. One tap, auditable, never
automatic (`S-122`).

## *"Or from the internet"* — the one hard problem

Diwali, Holi, Guru Purnima, Eid, Onam, Pongal are **lunisolar**. They move every year and regional
reckonings differ. Three sourcing options, and the choice is `Q-54`:

- **ask a model** — ❌ answers confidently, can be wrong, and **there is nothing in the product to
  check it against**. Every other AI call here either transcribes or proposes a mapping a
  deterministic validator checks against real data — a column list, a roster. This is exactly the
  `Q-51` shape from last session: an unverifiable claim, rendered as fact. The failure mode is a
  school decorating on the wrong day *because our screen told it to*;
- **a live API** — ❌ a key to rotate and a vendor to outlive, for data that changes once a year and
  is knowable a year ahead;
- **a checked file per academic year, in the repo** — ✅ `S-123`. Human-reviewed once, diffable in a
  PR, offline, identical everywhere, free.

**AI's legitimate job in this module is phrasing, not dates** — drafting the assembly note or the
wish, which is a human-confirm surface like every other AI output in the product.

## What Claude pushed that wasn't asked for

- **`S-125` — tier the catalogue or the card becomes wallpaper.** There is an international day for
  almost everything. A card with something on it *every single day* stops being read inside a week
  — the exact failure DASH3-OV was built to fix. Default: today's birthdays, today's **major**
  observances, the school's own events. Nothing else.
- **`S-126` — horizon by kind.** The founder's 7 days is right for a birthday and wrong for
  Independence Day, which needs two to three weeks of rehearsal, costumes and a parent notice.
  Give each entry a lead time; add a third line, **"Coming up"**. *"Independence Day — in 12 days"*
  is the line that makes the module worth opening at all.
- **`S-128` — the vacation birthday.** A child born in mid-May is never wished, every year, for
  their whole time at the school. `calendar.is_teaching_day` already knows; roll it to the nearest
  working day and label it honestly.
- **`S-127` — staff birthdays.** The founder said students. An admin wishing a teacher by name
  costs nothing and is felt for a year, and staff turnover is the school's most expensive problem.
  Self-entered, never imported, and fenced from anything payroll-shaped (`D-25`'s principle).
- **`S-130` — the parent's version answers the most-asked parent question in schools.** *"Is school
  open on Monday?"* — from rows that already exist, read-only, **zero new capture**. Probably the
  cheapest win available to the parent portal. Two constraints: the curated allowlist, and a parent
  sees **only their own child's** birthday — a classmate list is a roster leak wearing a party hat.
- **`S-132` — this is the teacher's P3 payoff and should look like one.** Every other block on My
  Day asks her for something. This one hands her a five-second moment with a child and asks for
  nothing. So: never a to-do row, never a tick, never amber for being unread, and **absent
  entirely** when there is nothing on.
- **`S-133` — show the day, not the age.** This line gets read out to a room. Day and month on
  shared surfaces; the full DOB stays on the student's record where the register needs it.
- **`S-134` — beware shipping a second calendar.** Plan → Year *is* a year calendar. A new
  `/dashboard/calendar` month grid gives the school two screens that disagree about what a calendar
  is for. Preference: Plan → Year gains a read mode, and the new surface is an **agenda** — dates
  in order with what each needs — which doesn't compete because it isn't a calendar.
- **`S-131` — don't call it "celebrations" in code.** `CelebrationProvider` is the task-completion
  confetti layer. Two unrelated things called the same word in one frontend is how a six-month-later
  bug gets written.

## What this module deliberately isn't

The natural next thought after *"events"* is **event planning** — budgets, committees, checklists
for the annual day. That is a second work tracker, and the product already has one. Preparation
becomes **a task on a board**, and *"Add as task"* is the entire integration. Also out: RSVP,
invitations, a photo gallery (social module, fenced by SPRD2 §11), a holiday-policy engine, and
any age-based cohort list.

## Blockers for the next session

Ordered by what they unblock.

1. **`Q-59` — does DOB reach us, and in what format?** Blocks the birthday half, which is most of
   the module. Nothing renders until this is answered and the importer changed.
2. **`Q-54` — where do festival dates come from?** 🔴 Blocks the entire observance half. The
   birthday and school-calendar halves can ship without it.
3. **`Q-55` — regional / faith scoping, and who picks?** 🔴 Blocks the catalogue file's shape.
   Note the sharp edge: ask a school **which festivals it observes**, never what it is.
4. **`Q-60` — one calendar or two?** Blocks the route, and whether Plan → Year is reopened.
5. **`Q-58` — does a wish leave the building?** Decides whether this module sends anything at all,
   and whether `NOTIF_TYPES` needs widening.
6. **`Q-57` — staff birthdays.** One nullable column, low stakes, easy to defer.
7. **`Q-56` — parents and the calendar.** Not a blocker here; it is a parent-portal decision
   recorded so it isn't reinvented there.

**Total data cost of everything decided or proposed: one nullable column, one shipped file, and a
control the paint UI should already have had.** `Q-57` adds a second nullable column if it lands.

**Independent of all of it:** defect 2 is live, is shrinking teaching years today, and should be
fixed whether or not this module is ever built.

**Next module by the backlog:** **Students** — still undesigned after seven sessions, and this one
adds DOB to `/students/[id]`.

---

# Second pass — same day

**Founder input:** DOB at setup for students / optional and self-entered for staff / none for
guardians · **the calendar is a suggestion stream, not a fixed plan** · approval has three lock
levels · **no plan adjustment this version** — the teacher marks the class instead · the catalogue
is fetched from the internet and **stored in our database**, sourcing to be researched.

**Outcome:** 5 decisions (`D-56`–`D-60`), 10 proposals (`S-142`–`S-151`), 3 new questions
(`Q-63`–`Q-65`), 2 closed (`Q-57`, `Q-59`), 1 reshaped (`Q-54`). One `S` superseded (`S-123`), one
strengthened (`S-122`).

## The reframe: the calendar is a stream, not a plan

> *"In the setup stage a brief version of the calendar is decided. No matter how well the year is
> planned it keeps on changing."*

This is the most useful sentence of the session, and it changes the module's centre of gravity.
The product had been treating the year calendar as **a thing fixed in April**. It isn't, and every
school knows it isn't. So dates now arrive **continuously, as suggestions**, and **approval is the
commit** (`D-57`).

The side effect is better than the feature: the first pass worried at length about a festival
catalogue silently writing `calendar_events` and corrupting the effective-days denominator
(`S-122`), and proposed a button somebody must remember to press. `D-57` makes it structural —
**approval is the only route that exists.** The fence stopped being a discipline and became a
shape.

## ✅ The three lock levels already exist *(verified)*

`D-58` — whole day · specific periods · runs as usual — describes, from the product side, exactly
the schema **V2-P7 already shipped**:

| `D-58` level | Fields | `effective_periods` (`services/calendar.py:84-131`) |
|---|---|---|
| Lock whole day | `affects_teaching=True`, `blocks_periods=NULL` | the day leaves the week |
| Lock specific periods | `affects_teaching=True`, `blocks_periods=[1,2]` | day yields `1 − lost/periods_per_day` |
| Runs as usual | `affects_teaching=False` | full teaching day |

The docstring even names the case: *"an event eating 3 of 8 periods leaves 5/8 of that day."*

**So the whole locking feature is a UI over tested fields — and it is also the fix for the live
defect.** Painting a Celebration deletes a teaching day today *because the paint UI never sends
`affects_teaching`*. `D-58` makes that choice the central act of the flow. The bug cannot survive
the feature (`S-142`).

Same story on the teacher side: `not_held_reason` already exists (`classroom.py:470`), and the
timesheet's work-type list deliberately has no CHECK constraint. `D-59` needs a link to the event,
not a table.

## 🔴 The one thing `D-59` can't actually defer

`D-59` defers "adjusting the plan". **Half of that adjustment is not deferrable and already
happens.** `effective_periods` is computed live, so the moment three days are locked for Diwali
every class-subject's remaining capacity shrinks and **RAG colours move across the school** — with
nothing on the syllabus board explaining why. A principal who locks three days and then watches
six subjects turn amber concludes the system broke.

So `S-143`: **the approval sheet shows the cost before the admin commits.**

> *"Removes 8 periods. 6-B Maths and 9-A Science move green → amber. 14 class-subjects
> unaffected."*

`PlannerService.forecast_org` already batches exactly this for the whole school in one pass — it
was built for DASH3's PR-6. A second caller, not a new engine. **Ship it with the sheet, not
after.**

And the half that *is* deferred (`S-144`) should be recorded as **permanent, not "next version"**:
rewriting approved plan entries is a **P2 violation** — *the approved plan is locked; re-forecast
is computed, never stored as mutated plan rows*. Writing "v2 adjusts the plan" into a roadmap
invites someone to implement it literally in eighteen months. What a later version can legitimately
add is a **proposal the admin approves**, through the existing `extend_plan` path.

## Two scopes that must not be merged

`D-59` gives the teacher a block. The case it actually serves is **not** the school-wide one
(`S-146`):

- **admin locks** → school-wide, in advance, every class;
- **teacher blocks** → *this* class, *this* period — 8-A went to the rehearsal while 8-B kept
  teaching.

Merge them and the day is removed twice. The rule: **if the admin locked it, the teacher is never
asked.** Which leads to the sharpest small point of the pass — `S-145`: a locked period must
**vanish from the teacher's capture surface**, from every denominator, and from the 16:00 unmarked
reminder. Showing a teacher eight red *"not logged"* rows on a holiday the school itself declared
is the fastest way to lose her trust in the surface. *(And per `Q-65`, "vanish" means vanish from
what is still **expected** — never erase what was already recorded. A school that closed at 11am
genuinely taught period 1.)*

## Storage decided, truth not

`D-60` moves the catalogue into our database and **supersedes `S-123`'s file-in-the-repo**. The
founder is right, and the reason is scale: 28+ states × per-year × multiple traditions is too much
to hand-edit, and it must be fixable without a deploy.

`S-149` reconciles it with what `S-123` was actually protecting: make it **platform data, not org
data** — no `org_id`, no RLS, `require_super_admin` on write, the `demo_requests` / EN-1 shape from
V3-P0. One curation serves every school; one correction fixes every school; `/platform` gains a
third tab beside Schools · Enquiries. Human review kept, deploy dropped.

> ⚠️ **A database does not make a date true.** Whatever fills that table still has to be right, and
> a wrong Diwali date is a school decorating on the wrong day *because our screen said so*. Hence
> `S-150` — every suggestion shows **where it came from**, because the admin approving it is the
> last human in the chain.

## The research, scoped (`Q-63`)

The four kinds of date asked for do not come from one place:

| What | Likely source | Shape |
|---|---|---|
| State-wise school holidays | each state's gazetted list | PDF, per state, published late in the preceding year |
| All-religion dates | almanacs / panchang | regionally **disagreeing** |
| International days | the UN observances list | the easy one |
| National holidays | gazette | several free APIs cover it |

`S-151`, stated so the research can prove it wrong: **there is very likely no single
machine-readable feed** covering Indian *state school* holidays plus all religions. Expect **a
small importer per source plus one annual human review**. Designing for one clean API and
discovering the fragmentation in month three is the expensive order to find out.

The research must also answer which religious dates are safe as **a single date** and which need
an honest range (*"observed 12–13 Oct depending on region"*) — a confidently wrong single date is
worse than a range.

## Where the build actually starts now

The approval flow moved to the front, because it now *is* the module — and steps 1–6 do not need
the research at all:

1. `students.date_of_birth` at setup + importer + coverage sentence
2. **The suggestion → approval sheet** (three levels) — *closes live defect 2 on its own*
3. **The cost preview on that sheet**, shipped with it
4. The teacher side: `not_held` → event, locked periods out of every denominator
5. The read service (one function, three sources)
6. The two cards
7. *(blocked on `Q-63`)* the catalogue, importers, tiering, super-admin curation tab
8. The agenda view, then wishes

## Blockers now

1. **`Q-63`** 🔴 — the sourcing research. Blocks step 7 only.
2. **`Q-65`** — locking a past/current day. Blocks the approval sheet's date rules and the precise
   meaning of `S-145`. *Claude recommends: allowed, and existing capture is kept and shown, never
   erased.*
3. **`Q-55`** 🔴 — still open, and now sharper: `D-60` names **state** explicitly, so the
   catalogue is keyed by state whether or not faith-scoping lands.
4. **`Q-64`** — do teachers see suggestions or only approved dates? *Claude recommends approved
   only.*
5. **`Q-60`** `Q-58` `Q-56` — unchanged from the first pass.
