# Module — staff attendance, half-day and leave

The staff side. Feeds [`payroll.md`](payroll.md), which is why `D-04`'s precision matters more
than it looks: once days-present drives money, every state in this module becomes a number
somebody is paid by.

---

> ## Built — V1-4, 2026-08-02 (migration `b4c5d6e7f8a9`)
>
> `D-04`, `S-18`, `S-31`, `S-19` and `S-34` are **shipped**. `staff_absences` widened in place —
> `status` (absent | half_day | late) + `portion` (am | pm) — exactly as `S-18` argued; no second
> table. `leave_requests.days` is numeric so a half-day is 0.5, with `is_half_day`/`portion`
> beside it. `staff_attendance.present_value` is the one place a marked day becomes a number of
> days present, and `S-19` was taken literally: **late is worth a full day**, a flag to be seen
> and never a deduction. `D-78`'s month summary (`services/staff_month.py`) is the payoff, and
> `S-34` is enforced in the service rather than left to a screen — `days_not_marked` is its own
> count, in its own word, and never an absence.
>
> `S-33`'s grace period and `S-32`'s leave types stayed out: both are answers to `Q-08`, which is
> deferred with payroll (`D-78`). §6's two consequences remain open and remain right.

## 1 · Where it stands today *(verified in code, 2026-07-30)*

Shipped as **SF-1** on 2026-07-29. Migration `c7d8e9f0a1b2`, applied to production.

### Staff attendance — admin-marked, exception-shaped

- `staff_attendance_days` — one row per org × date. Its existence is what separates *"nobody was
  absent"* from *"nobody marked it"*.
- `staff_absences` — absentees only. **Present is derived.**
- `mark` is a **full replace**, so reopening a day and correcting it needs no undo path.
- Approved leave pre-unticks the person and says why.
- **Present/absent only — there is no late tier and no half-day.** That was a deliberate SF-1
  call, now reversed by `D-04`.

### Leave

- `leave_requests` + append-only `leave_request_events` (law 3); `status` is a derived cache of
  the newest event.
- `organizations.leaves_per_year` / `leaves_per_month` — defaults 8 / 1, configurable in Setup →
  Settings.
- `days` counts **working days** — the year's `working_weekdays` minus holidays, never raw span.
  **This decision is made and should be reused, not re-litigated, when payroll arrives.**
- Over-policy applications are **flagged, not blocked** (`warnings` rides on the request; the
  admin decides). The reasoning is recorded in SF-1: *a validator that refuses an emergency is
  one staff route around by phone.*
- **No leave type** (casual / sick / earned) and **no half-day** on the request.

### Timesheet

- `timesheet_entries` — one row per member × date × period_no, recording what a teacher did with
  a period she was **not** teaching. Teaching periods are never copied here; the grid owns them.
- `core/work_types.py` is the picker — 8 buckets, **no CHECK constraint**, so a school's own
  word is kept.

### Screens

`/staff` (mark the day) · `/staff/leave` (approve, with the history timeline) · `/staff/today`
(who's teaching / working / free right now) · `/timesheet` + `/timesheet/leave` (the teacher's
own side).

---

## 2 · Decided this session

### `D-04` — half-day leave and late marking

- The admin marks staff attendance — unchanged.
- A teacher can apply for **full-day or half-day** leave; the admin approves.
- The admin can mark someone **late**.
- The backend keeps a running count of **days actually present**, feeding `D-05`.

**Reverses SF-1's explicit "present/absent only — no late tier for staff".** Recorded so the
reversal is visible rather than looking like a regression.

---

## 3 · Proposals (`S-nn`)

**`S-18` — half-day and late extend the exception row; no new table.** The module's whole shape
is "present is derived, deviations are rows". Keep it:

```
staff_absences  →  staff_day_marks   (rename, or keep the name and widen it)
    status  = absent | half_day | late
    portion = full | am | pm          -- meaningful when status = half_day
```

Present remains "no row". One row per person per day, still a full replace, still no undo path
needed. Anything else forks the truth about a single day across two tables.

**`S-19` — "late" needs a threshold decision, or it will not be used.** Late by five minutes is
not the same fact as late by an hour, and asking an admin to type minutes for each person will
not happen. Suggest late is simply a flag, and if a deduction ever attaches to it (`Q-08`), it
is *"N lates = half a day"* — a policy number in settings, not a per-person judgment.

**`S-31` — half-day must carry AM/PM, not just 0.5.** The substitution board's entire job is
knowing which periods need cover. "0.5 days" cannot answer that. This is `Q-15`.

**`S-32` — leave types, but only if payroll needs them.** Casual / sick / earned / unpaid is
standard, and `Q-08` may make it necessary (unpaid leave deducts, sick leave may not). But if
the calculation turns out not to care, skip it — an unused taxonomy is a form that people fill
in wrong.

**`S-33` — the grace period from `D-05` belongs here, not in payroll.** "How many days' grace
per leave" is a leave-policy concept. Putting it in the leave module keeps the payroll
calculation a pure function of days, which is what makes it explainable to the person being
paid.

**`S-34` — approved leave should pre-mark the day, not just pre-untick it.** Today approved
leave unticks the person but the admin still saves the day for the record to exist. Once money
depends on it, a day nobody marked must never silently read as "absent, unpaid". `S-14`'s rule —
not-captured is never a red — becomes a financial rule here, not just a display rule.

---

## 4 · Data model sketch

```
staff_absences (or staff_day_marks)
  + status    absent | half_day | late      (D-04, S-18)
  + portion   full | am | pm                (S-31)

leave_requests
  + is_half_day  bool                        (D-04)
  + portion      am | pm, nullable           (S-31)
  + leave_type   nullable                    (S-32, only if Q-08 needs it)

organizations
  + leave_grace_days       int               (D-05 / S-33)
  (leaves_per_year, leaves_per_month already exist)
```

---

## 5 · Open questions

`Q-08` (what actually reduces pay — the half-day and late semantics come from this) ·
`Q-12` (does covering a period earn anything) · `Q-15` (AM/PM on half-day).
See [`../open-questions.md`](../open-questions.md).

---

## 6 · Where this module's data must NOT go

Once `D-05` lands, staff attendance stops being purely operational and becomes evidence for a
payment. Two consequences to hold on to:

1. **Corrections need a trail.** `mark` being a full replace is right for an operational record
   and questionable for a financial one — if a day is silently rewritten three weeks later,
   nobody can explain a changed figure. Law 3 already answers this: the correction should be an
   append, or at minimum the payroll calculation should snapshot what it used.
2. **A teacher must be able to see her own attendance record**, not just her salary figure. If
   the number is disputed, the evidence has to be visible to the person disputing it. This is
   covered by `D-06`'s teacher view but is worth stating as a requirement, not a feature.
