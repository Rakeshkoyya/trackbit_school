# Module — Fee collection

Not a fee system — the school has one. This is **the collection board**: how much of the quarter
is in, who hasn't paid, and who is going to ring them.

**Sessions:** 8 (2026-08-01)
**Related:** [`tasks.md`](tasks.md) *(the follow-up is a task on the Follow-ups board)* ·
[`parent-access.md`](parent-access.md) *(the reminder's delivery)* ·
[`class-teacher.md`](class-teacher.md) *(who actually makes the call)*

---

## 1 · Who this is for, and when

| Role | The moment | Device / budget | The question they arrive with |
|---|---|---|---|
| **Admin / correspondent** | start of a quarter, and the week the instalment falls due | desktop, minutes | *"How much of Q2 is in, and who do I chase?"* |
| **Admin at the counter** | a parent standing in front of them | desktop, seconds | *"What does this child owe?"* — **already answered** by `/fees/[id]` |
| **Teacher given a follow-up** | in her tasks, between classes | phone | *"Who am I ringing, and what do I say?"* — 🔴 **and how much may she know?** (`Q-66`) |
| **Parent** | evening, phone, weak connection | seconds | *"How much do I owe, and by when?"* |

## 2 · What they must be able to decide

- Whether this quarter's collection is **on track or behind**, against something — last quarter,
  or the same week last year. A bare rupee figure decides nothing.
- **Which class** to push this week. Chasing 400 families is not a plan; chasing 8-B is.
- **Which family** to ring today, and **who** should ring them.
- Whether a family has **already been reminded** — by someone else, this morning.
- *(Parent)* whether they owe anything, and by when.

## 3 · Where it stands today *(verified)*

The collection *system* is genuinely built. The **read side for a principal** is not.

| Piece | Status |
|---|---|
| Structures, instalments, per-student enrolment, discounts, arrears | ✅ `models/fees.py` — 5 tables, `fee_math.py` ported money math |
| Payment, undo, mark-paid, ledger | ✅ append-only `fee_transactions` (law 3); undo is a compensating row |
| Per-student screen — pay / undo / discount / ledger | ✅ `/fees/[id]`. **This is the good screen and it is not in scope to change.** |
| Instalments carrying a **label** and a **due date** | ✅ `installments.installment_number` · `label` · `due_date` — so *"QTR1"* is expressible **today** |
| A school-wide summary | 🟡 `FeeSummary` = **4 year-wide scalars** (`total_fee`, `collected_fee`, `pending_installments`, `overdue_amount`). No quarter, no class, no trend. |
| **"Which students haven't paid"** | 🔴 **built and unreachable** — `GET /fees/overdue-students` returns name + class + amount + earliest due date, and **nothing in the web app calls it** (`school-api.ts` has no such function) |
| A reminder to a parent | 🔴 does not exist. `NOTIF_TYPES` has no fee type (CHECK constraint — `models/notification.py:18-25`) |
| Assigning a follow-up | 🟡 the **mechanism** exists — `followup_actions` is append-only with free `kind`/`subject_type`/`subject_id` (`models/insights.py:106-128`), and the Follow-ups board is a shipped pattern. Nothing wires fees to it. |
| Anything on the parent portal | 🔴 **nothing.** Confirmed by grep across `parent_portal.py`, `schemas/parent.py`, `parent-api.ts`. |
| Teachers never see fees | ✅ holds — `/fees` endpoints are admin-only, the dashboard card is `if m.is_admin`, and the web fees block is client-side |

## 4 · What's wrong with it

### 🔴 Defect 1 — the named list the founder is asking for is already computed, and nothing asks for it

`FeeService.overdue_students` returns exactly *"which student has not given yet"* — name, class,
amount, earliest due date, sorted by oldest — and `school-api.ts` has no `overdueStudents`. The
endpoint is live. The screen never calls it.

> **This is the third time this exact pattern has appeared in eight sessions** — `S-86` (per-student
> homework history, built, wired into the client, called by nothing), `S-74` (the cover picker never
> reads the timesheet), and now this. **The server keeps growing answers the client never asks
> for.** Worth a standing check at packet close: *does a screen call this?*

### 🔴 Defect 2 — arrears are invisible in every roll-up, so "pending" understates the truth

`student_fees.opening_dues` carries last year's unpaid balance, and the model says plainly:
*"adds to the outstanding balance but is kept separate from net_fee; **status is still driven by
instalments only**."*

Follow that through `summary()`:

- `total_fee` = Σ `net_fee` → **excludes arrears**
- `collected_fee` = Σ paid instalments → excludes arrears
- `overdue_amount` = unpaid instalments past due → **excludes arrears**
- `student_fee_status` = derived from instalments only → **a student carrying ₹20,000 from last
  year with this year's instalments paid reads `paid`**

So the one number a correspondent most wants — *what is actually owed to this school* — is the one
number the summary cannot produce, and the defaulter list silently omits the worst defaulters.
For a module whose entire purpose is *what is owed*, this is the defect that matters most
(`Q-68`).

### Defect 3 — `/fees` leads with four bare numbers, with three different denominators

*(verified)* `Net fee (year)` · `Collected` · `Overdue` · `Pending instalments`
(`fees/page.tsx:113-116`). Two are money, one is money-past-a-date, and one is **a count of
instalments** — not students, not families, not money. Four tiles, no sentence, nothing named,
nothing comparable to anything.

This is precisely the shape DASH3-OV replaced on the dashboard overview eight days ago, and it
survives here because nobody has opened this screen since P0-E.

### Defect 4 — `overdue_students` does a query per student

`_class_label` calls `db.get(SchoolClass, …)` inside the loop (`services/fees.py:72-78, 447-470`).
Two hundred overdue students is two hundred round trips on a remote database, for one list. The
same per-row-lookup pattern DASH3's `forecast_org` was built to kill.

### Defect 5 — "quarter" is not something the reads can group by yet

The founder collects quarterly and wants *"QTR1 collection and pending"*. The data supports it —
but **nothing groups by it**, and the obvious grouping keys are both wrong (see `S-153`).

## 5 · Ideas and directions

### Decided — `D-nn`

- **`D-62`** — this module is **read + remind only**. The collection system stays as it is; no new
  payment capture, no gateway, no receipt redesign.
- **`D-63`** — **only the admin sees fee data.** Unchanged, and it is a standing fence.
- **`D-64`** — the admin gets a **collection section**: due collection and pending fee, analysed
  **quarter-wise** (QTR1 collected / pending), down to **which class** and **which student** has
  not paid.
- **`D-65`** — two actions on a defaulter: **remind the parent**, and **assign a teacher to follow
  up** with them.
- **`D-66`** — the parent gets a **notification** and a **reminder block on their portal home**.

### Proposed — `S-nn`

**`S-152` · The collection board is `/fees` itself. Do not build `/dashboard/fees`.**
`/fees` already exists as a full area (landing + list + enrol, `/fees/structures`, `/fees/[id]`)
and its landing page is the weakest screen in the product. The founder's *"section in the
dashboard"* should **replace that landing page**, not become a ninth dashboard tab beside it.

This is the `S-134` trap again in a different module: two screens that disagree about what they
are for. The `/dashboard` overview keeps its small fees block — a sentence, two figures, a link —
and everything else lives on `/fees`. **No new route, and the counter screen `/fees/[id]` is
untouched** (`D-62`).

**`S-153` · Define a quarter by its **due-date window**, not by instalment number or label.**
Three candidate keys, and two of them break:

| Key | Breaks when |
|---|---|
| `installment_number` | structures differ — juniors pay in 2 instalments, seniors in 4, so "instalment 1" is a different quarter for different classes and the school-wide figure is nonsense |
| `label` | free text. *"Q1"*, *"Quarter 1"*, *"1st term"*, *"April"* — one school will produce all four and the grouping fragments |
| **`due_date` falling inside the quarter's window** | ✅ works across differing structures, aligns every class to the same calendar, and matches what the admin actually means: *"money due Jul–Sep"* |

So a quarter is a **computed window over the academic year**, and an instalment belongs to the
quarter its due date falls in. Degrades honestly: an instalment with **no due date** is
`unscheduled` — a **word, not a bucket** (ux §10), never silently dropped into Q1.

**`S-154` · 🔴 The fence and the follow-up collide, and the collision needs deciding out loud.**
`D-63` says only admins see fee data. `D-65` assigns a **teacher** to chase a parent. If that task
reads *"Call Kabir's father — ₹12,000 overdue"*, the teacher now sees fee data, and the
non-negotiable in `CLAUDE.md` and in `ux-principles.md`'s hard-fence table is broken by the
feature that was supposed to sit on top of it.

Three ways out (`Q-66`):

- **(a) The task names the family and the subject, never the amount.** *"Fee follow-up — Kabir
  Shah (8-B). Please speak to the family and record what they say."* The parent already knows the
  number; the teacher does not need it to make the call.
- **(b)** The teacher sees amounts for her own students. Fence breached, deliberately.
- **(c)** Only admins can be assigned fee follow-ups. Fence intact, but it wastes the one person
  with an actual relationship with the family — the class teacher.

*Claude recommends **(a)**, strongly.* The reason the fence exists is not confidentiality for its
own sake — it is that **a teacher who knows which families are behind on fees treats those
children differently**, and every child in that list has done nothing wrong. (a) keeps the
relationship and drops the number. It also makes the outcome better: what the school needs back is
*"spoke to the father — paying after the 15th"*, which is `ux §8`, and needs no rupees to record.

**`S-155` · Lead with the shape of the collection, not the total.**
*"₹42L of ₹68L collected"* is a fact nobody can act on. *"Q2 is 62% collected — that's ₹6L behind
where Q1 stood in its fifth week"* is a decision. Give the board a **collection curve** (cumulative
collected against the quarter's days, with the previous quarter as a reference line — the same
device `class-analytics` already uses for the first-test line), and the tiles become evidence
underneath it. Shape beats number for patterns (ux §15).

**`S-156` · The reminder must remember it fired, and it needs money-specific manners.**
`followup_actions` already gives idempotence for free — append-only, `subject_type='student'`,
`kind='fee_reminder'`, read once per list so every row can render *"reminded this morning by
Priya"* (ux §7, and it is exactly what DASH3 built it for). **No new table.**

But a fee reminder is not an absence alert, and it must not behave like one:

- **at most one per instalment per week**, no matter how many staff press the button;
- **quiet hours** — never before 8am or after 8pm;
- **it stops the moment the payment lands**, including a payment taken at the counter five minutes
  ago;
- **never to a guardian with `notify_opt_out`**, like every other guardian message (SPRD §7).

A parent reminded three times in a morning about money will not read the fourth message about
their child's attendance.

**`S-157` · A defaulter row is about a family's payment. It must never colour a child.**
Two rules, and both are cheap:

- the fee list names the **family/guardian** alongside the student — *"Kabir Shah (8-B) · father
  Ramesh, +91…"* — because the person who owes is the person you ring;
- **no fee status ever appears on an academic surface.** Not on `/students/[id]`, not in growth,
  not on the timeline, not in the daily report, not in a teacher's Lucy tool. The student's report
  card gaining a "fees pending" chip is the single most damaging thing this module could do, and
  it is one join away at all times.

**`S-158` · A full concession is not a defaulter.**
A student on 100% discount has ₹0 due and must never appear on a chase list, a class red count, or
a reminder. `net_fee` already nets the discount so the arithmetic is right — the risk is the
*screen*, where a row with `overdue = 0` can still render inside a "not paid" list if the list is
built from enrolment rather than from what is owed. Filter on amount owed, never on status alone.

**`S-159` · Give the class list a denominator, and rank by families not rupees.**
*"8-B: ₹1.4L pending"* is one big defaulter or fourteen small ones, and they need completely
different actions. Every class row carries **both**: *"8-B — 14 of 38 families pending, ₹1.4L"*
(ux §4). And offer the list sorted by **count of families**, because a morning of phone calls is
denominated in calls, not rupees.

**`S-160` · The parent's screen answers two questions and is not a ledger.**
*"How much, and by when."* One line, the due date, what has already been paid this year, and
nothing else. The transaction history is the office's screen — a parent who wants it asks at the
counter, and `PC-1`'s curated allowlist means every field is added deliberately anyway. Keep the
tone neutral and never dunning: this is a reminder, not a demand, and it is read by a family that
may be having a hard year.

**`S-161` · Say what the follow-up produced, not that it was pressed.**
*"Reminded"* is an event; *"spoke to the mother — paying after the 15th"* is what makes the row go
away (ux §8). The Follow-ups board already records completion with an outcome (`D-46`), so this is
reuse, not invention. Without it the same family is rung every week by a different person and the
school looks disorganised to exactly the people it is asking for money.

**`S-162` · Fix the N+1 while the screen is open.**
`_class_label` per overdue student is one query each (defect 4). Batch the class lookup the way
`forecast_org` batches the syllabus pass. It is a small fix and this is the only session that will
ever be looking at this file.

**`S-163` · The quarter board should show `collected · pending · overdue` as three states, not
two.**
*Pending* (due later) and *overdue* (due, not paid) are different facts with different actions —
one is a forecast, the other is a phone call. `summary()` already separates them and the current
tiles already blur them by putting a **count** next to two **amounts**. Keep them apart everywhere,
and never add them into a single "outstanding" figure.

### Rejected

- **A ninth `/dashboard` tab for fees.** REJECTED — `S-152`. `/fees` exists and its landing page
  is the natural home; a second fee screen would immediately disagree with the first.
- **Online payment / a gateway on the parent portal.** REJECTED for this version — `D-62` is read
  + remind, and `PC-1` is read-only. A parent *write* that moves money is the largest possible
  reversal of that fence and is nowhere near this module.
- **A per-child "fee status" chip on academic screens.** REJECTED — `S-157`.
- **Automatic escalation** (auto-reminders on a schedule with no human press). REJECTED for now —
  money messages that fire themselves will eventually reach a family in the week of a bereavement.
  Same reasoning as the birthday wish (`S-129`).

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `Fees` — `/fees` | admin | **CHANGING** → becomes the collection board | *"How much of Q2 is in, and who do I chase?"* |
| `Overview` fees block — `/dashboard` | admin | **CHANGING** | *"Is collection a problem this week?"* |
| `Student fee` — `/fees/[id]` | admin | **EXISTS, untouched** | *"What does this child owe?"* |
| `Structures` — `/fees/structures` | admin | EXISTS | — |
| Follow-up task — `/tasks` | teacher | **NEW** — `Q-66` | *"Who am I ringing, and what do I say?"* |
| `Fees` reminder — `/parent` | parent | **NEW** | *"How much do I owe, and by when?"* |

## 7 · What we deliberately don't build

- **A second fee system.** `D-62`. The money math, the ledger and the counter screen are done.
- **Online payment, a gateway, or any parent write.** Not in this version.
- **Fee data anywhere a teacher can see it** — including Lucy's tool registry, the daily report,
  and any widget (`D-63`, `S-154`).
- **Fee status on an academic surface** (`S-157`).
- **Automatic dunning.** Every reminder is a human press.
- **Scholarship / concession workflow.** `discount` exists as a number; who approves it and on
  what evidence is a different module and probably a different fence.

## 8 · Open questions

- **`Q-66`** 🔴 — does a teacher assigned a fee follow-up see the amount? *(The fence. `S-154`.)*
- **`Q-67`** — how is a quarter defined: due-date window (`S-153`), instalment number, or declared
  by the school in settings?
- **`Q-68`** 🔴 — do arrears (`opening_dues`) count as pending? Today they are invisible in every
  roll-up and in `status`.
- **`Q-69`** — does the parent get a full fee view, or only a reminder line?
- **`Q-70`** — who receives the reminder: every guardian on the record, or the primary only?

## 9 · Data implications

Almost nothing new — which is the point of `D-62`.

- **No new fee tables.** Quarters are a **computed window** (`S-153`); the class and quarter
  roll-ups are grouped queries over `installments` joined to `students`.
- **`followup_actions`** — reused as-is for *"reminded"* / *"assigned"*, with
  `subject_type='student'` and a fee `kind`. Append-only, already the idempotence read (`S-156`).
- **`NOTIF_TYPES`** — needs **one new value** and therefore a migration widening
  `ck_notifications_notif_type_valid`, the `substitute` precedent from DASH3.
- **`opening_dues`** — no schema change; what changes is whether the **reads** include it
  (`Q-68`). If yes, `summary`, `overdue_students` and `student_fee_status` all move together, or
  the screens will disagree with each other (ux §9).
- **Parent projection** — new allowlisted fields on the `PC-1` curated projection, field by field,
  never a spread.

## 10 · Rough build order

1. **Decide `Q-66` and `Q-68`.** Both change what the screens are allowed to say; neither is a
   build detail.
2. **The read service** — one function producing the quarter × class × student roll-up, batched
   (`S-162`), with `collected / pending / overdue` kept apart (`S-163`) and arrears handled per
   `Q-68`. Every screen below is a rendering of this one computation (ux §9).
3. **`/fees` becomes the collection board** (`S-152`) — curve, quarter strip, class table, named
   defaulter list. **This alone closes defect 1**, because the list finally gets called.
4. **The two actions** — remind (`S-156`) and assign (`S-154`/`Q-66`), both through
   `followup_actions`, with the outcome recorded (`S-161`).
5. **The `/dashboard` overview block** — a sentence and a link, nothing more.
6. **The parent reminder** last, because it is the only piece that sends anything to a family —
   and the only one that can go wrong in public.
