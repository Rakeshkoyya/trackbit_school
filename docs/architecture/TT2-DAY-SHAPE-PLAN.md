# TT-2 — the day shape: editable timings, typed periods

**Status:** building · **Started** 2026-08-10 · Extends V2-M3 (timetable) and HS-1/HS-2
(sessions). Supersedes nothing.

## §0 — read this first

Today the school day is two half-facts in two places:

- **when** — `academic_years.period_times`, a JSONB list of `{start, end, kind}` synthesised
  at setup from four numbers. One schedule per year, every weekday, **no editor anywhere in
  the app** (the admin can change `periods_per_day` and nothing else).
- **what** — `timetable_slots`, one cell per `(class_id, weekday, period_no)` pointing at a
  `class_subject_id` that is **NOT NULL**. So a cell can only ever be a subject.

Neither can express the founder's actual school:

> 8:00–2:00 classes for everyone · 30-min break · 3:30 homework class (hostellers only) ·
> 4:30 AI class · 6:00–7:00 sports. Assembly and yoga are taken by whichever teacher is free.

TT-2 makes the day shape a first-class, admin-editable thing: **the bell schedule says when,
the slot says what, and the slot's kind decides what the teacher is asked to capture.**

**Setup does not change.** The pack still carries `p1, p2, p3…` and their subjects. Everything
below is configured after handover, from the admin UI.

## §1 — the four decisions

- **`D-112` — the non-subject block is a `Session`.** Sessions already own attendance, per-
  student logs, R2 photo/video, a computed roster (classes ∪ students, hosteller filter) and a
  teacher UI. Building a second entity would duplicate four tables and ~600 lines of tested
  service code. `sessions` is therefore promoted from "hostel evening block" to **the
  non-subject block**, and its `kind` widens to the capture vocabulary.
- **`D-113` — the timetable is the only schedule.** A session referenced by a live timetable
  slot is *scheduled*; its own `weekdays` / `time` / `end_time` become **derived and
  read-only**, and the service rejects writes to them. A session with no slots keeps the
  standalone weekday/time path, so existing hostel sessions keep working untouched. One
  question — "when does AI class happen" — one answer.
- **`D-114` — typed slots follow the timetable's tier (free).** `PLAN_TIMETABLE` is free
  because per-period attendance cannot resolve a class without it. The same reasoning holds
  for a sports period. Per `D-107` (free buys the act of recording, paid buys the record over
  time) the split is: **scheduling a block and capturing it is free; the hostel week planner
  and the records board stay `SESSIONS_HOSTEL` (max).**
- **`D-115` — the bell schedule is effective-dated.** Founder call: *"after the term 1 exams
  admin can decide to introduce new classes and change the timetable structure."* A single
  JSONB on the year would silently re-render September's day-book and timesheets with
  October's times. So the bell schedule becomes a table with `[effective_from, effective_to)`,
  exactly like `timetable_slots` — and for the same reason (Law 3).

## §2 — the model

### 2.1 `bell_schedules` (new)

One row = the shape of the school day, valid over a date range.

| column | notes |
|---|---|
| `org_id`, `academic_year_id` | |
| `effective_from` Date NOT NULL / `effective_to` Date NULL | NULL = current, like slots |
| `periods_per_day` Int NOT NULL | derived from the entries; stored so a school with no timings still renders |
| `entries` JSONB NOT NULL | `[{start, end, kind, label}]` in wall-clock order |
| `note` Text NULL | "after Term 1 exams" — why the day changed |

`academic_years.period_times` / `periods_per_day` are **backfilled into row 1 and then no
longer read.** They stay in the table (additive-only rule) as dead columns.

The numbering rule is unchanged and stays load-bearing:

> `period_no` = the 1-based index among entries whose `kind == 'period'`

so adding a 3:30 homework block makes it period 9, and breaks still consume no number. That
keeps `class_periods`, `timesheet_entries`, `period_substitutions` and `blocks_periods` all
valid without a data migration.

`entries[].label` is new — "Short break", "Lunch", "Games" — so the timesheet can name a gap
instead of title-casing its kind.

### 2.2 `timetable_slots` (changed)

| column | change |
|---|---|
| `slot_type` Text NOT NULL server_default `'subject'` | `subject` \| `block` |
| `class_subject_id` | **NOT NULL → nullable** |
| `session_id` UUID FK sessions SET NULL | new, nullable |

`CHECK`: `slot_type='subject' AND class_subject_id IS NOT NULL` **or**
`slot_type='block' AND session_id IS NOT NULL`.

The *flavour* of a block is `sessions.kind`, never a second column — one type store.

### 2.3 `sessions` (changed)

- `kind` CHECK widens: `study | homework | activity` → **`+ sports | assembly | course`**.
- **`session_staff`** (new): `org_id`, `session_id`, `member_id`, unique `(session_id,
  member_id)`. Any staff member on the list can open the meeting, mark it and post memories —
  which is the whole point for assembly, yoga and the homework class. `owner_member_id`
  remains, as the person accountable for it.
- `session_meetings.note` (new, nullable) — the block's **class log**, the thing an extra
  course needs that a study session never did.

### 2.4 `core/day_shape.py` (new vocabulary module)

Per the `core/` convention — one computation, many renderings. Owns the block kinds and, for
each, **what the teacher is asked for**:

| kind | label | roll | class log | memories | homework check | school roll |
|---|---|---|---|---|---|---|
| `study` | Study / prep | ✓ | — | ✓ | — | — |
| `homework` | Homework class | ✓ | — | ✓ | **✓** | — |
| `sports` | Sports | ✓ | — | ✓ | — | — |
| `activity` | Activity | ✓ | ✓ | ✓ | — | — |
| `course` | Extra course | ✓ | ✓ | ✓ | — | — |
| `assembly` | Assembly / yoga | — | — | ✓ | — | **✓** (TT-6) |

`roll` and `school_roll` are opposite claims and no kind has both: `roll` is the block's own
second list, filed to its meeting; `school_roll` is the school-day register, filed to each
class. See §6.

Nothing else may branch on a kind string. `web/src/lib/day-shape.ts` mirrors it.

## §3 — the homework class, precisely

The founder's ask: *class tabs → subject tabs → the homework given shows in a card → the list
of students below with done / not-done, plus a photo or note per student.*

- Class and subject tabs reuse the existing `ClassSubjectPicker` (two pill rows), narrowed to
  the classes actually present in the block's roster.
- The card is the `HomeworkAssignment` for that class-subject open on the meeting date —
  `_homework_map`'s existing "open tonight" rule.
- The student list writes to **`homework_results`**, the canonical store behind
  `core/homework_verdict.py`, the parent portal and every insight. Not to a second store.
- **Default is `not_checked`, not `not_done`.** `not_checked` is already a real state — worth
  nothing, outside the denominator, rendered as a word and never as a red zero. It means what
  the founder asked for (nothing is claimed done until the teacher has seen the book) without
  requiring a tap per child to reach the normal case, which P1v2 forbids. `done` and
  `not_done` are both one tap from there.
- The per-student **note** uses `homework_results.note`, a column that has existed since HW-1
  and that no UI has ever written.
- The per-student **photo** lands in `session_media` with `student_id` set. This is inside the
  decided fence exception (hostel session media), not a new one — which is exactly why the
  photo belongs to the *block's meeting* and not to the homework assignment.

## §4 — build order

| # | packet | what |
|---|---|---|
| P0 | bell schedule | model + migration + `services/bell.py` resolver + `school_clock` labels; every `period_times` reader moves to the resolver |
| P1 | typed slots | slot columns + CHECK, `session_staff`, widened kind, `core/day_shape.py`, clash check over staff |
| P2 | admin UI | the timings editor (add/remove/reorder rows, name breaks, effective-from + history) and the typed cell editor |
| P3 | My Day | `teacher_day` includes staffed blocks; period rows carry kind + clock and route by kind |
| P4 | capture | homework class · sports · activity/course · assembly |
| P5 | downstream | compliance, day book, timesheet, substitution, marking periods, daily report must not read a block as an unmarked subject period |
| P6 | green bar | pytest · ruff · tsc · eslint · next build · docs |

## §5 — what this does NOT do

No solver (§11 stands — the generator still reports what it cannot place). No per-weekday bell
schedules; one shape at a time, changeable whenever the admin likes, with history. No parent-
facing surface for any of it. No mandatory per-student capture in any new screen.


## §6 — TT-6: assembly takes the school register (2026-08-18)

Founder: *"if I added assembly in my timetable at first period and I want to take attendance of
that whole school that are in assembly, it should reflect in each class."*

TT-2 gave assembly `roll=False` on the reasoning that nobody takes a roll at assembly and asking
for one would be the mandatory per-student capture P1v2 forbids. The second half of that is
still true; the first half was wrong about the school. Assembly is the one moment in the day
when **every child is standing in one place in front of one person**, which makes it the
cheapest register the school will ever take — not an extra one.

So `assembly` gains **`school_roll`**, and it is a different claim from `roll`:

| | `roll` | `school_roll` |
|---|---|---|
| whose list | the block's own roster | every class the block holds on the grid |
| filed to | `session_attendance` (the meeting) | `class_periods` — **one register per class** |
| means | "who came to games" | "who was in school today" |
| `D-91` | a child present at 08:20 can still miss the 18:00 game | this **is** the 08:20 register |

What that buys, and why it is a fan-out rather than a new store:

- **the write is the ordinary `mark`, once per class.** Everything that makes attendance
  correct — the once-a-day redirect, the reasons that survive a re-mark, the guardian alert on
  the day's first marked period — is written once and would have to be written twice if the
  hall's register were its own row. Same shape as TT-4's combined roll call, same reason;
- **nothing downstream learns a new word.** The month register, the report card, the parent's
  Today and the daily report keep reading one class at a time and never hear about assembly;
- **the period comes from the grid.** "Assembly is at period 1" is said in the timetable and
  nowhere else, so moving it moves the register with it. A block that is not on today's grid
  has no period to file against and refuses — a state, not a fault;
- **the door is the block, not the class.** The warden who takes assembly teaches almost none
  of the school, so `assert_can_take_class` would refuse her. `assert_may_take_block` admits
  her instead, and the classes she can reach are only the ones the grid puts in the hall at
  that period — never a list she names, or `session_id` would be a skeleton key into every
  register in the school. `tests/test_assembly_register.py` asserts both halves;
- **still capture-by-exception.** The sheet opens on "everyone is here" and costs the taps of
  the children who are away. A school of 400 costs six taps, not 400 (P1v2);
- **half a hall is not done.** `marked` is an ALL over the room, on the sheet and on My Day: a
  hall with one class still unmarked has not had its roll taken, and a green row there would
  lose a class's day quietly.

Surfaces: `GET|POST /attendance/assembly` · the **School register** section on the block
capture screen · the My Day assembly row, which carries the hall's counts and is the one block
row that is **not** optional. **No migration** — `school_roll` is a property of a kind, and the
registers it writes are the rows attendance has always written.
