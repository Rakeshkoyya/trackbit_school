# V1 blockers — the answers I need from you

> ## ✅ ANSWERED — 2026-08-01
>
> Sections A and B are answered inline below; **section C was accepted wholesale** ("your
> suggestions are almost nice, we can proceed"). The answers are recorded as **`D-78`–`D-88`** in
> `docs/brainstorm/decisions.md` (session 10), and `IMPLEMENTATION-PLAN.md` is updated to match
> (Revision 1). **This file is now a record, not a to-do** — if an answer here and a `D-nn` ever
> disagree, the `D-nn` wins.

**Written 2026-08-01**, after reading all nine brainstorm sessions (77 decisions, 81 questions,
three screen files, thirteen module files) and verifying the current code.

---

## How to answer this

There are 81 open questions in `open-questions.md`. **Most of them do not block v1** — they are
refinements, or they belong to modules I am recommending we cut. I have sorted them into four
sections:

| Section | What it is | What I need |
|---|---|---|
| **A · Scope calls** | 6 decisions that change **how big v1 is** | A real answer. These are the only ones that change the delivery date. |
| **B · Collisions** | 4 places where two of your own decisions contradict each other | A real answer. I cannot build either side until you pick. |
| **C · Defaults** | 38 questions where I have a recommendation | **Skim and object.** Silence = I build the recommendation. |
| **D · Deferred** | Questions belonging to things I'm recommending we cut | Nothing. Answer them when the module comes up. |

**The fastest path:** answer A and B (10 questions), skim C for anything that makes you wince, and
say *"rest as recommended"*. That unblocks the entire build.

Each answer goes in the **Your answer** column. Anything you leave blank in section C, I build as
recommended.

---

# Section A · Scope calls

These six decide whether v1 is a three-month build or a six-month one. Every one of them is a
thing you have already decided *in principle* — the question is only whether it lands in **this**
version.

---

### A-1 🔴 · Payroll — in or out of v1?

`D-05` and `D-06` moved payroll **in** and explicitly voided the SPRD2 fence. But `Q-05`–`Q-08`
are all unanswered, and they are not details — they are the whole calculation:

- estimate, or a payable record with payslips and statutory deductions? (`Q-05`)
- who may see a salary — any admin, or a new capability? (`Q-06`)
- what is the salary structure and where is it entered? (`Q-07`)
- what actually reduces pay — unapproved absence only? half-days? lates? what divisor? (`Q-08`)

**My recommendation: OUT of v1.** Three reasons, and the third is the real one:

1. It is the only module in the product carrying **real-world legal liability**. A wrong number
   here is a wage dispute, not a wrong chart.
2. It is the only module whose questions are all still open — everything else in this document has
   a defensible default. Payroll does not, because every school answers `Q-08` differently and the
   answer *is* the product.
3. **It needs `D-04` to exist first anyway.** Days-present is meaningless until half-day and late
   are captured. `D-04` is in v1 (it is cheap and it fixes the cover board). So v1 *builds the
   input to payroll* and stops there — which means shipping payroll in v2 is a small packet, not a
   restart.

What v1 **does** ship: half-day (AM/PM) and late on staff attendance, the running days-present
count, and the leave balance. The number a payroll would be computed *from* is captured and
correct from day one. What it does not ship: any screen showing money per person.

**Your answer:**
I agree lets defer payroll option but I want to have proper attendance and leave system capturing so I have number of days the teacher worked out of working days so I have information of the staff month.
---

### A-2 🔴 · The festival / holiday catalogue — in or out of v1?

`D-60` says we fetch state holidays, national holidays, all-religion dates and international
observances from the internet and store them platform-side. `Q-63` — the research that says
*where from* — you deliberately deferred to implementation.

**My recommendation: OUT of v1; the rest of the events module ships without it.**

Steps 1–6 of the events build order need **none** of it. What v1 ships:

- student date of birth at setup → **birthdays**, which is most of the module's daily value
- the school's **own** calendar, which it already maintains and which currently **has no read side
  at all** — an admin paints "Diwali" in April and the product never mentions it again
- the **Approve this date** sheet with the three lock levels — which is also the fix for a live
  defect (below)
- the two cards: admin overview *What's on*, teacher My Day strip

What it does not ship: rows suggested by us. The school types its own dates, exactly as it does
today, and for the first time they show up somewhere.

**Why I want this out:** a wrong Diwali date is a school decorating on the wrong day *because our
screen said so*, and it will be our screen it blames. That is not a risk worth carrying in the
version we hand to the first paying customer. In v2, with the research done, the catalogue drops
in behind the same approval sheet and changes nothing structurally.

**Your answer:**
I want this in the V1 and let me give you ideas, yes even the school own calender and the type is celebration or a event or holiday we capture it and remind it in this sections, and dont worry about wrongly displaying the diwali date form our side because it is just a reminder once they approve they can change the date as needed or fix it because usally chritmas will be given holidays but celebration is done way before, we will have that kind of flexiblity and then yes we will have intense research before implementing this module of section dont worry about wrong dates, I just want this added feature so product feel alive. 
---

### A-3 · The AI paper-check — in or out of v1?

`D-50` gives the exam photo a second, optional job: check the paper. `Q-51` asks how far it may go.

**My recommendation: OUT of v1, entirely.** Your own decision already calls it *"optional and
secondary"*, and the required half — transcribe names and marks — is built and works. Adding a
second AI claim to the exam screen buys nothing for the first customer and opens the one question
in the product with no deterministic backstop: there is no roster to check *"is this answer right"*
against.

If it comes back in v2, `S-116`'s scoping is right: only claims about **the teacher's paper**
(marks don't sum, a question is unmarked), never about the child's answer.

**Your answer:**
I need this in V1 and what i mean optional is that AI capability for analysis "is this answer right", I want the feature so teacher can easily enter the corrected sheet to the system, so our system holds like this in the exam tab after teach conducts exam and corrects the papers she cna simple open our app and take picture of each student and record his photos and once all the photos are added we analysis with AI and write down marks for each detect student and teacher can adjust the marks, or else we give option to enter manually like one by one. and also the under readable papers, we give option to enter and map details for that photo. so we have record of each exams, and there will be two tabs score and report after selecting the exam in the score just number will come and in report we give complete analysis like which topic are cover and which student are bad and good and which question are most wrong and all kind of analysis. 
now i decided there is not optional I want all this in V1.  

---

### A-4 · The exam training corpus — capture in v1, or not at all?

`D-54` says store the page images, what the model read, and what the human corrected it to, as a
future training corpus. `Q-61` asks whether that is opt-in and what the school gets back.

**My recommendation: CAPTURE in v1, USE in v2.** The split matters:

- The images and the model's read are **already stored** and already survive — that is evidence
  (P5), not corpus.
- The missing third is the human's answer, and it becomes recoverable **only at the moment of
  lock**. `D-53`'s verify-and-lock is in v1 regardless (it fixes a live defect). Writing the diff
  at that same moment costs almost nothing.
- **It cannot be recovered retrospectively.** Every month we don't capture it is a month of pairs
  gone.

So: write the diff at lock, behind an org setting **default off** (`Q-61`(b)), and build **no
export path at all** in v1. Nothing leaves the school's database this version. The de-identifying
export — which has to exist before the first export, not before the first row — is a v2 packet.

**Your answer:**
yes only capture in v1 I guess we are already having the system like we store photo of each exams and also the data is verified by teacher, so just make sure we have data so in future we can use it. 
---

### A-5 · May a parent submit an absence note? (`Q-01`)

Your session-1 heading said *"absent request from parents"*, but the flow you described was
staff-entered. This is the read-only fence.

**My recommendation: NO parent writes in v1.** The reason is on the absence card instead: a
`tel:` link — *"tell the school why"* — which closes the loop with zero writes and costs one line
of markup. Staff type the reason, exactly as `D-02` describes.

**Why I'd hold the line here:** the moment the portal accepts one write it needs moderation, a
pending state, a notification back, and an answer to *"I told the app and nobody read it"*. That
is a product, and it is the single most likely thing to generate an angry parent in month one.

**Your answer:**
okay i agree no parent writes only staff writes the reason by asking the kid or calling parents and we just capture the reason from the teacher. once the reason is added and allocated absent dates we show them in orangish-red and otherwise it will be in red. that will be displayed in admin dashboard and attendance screens. so this way admin can understand how many are absent and what teacher did follows up and noted in system or not.
---

### A-6 · Per-question capture for objective tests (`Q-53`)

You listed *objectives* as an exam type. For an MCQ paper the useful analytic is per-question
(*"nineteen of thirty got Q7 wrong"*), which a total mark can never give.

**My recommendation: OUT of v1.** It is the only idea in the entire brainstorm that needs a new
table **and** a new capture surface. Objective tests still record perfectly well as a total mark
in v1 — nothing is lost, only a future analytic is postponed.

**Your answer:**
yes agreed out of v1 there is not need, only thing is we generate a report for whole class and each student like a detailed report card of that exams. class report will also contain option like report card so there will be two level of report one is general report like a standard report card of school like subjects and exams of a student(showing just the numbers), and the other report is a detail anaylsis like per topic and skill abilities and per subject summary (generated using the ai summaries)

---

# Section B · Collisions

Four places where two things you decided cannot both be true. I cannot pick for you because each
one is a value judgement about your school, not an engineering trade-off.

---

### B-1 🔴 · `Q-66` — does a teacher chasing a fee see the amount?

`D-63`: **only the admin sees fee data.** `D-65`: **hand the defaulter to the class teacher, who
has the relationship.** Both cannot be literal — a task reading *"Call Kabir's father — ₹12,000
overdue"* breaks the fence the feature is built on.

| | |
|---|---|
| **(a)** | The task names the **family and the subject, never the amount**. *"Fee follow-up · Kabir Shah (8-B). Please speak to the family and record what they say."* |
| **(b)** | She sees amounts for her own students — a deliberate, narrow breach. |
| **(c)** | Only admins can be assigned fee follow-ups — fence intact, but it wastes the one person with a relationship. |

**My recommendation: (a), strongly.** The parent already knows the number; the teacher does not
need it to make the call. And the reason for the fence is not confidentiality for its own sake —
**a teacher who knows which families are behind on fees treats those children differently**, and
every child on that list has done nothing wrong.

If (a): I also close the inference routes — no sorting her tasks by amount, no *large/small* badge,
no count of how many families in her class are behind.

**Your answer:**
actually the assigned teacher for that student will get all the details of the fee history and installment date and pending amount and the conversation history regarding that fee payment( yes i know converations history I want you to maintain this in fee management system for every student) this information will be written in the task details like description and notes so once the task is assigned the teacher can know everything, 
mostly the teacher for follow up will be admin only so given the list of student assigned her for followup she can pull out data directly from the admin dashboard and call the parents. in bothcases we sent the detailed description inside that task. 
---

### B-2 🔴 · `Q-68` — do arrears count as pending?

**This is a live wrong number, not a design question.** `student_fees.opening_dues` — last year's
unpaid balance — is excluded from `total_fee`, from `collected`, from `overdue_amount` **and from
`status`**. So a student carrying ₹20,000 from last year with this year's instalments paid reads
**`paid`**, and never appears on the defaulter list. **The school's worst debtors are the ones the
screen cannot see.**

| | |
|---|---|
| **(a)** | Arrears count. `summary`, `overdue_students` and `status` all include them. |
| **(b)** | Arrears are **separate** — their own figure and their own list: *"₹3.2L in arrears from 2025-26, 22 families"*. |
| **(c)** | Leave as is, and the board's headline says **"this year"** out loud, every time. |

**My recommendation: (b).** (a) is tempting but it mixes two different collection problems — this
year's cash flow and last year's bad debt need different conversations and often different people.
(c) is defensible only with the disclaimer, permanently. What is **not** defensible is today's
behaviour, where the number is silently incomplete and nothing on screen admits it.

Whichever you pick, all three reads move together — `summary`, `overdue_students` and
`student_fee_status` — or the screens will disagree with each other.

**Your answer:**
yes i agree every year should be separate, and maybe we can show the previous by giving option to switch the acadamic year. 
---

### B-3 🔴 · `Q-73` — bands: is the unit a daily log or a weekly check-in?

You said both — *"logs today they did this and that"* and *"maybe weekly or sometime we
evaluate"*. They produce very different products, and **this decides whether the module is still
open in November.**

| | |
|---|---|
| **(a)** | **The weekly check-in is the unit.** Four fields, Friday, six children, five minutes. A daily note exists but nothing ever asks for one. |
| **(b)** | **The daily log is the unit**; the weekly evaluation rolls up the week's notes. |
| **(c)** | Cadence is per-subject configuration. |

**My recommendation: (a), and I consider this the highest-risk decision in the whole plan.** Six
children × a daily note = thirty free-text entries a week, from one teacher who is also teaching a
full timetable. Week one it gets done. Week three it is *"did flashcards"* thirty times. And by
then the admin's movement report is built on it, so the data is **worse than nothing**.

(c) is configuring a habit before anyone has formed it.

Whichever you pick, the page **opens already written** — his week is read from `lesson_observations`,
`check_results`, `homework_results`, `attendance_exceptions` and `session_student_logs`, capture
other teachers already did. That is what makes even (b) survivable, and it is the design either way.

**Your answer:**
yes agreed lets make it weekly checkin, so there will be a separate screen to record the performance of each c-band child and as I said for each teacher like in give subject there will be a group of students assigned and that teacher when open this c-band studnet she will see list of student and when clicked on one we get detailes report on theat student what is missing and what need to improve and growth so far and text taken and and studnet weekly logs. this is enough so we can calculate and report in admin dashbaord and teacher screens 
---

### B-4 🔴 · `Q-44` — past the gap, is "late" a fact about the child or the record?

`D-33` says past a 3-working-day gap homework *"can only be marked as late completion"*. But two
very different things produce a long gap:

- the **child** handed it in late — a fact about the child, and it goes into his permanent record;
- the **teacher** collected it on time and got round to recording it on Friday — a fact about the
  record.

Today the system cannot tell them apart, and forcing the first when it was the second **writes
something untrue about a student into their history** — the exact mistake `not_checked` exists to
prevent.

**My recommendation:** past the threshold the default verdict is worded **"recorded late"** (about
the record). The teacher can still explicitly mark a specific child as genuinely late. `checked_at`
vs the deadline keeps carrying the teacher's side separately, and both reach the admin — which is
what `D-38` asks for anyway.

**Also decide:** is the 3-day threshold an org setting? A boarding school and a day school will not
agree. *Recommendation: default 3, configurable in Settings, working days only.*

**Your answer:**
I have better decision making thing here, if the teacher didnot enter even one student homework at all for the 3days then we can understand that teacher has dealyed checking the homework, and if she enter the homework checking on the intended day (given date +1) then she checked but some students gave it late. let remove the 3-day threshold so make it one day so admin will get notifications directly when the teacher didnot checked homework or if checked number of student missed homework. and marking late is simply just a status do the homework at anytime teacher can mark them done or mark as late there is no hard limit we will keep it open so they can edit any time -simple for v1
---

# Section C · Defaults — object to any of these, or say nothing

38 questions. Each row is my answer and the one-line reason. **Anything you leave alone, I build
as written.** Grouped by module so you can skim the ones you care about.

## Attendance

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-02` | Does the attendance **mode** change the whole period card, or only attendance? | **Only attendance.** In `first_period` mode the teacher still opens every period to log the topic. | The syllabus forecast is built on per-period lesson logs; collapsing them breaks the planner's actual-vs-baseline arithmetic (P2). |
| `Q-03` | `twice_daily`: present AM, absent PM — what is it? | A **named state, `left_after_lunch`** — not a full absence in the register, but its own row on the admin board and its own signal to the parent. | This is the *reason a school picks that mode*. Collapsing it into "partial" throws away the only thing mode 3 exists to see. |
| `Q-04` | Minimum-attendance rule (the 75% question)? | **Yes — an org setting**, shown to the admin and on the parent's Today tab. Off by default. | It is the one number a parent will actually act on. Off by default because a school that doesn't enforce it shouldn't be made to look like it does. |
| `Q-11` | Mode changes mid-year — does history re-interpret? | **No.** The day row records the mode it was captured under; the register never re-reads the past. | Otherwise a school's own history changes under them when they flip a dropdown. |
| `Q-13` | A school-wide "no school today" that isn't a calendar holiday? | **Yes** — and it is the same *Approve this date* sheet from `D-58`, opened for today. One tap, a reason, and every downstream consequence stops. | A sudden closure is the most common real case, and building a second mechanism for it would be a third definition of "no school". |

## Class teacher

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-09` | Does the class-teacher dashboard replace My Day, or sit beside it? | **Its own nav item — "My Class"** — appearing only for a teacher who owns a class. | My Day stays the same product for every teacher, which makes it explainable and supportable. Mixing them makes the most-opened screen different for different people. |
| `Q-10` | Which modules on the class-teacher board? | **Six blocks, in this order:** needs-attention (red/yellow) · drifting · the month attendance grid · her class's syllabus across all subjects · her follow-ups · tonight's homework load. **No fees** (hard rule). Bands allowed but **not** in v1's first cut. | Order is people-who-need-something-today → people-who-will-next-week → the record → the academic position. Nothing above the fold is a chart. |
| `Q-14` | Can a class have two class teachers? | **No — one owner per class.** | A single named owner is what makes "assign the follow-up" unambiguous. It is a one-line change later; un-picking it after people have used it is not. |

## Parent access

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-24` | Where does the date of birth come from? | **Captured at setup with the roster** (`D-56`), a new importer column with real Indian date parsing (`dd/mm/yyyy`, `dd-mm-yy`, Excel serials). A DOB the importer can't confidently parse is **unresolved**, never guessed. Setup shows *"42 students have no date of birth"* until cleared. | A mis-parsed `mm/dd` silently moves 40% of a school's birthdays *and* breaks 40% of parent logins. Guessing is the one thing that must not happen. |
| `Q-25` | Siblings — one login or three? | **(b)** — after the first login, *"Add another child"*, each proved with their own DOB. The existing sibling switcher then works exactly as it does today. | A parent of three logging in three times is how a portal gets abandoned. |
| `Q-26` | Is the school code secret? | **Random 6–8 characters**, handed to parents, never published, never on the marketing site. | Combined with type-to-search on the child step, the roster is never browsable by anyone holding a code. |
| `Q-27` | What happens to the guardian phone link? | **It stays, and it stays the notification target.** DOB login *claims* the guardian rows for that phone; `notify_opt_out` stays per guardian row; revocation stays the live guardian-link check. | The whole PC-1 model hangs off it and it works. The login method changing shouldn't rewrite the account model. |
| `Q-28` | Can the password change? | **DOB is the first-time credential**; the parent is invited (not forced) to set a password afterwards. `/parent/auth/credentials` already exists. | A credential the school printed in a register should not be the credential forever. |
| `Q-29` | Is phone-OTP removed? | **Kept, not default** — it is the recovery path when a DOB is missing or wrong. | It is working, more secure code. Deleting it leaves the "no DOB on record" parent with nothing. |
| `Q-16` | Which denominator does a parent's "syllabus covered" use? | **The whole syllabus.** The admin sees both numbers side by side. | Coverage against *planned* topics **falls** when the school sizes next term's chapters — nothing was un-taught, but a parent reads it as the school going backwards. |
| `Q-19` | Does "missed while absent" stay on the parent's report? | **Yes**, worded as catch-up: *"taught while Diya was away — worth catching up"*. | It is the best line on any parent screen in the product: it turns an absence into an academic consequence a parent understands. It is about the child, not the school's pace, so `D-11` holds. |
| `Q-56` | Do parents see the school calendar? | **Yes** — read-only, through the same allowlist, and **only their own child's birthday**. | *"Is school open on Monday?"* is the most-asked question in a school office, the rows already exist, and it needs zero new capture. A list of classmates' birthdays is a roster leak wearing a party hat. |
| `Q-69` | Parent fee view — reminder only, or a page? | **Reminder only**, one line, on Today. No fee tab. | A parent's two questions are *how much* and *by when*, and both fit on one line. A tab invites the ledger, and the ledger invites *"why was I charged this"*, which is a counter conversation. |
| `Q-70` | Who gets the fee reminder? | **The primary guardian only**; the admin sees the other numbers to ring manually. | Money is the one topic where messaging both parents can land badly inside a family. Deliberately different from the absence alert, which reaches everyone. |
| `Q-39` | Does a parent hear about a homework miss? | **Only on a pattern — two consecutive homework days missed.** Never a single miss. | A message for every forgotten worksheet makes the school a nag and trains parents to mute the channel that later carries the absence alert. |

## Homework

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-40` | Is a "partial" worth half or nothing? | **0.5, everywhere.** | Today homework counts it as **zero** and the syllabus board counts a partial topic as **0.5** — same word, two arithmetics, one product. 0.5 is what "partly" means. |
| `Q-43` | Does a late completion count toward completion? | **(c)** — counts as **done, reported separately**: *"82% done · 6 of them late"*. A **waived** item leaves the denominator entirely. | Same discipline `not_checked` already uses: the figure stays true and the second fact isn't buried inside it. Folding late into done hides a class where everything arrives four days late. |

## Teacher load / timesheet

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-12` | Does covering a period earn anything? | **No — purely operational.** | The moment cover earns money the substitution record becomes a financial document needing approval and dispute handling. |
| `Q-15` | Half-day leave — which half, and who chooses? | **AM/PM on the request**, chosen by the applicant, editable by the admin on approval. | *Which* half decides which periods need covering, which is the entire reason SF-1 exists. |
| `Q-32` | Can the admin assign work into a free period beyond cover? | **Yes** — a `source = self \| assigned` flag on the entry, not a new table. One entry per period; an assignment onto an occupied period is replace-with-warning, never a second row. | Half the work in a school is handed out, not chosen. It turns the admin's screen from *"who is free"* into *"who is free — give it to her"*. |
| `Q-33` | Work outside the periods (a 4pm meeting)? | **Keep entries period-indexed**, plus a small day-level **extra duty** line. | `period_no` is what makes *"who is free in period 4"* answerable. A second time model should wait until a school asks. |
| `Q-34` | How far back can a day be filled in? | **No lock**, but bump `updated_at` (it exists and is never bumped) so the admin's detail view can distinguish recorded-that-day from back-filled. | A hard lock stops it being filled at all; no marker means March's back-fill reads like 11:58 on the day. |
| `Q-35` | Do hostel sessions count as teaching load? | **Yes, read-only, unioned in** — but reported **beside** school periods, not added to the same mean. | A warden running prep six evenings a week currently reads as *lightly loaded* on every board. An hour of prep and a taught period are not the same work. |
| `Q-36` | Who else may read a teacher's timesheet? | **Admin and self only** — unchanged. | Widening it is a one-line change later; narrowing it after people have seen each other's days is not. |
| `Q-37` | Does covering a period show on the substitute's own timesheet? | **Yes** — union `period_substitutions` in, read-only. | It is a bug, not a question: she covered three periods this morning and her own grid shows three *free* cells. It ships with the `/staff/today` fix, same union, other screen. |

## Exams

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-50` | Does any screen blend exam types into one number? | **Never blend.** One nullable `scale` field, two values — `minor` (slip / class / CET / chapter) and `major` (unit / term / pre-board). **Trajectory from minor, standing from major, never added.** | Today *"Maths is at 61%"* is the mean of an April diagnostic, twelve slip tests and one final, and the type filter defaults to off. Weights would be the report-card designer SPRD2 §11 fences. |
| `Q-52` | Does a recorded exam link to its planned exam block? | **Yes — one nullable FK** (`exam_event_id`). Nullable because a Tuesday slip test has no calendar block. | It is the join the two modules were both built for: *"we covered 70% of the Term-1 portion — what did it cost?"* is unanswerable without it. |
| `Q-62` | Can a locked exam be edited, and by whom? | **(c)** — the admin unlocks with a reason; the unlock is an **appended row**, never a mutation, and the frozen corrections are flagged rather than rewritten. | Same shape as `plan_approvals`, `demo_request_notes` and `leave_request_events` — status is a derived cache of the newest event. A well-worn pattern to copy. |

## Bands / support programme

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-75` | Does a parent ever hear about the support programme? | **Nothing in v1.** | P4 holds. But note this is a real cost, not a safe default: a child in a support programme whose family is never told means the school does work it gets no credit for. Worth revisiting in v2 as *the school's effort, never the tier*. |
| `Q-76` | Descriptors per subject × band, or also per grade? | **Per subject × band (nine texts), with a nullable grade-group scope column added now and unused.** | 27 empty boxes get filled in by nobody, 72 by no one at all. The column costs nothing now and is expensive to retrofit. Ship the nine **pre-written and editable**. |
| `Q-77` | Is a band ever scoped to a skill? | **No.** Leave `scope_skill_area_id` in place, stop treating it as a band scope; `skill_areas` keeps its real job — the diagnostic radar. | *"Is Kabir in the reading programme or the English programme"* is a question nobody should have to ask. |
| `Q-78` | What does Band A get? | **The harder version of the same work.** `daily_checks.band_scope` already accepts `'A'` and the generator already writes band-scoped checks — it simply never generates one for A. | One line of generator code. Without it the letters quietly become good/average/bad and the tier drifts into the label P4 exists to prevent. |
| `Q-79` | The test says B, the teacher says C — which wins? | **The teacher wins, and the disagreement is recorded** on the band row: *"teacher assessment (test suggested B)"*. | The shape already exists — `band_board` returns `current_tier` and `suggested_tier` side by side. It also produces the only signal that would ever tell a school its thresholds are wrong. |
| `Q-80` | A promoted test only some children sat — what about the rest? | **Stated on screen:** *"12 re-banded · 26 didn't sit this test and keep their current band."* | The code already skips them correctly. Silence is how a teacher ends up believing the whole class was re-assessed on Tuesday — not-captured-is-not-a-zero, applied to a band. |
| `Q-81` | Does filing a re-band show the moves for review first? | **Yes, for every route.** *"3 moving up, 1 moving down, 8 unchanged, 26 didn't sit it"* → Confirm. | `student_bands` is append-only, so a mistaken re-band is **permanent** in a child's record. A child slipping B → C is the most consequential thing this module does and it currently happens without anyone reading his name. |

## Events & dates

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-58` | Is the birthday wish outbound to guardians, or in-school? | **In-school only in v1.** The teacher's strip and the class teacher's month list. Nothing is sent. | The outbound version will eventually fire at a family that has just lost someone, or for a child who left in March. If it ships later: human-pressed, `notify_opt_out` honoured, `status='left'` excluded, and a record that it fired. |
| `Q-60` | One calendar or two? | **One grid, one agenda.** Plan → Year gains a read mode and stays the only calendar grid; *What's coming* is an **agenda** — dates in order with what each needs — which is not a calendar and so doesn't compete. | The worst outcome is a new route rendering the same grid with a different brush set, and that is the default outcome if nobody decides. |
| `Q-64` | Do teachers see unapproved suggestions? | **Approved only.** | The strip's whole value is that it costs zero attention and is never wrong. A provisional row makes her decide whether to trust it, which is more expensive than the information is worth. |
| `Q-65` | Locking a past or current day — what happens to what was captured? | **Kept and shown, never deleted.** *"Periods 1–2 were taught and recorded; locking 3–8."* | A school that closed at 11am genuinely taught period 1. Destroying that is both data loss and a law-3 violation. `blocks_periods` already expresses exactly this. |

## Syllabus

| Q | Question | What I will build | Why |
|---|---|---|---|
| `Q-18` | Is "not enough data yet" acceptable to an admin? | **Keep the guard, change the copy to a countdown**: *"ranking starts once 3 subjects have plans (2 so far)"*. | Honest, and it reads as progress rather than a broken screen — which matters most in week two, when every school sees it. |

---

# Section D · Deferred — no answer needed now

These belong to things I am recommending we cut from v1 (section A). They come back with their
module.

| Q | Belongs to |
|---|---|
| `Q-05` `Q-06` `Q-07` `Q-08` | Payroll (A-1) |
| `Q-63` | The observance catalogue (A-2) |
| `Q-51` | The AI paper-check (A-3) |
| `Q-53` | Per-question objective capture (A-6) |
| `Q-54` `Q-55` | Superseded by `D-60`/`D-61`; only relevant once the catalogue is built |

---

# What I am proceeding with regardless

These need no decision — they are **verified live defects**, found across sessions 3–9, all of
them small, none of them dependent on anything above. They are packet **V1-0** in the plan and
they ship first.

| | Defect |
|---|---|
| 🔴 | Painting a "Celebration" on Plan → Year **silently removes a teaching day**, even when the school is open — every plan forecast in the school is denominated in effective teaching days |
| 🔴 | `/staff/today` shows an absent teacher as **eight free periods** — on the screen the admin opens to find cover |
| 🔴 | `busy_reason` can't see approved leave, so cover can be assigned to someone on leave |
| 🔴 | A child absent when homework was set is flagged not-done, and their guardian is reminded about work they never received |
| 🔴 | `/tasks` re-filters board rows on the client, so an **admin sees none of the follow-ups they assigned** |
| 🔴 | The rail's due dates default to midnight **UTC** — a Monday follow-up is overdue at 05:30 Tuesday |
| 🔴 | The rail dedupes per calendar day, so three days of absence create three identical open tasks |
| 🔴 | An **intervention can never be finished** — `status` allows `achieved` and nothing updates it, so a goal met in July keeps injecting a daily check in March |
| 🔴 | **Every intervention in every real school is created unassigned** — it assigns to `class_teacher_member_id`, which no screen has ever set |
| 🔴 | `categorize_from_cycle` writes **one overall letter** from the sum of every score in a cycle |
| 🔴 | `apply_band_suggestions` re-bands a whole class from each child's **most recent cycle, whatever it is** — a five-mark slip test can move eleven children between tiers |
| 🔴 | Slip tests and term exams **pool into one average** on three screens, and the type filter defaults to off |
| 🔴 | `ExamService.save` full-deletes and re-inserts a cycle's scores on every edit — a mark corrected in November silently replaces July's |
| 🔴 | `GET /fees/overdue-students` returns the named defaulter list and **the web app has never called it** |
| — | The homework check queue looks at **exactly one day**, so Friday's homework never appears on Monday |
| — | The cover picker never reads the timesheet, so a teacher doing exam work is offered as free |
| — | A substitute can't check homework, though the column recording who checked exists for that case |
| — | `schoolApi.studentHomework`, `studentInterventions` and the fees defaulter list are all **built, wired into the client, and called by nothing** |
| — | `ExamService.save` never sets `verified_by`, so the *"· verified"* badge can never light up |
| — | `calendar_events` has had a write side for a year and **no read side** |
| — | `overdue_students` runs a query **per student** — 200 defaulters is 200 remote round trips |
| — | `leave.py::_working_days` passes ORM rows to a pure function — **every leave application 500s in a school with a calendar event** |

---

*Once A and B are answered, `IMPLEMENTATION-PLAN.md` becomes executable end to end.*
