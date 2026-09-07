# FB-1 — field feedback from the first live school

> **Status: SCOPE LOCKED 2026-09-08.** The list below is the whole of it. Anything
> new that arrives from the school goes into a *second* packet, not into this one —
> the point of locking is that we can finish something.

## §0 Cold start — read this first

SHANA International School has been on the app since **17 August 2026**. This is the
first time real teachers have used TrackBit on a real school day, and the WhatsApp
group `Trackbit Shana` is where they report. This packet is the triage of everything
they said **between 18 August and 7 September**.

The raw source — chat export, screenshots, a sample answer-script PDF — is in
`docs/feedback/`, which is **gitignored** (real staff names, real phone numbers, real
student marks). This file is the committed distillation. If you need the evidence,
open the folder; do not copy it in here.

**The one sentence that matters:** most of what looks like "the mentors are not
entering data" is actually **the app refusing to let them**. Three of the four
loudest complaints from the admin (`syllabus is empty`, `exam data is missing`,
`homework not checked`) trace back to two real defects, not to staff discipline.

---

## §1 What they reported

| # | When | Who | What they said |
|---|---|---|---|
| 1 | 18 Aug | Bipin (PT) | "morning Yoga and evening football session left out" |
| 2 | 21 Aug | Tejas | Uploading a class-5 CET answer sheet from Drive → **"Could not read the papers"** |
| 3 | 21 Aug | Kamlesh (admin) | Syllabus board — "please update this as soon as possible" |
| 4 | 21 Aug | Kamlesh | Homework board — "are you checking students notebooks on time, here data is not updated" |
| 5 | 21 Aug | Kamlesh | Exams board — "**all exam data is missing**" |
| 6 | 21 Aug | Kamlesh | Daily report screenshot, no comment |
| 7 | 5 Sep | Geetika | "Kindly **add other subjects** as well under the ABC Category" |
| 8 | 5 Sep | Geetika | "We haven't updated today's daily log because it is showing **School Closed**" |

Carried in from 17 Aug because it is **still open** and is the cause of #5:

| # | When | Who | What they said |
|---|---|---|---|
| 9 | 17 Aug | Geetika | "I tried uploading the test PDF, then the photo — each time it showed **Failed**. I also tried entering the marks manually but **didn't save**." |

---

## §2 Triage

### 🔴 P0 — the app is stopping the work

**FB-1a · An exam block reads as "school closed", so nothing gets logged**
*(report #8, and the likely reason #3 and #5 look empty across the PA2 window)*

`day_lock()` decides a day is closed like this:

```python
# api/app/services/calendar.py:169  (and again at :194 in day_locks)
closed = any(not e.blocks_periods for e in events)
```

Any calendar event with `affects_teaching=True` and an empty `blocks_periods` closes
the **whole school day**. `blocks_periods = NULL` legitimately means "the whole day"
for a *holiday* — but the setup pack marks exam blocks the same way:

```python
# api/app/services/setup_pack/commit.py:574
affects_teaching=kind in {"holiday", "exam_block"}
```

So **PA2 — an exam, on a day the school is open and full of children — renders as
"School is closed today · PA2 · Nothing to mark or log. Enjoy it."** Teachers took it
at its word and stopped logging. Every downstream board then reads as staff failure.

An exam block is a third state, not a holiday: **school open · register still
expected · no regular lesson logs expected · test scores very much expected.**

- Fix `day_lock` / `day_locks` so `exam_block` never sets `closed`.
- Give `DayLock` a way to say *why* teaching is off, so My Day can say
  "PA2 exam today — no regular lessons. Registers and test marks as usual."
- Decide what an exam day expects, and make the daily report and the 16:00 nudge
  agree with it. `calendar.py` is deliberately the ONE answer to "is this period
  still expected today" — keep it that way, do not add a second rule elsewhere.
- Check whether any already-generated daily report recorded an exam day as closed,
  and re-run it if the report is stored rather than computed.

**Done when:** a day carrying only an `exam_block` shows My Day with its periods and
a plain-language exam banner; a `holiday` still closes the day; `pytest` green.

---

**FB-1b · Exam script upload fails, so no exam data exists at all**
*(reports #2, #5, #9 — two different teachers, twelve days apart, still open)*

Both surfaces fail: `exam-capture.tsx:208` ("Could not read the papers") and
`score-capture.tsx:61` ("Upload failed"). Something **throws** — this is not the
graceful `ai_off` path, which returns success with `parse_error="ai_off"`.

Two candidates, and we do not yet know which. This needs a repro against prod:

1. **The content-type gate.** `score_capture.py:156` requires the type to start with
   `image/` or `application/pdf`. Tejas said "from the **drive**" — the Android
   Drive/Files picker frequently hands the browser `application/octet-stream` or an
   empty type, and the endpoint already defaults to `application/octet-stream` when
   the browser sends nothing (`assessments.py:242`). That combination is rejected as
   `bad_page_type` even for a perfectly good JPEG. **Leading hypothesis** — it
   matches "from the drive" exactly.
2. **Storage.** `storage.save_bytes` falls back to `_local_put` when
   `settings.storage_configured` is false, writing into the container filesystem,
   which on Dokploy is ephemeral. If R2 is misconfigured on prod this either throws
   or silently loses every page on the next deploy.

Settle in the same pass: **is `OPENROUTER_API_KEY` set on prod?** Without it
`parse()` returns `parse_error="ai_off"` and the teacher gets *no toast at all* —
neither success nor failure. That is its own defect: the screen must say "photos
saved, marks could not be read automatically — type them in", not go quiet.

- Reproduce with the real artefact: `docs/feedback/.../G7 S.St CET 4 Rakesh.pdf`.
- Sniff the actual bytes rather than trusting the browser's content-type; accept a
  file whose type is missing or `octet-stream` when it sniffs as an image or a PDF.
- Verify R2 config on prod, and that an uploaded page survives a redeploy.
- Make `ai_off` a visible, honest state on both capture surfaces.

**Done when:** a photo and a PDF both upload from an Android Drive pick on prod, the
page survives a redeploy, and every failure path shows a sentence a teacher can act on.

---

**FB-1c · Manual marks do not save**
*(report #9 — "I also tried entering the marks manually but didn't save")*

Unreproduced and unexplained. It may be a consequence of FB-1b (no capture row to
attach to), or the confirm call failing quietly, or the save control sitting under
the fixed mobile nav. **Do not close FB-1b and assume this went with it** — it is the
fallback path that has to work when the camera route fails, so it is P0 on its own.

**Done when:** typing marks for a class on a phone, with no photo at all, saves and
survives a reload.

---

### 🟠 P1 — the app is telling the truth badly

**FB-1d · My Day contradicts itself on a closed day**
*(visible in report #8's screenshot)*

`web/src/app/(app)/my-day/page.tsx:428` renders the `otherClasses` section — headed
"Today's classes", with live **Covered / Partially / Set homework** buttons —
directly beneath "Nothing to mark or log. Enjoy it." The closed-day guard covers
`periods` but not `classes`. Whatever FB-1a decides a closed day means, this section
has to obey it.

**FB-1e · The daily report prints a literal `?`**

```python
# api/app/services/daily_report.py:227 and :231
f"{cs_meta.get(csid, (None, '?'))[1]} had attendance but no lesson log — was it logged?"
```

The admin's 21 Aug report reads "**? had attendance but no lesson log**". A missing
`cs_meta` entry leaks its placeholder into the school's daily report. Find why the id
is missing — the likely culprit is a register taken against a class with **zero
`class_subjects`** (prod 11-A/12-A, already on record) or an assembly / `school_roll`
register from TT-6, which has no class-subject by design. Then either name the class
properly or drop the line; never print `?`.

**FB-1f · "1 children are in Band C"**

`api/app/services/bands.py:613` hard-codes the plural. The file gets this right three
lines above (`child{'' if moved_up == 1 else 'ren'}`) — apply the same there.

**FB-1g · Numbers that argue with each other.** Each needs ten minutes of verifying
against the real org before we decide whether it is a bug or a true-but-ugly reading:

- **Syllabus tile** (report #3): `OF WHAT IS PLANNED —` above `10 of 0 scheduled`,
  with `24 class-subjects · nothing scheduled yet`. A zero denominator is being
  rendered as if it were a figure. `core/coverage.py` owns this, and a
  `CoverageFigure` carries its denominator precisely so this cannot happen — find
  which surface is bypassing it. Per house rule, not-scheduled is a **word**.
- **Daily report** (report #6): `PLAN PACE — All classes on pace` on a day the
  syllabus board says nothing is scheduled at all. "On pace" against an empty plan
  is a false all-clear, and it is the most misleading line on the page.
- **Daily report**: "21 classes still unlogged", but the `Not logged:` list names
  six, with no "+15 more".
- **Exams trajectory** (report #5): the caption says "a subject with a single test
  has no trajectory and is left out", then draws Biology 95% as a flat line from
  18 Aug to 19 Aug. One of the two is wrong.
- **ABC bands overview** (report #7): headline "1 children are in Band C" against a
  donut reading `C 17% · 3`, above `18 placements across 3 subjects · 18 of 18
  children assessed`. Confirm whether placements are being counted as children in
  `services/insights/bands.py:187`.

**FB-1h · Toasts sit on top of the mobile bottom nav.** Cosmetic, visible in two
separate screenshots. Fix it while we are in there.

---

### 🟢 P2 — asked for, and mostly already possible

**FB-1i · More subjects under ABC bands** *(report #7)*

Not a missing feature. `Subject.band_monitored` is configuration by design
(`models/academics.py:93-97`), and an **admin** can already toggle it at
Settings → Support (`PUT /bands/setup/monitored`, `require_admin`). Geetika is a
teacher, so she cannot — and the bands screen only tells her "Choose them in Setup →
Settings → Support" when *nothing* is monitored, never when three subjects are.

- **Do now, no code:** have Kamlesh switch on the subjects the school wants.
- **Then:** make the path discoverable from the bands screen for an admin, and make
  the subject line ("Term-2 · English, Hindi, Maths") legible as *the monitored set*
  rather than as a limit.

**FB-1j · Morning yoga and evening football are still not in the timetable**
*(report #1 — promised on 17 Aug and not delivered)*

Bipin runs 06:20–07:00 and 18:00–19:00 for **all hostellers**. TT-5 blocks plus the
`D-129` student category should express this exactly. Before writing any code, check
whether the bell schedule accepts entries **outside the school day** — if it does,
this is configuration; if it does not, that is the packet.

Assembly (17 Aug) already shipped as TT-6.

---

### ⚪ Not a defect — report back, do not build

**Reports #3 and #4 are the product working.** Arti 0 checked of 3 set, Tejas 0 of 9,
syllabus at 3% — those are true numbers about staff behaviour, and the admin used the
board exactly as intended and chased his mentors. Nothing to fix.

The honest caveat we owe Kamlesh: **part of that emptiness is ours**, via FB-1a and
FB-1b. Worth saying so in the group when the fixes ship, so the mentors are not left
carrying blame for a bug.

---

## §3 The todo — locked

Order is by "is the school blocked", not by size.

- [x] **FB-1a** exam block ≠ school closed — *plus the off-timetable recorder, below*
- [x] **FB-1b** exam script upload: magic-byte sniffing, honest `ai_off`
      *(⚠️ prod storage still unverified — see §3.1)*
- [x] **FB-1c** the disabled Save button now always says why
      *(⚠️ the original report is still unreproduced — see §3.1)*
- [x] **FB-1d** My Day obeys the closed day everywhere
- [x] **FB-1e** no `?` in the daily report — a block was leaking in as a `None`
- [x] **FB-1f** "1 child is in Band C"
- [x] **FB-1g** four of the five figures fixed; the fifth was not a bug
- [x] **FB-1h** toasts clear the bottom nav
- [x] **FB-1i** the monitored set is named, and the way to change it is on the screen
- [x] **FB-1j** verified as configuration — no code needed, recipe in §3.2

### §3.1 What is NOT closed, despite the ticks

Two things were fixed by reasoning from the code and the screenshots, and have
**not been confirmed against the live school**. Do not tell SHANA they are done
until somebody has watched them work on prod:

1. **Is R2 configured on prod?** `storage.save_bytes` silently falls back to
   `_local_put` when `settings.storage_configured` is false, writing into the
   Dokploy container's own filesystem — which is ephemeral. If that is the
   state, every uploaded script disappears on the next deploy and the
   content-type fix will not have solved the complaint. **Check
   `R2_*` on the Dokploy app, upload a page, redeploy, and re-open it.**
2. **`FB-1c` is a plausible fix, not a reproduction.** The exhaustive hint kills
   the specific dead end we can see in the code — a disabled button with an
   EMPTY explanation when the subject or the total is missing. Geetika's actual
   session is still unknown. Ask her to try again and say what happens.

Also unverified: whether `OPENROUTER_API_KEY` is set on prod. Without it the
photos still upload and the teacher now gets "Photos saved — type the marks
below", which is correct behaviour either way, but the school is doing OCR by
hand and does not know it.

### §3.2 FB-1j — the recipe, no code required

Everything Bipin asked for on 18 August already exists:

| Session | Block kind | Why |
|---|---|---|
| Morning yoga, 06:20–07:00 | `assembly` — literally labelled **"Assembly / yoga"** | Takes the school register, filed to every class (TT-6) |
| Evening football, 18:00–19:00 | `sports` | Its own roll, its own roster |

Both are hostellers-only, which is `sessions.category_id` → the Hostellers
category (`D-129` — set it by **id**, never by matching the name, or renaming
the category empties the roll). The bell schedule validator only requires each
row to have a start before its end and to sit in order, so **06:20 and 18:00 are
accepted**; the school day does not have to contain them.

So this is a setup task, not a packet. Do it with Kamlesh on a call.

## §4 Standing rules for this packet

- Every fix lands with a test. `pytest` + `ruff` for the API; `tsc --noEmit` +
  `eslint` + `next build` for the web. The full backend suite is the regression gate.
- **Look at the built screen.** Every item above was found by a teacher looking at a
  page, not by anyone reading a diff.
- Nothing here needs a migration as currently scoped. If one appears, grep
  `alembic/versions/` for a free revision id first.
- `docs/feedback/` never gets committed and never leaves this machine.

## §5 Open questions for the school

1. Which subjects should ABC bands cover — all of them, or a chosen set per term?
2. Are yoga and football **every** day, and is the roll for them all hostellers or a
   named group?
3. On a PA2 exam day: is the register still taken as normal, and by whom?
