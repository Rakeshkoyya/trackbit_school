# Setting up Sunrise International School

The click-by-click run. Every value below is exact — type it as written, because
the importers resolve classes and subjects **by name**. Numbers in the *Expect*
lines are what the screen should say; anything else is a finding worth writing
down.

Reference tables (staff, calendar, fees, hostel) live in **SCHOOL.md**.
Files live in **`data/`**.

Budget roughly **60–90 minutes**. Step 6 (60 syllabus imports) is over half of it.

---

## 0. Create the school — super-admin

Schools do not self-onboard (V3-P0). Log in as the platform operator, then:

1. **`super@trackbit.app`** → lands on **`/platform`**.
2. **New school** →
   - School name: `Sunrise International School`
   - Admin name: `Vikram Rathore`
   - Admin email: `principal@sunriseintl.edu.in`
3. Copy the handover credentials it shows — **that panel is the only place the
   temp password appears.** The admin is forced to change it at first login.
4. **Enter & set up** → you are now inside the org as an admin.

> If `ALLOW_PUBLIC_ORG_SIGNUP` is still `True` on this deployment, note it: in
> production it should be `False`, and the login page should have no register link.

Then open **Setup → Wizard**.

---

## 1. Academic year

| Field | Value |
|---|---|
| Name | `2026-27` |
| First day | `2026-06-01` |
| Last day | `2027-04-10` |

**Expect:** the year calendar on the right fills in; the year becomes active.

### 1b. Tracking start — leave the wizard for a moment

The wizard has no field for this. Go to **Setup → Academics**, find `2026-27`,
and set **tracking from** = **`2026-07-20`**.

This is the school adopting the product mid-year: the session opened on 1 June,
but nothing was captured until 20 July. Everything before that date is *no data*,
never a warning — no seven weeks of "missing attendance", and the planner sizes
the year from the go-live date. Come back to the wizard afterwards.

**Expect:** the year row now reads *tracking from 2026-07-20*.

> The date is deliberately just **behind** today. Set it in the future and My Day,
> the plan and the daily report all have nothing to show — which looks like a
> broken product rather than a school that starts on Monday. If you run this setup
> much later than July 2026, move it to the Monday before you start.

---

## 2. School timings

| Field | Value |
|---|---|
| Day starts at | `08:00` |
| Periods per day | `8` |
| Minutes per period | `40` |
| Lunch after period | `5` |
| Lunch minutes | `40` |

**Expect:** the preview shows P1 08:00–08:40 … P5 10:40–11:20, **Lunch**
11:20–12:00, P6 12:00–12:40 … P8 13:20–14:00. Weekly capacity is now
**48 periods** per class (Mon–Sat × 8).

> Working days are **not** on any screen — `academic_years.working_weekdays`
> defaults to Mon–Sat, which is what this school runs. Nothing to do.

---

## 3. Classes

Add eight, pressing enter between each. **Leave Section blank every time** —
one section per grade, so no A/B duplication.

`1` · `2` · `3` · `4` · `5` · `6` · `7` · `8`

**Expect:** 8 chips in the aside.

---

## 4. Subjects

Add all ten, spelled exactly:

`English` · `Hindi` · `Mathematics` · `EVS` · `Science` · `Social Studies` ·
`Sanskrit` · `Computer Science` · `Art & Craft` · `Physical Education`

**Expect:** 10 subjects. Not every class runs every subject — classes 1–4 take
EVS and Art & Craft, classes 5–8 take Science, Social Studies and Sanskrit. The
staff sheet in step 5 is what wires each subject to the right classes.

---

## 5. Teachers & assignments

Import **`data/teachers_staff.xlsx`**.

**Expect:** *24 teachers added · 60 assignments made*, **no** unresolved warning.

> ⚠️ **Copy the password list now.** It is shown once and never again. Each
> teacher's username is pinned in the sheet (`sis.meena.iyer` and so on) —
> the `sis.` prefix is there because `users.username` is global across every
> school in the database, so an unprefixed `meena.iyer` could already be taken
> and the importer would silently hand out `meena.iyer2`.
>
> The API supports a `default_password` for exactly this situation; the wizard
> doesn't offer it. Worth noting if you'd rather hand every teacher the same
> starting password.

Scroll to **Who teaches what**:

**Expect:** every class reads **"48 of 48 periods/week allocated"**. Spot-check
class 8 — English 7, Hindi 5, Sanskrit 4, Mathematics 9, Science 9,
Social Studies 7, Computer Science 4, Physical Education 3.

---

## 6. Syllabus — 60 imports

The long step. One file per class-subject; the filename says exactly where it
goes: **`data/syllabus/class_<n>/syllabus_<n>_<subject>.xlsx`**.

For each of the 8 classes, for each of its subjects:

1. Pick the class, pick the subject.
2. Import the matching file.
3. Review the draft — chapters with their topics, **every topic sized**.
4. *Save to this subject.*

**Expect per file:** the chapter count in the table below, **0 unsized topics**,
and no "unresolved term" warning (this pack files chapters under the year, not
under terms — see *Known gaps* in README.md).

| Class | Files | Chapters | Topics |
|---|---|---|---|
| 1 | 7 | 90 | 320 |
| 2 | 7 | 87 | 308 |
| 3 | 7 | 90 | 317 |
| 4 | 7 | 91 | 320 |
| 5 | 8 | 104 | 368 |
| 6 | 8 | 118 | 403 |
| 7 | 8 | 119 | 387 |
| 8 | 8 | 119 | 374 |
| **All** | **60** | **818** | **2797** |

> Don't use **Copy from…** here. It's for true sibling *sections* (6-A → 6-B);
> this school has one section per grade and each grade has its own files.

---

## 7. Calendar, holidays & exams

19 entries, painted by hand — there is no calendar importer.
Copy from **`data/calendar_events.csv`** or the table in **SCHOOL.md**.

Kinds to use: **Holiday** (13) · **Exam** (4) · **Celebration** (2 — Teachers'
Day, Annual Day) · **Event** (1 — Annual Sports Day).

Two of the four exam blocks are **partial days** — Unit Test 1 and Unit Test 2
eat **periods 1, 2, 3** only. The school still teaches that afternoon, and the
effective-days engine prorates them instead of writing the day off. Set the
period range on those two; leave Half-Yearly and Annual as whole-day.

**Expect afterwards:** roughly **169 teaching days (~28 weeks)** left between
20 July and the year's end. That is the number every plan is sized against.

### Exam portions

Still on this step, set **exam portions** per class — the chapters each exam
covers. A quick pass: for the **Half-Yearly**, take each subject "up to" the
chapter that lands around mid-October in the plan; for the **Annual**, the last
chapter.

**Expect:** the **Exam fit** panel reads *perfect* or *spare time* for every
subject. Then, deliberately: delete the Half-Yearly block and repaint it 6–8
weeks earlier — verdicts should flip toward *manageable* / *won't fit*. Put it
back.

---

## 8. Students

Import **`data/students_roster.xlsx`**.

**Expect:** **created 240 · skipped 0 · errors 0**. Categories `Day Scholar` and
`Hosteller` are created on the fly; 66 of the 240 are hostellers (10% in classes
1–2 climbing to 45% in classes 7–8). Every student has a father and mother
guardian with a phone — those are the numbers absence alerts go to.

---

## 9. Timetable

Tap **"Generate the whole school's timetable"**.

**Expect:** the preview says **384 periods across 8 classes** (8 × 48), every
subject placed, **no teacher double-booked**. Apply, then open class 6's grid
and confirm it looks like a school week rather than eight Maths periods on
Monday.

If it reports clashes, that is a real finding — the heaviest teacher here carries
22 of a possible 46 periods, so the instance is not tight.

---

## 10. Generate & lock

**Expect:**
- The **gap report is empty**. (To see it work: delete class 3's Computer Science
  syllabus, come back — generation is blocked with a named gap. Restore it.)
- **Generate every plan** → all **60** come back clean: fits, in order, before
  the exams.
- **Approve & lock 60 plans** → done.

---

## After the wizard

The wizard covers academics. Four things it doesn't:

### Fee structures — Fees → Structures
8 structures (class band × category), from **`data/fee_structures.csv`**.
Fees are **admin-only**; log in as a teacher afterwards and confirm the Fees
nav item isn't there at all.

### Hostel blocks — Plan → Hostel
6 blocks, from **`data/hostel_sessions.csv`**. Each links its classes and is
**hostellers-only**, so the roster is computed — 66 students appear with zero
per-student picking, and a new admission joins automatically.

Note *Sunday Games* sits on a non-working day on purpose: hostel life doesn't
stop on Sunday, and it checks that a block outside the teaching week is allowed.

### Band thresholds — Students → Bands
Set the A/B/C cut-offs (`band_a_min` / `band_b_min`) before recording a band
test. Bands are **staff-only intervention tiers** — they must never surface on
anything a guardian receives.

### Give the teachers their logins
You copied 24 username/password pairs at step 5. Pick three to actually use:
- **`sis.meena.iyer`** — primary English, classes 1–2 (22 periods, the busiest)
- **`sis.anjali.gupta`** — middle Science, classes 7–8
- **`sis.vikram.singh`** — middle Maths *and* the senior evening-prep warden

Then work through **VERIFY.md**.
