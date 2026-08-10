# FE-1 — the fee desk

**Status:** proposed, awaiting founder confirmation · **Written:** 2026-08-11
**Supersedes nothing.** Extends M6 (the ported fee module), V1-10 (the collection
board) and V1-18. Reference prototype: `../fee_management_system` ("Plutus").

---

## §0 — Cold start

Read this section if you are picking the packet up with no context.

**The fee module already exists and its arithmetic is correct.** It was ported
from Plutus onto `org_id` + RLS: five tables, a money library, an append-only
ledger, a conversation history, a collection board with quarter windows, and 20
routes. Nothing in this plan replaces that engine.

**What is wrong is the desk on top of it.** Today an admin who wants to price her
school and collect from it has to:

1. type a class *label* by hand (`6-B`) into a free-text box, hoping it matches
   the label the student list will later build from `school_classes`;
2. accept an even split — there is no way to give instalment 2 a due date or a
   name in the UI;
3. enrol students **one at a time**, typing each student's total fee by hand into
   a dropdown-driven sheet, even though the structure she just wrote knows it;
4. never see a student who has not been enrolled yet — the fee screen lists only
   fee *records*, so the 40 children nobody set up are invisible;
5. give up if a family asks to split an instalment, because no route can add,
   split or remove one after enrolment;
6. keep the receipt photo in WhatsApp, because nothing here stores one.

FE-1 builds the desk: **price the year → set the class up → work one family**,
with a proof of every rupee and a log of every action.

**The three screens** are `Fees → Dashboard · Students · Structure`. The
Dashboard is the V1-10 collection board, already built and unchanged.

---

## §1 — The ask, restated

The founder's words, and what each one commits us to.

> *"the first step is to enter the fee structure this is the backbone of that
> year data, this structure contains data like class total fee and default
> installments, just like the plutus, once all the classes and fee structure is
> done"*

A **coverage-first** structure screen. "Once all the classes … is done" is a
completeness check, so the screen must show every class in the year — including
the ones with no price — not just a list of the structures that happen to exist.

> *"second step is adding students data, since we already have student data in
> our system we just show them here, so same selection methods like classes in
> nav buttons at top and below the table of student will show"*

Class chips across the top, students beneath. Students are **read** from the
existing roster, never re-entered. A student with no fee record still appears.

> *"the user can click on that row and enter details, like discount and
> installments we can add more installments as well (some cases some parent
> wants more installments to pay) and mode of payment and all the exsisting
> features that are there in both plutus and current implementations"*

Row → detail. Per-student discount, a **mutable instalment schedule**, payment
with mode, and everything Plutus and the current build already do.

> *"we can add feature like payment proof like capturing pic or upload the pic or
> pdf"*

Camera or file, image or PDF, attached to the payment it proves.

> *"there will be two section under the installments, we can show the
> converstaion history and transcation history, so we can properly store every
> action that has taken by who and what action so that log will also be recoded"*

Two sections **under** the instalment table — the money stays on screen while you
read what was said. And a complete actor log, which today only money mutations
produce.

> *"under the fee menu we can have navtabs one for dashboard and the other for
> student where by default all the student will be shown we can choose by class"*

A tabbed area. Students defaults to **All**.

---

## §2 — What is already built, and stays

Do not rewrite any of this. Import it.

| Thing | Where | Why it stays |
|---|---|---|
| Money arithmetic | `services/fee_math.py` | `q()` 2-dp Decimal, `proportional_installments`, `waterfall`, `even_split`. Status is **computed, never stored as truth**. |
| The collection vocabulary | `core/collection.py` | A quarter is a **due-date window**; `collected`/`pending`/`overdue` are three states that are never added; `Collection` deliberately has **no `outstanding`**. |
| The append-only ledger | `models/fees.py::Transaction` | Undo writes a compensating row. Never UPDATE, never DELETE. |
| The conversation | `models/fees.py::FeeNote` | `said` is the load-bearing column (`D-84`). |
| The collection board | `services/collection.py`, `components/school/collection-board.tsx` | Quarter strip, pace marker, class table with **both denominators**, named defaulters, reminders with manners. This *is* the Dashboard tab. |
| Object storage | `services/storage.py` | Key-based API with presign + confirm, R2 or local disk. Payment proof rides this, exactly as `session_media` does. |
| The fee fence | `endpoints/fees.py` | Teachers never see fees. The one exception is `D-83`: an assigned follow-up task, one student, inside that task. |

**R2 is configured in `api/.env`** (account, key, secret and bucket all carry
values; `R2_PUBLIC_BASE_URL` is empty, so reads mint presigned GETs — the same
shape HS-1 uses). ⚠️ That is the *local* env file. Dokploy injects its own; §10
makes verifying the deployed values a pre-flight step, because proofs written to
a container's local disk are lost on the next deploy.

---

## §3 — The gap, precisely

| Capability | Today | FE-1 |
|---|---|---|
| Structure targets a class | `class_name` **TEXT**, typed by hand, matched later against a label built from `school_classes` | `class_id` FK, picked from the year's real classes; label kept as display fallback |
| Per-instalment label + due date | In the model and the API. **Not in the UI** — the page even-splits and sends no dates | Editable grid, live reconciliation |
| Edit a structure | Create-only (a new one archives the old) | `PUT`, presented as edit, still archiving underneath so history survives |
| Structure coverage | Lists only what exists | Every class in the year, priced or not |
| See an un-enrolled student | Impossible on the fee screens | Every student in the class, "fees not set up" as a **word** |
| Set a class up | One sheet per student, total fee typed by hand | Select rows → apply the class's structure; already-set-up students skipped and reported |
| Add / split / remove an instalment | **No route exists** | `split`, `add`, `remove`, each preserving `sum(instalments) == net payable` |
| Payment date per transaction | `paid_on` accepted, written to the *instalment*, lost on the transaction row | `fee_transactions.paid_on` |
| Payment proof | Nothing | `fee_payment_proofs`, camera or file, image or PDF |
| Who did what | Money mutations only | `fee_events` — enrolment, structure edits, schedule edits, proof uploads, reminders, assignments |
| Detail route | `/fees/[student_fee_id]` — cannot render a student with no record | `/fees/students/[student_id]`, old path redirects |
| `list_student_fees` cost | Loads every row, then `db.get(SchoolClass, …)` **per student** and filters in Python | Batched labels + SQL filters (the fix `overdue_students` already had) |
| Guard | `require_office_up` (an admin-only alias CLAUDE.md says to retire on touch) | `require_admin`, except `followup_detail` |

---

## §4 — Decisions

Numbered from D-116 (D-115 is the highest in use). These are **proposals** until
the founder confirms; the ones marked ⚑ change behaviour a reviewer could
disagree with.

**D-116 — A structure prices a CLASS, not a section.** *(founder, Q-1, confirmed
2026-08-11 — this replaces the `class_id` FK the first draft proposed.)*

One structure for "6" covers 6-A, 6-B and 6-C. That means the key cannot be a
`school_classes` FK, because a class in the founder's sense is several rows.
`fee_structures.class_name` therefore stays the key, with two changes:

* it holds the **class name only** (`"6"`), never the sectioned label (`"6-B"`)
  the current UI writes;
* it is **picked**, never typed — the editor offers the distinct
  `school_classes.name` values for the year.

Matching a student to her structure is `student → class_id → SchoolClass.name →
structure.class_name`. A one-off backfill normalises any existing row whose
`class_name` matches `name-section` but no bare `name`, and a partial unique
index stops two active structures ever sharing a key — which the service already
tries to guarantee in Python and could not enforce.

*Consequence:* the draft's "Also apply to 6-B, 6-C" control is **deleted**. One
structure already covers the grade, so the control would have been offering to
create rows the model no longer wants.

**D-117 — The structure screen is a coverage grid, not a list.**
Every class in the year gets a row. An unpriced class reads **"not priced"** in
amber, never `₹0`. This is the "once all the classes … is done" check, and it is
the same device the SY-2 syllabus grid uses.

**D-118 ⚑ — Editing a structure never rewrites a student's fee record.**
P2: the plan is the baseline. Saving an edited structure archives the old row and
writes a new one; the students already on the old amount are **untouched** and
the Students tab surfaces them as *"12 students on the previous ₹58,000"* with an
explicit **Re-apply** action. Silently repricing a family mid-year — possibly
after they have paid against the old figure — is the failure this prevents.

**D-119 — The Students tab lists students, not fee records.**
The roster is the source. "fees not set up" is a state and a word, never a zero
and never red — the same rule that keeps an unmarked register out of the red.

**D-120 — Setting a class up is one action, not N.**
Select rows → apply the class structure. Skips students who already have a record
for the year and says how many it skipped. Per-student typing for a whole class
is what P1v2 calls a mis-designed feature; the discount is the per-student edit,
and it comes after.

**D-121 ⚑ — The schedule may change; the total may not change by accident.**
`sum(instalments) == net_fee` is an invariant asserted after **every** schedule
mutation, in one place (`fee_math.assert_balanced`). Therefore:

* **Split** divides one unpaid instalment into N parts. The sum is preserved by
  construction — this is the "parent wants more instalments" case and the one to
  reach for first.
* **Add** appends an instalment and rebalances the *unpaid* ones proportionally,
  so the net is unchanged. The dialog says where the money comes from before it
  commits.
* **Remove** is allowed only on an instalment with `paid_amount = 0`, and
  redistributes its amount over the remaining unpaid ones.
* Changing the **total** is a discount edit, which already exists and already
  rescales the unpaid portion.

**D-122 — Proof attaches to the transaction, not to the student.**
A proof is evidence *of a payment*. `fee_payment_proofs.transaction_id` is the
key; `student_fee_id` rides along denormalised so the detail page can list every
proof in one query.

**D-123 ⚑ — A proof may be removed; the fact that it existed may not.**
Soft delete (`deleted_at`, `deleted_by_member_id`) with the object purged from
storage. Hard-deleting is refused (law 3), but a misfiled receipt is a real
privacy problem — a photo of the wrong family's cheque must be removable.

**D-124 — `fee_events` is the actor log; `fee_transactions` stays the money
ledger.** One new append-only table for who-did-what, because a third of the
actions the founder wants logged (structure edits) have no `student_fee_id` at
all, and because polluting a summable money ledger with zero-amount rows is how
totals go wrong. The detail page merges both into one feed.

**D-125 — The detail page is routed by student, not by fee record.**
`/fees/students/[student_id]`. A student with no fee record still has a page —
that is where you set them up. `/fees/[id]` redirects by resolving the fee record
to its student, so the collection board's existing defaulter links keep working.

**D-126 — `require_office_up` retires from this module.** Every route becomes
`require_admin`, except `followup_detail`, which stays `require_academic` with
the assignment check in the service (`D-83`).

**D-127 ⚑ — A transferred student's fee record is CLOSED, not deleted.**
*(founder, Q-2, confirmed 2026-08-11.)* Transferring prompts first. On confirm:

* every instalment with `paid_amount = 0` is marked **`voided`** — never deleted
  (law 3);
* the remaining balance comes off the total, so the record's payable drops to
  what was actually billed and paid. The school stops chasing it, and the
  collection board stops counting it as billed, pending or overdue;
* `student_fees.status` becomes **`closed`**, with `closed_at`, `closed_reason`
  and `closed_by_member_id`;
* **the transfer is undoable.** Reopening un-voids the instalments and restores
  the status, and both the close and the reopen are `fee_events` rows.

A voided instalment is excluded from every figure in `core/collection.py` — it
was never collected and was never owed, so it must not sit in any of the three
states. It stays visible on the family page, struck through, because the record
of what was originally scheduled is exactly what somebody will ask about.

**D-128 — Receipt numbers are generated, sequentially, per org and per year.**
*(founder, Q-4, confirmed 2026-08-11.)* Format `FR/2026-27/001`. A counter row
per (org, academic year) is taken under `SELECT … FOR UPDATE`, so two clerks
recording a payment at the same moment cannot be handed the same number —
`MAX(receipt_number) + 1` would do exactly that. The field stays editable: a
school reconciling against a pre-printed book has to be able to type the number
on the paper in front of it.

---

## §5 — The screens

### Design direction

The material this desk is made of is the **school receipt book**: ruled columns,
a running balance, a counterfoil torn off and kept, and a margin where the clerk
writes what the family said. Everything below is derived from that, inside
TrackBit's existing system — the chip rows from `class-subject-picker.tsx`, the
`components/charts/` kit, `Sheet`/`Modal`, `money()` from `school-format`,
`dayKey` from `lib/format.ts`, and the `.dark` class for theme. No new palette,
no second charting path.

**The signature device is the instalment row as a counterfoil**: number, period,
due date, amount, and a stub on the right that carries the payment mode and the
proof. It is the one row a school already recognises, and it is the row every
other fee screen summarises.

Two rules from `core/` govern every figure drawn here:

* **A figure carries its denominator.** *"₹31,000 of ₹62,000"*, never *"50%"*.
* **Not-captured is a word, never a zero and never red.** An unpriced class, a
  student with no fee record, and a quarter that has not started are all states.

Copy rules: buttons name what happens and keep the name through the flow
("Record payment" → "Payment recorded"). Empty states are invitations with the
next action in them, not apologies.

---

### 5.1 The area shell — `/fees`

```
Fees                                              [ 2026-27 ▾ ]
┌────────────┬──────────┬───────────┐
│ Dashboard  │ Students │ Structure │
└────────────┴──────────┴───────────┘
```

Three tabs in workflow order reading right-to-left as you set up, and in
frequency order reading left-to-right as you use it daily. `Dashboard` is the
default landing.

The `FeatureGate` for `FEATURES.feesCollection` stays on the **area layout**, one
decision covering all sub-routes. ⚠️ SY-2's lesson applies directly: *Plan →
Exams was blank because it was a Pro feature with no gate — a 402, not missing
data.* Every new sub-route must sit inside this layout, and the gate must render
the upgrade card, never an empty screen.

**Dashboard** is the V1-10 collection board unchanged, plus two additions:

* an empty state, when the year has no structures, that says *"No fees priced for
  2026-27 yet. Start with the structure."* and links to the Structure tab;
* a **collected by mode** strip (cash · cheque · online), grouped from
  `fee_transactions.mode`. It is the one Plutus figure the board does not carry,
  it is one `GROUP BY`, and it is the number that reconciles against the bank.

---

### 5.2 Structure — `/fees/structure`

```
  Structure                                6 of 8 classes priced
  The year's backbone. Every student's fee starts here.

  ┌───────────────────────────────────────────────────────────────┐
  │ CLASS   SECTIONS   CATEGORY     TOTAL       SCHEDULE  STUDENTS │
  ├───────────────────────────────────────────────────────────────┤
  │ 1       A · B      All          ₹48,000     3 parts       46   │
  │ 6       A · B · C  All          ₹62,000     4 parts       94   │
  │ 6       A · B · C  Staff ward   ₹31,000     4 parts        2   │
  │ 11      A          —            not priced  —              0 → │
  └───────────────────────────────────────────────────────────────┘
```

* Rows are the **distinct class names** in the year (`D-116`), left-joined to
  active structures. The SECTIONS column names what the price covers, so nobody
  has to wonder whether 6-C was included — it is the one thing per-class pricing
  has to make obvious.
* A class with two categories shows two rows; a class with none shows one row
  reading **not priced**.
* The **STUDENTS** column counts every student across all sections of that class
  who is on that structure — the fact that tells you whether editing is safe, and
  the thing `D-118` needs you to see first.
* Row click opens the editor.

**The editor** (a `Sheet`):

```
  Class      [ 6 ▾ ]  covers 6-A, 6-B, 6-C · 94 students
  Category   [ All ▾ ]
  Total fee  [ 62000 ]      Instalments    [ 4 ▾ ]

  Preset:  ( Split evenly )  ( Quarterly )  ( Copy from 5-A ▾ )

  ┌────────────────────────────────────────────────┐
  │ #   PERIOD            DUE DATE      AMOUNT     │
  │ 1   [1st Quarter  ]   [10-04-2026]  [ 15500 ]  │
  │ 2   [2nd Quarter  ]   [10-07-2026]  [ 15500 ]  │
  │ 3   [3rd Quarter  ]   [10-10-2026]  [ 15500 ]  │
  │ 4   [4th Quarter  ]   [10-01-2027]  [ 15500 ]  │
  └────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────┐
  │  ₹62,000 of ₹62,000 allocated       ✓ balanced │   ← green
  │  ₹2,000 still to allocate                      │   ← amber, when short
  └────────────────────────────────────────────────┘

                                    [ Cancel ]  [ Save structure ]
```

* The reconciliation bar is Plutus's best idea, kept and re-worded: *"₹2,000
  still to allocate"* tells you what to do; *"Difference: ₹2,000"* does not. Save
  is disabled until balanced — the same rule the service enforces.
* The class picker offers the year's distinct class **names** and says what the
  price covers underneath it. There is no free-text class box and no
  "also apply to" — one structure is the whole grade (`D-116`).
* **Quarterly** seeds due dates from the academic year's start using
  `fee_math.default_due_dates`; **Copy from** reads another class's active
  structure. Both are seeds — every field stays editable.
* Editing an existing structure that has students on it shows a line above Save:
  *"31 students are on the current ₹62,000. Saving prices new students only —
  you can re-apply to the rest afterwards."* (`D-118`.)

---

### 5.3 Students — `/fees/students`

```
  [ All ] [ 1-A ] [ 1-B ] [ 6-A ] [ 6-B ] [ 11-A ] …    ← ClassTabs, reused

  Search…            [ Any status ▾ ]     [ Set fees for this class ]

  ┌──────────────────────────────────────────────────────────────────┐
  │ ☐  STUDENT          ADM.    NET       PAID      BALANCE   STATUS │
  ├──────────────────────────────────────────────────────────────────┤
  │ ☐  Aarav Sharma     1024    ₹62,000   ₹31,000   ₹31,000   partial│
  │ ☐  Diya Patel       1025    ₹62,000   ₹62,000   —         paid   │
  │ ☐  Kabir Rao        1026    ₹55,800   —         ₹55,800   overdue│
  │ ☐  Meera Nair       1027    fees not set up               →      │
  └──────────────────────────────────────────────────────────────────┘

  4 selected · ₹2,48,000 will be billed      [ Apply 6-A structure ]
```

* The class row is the **existing `ClassTabs`** component from
  `class-subject-picker.tsx`, with an **All** chip prepended. That component
  already handles school-order sorting (`10` after `9`) and horizontal
  containment; do not write a second picker.
* **Every student in the class appears.** `fees not set up` spans the money
  columns as one muted word (`D-119`).
* Selecting rows reveals the action bar with the amount it is about to bill —
  the confirmation is the number, not a dialog.
* `Apply structure` skips students who already have a record and reports it:
  *"Set up 22 students. 2 already had fee records."*
* The class's structure line sits above the table: *"6-A · ₹62,000 · 4
  instalments"*, with **not priced → Set the structure** when it is missing, so
  the tab never dead-ends.

---

### 5.4 A family — `/fees/students/[student_id]`

```
  ← Students
  Aarav Sharma                                            [ partial ]
  6-A · Adm. 1024 · 2026-27                        [ Edit discount ]

  Total      Discount   Net        Prev. dues   Payable    Paid       Balance
  ₹62,000    —          ₹62,000    —            ₹62,000    ₹31,000    ₹31,000

  INSTALMENTS                                       [ + Add instalment ]
  ┌────────────────────────────────────────────────────────────────────┐
  │ 1  1st Quarter   10 Apr   ₹15,500   ₹15,500   paid     cash   📎2 ⟲│
  │ 2  2nd Quarter   10 Jul   ₹15,500   ₹15,500   paid     online 📎1 ⟲│
  │ 3  3rd Quarter   10 Oct   ₹15,500   —         overdue  [Record payment] ⋯│
  │ 4  4th Quarter   10 Jan   ₹15,500   —         pending  [Record payment] ⋯│
  └────────────────────────────────────────────────────────────────────┘

  ┌ Conversation ── Transactions ──────────────────────────────────────┐
  │                                                                     │
  │  09 Aug · Priya Menon · called                                      │
  │  "Spoke to the mother — paying after the 15th"       promised 15 Aug│
  │                                                                     │
  │  02 Aug · Priya Menon · reminder sent to father                     │
  │                                                                     │
  │                                           [ + Log a call ]          │
  └─────────────────────────────────────────────────────────────────────┘
```

* The stat row is Plutus's, kept — it is the right seven figures. `Prev. dues`
  renders as `—` when zero rather than `₹0`, and the year's dues and the carried
  dues never pool (`D-88`).
* **The instalment row is the counterfoil.** Due date is inline-editable
  (`PATCH …/due-date`, which exists and until V1-13 was a 500 nobody called). The
  right stub carries the mode, the proof count, and `⟲` undo where a payment
  exists.
* `⋯` per row → **Split**, **Change due date**, **Remove** (unpaid only).
* **Conversation is the default tab**, above Transactions, because the question
  at the counter is *"what did they say"*, not *"what did we record"* — the
  reason already written into the current page.
* **Transactions** is the merged feed: money rows from `fee_transactions` and
  actor rows from `fee_events`, one chronology, each line naming who did it.
  Money rows carry the amount in the type colour; actor rows are muted.
* A student with **no fee record** gets this page as a single invitation: the
  class's structure summarised, and one button — *"Set up fees from the 6-A
  structure"* — plus *"Enter a different amount"* for the exception.

**Record payment** (a `Sheet`):

```
  Instalment 3 · 3rd Quarter          remaining ₹15,500

  Amount   [ 15500 ]        Date     [ 11-08-2026 ]
  Mode     [ Cash ▾ ]       Receipt  [ FR/2026-27/151 ]
  Note     [                                        ]

  Proof    [ 📷 Take photo ]  [ 📎 Upload image or PDF ]
           ┌─────────┐
           │ receipt │  cheque-front.jpg · 240 KB   ✕
           │  .jpg   │
           └─────────┘

                                [ Cancel ]  [ Record payment ]
```

* `📷 Take photo` is `<input type="file" accept="image/*" capture="environment">`
  — the phone camera on mobile, a file picker on desktop, no second code path.
* Proof is **optional**. Making it mandatory would stop a cash payment being
  recorded at the counter, which is the one thing this screen must never do.
* Uploads go through presign → PUT → confirm when R2 is configured, and through
  the pass-through endpoint when it is not (the HS-1 pattern, already written).

**Split** (a `Modal`):

```
  Split 3rd Quarter · ₹15,500

  Into [ 2 ▾ ] parts

  ┌──────────────────────────────────────┐
  │ 3a  3rd Quarter (1)  10 Oct  ₹7,750  │
  │ 3b  3rd Quarter (2)  10 Nov  ₹7,750  │
  └──────────────────────────────────────┘
  Amounts and dates stay editable. The total does not change.

                            [ Cancel ]  [ Split instalment ]
```

---

## §6 — Data model

One additive migration. Revision **`b7c8d9e0f1a2`**, down-revision
**`d4e5f6a7b8c9a`** (the TT-3 head). Both verified free/current on 2026-08-11 —
re-verify with `uv run alembic current` before writing it, per CLAUDE.md.

```sql
-- D-116: class_name holds the CLASS NAME only. Normalise "6-B" -> "6" where the
-- suffix is a real section of a real class in the same org + year, then archive
-- any duplicate the normalisation collides into, then enforce it for good.
--   (data migration, then:)
CREATE UNIQUE INDEX uq_fee_structures_active_key ON fee_structures (
  org_id, academic_year_id, class_name,
  COALESCE(category_id, '00000000-0000-0000-0000-000000000000'::uuid)
) WHERE is_active;

-- the payment date belongs to the payment
ALTER TABLE fee_transactions ADD COLUMN paid_on DATE NULL;

-- D-127: transfer closes a record, reversibly
ALTER TABLE student_fees ADD COLUMN closed_at TIMESTAMPTZ NULL;
ALTER TABLE student_fees ADD COLUMN closed_reason TEXT NULL;
ALTER TABLE student_fees ADD COLUMN closed_by_member_id UUID NULL
  REFERENCES memberships(id) ON DELETE SET NULL;
-- installments.status gains 'voided'; it is a computed word, so no constraint
-- changes -- but `voided` is STORED (it is a decision, not a derivation) via a
-- new boolean so recompute cannot silently un-void it:
ALTER TABLE installments ADD COLUMN is_voided BOOLEAN NOT NULL DEFAULT false;

-- D-128: one receipt sequence per org + academic year
CREATE TABLE fee_receipt_counters (
  org_id           UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
  prefix           TEXT NOT NULL DEFAULT 'FR',
  next_seq         INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (org_id, academic_year_id)
);

-- D-122/D-123: proof of payment
CREATE TABLE fee_payment_proofs (
  id                    UUID PRIMARY KEY,
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  transaction_id        UUID NOT NULL REFERENCES fee_transactions(id) ON DELETE CASCADE,
  student_fee_id        UUID NOT NULL REFERENCES student_fees(id) ON DELETE CASCADE,
  kind                  TEXT NOT NULL,          -- photo | pdf
  object_key            TEXT NOT NULL,          -- the KEY, never a URL
  content_type          TEXT NOT NULL,
  size_bytes            BIGINT NOT NULL DEFAULT 0,
  caption               TEXT NULL,
  uploaded_by_member_id UUID NULL REFERENCES memberships(id) ON DELETE SET NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at            TIMESTAMPTZ NULL,
  deleted_by_member_id  UUID NULL REFERENCES memberships(id) ON DELETE SET NULL
);

-- D-124: who did what
CREATE TABLE fee_events (
  id                UUID PRIMARY KEY,
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  student_fee_id    UUID NULL REFERENCES student_fees(id) ON DELETE CASCADE,
  fee_structure_id  UUID NULL REFERENCES fee_structures(id) ON DELETE SET NULL,
  academic_year_id  UUID NULL REFERENCES academic_years(id) ON DELETE CASCADE,
  kind              TEXT NOT NULL,
  summary           TEXT NOT NULL,   -- one human sentence, written at write time
  meta              JSONB NOT NULL DEFAULT '{}'::jsonb,
  actor_member_id   UUID NULL REFERENCES memberships(id) ON DELETE SET NULL,
  actor_name        TEXT NULL,       -- denormalised: the log outlives the account
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_fee_events_student_fee ON fee_events(student_fee_id, created_at DESC);
```

`fee_events.kind` vocabulary: `structure_created` · `structure_replaced` ·
`fee_created` · `fee_bulk_applied` · `discount_changed` · `schedule_split` ·
`schedule_added` · `schedule_removed` · `due_date_changed` · `proof_added` ·
`proof_removed` · `reminder_sent` · `followup_assigned` · `note_added`.

**Both new tables get an `org_isolation` RLS policy** (law 2) and every query is
scoped by `org_id` in the service anyway. `summary` is written as a finished
sentence at write time so no reader ever re-derives the wording — the same reason
`created_by_name` is denormalised on the ledger.

**Prod is additive-safe:** every column is nullable or has a default, and the two
tables are new, so the migration can run ahead of the code deploy as the
convention requires.

---

## §7 — API

New (all `require_admin`):

```
PUT    /fees/structures/{id}                      edit (archives + replaces)
GET    /fees/structures/coverage?year_id=         every class, priced or not
POST   /fees/structures/{id}/apply                bulk create student fees
                                                  { student_ids[], skip_existing }

GET    /fees/students?year_id=&class_id=&status=&q=   roster ∪ fee records
POST   /fees/installments/{id}/split              { parts } | { amounts[] }
POST   /fees/student-fees/{id}/installments       add + rebalance
DELETE /fees/installments/{id}                    unpaid only, redistributes

POST   /fees/transactions/{id}/proofs/presign     → { url|null, key }
POST   /fees/transactions/{id}/proofs             confirm, or pass-through upload
GET    /fees/student-fees/{id}/proofs
DELETE /fees/proofs/{id}                          soft delete + purge object

GET    /fees/student-fees/{id}/activity           merged events + ledger
GET    /fees/collection/by-mode?year_id=          cash | cheque | online
```

Changed:

* every existing fee route `require_office_up` → `require_admin` (`D-126`);
* `POST /fees/installments/{id}/pay` accepts `proof_key` so a payment and its
  proof land in one round trip;
* `GET /fees/student-fees` keeps working (the collection board uses it) but gains
  `class_id` and moves its filtering into SQL.

**No route returns a fee figure to a teacher.** The new `/fees/students` read is
`require_admin` like the rest; `followup_detail` remains the single `D-83`
exception.

---

## §8 — Services

`services/fees.py` is ~520 lines and will not survive this comfortably. Split
along the seam the screens already draw (CLAUDE.md: 200–400 typical, 800 max):

```
services/fees.py            student fee records, payments, undo   (existing, trimmed)
services/fee_structures.py  structures, coverage, bulk apply       NEW
services/fee_schedule.py    split / add / remove + the invariant   NEW
services/fee_proofs.py      presign, confirm, list, soft delete    NEW
services/fee_events.py      the actor log — one `record()` helper  NEW
```

`fee_math.py` gains two pure functions, both unit-testable with no DB:

```python
def assert_balanced(net_fee, installments) -> None:
    """Raise ValidationError unless sum(amounts) == q(net_fee). Called after
    EVERY schedule mutation — D-121's invariant, asserted in one place."""

def rebalance_unpaid(net_fee, installments) -> list[Decimal]:
    """Scale the unpaid portion so the schedule re-sums to net_fee, never
    reducing any instalment below what has already been paid on it."""
```

`split_installment` is `even_split` over one row plus the parent's due date
carried to the first part — no new arithmetic.

**Two things to fix while in here**, both real defects rather than new work:

1. `list_student_fees` loads every fee record for the year, calls
   `db.get(SchoolClass, …)` **per student**, then filters `class_name`, `status`
   and `search` in Python. `overdue_students` was already fixed this way in
   V1-0e; this one was missed, and it is about to become the module's main screen.
2. `topic_progress` in `services/planner.py` is a sixth coverage definition — out
   of scope here, but noted so it is not confused with fee work.

---

## §9 — Phases

Work packet by packet. Do not start the next until the previous one's Done-when
passes **and** `pytest` is still green.

| # | Phase | Done when |
|---|---|---|
| **FE-1a** | Migration + models + RLS + `fee_events.record()` | `alembic upgrade head` clean on the **test DB**; both new tables carry an org-isolation policy; `test_rls.py` green under the restricted role |
| **FE-1b** | Structures: `class_id`, `PUT`, coverage read, bulk apply | An admin can price 6-A, copy it to 6-B/6-C, and set 31 students up in one action; re-applying skips the 2 who already had records and says so |
| **FE-1c** | Schedule: split / add / remove + `assert_balanced` | `sum(instalments) == net_fee` holds after every operation, proven by a property test over random splits; removing a part-paid instalment is refused |
| **FE-1d** | Proof: presign, confirm, list, soft delete | A JPEG and a PDF both round-trip with R2 configured **and** with it unconfigured; a deleted proof's object is gone and its row remains |
| **FE-1e** | Activity: `fee_events` writes on all 14 kinds + merged read | Every write route in the module leaves exactly one event row naming its actor; the merged feed is one chronology |
| **FE-1f** | Guards: `require_office_up` → `require_admin`; negative tests | A teacher gets 403 on all 19 admin routes and 200 only on an assigned `followup_detail`; `route_map.py` shows no `require_office_up` in this module |
| **FE-1g** | Web: the area shell + Structure tab | Coverage grid renders every class; an unpriced class reads "not priced"; the editor will not save unbalanced |
| **FE-1h** | Web: Students tab | Class chips from `ClassTabs`; un-enrolled students visible; bulk apply from the selection bar |
| **FE-1i** | Web: the family page | Counterfoil rows, split/add/remove, payment with proof, Conversation + Transactions tabs; `/fees/[id]` redirects |
| **FE-1j** | Dashboard additions + review in the browser | Empty state routes to Structure; by-mode strip reconciles to the collected total; **both themes and mobile checked on the real screen**, not the diff |
| **FE-1k** | Transfer / close a record (`D-127`) | Closing voids the unpaid instalments, drops the payable to what was billed, and removes the student from every collection figure; reopening restores all of it; both leave events |

FE-1k is **last on purpose**. Everything before it is the desk the founder
described; closing a transferred student is an edge case that touches
`core/collection.py`'s three states, and it is safer to change those once the
rest is green and its tests are watching.

Green bar per phase: `uv run pytest -q` + `uv run ruff check app tests`;
`npx tsc --noEmit` + `npm run lint` + `npm run build`.

New tests, alongside the four existing fee suites:

* `test_fee_schedule.py` — the `D-121` invariant, including the property test
* `test_fee_proofs.py` — both storage backends, soft delete
* `test_fee_events.py` — one row per write, actor named
* `test_fees_guards.py` — the negative authorization pass for every route

---

## §10 — Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| ~~`.env` is in `ACTIVE: PRODUCTION` mode~~ — **resolved.** Verified 2026-08-11: `.env` has been in `ACTIVE: LOCAL` since 2026-08-10, `DATABASE_URL` is `trackbit_school_app` (NOBYPASSRLS) on localhost, and the local dev DB is at `d4e5f6a7b8c9a (head)`. ⚠️ CLAUDE.md still claims PRODUCTION mode and is stale | — | Law 2 is genuinely live in this mode, so FE-1a's RLS policies are testable. Re-check the `# --- ACTIVE:` banner before any Alembic run — it is switchable and this doc will go stale the same way CLAUDE.md did |
| **R2 unconfigured in Dokploy** — proofs write to container disk and vanish on the next deploy | Medium | Pre-flight: confirm the four `R2_*` values are injected in Dokploy **before** FE-1d ships. If they are not, gate the proof UI off rather than storing to disk |
| `class_id` backfill misses rows whose `class_name` never matched a real class | Medium | Backfill is best-effort; the matcher falls back to `class_name`, and the coverage grid surfaces any orphan as an unpriced class rather than losing it |
| Structure edit surprises a school mid-year | Medium | `D-118`: never retroactive, and the count of affected students is on screen before Save |
| Splitting an instalment that a payment lands on concurrently | Low | The operation reloads and re-asserts the invariant inside the transaction; a split of a part-paid instalment keeps the paid amount on the first part |
| Scope creep into receipts/PDF generation | Medium | Out of scope, §11 |
| `services/fees.py` grows past 800 lines | Medium | The §8 split happens in FE-1b, not after |

---

## §11 — Out of scope

Explicitly not in FE-1, and each for a reason:

* **Receipt PDF generation** — Plutus deferred it too. The proof feature stores
  what the school already produces; generating a receipt is its own packet.
* **Online payment collection / gateway** — a fence, and a compliance surface.
* **Anything parent-facing.** SPRD2 §11 is binding: the portal is read-only and
  there is no parent-facing chat or AI. A parent seeing their own balance is a
  *separate* founder decision, not something FE-1 assumes.
* **Automatic dunning.** Reminders stay one human press each, with the manners
  already in `CollectionService.remind` — one per week, quiet hours, primary
  guardian only, stops when the payment lands.
* **Teacher access to fees.** Unchanged. `D-83` remains the only door.
* **Fee heads / component-wise fees** (tuition + transport + lab as separate
  lines). Real schools want this eventually; it is a bigger model change and
  nothing here blocks it — `FeeStructure` would gain a child table.
* **Package-tier changes.** Fees stays a Pro feature (`D-106`).

---

## §12 — Questions, answered

All four were settled by the founder on **2026-08-11**. Kept here with the
answers, because the *reasons* the questions existed are what a later reader
needs.

**Q-1 — Per class-section or per class? → PER CLASS.** One structure for "6"
covers 6-A, 6-B and 6-C. This became `D-116` and removed the `class_id` FK the
first draft proposed. The stream case (11-MPC vs 11-BiPC) is served by the
**category** dimension, which already exists — not by sections.

**Q-2 — A student who transfers mid-year? → PROMPT, THEN CLOSE, REVERSIBLY.**
Became `D-127`: unpaid instalments are voided, the balance comes off the total,
status goes to `closed`, and the whole thing can be undone.

**Q-3 — Bulk entry of last year's arrears? → NOT THIS VERSION.** `opening_dues`
stays per-student. A bulk importer comes later; nothing in FE-1 blocks it.

**Q-4 — Receipt numbering? → GENERATE IT, per org and year.** Became `D-128`:
`FR/2026-27/001` from a locked counter row, with the field still editable.

---

## Appendix — files touched

| File | Action |
|---|---|
| `api/alembic/versions/b7c8d9e0f1a2_*.py` | CREATE |
| `api/app/models/fees.py` | UPDATE — `class_id`, `paid_on`, two new models |
| `api/app/schemas/fees.py` | UPDATE — split/add, proof, coverage, activity |
| `api/app/services/fees.py` | UPDATE — trim, batch the N+1, fix filters |
| `api/app/services/fee_math.py` | UPDATE — `assert_balanced`, `rebalance_unpaid` |
| `api/app/services/fee_structures.py` · `fee_schedule.py` · `fee_proofs.py` · `fee_events.py` | CREATE |
| `api/app/api/v1/endpoints/fees.py` | UPDATE — new routes, `require_admin` |
| `api/tests/test_fee_schedule.py` · `test_fee_proofs.py` · `test_fee_events.py` · `test_fees_guards.py` | CREATE |
| `web/src/app/(app)/fees/layout.tsx` | UPDATE — tab shell inside the gate |
| `web/src/app/(app)/fees/page.tsx` | UPDATE — dashboard only |
| `web/src/app/(app)/fees/structure/page.tsx` | CREATE (replaces `structures/`) |
| `web/src/app/(app)/fees/students/page.tsx` | CREATE |
| `web/src/app/(app)/fees/students/[id]/page.tsx` | CREATE |
| `web/src/app/(app)/fees/[id]/page.tsx` | UPDATE — redirect |
| `web/src/components/school/fee-structure-editor.tsx` · `fee-installments.tsx` · `fee-payment-sheet.tsx` · `fee-proof-upload.tsx` · `fee-activity.tsx` | CREATE |
| `web/src/lib/school-api.ts` · `school-types.ts` | UPDATE |
| `docs/architecture/FEATURE-MAP.md` | UPDATE — the fee rows |
