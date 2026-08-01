# The matrix — who sees what, on which screen

Every screen touched by the session-1 decisions, by role. This is the "what goes where" answer.

**Status key:** `EXISTS` = built and unchanged · `CHANGING` = built, redesign proposed ·
`NEW` = does not exist · `DEAD` = built but unreachable in the UI.

**Roles.** There are exactly two staff roles (`admin`, `teacher`) plus a read-only parent token
and the platform super-admin. **Class teacher is a capability, not a role** (`D-03`) — a teacher
who owns a class sees one extra area.

---

## 1 · Admin

### `/dashboard` — the operating board (7 tabs)

| Screen | Status | What's on it today *(verified)* | What changes |
|---|---|---|---|
| `/dashboard` overview | CHANGING | One block per module — headline sentence, 2–3 figures, named rows, action rail. Attendance block reads the same roll-up the tab does. | Attendance block gains the yellow/red split from `D-02`. Staff block gains half-day/late. New payroll block? — **no**, see `S-17`. **+ a `What's on` block** (`D-51`) — today's birthdays and observances, this week, then *Coming up* with lead time (`S-126`). The **only** block on this screen not reporting a problem, so it is never styled as an alert (`S-132`). Its one real action, *Add to school calendar*, is the sole path in the module allowed to change a teaching day (`S-122`). |
| `/dashboard/attendance` | CHANGING | 4 stat tiles · period capture heatmap · 14-day pulse area · by-class bars · staff strip · "absent 3+ school days" red list with a working action rail (remind guardian / assign follow-up). | Rewritten as **questions, not numbers** (`S-08`). Red list moves to the top and splits yellow (reason known) / red (`D-02`). New rows: drifting, chronic late, left-after-lunch. Heatmap gains a **by-teacher** pivot. Charts fold behind *More*. |
| `/dashboard/staff` | CHANGING | Live "who's teaching / working / free" board, absentees with periods due vs covered, leave queue, teacher week vs mean, non-teaching bucket chart, per-teacher day strip. | Gains half-day and late states (`D-04`); half-day must show **which half** (`Q-15`). **+ the slack profile** — stacked per period, for finding the meeting slot (`D-21`, `S-66`), its free band labelled *"free or unrecorded"* (`D-23`). **+ filters.** The "unlogged" tile is **deleted, not fixed** (`S-76`). Hostel evenings count (`S-68`). **No ranking of people, and no path to pay** (`S-67`, `D-25`). |
| **`Approve this date`** (sheet, from the overview card + `What's coming`) | **NEW** | Nothing — a suggestion has nowhere to be approved, and the paint UI silently drops `affects_teaching`. | **`D-57` `D-58`.** The **only** place in the product a teaching day can be created or destroyed. Three levels — **school closed** / **some periods only** / **runs as usual (assembly)** — which are `affects_teaching` + `blocks_periods`, both already prorated by `effective_periods` (`S-142`). 🔴 **+ the cost, before they commit** (`S-143`): *"removes 8 periods; 6-B Maths green → amber"*, off `forecast_org`, which DASH3 already batched. **+ provenance on the row** (`S-150`). Dismissal is append-only and permanent (`S-148`). Locking a past day keeps what was already captured, never erases it (`Q-65`). |
| **Cover sheet** (from staff tab **+ `/staff/leave`**) | **CHANGING** | Per period: class, subject, ranked candidates with reasons, Assign, Cancel cover. Today-only, and the rank ignores the timesheet. | **`D-26`** two panels *(largely built)*. **+ what the class gains** — the next planned topic, and who can actually teach it (`D-29`, `S-79a`). **+ what the substitute gives up** (`S-74`) and whether she is behind herself (`S-79b`). **+ opens for a future date from a leave approval** (`D-27`, `S-80`). 🔴 **+ `busy_reason` must check approved leave**, or `D-27` assigns cover to someone on leave (`S-82`). |
| `/dashboard/syllabus` | EXISTS | Coverage by school / class / subject / teacher × year / term / exam. | — |
| `/dashboard/homework` | **CHANGING** | Completion roll-ups by class and subject, repeat non-doers named with streak/subject/teacher + working actions, per-teacher checking table, perfect + most improved. | 🔴 **"Overdue, unchecked" is blaming teachers for a bug** — their queue only ever showed yesterday; `D-33` fixes it at source. 🔴 **The red list names absent children** — `D-34` makes them *carried*, skipped by the streak (`S-85`, `S-102`). **+ a late column** — *"82% done · 6 late"*, and the child's lateness kept separate from the teacher's (`D-33`, `D-38`, `S-99`, `Q-43`). **+ daily load per class** (`D-37`). Say what a *partial* is worth (`S-88`, `Q-40`). |
| `/dashboard/tasks` | EXISTS | Task health, daily duties denominated by periods actually due. Open/overdue/completed **by assignee**, red rows named, *Reassign · Extend · Nudge*. | — *(session 5: this is already the right screen for "did what I asked for get done"; the change is that the **board** must stop lying — below)* |
| `/dashboard/exams` | **CHANGING** 🔴 | Exam roll-ups with participation beside every average; by-class / by-subject, trajectories, distribution bucketed in Postgres. | 🔴 **Every test type pools into one average** — `tot_s / tot_x` across all cycles, type filter defaults to off, so *"Maths is at 61%"* is the mean of a diagnostic, twelve slip tests and one final (`S-114` — `scale` = minor \| major, **never** pooled; weights are the fenced report-card designer). **+ `S-113`** the type filter offers the school's own words (*CET*, *pre-board*) instead of nine fixed ones. **+ `S-115`** links a recorded exam to its planned block, so this tab and `/dashboard/syllabus` can be asked one question together. |

### `/boards/[id]` — the **Follow-ups** board

| Screen | Status | Today *(verified)* | Changes |
|---|---|---|---|
| `/boards/[id]` (Follow-ups) | **CHANGING** 🔴 | One shared board, `task_scope='assigned'` — teacher sees her own rows, admin sees all (`visibility.py:67`, enforced in `task.py:265`). Public **not** private, so law 5 can't blind the admin to the tasks they assigned (`D-40`). | 🔴 **The admin's `/tasks` tab shows them none of it** — a client-side re-filter discards the server's answer (`D-48`). 🔴 **It is a ledger**: every instance ever, no window → **`D-44`** windows the read (open always · done 7 days · older behind a date filter that **ships with it**), no archive, no job. **+ `D-45` a Stale group** for untouched open rows, close or re-date, **never** auto-close — and after `D-43` this is the *only* thing stopping a dropped follow-up staying dropped. **+ `D-46` the task carries its subject** and completion records **what happened**. Due dates move to org-local end of day (`D-48`); the rail dedupes on the **open task**, not the calendar day (`D-47`). |

### `/staff` — the staff area

| Screen | Status | Today | Changes |
|---|---|---|---|
| `/staff` (attendance) | CHANGING | Admin opens the day, everyone ticked present, unticks who's away, saves. Full replace. **Present/absent only.** | Adds **half-day (AM/PM)** and **late** (`D-04`). Stays exception-only — present is still derived. |
| `/staff/leave` | CHANGING | Apply/approve/cancel with an append-only history timeline; over-policy applications flagged, not blocked. **Approval is the end of the interaction.** | Leave gains a **half-day** type and AM/PM (`Q-15`); policy adds `D-05`'s grace period. **+ `D-27`: approving hands back the cover flow** — "Arrange cover for 3 days", one sheet per day (`S-80`), and the uncovered periods land on the action rail dated to that day (`S-81`). |
| `/staff/today` | **CHANGING** 🔴 | The teacher × period grid of `D-21` — and it is **wrong**: it reads the timetable and timesheet only, so **an absent teacher shows eight free periods** and a teacher already covering shows free. `/dashboard/staff` computes the same grid correctly. | **`S-72` — delete one of the two computations** and render `WorkloadInsights`. Tiles must stop counting non-teaching staff. Reads half-day/late (`D-04`) and the *free* / *not told us* split (`S-61`). |
| **`/staff/salary`** | **NEW** | — | **`D-06`.** Per staff member: days present, days absent, leave used vs balance, **estimated salary**. Month selector. Gated by `Q-06`, shaped by `Q-05`/`Q-07`/`Q-08`. |

### `/setup`

| Screen | Status | Today | Changes |
|---|---|---|---|
| `/setup` (Academics) | CHANGING | Years, classes, subjects, class-subjects, skill areas. **Two lenses on assignments: by class (editable) and by teacher (READ-ONLY).** | **Class teacher assignment** (`D-03`) — the API already accepts it; only the form is missing. **+ `D-28` / `S-77`: make the by-teacher lens writable** — pick a teacher, tick their class-subjects, save many at once. This screen is what the whole substitution flow reasons over. Batch its per-class queries; make the 48-periods badge a real load validator. |
| `/setup/settings` | CHANGING | Band thresholds, parent portal toggle, leaves per year/month, report hour. | **+ attendance mode** (`D-01`) · **+ minimum-attendance threshold** if `Q-04` says yes · **+ payroll policy** (grace period, monthly application cap, what deducts pay per `Q-08`). |
| `/setup/members` | CHANGING | Add/remove members, set role. | **+ salary amount per member** if `Q-07` lands here · **+ the payroll-visibility capability** if `Q-06` picks (b). |

### `/students`

| Screen | Status | Today | Changes |
|---|---|---|---|
| `/students` directory | EXISTS | Search, group-by class, filters, grouped card tables. | Optionally an attendance-status column so the directory can be scanned for absentees. |
| `/students/[id]` | CHANGING | Report card: attendance gauge (**% of marked periods**), tiles, ability radar, strengths/growth areas, score history, attendance by subject, chapter drill-down. **Homework appears only as per-subject counts.** | The attendance gauge must state its denominator and switch to **days** once the day roll-up exists (`S-01`, `S-03`). Absence reasons and follow-up history appear here. **+ the homework history block** (`D-31`, `S-86`) — `GET /homework/student/{id}` and `schoolApi.studentHomework` both exist and **nothing calls them**; this is the founder's "which homework and when he missed", a component away. **+ session 6:** the score history draws **one line through slip tests and finals** — `GrowthScore` carries no type (`S-114`); the average needs its denominator, *"61% across 5 of the 9 tests 8-B sat"* (`S-118`); and the **paper itself should be one tap away** — the photos are kept forever as evidence and `storage.url_for` exists, but *"can I see it?"* is unanswerable on the screen where a parent asks it (`S-119`). |
| `/students/scores` (+ `/[classId]`, `/exam/[cycleId]`) | **CHANGING** | Exam-first: class cards + a feed of previous exams. Capture = drop photos → AI transcribes header + rows → **`score_match.py` decides identity** (roll → exact → fuzzy → unmatched-with-candidates) → review grid → cycle + scores + evidence in one transaction. | **`D-50`: the photo gains a second, optional job** — a **marking check** beside the review grid (*marks total 23, header says 25* · *Q4 unmarked*), never inside it, never blocking the save (`S-116`). Anything judging the **answer** stays behind a flag and is **never stored** (`S-117`, `Q-51`). **+ `D-55`/`S-135`** the school's own exam type (a small `exam_types` table beside the system `type`, carrying `scale`). **+ `S-114`** minor/major grouping in the feed. **+ `D-53`: the grid ends in *Verify & lock*** — 🔴 today `verified_by` is never set by this flow so the *"· verified"* badge cannot light up, and `save` full-deletes and re-inserts scores, so **`D-54`'s training pair would drift after the fact** (`S-136`). Locked = read-only with who and when; unlock is an appended row with a reason (`S-139`, `Q-62`). **+ `D-54`** the diff between what the model read and what the human locked, with a reason bucket, written once at lock (`S-137`, `S-140`) — org opt-in, default off (`S-138`, `Q-61`). |
| `/students/bands` | **CHANGING** 🔴 | Pick a class → three columns of names and a count, threshold sheet (**two numbers for the whole school**), *Record a band test*, *Manage students individually*. Answers *how many are in C* and nothing else. | **`D-67`: becomes the programme board, and movement is the headline** — *"11 moved up this term, 3 slipped, 4 have been C since April"* → **Stuck**, named, with the owner and weeks since her last check-in → **by class × subject** (`D-73`) → **not assessed yet**, a word, never a zero. Distribution goes under *More* (`S-169`). **`D-75`: bands are per subject and there is no overall letter** — 🔴 today one letter is written from the sum of every score in a cycle, so a child who can't read and is fine at arithmetic gets a tier describing neither; a single chip becomes **"C · Hindi"** (`S-186`). Under `D-77` a child can have **two owners**, so every stuck row **names the subject** (`S-188`). **No ranking of teachers by children moved** (`S-170`, the `D-25` rule). |
| `/students/bands/[classId]` | **CHANGING** | Records a band test and re-tiers the class from the thresholds (admin-only). | **`D-70`: two routes, both first class** — from a test's marks, or the teacher's own assessment, with **the descriptor open beside the control** (`D-69`, `S-166`). The marks pre-fill and she moves only who she disagrees with, so it defaults rather than demanding 38 judgements. 🔴 `apply_band_suggestions` currently re-bands from *the latest cycle, whatever it is* — a slip test can move eleven children; **`S-183` deletes it**, replaced by `D-76`'s explicit promotion. **This screen is ENTRY only** (`S-185`): once a class is filed, a child moves band on a **test**, from the teacher's exam screen. **Assign owners for the C children happens here**, straight after filing — one per subject (`D-71`, `D-77`). |
| **`/setup/settings` → Bands** | **NEW** | Two org-wide percentages, on a sheet inside the bands page. | **`D-74`.** Monitored subjects (`D-68` — English, Hindi, Maths to start), and **per subject**: the three descriptors (`D-69`), the thresholds, the re-assessment test, and the check-in cadence. Ship the nine descriptors **pre-written and editable** — 27 empty boxes get filled in by nobody (`S-175`, `Q-76`). |
| `/students/trends` | EXISTS | Class trajectories. | — |

---

### `/fees` — admin only, always (`D-63`)

| Screen | Status | Today *(verified)* | Changes |
|---|---|---|---|
| `/fees` | **CHANGING** 🔴 | Four bare tiles — `Net fee (year)` · `Collected` · `Overdue` · `Pending instalments` — over an enrolment list. Three different denominators in one row, no sentence, nothing named. | **`D-64`: becomes the collection board** — and it replaces this landing page rather than becoming a ninth dashboard tab (`S-152`). Headline sentence → **collection curve vs last quarter** (`S-155`) → quarter strip with `collected / pending / overdue` kept apart (`S-163`) → **by class with both denominators** — *"8-B — 14 of 38 families pending, ₹1.4L"* (`S-159`) → **the named defaulter list**. 🔴 That list is `overdue_students`, which has existed since P0-D and **`school-api.ts` has never called it**. Quarter = **due-date window** (`S-153`, `Q-67`). Arrears are invisible today (`Q-68`). Fix the per-student `_class_label` N+1 while it's open (`S-162`). |
| `/fees/[id]` | **EXISTS, untouched** | Instalments, pay / mark-paid / undo, discount, append-only ledger. | **Deliberately out of scope** (`D-62`) — it is the part that works, and it is where money is actually taken. |
| `/fees/structures` | EXISTS | Structure + instalment templates. | — |

**Actions on the board (`D-65`):** **Remind** → parent notification + a `followup_actions` row, so
the row re-renders *"reminded 9:12am · you"* and nobody is chased twice (`S-156`) · **Assign
follow-up** → a task for the class teacher, 🔴 **whose content is `Q-66`**.

**The rule that outranks the screen:** no fee status ever reaches an academic surface — not
`/students/[id]`, not growth, not the timeline, not the daily report, not a Lucy tool (`S-157`).

---

## 2 · Teacher (subject)

| Screen | Status | Today | Changes |
|---|---|---|---|
| `/my-day` | CHANGING | A list of tappable period rows + yesterday's homework check + "this evening" sessions. Free periods are **not** on it. | In `first_period` / `twice_daily` mode, only the marking period(s) ask for attendance, pending `Q-02`. Rows say what's **missing**, not what's done (`S-39`). **The timesheet stays out** — `S-63` REJECTED by `D-24`: nothing joins the daily capture flow. |
| `/my-day/period/[classId]/[no]` | EXISTS | Attendance row · topics · homework · checks · test capture · deep log · "not held" · save session. | Attendance row hidden or read-only in non-marking periods (`Q-02`). **+ `D-59`: "not held, because"** — `not_held_reason` exists (`classroom.py:470`) and gains a **reference to the approved event** instead of free text (`S-147`), so *"what did Diwali cost us in periods?"* is answerable. **Two scopes, never merged** (`S-146`): the admin's lock is school-wide and the teacher is then **never asked**; her block is per-class (8-A at the rehearsal, 8-B still teaching). 🔴 **`S-145`: a locked period leaves her capture surface, every denominator and the 16:00 reminder** — but "leaves" means *no longer expected*, never *erase what was recorded* (`Q-65`). |
| `/my-day` **what's-on strip** | **NEW** | Nothing. | **`D-51`, `S-132`.** One line at the very top — *"🎂 Aarav Sharma (6-B) — birthday today · 🪔 Guru Purnima"*. **Her classes only**; day and month, never an age (`S-133`); absent children marked so she doesn't ask the class to sing at an empty chair; a birthday landing in a vacation rolls to the nearest working day (`S-128`). **The one block on My Day that asks her for nothing** — so never a tick, never amber, and absent entirely when there is nothing on. |
| `/my-day` **tasks section** | **NEW** | Nothing — `MyDayOut` is `{date, classes, periods, homework_pending}` (`schemas/classroom.py:66`). | **`D-41`: a rule under the periods, then tasks, tickable in place.** **`D-43`: it is a window, not her list** — rail-assigned within **3 days** ∪ **due today**, then a **`n older tasks →`** footer so the window is never silent. No *Upcoming*, no overdue backlog, no undated self-made tasks: those are `/tasks`. Consistent with `D-24`/`D-36` by one rule: *work on another screen → counted button; work **is** the row → the row.* Nothing goes above the periods. A filtered read over `HomeService.my_tasks` (`home.py:117`) — a frontend packet. Late is a **state, not a group** (`S-108`); cap 3–5 as a backstop (`S-109`); badge who asked (`S-106`). |
| `/my-day` homework block | **REMOVED** | "Yesterday's homework — mark completion": one tap for *Everyone did it*, or a tap-to-cycle roster. 🔴 Lists only `date == today − 1`, so **Friday's never appears on Monday**. | **`D-36`: it goes.** Replaced by a button — **`[ Homework · 4 to check ]`** — and the count is not decoration (`S-100`). Checking is a desk activity with a stack of books, not a between-classes tap. |
| **`/homework`** — the teacher's homework screen | **NEW** | — | **`D-32` / `D-36` / `S-101`.** L1: her classes × homework given, which day and what, waiting first, oldest first — **nothing ever expires** (`D-33`). L2: the check sheet, absentees badged and not pre-flagged (`S-85`), carried items on the returning child's row (`S-97`), streak as she taps (`S-89`). L3: **by student** *(= `S-86`'s unreachable endpoint, so it also delivers `D-31`)* and **by day**. |
| `/my-day/period/.../attendance` | CHANGING | Roll call. **Every box starts unchecked**; tick who answers; unticked saves absent. "Tick everyone" shortcut. Late mode appears after first save. | Unify with the session sheet — one component, one default (`S-12`). Optional **reason entry** at capture time, never required (`D-02`). |
| `/sessions/[id]/attendance` | CHANGING | **Everyone starts present**; tap to cycle present → absent → late. Opposite default to the school sheet. | Same component as above (`S-12`). |
| `/timesheet` (week) | CHANGING | Week grid — teaching periods locked, free cells tappable. **Periods she covered show as free** (`Q-37`). | Counters become **her** record, not her score (`S-70`). Cover unioned in (`Q-37`). Picker **pre-selects** her usual category, writes nothing (`S-75`). A one-off working Sunday becomes recordable. **No completion %, no nag** (`D-23`). |
| **`/timesheet` month view** | **NEW** | — | **`D-18`, `S-64`.** One cell per **day**, not 200 cells — taught/recorded/open plus holidays, leave and exam days read from the calendar. Her record, not a hole-finder (`D-23`). Navigates; doesn't edit. |
| **`/timesheet/[date]` day view** | **NEW** | — | **`D-18`.** Vertical timeline including breaks, classes locked, gaps tappable, cover marked. Nothing to submit (`D-23`). |
| `/timesheet/leave` | CHANGING | Balance, apply, own history. | **+ half-day application** with AM/PM (`D-04`, `Q-15`). |
| **`/timesheet/salary`** | **NEW** | — | **`D-06` teacher view.** Her own month: days present, leave used, her own estimated figure. **She sees only herself** (`Q-06`). |
| `/students/[id]` | EXISTS | Same report card, restricted to students in classes she teaches (`not_your_student`). | **+ the support-programme block** (session 9) — the tier already renders as *"Support tier C"* with its history, and the **plan attached to it never does**: `schoolApi.studentInterventions` is wired into the client and called by nothing (**fourth instance** of that pattern). |
| **`/support`** — her support students | **NEW** | — | **`D-71` / `D-72` / `D-77`.** The children she owns, grouped by subject — ownership is **per subject**, so a child C in Hindi and Maths sits on two teachers' lists and neither is guessing whose he is — each with when he entered, how the thread is going, and one button. Headline is about *her* week — *"3 of your 6 checked in. Kabir hasn't in three."* **Six children, five minutes.** A *Moved to B* list stays visible for the term, because a list that only grows is a list nobody opens. **No comparison against other owners** (`S-170`). |
| **`Use this as the band test`** — on `/students/scores/exam/[cycleId]` | **NEW** | — | **`D-76`**, and the best idea of the session. One action at the bottom of an exam she has just locked: promote this CET / slip test to be the band-deciding test for that class-subject. A **flag, never a `type` change** (`S-182` — re-typing deletes the test from the exam analytics), **locked only** (`D-53`), **total marks and how many sat it on screen**, small tests **warn but never block** (`S-184`), **one subject** (`S-187`). Non-sitters keep their band and the screen says so (`Q-80`); the moves are shown before they commit, because `student_bands` is append-only and a wrong row is permanent (`Q-81`). |
| **`/support/[studentId]`** — one child | **NEW** | — | **`D-72`**, and the screen the module lives or dies on. **It opens already written** (`S-164`): his week is read from `lesson_observations`, `check_results`, `homework_results`, `attendance_exceptions` and `session_student_logs` — capture that other teachers already did — then she writes the **weekly check-in**, four fields (`S-165`, `Q-73`). The **exit criterion is on screen from day one** (`S-167`). *No signals this week* is a statement about the record, never *"no progress"* and never red. |
| **Fee follow-up task** — on `/tasks` | **NEW** 🔴 | — | **`D-65`**, and the only fee-shaped thing that ever reaches a teacher. 🔴 **`Q-66` decides what it may say**: `D-63` says only admins see fee data, so a task reading *"₹12,000 overdue"* breaks the fence the feature sits on. **`S-154` recommends the family and the subject, never the amount** — *"Fee follow-up · Kabir Shah (8-B). Please speak to the family and record what they say."* Close the inference routes too: no sorting by amount, no large/small badge. Completion records **what the family said** (`S-161`). |

---

## 3 · Teacher (class teacher) — the new area

**`D-03`.** Appears only for a teacher who owns a class. Route and placement pending `Q-09`.

| Block | Status | What it answers |
|---|---|---|
| **Month attendance grid** — her students × school days | NEW | *Who is slipping?* A row's **shape** reads instantly: every Monday, or a solid block, or a slow fade. This is the one grid of cells that is genuinely a decision surface. |
| **Needs attention** — yellow (reason known) / red (3+ days, no reason) | NEW | *Who do I call today?* Same rule as the admin's board, same server-computed status (`S-22`). |
| **Drifting** — the 60–85% band, trending down | NEW | *Who do I catch before they become red?* |
| **My follow-ups** — what the admin assigned her | NEW | Today the admin can assign her a follow-up and **she has nowhere to see it.** This closes that loop. |
| **Syllabus for my class** — coverage across all subjects, not just hers | NEW | *Is my class behind in anything?* Reuses the existing forecast, re-pivoted by class. |
| **Birthdays this month** — her class only | NEW | *Whose birthday do I need to organise something for?* (`D-51`). The fuller version of the teacher's one-line strip, because she is the one who gets asked. Day and month, never an age (`S-133`). |
| Other modules | TBD | `Q-10` |

**Actions on the screen:** record an informed absence with a reason · log "called the parent —
outcome" · nothing else. Two actions, both of which close a red row.

---

## 4 · Parent (read-only portal)

| Screen | Status | Today | Changes |
|---|---|---|---|
| `/parent` (Today) | CHANGING | One daily status line (present / partial / absent / not marked / no school) · taught today · last homework verdict · still to do · homework set today · evening sessions. *(verified)* `not_checked` reads neutrally and its badge is suppressed in "still to do" — **the HW-1 rule holds here.** | **+ the pattern, not just the day** (`S-11`): a month calendar strip and "present 18 of 21 school days". **+ the reason** if the school recorded one. **+** a `tel:`/WhatsApp "tell the school why" link (`Q-01a`). **+ split "still to do" from "missed"** (`S-94`). **+ homework from days the child was absent shows YELLOW and "pending"** (`D-35`) — same palette as `D-02`, and it must be able to clear when the teacher waives it (`S-98`). **+ a miss notification on a *pattern*, never a single one** (`S-90`, `Q-39`). |
| `/parent/progress` | CHANGING | Per-subject: syllabus covered, attendance %, homework count, last test. | Attendance % must state its denominator (`S-03`). |
| `/parent/report` | EXISTS | Curated growth projection — coverage, missed-while-absent, scores, derived strengths/growth areas. | Optional minimum-attendance line if `Q-04` says yes. |
| `/parent/profile` | EXISTS | Child + sibling switcher. | — |
| **`/parent` fee reminder** | **NEW** — `D-66` | — | The first fee surface a parent has ever had *(verified: zero fee fields anywhere in `parent_portal.py`, `schemas/parent.py`, `parent-api.ts`)*. A **block on Today**, not a tab: *"Term 2 fee · ₹12,000 · due 15 August"* + what's already paid + a `tel:` link. **It does not render when nothing is due** — a fee section shown to a family that owes nothing reads as a demand. Never red, never "defaulter" (`S-160`). Manners on the notification (`S-156`): one per instalment per week, quiet hours, **stops the instant payment lands**, `notify_opt_out` honoured. **No payment path** — `PC-1` is read-only. |
| **`/parent` school calendar** | **PROPOSED** — `Q-56` | — | **`S-130`.** *"Is school open on Monday?"* is the most-asked question in a school office, and the rows that answer it already exist and are already maintained — **read-only, zero new capture**. Probably the cheapest win available to the portal. Constraints: the curated allowlist field-by-field like every other parent surface, and **only their own child's birthday** — a list of classmates' birthdays is a roster leak wearing a party hat. |

**Hard rules that hold on every parent screen:** never a band or tier (P4) · never a skill
profile, raw observation or check flag · never per-period attendance detail — parents get a
**daily** status · never another child's data · **read-only** unless `Q-01` reverses it.

---

## 5 · Student

**Nothing. `D-07`.** No login, no surface, no notification. Students are data. Anything a student
needs reaches them through the parent portal or a printed page a teacher hands them.

---

## 6 · Super-admin (platform operator)

Out of scope for these sessions. `/platform` (schools, enquiries) is unaffected by everything
above, **except**: if payroll lands, the operator setting up a school will be asked to configure
salary policy, and the operator can read across orgs by design (`require_super_admin` lifts the
RLS GUC). **That means the operator can read every school's salary data.** Worth a conscious
decision rather than a discovery — added as a note on `Q-06`.

---

## Cross-cutting: where the same fact is rendered

The same underlying number appears on many screens. Every one of these must come from **one**
server-side computation, or they will disagree — which is not hypothetical: three different
definitions of "absent for a day" are in the code right now (see `modules/attendance.md`).

| Fact | Rendered on |
|---|---|
| Is this student absent today? | admin attendance tab · class teacher grid · parent Today · daily report · student report card · Lucy |
| Attendance % | student report card · parent progress (per subject) · admin tiles · class teacher grid · daily report |
| Absence status colour (yellow/red) | admin attendance tab · admin overview · class teacher board · student report card |
| Days present (staff) | staff attendance · staff salary (admin) · timesheet salary (teacher) · leave balance |
| **Is this teacher free in period N?** | `/staff/today` · `/dashboard/staff` live board + day strip · the **cover picker** · the slack profile · Lucy. 🔴 **Already two computations that disagree, and the picker reads neither properly** — see `S-72`, `S-74`. |
| **Did this child do the homework?** | teacher's check sheet · teacher's by-student view · admin red list · `/students/[id]` · daily report · parent Today. **One component serves the two per-student views** (`S-101`), and `done`/`late`/`carried`/`waived`/`not_checked` must mean the same thing in all six. |
| **A teacher's teaching load** | `/dashboard/staff` bars · `/setup` teacher-load panel · the timetable clash validator · fairness view. Must include hostel sessions or a warden reads as idle (`S-68`). |
