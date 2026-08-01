# Module — the class teacher

A teacher who owns a class + section. Not a third role: a **capability on a membership**, so
role guards, RLS and nav all stay two-role.

---

## 1 · Where it stands today *(verified in code, 2026-07-30)*

The concept is **half-built and currently dead**.

| Layer | State |
|---|---|
| Model | `school_classes.class_teacher_member_id` — nullable FK to `memberships` ✅ |
| API | `POST /academics/classes` and `PATCH /academics/classes/{id}` both accept it ✅ |
| Schema | `ClassCreate` / `ClassUpdate` / `ClassOut` all carry it ✅ |
| **UI to set it** | **None.** `createClass` in `school-api.ts` doesn't send it; there is no `updateClass` at all. ❌ |
| Read sites | 4 — admin absence list ("class teacher Ramesh"), class page, Setup teacher panel, assessments notification |

So the field is null in every real school, and the admin's red list has always rendered
"class teacher: —". **The assignment half of `D-03` is a frontend-only job** — an afternoon's
work, and the cheapest thing decided in session 1.

There is **no class teacher screen of any kind**. She is named as the owner of every red absence
row, the admin can assign her a follow-up, and she has nowhere to see it.

---

## 2 · Decided this session

### `D-03` — admin assigns the class teacher; she gets a dedicated dashboard

- The admin configures which teacher owns which class + section, in **Setup**.
- Once assigned, she gets a **dashboard for her class**: attendance, syllabus, and a few other
  modules.

---

## 3 · Proposals (`S-nn`)

**`S-20` — ship the assignment first, on its own.** The backend is done. A select on the class
row in Setup immediately fixes four existing read sites that have never had data, including the
"who owns this absence" line on the admin's board. It also unblocks everything below.

**`S-26` — the month attendance grid is the centrepiece.** Her students down the side, school
days across the top, one cell per day. This is the one grid of cells in the product that is
genuinely a decision surface, because a row's **shape** reads faster than any number:

```
              M T W T F  M T W T F  M T W T F
Aarav  ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✓ ✓     100%
Diya   ·····  ✓ ✗ ✓ ✓ ✓  ✓ ✗ ✓ ✓ ✓  ✓ ✗ ✓ ✓ ✓      80%   ← every Tuesday
Kabir  ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✗ ✗ ✗  ✗ ✗ ✓ ✓ ✓      67%   ← a block, then back
Ishaan ·····  ✓ ✓ ✓ ✓ ✓  ✓ ✓ ✓ ✗ ✓  ✗ ✓ ✗ ✗ ·      73%   ← fading
```

Three different problems, three different conversations, readable in one glance — and none of
them expressible as "attendance %". Cells carry the `D-02` colour: yellow where a reason is
recorded, red where it isn't.

**`S-27` — the screen holds exactly two actions.** Record an informed absence with a reason, and
log a parent call with its outcome. Both of them turn a red row yellow (`S-21`). Everything else
on the screen is a link to where that work already lives. A screen with two actions gets used; a
screen with nine becomes another dashboard nobody opens.

**`S-28` — she sees her class's syllabus across *all* subjects, not just hers.** "Is my class
behind in anything?" is a class teacher's question, and the answer already exists — the syllabus
forecast just needs re-pivoting by class. Same trick the DASH3 insights already use for the
teacher pivot.

**`S-29` — her follow-up inbox.** What the admin assigned her, with the student, the reason, and
how long it has been sitting. This is the missing half of a loop that already exists on the
admin's side.

**`S-30` — she is staff, so bands are allowed here.** P4 fences bands from *parents*, not from
teachers. A class teacher seeing her class's band distribution is within the rule — but it
should be a deliberate call, not an accident of what got put on the page.

---

## 4 · Screen sketch

```
My Class · 6-B                                    32 students

  ┌ Needs attention ─────────────────────────────────────────┐
  │ 🔴 Kabir Shah — absent 4 days, no reason                  │
  │      last present Tue 22 · 2 guardians on file            │
  │      [ Record a reason ]  [ Log a parent call ]           │
  │ 🟡 Diya Nair — absent today · "fever" (office, 9:10am)    │
  │ 🟡 Aarav Rao — away 12–15 Aug · family function           │
  └──────────────────────────────────────────────────────────┘

  ┌ Drifting ────────────────────────────────────────────────┐
  │ Ishaan Kumar  73%, down from 91% last month               │
  └──────────────────────────────────────────────────────────┘

  ┌ This month ──────────────────────────────────────────────┐
  │ [ the grid above ]                                        │
  └──────────────────────────────────────────────────────────┘

  ┌ My class's syllabus ─────────────────────────────────────┐
  │ Maths ▓▓▓▓▓▓▓░░ on plan   English ▓▓▓▓░░░░░ 2w behind     │
  │ Science ▓▓▓▓▓▓░░░ on plan  Hindi ▓▓▓▓▓▓▓▓░ ahead         │
  └──────────────────────────────────────────────────────────┘
```

Order is deliberate: the people who need something today, then the people who will next week,
then the record, then the class's academic position. Nothing above the fold is a chart.

---

## 5 · Data model sketch

Almost nothing new is needed — which is the point.

```
school_classes.class_teacher_member_id     EXISTS — just needs a UI (S-20)

memberships                                 nothing new: "is a class teacher" is derived
                                            by asking whether any class points at her
```

Everything the screen renders is a re-pivot of data that already exists: attendance exceptions,
the absence reasons from `D-02`, the syllabus forecast, and `followup_actions`.

---

## 6 · Open questions

`Q-09` (own area, or folded into My Day?) · `Q-10` (which other modules?) ·
`Q-14` (one class teacher per class?). See [`../open-questions.md`](../open-questions.md).

---

## 7 · Rough build order

| Step | Migration | Contents |
|---|---|---|
| 1 | none | `S-20` — assignment UI in Setup. Standalone, immediately useful. |
| 2 | none | The area + the month grid (`S-26`) + needs-attention. Depends on `D-02` landing first. |
| 3 | none | Drifting, syllabus pivot (`S-28`), follow-up inbox (`S-29`) |
