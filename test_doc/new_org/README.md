# new_org — full setup walkthrough pack

Documents for testing the whole setup wizard on a **fresh organisation**, end to end,
including the new planner features (periods/week capture, whole-school timetable
generation, exam-gap fit, computed class week). Regenerate with
`cd api && uv run python ../test_doc/new_org/generate.py`.

## What to enter at each wizard step

| Step | What to do |
|---|---|
| 1 · Year | Label **2026-27**, `2026-06-15` → `2027-04-15`. Add terms **Term 1** (`2026-06-15` → `2026-10-31`) and **Term 2** (`2026-11-01` → `2027-04-15`). |
| 2 · Timings | Mon–Sat working, **8 periods/day**. (Capacity becomes 48 periods/week per class.) |
| 3 · Classes | **6-A, 6-B, 7-A** |
| 4 · Subjects | **English, Mathematics, Science, Social Studies, Hindi** |
| 5 · Teachers | Import **`teachers_staff.xlsx`** |
| 6 · Syllabus | Per class-subject: **`syllabus_maths_termwise.xlsx`** on each Mathematics, **`syllabus_science.xlsx`** on each Science, **`syllabus_generic.xlsx`** on English + Social Studies, paste **`syllabus_hindi.txt`** on Hindi |
| 7 · Calendar | Paint exams in the UI: e.g. **Term 1 Exam** `2026-09-21` → `2026-09-26`, **Term 2 Exam** `2027-03-08` → `2027-03-13`, plus a Diwali holiday week in Nov. Then set each exam's **portion** per subject — the **Exam fit** panel updates live as you do. |
| 8 · Students | Import **`students_roster.xlsx`** |
| 9 · Timetable | Tap **“Generate the whole school's timetable”** → preview → apply. |
| 10 · Generate | Check the **gap report** is clean, then *Generate every plan* → *Approve & lock*. |

## What each file should produce

**`teachers_staff.xlsx`** — 7 rows.
- 6 teachers created; assignments carry **periods/week** via the `x10` / `x9` suffixes.
- Every class ends up allocated **exactly 48 of 48** periods/week
  (Maths 10 · Science 10 · English 10 · Social 9 · Hindi 9) — check the
  "48 of 48 periods/week allocated" line on each class in the staff step.
- `Divya Nair`: her `9-C Astronomy x4` token comes back **unresolved** (no such
  class/subject); `7-A Hindi x9` still lands — so 7-A Hindi's teacher is Divya, and
  Farhan keeps 6-A/6-B Hindi.
- The nameless row lands in `errors`.

**`students_roster.xlsx`** — 33 rows → **created 31, errors 2**.
- 30 assigned across 6-A / 6-B / 7-A (10 each), each with father+mother guardian rows.
- `Zoya Ansari` names class 8-A → imports **unassigned**.
- One row missing a name, one missing an admission no → `errors`.

**`syllabus_maths_termwise.xlsx`** — 11 chapters / 24 topics with a **Term** column.
- Term 1 chapters are sized (≈52 periods); **Term 2 chapters have blank Periods** —
  they import as *unsized*, are never scheduled, and the generate step reports them.
  This is the correct term-wise state: size them when Term 2 begins
  (Plan → Syllabus → set periods → generate Term 2).

**`syllabus_science.xlsx`** — 11 chapters / 26 topics, fully sized (≈84 periods).

**`syllabus_generic.xlsx`** — 7 units / 21 topics (≈68 periods). Reusable on any
class-subject that needs a sized syllabus quickly.

**`syllabus_hindi.txt`** — paste path; trailing `(3)` becomes `est_periods = 3`.

## What to verify after setup (the new V2-P12 surfaces)

1. **Timetable** (Plan → Timetable): every class full 48/48, no teacher in two places
   at once. Suresh (Maths in all 3 classes) is the clash-pressure case.
2. **Exam fit** (Plan → Year, and in the wizard's calendar step): after portions are
   set, each subject shows *won't fit / manageable / perfect / spare time* with
   "needs Xp · has ~Yp". **Drag the Term 1 exam earlier** (delete + repaint a week
   earlier) and watch verdicts tighten; move it later and they relax.
3. **Class week** (Plan → Week plan): the day-by-day grid — subject + topic per
   period. Log a lesson from My Day, come back: that cell turns green (actual) and
   the projection shifts.
4. **Forecast** (Plan → Week plan): Maths shows the Term-2 chapters as unsized
   (`unplanned`) until you size them — never a false green.
5. **Gap report** (wizard step 10): should be clean with this pack. To see it fire,
   skip a syllabus import for one class or skip the timetable step.

## Deliberate failure rows (don't "fix" them)

Same philosophy as `../README.md`: each importer file carries rows meant to fail so
the `errors` / `unresolved` / unassigned surfaces get exercised, not just the happy path.
