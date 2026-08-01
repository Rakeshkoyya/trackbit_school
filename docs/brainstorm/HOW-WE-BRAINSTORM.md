# How a brainstorm session runs

The ritual. Same shape every time, so that after eight sessions the folder reads as one document
instead of eight transcripts.

**Trigger:** the founder says *"let's brainstorm on \<module\>"* (or "brainstorm session", or
names a module and says they want to think about it rather than build it). That starts this
protocol. Nothing gets coded during a brainstorm session.

---

## The frame: UI/UX first, always

Every module is thought about as **a person, at a moment, with a question**. Not as tables, not
as endpoints. The data model gets a short section at the bottom of each module file, and it is
written last, after we know what has to be on the screen.

The four questions that open every module:

1. **Who is this for?** Which role — and *which version* of that role. A teacher at 9:02 with
   forty children in front of her is a different user from the same teacher at 4pm at her desk.
2. **What did they arrive asking?** In their words, not ours. *"Did my son do his homework?"*,
   not *"homework completion status"*.
3. **What do they leave having done?** The decision made, the action taken, the worry put down.
   If a screen has no answer here, it is a report, and reports do not need to be screens.
4. **What would they never forgive us for showing them?** Fee data to a teacher. A band to a
   parent. A red mark for a day nobody captured.

---

## The five steps of a session

### 1 · Ground it in what exists
Claude reads the actual code for the module first and writes down what is there **today**,
marked *(verified)* with file references. No brainstorm starts from an imagined baseline —
half of what gets "designed" in a session usually already exists, and the other half is broken
in a way nobody knew.

### 2 · Walk the roles
For each role that touches the module: the moment, the question, the decision. Out of this comes
a list of screens — which may be existing screens, changed screens, or new ones.

### 3 · Brainstorm freely
The founder talks, Claude proposes. Everything gets written down, including the ideas that get
rejected — a rejected idea recorded with its reason does not come back in session six.

**Claude's job here is to push, not to transcribe.** Specifically:
- offer at least two or three ideas the founder did not ask for, per module
- name the thing that will be wrong with an idea before it is built
- say when an idea belongs to a different module, or to no module
- say when something is already built and just needs to be reachable
- flag every fence, law or principle the idea crosses (see `ux-principles.md`)

### 4 · Write it down, in three places
| Artifact | Gets |
|---|---|
| `modules/<module>.md` | the thinking — needs, problems, ideas, what we won't build |
| `screens/<role>.md` | the visualization — each screen, block by block, in the order it appears |
| `decisions.md` / `open-questions.md` | anything settled, and anything that got stuck |

### 5 · Close with the blockers
Every session ends by naming the questions that must be answered before the next one, ordered by
how much they unblock. A session that ends without this leaves the next one starting cold.

---

## The three tags

Used in every file. They exist so that months later nobody has to guess whether a line was a
decision or a passing thought.

| Tag | Means | Owner |
|---|---|---|
| **`D-nn`** | **Decided.** Build to this. | founder |
| **`S-nn`** | **Suggestion.** Claude's, not yet accepted or rejected. | Claude |
| **`Q-nn`** | **Open question.** Blocks something. | founder |

Numbers are global and never reused. An accepted `S-nn` becomes a `D-nn` and the old line is
marked `→ D-nn`. A rejected one is marked `REJECTED — <reason>` and **kept**.

Anything describing current behaviour is marked *(verified)* and carries a file reference.
Everything else is intent.

---

## What a finished module looks like

When a module is done being brainstormed, a person who has never seen the product should be able
to read its module file plus its screen entries and **describe the screens out loud** — what is
on them, in what order, and what the user does next. If they can't, the module isn't finished.

Concretely, done means:

- [ ] every role that touches the module has its moment and question written down
- [ ] every screen has an entry in `screens/<role>.md` using the template
- [ ] every screen states what is deliberately **not** on it
- [ ] every screen has an empty state and a not-yet-captured state
- [ ] the decisions are in `decisions.md`, the blockers in `open-questions.md`
- [ ] the data-model sketch exists and is *short*

---

## Templates

- [`modules/_template.md`](modules/_template.md) — for a new module
- [`screens/_template.md`](screens/_template.md) — for a new screen

Copy them rather than improvising the structure; the value of this folder is that every file
answers the same questions in the same order.

---

## Module backlog

Tick as they are brainstormed. Order is the founder's call — this is just the surface area.

- [x] **Attendance** — session 1 (2026-07-30)
- [x] **Class teacher** — session 1, opened out of attendance
- [x] **Staff attendance / leave** — session 1, partially
- [x] **Payroll** — session 1, decisions only, blocked on `Q-05`–`Q-08`
- [x] **Syllabus coverage** — session 2 (2026-07-30)
- [x] **Teacher load** — the period module: timesheet, who is free. Session 3 (2026-07-31)
- [x] **Substitution / cover** — opened out of teacher load, session 3
- [x] **Homework** — session 4 (2026-07-31)
- [ ] **Students** — directory, profile, the report card *(next up: four sessions have added
      blocks to `/students/[id]` and nobody has designed the page)*
- [x] **Exams & scores** — session 6 (2026-08-01): types, capture (form + photo), the paper check,
      and the four analytic levels. **Bands were deliberately left out** (P4 — they are not a
      results concept; they got session 9). Second pass added **verify-and-lock** and the **future
      training corpus** (`D-53`–`D-55`) — the first data in the product whose purpose is not
      running the school
- [x] **Bands** — session 9 (2026-08-01), **two passes, FINALISED**: the A/B/C **support
      programme** — per-subject bands with no overall letter, written descriptors as the standard,
      one owner **per subject** who owns moving a C child to B, her weekly check-in, and the
      admin's movement report. Re-banding happens on a test — including an ordinary CET or slip
      test the teacher **promotes**. Found that an intervention **cannot be finished** and that its
      owner has never once been set
- [x] **Events & dates** — session 7 (2026-08-01), **two passes**: birthdays, the school's own
      calendar, and festivals/observances. The second pass reframed it — the calendar is a
      **stream of suggestions** and **approval is the commit**, with three lock levels that turned
      out to already exist in the schema. Found a live defect where recording a celebration
      shrinks the teaching year, which the approval sheet fixes as a side effect
- [ ] **Planner** — the year, terms, plan generation, approval *(coverage was session 2)*
- [ ] **Timetable**
- [ ] **Sessions / hostel**
- [x] **Tasks** — session 5 (2026-07-31): the Follow-ups board + the My Day section only; the
      module's internals were not reopened
- [x] **Fees** — session 8 (2026-08-01): the admin's collection board (quarter-wise, by class,
      by student), remind + assign, and the parent's reminder. The collection *system* was
      already built; found the defaulter list computed on the server and called by nothing,
      and a fence collision between "only admin sees fees" and "assign a teacher to follow up"
- [x] **Parent access** — login + notification delivery, session 2
- [ ] **Parent portal** — the rest of it as a product in its own right
- [ ] **Admin dashboard** — after its feeder modules are settled
- [ ] **Setup & onboarding wizard**
- [ ] **Lucy**
- [ ] **Notifications** — the whole message surface, across modules

Two of these are best left until last: the **admin dashboard** and **notifications**. Both are
downstream of everything else — the dashboard shows what the modules capture, and every
notification is a module's event. Brainstorming them early means redoing them.
