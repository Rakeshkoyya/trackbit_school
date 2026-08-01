# Module — bands (the A/B/C support programme)

Not a grading scheme. A **programme**: assess every child against a written standard, group them,
give every C child a teacher who owns moving them to B, work at it, re-assess, and measure the
**movement**.

**Sessions:** 9 (2026-08-01), **two passes — FINALISED**
**Related:** [`exams.md`](exams.md) (bands were deliberately left out of it) ·
[`class-teacher.md`](class-teacher.md) (the owner problem) · [`homework.md`](homework.md) ·
[`syllabus.md`](syllabus.md) · [`parent-access.md`](parent-access.md) (P4)

> **Status: finalised.** The second pass closed all three blockers — the band is **per subject**
> with no overall letter (`D-75`), re-banding happens on a **test the teacher may promote**
> (`D-76`), and there is **one owner per subject** (`D-77`). The build order in §10 is buildable
> as it stands; the remaining `Q-nn` are copy and grain, not structure.

---

## 1 · Who this is for, and when

| Role | The moment | Device / time budget | The question they arrive with |
|---|---|---|---|
| **Subject teacher** (assessing) | Week 2 of the year, after the diagnostic test | laptop, 20 min per class, once | *"Which of my 38 children can't read the textbook?"* |
| **Assigned teacher** (the owner) | 4pm, twice a week, after her last period | phone, **60 seconds per child** | *"What did I do with Kabir today, and is he any closer to B?"* |
| **Assigned teacher** (weekly) | Friday, or Monday morning | phone or laptop, 5 min for all her children | *"Which of my six are moving and which one am I stuck on?"* |
| **Subject teacher** (in the period) | 9:02, class in front of her | phone, **seconds** | *"Who in this room needs the easier version of this?"* |
| **Admin** | Monday, and at term end | desktop, minutes | *"Is this programme working — did anybody actually move?"* |
| **Admin** (setting it up) | Once, at onboarding | desktop, an hour | *"What does a B child in English mean in my school?"* |
| **Parent** | — | — | **Nothing. P4.** The tier never reaches them. |

The two teacher moments are different people, and the module dies if they are given the same
screen. The 9:02 teacher will never open a support log. The 4pm owner will.

## 2 · What they must be able to decide

- **Which band is this child in, for this subject** — and on what evidence.
- **Who is responsible** for a C child, by name, per subject.
- **What "moved to B" means for this child**, decided before the work starts, not after.
- **What to do with him tomorrow** — the next concrete thing, not a goal statement.
- **Is he moving?** — for the owner, weekly; for the admin, per term.
- **Is the programme working?** — which is a question about *movement*, not about distribution.

## 3 · Where it stands today *(verified in code, 2026-08-01)*

**More is built than anyone thinks, and the one loop the module exists to close cannot be closed.**

### 3.1 · The tier itself — built, append-only, and correct

`student_bands` (`models/assessments.py:117-137`): one append row per change, `tier A|B|C`,
scoped to a **term**, `set_by` + `note`, never updated in place. Law 3 is honoured. The history is
real and `/students/[id]` renders it (`students/[id]/page.tsx:194-232`) as
*"Support tier B"* + *"Support tier history: C (12 Jul) → B (30 Jul)"*.

### 3.2 · Three ways a tier gets set — all of them already work

| Route | Where | Verified |
|---|---|---|
| **Manual, per child** | a `set…` dropdown on the band board | `assessments.py:377-385`, `assessments.tsx:157-162` |
| **One tap from a band test** | `POST /assessments/bands/categorize` | `assessments.py:326-362` |
| **One tap from "the latest scores"** | `apply_band_suggestions` | `assessments.py:299-324` |

Thresholds are **two org-wide numbers** — `organizations.band_a_min` / `band_b_min`, default 75 / 50
— configured from a sheet on the bands page (`assessments.py:269-280`, `bands/page.tsx:30-70`).

### 3.3 · The C-band child already gets differentiated work every single day

This is the part nobody knows exists. `RecommendationsService._generate`
(`recommendations.py:131-158`) reads the class's band distribution and materialises, per
class-subject per day, with **zero teacher setup**:

- ≤ 2 class-wide checks,
- **+ 1 richer check when there are C-band children in the room**,
- **+ ≤ 1 targeted check per intervention student, by name.**

`daily_checks.band_scope` is `all|A|B|C` (`models/checks.py:52`) and the teacher confirms
*"class did it ✓"* and taps only the deviations, which land in `check_results`. So a C child is
**already** being given an easier route through today's topic, and the misses are already recorded
per child, and no screen in the product ever says so.

### 3.4 · Per-child capture already exists in five places, all exception-shaped

A C child's week is largely written down already, by teachers doing their normal work:

| Signal | Table | Shape |
|---|---|---|
| *"needs work on Reading today"* | `lesson_observations` | rating `needs_work`/`excellent` + note, per section/concept, **exceptions only** (`classroom.py:99-146`) |
| *"didn't do the C-band check"* | `check_results` | `not_done` \| `note` (`checks.py:73-94`) |
| *"didn't do homework"* | `homework_results` | `not_done` \| `partial`, with `not_checked` kept distinct |
| *"wasn't there"* | `attendance_exceptions` | absent \| late |
| *"in evening study he finished Ex 4.2 without help"* | `session_student_logs` | named sections + free note (HS-2) |
| *"I spent period 7 on reading practice"* | `timesheet_entries` | `work_type='student_support'` — **already a bucket** (`core/work_types.py:18`) |

### 3.5 · Interventions — the goal exists, the loop is broken

`interventions` + `intervention_items` (`models/assessments.py:210-244`): a goal, a
`target_tier` defaulting to `B`, a checklist, and each checklist line **spawns a task**
(`assessments.py:535-563`).

## 4 · What's wrong with it

### 4.1 🔴 One letter per child, when the child is three different students

`categorize_from_cycle` sums **every score in the cycle** into one percentage and writes **one
overall tier** (`assessments.py:339-353`). `_current_tiers`, `current_band_map`, `band_board` and
`recommendations._current_tier` all filter `scope_skill_area_id IS NULL` — the *overall* row.

A child who reads two years below his grade and is fine at arithmetic gets **one letter that
describes neither**, and the daily check generator then gives him easier maths he doesn't need
while his English goes untouched. This is the founder's per-subject decision (`D-68`) and it is
also, independently, the module's biggest live defect.

> Note the scope column already exists — `student_bands.scope_skill_area_id` — and **has never been
> written by any code path**. The mechanism for scoped bands was built and then only the overall
> row was ever used.

> ✅ **Decided — `D-75`.** Per subject, and the overall letter is **retired**. Cheaper than it
> looks: `categorize_from_cycle` already refuses org-wide cycles, and SC-5 exams are already
> class × subject — it writes the band scoped to the cycle's subject, and where a cycle carries
> several subjects (a term exam) it groups by `subject_id` and writes **one row per subject in one
> pass**. A term exam re-bands a child in every subject at once.

### 4.2 🔴 `apply_band_suggestions` re-bands a child off whatever test happened last

`_latest_pcts` (`assessments.py:224-249`) takes the student's **most recent cycle with scores**,
whatever it is — a Hindi slip test, a five-mark objective, a term exam — averages it, and offers
that as the suggested tier for a one-tap apply-to-all. A Tuesday slip test can move eleven children
between support tiers.

*(Same family as `S-114`, where slip tests and term exams pool into one average on three screens.)*

> ✅ **Decided — `D-76` / `S-183`: this route is deleted.** Re-banding happens on a test the teacher
> **chose** — a dedicated band test, or an ordinary one she promotes. There is then no reason to
> keep an implicit "whatever happened last" path, and every reason not to.

### 4.3 🔴 Every intervention task in every real school is created **unassigned**

`create_intervention` picks the assignee from `school_classes.class_teacher_member_id`
(`assessments.py:546-551`) — and **there is no UI anywhere that sets that field**
([`class-teacher.md`](class-teacher.md) §1, verified 2026-07-30; `createClass` doesn't send it and
`updateClass` doesn't exist).

So the founder's *"for every C band child there will be a teacher assigned, and it is her
responsibility"* is **already implemented, as a dead link**. The tasks are created, land on a board
with no assignee, and nobody is responsible.

### 4.4 🔴 An intervention can never be finished

`Intervention.status` allows `active|achieved|dropped`. There are exactly **two** intervention
endpoints — `POST /assessments/interventions` and `GET /assessments/students/{id}/interventions`
(`endpoints/assessments.py:249-271`). **Nothing updates the status.** No service method, no Lucy
tool, no UI.

Consequence, and it compounds: `recommendations._intervention_students` filters
`Intervention.status == 'active'` (`recommendations.py:102-107`), so **a goal that was achieved in
July keeps injecting a targeted daily check into the period card in March.** The one loop this
module exists to close — *the child moved to B, we're done* — is the one thing the schema allows
and the code cannot do.

### 4.5 🔴 Fourth instance of "built, wired into the client, called by nothing"

`schoolApi.studentInterventions` exists (`school-api.ts:415-416`) and **no component calls it**.
The report card shows the child's tier and the tier history and never shows the plan attached to
it. After `S-86` (per-student homework history), `S-74` (the cover picker and the timesheet) and
the fees defaulter list, this is number four.

### 4.6 · The intervention sheet asks a teacher to pick a task board

`InterventionSheet` (`assessments.tsx:90-118`) has a **Task board** dropdown listing every board in
the school. The school's internal data model, on the screen, in the middle of a conversation about
a child. Nobody setting up support for Kabir wants to choose a board.

### 4.7 · There is no standard to assess against

The founder's *"help doc of characteristics for each band"* has **no representation anywhere** —
not a table, not a column, not a seeded text. Today a tier means only *"scored below 50% on
whatever the last test was"*, which is why two teachers in the same school band the same child
differently and neither is wrong.

### 4.8 · The bands screen is a photograph of a distribution

`/students/bands` shows three columns of names and a count. It cannot answer *did anyone move*,
*who has been C for two terms*, *who owns this child*, or *what happened this week* — which are all
four of the questions the programme is actually about. It also renders for teachers
(`allow={["admin","teacher"]}`), read-only, with no notion of *which* children are theirs.

## 5 · Ideas and directions

### Decided — `D-67` … `D-74`

**`D-67` — bands are a programme with a lifecycle, and the measure is movement.**
Assess → group → assign an owner → work → re-assess → move. Not a label that gets stamped once.
The number the admin is shown first is *how many children moved*, never the distribution.

**`D-68` — the band is per subject.** English, Hindi and Maths to begin with; the monitored set is
**configuration**, so a school adds Science later without a code change.

**`D-69` — each band has a written descriptor, per subject** — the "help doc": *what a B child in
English can do*. It is the thing teachers assess against, and it is editable by the school.

**`D-70` — two routes into a band: the marks of an assessment, or the teacher's own observation
against the descriptors.** Both are first-class. Which one produced a row is recorded on it.

**`D-71` — every C child has an assigned teacher who owns moving them to B**, and she has one page
listing her children.

**`D-72` — the owner logs progress per child** — *"today we did this and that"* — and there is a
periodic evaluation where the child is re-assessed.

**`D-73` — the admin sees the programme by class and by subject**, with reports.

**`D-74` — Settings holds the rules:** which subjects are monitored, the descriptors, the
thresholds, and the assessment test and conditions **per band per subject**.

#### Second pass — the three answers

**`D-75` — the band is per subject, and there is no overall letter.** Closes `Q-71` at option (a).
A child is A in Maths and C in Hindi; nothing computes a blend. One chip reads **"C · Hindi"**.

**`D-76` — re-banding happens on a test: a dedicated band test, or any ordinary test the teacher
**promotes** to be band-deciding for that subject.** Closes `Q-74`. **Entry** into the programme may
still be teacher judgement against the descriptors (`D-70`) — in week two there is no test to read —
but **movement is always evidenced**, which is what `S-178` was reaching for procedurally.

**`D-77` — one owner per subject.** Closes `Q-72` at option (a). A child C in two subjects has two
owners and sits on two `/support` lists.

### Proposed — `S-164` … `S-188`

**`S-164` — the daily log will be dead by week three unless the page opens already written.**
This is the single biggest design risk in the module. A free textarea per child per day is a
compliance chore, and P3 says a capture surface must return something first. But §3.4 above shows
the child's day is *already captured* in five tables. So the owner's page should **open with the
week already filled in** — *"Mon: absent · Tue: needs work, Reading (Anil) · Wed: homework not done
· Thu: C-band check missed · Fri: —"* — and ask her for the one thing only she knows: what she
actually did with him. One line, optional, never a blocked save.

**`S-165` — make the weekly checkpoint the unit of the programme, and the daily note the
exception.** Four fields, once a week, per child: *what we worked on · what changed · what's next ·
ready to re-test?* Six children × 40 seconds = under five minutes, on a Friday. It is also the only
thing that produces the movement evidence `D-73`'s report needs. Daily notes stay available for the
day something happens, but nothing in the product ever asks for one.

> The founder said *"maybe weekly or sometime"*. Making that choice **now** decides whether this
> module is used in November (`Q-73`).

**`S-166` — the letter never appears without its descriptor.** Everywhere a tier renders for staff,
render the sentence: *"Band B — reads a grade-level passage aloud with ≤ 3 errors."* A letter alone
is a label, which is precisely what P4 says a band must not become — and the descriptor is also the
answer to the founder's *"each B band child should have this ability"*.

**`S-167` — the exit criterion is written when the child enters, not judged when the term ends.**
*"Moves to B when he reads 60 wpm with ≤ 3 errors, twice running."* Without it the owner is scored
on a judgement she also makes, and no child ever formally exits — which is `Q-74`, and is also
exactly the bug in §4.4 rendered as a process problem instead of a missing endpoint.

**`S-168` — the owner is per (child × subject), defaulting to the subject teacher of his class.**
"Assign a teacher to a C child" is ambiguous the moment a child is C in both English and Maths. One
owner for the child means one teacher answering for a subject she doesn't teach; per-subject means
Kabir has two owners and each knows exactly what hers is. *(Claude recommends per-subject —* `Q-72`
*decides it.)*

**`S-169` — the admin's report is the film, not the photograph.** Four rows, in this order:
*moved up this term* · *slipped* · **`stuck` — C for two terms with no movement** · *not yet
assessed*. The distribution donut goes under **More**. `stuck` is the only row that produces a
conversation.

**`S-170` — do not rank teachers by movement, and say so in the module.** The obvious next chart is
"which assigned teachers move the most children", and it is the `D-25` timesheet fence again: a
teacher whose support log can cost her an appraisal will write a support log that flatters her. The
children handed to the best teacher are, by construction, the hardest ones.

**`S-171` — the re-assessment is an exam that already exists.** `band_test` is already an
`assessment_cycles.type` (`models/assessments.py:57-58`) and `categorize_from_cycle` already
re-tiers a class from one. The programme should **schedule** a band test and read those rows — not
grow a second test surface. Exams (`D-49`–`D-55`) owns capture; bands owns what the marks *mean*.

**`S-172` — the programme should feed the daily check generator, not run beside it.** §3.3 already
turns a band into differentiated daily work. If the support programme grows its own "today's
activity for Kabir" list, a teacher sees the same instruction from two systems and trusts neither.
The intervention goal is *already* the text of the targeted check (`recommendations.py:151-157`).

**`S-173` — per-subject bands are a rewrite of the read path, not an added column.** Everything in
§4.1 changes, plus the directory chip, the class analytics donut
(`class-analytics.tsx:205`) and `growth.py:283`. And the **overall** letter should be *retired*,
not kept beside the per-subject ones — two definitions of "Kabir's band" is the defect this folder
has now found in five consecutive modules (`Q-71`).

**`S-174` — decide subject *or* skill, once.** `student_bands.scope_skill_area_id` points at
`skill_areas` (seeded Reading / Writing / Speaking / Math — `seed.py:322`), while subjects are
English / Mathematics / Science / Social Studies / Hindi (`seed.py:124`). Two overlapping
vocabularies, one unused. The founder said subject; then the skill scope should either be dropped
or explicitly reserved for the diagnostic radar it already drives (`Q-77`).

**`S-175` — ship starter descriptors; do not hand the school 27 empty boxes.** 3 subjects × 3 bands
is 9 texts; per grade it is 72 and none of them will be written. Seed an editable starter set the
way board templates are seeded (§5.5), and make **grade-group overrides optional** (`Q-76`).

**`S-176` — "time spent on support" needs no new capture.** `timesheet_entries.work_type =
'student_support'` already exists and is already in the seed (`seed.py:503`). It is currently
unlinked to a student; an optional student reference on that row turns the whole programme's effort
side on for one nullable column.

**`S-177` — a support group can be a `session`.** Where the school runs support as an actual
period, the hostel-sessions module already models exactly this: a picked set of students, an owning
teacher, a recurring slot, attendance, per-student sectioned notes, and media (HS-1/HS-2). A
remedial group is that, minus the hostel. Reuse it before building a second capture surface.

**`S-178` — the C→B move must be *evidenced*, not typed.** When the owner presses *Move to B*, the
sheet should show what it is standing on — the exit criterion from `S-167`, the last band test
percentage, the trend of weekly checkpoints — and the resulting `student_bands` row should carry
that as its `note`, the way `categorize_from_cycle` already writes *"band test: Term 1 Diagnostic"*.

**`S-179` — the A band needs a reason to exist, or this becomes a deficit ladder.** Today the
programme as described does nothing for A children and slightly less than nothing for B. If A means
only "not our problem", teachers will read the whole thing as remedial-only and the letter becomes
the label P4 forbids. Cheapest fix: the daily check generator already supports `band_scope='A'` —
give A children the *harder* version of the same topic, which costs nothing and changes what the
tier means (`Q-78`).

**`S-180` — 🔴 four fixes are needed before any of this is worth building**, and three of them are
small: an endpoint that closes an intervention (§4.4), the class-teacher assignment UI or a proper
owner column (§4.3), calling `studentInterventions` from the report card (§4.5), and subject-scoping
`apply_band_suggestions` so a slip test can't re-band a class (§4.2). The first one is not optional
— without it the module's core loop is unrepresentable.

**`S-181` — the parent gets "extra support", or nothing.** P4 permits nothing today and that is the
safe answer. But a child in a support programme whose family is never told is a real problem for
the school, and the founder should decide it deliberately rather than by omission. If anything is
ever said, it is *"Kabir is in extra reading practice with Ms Priya on Tuesdays"* — a fact about the
school's effort — and **never** a letter, a tier name, a count of C children, or a comparison
(`Q-75`).

#### Second pass — `S-182` … `S-188`

**`S-182` — promotion is a flag on the cycle, never a type change.** Re-typing a slip test to
`band_test` would remove it from the exam analytics that already count slip tests, so the school
would lose the test to gain the band. It is a separate mark recording **who promoted it and when**.
*(Build note: this lands in the same column region as `D-55`/`S-135`'s school-owned exam types —
do them in one migration or they will collide.)*

**`S-183` — 🔴 delete `apply_band_suggestions`.** With `D-76`'s explicit promotion, the implicit
route — re-band the class from *each child's most recent cycle, whatever it was* — is redundant
**and** is defect §4.2. Two paths to one outcome, and the unchosen one is the dangerous one.
`D-76` is what makes deleting it safe rather than a regression.

**`S-184` — a promoted test must be locked, and its size must be visible.** `D-53` gives an exam
verify-and-lock; an unverified transcription must not move a child between support tiers. Show the
total marks and how many sat it at the moment of promotion, and **warn, never block**, on a
five-mark test or a half-empty room — SF-1's leave-policy shape, because a validator that refuses a
legitimate case is a rule staff route around by hand.

**`S-185` — write the entry/movement split down as a rule**, or it will drift: *entry may be
judgement; movement is a test.* Both halves of `D-70` survive, in different phases.

**`S-186` — one chip reads "C · Hindi".** The consequence of retiring the overall letter. The
lowest band with the subject that earned it — never an average, never a bare letter.

**`S-187` — a promoted test re-bands one subject.** Promoting 7-A's Maths slip test moves Maths and
nothing else.

**`S-188` — every row about a stuck child names the subject.** With two owners possible, *"Kabir
Shah — owner Priya"* lets both of them assume the other is on it. *"Kabir Shah — Hindi, owner
Priya"* does not.

> ⚠️ *(verified)* **`D-76` changes a permission, and it is easy to miss.** Every band write is
> admin-only today (`require_coordinator_up` on `/bands` and `/bands/apply-suggestions`), and
> `ExamService.save` explicitly refuses a `band_test` from a non-admin (`services/exams.py:212`).
> *"It's up to her choice"* makes promotion a **teacher's** action. Either the promotion flag is
> deliberately teacher-allowed while the dedicated band test stays admin-only, or the feature ships
> and no teacher can use it. One guard, decided at step 3.

> **One thing gets better for free.** `_generate` already runs per class-subject, so per-subject
> bands mean the English period finally hands the easier route to the children who cannot read —
> instead of to whoever the blended letter happened to catch.

### Rejected

- **A distribution pie as the admin's headline** — REJECTED, ux §2 and `D-67`: it is a photograph of
  a decision already made, and it looks identical in a school where nobody has moved for a year.
- **A per-child daily photo of work** — REJECTED, P5: evidence is batch. The hostel-session
  exception was decided explicitly and does not extend here.
- **Ranking assigned teachers by children moved** — REJECTED, `S-170` (`D-25` precedent).
- **A separate "support test" surface** — REJECTED, `S-171`: exams owns capture.
- **Showing the tier to parents in any form** — REJECTED, P4, standing.

## 6 · Screens

| Screen | Role | Status | Arrives asking |
|---|---|---|---|
| `My support students` — `/support` | teacher (owner) | **NEW** | *"Who am I responsible for, and who needs me this week?"* |
| `Support child` — `/support/[studentId]` | teacher (owner) | **NEW** | *"What's happened with Kabir, and what do I do next?"* |
| `Bands` — `/students/bands` | admin | **CHANGING** | *"Is this programme working?"* |
| `Assess a class` — `/students/bands/[classId]` | admin + subject teacher | **CHANGING** | *"Which band is each child in, for this subject?"* |
| `Band setup` — `/setup/settings` → Bands | admin | **NEW** | *"What does B mean in my school?"* |
| `Use this as the band test` — on `/students/scores/exam/[cycleId]` | teacher | **NEW** | *"This slip test showed me what I needed — can it count?"* (`D-76`) |
| Period card, checks section | teacher | EXISTS | — *(already band-aware; §3.3, and gets more accurate under `D-75`)* |
| `/students/[id]` report card | staff | **CHANGING** | — *(gains the programme block; §4.5)* |

Detail in [`../screens/teacher.md`](../screens/teacher.md) and
[`../screens/admin.md`](../screens/admin.md).

## 7 · What we deliberately don't build

- **No parent-facing tier, ever** — P4, standing, restated because this module multiplies the
  places a letter could leak.
- **No IEP / diagnosis / special-needs clinical framing.** A band is a teaching group, not an
  assessment of a child. The moment a descriptor reads like a diagnosis, this is a different
  product with a different duty of care.
- **No ranking of teachers** (`S-170`), and no ranking of children — the tier is never a merit list
  and never sorts a class.
- **No test authoring** — SPRD2 §11, and `S-171`.
- **No per-student photo evidence** — P5.
- **No second daily-work generator** — `S-172`.

## 8 · Open questions

**Closed by the second pass:** `Q-71` → `D-75` · `Q-72` → `D-77` · `Q-74` → `D-76` · `Q-77`
effectively (a) via `D-75` · `Q-79` narrowed to the **entry** assessment only.

**Still open, none of them blocking:** `Q-73` 🔴 (daily log or weekly check-in — the one that
decides whether the module is still in use in November) · `Q-75` (does a parent ever hear
anything?) · `Q-76` (descriptors per grade?) · `Q-78` (what does band A get?) · `Q-80` (a promoted
test only some children sat) · `Q-81` (does a re-band show its moves before it commits — and
`student_bands` is append-only, so a mistake is permanent).
Full text in [`../open-questions.md`](../open-questions.md).

## 9 · Data implications

Short, because most of it exists.

```
student_bands                    EXISTS. Gains a SUBJECT scope (D-68/D-75) — the
                                 unused scope_skill_area_id stays where it is and
                                 stops pretending to be a band scope (Q-77) — plus
                                 a source ('test'|'observation', D-70) and the
                                 deciding cycle_id, so a row explains itself.
                                 There is NO overall row any more (D-75).

assessment_cycles.<promoted>     NEW, one nullable mark + who + when (S-182).
                                 NOT a change to `type` — re-typing a slip test
                                 deletes it from the exam analytics. Same column
                                 region as D-55/S-135's school-owned exam types:
                                 one migration, or they collide.

band_descriptors                 NEW, small. (subject × tier [× grade group?]) →
                                 text. Org-scoped, editable, seeded with a starter
                                 set (S-175). The "help doc" (D-69).

organizations.band_a_min/b_min   EXISTS but is ONE pair for the whole school.
                                 D-74 makes the rule per subject → the pair moves
                                 onto a per-subject config row, or the descriptor
                                 table carries it.

<monitored subjects>             D-68. A flag on the subject, not a new table.

interventions                    EXISTS — needs a SUBJECT + an OWNER, one row per
                                 (child × subject) (D-77), an exit criterion
                                 (S-167) and, above all, an endpoint that can set
                                 status='achieved' (S-180 🔴).

support_checkpoints              NEW, append-only (law 3). One row per
                                 (intervention × week): worked on · what changed ·
                                 next · ready-to-retest. This is S-165 and it is
                                 the only genuinely new capture in the module.

<the daily log>                  NOT a new table if S-164 holds: the day is read
                                 from lesson_observations + check_results +
                                 homework_results + attendance_exceptions +
                                 session_student_logs. A free note is one optional
                                 field on the checkpoint, or an entry beside it.

timesheet_entries.student_id     OPTIONAL nullable column (S-176) — turns the
                                 already-captured 'student_support' periods into
                                 the programme's effort figure.
```

**Two new tables, three nullable columns, one flag** — and one deletion (`S-183`). If this module
ends up with six tables it was designed as a new product instead of a pivot of the existing one.

## 10 · Build order — final

| Step | Migration | Contents |
|---|---|---|
| **0** | none | **The fixes, and they come first** (`S-180`): 🔴 the close-an-intervention endpoint · the owner assignment · call `studentInterventions` from the report card · **delete `apply_band_suggestions`** (`S-183`). Nothing below is honest until these land, and the first one is not optional — without it the module's core loop cannot be represented in a schema that already exists to represent it. |
| **1** | small | Descriptors, monitored subjects, per-subject thresholds (`D-69`, `D-68`, `D-74`) — the setup screen, seeded pre-written (`S-175`). Everything downstream renders **the sentence, not the letter** (`S-166`). |
| **2** | yes | **Per-subject bands** (`D-75`) — the read-path rewrite (`S-173`): `_current_tiers`, `current_band_map`, `band_board`, `recommendations._current_tier`, the directory chip (→ `"C · Hindi"`, `S-186`), the class-analytics donut and `growth.py`. Plus the assess-a-class screen with both entry routes (`D-70`). |
| **3** | small | **Promotion** (`D-76`): the flag on the cycle (`S-182`), *Use this as the band test* on the exam screen, locked-only with size shown (`S-184`), one subject (`S-187`), and the review step if `Q-81` says so. `categorize_from_cycle` writes per-subject rows. |
| **4** | small | The **owner per subject** (`D-77`) + the weekly check-in (`D-72`/`S-165`, pending `Q-73`) + `/support` and `/support/[studentId]`, **opening pre-filled** (`S-164`). |
| **5** | none | The admin's movement report (`D-73`/`S-169`), subject named on every stuck row (`S-188`), and the `/students/[id]` programme block. |
| **6** | none | `S-179`'s A-band checks, `S-176`'s effort figure, `S-177`'s support groups. |

Steps 0–2 are worth shipping on their own: they fix four live defects and make a band mean
something per subject, before anybody has to write a single check-in.
