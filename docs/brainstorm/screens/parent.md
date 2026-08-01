# Screens — Parent

The read-only portal. Its own shell, its own mobile-first layout, no staff nav. Four tabs and a
sibling switcher.

**Who the parent is:** a phone user on a weak connection, opening the app in a spare minute —
often in the evening, often while asking their child a question they already know the answer to.
They are not analysts. They arrive with **one** question and they want it answered in the first
screenful, in a sentence.

**The hard fences, on every screen here:**

| Rule | |
|---|---|
| **Read-only** | no writes of any kind, unless `Q-01` reverses it |
| **Curated projection** | everything goes through the allowlist in `parent_portal.py` — field by field, never a spread, so a new staff field cannot reach a parent by accident |
| **Never a band** | P4. Not on a screen, not in a message, not in an export |
| **Never per-period attendance** | parents get a **daily** status; the period detail is a staff concept |
| **Never another child** | siblings switch explicitly |
| **No AI, no chat** | Lucy is staff-only |

---

## `Login` — `/parent/login`

**Status:** CHANGING (replaces phone-OTP) · **Refs:** `D-13` `S-55` `S-56` `S-57` ·
**Blocked on** `Q-24` `Q-25` `Q-27`

**Arrives asking:** *"How do I get in?"* · **Leaves having:** a session that lasts until they
log out.

**Context:** once, ever. Usually while holding a slip of paper the school gave them.

### The flow (`D-13`)
```
  school code  →  class  →  section  →  child  →  date of birth  →  in
```

### Two changes that keep the flow identical and fix what breaks it
- **`S-55` — the child step is type-to-search, not a browsable list.** A dropdown of every child
  in the section hands the whole roster to anyone with a school code, *before* any password.
  3+ characters and a match. A parent knows their child's name; nobody needs to browse.
- **`S-56` — lock after 5 attempts, throttle per hour.** A date of birth is ~5,500 guesses and
  the picker names the target. The OTP module's lock already does exactly this and already
  survives request rollback — reuse it, keyed per student.

### States
| State | Shows |
|---|---|
| Unknown school code | *"We don't recognise that code — check with the school office."* Never *"no such school"* with a hint. |
| No DOB on record (`Q-24`) | **Must have an answer.** *(verified)* `students` has no DOB column today, so every student starts here. Suggest: *"Ask the office to add your child's date of birth."* |
| Wrong DOB | Attempts remaining, then a lock with a phone number to call. |
| Second child (`Q-25`) | *"Add another child"* — prove each once, then the sibling switcher works as it does today. |

### Deliberately not here
Self-registration · a password anyone can reset by email · anything that reveals whether a
student exists before the DOB is entered.

## `Today` — `/parent`

**Status:** CHANGING · **Refs:** `S-11` `S-25` `Q-01` `Q-03` `Q-04`

**Arrives asking:** *"Was my child in school today, and is there anything I should do tonight?"*
**Leaves having:** checked the homework, or knowing to call the school.

**Context:** evening, phone, one minute, possibly with the child in the room.

### What's on it today *(verified)*
One daily status line (present / partial / absent / not marked / no school) → taught today →
last homework and its verdict → still to do → homework set today → evening sessions.

The tone is already right — `not_checked` is worded as *"not checked yet"*, the teacher's pending
action, never as something the child failed to do. **That care should be the model for every new
line added here.**

### What's missing: the pattern (`S-11`)
A parent gets today, and today only. They cannot see whether this is unusual. Add:

- a **month calendar strip** — the one chart every parent reads instantly, no legend needed
- **"present 18 of 21 school days this month"** — the sentence version of the same fact
- **the reason, if the school recorded one** — so a parent who phoned the office at 8am sees
  that it was heard. *This is the quiet payoff of `D-02`: the reason field is not just admin
  bookkeeping, it closes a loop with the parent.*
- if `Q-04` says yes, the minimum-attendance line — *"needs 75%, currently 82%"* — which is the
  one number a parent will act on

### `S-25` — "tell the school why"
A **`tel:` link** on the absence card (WhatsApp is out — `D-08`). **Zero writes, fence intact**,
and it is what makes `D-02`'s reason field actually get filled. Depends on `Q-01`.

### Session 4 — homework (`D-35`, `S-90`, `S-94`, `Q-39`)

**When the child was absent, the homework is shown — yellow, pending (`D-35`).** Not hidden, so
the parent knows class was missed and there is work outstanding; **not red**, because nothing was
refused. This matches `D-02`'s colour language exactly — yellow is *known and being handled*, red
is *nobody has explained this* — so a parent now reads one palette across attendance and homework.

Two things this needs to stay honest:
- **It must be able to clear.** `D-34` lets the teacher decide the backlog isn't required and set
  fresh work instead; that outcome has to reach this screen (`S-98`), or the yellow becomes
  permanent and the parent learns to ignore it.
- **The wording is "pending", not "missed".** The child was not there. `ux-principles` §10 —
  states stay words.

**Split "still to do" from "missed" (`S-94`).** *(verified)* the pending list keeps a `not_done`
item with no due date for the whole eight-day window, so work that was simply missed sits beside
work that is upcoming, looking like it can still be handed in. Two clearly worded lines — and the
*missed* one carries **no red**: it is a fact, and the child may well have finished it since.

**A miss is worth a message only as a pattern (`S-90`, `Q-39`).** Today the parent hears when
homework is **set** and never when it was **not done**; `homework_results` names the child, so the
message is possible. Recommended threshold: **two consecutive homework days missed** — the same
one the admin's red list uses, and the same shape as `D-02`'s absence rule. A message for every
forgotten worksheet makes the school a nag and trains parents to mute it. Delivery is in-app plus
web push (`D-08`, `D-14`), and *(verified)* `add_homework`'s existing notify call is one of the
three WhatsApp stubs still needing that destination.

**What must not change:** *(verified)* `not_checked` reads neutrally here and its badge is
suppressed in the pending list. HW-1's rule — a missing check is the teacher's pending action,
never the child's failure — survives into this UI, and it is the thing most likely to be broken by
someone tidying the copy.

### States
| State | Shows |
|---|---|
| Not marked yet | *"Teachers mark attendance during the day — check back later."* Never a zero, never a red. |
| No school | *"No school periods today."* |
| Absent, no reason on file | the fact, calmly, plus the "tell us why" link |
| Absent AM, present PM (`Q-03`) | needs its own wording — "partial" is not what a parent needs to read |

### Deliberately not here
Which periods were missed · which teacher marked it · the class's attendance · anything
comparative. A parent asking *"how does my child compare"* is a conversation for a teacher, not
a screen.

---

## `Progress` — `/parent/progress`

**Status:** CHANGING · **Refs:** `D-11` `S-03` `S-48` `S-51` `S-54` `Q-16`

**Arrives asking:** *"What are they learning, and how far have they got?"*

Per subject: syllabus covered (meter bar), attendance %, homework count, last test. Clean today,
and it already honours `D-11` — **no pace, no RAG, no weeks-behind, nowhere.**

### Changes
- **Name the chapter, not just the percentage** (`S-48`). *"This week in Maths: Fractions —
  addition and subtraction"* beats *"58% covered"*, because it is the thing a parent can ask
  their child about at dinner. Derivable from lesson logs today.
- **Use a denominator that only goes up** (`S-54`, `Q-16`). Coverage against *planned* topics
  **falls** when the school sizes next term's chapters — nothing was un-taught, but a parent
  reads it as the school going backwards. Parent coverage should be against the whole syllabus.
- **The attendance % must state its denominator** (`S-03`) and must be the same number the Today
  tab implies — which today it is not, because one is period-based and the other day-based.
- ⚠️ **The admin's "syllabus covered" and this one are computed differently right now** —
  different numerator *and* denominator (`S-51`). Same phrase, two numbers, same day.

### Deliberately not here
That the school is behind · weeks-behind · RAG colours · other children · other classes ·
anything that would make a parent phone the principal about a teacher's pace (`D-11`).

---

## `Report` — `/parent/report`

**Status:** EXISTS · **Refs:** `Q-04`

**Arrives asking:** *"Give me the whole picture."*

The curated growth projection — coverage, chapters missed while absent, verified scores, derived
strengths and growth areas. **"Missed while absent" is the best thing on any parent screen in
the product**: it converts an absence from a compliance fact into an academic consequence a
parent understands. Worth reusing that framing anywhere else absence is shown.

**May add:** the minimum-attendance line, if `Q-04` says yes.

---

## `Notifications` — `/parent/notifications` · **NEW**

**Refs:** `D-08` `D-13` `D-14` `S-61` `S-62`

**Arrives asking:** *"Did the school tell me anything?"*

**`D-08`: no WhatsApp in this version.** Guardian messaging is delivered in-app, and this tab is
where a parent reads it — absence alerts, homework set, the weekly note.

*(verified)* Today `notify_guardian.py` is a WhatsApp stub that logs to the console when no keys
are set, and it is what the absence alert, the homework notification and the Saturday summary
all call. All three need this destination instead.

### Settled
- **Reach — `D-14`: web push.** That is what makes an in-app notification actually arrive.
- **Login — `D-13`:** school code → class → section → child → date of birth. See the Login screen.

### Two design consequences
- **`S-61` — the Today tab should *be* the notification surface.** A parent who opens it once a
  day should have seen everything. This tab is then the **archive**, not the delivery mechanism,
  and nobody has to check two places.
- **`S-62` — push is best-effort; the absence alert is not.** iOS needs the site installed to the
  home screen before push works at all, permission can be denied, phones are off. So the alert
  that matters most is the least reliable. The admin's board should show **who was not
  reachable**, so the office can phone those few. *(That is the honest version of removing
  WhatsApp: the reach problem doesn't vanish, it becomes visible.)*

### Deliberately not here
Replies. The portal is read-only (`Q-01`) — a notification a parent can answer is a messaging
product, and that is a different decision.

## `Profile` — `/parent/profile` · **EXISTS**

Child details and the sibling switcher. Siblings roll up automatically — one phone number links
every guardian row it matches.

---

## `Fee reminder` — block on `/parent` (Today) · **NEW**

**Role:** parent · **Status:** NEW
**Refs:** `D-66` `S-156` `S-160` `Q-69` `Q-70`

**Arrives asking:** *"How much do I owe, and by when?"*

**Leaves having:** knowing the number and the date — and, if they want, the school's phone number
to arrange it.

**Context of use:** evening, phone, weak connection, often after a notification landed. Read by a
family that may be having a hard year. **Tone is the whole design here.**

### What's on it, in order

A **block on the Today screen**, not a tab of its own — the founder's *"shown on their homepage
dashboard as a reminder"*. It renders **only when something is actually due**:

1. **One line** — *"Term 2 fee · ₹12,000 · due 15 August"*
2. **What's already paid this year**, so the family sees credit not just debt — *"₹36,000 paid so
   far"*
3. **How to pay** — the school's number / office hours. A `tel:` link, nothing more.

That's it. **Not a ledger** (`S-160`) — the transaction history is the office's screen. `PC-1`'s
curated allowlist means every field here is added deliberately, field by field, never a spread.

### Actions

- **Call the school** → `tel:`. That is the only action, because `PC-1` is read-only and this
  version has no payment path (`D-62`).

### States

| State | What the parent sees |
|---|---|
| Nothing due | **The block does not render.** A parent who owes nothing should never see a fee section — its presence alone reads as a demand. |
| Paid in full for the year | *"Fees paid in full. Thank you."* Once, then it stops rendering. |
| Overdue | Same block, same tone, with the date it was due. **Never red, never a warning icon, never "DEFAULTER".** |
| Two children | One line per child, under the sibling switcher that already exists. |
| Full concession | Nothing renders (`S-158`) — they owe nothing. |

### The notification (`D-66`)

Same content, same tone, and **the manners matter more than the message** (`S-156`): at most one
per instalment per week however many staff press the button, never before 8am or after 8pm, it
**stops the instant the payment lands**, and it never goes to a guardian with `notify_opt_out`.

*A parent reminded three times in a morning about money will not read the fourth message about
their child's attendance.* That is the real cost of getting this wrong — it damages every other
channel the school has.

### Deliberately not here

A transaction ledger · a receipt · **any online payment** (`D-62`, and a parent write reverses
`PC-1`) · another child's fees · the school's collection figures · any comparison to other
families · a late fee or penalty calculation.

---

## Open for this role

- **`Q-21` / `Q-22`** 🔴 — how an in-app notification actually reaches a parent, and how a parent
  logs in at all now that WhatsApp is out. `Q-22` blocks the whole portal in this version.
- **`Q-01`** — does a parent ever *submit* anything (an absence note)? The fence question for the
  portal; blocks `D-02`'s shape.
- **`Q-16`** — which denominator the parent's "syllabus covered" uses.
- **`Q-19`** — does "taught while your child was away" stay, given `D-11`?
- **`Q-04`** — is the minimum-attendance rule shown to parents, or admin-only?
- **Fees** — no fee view; scoped as "PC phase 2". Worth its own session: *"how much do I owe"* is
  arguably the parent's second question after *"was my child in school"*.
- **Notifications as a module** — now that delivery is in-app (`D-08`), the notification surface
  and the portal are the *same product*, not two. They should be brainstormed together.
