# What to check once the school is set up

Work down this list with the app open. It walks every module the product has, at
the size it will actually run at — 8 classes, 60 class-subjects, 240 students,
24 teachers, 66 hostellers.

Each block says **what to do**, **what should happen**, and — where it matters —
**the principle it is proving**. A box that doesn't behave is a finding; write it
down with the class/subject/date so it can be reproduced.

Three teacher logins are worth keeping open (passwords from setup step 5):

| Login | Who they are | Why |
|---|---|---|
| `sis.meena.iyer` | English, classes 1–2 | busiest teacher, 22 periods/week |
| `sis.anjali.gupta` | Science, classes 7–8 | senior classes, band/score work |
| `sis.vikram.singh` | Maths 5–6 + senior evening prep | teaches **and** wardens |

---

## 1. Does it hold 8 classes without getting slow?

The old demo org had 4 classes and 54 students. This one is ~4.5× that, on a
remote database where every query is a network round-trip.

- [ ] **Dashboard** — time the first paint. Anything over ~3s is worth noting.
- [ ] **Plan → Classes** — the overview loops per class in places; this is where
      a per-class loop over 8 classes × 8 subjects shows up.
- [ ] **Students** directory with 240 rows — search, group-by-class, and the
      class/category/status filters should stay instant.
- [ ] **Plan → Timetable** — 8 grids of 48 cells.
- [ ] Note anything that fires a visible burst of requests (the network tab is
      the honest answer here).

## 2. Admin's morning — Dashboard & the daily report

- [ ] **Dashboard** leads with the **daily report** (risks first, sections
      expandable). It should exist even with no AI key — the deterministic
      aggregation is the report; the model only phrases it.
- [ ] The **RAG board** shows all 60 class-subjects, none of them red on day one.
- [ ] **Nothing from before 20 July appears as a problem.** No "missing
      attendance" for June. *Pre-adoption is no-data, never a warning.*
- [ ] The **fee card is visible to you as admin**. Log in as a teacher and
      confirm it — and the whole Fees nav item — is **gone**.
- [ ] Turn an alert into a task in one tap; it lands on a board.

## 3. Teacher's day — My Day and the period page

Log in as **`sis.meena.iyer`**.

- [ ] **My Day** lists today's periods from the timetable as tappable rows —
      hers should be classes 1 and 2 only, never a class she doesn't teach.
- [ ] Open a period. **Count the taps.** *P1v2 budget: a routine period is
      ≤ 5 taps / ≤ 30 seconds.*
  - [ ] **All present** is one tap. The exception sheet cycles
        present → absent → late per student, and only deviations are stored.
  - [ ] **Topic** is picked from her syllabus list, grouped by chapter, with
        ✓/◐ markers for what's already covered — not typed free-hand.
  - [ ] **Homework** — class-wide, and per-student for one child.
  - [ ] **Checks** — the recommendation is already there with **zero setup**.
        "Class did it ✓" is one tap; flagging exceptions is the sheet.
  - [ ] **Not held** works and reads differently from "nobody was marked".
  - [ ] The **deep log** (observations) is genuinely optional and exception-only
        — flag two students, leave the other 28 alone.
- [ ] Mark an absence in the **first** period of the day → the guardian alert
      fires once (console/WhatsApp stub). Mark another period → **no second
      alert** for the same child.
- [ ] The alert text carries **no band information**. *P4.*

Then as **`sis.anjali.gupta`**: her My Day is classes 7–8. Confirm she cannot
reach class 3's period page by URL (`not_your_student` / 403 on the student side).

## 4. Plan — the pillar

- [ ] **Plan → Year**: calendar, holidays, exam blocks, exam-fit panel.
      The two partial exam blocks (Unit Tests) should cost **3 periods**, not a
      whole day — the effective-days count reflects that.
- [ ] **Plan → Week plan**: pick class 6 → every period in the week shows its
      planned topic.
- [ ] The topic you logged in step 3 now shows as **actual** on that cell, next
      to the baseline. *P2: the plan is the baseline, the log is the actual —
      the forecast is recomputed, the plan rows are never rewritten.*
- [ ] **Plan → Classes**: all 60 class-subjects **on track**. None reading
      `unallocated`, `not sized`, or `unplanned`.
- [ ] **Plan → Syllabus**: open class 8 Science — 18 chapters, every topic sized.
- [ ] **Plan → Timetable**: class grid for admin; a teacher sees only their own
      week, read-only.
- [ ] Deliberately break it: set a class-6 slot to a teacher already busy that
      period. The **clash validator** should refuse, deterministically, naming
      the other class.
- [ ] **Extend a plan**: add a chapter to class 5 Maths and use *Schedule new
      chapters*. It must append **after** the locked entries — the approved
      baseline never moves.

## 5. Recommendations & checks at scale

- [ ] Open period cards in three different classes. Each has its own checks,
      generated from the planned topic × the class's band distribution — with no
      teacher setup anywhere.
- [ ] The volume is capped: ≤ 2 class-wide + 1 richer C-band + ≤ 1 per
      intervention student. If a card shows six checks, that is a finding.

## 6. Students — the per-student truth

- [ ] **Students → Directory**: 240 rows, grouped by class by default.
      Search a name; filter Hosteller (66); filter by class.
- [ ] Open a student → **growth report**: attendance, chapters taught, chapters
      **missed while absent**, homework (incl. personal), check flags,
      observations, test scores, skill profile.
- [ ] Expand a chapter → per-topic taught-date and whether *this* child was there.
- [ ] **Timeline**: today's periods for that student, built from the timetable ×
      attendance × logs × checks × homework × sessions. Absent periods show as
      **gaps**. *No new capture table — it is all computed.*
- [ ] As a teacher, open a student from a class you don't teach → **403**.

## 7. Scores, exams & bands

- [ ] **Students → Scores** → class card → **Whole class** tab. Drop a photo or
      PDF of a marks sheet *before* typing anything — the draft capture should
      prefill title/subject/total and match marks to names, then hand you a
      review step. (No AI key = the deterministic path; note which you tested.)
- [ ] **Few students** tab: pick 8 of the 30 first, then enter marks.
- [ ] Save → the exam appears in the feed with avg %, scored/roster, evidence
      pages, author. Reopen it and edit — full replace.
- [ ] **Students → Bands**: set A/B/C thresholds, record a `band_test` for class
      7, then **categorize**. The class re-tiers into three columns and the new
      band rows **name the source test**.
- [ ] Change a band → history keeps the old row. *Law 3: append-only, never
      overwrite.*
- [ ] **Bands appear nowhere a guardian can see them.** Check the absence alert,
      the Saturday guardian note, and the homework notification. *P4.*
- [ ] **Trends**: weak-subject detection feeds a dashboard alert.

## 8. Hostel — 66 boarders

- [ ] **Plan → Hostel**: the 6 blocks in a week grid.
- [ ] Open *Evening Prep (seniors)* as **`sis.vikram.singh`** → the roster is
      **computed**: hostellers of classes 5–8 only. Nobody picked them by hand.
- [ ] `kind` changes the surface: **study** = optional per-row notes,
      **homework** = tonight's homework board, **activity** = memories only.
- [ ] Upload a class photo, then a video. The big-file path presigns and PUTs
      direct to R2; ≤ 25 MB goes through the app. If `R2_*` isn't configured,
      confirm the dev fallback rather than a silent failure.
- [ ] Open one student's card from the roster → attendance + homework + sectioned
      study log + their own media, in one round trip.
- [ ] **My Day** for a warden shows a **This evening** section.
- [ ] *Sunday Games* sits on a non-working day — confirm the block is allowed and
      renders (the teaching week stops on Saturday; hostel life doesn't).

## 9. Tasks

- [ ] **Tasks → Today / Boards / Done**. The Maintenance and Housekeeping board
      templates ship with the seed — confirm they're here for a fresh org too, or
      note that they aren't.
- [ ] Create a recurring template; confirm instances materialize ahead and the
      `(template_id, occurrence_date)` guard stops duplicates.
- [ ] A **private board** stays invisible to an admin who isn't a member. *Law 5
      — this is deliberate, not a bug.*

## 10. Fees

- [ ] 8 structures entered; enrol a class-8 hosteller → ₹1,28,000 over 3
      installments.
- [ ] Take a payment, apply a discount, then **undo** the payment.
- [ ] The ledger shows a **compensating row**, not a deleted one. *Law 3.*
- [ ] Teacher login: no Fees nav, and `/fees` by URL is refused.

## 11. Lucy

- [ ] `/lucy` gates politely if there's no AI key. With one:
- [ ] Ask a read question — "which class-subjects are behind?" — and check the
      **numbers in the widget match the module screen**. The model chooses the
      widget; the data comes from the stored tool result, so it cannot type a
      number in.
- [ ] Ask for a **write** — "add a task to fix the class 6 projector". It must
      come back as a **confirm card**; nothing is written until you tap it.
- [ ] As a teacher, ask a fee question → refused by the same fence as the UI.
- [ ] Pin a widget → it appears on the Lucy landing board and refreshes live.
- [ ] An admin cannot read a teacher's conversations.

## 12. Jobs & notifications

Fire these from `/ops/run/*` rather than waiting for the clock:

- [ ] **Teacher reminder (16:00)** — unmarked/unlogged periods go to that
      teacher, not to everyone.
- [ ] **Daily report (19:00 draft / 06:00 regen / 08:00 notify)** — regenerating
      never overwrites a report already marked `final`.
- [ ] **Saturday guardian summary** — plain, no band info.
- [ ] Everything is idempotent: run each twice, confirm no duplicate messages.
      *One scheduler instance only — two gunicorn workers would double every
      guardian's WhatsApp.*

## 13. Platform layer

- [ ] Back as `super@trackbit.app` → `/platform` lists Sunrise with live stats
      (students, teachers, classes).
- [ ] Create a second throwaway school → confirm **no data bleeds** between them:
      classes, students, plans, Lucy conversations.
- [ ] The org admin (`principal@sunriseintl.edu.in`) **cannot** reach `/platform`.
- [ ] The setup **wizard tab is operator-only**.

## 14. The cross-cutting rules

Worth one deliberate pass, because they're the product's spine:

- [ ] **P1v2** — no screen anywhere requires per-student entry for a whole class.
      If one does, that's a design bug, not a UI nit.
- [ ] **P2** — nothing you logged mutated a plan row.
- [ ] **P3** — logging homework notified the guardians without extra work.
- [ ] **P4** — bands never left the staff surfaces.
- [ ] **P5** — you never wrote a report; the report wrote itself from the day.
- [ ] **Law 1** — no screen let you act on another org's data.
- [ ] **Law 3** — every undo you tried was a new row, not a deletion.

---

## Recording findings

For anything that misbehaves, note: the screen, the class/subject/student, the
date, what you expected, what happened. If it's a number that looks wrong, the
fastest check is usually the same number on the module screen the widget or
report drew it from.
