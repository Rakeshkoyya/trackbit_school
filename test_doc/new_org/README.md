# new_org — full setup walkthrough (classes 5 · 6 · 7)

Clean mock data for testing the whole academic-planner setup on a **fresh organisation**.
Every row is valid — imports should land 100%, and the final generate step should lock
every plan. Regenerate files with `cd api && uv run python ../test_doc/new_org/generate.py`.

**The school this pack describes:**
- 3 classes — **5, 6, 7** (leave Section blank everywhere)
- 6 subjects — **Mathematics, Science, English, Social Studies, Hindi, IT**
- 5 teachers — **Anil Kumar teaches two subjects** (Math + Science on class 5)
- 10 students per class (30 total)
- Every class's week is exactly full: 9+9+8+8+7+7 = **48 of 48 periods**

---

## Step-by-step: what to do and what to decide

### Step 1 — Academic year
Label **2026-27**, from **2026-06-15** to **2027-04-15**.
Add both terms (the syllabus files reference them by name — spell them exactly):
- **Term 1** — 2026-06-15 → 2026-10-31
- **Term 2** — 2026-11-01 → 2027-04-15

### Step 2 — School timings
Working days **Mon–Sat**, **8 periods/day**.
*Decision:* this fixes each class's weekly capacity at 48 — the staff file's `x` numbers
are built to sum to exactly that.

### Step 3 — Classes
Add **5**, **6**, **7**. Leave the section field **blank** (one section per grade, so no
A/B duplication).

### Step 4 — Subjects
Add all six: **Mathematics, Science, English, Social Studies, Hindi, IT**
(spell them exactly — the staff file's assignments resolve by name).

### Step 5 — Teachers & assignments
Import **`teachers_staff.xlsx`** → 5 accounts, 18 assignments, zero errors.
- ⚠️ **Write down the generated passwords** shown after import — you'll want them to log
  in as a teacher later (e.g. to see My Day).
- Check each class's panel now reads **“48 of 48 periods/week allocated”**. That's the
  `x9`/`x8`/`x7` suffixes doing their job.
- Anil Kumar should show on both 5-Mathematics and 5-Science.

### Step 6 — Syllabus (the shortcut matters)
Only import onto **class 5**, then copy:
1. On class **5**, import each file onto its subject:
   `syllabus_mathematics.xlsx` · `syllabus_science.xlsx` · `syllabus_english.xlsx` ·
   `syllabus_social_studies.xlsx` · `syllabus_hindi.xlsx` · `syllabus_it.xlsx`
   (each shows a draft first — chapters split into Term 1/Term 2, every topic sized —
   then *Save to this subject*).
2. Go back to **Teachers & assignments**, open class **6**'s subject panel, and use
   **“Same as another section? Copy from 5”** → copies all six subjects' syllabus in one
   click. Repeat for class **7**.
3. Back on the Syllabus step, re-select any class+subject — the saved chapters now show
   right there, editable (change a period count, delete a topic) without re-importing.

*Decision:* real grades have different syllabi; reusing one file per subject across
5/6/7 is a mock-data convenience.

### Step 7 — Calendar, holidays & exams (all in the UI)
Paint on the calendar:
- **Term 1 Exam** — 2026-09-21 → 2026-09-26
- **Term 2 Exam** — 2027-03-08 → 2027-03-13
- A **Diwali holiday** week, e.g. 2026-11-09 → 2026-11-14
- Any other holidays you like — watch **teaching days** recompute.

Then set **exam portions** per class: for the Term 1 exam pick roughly the last Term-1
chapter of each subject ("up to *Integers*" for Maths, "up to *Changes Around Us*" for
Science, …); for Term 2 pick the final chapter.

**Watch the Exam fit panel** below the calendar: every subject should read *perfect* or
*spare time* with real numbers ("needs 42p · has ~126p"). Now **delete the Term 1 exam
and repaint it 6–8 weeks earlier** — verdicts flip toward *manageable / won't fit*.
That's the guidance loop you asked for. Repaint it back when done.

### Step 8 — Students
Import **`students_roster.xlsx`** → **created 30, skipped 0, errors 0**.
Check the **Students page**: table view with class column; filter by class 5/6/7;
click a row → **Edit details** → change a roll number → Save.

### Step 9 — Timetable
Tap **“Generate the whole school's timetable”** → preview should say
**144 periods across 3 classes** with *every subject placed cleanly* (no teacher
double-booked — Priya carries 45/48 periods, the tightest load). Apply.
Open a class grid and spot-check: no two classes share a teacher in the same period.

### Step 10 — Generate & lock
- The gap report should be **empty** (button enabled). To see the blocking work, try
  this first: delete one subject's syllabus (Syllabus step → trash a chapter set) and
  come back — generation is blocked with a named gap. Restore it (re-import/copy).
- **Generate every plan** → all 18 subjects come back **clean** (fits, in order,
  before their exams).
- **Approve & lock 18 plans** → done screen.

---

## After setup — what to verify

1. **Plan → Week plan**: pick a class → the **class week grid** shows every period with
   its topic. Navigate weeks; future weeks show the projected syllabus.
2. **Plan → Year**: exam fit panel + calendar live here permanently.
3. **Log in as a teacher** (e.g. Priya's generated password): **My Day** shows her
   periods from the generated timetable; take attendance on one period, log the topic.
   Return to Plan → Week plan as admin — that cell is now green (actual).
4. **Plan → Classes**: every subject **on track** (green), none `unallocated`/`not sized`.
5. **Students**: filter, search, edit — and open a student to see today's timeline after
   some attendance exists.

## Files

| File | Where | Expect |
|---|---|---|
| `teachers_staff.xlsx` | Setup wizard → Teachers | 5 created · 18 assignments · 48/48 per class |
| `students_roster.xlsx` | Wizard → Students (or Students → Import) | 30 created, 0 errors |
| `syllabus_mathematics.xlsx` | Syllabus → class 5 → Mathematics | 11 ch · 24 topics · 85p, termed |
| `syllabus_science.xlsx` | Syllabus → class 5 → Science | 11 ch · 26 topics · 82p |
| `syllabus_english.xlsx` | Syllabus → class 5 → English | 10 ch · 20 topics · 70p |
| `syllabus_social_studies.xlsx` | Syllabus → class 5 → Social Studies | 11 ch · 22 topics · 72p |
| `syllabus_hindi.xlsx` | Syllabus → class 5 → Hindi | 10 ch · 20 topics · 62p |
| `syllabus_it.xlsx` | Syllabus → class 5 → IT | 9 ch · 18 topics · 60p |

Classes 6 and 7 get their syllabus via **Copy from 5** (one click each).
