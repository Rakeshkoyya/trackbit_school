# TrackBit — Product Architecture

**The Academic Health Layer for Schools** · v1.1 — folded in the director's pain-point review (July 2026)

> TrackBit tells a school director whether teaching is on plan and which students are slipping — early enough to act — while asking each teacher for less than a minute a day.

---

## 1. What TrackBit is (and is not)

TrackBit is **not** a school ERP. It does not replace the school's records, admissions, attendance, or timetable software. It sits **beside** whatever the school already uses and answers the one question no ERP answers:

**"Is my school actually teaching well, right now?"**

### Design principles (every feature must pass all five)

1. **One-minute teacher budget.** No teacher spends more than ~1 minute/day feeding the system. If a feature needs more, it is redesigned or cut.
2. **Plan is baseline, log is actual.** The system re-forecasts automatically ("at current pace, Ch. 12 finishes 3 weeks after exams"). Nobody manually maintains the plan.
3. **Teachers get value before they give data.** Every capture action pays the teacher back immediately (e.g., logging homework auto-notifies parents — no more 40 diaries).
4. **Bands are private intervention tiers, never labels.** A/B/C grouping is visible to staff only, always framed as support tiers with movement goals.
5. **Nobody writes a report.** Every report is a byproduct of doing the work — captured at the moment of action, with evidence (a tap, a count, a photo). If someone has to "report to" someone, the design is wrong.

---

## 2. Coverage — the director's pain points

From the director's list of 18 school pain points (July 2026), the ten we focus on map directly onto the modules:

| # | Pain point | Where it lives |
|---|---|---|
| 1 | Task management | **M5** — built |
| 2 | Annual calendar | **M1** Academic Planner |
| 3 | Timetable (creation) | Fenced for v1 — parked, see §8 |
| 4 | Fee collection | **M6** — built |
| 5 | Daily / international day celebrations | **M1** day-celebration engine |
| 6 | Teacher KPI over time | **M4** teacher growth profile (derived — no new capture) |
| 7 | Class academic plan | **M1** Academic Planner |
| 8 | Student categorization A/B/C | **M3** Bands |
| 9 | Student homework tracker | **M2** Classroom Log |
| 10 | Student performance — test scores | **M3** Assessments + diagnostic intake |

Of the remaining eight: **repair/maintenance (11)** and **cleaning (15)** ship as ready-made board templates on M5 — zero new code. **LMS (17)** and **NEP/NCF teacher training (18)** are Playground's lane (the director's interest here is future cross-sell validation, not a merge). Visitor tracker, purchases/inventory, social media insights, and sports/health records stay fenced (§8).

---

## 3. Roles

| Role | Who | What they do in TrackBit |
|---|---|---|
| **Director** (org admin) | Owner / principal / director | Annual planning, dashboard review, assigns interventions, sees fees summary |
| **Coordinator** | Academic coordinator / vice principal | Plan upkeep approvals, marks verification, logging compliance, band reviews |
| **Teacher** | Subject & class teachers | 30-second daily log per class, sessions, homework, marks, C-band checklists |
| **Office Staff** | Admin / accountant | Fee collection, receipts, defaulter follow-ups (existing Fees module) |
| **Parent** | — | **No login in v1.** Receives homework & weekly notifications on WhatsApp/SMS |

---

## 4. Module map

```
                    ┌─────────────────────────────┐
                    │  M1  ACADEMIC PLANNER        │  ← the baseline (setup, once/term)
                    │  calendar · syllabus · days  │
                    └──────────────┬──────────────┘
                                   │ plan flows down
                    ┌──────────────▼──────────────┐
                    │  M2  CLASSROOM LOG+SESSIONS  │  ← the "actual" (30 sec/day/class)
                    │  lesson · homework · session │──► parent notifications
                    └──────────────┬──────────────┘
                                   │ plan vs actual
      ┌──────────────┐  ┌─────────▼──────────────┐
      │ M3 ASSESSMENTS│─►│  M4  DIRECTOR DASHBOARD │  ← the insight
      │ diagnostic ·  │  │  RAG · alerts · digest  │
      │ marks · bands │  │  teacher growth profile │
      └──────┬───────┘  └─────────┬──────────────┘
             │ interventions       │ problems become actions
      ┌──────▼───────────────────▼──────┐
      │  M5  TASKS (existing)            │  ← the action layer (+ ops templates)
      └──────────────────────────────────┘

      ┌──────────────────────────────────┐
      │  M6  FEES (existing)             │  ← standalone revenue anchor
      └──────────────────────────────────┘
```

The core loop: **M1 sets the plan → M2 records reality → M3/M4 detect gaps → M5 assigns the response → M4 shows whether it worked.**

---

## 5. Modules in detail

### M1 — Academic Planner (the year compiler)

*User: Director + Coordinator. Frequency: once per term + occasional edits.*

**What the school achieves:** the entire academic year compiled against *real* available teaching days — the annual planning ritual the director already does on paper, digitized and kept alive all year — plus a school that never misses a day worth celebrating.

**Features**
- School calendar: working days, holiday list, exam blocks, events (annual day, sports day) with teaching-days impact
- Classes, sections, subjects; periods-per-week allocation per subject (entered, **never generated** — no timetable solver)
- Syllabus per class/subject: chapters → topics
- AI-drafted week-by-week topic distribution against effective teaching days; director adjusts and approves → **baseline locked**
- Mid-year event insertion → plan visibly absorbs the lost days and re-forecasts
- **Day-celebration engine:** curated calendar of national/international/local days Indian schools celebrate; suggestion card ~2 weeks ahead ("Teachers' Day is coming — plan a celebration?"); one tap to accept → event created, affected periods absorbed, plan re-forecasts
- **AI drafts the celebration plan** (activities + prep checklist → M5 tasks). Suggestion cards, not a chatbot — one reliable tap for a non-tech admin
- Event prep work spins out as task lists in M5

**Screens**
1. School calendar (year view with holidays/events/exams)
2. Class & subject setup (with periods/week)
3. Syllabus editor (chapters/topics per class-subject)
4. Plan review board (AI draft → drag-adjust weeks → approve)
5. Plan vs forecast view (baseline vs projected completion, per class-subject)
6. Day suggestions feed (upcoming celebration cards: accept / skip)

---

### M2 — Classroom Log & Sessions (the daily capture)

*User: Teacher. Frequency: ~30 seconds per class per day; ~1 minute per session.*

**What the school achieves:** a truthful daily record of what was actually taught, what homework was given, and what happened in every after-school session — the raw data every other module runs on — captured so lightly that teachers keep doing it in week four. Nobody reports to anybody; the record assembles itself (P5).

**Features — Classroom Log**
- One-tap log: "covered → [topic from this week's plan]" (pre-filled from M1; deviation is two taps)
- Homework entry: free text/photo/voice → structured record
- **Parent auto-notify on homework log** (the teacher's reward: no diaries, no "what's the homework?" calls)
- Homework completion as a count ("34/40 done") — never per-item grading
- Channel-flexible capture: web/app quick-log at launch; WhatsApp/voice/photo parsing as the capture channel matures
- Gentle 4 pm reminder for unlogged classes; coordinator sees compliance view

**Features — Sessions** *(teacher-run after-school / remedial / homework classes — NOT school-wide attendance)*
- Define a recurring session (homework class, remedial hour, reading club) with its student list
- Open today's session → tap attendance, with late-minutes on the stragglers
- Per-student homework done / not done
- **Optional batch photo of the work as evidence** (one photo for the pile, not one per student — the one-minute budget holds)
- Record rolls straight to the director's dashboard and into each C-band student's intervention history — the teacher never writes a report

**Screens**
1. Teacher home — "My day": today's classes with this week's planned topics + today's sessions
2. Quick log (per class): covered + homework in one screen
3. Session capture: attendance taps + homework ticks + batch photo
4. My classes / My sessions — per-class history and pace vs plan
5. (Coordinator) Logging compliance view

---

### M3 — Assessments & Bands (the learning tracker)

*User: Teacher enters/uploads, Coordinator verifies, Director reviews. Frequency: term-start diagnostic + each test cycle.*

**What the school achieves:** every child skill-profiled at term start using the school's own trusted paper test, weak subjects flagged mid-term instead of at results, and every struggling child in a named intervention tier with a goal — "move C to B" made operational and *measured*.

**Features**
- **Term-start diagnostic intake:** the director's existing paper test, conducted as always — TrackBit records scores per skill area (reading, writing, speaking, … — areas configurable to match the school's test). TrackBit **records and tracks; it never authors or conducts tests**
- **Skill profile per student:** bands suggested per skill, not just per subject — "weak" becomes "weak at *what*", which is what interventions need
- Re-tests each term plot the child's skill progress line — the school sees movement, not just marks
- Marks intake with minimal friction: Excel upload or photo of the marks register → parsed → verify screen (marks already exist; create no new work)
- Class/subject performance trends across test cycles
- **Weak-subject early warning:** class average falling against previous cycles or plan expectations → alert to director/coordinator
- **A/B/C intervention tiers** per class: private to staff, suggested from diagnostic + marks, teacher can override; every C-band student gets a movement goal
- **Daily checklist for C-band students only** (hard words learnt, writing practice, reading) — scoped to the 5–8 kids per class where the effort is justified; generates teacher tasks in M5; session attendance (M2) feeds the same intervention history
- Band movement report per term (the school's "are we educating?" score)

**Screens**
1. Diagnostic intake & skill profile (record paper-test scores → per-student skill radar)
2. Marks intake (upload/photo → verify table)
3. Class performance trends (per subject, across cycles)
4. Band board (per class: tiers, goals, movement arrows)
5. Intervention plan (per C-band student: checklist + sessions + progress)

---

### M4 — Director Dashboard & Weekly Digest (the insight)

*User: Director, Coordinator. Frequency: 10 minutes/day + Monday digest.*

**What the school achieves:** the director knows the state of teaching in his school every Monday morning without asking anyone — and every problem on the screen has an "assign action" button next to it.

**Features**
- **RAG board:** every class-subject in red/amber/green for syllabus pace vs plan
- Homework health: assignment frequency & completion rates by class/teacher
- Session records: yesterday's after-school sessions — who attended, how late, homework done (the founder's homework-class story, systematized)
- Assessment trends, skill-profile movement, and band-movement summary
- Alert feed: subjects falling behind, compliance drops, weak-subject warnings
- **Teacher growth profile** *(v1.5)*: the director's "KPI over time," built entirely from already-captured data — pace vs plan, logging consistency, homework regularity, class trends, band movement in her classes — per-term snapshots. Framed as a growth profile the teacher sees herself first. **No leaderboards, no rankings** — rankings turn every teacher against the product they feed
- **Weekly WhatsApp digest to the director** ("Class 7 Science 2 weeks behind; Class 5 Math homework completion down to 60%") — directors live in WhatsApp, not dashboards
- One-tap "create task" from any alert → M5 (catch-up plan, intervention, follow-up)

**Screens**
1. Director home — RAG board + alert feed + session records
2. Class-subject drill-down (pace line, homework, marks, teacher log history)
3. Teacher growth profile (per-term, growth-framed, teacher-visible)
4. Weekly digest (delivered in WhatsApp; web archive)

---

### M5 — Tasks (existing module → the action layer)

*Already built (TrackBit v2 core). New role: where detected problems become assigned work.*

**What the school achieves:** nothing detected by the system dies in a meeting — every gap becomes a task with an owner and a deadline, and the dashboard shows whether the fix worked. And two of the director's operational pains ship on day one as templates.

**Integration points (new)**
- Alert → task: dashboard alerts create pre-filled tasks (owner, context, deadline)
- Intervention → tasks: C-band goals generate recurring checklist tasks for the class teacher
- Event → tasks: M1 calendar events and celebration plans spawn prep task lists
- Existing task features (boards, reminders, celebration layer, critical alarms) unchanged

**Board templates (pain points 11 & 15, zero new code)**
- **Maintenance board:** repair request = task + photo + assignee + status — the repair/maintenance tracker
- **Housekeeping board:** recurring cleaning checklists with photo-proof convention — the cleaning module

---

### M6 — Fees (existing module → standalone anchor)

*Already built. Stays architecturally separate from the academic spine.*

- Fee structures, collection, receipts, defaulter reminders, collection summary for the director
- The door-opener module (money software gets budget); do not entangle with academic data
- Only touchpoint: a collection summary card on the director dashboard

---

### Cross-cutting

- **Org & roles:** school setup wizard, magic-link staff invites (existing v2 pattern)
- **Notification engine:** channel-adapter (email + push at launch; WhatsApp as it lands) serving parent notifies, teacher reminders, director digest
- **AI services:** plan drafting (M1), celebration-plan drafting (M1), capture parsing (M2), marks-photo parsing (M3) — invisible plumbing, never a "chatbot feature"

---

## 6. User flows

### Flow 0 — Annual setup (Director + Coordinator, ~2 hours, planning season)

1. Create school → invite coordinator & teachers (magic links)
2. Enter calendar: working days, holidays, exam blocks, known events
3. Define classes, sections, subjects, periods/week per subject
4. Enter/upload syllabus per class-subject (chapters → topics)
5. AI drafts week-by-week distribution against effective teaching days
6. Director reviews on the plan board, drags adjustments, **approves → baseline locked**
7. Every teacher now sees her classes' week-wise plan; the year is live

*This session is also the sales demo: the director walks out with his whole year compiled.*

### Flow 1 — Teacher's daily log (30 seconds per class)

1. After class (or end of day), teacher opens quick-log for that class
2. Taps the pre-filled planned topic (or adjusts) → "covered"
3. Types/speaks/photographs the homework → done
4. System: updates pace vs plan · notifies parents of homework · clears her 4 pm reminder

### Flow 2 — Homework reaches parents (zero extra effort)

1. Teacher logs homework (Flow 1) → parents of that class get the message
2. Next day, teacher marks completion as a count ("34/40")
3. Low completion trends surface on the dashboard, not in the moment

### Flow 3 — Diagnostic → bands → intervention

1. Term start: school conducts its own paper diagnostic as always
2. Teacher records scores per skill area (photo/Excel/quick entry) → coordinator verifies
3. Skill profiles generated; band board suggests tiers per skill; teacher confirms or overrides
4. Each C-band student gets a goal + daily checklist → recurring tasks for the class teacher (M5); session attendance (M2) joins the same record
5. Unit-test marks flow in each cycle; weak-subject alerts fire if a class average slips
6. Re-test at next term start → the skill progress line shows whether intervention worked

### Flow 4 — Director's weekly review (Monday, 10 minutes)

1. 8:00 am — WhatsApp digest arrives
2. Opens dashboard → RAG board → drills into ambers/reds
3. One-tap creates catch-up tasks for affected teachers with deadlines
4. Glances at session records, fee collection card, and band movement summary → done

### Flow 5 — A day worth celebrating

1. Two weeks out, a suggestion card appears for the director: "World Environment Day — plan a celebration?"
2. One tap: **Yes, plan it** (or Skip)
3. Event lands on the calendar; affected periods absorbed; plan re-forecasts
4. AI drafts the celebration plan — activities + prep checklist → tasks assigned to responsible staff (M5)

### Flow 6 — After-school session (the founder's homework-class story)

1. 4:15 pm — teacher opens today's homework-class session
2. Taps attendance as students arrive; late arrivals get their minutes noted
3. Checks each student's homework: done / not done; snaps **one batch photo** of the work
4. Done — no report written, nothing to email anyone
5. Next morning the director's dashboard shows: who attended, how late, who finished — and each C-band student's intervention history quietly grew

---

## 7. A day in the life (product complete)

**Mrs. Lakshmi — Class teacher, 5 periods/day + homework class**
- 8:40 — opens "My day": her 5 classes, each showing this week's planned topic, plus today's homework session
- After 3rd period — 25 seconds: taps "covered: Nutrition in Plants (2/3)", speaks homework; 38 parents notified
- 1:30 — marks yesterday's homework count for 6B: 34/40
- 3:45 — ticks today's checklist for her 6 intervention-tier kids (2 minutes)
- 4:15 — homework class: attendance taps (2 late), homework ticks, one batch photo (under a minute)
- 4:30 — no reminder fires; everything's logged. Total time: under 6 minutes, and she never wrote in a diary or a report

**Director sir — 10 minutes + one meeting**
- 8:00 — Monday digest on WhatsApp: "7-Science 2 wks behind · 5-Math HW completion 60% · 3 alerts"
- 8:05 — yesterday's session record: homework class 14/17 attended, 2 late, 12 finished — nobody had to tell him
- 10:30 — dashboard: RAG board shows 7-Science amber → drill-down shows rehearsals ate 6 periods → creates catch-up task for the science teacher, due before unit test
- 10:38 — fee card: 82% collected, 23 defaulters (office staff already tasked); accepts the "Teachers' Day" celebration card — prep tasks fan out
- 4:00 — weekly coordinator meeting runs off the dashboard, not off memory

**Coordinator ma'am**
- 9:00 — compliance view: 2 teachers didn't log Friday → gentle word at break
- 11:00 — verifies the 6A Math marks photo-parse (90 seconds)
- 2:00 — band board review: 4 students moved C→B this cycle; updates two goals
- 3:00 — approves the plan shift the director made after Annual Day was added

**Office staff**
- All day in the Fees module: records 14 payments, prints receipts, sends the defaulter reminder batch, closes with the daily collection summary — untouched by the academic modules
- Logs a broken fan as a task on the Maintenance board (photo attached) — assigned, tracked, closed with proof

**Parent (no app, no login)**
- 3:50 — WhatsApp: "Homework for 6B: Science — draw the digestive system, due Thu"
- Saturday — weekly summary: homework given 5/5 days, child's completion 4/5

---

## 8. Deliberately NOT building (the fences)

| Excluded | Why |
|---|---|
| Timetable generator | Pain confirmed (July 2026) as **annual creation** — still out of v1: constraint-solver swamp. Parked for post-v1 revisit as a possible AI-draft assist. We only capture periods/week as data |
| School-wide attendance registers | Every ERP has them; integrate/sync later if demanded. (M2 Sessions ≠ registers — sessions are teacher-run classes only) |
| Report-card designer | Commodity; every ERP has one |
| Full parent app/login | Notifications deliver 90% of the value at 5% of the cost |
| Test authoring / conducting | TrackBit records and tracks; the school's own paper tests stay on paper. Digital assessment is Playground's lane, someday |
| Visitor tracker | Front-office/hardware territory; different product |
| Purchases / stock / inventory | Procurement product; different company |
| Social media insights | Marketing product; different company |
| Sports & student health records | Record-keeping ERP territory; revisit only on paying-school demand |
| LMS + NEP/NCF teacher training | **Playground's lane** — the director's interest validates the future cross-sell; merging the products now would sink both |
| Library, transport, HR, payroll | The ERP knife fight we exited |
| AI orchestrator/chatbot | Year-3 feature; needs trusted data underneath first. (M1's celebration cards are suggestion buttons, not chat) |
| Detailed AI lesson plans (objectives/activities) | Teacher-facing content product — later premium, borders Playground |
| Per-item homework grading / per-student session photos | Breaks the one-minute budget; batch evidence only |

If a school asks for any of these, the answer is: "we work alongside your ERP" — not a rebuild.

---

## 9. Build order (mapped to the pilot school)

| Phase | Build | Proves |
|---|---|---|
| **P1** | M1 Planner + M2 Classroom Log + parent notifications (on existing org/auth/notification rails). Day-celebration engine trails as an M1 add-on | Teachers still logging in week 4 — the make-or-break metric |
| **P1.5** | M2 **Sessions** (founder is its first daily user — his own homework class; the director's demo moment) | The session record replaces the founder's verbal report the very next morning |
| **P2** (needs 2–4 wks of P1 data) | M4 Dashboard + weekly digest + alert→task integration (M5) + Maintenance/Housekeeping templates | The director opens it every Monday without being asked |
| **P3** (term start / first test cycle) | M3 diagnostic intake + skill profiles + marks + bands + intervention checklists | A C-band student measurably moves; case study written |

Existing modules: **M5 Tasks** continues as built (v2 plan); **M6 Fees** continues as built. Teacher growth profile lands as **v1.5** once two terms of data exist. Pilot: the director's school, targeting a live case study before the **Jan–Apr 2027 buying window**.

---

*Companion docs: `trackbit-prd-v2.md` (task module PRD), `trackbit-v2-implementation-plan.md` (task module build plan). This document defines the product layer above them. v1.1 supersedes v1.0 (2026-07-05) — added: principle P5, pain-point coverage map, day-celebration engine (M1), Sessions (M2), diagnostic intake & skill profiles (M3), teacher growth profile (M4 v1.5), ops board templates (M5), expanded fences.*

---

## v1.2 addendum (2026-07-07) — the "Daily OS" redesign

After the founder's end-to-end walkthrough, **SPRD v2 (`trackbit-school-prd-v2.md`) is
authoritative wherever it conflicts with this document.** The deltas:

- **Positioning:** TrackBit is now *the school's daily operating system*, no longer a thin
  layer beside the ERP. The pitch, and the reliability bar, change accordingly.
- **Roles:** collapsed to `admin` + `teacher` (director/coordinator/office retired).
- **P1 restated as capture-by-exception:** confirm the norm in one tap, record only deviations.
- **Fences moved IN:** per-period attendance (exception-capture only) · timetable
  (import-first + AI-assisted draft with deterministic validators — still no guaranteed
  solver) · daily report generation · per-student homework.
- **Fences still standing:** payroll/HR/library/transport/inventory/visitor/social ·
  report-card designer · test authoring · parent app/login · chat UI · mandatory per-student
  capture · per-student evidence photos · LMS/teacher training (Playground's lane).
- **New spine:** wizard compiles the year (plan + timetable) → teachers confirm each period
  by exception → the system joins captures into per-student truth ("every hour" tracking is
  a *join*, not a capture) → the 8 AM daily report → gaps become tasks.
