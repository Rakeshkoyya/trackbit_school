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

### Step 6 — Syllabus (18 imports — one file per class per subject)
Each class has its own grade-appropriate syllabus. On the Syllabus step, pick the class,
pick the subject, import its file, review the draft (chapters split into Term 1/Term 2,
every topic sized), then *Save to this subject*. The naming says exactly where each file
goes: **`syllabus_<class>_<subject>.xlsx`** — e.g. `syllabus_5_mathematics.xlsx` → class
**5** → **Mathematics**, `syllabus_7_it.xlsx` → class **7** → **IT**.

Work class by class (6 files for class 5, then 6, then 7). After saving, re-select any
class+subject — the saved chapters show right there, editable (change a period count,
delete a topic) without re-importing.

*Note:* the “Copy from…” control in the subject panel is for true sibling **sections**
(6-A → 6-B). Don't use it across grades here — each grade has its own files.

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
| `syllabus_5_*.xlsx` (6 files) | Syllabus → class 5 → matching subject | class-5 chapters, 56–80p each, termed |
| `syllabus_6_*.xlsx` (6 files) | Syllabus → class 6 → matching subject | class-6 chapters, 60–85p each, termed |
| `syllabus_7_*.xlsx` (6 files) | Syllabus → class 7 → matching subject | class-7 chapters, 62–88p each, termed |

All 18 syllabus files follow `syllabus_<class>_<subject>.xlsx`; every topic is sized, so
the final generate step should lock all 18 plans cleanly.
