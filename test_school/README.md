# Green Valley — sample school for testing setup

One coherent school. Every file lines up with the same set, so the imports resolve
against each other:

- **Classes:** 6-A, 6-B, 7-A
- **Subjects:** Mathematics, Science, English, Social Studies, Hindi
- **Year:** 2026-27 (1 Apr 2026 – 31 Mar 2027), Mon–Sat, 8 periods/day

Regenerate any time: `cd api && uv run python ../test_school/generate.py`

## Do this first (in the wizard), or the uploads won't resolve

The importers match names against data that already exists. Set these up **before**
uploading anything:

1. **Year** — 2026-27, start 2026-04-01, end 2027-03-31.
2. **Timings** — 8 periods/day (the timetable references assume 8).
3. **Classes** — add three: `6 / A`, `6 / B`, `7 / A` (one row per section).
4. **Subjects** — add all five: Mathematics, Science, English, Social Studies, Hindi.
   Use these exact names (they're on the wizard's suggested chips).

Then the upload steps below will match classes and subjects by name.

## What to upload, and where

| Wizard step | File | What it does |
|---|---|---|
| **Teachers** | `teachers.xlsx` | Creates 6 teachers and wires each to their class-subjects |
| **Syllabus** | `syllabus/class<N>_<subject>.xlsx` | Pick the class + subject, then upload its file |
| **Students** | `students.xlsx` | 45 students across 6-A, 6-B, 7-A with guardians |
| **Timetable** | see note below | The app **ignores** the file — read on |

### teachers.xlsx (6 rows)

Columns: `Name, Username, Email, Phone, Assignments`. The `Assignments` column is what
gets wired up — e.g. `6-A Mathematics; 6-B Mathematics`. Every assignment here matches a
class + subject you created, so all 15 class-subjects end up covered:

- Sunita Rao → 6-A, 6-B Mathematics
- Deepak Iyer → 7-A Mathematics, 7-A Science
- Vikram Nair → 6-A, 6-B Science
- Lakshmi Menon → English (all three)
- Rahul Verma → Social Studies (all three)
- Anjali Gupta → Hindi (all three)

Each teacher gets a generated password shown once on import — copy them.

### syllabus/ (one file per class-subject)

The syllabus step is **per class-subject**: choose the class, choose the subject, then
upload. Files are named `class6_science.xlsx`, `class7_mathematics.xlsx`, etc. Class-6
files fit both 6-A and 6-B (same content). Formats vary on purpose so you can exercise
each path:

- Most are **grid** sheets: `Chapter, Topic, Periods` (blank Chapter continues the one above).
- `class6_english.txt` is **free text** — paste it into the text box, or upload the file.
- `class6_mathematics_TERMWISE.xlsx` is **optional/advanced** (see below).

### students.xlsx (45 rows)

Columns: `Admission No, Student Name, Roll No, Class, Section, Category, Father Name,
Father Mobile, Mother Name, Mother Mobile`. Admission numbers `GV2601…` are unique;
categories are Day Scholar / Hosteller / RTE. Class + Section match your three classes,
so everyone lands assigned.

## Timetable — read this

`timetable/class6A_timetable.xlsx` etc. are **reference sheets only**. The current build's
timetable import **does not read the uploaded file** — it auto-fills the weekly grid from
each class's subjects and their periods/week, then you confirm/drag in the grid. So:

- To test the timetable, just click **Import / draft** on Plan → Timetable for a class and
  confirm the auto-filled grid. No file needed.
- These sheets show a plausible Mon–Sat × 8-period layout for eyeballing / hand-entry, and
  are the shape a real AI-parse would target if that gets enabled later.

## Optional: term-wise syllabus

`syllabus/class6_mathematics_TERMWISE.xlsx` has a `Term` column and leaves **Term 2 unsized**
(no period counts) — the case the term-wise planning feature is built for. It only resolves
the Term column if **Term 1 and Term 2 exist** for the year; without them, those chapters
import untermed (still fine, just not split by term). There's no term-creation step in the
wizard yet, so treat this file as an extra once terms exist.
