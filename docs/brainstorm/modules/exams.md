# Module — Exams & scores

Every test a school runs, from a five-mark slip test on a Tuesday to the term finals — captured
once, by the teacher who marked it, and readable afterwards at three levels: the school, the class,
the child.

**Sessions:** 6 (2026-08-01)
**Related:** [`syllabus.md`](syllabus.md) · [`homework.md`](homework.md) ·
[`class-teacher.md`](class-teacher.md)

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Teacher** | evening, marked papers in a stack beside her | phone or laptop, minutes | *"Let me get these marks in."* |
| **Teacher** | next morning | phone | *"How did 8-B actually do?"* |
| **Admin** | after an exam round | desktop, minutes | *"Which class and which subject need attention?"* |
| **Admin / class teacher** | before a parent meeting | desktop | *"How is this child doing, and can I show them why?"* |

The teacher's moment is the one that decides whether the module exists at all. **Marks entry is a
desk activity with a stack of papers** — the same shape as homework checking (`D-36`), and the
opposite of the 9:02 capture flow. Optimising it for a thumb between classes would be the mistake
session 4 already made once.

## 2 · What they must be able to decide

- **Teacher:** get a class's marks recorded without typing forty names, and see immediately whether
  the class understood the chapter.
- **Admin:** which class, which subject, which teacher needs help — with participation attached, so
  a half-marked exam can't flatter anyone.
- **Class teacher, at a parent meeting:** what this child's trajectory is, **and show the paper**.

## 3 · Where it stands today *(verified)*

**Most of what was described is built.** SC-5 shipped the exam-first capture flow on 2026-07-12.

| Asked for | Status |
|---|---|
| Multiple exam types recorded in one place | ✅ `CYCLE_TYPES` — 9 values incl. `chapter_test`, `class_test`, `slip_test`, `objective`, `band_test`, `unit_test`, `term_exam` (`models/assessments.py:57`) |
| A page where the teacher enters marks | ✅ `/students/scores/[classId]`, **Whole class \| Few students** tabs; `ExamService.save` creates cycle + scores in one transaction (`services/exams.py:209`) |
| Photo scan → extract names and scores | ✅ `ai/scores.py::extract_marksheet` transcribes; **`score_match.py` decides identity** — roll → exact → fuzzy → unmatched-with-candidates, and one student can never be claimed twice |
| Extract the paper's basic details | ✅ `parsed_meta` — title, subject, total marks, topic, date — prefills the form the human confirms (`models/assessments.py:165`) |
| Evidence kept | ✅ `score_capture_pages`, R2 object keys, URLs minted per read, kept forever (P5) |
| A report for a student | ✅ `services/growth.py` → `/students/[id]` — score history, subject performance, ability radar |
| Class-level analytics | ✅ `AssessmentService.class_analysis` + `trends` → `components/school/class-analytics.tsx` |
| Subject / school-level analytics | ✅ `services/insights/exams.py` → `/dashboard/exams` — by class, by subject, trajectories, distribution bucketed **in Postgres** |
| Participation beside every average | ✅ and it is the module's stated honesty rule (`insights/exams.py:10-14`) |
| **Evaluate whether the paper was marked/answered correctly** | 🔴 **not built, and it is the one genuinely new ask** |

The AI split is already the right one and worth naming, because the new ask tests it: **the model
transcribes, deterministic code decides.** `ai/scores.py`'s own prompt says *"Transcribe what is
printed — never invent"*, and `score_match.py` exists so that "a hallucinated name can never write a
score". Nothing in the module currently asks a model for an **opinion**.

## 4 · What's wrong with it

Five, all verified. Four of them are about the same thing: **the module records exams but does not
organise them** — which is precisely the gap the founder named.

### 4.1 A school that runs "CET" cannot record a CET

`assessment_cycles.type` is a **CHECK constraint over 9 fixed values**
(`models/assessments.py:57-58, 84-88`). "CET" is not one of them. The school either cannot save it,
or files it as `class_test` — and once it is a `class_test` no analytic can ever separate it again.

**Three weeks ago this exact question was answered the other way.** `core/work_types.py` is the
timesheet's picker, and its docstring is explicit:

> *"the column is plain Text with **no CHECK constraint**: a school that renames its work must
> never lose rows to a database error… an unknown value titles itself instead of vanishing."*

Two modules, opposite answers, and the exam one is the one where the school's own vocabulary
matters most — *CET*, *cycle test*, *revision test*, *pre-board* are the words the staffroom
actually uses. See `S-113`.

### 4.2 Every kind of test pools into one average

`ExamInsights.board` computes `tot_s / tot_x` across **all** cycles in scope, and `by_subject`
pools raw marks the same way (`insights/exams.py:126-164`). A 5-mark slip test and an 80-mark term
exam are added into one fraction. `class_analysis` and `growth` do the same.

There *is* a `type_filter`, and it defaults to none — so the number the admin sees first is the
blended one. **"Maths is at 61%"** is then a fact about nothing: it is the arithmetic mean of a
diagnostic taken in April, twelve slip tests, and one final. See `S-114`.

### 4.3 A student's report card cannot tell a slip test from the finals

`GrowthScore` is `{cycle_name, date, score, max_score}` — **no type** (`schemas/growth.py:55`). The
score history on `/students/[id]` draws one series through all of them.

So a child whose slip tests run at 40% and whose finals are 85% reads as *erratic*, and a child who
is flat at 60% across both reads as *the same as* a child flat at 60% on slip tests alone. This is
the screen a class teacher sits in front of a parent with.

### 4.4 The exam the planner plans for and the exam whose marks are recorded are two different objects

V2-P7 added `exam_portions`: an exam is a `calendar_events` row of type `exam_block`, and a portion
says *"for this class-subject, that exam covers the syllabus up to this topic"*
(`models/exams.py:1-12`). The syllabus board answers *"will the Term-1 portion be finished before
the Term-1 exam?"* from it.

**`AssessmentCycle` has no `exam_event_id`** (`models/assessments.py:61-88`). So the two halves
never meet:

- the planner knows an exam is coming and what it will cover;
- the results know what was scored;
- **nothing can ask "we finished only 70% of the portion — did the marks show it?"**

That question is the entire reason to have both modules, and it is one nullable column away. See
`S-115`.

### 4.5 An exam saved through the new flow can never show as verified

`AssessmentScore.verified_by` exists, `AssessmentService.verify` exists — and `ExamService.save`
writes `entered_by` only (`services/exams.py:275-279`). The feed then renders *"· verified"* off
`bool_or(verified_by IS NOT NULL)` (`exams.py:108`, `web/…/scores/page.tsx:48`), a badge that
**cannot light up** for any exam recorded through SC-5. Either verification means something here
and gets a surface, or the badge goes. Small, but it is a promise on screen with nothing behind it.

## 5 · Ideas and directions

### Decided — `D-49` `D-50`

- **`D-49`** Every test the school runs is recorded in one place, by the teacher who marked it,
  **either by form or by photo**, and is afterwards readable at **school · class · subject ·
  student** level. *(Substantially built — §3.)*
- **`D-50`** The photo does **two** jobs: **names + scores extraction, which is required**, and
  **checking the paper, which is optional and secondary**. The second never blocks the first.

### The new ask, and the line it has to respect

> *"we also evaluate if the exam paper is done correctly or not (this is optional)"*

**This is a different kind of AI claim from anything else in the product, and the difference is
worth being precise about.** Every existing call either transcribes (*"what is printed on this
page"*) or proposes a mapping a deterministic validator then checks (`ingest.py` filters the
model's column guesses against the real column list; `score_match.py` refuses to attach a
`student_id` the roster doesn't confirm). **There is no roster to check "is this answer right"
against.** It is the model's opinion, about a child, with nothing behind it.

Which does not mean don't build it. It means **build the half that has a ground truth**:

**`S-116` · Ship it as a *marking check*, not an *evaluation*.** Two claims only, both about the
**teacher's paper** rather than the child's mind, and both checkable:

- **the marks don't add up** — per-question marks sum to 23, the total written at the top says 25.
  This is arithmetic, the model only has to read digits it is already reading, and the school can
  verify every instance in three seconds.
- **a question looks unmarked** — no tick, no cross, no number beside it.

Both are genuinely useful (a mis-totalled paper is the most common real error in a marked stack,
and it is the one that reaches a parent), neither requires the model to know the subject, and both
degrade to silence when the photo is poor.

**`S-117` · Anything that judges the answer itself stays behind a flag, is never persisted, and is
never phrased as a verdict.** *"Q4 may need a second look"* is a prompt to a human. *"Q4 is wrong"*
is the product forming an opinion about a child's work — and once that is stored it is one join
away from a report card and two from a parent. The existing doctrine already covers it — *every AI
output lands in a human-confirm surface before persisting* — but here the confirm surface has to be
the **only** place it exists.

⚠️ **Fence question for the founder (`Q-51`):** SPRD2 §11 puts *"test authoring/conducting"* out of
scope. Evaluation is neither, so the letter of the fence does not block this — but it is close
enough that it should be an explicit decision rather than a drift.

### Proposed — `S-113` … `S-120`

**`S-113` · The exam type is the school's own word.**
Drop the CHECK constraint; keep the nine as a **picker**, and let an unrecognised value title
itself, exactly as `work_types.label_for` does. A school that runs *CET* files it as *CET* and
every analytic can separate it forever after. Fixes 4.1.

**`S-114` · Add `scale` — two values — and never blend across it.**
`minor` (slip test, class test, CET, chapter test: frequent, low-stakes) · `major` (unit, term,
pre-board: rare, high-stakes). One nullable column, defaulted from the type.

Then every screen has an honest default: **trajectory is drawn from `minor`** (that is what
frequent tests are *for* — they show movement), **standing is read from `major`**, and **the two
are never added together.** Fixes 4.2 and 4.3 with one field.

> ⚠️ **The obvious alternative is weights, and it is a trap.** "Slip test 10%, term exam 60%" is a
> **report-card designer**, which SPRD2 §11 fences — and rightly: every school wants different
> weights, the composite it produces is checkable against nothing, and the argument about the
> weights becomes the product. Two buckets and *never pool* gets the same honesty with none of the
> policy.

**`S-115` · One nullable `exam_event_id` on `assessment_cycles`.**
Links the recorded marks to the planned exam block and therefore to its portion. Unlocks the one
question neither module can answer alone: *"we covered 70% of the portion — what did that cost?"*
Nullable because a Tuesday slip test has no calendar block and never will. Fixes 4.4.

**`S-116` / `S-117`** — above.

**`S-118` · A student's average needs its denominator too.**
`insights/exams.py` already refuses a bare average at school level — *"88% from 9 of 42 students is
not an 88% class"*. The **student's** card has no equivalent: *"61%"* over what? Three of the nine
tests the class sat? A child who is absent for the hard ones reads as strong. Say **"61% across 5
of the 9 tests 8-B sat"**. Same rule, one level down (ux-principles §4).

**`S-119` · Put the paper on the child's page.**
The photo pages are kept forever as evidence (P5) and rendered on the exam detail screen — but
`/students/[id]` shows a number with no way back to it. *"Can I see it?"* is the one question a
parent meeting actually produces, and it is unanswerable from the screen where it is asked. The
plumbing exists (`storage.url_for`); it is a link.

**`S-120` · Per-question capture for objective tests is a different module — say so now.**
The founder listed *objectives* as a type. For an MCQ paper the analytic that matters is
**per question** — *"nineteen of thirty got Q7 wrong"* — which is the one thing a total mark can
never yield, and which points straight back at a topic. It is also a new table, a new capture
surface, and a real scope increase. Worth doing eventually; **not** worth sneaking in under
"exams". See `Q-53`.

### Second pass — verify-and-lock, and the training corpus (`D-53` `D-54` `D-55`)

The founder's follow-up adds a third job to the capture screen and answers `Q-49`:

> *"once the scan is done teacher will verify it and lock the data, so internally we can capture the
> data of images and the validation data for that image so later on we can train our own model —
> but this idea is for future."*

**`S-135` · Make the new exam-type field a small `exam_types` table, not a bare column.**
`D-55` is right that the field goes **beside** `type` rather than replacing it — code branches on
`type` today (`diagnostic` → skill grid, `band_test` → admin-only, `grid_only` in the feed), so
`type` stays the **system kind** and the new field is the **school's word**.

The reason to make it a table rather than free text: **the exam type is the grouping key for a
year of trend lines.** *"CET"*, *"C.E.T"* and *"Cet"* typed on three different evenings become
three series on the admin's chart. `work_types` gets away with free text because a timesheet bucket
is never a chart's x-axis; this is. A table also carries **`scale`** (`S-114`) per type, so the
school configures *"CET = minor"* once in Setup and the teacher picks **one** thing per exam
instead of two. Precedent in the codebase: `board_categories` does exactly this for task tags —
a free-text tag given an identity, a colour and an order.

*This contradicts session 6's "three nullable columns and nothing else" line. The table is worth
it; the bare column still works if the cheaper build is preferred.*

**`S-136` · The lock is what makes the corpus valid — it is not UI polish.**
*(verified)* `ExamService.save` **full-deletes and re-inserts** a cycle's scores on every edit
(`services/exams.py:270-279`). So a mark corrected in November silently replaces the mark confirmed
in July, and nothing records that they differed. For a report card that is survivable. For `D-54`
it is fatal: **the "human truth" half of every training pair would keep changing after the fact**,
and a corpus whose labels drift is worse than no corpus, because you cannot tell which rows moved.

So `locked_at` (+ who) is load-bearing twice over — and it also finally gives
`assessment_scores.verified_by` the meaning it has never had (§4.5).

**`S-137` · Store the diff, not just both sides.**
The value in this corpus is concentrated almost entirely in the rows where **the human changed
something** — a 7 read as 1, a fuzzy name match the teacher rejected, a total the model got wrong.
Fifty thousand correctly-read pages teach very little. Storing `{parsed_rows} → {locked_rows}` as
an explicit diff at lock time makes the corpus queryable as *"where were we wrong"* rather than
*"everything we ever saw"*, and it is the difference between a dataset and a folder.

**`S-138` · Training is a different purpose from running the school — ask for it.**
This is the first data in the product that does not serve the school that entered it. It is
children's handwriting with their names on it, and it is the school's. Make it an **org setting**
(the shape already exists — `parent_portal_enabled`, `band_a_min` live on `organizations`), default
off, turned on when the school agrees.

⚠️ **And note that de-identification cannot happen at capture.** The matcher needs the name to
verify the row, and the child's name is written on the image itself in their own hand. So the
corpus is PII until it is cropped or redacted **on the way out** — which means that step must exist
before the first export, not before the first row. See `Q-61`.

**`S-139` · Unlocking is an appended row, never a mutation** (law 3), carrying a reason — and it
**flags** the affected training pair rather than silently rewriting it. Same shape as
`plan_approvals`, `demo_request_notes` and `leave_request_events`, where the status is a derived
cache of the newest event. See `Q-62`.

**`S-140` · Record *why* a row was corrected, in four buckets.**
`misread_digit` · `wrong_student` · `unmatched` · `header_wrong`. One tap on the review row, and it
turns the corpus from "these two differ" into "the model confuses 7 and 1 in this handwriting" —
which is the only form in which this data ever improves a model.

**`S-141` · Say the storage cost out loud, once.**
~40 pages/exam × ~500 KB × ~50 exams/class-year × 20 classes ≈ **20 GB per school per year**, kept
forever in R2. That is cheap and fine — and it should be a decision rather than a surprise in month
nine. It also argues for keeping the **page** image (already what we store) rather than adding
per-student crops, which would multiply the count and cross the batch-evidence fence (P5).

### Rejected

- **Weighted composite marks / a computed final grade** — REJECTED, see the warning under `S-114`.
  This is the report-card designer the architecture fences, and the fence is right.
- **Storing an AI verdict on a child's answer** — REJECTED (`S-117`). It may be *shown* to a human
  who is looking at the paper; it is never written down.
- **Making marks entry a between-classes flow** — REJECTED before it was proposed. Marking is a
  desk activity with a stack of papers; `D-36` already settled the identical question for homework.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `Scores` — `/students/scores` | teacher | EXISTS | *"Let me get these marks in."* |
| `Exam capture` — `/students/scores/[classId]` | teacher | CHANGING | *"Forty papers, marked. Now what?"* |
| `Exam` — `/students/scores/exam/[cycleId]` | both | CHANGING | *"How did they do, and is this right?"* |
| `Exams` — `/dashboard/exams` | admin | CHANGING | *"Which class and subject need attention?"* |

**Not designed here:** `/students/[id]`, the report card. This module leaves three requirements on
it — the score history must distinguish a slip test from the finals (`S-114`), the average needs its
denominator (`S-118`), and the paper should be one tap away (`S-119`) — and hands them to the
**Students** session, which owns that page. Six sessions have now added blocks to it without anyone
designing it; adding a fifth set here would make that worse, not better.

## 7 · What we deliberately don't build

- **No test authoring or conducting** (SPRD2 §11). We record what happened on paper.
- **No report-card designer, and no computed composite grade.** `S-114`'s two buckets are the
  furthest this goes.
- **No AI verdict stored about a child's answer** (`S-117`).
- **No ranking of students, and no rank on any parent-facing surface.** A position in a class is
  the one number that changes a child's year and tells a teacher nothing they can act on.
- **Bands stay out of this module entirely** (P4) — `insights/exams.py` already includes `band_test`
  cycles as *marks* while returning no tier anywhere, and that is the correct line.

## 8 · Open questions

| | Status |
|---|---|
| `Q-49` — fixed list or the school's word? | **ANSWERED — `D-55`.** A new field beside `type`; `S-135` recommends a table |
| `Q-50` — does any screen blend exam types? | 🔴 open — three screens currently show a blended number |
| `Q-51` — how far does the paper check go? | 🔴 open — the fence |
| `Q-52` — link the exam to its planned block? | open — one nullable FK |
| `Q-53` — per-question capture for objectives? | open — the only idea needing a new table |
| `Q-61` — is the corpus opt-in, and what does the school get? | 🔴 open — blocks **using** it, not building it |
| `Q-62` — can a locked exam be edited, and by whom? | open — blocks the lock's UI |

## 9 · Data implications

Session 6 said *"three nullable columns and one dropped constraint"*. The second pass changes that
— honestly, upward:

**On `assessment_cycles`:**
- **`exam_type_id`** — the school's own type (`D-55`). `S-135` argues this points at a small
  **`exam_types` table** (name · system kind · `scale` · position) rather than being free text,
  because it is the grouping key for a year of trend lines. The existing `type` **stays**, as the
  system kind the code branches on.
- **`exam_event_id`** — nullable FK to `calendar_events` (`S-115`).
- **`locked_at` / `locked_by`** — `D-53`. Or, if `Q-62` picks the appended form, a small
  `exam_lock_events` table and `locked` becomes a derived cache — the `plan_approvals` shape.
- `scale` moves onto `exam_types` if `S-135` lands; otherwise it is a column here (`S-114`).

**On `score_captures` (all draft-side, nothing new about a student):**
- **`check_findings`** — the marking-check output (`S-116`).
- **`locked_rows`** + **`corrections`** — the human's confirmed rows and the diff against
  `parsed_rows`, written **once, at lock** (`S-136`/`S-137`), each correction carrying a reason
  bucket (`S-140`).

**On `organizations`:** one boolean for `S-138` (`training_data_opt_in`), default off.

**Schema-only, no migration:** `GrowthScore` gains `type` + `scale` (4.3).

So: **one small table (`exam_types`), one boolean, and a handful of nullable columns** — plus
`S-120` (per-question), still scoped out, still the only idea needing a table of real size.

## 10 · Rough build order

1. **`D-55` / `S-135`** — the exam type. Until it lands a school cannot record its own vocabulary,
   and mis-filed exams do not un-file themselves.
2. **`D-53` / `S-136`** — verify-and-lock. It is the trust gate, it fixes §4.5's dead badge, **and
   it must exist before `D-54` stores anything**, because an unlocked score is not a label.
3. **`S-114`** — `scale` and the never-pool rule across `insights/exams.py`, `class_analysis` and
   `growth`. The founder's "organise them", in one field.
4. **`D-54` / `S-137` / `S-140`** — write the diff at lock, with reason buckets. Cheap once step 2
   exists; impossible before it.
5. **`S-118`** + **`S-119`** — the student's denominator and the link to the paper. Both small, both
   on the screen a parent meeting happens over.
6. **`S-115`** — the exam-block link. Unlocks the syllabus↔results join.
7. **`S-116`** — the marking check, drafts only, after `Q-51` is answered.
8. **`S-138`** — the opt-in setting and the de-identifying export, before the first export ever
   runs.
