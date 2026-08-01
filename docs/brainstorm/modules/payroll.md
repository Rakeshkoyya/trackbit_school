# Module — payroll (attendance-driven salary)

**Status: greenfield.** *(verified)* There is no salary, payroll or compensation code anywhere
in the repo — not a field, not a service, not a string.

⚠️ **This module reverses a standing fence.** SPRD2 §11 lists payroll and HR under "Still OUT",
and SF-1 shipped six weeks ago explicitly as *"operational only: who covers period 4, not
payroll or HR"*. `D-05` voids that. Recorded loudly so nobody later reads the fence and treats
this work as a mistake.

---

## 1 · Decided this session

### `D-05` — salary is calculated from days present

Days present drive the calculation. Configuration lives in Organisation settings:

- total leaves allowed per year
- grace period per leave
- how many days per month a person may apply for

### `D-06` — a Salary tab under the Staff menu, two views

- **Admin** — a dashboard-style screen: days present per staff member and their estimated salary.
- **Teacher** — her own page, her own month's record. She sees only herself.

---

## 2 · The question that decides everything else

### `Q-05` — an estimate, or a payable record?

| | (a) Estimate | (b) Payable record |
|---|---|---|
| What it is | a number the admin reads before deciding what to pay | the system of record for payment |
| Needs | days present, a monthly amount, a divisor | payslips, month lock, arrears, revisions, PF / ESI / professional tax / TDS, a bank transfer file, a dispute path, an audit trail |
| Liability | none — a human still decides | real; a wrong figure is a wage dispute |
| Build size | a tab | a product |

**Claude recommends (a), and recommends naming it that way on the screen** — *"Estimated, based
on days present"* — so nobody mistakes it for a payslip. (b) can follow later as its own
explicitly-decided product; the reverse (shipping (b) and walking it back) is not available.

Everything below assumes (a) until `Q-05` says otherwise.

---

## 3 · Proposals (`S-nn`)

**`S-15` — call it "salary estimate", not "payroll", in v1.** The word sets expectations with
the school, and "payroll" promises statutory compliance that (a) does not deliver. It also keeps
the fence reversal proportionate — TrackBit is still not an HR product.

**`S-16` — the calculation must be explainable line by line.** The screen's job is not the final
number; it is *why* the number is that. A teacher looking at her own page should see:

```
  Base (monthly)                        ₹ 32,000
  Working days in July                        26
  Present                                     23
  Approved leave (within balance)               2   no deduction
  Unapproved absence                            1   − ₹ 1,230
  Half-days                                     0
  ────────────────────────────────────────────────
  Estimated                             ₹ 30,770
```

Any figure the person being paid cannot reconstruct will be disputed, and the dispute lands on
the admin, not on us.

**`S-17` — salary is the most sensitive column that will exist in this database. Fence it
explicitly.** Three places currently read broadly and would leak it by default:

| Surface | Risk | Required |
|---|---|---|
| **Lucy** | 43 read tools wrap the existing services; a new field on a wrapped model can surface in chat | payroll tools excluded from the registry, or gated on the same capability as the screen |
| **Daily report** | assembles from services with a synthetic admin context | never includes payroll |
| **Widgets** | materialize from stored tool results | cannot reach a field the tools never return |
| **Super-admin** | `require_super_admin` lifts the RLS GUC — the operator reads across orgs by design | a conscious decision, not a discovery (see `Q-06`) |

**`S-35` — a pay revision is an append, never an update.** Law 3, applied where it matters most:
if the monthly amount is overwritten, last month's figure becomes unexplainable the moment
anyone gets a raise. `salary_records` with an `effective_from` date, and the calculation picks
the row in force for that month.

**`S-36` — snapshot what the calculation used.** Attendance can be corrected weeks later
(`mark` is a full replace). If July's estimate is recomputed in September from data that has
since changed, the two figures differ and nobody can say why. Store the inputs with the month's
result, or make the month explicitly recomputable-and-versioned.

**`S-37` — the teacher's salary page must show her attendance evidence, not just the figure.**
"You were absent 3 days" needs to be clickable to *which* days. Otherwise the first dispute
becomes a manual reconciliation the admin does in a notebook.

**`S-38` — do not put payroll on the admin overview or the daily report.** Every other module
earns a block on the operating board. This one should not — a salary figure on a screen that is
open on a projector in a staff room is a different kind of accident. Keep it behind its own tab,
behind its own capability.

---

## 4 · Data model sketch

Nothing committed. Shapes only.

```
salary_records                    NEW — append-only pay revisions      (S-35)
  org_id, member_id, amount_monthly, effective_from, note,
  created_by_member_id, created_at
  the calculation reads the row in force for the month

salary_months                     NEW — one row per member × month     (S-36)
  org_id, member_id, month,
  working_days, present_days, half_days, leave_used, unpaid_days,
  base_amount, deduction, estimated_amount,
  computed_at, inputs_snapshot (jsonb)
  a derived cache with a rebuild path — like plans.status

organizations
  + payroll_enabled        bool                                        (S-38)
  + leave_grace_days       int                                         (D-05, lives with leave — S-33)
  + monthly_apply_cap      int                                         (D-05)
  + pay_divisor            working_days | fixed_26 | fixed_30          (Q-08)

memberships
  + can_view_payroll       bool                                        (Q-06 option b)
```

Both new tables get an org-isolation RLS policy (law 2), same as every other table.

---

## 5 · Open questions

All four are blocking, and none can be guessed:

- **`Q-05`** estimate vs payable record — decides the whole module
- **`Q-06`** who may see salary — decides the guard on every endpoint
- **`Q-07`** salary structure, and where the amount is entered
- **`Q-08`** what actually reduces pay — decides the calculation
- `Q-12` does covering a period earn anything

See [`../open-questions.md`](../open-questions.md).

---

## 6 · Rough build order

Deliberately last of the four modules. It depends on `D-04` (half-day and late must exist before
days-present means anything) and it is the only module here that carries real-world liability.

| Step | Migration | Contents |
|---|---|---|
| 0 | — | answer `Q-05`–`Q-08` |
| 1 | yes | `salary_records` (`S-35`) + the amount entry surface + `Q-06`'s capability |
| 2 | yes | `salary_months` (`S-36`) + the calculation + `S-17`'s exclusions |
| 3 | none | admin screen (`D-06`) with `S-16`'s line-by-line breakdown |
| 4 | none | teacher self-view (`D-06`) with `S-37`'s clickable evidence |
