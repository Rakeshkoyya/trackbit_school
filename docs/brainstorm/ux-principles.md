# UX principles for every screen we design here

The checklist. Apply it to every screen in every module — it is what turns "a bunch of numbers"
into something a person acts on. Most of these were learned the hard way in modules that already
shipped; the references say where.

---

## 1 · A screen answers one question

Every screen has a sentence: *"I came here to find out ___."* If it needs two sentences, it is
two screens, or one screen with a tab. If it needs none, it is a report, and a report can be a
section on another screen.

Write the question in the screen's spec before designing anything on it.

## 2 · Lead with a sentence, not a number

`78%` tells nobody what to do. *"31 of 44 periods marked — 6-B has marked nothing since period
2"* does. The headline of a screen should be a plain English sentence a person could say out
loud, and the figures sit under it as evidence.

*(This is the DASH3-OV move that fixed the admin overview; the attendance tab never got it.)*

## 3 · Name the people

A count is the end of a thought; a name is the start of an action. *"3 students absent 3+ days"*
becomes useful only as *"Kabir Shah — absent 4 days, no reason, class teacher Priya"*.

Any row that reports a problem should name who it is about and who owns it.

## 4 · Every figure carries its denominator

Never a bare `82%`. *"82% of school days"* and *"82% of marked periods"* are different facts and
people will read whichever one flatters them. A percentage without its denominator is the
bunch-of-numbers problem in a single line.

## 5 · Not-captured is never a failure, and never a zero

A class nobody marked is a **gap in the record** — not an absence, not 0%, not red. A staff day
nobody marked is not a full house and not an empty school. This distinction is the whole reason
`class_periods.attendance_marked_at`, `staff_attendance_days` and `homework_checks` exist as
separate rows, and it must survive into every screen that renders them.

Corollary: an admin who marks staff attendance at 10am must not see a red tile every morning.

## 6 · Two actions, not nine

A screen with two actions gets used. A screen with nine becomes another dashboard nobody opens.
Pick the two that close the loop the screen exists for, and make everything else a link to where
that work actually lives.

## 7 · Every red row has a next step attached to it

If a screen tells someone something is wrong and gives them nowhere to go, it has made their day
worse. The action rail belongs on the row, not in a menu.

And the action must remember it fired — the same parent should not be reminded three times in a
morning. *(This is why `followup_actions` is append-only and read per-list in one query.)*

## 8 · Record the outcome, not just the press

"Reminded guardian" is an event. *"Spoke to the father — fever, back Monday"* is the fact that
makes the row go away. If the outcome has nowhere to go, the row keeps re-asking and people stop
trusting the screen.

## 9 · One computation, many renderings

The same fact appears on five screens. It must come from **one** server-side function. Three
components each deciding their own version of "absent" is not hypothetical — it is in the code
right now, and it is the worst defect the attendance review found.

Colour is a rendering of a server-computed status, never logic in a component.

## 10 · States are words when they are not measurements

`unplanned`, `unestimated`, `not_checked`, `not_marked` are **states**, not bad scores. They stay
neutral in colour and stay words on the screen. Turning a state into a colour invents a
judgement the data does not support.

## 11 · Respect the one-minute budget

P1v2 is an acceptance criterion, not a slogan. Capture-by-exception: confirm the norm in one tap,
record only deviations. Quick log ≤ 3 taps / 25s. Routine period card ≤ 5 taps / 30s. A
15-student session ≤ 60s.

**Any feature needing per-student entry for a whole class is mis-designed** — redesign it or cut
it. This applies to anything new we invent in these sessions.

## 12 · Give value before asking for data

P3. A teacher logging homework gets parents notified for free. Every capture surface should
return something to the person doing the capturing, or it becomes a compliance chore.

## 13 · Design the empty state and the first-week state

Most screens will be seen first by a school with almost no data. An empty state that explains
what will appear and how it gets there is part of the design, not a fallback. A screen that
looks broken in week one gets abandoned in week two.

## 14 · Mobile is the real device for teachers

A teacher uses this standing up, one-handed, in front of a class. 360px, thumb reach, no
horizontal scroll, sticky primary action. Admins are on a desktop; parents are on a phone with a
weak connection.

## 15 · Shape beats number for patterns

A month grid of attendance cells says "every Monday" or "a block in October" or "slowly fading"
faster than any percentage. When the question is *what is the pattern*, draw the pattern.

When the question is *how much*, a number is fine — just give it its denominator (§4).

---

## Hard fences that override any design idea

These are not UX preferences. Crossing one is a bug, whatever the mock looks like.

| Fence | Rule |
|---|---|
| **P4 — bands** | A/B/C tiers are private intervention tiers. They never appear on any parent- or guardian-facing surface — screen, message, report, export. |
| **Teachers and fees** | Teachers never see fee data — not a summary, not a total, not a chart. One narrow exception (`D-83`): a teacher **assigned a fee follow-up task** sees that one student's detail inside the task, and nowhere else. No inference routes — no amount-sorting, no class counts. |
| **Parent portal** | Read-only, and everything a parent sees goes through the curated allowlist projection — field by field, never a spread. Parents get a **daily** attendance status, never per-period detail. |
| **Per-student photos** | Evidence is batch (P5). Two exceptions, both decided explicitly: hostel session media (HS-2) and exam script photos (`D-82`) — a photo per student's marked paper is the exam capture mechanism. Classroom activity photos stay batch-only. |
| **No parent-facing AI or chat** | Lucy is staff-only. |
| **Students** | No login, no surface, ever (`D-07`). |
| **Salary** | If payroll ships, it is fenced from Lucy, the daily report and every widget (`S-17`). |
| **Timesheet** | Never feeds pay, an appraisal, or a ranking of people (`D-25`). Payroll reads staff attendance and half-day leave only. A teacher who knows her timesheet cannot cost her money has no reason to write anything but the truth. |

---

## Questions to ask of any screen before it is called done

- What did the user arrive asking?
- What do they leave having decided?
- Is the headline a sentence?
- Does every figure have a denominator?
- Are the people named?
- What happens when there is no data yet?
- What happens when the school never captured it?
- What is deliberately **not** on this screen, and would someone ask for it?
- Which fence is closest to this screen, and does it hold?
