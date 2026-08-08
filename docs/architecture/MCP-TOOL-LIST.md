# The tool list — for approval

**Status:** **approved** — 163 tools (151 on 2026-08-07, plus §8A's 12 on 2026-08-08).
Companion to [`MCP-SERVER-PLAN.md`](MCP-SERVER-PLAN.md), which carries the architecture;
this file carries **the list**. Written 2026-08-07.

**Built so far:** the three navigation tools (#10–12) landed with Phase 1 on 2026-08-08,
alongside the toolset/scope machinery this whole list depends on. The registry holds
**45** tools. Everything else here is still to build.

**How to use this now that it is approved:** it is the build checklist. A tool not ticked
here does not get written (`D-101`); adding one is a decision, not a backlog item.

---

## Decisions this list is built on

| # | Decision |
|---|---|
| **D-99** | **Connector auth is OAuth** — URL + Client ID + Client Secret, because that is what claude.ai and most agent clients require. The API becomes an OAuth 2.1 authorization server; the connection screen issues the client credentials. A header PAT stays alongside for Claude Code / Cursor and for testing. Supersedes `MCP-SERVER-PLAN.md` §4. |
| **D-100** | **Approval by exception, not by default.** Routine, correctable edits apply immediately. Only two narrow categories ask first (§2). Dangerous operations are not exposed at all, rather than gated. Supersedes `MCP-SERVER-PLAN.md` §3.3's "every write is `confirm=True`". |
| **D-101** | **The list is fixed by approval.** Only tools ticked here are implemented. Adding one later is a decision, not a backlog item. |
| **D-102** | **A strike removes a tool from MCP, not from the product.** `assign_homework`, `confirm_check` and `add_plan_comment` are shipped Lucy features that this list strikes. One pool (`D-93`) means the answer is a filter, not a deletion: `ToolSpec.transports` names which surfaces may expose a tool, and `visible_tools(..., transport="mcp")` drops the three. *Built in Phase 1, 2026-08-08.* |
| **D-103** | **Agent access: `off` for a new school, `admins` once it is live, and a teacher may hold her own connector** scoped to her own authority — never exceeding it. Answers `Q1` and `Q2`; shapes the Phase 2 credential screen. |
| **D-104** | **`§8A` is approved — all 12 tools — and `Q7` is answered `(b)`: band assessments get their own answer-sheet capture**, rather than routing through an exam cycle and `promote_exam_to_band_test`. This needs a migration (`band_assessment_pages`, or `ScoreCapture` with a nullable `cycle_id`), service work and a screen, so **it is its own packet** and does not ride along with the transport. |
| **D-105** | **Build against production, deliberately.** The founder has reaffirmed that prod is pre-launch and holds no client data. ⚠️ Standing consequence: `doadmin` has `rolbypassrls = true`, so **no RLS behaviour can be verified there** — anything security-shaped must still be reasoned about on the local DB, and `TEST_DATABASE_URL` never moves. |

---

## 1. Legend

| Mark | Meaning |
|---|---|
| **A** | **Auto** — applies immediately, no human step |
| **B** | **Approval** — proposes into the Approvals screen, a human confirms |
| *HAVE* | exists in the registry today (42 tools) |
| *(admin)* | admin-only; a teacher's client never sees it |
| 🔴 | has a blocker or a caveat — read the note |

Everything not marked *(admin)* is available to any member, with the **service's own
scoping** deciding which classes and students they may touch — a teacher never reaches
another teacher's class through any tool here.

---

## 2. The two things that still ask first

`D-100` makes everything auto-apply except these. Both are narrow, and both are marked
**B** in the list.

**2.1 — Writes that reach a person outside the school, or that cannot be corrected in
place.** CLAUDE.md draws the line already: *"A mistyped mark or a mis-tapped absence is
corrected in place; that is not history, it is a typo"* — but band changes, plan
approvals, score verifications and leave decisions are **append rows** where undo is a
compensating entry and the wrong one stays visible forever (law 3). Eighteen tools.

**2.2 — The volume guard.** Any single call touching more than **25 students** or
**50 rows** escalates to approval automatically, whatever its tier. This is the school's
own capture-by-exception principle (P1v2) pointed at the agent: routine volume flows,
unusual volume asks. It costs one comparison per call, and it is the thing that stops a
mis-parsed spreadsheet from rewriting a term.

> Concretely: `assign_homework` for one class auto-applies. `assign_homework_bulk` across
> 14 classes asks — because guardians are notified the instant it lands (P3), and there
> is no unsend.

---

## 3. `core` — always on, cannot be disabled

**Reads**

- [x] 1. **`whoami`** — who the agent is acting as: name, role, class teacher of, subjects taught, what it may do. The first call of any session. *NEW*
- [x] 2. **`get_school_structure`** — years, terms, classes, subjects with ids. Call before anything that needs an id; never guess one. *HAVE*
- [x] 3. **`get_class_subjects`** — a class's subject allocations and their teachers. *HAVE*
- [x] 4. **`search_students`** — find students by name or admission number. *HAVE*
- [x] 5. **`get_student`** — one student's profile, class, category, guardians. *HAVE*
- [x] 6. **`get_org_settings`** — timings, policies, state/board, `attendance_mode`. Without it the model misreads the school's shape. *NEW*
- [x] 7. **`get_calendar`** — working days, holidays, events. Makes "how many teaching days are left" answerable. *NEW*
- [x] 8. **`get_exam_calendar`** — the year's main exams. *NEW*
- [x] 9. **`list_members`** — staff names, roles and ids. *(admin)* *NEW*
- [x] 10. **`list_domains`** — which toolsets this connector has, with counts. *NEW*
- [x] 11. **`list_tools`** — the tools in one domain, one line each. *NEW*
- [x] 12. **`describe_tool`** — one tool's full schema and a worked example. *NEW*

*(10–12 are the navigation tools — `MCP-SERVER-PLAN.md` §5.)*

**Writes:** none. Creating years, classes, subjects and members is not on this list — §16.

---

## 4. `students` — the record

**Reads**

- [x] 13. **`get_student_growth`** — the full growth report: attendance, per-subject coverage, homework, observations, scores, skills, band history, growth areas. *HAVE*
- [x] 14. **`get_student_timeline`** — what one child did on a date, period by period. *HAVE*
- [x] 15. **`get_student_report_card`** — the report card numbers. *NEW*
- [x] 16. **`get_student_analysis`** — exam analysis for one child. *NEW*
- [x] 17. **`get_class_academics`** — the class roster with its academic record. *NEW*
- [x] 18. **`get_my_class`** — the class teacher's whole board. *NEW*
- [x] 19. **`get_class_students`** — one class's student list. *NEW*
- [x] 20. **`get_student_notes`** — the class teacher's log on a child. *NEW*
- [x] 21. **`get_guardians`** — a child's guardians and contact details. *NEW*

**Writes**

- [x] 22. **`add_student_note`** — a note on a child's record. *class teacher + admin* · **A** · *NEW*

---

## 5. `attendance`

**Reads**

- [x] 23. **`get_attendance_roster`** — one class-period's sheet with per-student status. *HAVE*
- [x] 24. **`get_attendance_day`** — a class's whole day, per period, marked or not. *HAVE*
- [x] 25. **`get_attendance_register`** — the day's register as taken. *NEW*
- [x] 26. **`get_my_classes`** — the classes this member may mark. *NEW*
- [x] 27. **`get_absence_notes`** — recorded reasons and notes for a child's absences. *NEW*

**Writes**

- [x] 28. **`mark_attendance`** — mark one class-period by exception; everyone present except those listed. *HAVE* · **A**
- [x] 29. **`mark_attendance_bulk`** — the same across several classes or days. **A**, escalates on volume · *NEW*
- [x] 30. **`set_absence_reason`** — record why a child was away. **A** · *NEW*
- [x] 31. **`add_absence_note`** — a free note against an absence. **A** · *NEW*

---

## 6. `capture` — the teacher's daily loop

**Reads**

- [x] 32. **`get_my_day`** — this teacher's periods with their capture state, plus pending checks. *HAVE*
- [x] 33. **`get_period_card`** — the capture surface's own state for one period. *NEW*
- [x] 34. **`list_checks`** — 🔴 today's daily checks. `confirm_check` exists with no way to list them; the model has to guess an id today. *NEW*
- [x] 35. **`get_homework_log`** — homework set, by class-subject and date. *NEW*
- [x] 36. **`get_homework_queue`** — what this teacher still has to check. *NEW*
- [x] 37. **`get_student_homework`** — one child's homework history and verdicts. *NEW*
- [x] 38. **`get_homework_load`** — how much homework a class is carrying. *NEW*
- [x] 39. **`get_class_log`** — the deliberate per-student class log. *NEW*
- [x] 40. **`get_observations`** — per-student observations from period cards. *NEW*
- [x] 41. **`get_compliance`** — which class-subjects have a lesson log today. *(admin)* *HAVE*

**Writes**

- [x] 42. **`log_lesson`** — what was taught: topic and/or note, full or partial coverage. *HAVE* · **A**
- [x] 43. **`log_lessons_bulk`** — a week of lessons in one call. **A**, escalates on volume · *NEW*
- [ ] 44. **`assign_homework`** — set homework for a class or one child. *HAVE* · **A** — 🔴 notifies guardians immediately (P3)
- [ ] 45. **`assign_homework_bulk`** — across several class-subjects. **B** — see §2.2 · *NEW*
- [ ] 46. **`check_homework`** — record done/late/not-done verdicts for a set. **A** — 🔴 `not_checked` is the teacher's gap, never a child's miss · *NEW*
- [ ] 47. **`confirm_check`** — confirm a daily check, flagging only exceptions. *HAVE* · **A**
- [ ] 48. **`add_class_log_entry`** — a deliberate per-student class-log note. **A** · *NEW*
- [ ] 49. **`save_observations`** — per-student observations against a period. **A** · *NEW*

---

## 7. `planning` — syllabus, plans, timetable

**Reads**

- [x] 50. **`get_plan_forecast`** — RAG forecast per subject: on track, weeks behind, projected finish. *HAVE*
- [x] 51. **`get_exam_fit`** — whether each subject finishes its portions before each exam. *HAVE*
- [x] 52. **`get_topic_progress`** — 🔴 topic-level planned-vs-taught. **Blocked**: it is a sixth definition of "syllabus covered" and must be moved onto `core/coverage.py` before shipping. *HAVE*
- [x] 53. **`get_syllabus`** — units and topics with their period estimates. *NEW*
- [x] 54. **`get_class_syllabus`** — one class's syllabus across subjects. *NEW*
- [x] 55. **`get_my_subjects`** — this teacher's own plans. The most-asked teacher question. *NEW*
- [x] 56. **`get_week_schedule`** — what is planned for a given week. *NEW*
- [x] 57. **`get_plan_comments`** — change-request comments on a plan. *NEW*
- [x] 58. **`get_exam_map`** — which chapters are in which exam's portion. *NEW*
- [x] 59. **`get_timetable_grid`** — the school's timetable. *NEW*
- [x] 60. **`get_my_week`** — this teacher's week. *NEW*
- [x] 61. **`get_teacher_week`** — any teacher's week. *(admin)* *NEW*
- [x] 62. **`validate_timetable`** — clashes and gaps. *NEW*

**Writes**

- [ ] 63. **`add_plan_comment`** — ask for a chapter to be resized or moved. *HAVE* · **A**
- [ ] 64. **`resolve_plan_comment`** — close a comment. **A** · *NEW*
- [ ] 65. **`reschedule_plan`** — a teacher moving her own chapters. P2 keeps the baseline frozen, so this cannot move the promise she is measured against. **A** · *NEW*
- [ ] 66. **`draft_plan`** — build a draft. A draft is not the plan. **A** · *NEW*
- [ ] 67. **`generate_plan`** — generate a draft from the syllabus and calendar. **A** · *NEW*
- [ ] 68. **`create_syllabus_unit`** — add a unit. **A** · *NEW*
- [ ] 69. **`create_topic`** — add a chapter/topic. **A** · *NEW*
- [ ] 70. **`set_topic_estimate`** — how many periods a chapter needs. **A** · *NEW*
- [ ] 71. **`split_topic`** — break a chapter into parts. **A** · *NEW*
- [ ] 72. **`set_exam_portion`** — set which chapters an exam covers. **A** · *NEW*
- [ ] 73. **`extend_plan`** — push a plan's end date. **B** — changes the promise · *NEW*
- [ ] 74. **`approve_plan`** — 🔴 **B**. Freezes the baseline (law 3, P2). The card renders the promise: finish date, buffer, exam fit. *NEW*
- [ ] 75. **`unapprove_plan`** — **B** *(admin)* · *NEW*
- [ ] 76. **`create_calendar_events`** — holidays and working days in bulk. **B** — shifts every forecast in the school · *NEW*

---

## 8. `exams` — tests, scores, analysis

**Reads**

- [x] 77. **`get_exam_feed`** — recent tests with averages and participation. *HAVE*
- [x] 78. **`get_exam_detail`** — one exam's full result sheet. *HAVE*
- [x] 79. **`get_exam_report`** — distribution and per-question breakdown. *NEW*
- [x] 80. **`get_cycle_grid`** — the score-entry grid as it stands. *NEW*
- [x] 81. **`get_exam_types`** — the school's own test vocabulary. *NEW*
- [x] 82. **`get_class_report_card`** — a whole class's report cards. *NEW*
- [x] 83. **`get_assessment_trends`** — per-subject trend across cycles for a class. *HAVE*
- [x] 84. **`get_class_analysis`** — the class's academic heatmap. *HAVE*
- [x] 85. **`get_skill_profile`** — one child's per-skill scores. *HAVE*
- [x] 86. **`get_weak_subjects`** — subjects trending weak school-wide. *HAVE*
- [x] 87. **`get_main_exam`** — one main exam's detail, portions and schedule. *NEW*

*(The school-wide exams board lives in `insights` as #153 — one tool, one domain.)*

**Writes**

- [x] 88. **`create_exam_cycle`** — create a test. **A** · *NEW*
- [x] 89. **`save_scores`** — 🔴 **B**. Transcribe marks from a spreadsheet into the existing verify grid; a human still verifies and locks. The mark is the record. *NEW*
- [x] 90. **`verify_scores`** — **B** *(admin)* · *NEW*
- [x] 91. **`lock_exam`** — **B**. A locked exam is the record; both save paths refuse it afterwards. *NEW*
- [x] 92. **`unlock_exam`** — **B** *(admin)* · *NEW*
- [ ] 93. **`create_main_exam`** — put an exam on the year calendar. **B** · *NEW*

---

## 8A. `exams` — answer-sheet capture *(approved 2026-08-08, `D-104`)*

> Numbered 184+ so nothing above renumbers. **All 12 approved.** `Q7` answered
> **(b)** — see the note under Q7 below: band assessments get capture of their own,
> which makes #195 a convenience rather than the mechanism, and makes this section
> **its own packet with a migration in it**, not part of the transport work.

### What the code actually does — read before ticking

You described three exam areas with one shared function. **In the code it is two plus
one**, and the difference is load-bearing:

| Area | Where the exam lives | Where the marks live | Photo capture |
|---|---|---|---|
| **Students → class tests** | `AssessmentCycle` | `AssessmentScore` | ✅ `ScoreCaptureService` |
| **Plan → main exams** | `CalendarEvent` + `AssessmentCycle` rows linked by `exam_event_id` (`main_exams.py:193`) | `AssessmentScore` — **the same table** | ✅ **the same pipeline** |
| **ABC → band assessments** | `BandAssessment` | `BandAssessmentResult` | ❌ **none** — `band_assessments.py` imports no `storage`, no `ScoreCapture`, no `object_key` |

So **one set of capture tools already covers two of your three areas.** A main exam is
not a separate marks system — it is a calendar event that groups ordinary cycles, which
is why `exam_marks.py` can read every mark a class has in four queries.

The third is genuinely different, and deliberately: `core/band_assessment.py` keeps
`marks` | `rating` | `other` as three kinds of statement that never pool, so a
`BandAssessment` is not an exam. **The bridge already exists**: `bands.py:503::promote`
turns a *locked* `AssessmentCycle` into a band test, writing append-only `StudentBand`
rows. See Q7 below.

The pipeline, verified in `score_capture.py`: `create` → `pages` → `parse` → `confirm`.
Two modes — `scripts` (one page = one child's marked paper, `D-80`) and marksheet (one
page = a register of many). AI transcribes, the **deterministic** `score_match.py`
attaches student ids, and **the human confirms** — `D-49`/`D-80`, not negotiable. With
AI off the photos still store as evidence and the grid stays manually editable.
`storage.presign_put()` (`storage.py:104`) is how a file gets in without going through
the MCP channel.

**Reads**

- [x] 184. **`list_exam_captures`** — captures for a cycle or class: status, page count, when. *NEW*
- [x] 185. **`get_exam_capture`** — one capture in full: pages with URLs, the parsed review grid, the roster it matches against, parse errors. *NEW*
- [x] 186. **`get_student_paper`** — 🔴 the child's **own marked script** for one exam (`S-119`). Already surfaced as `paper_url` on report cards via `ScoreCapturePage.student_id` — this is the tool that answers "show me her actual paper" in a parent meeting. *NEW*
- [x] 187. **`preview_band_promotion`** — what promoting a locked exam to a band test would move, per child, **before** it commits (`Q-81`). *NEW*

**Writes**

- [x] 188. **`create_exam_capture`** — open a capture for cycle × class × subject, or a *draft* (papers first, the exam created from what the parse reads). `mode`: `scripts` | `marksheet`. **A** · *NEW*
- [x] 189. **`get_capture_upload_url`** — a presigned PUT for one page; the client uploads the photo or PDF directly to storage, never through the MCP channel. **A** · *NEW*
- [x] 190. **`attach_capture_page`** — register an uploaded page against the capture. Images and PDFs, 25 MB each. **A** · *NEW*
- [x] 191. **`parse_capture`** — transcribe the pages and match students, producing the review grid. Writes nothing to `assessment_scores`. **A** · *NEW*
- [x] 192. **`set_page_student`** — attach a page to the child whose paper it is. **A** · *NEW*
- [x] 193. **`confirm_capture`** — 🔴 **B**. Writes the reviewed rows as real scores through `AssessmentService.save_scores`. The mark is the record — same tier as #89. Per-paper `remark` rides on this call; there is no separate remark endpoint. *NEW*
- [x] 194. **`discard_capture`** — abandon a capture; the pages stay as evidence. **A** · *NEW*
- [x] 195. **`promote_exam_to_band_test`** — 🔴 **B**. Commits the preview: appends `StudentBand` rows. `student_bands` is append-only, so a mistaken re-band is permanent in a child's record, and a child slipping B → C is the most consequential thing the bands module does. *NEW*

### Q7 — answered 2026-08-08: **(b)** (`D-104`)

Band assessments have no answer-sheet capture at all. The founder chose **(b): add
capture to `BandAssessment` itself** — a migration (`band_assessment_pages`, or reusing
`ScoreCapture` with a nullable `cycle_id`), service work, and a screen.

The reasoning that supports it: `core/band_assessment.py` keeps `marks` | `rating` |
`other` as three kinds of statement that never pool, and a `rating` or `other` assessment
**never becomes an exam cycle** — so under (a) those two kinds could never carry evidence
at all. (b) is the only option that covers all three.

**Consequences, which are real:**

- This is **its own packet**, with a migration in it. It does **not** ride along with the
  transport work, and nothing in Phases 1–5 waits for it.
- `promote_exam_to_band_test` (#195) stays on the list, but it becomes a *convenience*
  for the case where a band tier really did come from a class test — no longer the only
  route to evidence.
- The rejected option (a) is recorded here on purpose: if the packet turns out larger
  than it looks, (a) is the fallback that ships something, for `marks` assessments only.

---

## 9. `bands` — the support programme · **staff-only, always**

> **P4 is absolute.** Band tiers never reach a parent or guardian on any surface. The band
> is **per subject — there is no overall letter** (`D-75`), and the chip never renders
> without its sentence.

**Reads**

- [x] 94. **`get_band_board`** — a class's tiers in one subject, and what a chosen test would suggest. *HAVE*
- [x] 95. **`get_band_history`** — one child's tier changes over time. *HAVE*
- [x] 96. **`get_band_distribution`** — how the school sits across A/B/C. *NEW*
- [x] 97. **`get_my_band_students`** — this owner's support children. *NEW*
- [x] 98. **`get_band_programme`** — the programme board. *(admin)* *NEW*
- [x] 99. **`get_support_summary`** — one intervention's story so far. *NEW*

**Writes**

- [x] 100. **`file_bands`** — 🔴 **B**. Files tier changes for a class-subject. Append-only history — a wrong filing is corrected by a compensating row, never erased. *NEW*
- [x] 101. **`create_band_assessment`** — set up a support assessment (marks | rating | other — these never pool). **A** · *NEW*
- [x] 102. **`save_band_results`** — record its results. **A** · *NEW*
- [x] 103. **`support_check_in`** — the weekly check-in on a support child. **A** · *NEW*
- [x] 104. **`close_intervention`** — **B**. Ends a child's support cycle. *NEW*

---

## 10. `staff` — people, leave, timesheet

> 🔴 `D-25`: **a record, not an appraisal.** No score, no rank, no completeness
> percentage, no path to pay — enforced by a suite that greps the payload.

**Reads**

- [x] 105. **`get_staff_directory`** — staff list and profiles. *(admin)* *NEW*
- [x] 106. **`get_staff_board`** — who is present, away or on leave; who is teaching now. *(admin)* *HAVE*
- [x] 107. **`get_absence_impact`** — what one absent teacher's day breaks, and who is free to cover. *(admin)* *HAVE*
- [x] 108. **`get_staff_attendance`** — the staff register. *(admin)* *NEW*
- [x] 109. **`get_leave_queue`** — pending and decided leave. *NEW*
- [x] 110. **`get_leave_balance`** — leave left, by type. *NEW*
- [x] 111. **`get_my_timesheet`** — own non-teaching time. *NEW*
- [x] 112. **`get_my_month`** — own days worked and leave taken. *NEW*
- [x] 113. **`get_staff_record`** — 🔴 one member's day/month record. The description must forbid appraisal language *in the negative*. *NEW*
- [x] 114. **`get_substitutions`** — today's cover arrangements. *(admin)* *NEW*

**Writes**

- [x] 115. **`apply_leave`** — own leave request. **A** · *NEW*
- [x] 116. **`cancel_leave`** — own pending request. **A** · *NEW*
- [x] 117. **`set_timesheet_entry`** — own non-teaching period. **A** · *NEW*
- [x] 118. **`delete_timesheet_entry`** — own entry. **A** · *NEW*
- [x] 119. **`decide_leave`** — 🔴 **B** *(admin)*. Approve or refuse someone's leave — a decision about a person, append-only. *NEW*
- [x] 120. **`mark_staff_attendance`** — **B** *(admin)*. Marks a colleague present or absent. *NEW*
- [x] 121. **`assign_substitution`** — **B** *(admin)*. Someone has to actually walk into that room; the card names them. *NEW*
- [x] 122. **`cancel_substitution`** — **B** *(admin)* · *NEW*

---

## 11. `tasks` — the repeating-work engine

> This is the toolset the "action-plan PDF → a task for every teacher" scenario runs on.
> Tasks are event-sourced, so every state change is already append-only and reversible by
> a further event — which is exactly why almost all of it can auto-apply.

**Reads**

- [x] 123. **`list_task_boards`** — boards this member can see. *HAVE*
- [x] 124. **`get_my_tasks`** — own open, due and overdue tasks. *NEW*
- [x] 125. **`get_board_tasks`** — one board's tasks. *NEW*
- [x] 126. **`get_task`** — one task with its history. *NEW*
- [x] 127. **`get_board_report`** — a board's throughput. *NEW*
- [x] 128. **`list_recurring`** — recurring templates and their schedules. *NEW*
- [x] 129. **`get_task_board`** — assigned-task health plus today's classroom duties per teacher. *(admin)* *HAVE*

**Writes**

- [x] 130. **`create_task`** — one task. *HAVE* · **A**
- [x] 131. **`create_tasks_bulk`** — 🔴 the headline scenario: N tasks in one transaction. **A**, escalates on volume (§2.2) · *NEW*
- [x] 132. **`assign_task`** — **A** · *NEW*
- [x] 133. **`reassign_task`** — **A** · *NEW*
- [x] 134. **`claim_task`** — **A** · *NEW*
- [x] 135. **`complete_task`** — **A** · *NEW*
- [x] 136. **`reopen_task`** — **A** · *NEW*
- [x] 137. **`cancel_task`** — **A** · *NEW*
- [x] 138. **`add_task_note`** — **A** · *NEW*
- [x] 139. **`create_board`** — **A** · *NEW*
- [x] 140. **`add_board_member`** — **A**. Law 5 still holds: admins do not see private boards they are not on. *NEW*
- [x] 141. **`create_category`** — **A** · *NEW*
- [x] 142. **`create_recurring_template`** — the "weekly task document" turned into a schedule. **A** · *NEW*
- [x] 143. **`update_recurring`** — **A** · *NEW*
- [x] 144. **`toggle_recurring`** — pause or resume. **A** · *NEW*

---

## 12. `insights` — the admin's boards · *(admin throughout)*

**Reads**

- [x] 145. **`get_dashboard`** — the director dashboard and live alert feed. *HAVE*
- [x] 146. **`get_daily_report`** — the day already written up. *HAVE*
- [x] 147. **`get_school_overview`** — whole-school health for a year. *HAVE*
- [x] 148. **`get_teacher_load`** — periods per week per teacher. *HAVE*
- [x] 149. **`get_absence_streaks`** — children missing school for N days running. *HAVE*
- [x] 150. **`get_capture_grid`** — class × period, what was actually marked. Separates "attendance is bad" from "attendance was never taken". *HAVE*
- [x] 151. **`get_syllabus_board`** — coverage against plan, pivoted by class, subject or teacher. *HAVE*
- [x] 152. **`get_homework_board`** — the set → checked → done funnel. *HAVE*
- [x] 153. **`get_exams_board`** — results school-wide. *HAVE*
- [x] 154. **`get_presence`** — the presence tab, day and month. *NEW*
- [x] 155. **`get_daybook`** — the day's teaching record. *NEW*
- [x] 156. **`get_attendance_reach`** — whether guardians were actually reached. *NEW*
- [x] 157. **`get_calls`** — the call list. *NEW*
- [x] 158. **`get_syllabus_pulse`** — the week's movement. *NEW*
- [x] 159. **`get_actions_history`** — what the action rail has done. *NEW*

**Writes**

- [ ] 160. **`regenerate_daily_report`** — rebuild a day's report. **A** · *NEW*

---

## 13. `sessions` — hostel and activity

**Reads**

- [x] 161. **`get_session_records`** — a date's session records with counts and evidence. *HAVE*
- [x] 162. **`list_sessions`** — configured session blocks. *NEW*
- [x] 163. **`get_session`** — one session with its meetings. *NEW*

**Writes**

- [x] 164. **`create_session`** — **A** · *NEW*
- [x] 165. **`update_session`** — **A** · *NEW*
- [x] 166. **`create_meeting`** — **A** · *NEW*
- [x] 167. **`mark_session_attendance`** — **A** · *NEW*
- [x] 168. **`save_session_logs`** — per-student study/homework logs. **A** · *NEW*

---

## 14. `events` — the calendar's occasions

**Reads**

- [ ] 169. **`get_whats_on`** — what is coming up. *NEW*
- [ ] 170. **`get_event_suggestions`** — observances suggested for this state and board. *(admin)* *NEW*
- [ ] 171. **`get_catalogue`** — the observance catalogue. *(admin)* *NEW*

**Writes**

- [ ] 172. **`approve_observance`** — put it on the calendar. **A** *(admin)* · *NEW*
- [ ] 173. **`dismiss_observance`** — **A** *(admin)* · *NEW*
- [ ] 174. **`set_event_cost`** — record what an event costs in teaching time. **A** *(admin)* · *NEW*

---

## 15. `fees` — *(admin only, OFF by default)*

> Requires a separately-worded opt-in when issuing a credential. **Teachers never see
> fees** — the fence is a word-boundary regex over the whole teacher tool surface, and it
> must be extended to cover this list.

**Reads**

- [x] 175. **`get_fee_collection`** — collected / pending / overdue by quarter, per class, with defaulters. Three different facts that must never be added together. *HAVE*
- [x] 176. **`get_overdue_students`** — who is actually overdue. *NEW*
- [x] 177. **`get_fee_structures`** — the school's fee structures. *NEW*
- [x] 178. **`get_student_fee`** — one child's fee record. *NEW*
- [x] 179. **`get_fee_transactions`** — one record's transaction history. *NEW*

**Writes**

- [ ] 180. **`add_fee_note`** — a follow-up note. **A** · *NEW*
- [ ] 181. **`create_fee_structure`** — **B** · *NEW*
- [ ] 182. **`assign_fee_structure`** — attach a structure to students. **B** · *NEW*
- [ ] 183. **`set_installment_due_date`** — **B**. Also the only way to resolve an `unscheduled` instalment, which has no web caller today. *NEW*

---

## 16. Deliberately NOT on the list

So the approval is informed. Each of these is one sentence from being added — overrule
any of them and it moves up.

| Not exposed | Why |
|---|---|
| **Create / delete a student; guardian changes** | Your call — identity, and guardian rows are the parent portal's authentication. `set_student_status` would be the safe version if you ever want it. |
| **Invite a member, change a role, reset a password, remove a member** | An agent that can grant itself admin has no fence. |
| **Create / delete years, classes, subjects, class-subjects; teacher allocation; `activate_year`** | Structural setup. The wizard owns it, it happens once, and it is not repeating work. **This is the largest thing I left out — say the word if you want the agent to build a school from a spreadsheet.** |
| **Every `import/commit`** — roster, staff, syllabus, timetable, members | The agent may run `analyze` (worth adding if you want spreadsheet ingestion — say so and I will list them); the human commits in the existing review screen, which is the only place import errors get caught. |
| **Record a fee payment** — `mark-paid`, `pay`, `undo` | Money received is a claim about the physical world that nothing in software can verify. Fee *configuration* is on the list; recording cash is not. |
| **Remind a guardian, nudge a member, the action rail** | The agent never composes or triggers a free-text message to someone outside the school. Product notifications that fall out of a captured fact (homework → guardian) are the product working and stay in. |
| **Open / close / not-held a period** | Device-level capture state; an agent opening a period fabricates presence. |
| **Upload exam scripts, session media, task photos** | The photo *is* the capture mechanism, and MCP is a poor transport for binaries. |
| **The parent portal, all 13 routes** | Fence, absolute: no parent- or guardian-facing AI surface, no parent writes. |
| **Platform / operator routes** | `require_super_admin` lifts RLS org scoping by design. A separate server, or nothing. |
| **Auth, billing, push, `ops/run`** | Credentials, money, device subscriptions, job triggers. |

---

## 17. Totals

Machine-verified against this file's numbered items on 2026-08-07 — not estimated.

| | Reads | Writes **A** | Writes **B** | Total |
|---|---:|---:|---:|---:|
| **✅ Approved** | 110 | 41 | 12 | **163** |
| ❌ Struck | 3 | 20 | 9 | **32** |
| | | | | **195** |

§8A's 12 moved from pending to approved on 2026-08-08 (`D-104`).

Of the 163 approved, **45 exist today** (verified by importing `REGISTRY`) — the 42 that
predate this work, plus the three navigation tools built in Phase 1. So **118 to build**.

⚠️ Three of those 45 (`assign_homework`, `confirm_check`, `add_plan_comment`) are
**struck** here and live only on Lucy's transport (`D-102`). They count towards the
registry, not towards the MCP surface: an MCP client sees **42** of the 45 today.

**What the strikes did.** All of `planning`'s writes, all of `events`, all of `fees`'
writes, `create_main_exam`, `regenerate_daily_report`, and six `capture` writes
(`assign_homework`, `assign_homework_bulk`, `check_homework`, `confirm_check`,
`add_class_log_entry`, `save_observations`) are out. Net effect: **the agent reads
everything and writes attendance, tasks, exams, bands, staff, sessions and student
notes — but never sets homework, never edits a plan or syllabus, and never touches
money.** Three of the four guardian-notifying paths left the surface with them.

Only **10 of 45 approved writes** ask for approval; the other 35 apply immediately.

A default connector (`core + students + capture + planning + tasks`) sees ~70 of these —
the credential's toolsets bound the list (`MCP-SERVER-PLAN.md` §5).

A default connector (`core + students + capture + planning + tasks`) sees **~75** of
these, not 183 — the credential's toolsets bound the list (`MCP-SERVER-PLAN.md` §5).

**The ratio that matters: 55 of 74 writes apply with no human step.** The 19 that ask are
the append-only decisions and the school-wide ones.

---

## 18. Next step

Approved, so this file is now the build checklist.

1. ~~Phase 1 — domains and scope on the registry~~ ✅ **done 2026-08-08**, which also
   shipped #10–12.
2. **Phase 2 — credentials.** OAuth 2.1 (`D-99`) + the header PAT, and the `agent_access`
   org setting per `D-103`.
3. Phase 3 transport → Phase 4 screens → **Phase 5 the change-set engine, which no write
   tool ships before** → then the tools, domain by domain.

Two things run on their own track and block nothing here: **`§8A` band capture**
(`D-104`, has a migration) and **the `topic_progress` fix** (Phase 0.1, cross-stack —
until it lands, tool #52 answers "is 7A on track?" wrongly).
