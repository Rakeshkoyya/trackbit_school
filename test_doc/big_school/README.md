# Big-school setup pack — Sunrise International School

A **full-size** school to set up on a real database and then live in: classes 1–8
with 30 students each, 24 teachers split between primary and middle, the CBSE
subject spread, and a hostel. Everything is sized so that imports land 100% and
all 60 plans can be approved and locked.

|  |  |
|---|---|
| Classes | **8** (1–8, one section each) |
| Students | **240** — 30 per class · 66 hostellers |
| Teachers | **24** — 8 primary · 11 middle · 5 specialists |
| Subjects | **10** · **60** class-subjects |
| Syllabus | **818** chapters · **2,797** topics, every one sized |
| Week | Mon–Sat × 8 periods = **48** per class · **384** across the school |
| Year | 2026-27 (1 Jun 2026 → 10 Apr 2027), **live from Mon 20 Jul 2026** |

## Read these in order

| File | What it's for |
|---|---|
| **SETUP.md** | the click-by-click run — exact values, expected counts |
| **SCHOOL.md** | the reference sheet — staff, periods, calendar, fees, hostel (generated) |
| **VERIFY.md** | what to check afterwards, module by module |
| `data/` | the files you import |
| `generate.py` · `content.py` | how the pack is built |
| `validate.py` | proves the pack lands, without touching a database |

## The files

```
data/
  teachers_staff.xlsx                       -> wizard step 5   (24 rows, 60 assignments)
  students_roster.xlsx                      -> wizard step 8   (240 rows)
  syllabus/class_<n>/syllabus_<n>_<sub>.xlsx-> wizard step 6   (60 files)
  calendar_events.csv                       -> wizard step 7   (19 entries, typed by hand)
  fee_structures.csv                        -> Fees > Structures (8, typed by hand)
  hostel_sessions.csv                       -> Plan > Hostel     (6, typed by hand)
```

## Regenerating

```bash
cd api && uv run python ../test_doc/big_school/generate.py   # rewrites data/ + SCHOOL.md
cd api && uv run python ../test_doc/big_school/validate.py   # 27 checks, no DB needed
```

`validate.py` runs the pack back through the **real** importers
(`staff_import`, `roster_import`, `syllabus_import`) and asserts every assignment
resolves, every roster row would be accepted, all 60 syllabus files parse to the
chapters they were written with, and **zero topics are unsized**. It blanks
`OPENROUTER_API_KEY` first so the deterministic heuristic is what gets proven —
with a live key, `build_analysis` would make a model call per file.

The school is **fixed**, not random: SETUP.md quotes exact numbers, so they have
to stay true. Only student names and phones come from a seeded RNG
(`STUDENT_SEED = 20260727`).

## How this differs from `test_doc/new_org/`

They test different things and both are worth keeping.

| | `new_org` | `big_school` (this) |
|---|---|---|
| Purpose | fuzz the importers | run the product at real scale |
| School | different on every run | one fixed school |
| Size | 4 classes · ~54 students · 5 teachers | 8 classes · 240 students · 24 teachers |
| Content | sampled from a generic bank | NCERT chapter lists per grade |
| Terms | term-split syllabus | whole-year (see gaps below) |
| Adoption | year start | **mid-year**, `tracking_start_date` |
| Failure modes | `--messy` injects bad rows | none — this pack is meant to land |

## The four invariants

A fixture that imports at 99% teaches you nothing, so the generator refuses to
emit a pack that breaks any of these (`check_invariants`, then `validate.py`):

- **I1** every class's subject periods sum **exactly** to 48 → "48 of 48 allocated"
- **I2** every class-subject has exactly one teacher, heaviest load 22 of a
  possible 46 → the timetable is solvable with nobody double-booked
- **I3** every topic is sized → `approve` can lock all 60 plans
- **I4** each syllabus claims ~72% of the periods the **tracked** window offers →
  forecasts are green with visible slack, exam-fit reads *perfect* / *spare time*

## Design notes worth knowing

**Mid-year adoption is the point, not a shortcut.** The year opened 1 June; the
school goes live 20 July. That is how schools actually arrive, and it exercises
`tracking_start_date`: pre-adoption is *no data*, never a warning. Every syllabus
is sized against the ~169 teaching days left after go-live, not the full year.
The date sits deliberately just *behind* today — set it in the future and My Day,
the plan and the report all render empty.

**Topic counts flex with the timetable.** Class 7 Hindi has 19 chapters and 5
periods a week. Four sub-topics each would be 76 topics sharing 98 periods, and
the only way to write that down is to round every topic up — inventing periods
the year doesn't have. The generator drops to two fatter topics per chapter
instead. Honest, and closer to what a teacher logs.

**Usernames are pinned with a `sis.` prefix.** `users.username` is global across
every school in the database, so a plain `meena.iyer` might already be taken and
the importer would quietly hand out `meena.iyer2` — making SCHOOL.md wrong about
a login. The prefix removes the collision.

**Non-academic subjects carry a syllabus too.** Art & Craft and Physical
Education get light chapter plans. They hold 4 of every class's 48 periods; a
class-subject with no syllabus blocks plan generation with a named gap, so
leaving them out would mean either an incomplete week or a permanent gap report.

## Known gaps found while preparing this pack

Not blockers — the pack works around all of them — but each one costs the admin
time or reach:

1. **Terms have no UI.** `schoolApi.createTerm` exists in `web/src/lib/school-api.ts`
   and `POST /academics/terms` works, but no component calls it. Term-scoped
   planning (V2-P11 — per-term draft/approve/unapprove, `partial` status,
   per-term capacity) is therefore unreachable from the app. **This pack files
   every chapter under the year instead**, which is the supported `term_id = NULL`
   path. To test terms today you need `test_doc/new_org` plus a hand-created term.
2. **Working days have no UI.** `academic_years.working_weekdays` defaults to
   Mon–Sat, which happens to be right here. A Mon–Fri school can't say so.
3. **No calendar importer.** 19 events painted by hand — the one step that
   doesn't scale with school size. `data/calendar_events.csv` is the crib sheet.
4. **60 syllabus imports, one class-subject at a time.** Over half the setup
   time at this size. One file per class-subject is the shape the API takes
   (`syllabus_import.commit` is per `class_subject_id`).
5. **Staff import can't take a shared starting password.** The API has
   `default_password`; the wizard's commit doesn't send it, so 24 generated
   passwords are shown once and must be copied right then.

---

Built for the first production-database run, 23 July 2026.
