# Module — student attendance

Covers: how attendance is taken, by whom, in what mode, what an absence means afterwards, and
how it is shown to each role.

Related: [`class-teacher.md`](class-teacher.md) (who owns the follow-up),
[`staff-attendance-leave.md`](staff-attendance-leave.md) (the staff side, a separate shape).

---

## 1 · Where it stands today *(verified in code, 2026-07-30)*

### Capture — three shapes for one act

| What | Storage | Shape | Marked by | Screen |
|---|---|---|---|---|
| Student × class-period | `class_periods` + `attendance_exceptions` | **exception-only**; present is derived (roster − absentees) | teacher, substitute, or admin | `/my-day/period/[classId]/[no]/attendance` |
| Student × hostel session | `session_attendance` | **one row per student** (present/late/absent) | teacher / warden | `/sessions/[id]/attendance` |
| Staff × day | `staff_attendance_days` + `staff_absences` | exception-only, no late tier | admin only | `/staff` |

`class_periods` is the anchor row for a period; `attendance_marked_at` being non-null **is** the
"this class was marked" signal, and its absence unambiguously means nothing was captured. That
distinction is load-bearing and must survive every change below.

### The two student sheets have opposite defaults

- School roll call: **every box starts unchecked**, tick who answers, unticked saves as absent.
  A "Tick everyone" shortcut makes the fast path 2 taps.
- Session roll call: **everyone starts present**, tap a student to cycle present → absent → late.

Same teacher, same act, two habits — and SPRD2 §5.4 specifies *"All present ✓ one tap"*, which
neither screen does.

### The three definitions of "absent for a day" 🔴

This is the most serious defect in the module and everything else waits on it.

| Where | Rule | File |
|---|---|---|
| Parent portal | absent in **every** marked period = absent; some = "partial" | `services/parent_portal.py` |
| Admin red list | `n_absent >= n_marked` — same rule | `services/insights/attendance.py` |
| **Daily report, repeat-absentee** | `count(distinct date)` over absent rows — absent in **any one** period counts the whole day | `services/daily_report.py:271` |
| Student report card % | present *periods* / marked *periods*, labelled only "Attendance 82%" | `services/growth.py` |

So the 19:00 report the admin reads every morning can say *"Asha absent 3 of last 5 days"* while
the red list has her nowhere and her parent's app says she was present all three days.

### The percentage rewards under-capture

Every attendance % in the product is over **marked periods**. A class that marks only period 1
scores 97%; a class that marks all eight scores 91%. The capture heatmap exists because someone
already noticed this — but the percentage tiles sit beside it with no denominator stated.

### Other verified gaps

- **No enrolment date on students.** `students` has `admission_no` but no admission/enrolment
  *date*, so a September joiner's % is computed over the class's entire marked history and is
  understated. That number reaches a parent.
- **No absence reason** anywhere. Sick vs family function vs quietly dropped out is unrecorded.
- **No planned/informed absence.** A child on a 10-day family trip lights the red list every
  morning and the admin re-decides daily.
- **The alert fires only on the first marked period.** Present at P1 and gone by lunch produces
  no alert, ever. And if P1 is never marked and P4 is, a guardian gets "absent today" at 12:30
  with no cutoff guard.
- **`mark` accepts any date silently** — a teacher can rewrite last month.
- **Late is captured and then ignored.** `late_minutes` exists; late counts as present
  everywhere; "late 4 of 5 days" is invisible.
- **`AttendanceMarkOut.mark_id`** is a deprecated alias still shipping.

---

## 2 · Decided this session

### `D-01` — attendance frequency is an org setting

Three modes, selected in Organisation settings, and the whole system follows:

| Mode | Meaning |
|---|---|
| `per_period` | a mark per timetabled period (today's only behaviour) |
| `first_period` | one roll call a day, at the day's first period |
| `twice_daily` | first period, **and the first period after lunch** |

**What "the whole system follows" has to mean, concretely:**

- **My Day** asks for attendance only in the marking period(s).
- **The capture heatmap's denominator** becomes the marking periods, not every timetabled
  period — otherwise a school on `first_period` sees "6 of 44 captured" in red every morning.
- **The 16:00 reminder** counts only unmarked *marking* periods.
- **Every attendance %** is denominated in marking slots, which is what finally makes it
  comparable across classes.
- **The absence alert** fires on the first marking period, as now.

*Implementation note (verified):* "the first period after lunch" is already computable with no
extra config — `academic_years.period_times` carries entries with a `kind`, and
`school_clock.day_periods` filters `kind == 'period'`, so the break is already a distinct entry.
The after-lunch marking slot is the first period entry that starts after the break entry.

### `D-02` — absence reason, then a RAG-coloured follow-up

1. Teacher marks absent — **capture is unchanged**, still exception-only, still one tap.
2. The absence surfaces on the admin's screens.
3. **Admin or teacher adds the reason afterwards.** Never required at capture.
4. Colour: **reason recorded → yellow**; **3+ days with no reason → red**.
5. Red rows carry two actions: **inform the parents**, and **assign a teacher to follow up**.

### `D-07` — no student login

Students are data. Nothing in this module has a student-facing surface.

---

## 3 · Proposals (`S-nn`) — not yet decided

### Foundations

**`S-01` — one `day_status()` function, before anything else.** Every surface calls it. Zero
migration, and it kills the three-definitions bug. This is the cheapest high-trust change in the
whole redesign and everything in `D-01`/`D-02` sits on top of it.

**`S-02` — add `students.enrolled_on`.** A mid-year joiner's denominator starts on the day they
joined. Small field, high integrity, visible to parents.

**`S-03` — every percentage states its denominator.** "82% of school days" or "82% of marked
periods" — never a bare "82%". A number without its denominator is precisely the
bunch-of-numbers problem in a single line.

**`S-04` — backdating policy.** Teacher may mark today and yesterday; admin may mark any date,
and the row records that it was entered late. Today anyone can silently rewrite any date.

**`S-23` — a day roll-up table, but only later.** `attendance_days` as a rebuildable derived
cache (same discipline as `plans.status`) is what makes the term register, the parent month
calendar, and streaks-in-one-query possible. It is **not** needed for `D-01` or `D-02` and
should not be built until the register is actually wanted — `S-01` gets the correctness without
the migration.

### New signals

**`S-05` — "left after lunch" as a first-class state.** In `twice_daily` mode this is not an
edge case, it is *the reason the school chose that mode*. Present AM, absent PM should be its
own named state with its own row on the admin board and its own parent message — never folded
into "partial". Blocked on `Q-03`.

**`S-06` — chronic lateness.** "Late in the first period 4 of the last 5 days" as a row in the
same family as the red list. An admin row, not a parent message.

**`S-07` — the drifting band.** The red list catches people at 3 consecutive days. Nobody
catches the slow fade from 95% to 78% over a term, which is where intervention is cheapest.
Students at 60–85% and trending down get their own list.

### Follow-up mechanics (how `D-02` should be built)

**`S-22` — the status is computed once, server-side.** `D-02`'s yellow/red is a *state machine
on the absence*, not colour logic in a component. Compute a status enum
(`unexplained` / `explained` / `escalating` / `resolved`) in one service and let every UI paint
it. Three components deciding their own colours is exactly how the three definitions of "absent"
came about.

**`S-14` — not-captured is never red.** A day nobody marked is a gap in the record, not an
absence, and must never colour red or count toward the 3-day escalation. This rule is already
honoured elsewhere in DASH3 and must extend to the new colours.

**`S-21` — record the follow-up *outcome*, not just the press.** Today the action rail appends a
row saying the button was pressed. "Spoke to the father — fever, back Monday" has nowhere to go,
so the red row keeps re-asking and the admin stops trusting it. The outcome belongs on the
student's absence record, and it is what turns a red row yellow.

**`S-24` — informed/planned absence.** The office takes a phone call: "away 12–15 August, family
function". Recording that once should pre-mark those days, suppress the guardian alert, keep the
child off the red list with the reason visible, and stop the daily re-decision. This is `D-02`'s
yellow, applied ahead of time instead of afterwards.

**`S-13` — alert guardrails.** Suppress the absence alert when a reason or informed absence
already exists, and add a cutoff hour after which the alert escalates to the admin instead of
messaging a parent — nobody wants a 4pm "your child is absent today".

### Screens

**`S-08` — the admin attendance tab, rewritten as questions.** Apply the DASH3-OV pattern the
overview already got and this tab never did: a plain-sentence headline, named rows, an action
per row, charts folded behind *More*.

> *428 of 470 in today. 6 need a call. 13 periods still unmarked in 3 classes.*
> 1. **Needs a call** — red first, then yellow, each with reason-if-known, owner, last contact
> 2. **Drifting** · 3. **Left after lunch** · 4. **Chronic late**
> 5. **Is the record complete** — the heatmap, pivoted **by teacher** as well as by class
> 6. *More* → the 14-day pulse, by-class bars

**`S-09` — pivot the capture heatmap by teacher.** The decision an admin makes from it is *who
to talk to*, and the class grid makes them work that out. The syllabus insights already do
exactly this re-pivot, so the pattern exists.

**`S-10` — the 16:00 nudge should name and link.** Today it is a bare count: *"You have 3
class-period(s) not yet marked"* — names nothing, links nowhere.

**`S-11` — parents get the pattern, not just the day.** A month calendar strip and "present 18
of 21 school days". The calendar is the one chart every parent reads instantly. Still never
per-period detail.

**`S-12` — one roll-call component, one default.** Unify the school and session sheets. Default
to "everyone present, tap the exceptions" (the P1v2 budget and the §5.4 spec), with a "call the
roll" toggle preserving the current name-by-name flow for teachers who prefer it. Storage stays
as it is — this is a frontend unification, not a migration.

**`S-25` — the parent's absence card gets a "tell the school why" link.** `tel:` or WhatsApp
deep link to the school's number. Zero writes, fence intact, and it is what makes `D-02`'s
reason field actually get filled. Depends on `Q-01`.

---

## 4 · Data model sketch

Nothing here is committed. Shapes only, so the discussion has something concrete.

```
organizations
  + attendance_mode        per_period | first_period | twice_daily   (D-01)
  + min_attendance_pct     nullable int                              (Q-04)

students
  + enrolled_on            date, nullable                            (S-02)

attendance_exceptions
  + reason_code            nullable text — small vocabulary + free text  (D-02)
  + reason_note            nullable text
  + reason_by_member_id    who added it, when                        (D-02 step 3)

student_absence_notes      NEW — informed/planned absence + follow-up outcomes  (S-24, S-21)
  org_id, student_id, from_date, to_date, reason_code, note,
  source (parent_call | office | teacher), created_by, created_at
  APPEND-ONLY (law 3) — a correction is a new row, never an edit

attendance_days            NEW, LATER ONLY — derived cache             (S-23)
  org_id, student_id, date, status, marking_slots, absent_slots, mode_at_capture
  rebuildable from class_periods + exceptions; never a capture surface
```

**Constraints that must hold:**
- Capture stays exception-only. No table here may require a row per present student (P1v2).
- The reason is always optional and always *after* the fact. If entering a reason ever becomes a
  step in the capture flow, this design has failed.
- Nothing in this module reaches a parent except through the curated projection in
  `parent_portal.py` — field-by-field, never a spread (P4 discipline).

---

## 5 · Open questions

`Q-01` (parent submits?) · `Q-02` (does the mode affect the whole period card?) ·
`Q-03` (present AM, absent PM = ?) · `Q-04` (minimum-attendance rule) ·
`Q-11` (mode change mid-year) · `Q-13` (school-wide closure). See
[`../open-questions.md`](../open-questions.md).

---

## 6 · Rough build order (thinking aid, not a commitment)

| Step | Migration | Contents |
|---|---|---|
| 1 | none | `S-01` one day-status function · `S-03` denominators in every label · drop `mark_id` |
| 2 | yes | `D-01` attendance mode · `S-02` enrolled_on · `S-04` backdating · `Q-02`-dependent My Day changes |
| 3 | yes | `D-02` reasons + `S-22` status machine + `S-24` informed absence + `S-21` outcomes + `S-13` alert guardrails |
| 4 | none | `S-08` admin tab as questions · `S-09` by-teacher heatmap · `S-05`/`S-06`/`S-07` new signals · `S-10` nudge |
| 5 | none | `S-11` parent pattern view · `S-25` tell-us-why link · `S-12` unified sheet |
| 6 | optional | `S-23` day roll-up + term/annual register export |
