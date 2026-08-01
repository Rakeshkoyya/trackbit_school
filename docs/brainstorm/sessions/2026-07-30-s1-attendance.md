# Session 1 — 2026-07-30

**Topic:** attendance, opened out into class teacher, staff and payroll.
**Outcome:** 7 decisions (`D-01`–`D-07`), 15 open questions, this folder created.

---

## How it went

The session started as "review the attendance module and refine it". The code review turned up
one defect serious enough to reframe the rest of the conversation, and the founder's response
opened three adjacent modules.

## What the review found

*(Full detail in [`../modules/attendance.md`](../modules/attendance.md) §1. Summarised here so
the session record stands alone.)*

1. **"Absent for a day" is defined three ways in the same product.** The parent portal and the
   admin red list agree (absent in *every* marked period). The 19:00 daily report disagrees
   (absent in *any* period counts the day). The student report card shows a fourth number
   entirely — a period rate labelled just "Attendance 82%". Net effect: the report the admin
   reads every morning can name a student the red list and the parent app both consider present.
2. **The percentage rewards under-capture.** All attendance % is over *marked* periods, so a
   class that marks one period a day scores higher than one that marks eight.
3. **Two roll-call screens with opposite defaults** — school starts everyone unchecked, sessions
   start everyone present.
4. **No absence reason, no informed absence, no follow-up outcome.** The loop dead-ends at the
   parent boundary.
5. **Signals that don't exist:** left mid-day, chronic lateness, the drifting 60–85% band.
6. **The class teacher field is dead** — model and API complete, no UI, null everywhere.
7. **No enrolment date on students**, so mid-year joiners' percentages are wrong.
8. **No salary or payroll code of any kind** — genuinely greenfield.

## What the founder decided

| # | Decision |
|---|---|
| `D-01` | Attendance frequency is an org setting: every period / first period only / twice daily (first + after lunch). The whole system follows the mode. |
| `D-02` | Teacher marks absent → admin or teacher adds a reason later → reason = yellow, 3+ days without one = red → inform parents / assign a teacher to follow up. |
| `D-03` | Admin assigns class teachers in Setup; each gets a dedicated dashboard for her class (attendance, syllabus, more). |
| `D-04` | Staff half-day leave and late marking; admin approves; backend tracks days present. |
| `D-05` | **Payroll** — salary calculated from days present. Policy config in org settings. *(Reverses the §11 fence.)* |
| `D-06` | Salary tab under Staff: admin dashboard view + teacher self-view for her own month. |
| `D-07` | No student login, ever. Students are data — this is school-level management software. |

## Things worth flagging from this session

**Two fences moved.** `D-05` reverses "payroll/HR is OUT" and SF-1's own "operational only, not
payroll". `D-04` reverses SF-1's "present/absent only — no late tier for staff". Both are
recorded in `decisions.md` rather than left to be rediscovered as apparent regressions.

**One decision is ambiguous and needs a straight answer.** The heading was *"absent request from
parents"* but the flow described was teacher-marks / staff-types-the-reason. Those are different
products — one keeps the read-only parent fence intact, the other reverses it. Raised as `Q-01`
and it blocks the shape of `D-02`.

**One decision is nearly free.** `D-03`'s assignment half is a frontend select; the backend has
accepted `class_teacher_member_id` since P0-C. Shipping it alone would immediately populate four
existing screens that have never had data.

**One decision is much larger than it reads.** `D-05` is a tab in the description and a product
in practice. The estimate-vs-payable-record question (`Q-05`) has to be answered before any of
it is built, and salary needs an explicit fence against Lucy, the daily report and the widget
layer — none of which have a concept of "this field is different".

## What to do before session 2

The blocking questions, in the order they unblock work:

1. **`Q-01`** — does a parent ever submit an absence, or does staff always type it?
2. **`Q-02`** — does the attendance mode affect only attendance, or the whole period card?
3. **`Q-03`** — in twice-daily mode, what is "present AM, absent PM"?
4. **`Q-05`** / **`Q-06`** / **`Q-08`** — payroll: estimate or record, who may see it, what
   deducts pay.

Non-blocking but cheap to settle: `Q-04` (75% rule), `Q-09`/`Q-10` (class teacher screen shape),
`Q-15` (AM/PM on half-day).

---

## Files created this session

```
docs/brainstorm/
  README.md
  decisions.md
  open-questions.md
  role-screen-map.md
  modules/attendance.md
  modules/class-teacher.md
  modules/staff-attendance-leave.md
  modules/payroll.md
  sessions/2026-07-30-s1-attendance.md   ← this file
```

No code was written and no migration was created, by design.
