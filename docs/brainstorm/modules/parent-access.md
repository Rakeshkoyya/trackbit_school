# Module — parent access: how a parent gets in, and how we reach them

Two halves of one problem. A notification is worthless if the parent cannot log in to act on it,
and a login is worthless if nothing ever tells them to open the app.

**Sessions:** 2 (2026-07-30)
**Related:** [`../screens/parent.md`](../screens/parent.md) · attendance (`D-02` absence alerts)

---

## 1 · Who this is for, and when

| Role | The moment | Device | The question |
|---|---|---|---|
| **Parent** | evening, or the moment a push lands | phone, weak connection, one minute | *"Was my child in school, and is there anything I need to do?"* |
| **Admin/office** | onboarding a school, or when a parent can't get in | desktop | *"Why can't this parent log in?"* |

## 2 · What they must be able to do

- **Parent:** get in without help, once, and stay in. Receive the things that matter without
  opening the app.
- **Office:** hand a parent their access in one sentence, and fix it when it fails.

---

## 3 · Where it stands today *(verified 2026-07-30)*

Shipped as **PC-1** (2026-07-23), migration `c4d5e6f7a8b9`.

- **Login is phone-OTP.** Last-10-digit phone matching, 5/hr throttle, 5-attempt lock. The
  failed-attempt bump commits in its own session so a lockout survives the request rollback.
- **`guardians.user_id`** is claimed at first login, and **all** guardian rows with that phone are
  linked — which is how **siblings roll up** into one session with a switcher.
- **`role='parent'` session**, no membership, no `token_version` — revocation is the live
  guardian-link check in `get_current_parent`.
- Optional username/email + password already exists at `/parent/auth/credentials`.
- **OTP delivery** tries the WhatsApp auth-template first, falls back to MSG91 SMS, and logs to
  the console when neither is configured (`OTP_ECHO_IN_RESPONSE` echoes the code in dev).
- **Guardian messaging** is `notify_guardian.py` — a WhatsApp stub. The absence alert, the
  homework notification and the Saturday summary all call it.

### What does **not** exist
- ❌ `organizations` has **no school code / slug**
- ❌ `students` has **no date of birth** — and the roster importer does not map one
  (`TARGET_FIELDS` = full_name, admission_no, roll_no, class_name, section, category…)
- ❌ no notifications tab in the portal
- ❌ no push registration for parents (push exists for staff)

---

## 4 · Decided this session

- **`D-08`** — no WhatsApp in this version; notifications are in-app + a parent Notifications tab.
- **`D-14`** — **web push** for parents, so notifications actually arrive.
- **`D-13`** — login is **school code → class → section → student → date of birth**, session
  persists until logout.

---

## 5 · What `D-13` costs, honestly

Not objections — the pattern is common and the UX is genuinely better than OTP. These are the
four things that will bite, each with a fix that keeps the flow identical.

### 5.1 · The picker is a roster leak · `S-55`
School code → class → section returns **every child's name in that section**, before any password
is entered. Anyone holding a school code can harvest the school's student list.

**Fix:** don't render a browsable list. After class + section, **type-to-search** requiring 3+
characters, or ask for roll / admission number. A parent knows their own child's name; nobody
needs to *browse*. Same number of taps, no roster exposed.

### 5.2 · A date of birth is about 5,500 guesses · `S-56`
And the picker tells an attacker exactly whom to target. Without a lockout it falls in minutes.

**Fix:** reuse the OTP module's existing machinery — 5-attempt lock, hourly throttle — keyed per
student rather than per phone. It is already written and already survives request rollback.

### 5.3 · The school code must not be guessable · `S-57`
`DPS2024` plus a browsable class list is the whole school's roster. A random 6–8 character code,
handed to parents and never published, costs nothing and removes the drive-by case entirely.

### 5.4 · The date of birth does not exist yet · `Q-24` 🔴
No column, no importer mapping, no data. Consequences:

- the importer needs a DOB column **and a date parser** — Indian sheets mix `dd/mm/yy`,
  `dd-mm-yyyy` and Excel serial numbers, and this is a real source of wrong logins
- already-onboarded schools must backfill
- **a student with no DOB has a parent who can never log in**

**Fix:** Setup shows *"42 students have no date of birth"* until cleared, and the admin can set a
per-student override credential for the gaps.

---

## 6 · Open threads

| | |
|---|---|
| `Q-24` 🔴 | where the DOB comes from, and what happens to students without one |
| `Q-25` 🔴 | siblings — one login or three? *(today one phone rolls them all up)* |
| `Q-26` | is the school code secret? |
| `Q-27` | what replaces the guardian-phone link — what is the account, what gets revoked, who receives the push? |
| `Q-28` | can the password ever change from the DOB? |
| `Q-29` | is phone-OTP removed, or kept as the recovery path? |

*Claude's recommendation on `Q-25`:* after login, offer **"add another child"** — prove each
child once with their DOB, and the session then behaves exactly as it does today, switcher
included.

---

## 7 · Reaching them — the other half

`D-14` gives parents web push. Two design consequences worth holding on to:

**`S-61` · The Today tab should *be* the notification surface.** A parent who opens it once a day
should have seen everything — the absence, the homework, the note. The Notifications tab is then
an **archive**, not the delivery mechanism, and no parent has to check two places.

**`S-62` · Web push is best-effort, and the absence alert is not.** iOS requires the site to be
installed to the home screen before push works at all; permission can be denied; a phone can be
off. So the alert that matters most is the least reliable. The school needs a fallback it
controls — the admin's board already shows who was alerted; it should also show **who was not
reachable**, so the office can phone those few. *(This is the honest version of "we removed
WhatsApp": the reach problem doesn't disappear, it becomes visible.)*

---

## 8 · What we deliberately don't build

- **No parent writes** (PC-1 fence, unless `Q-01` reverses it) — including no replies to a
  notification. A notification a parent can answer is a messaging product.
- **No student login** (`D-07`).
- **No band, skill, observation or check-flag** reaches this surface, ever (P4).

## 9 · Data implications

```
organizations
  + school_code          text, unique, random 6–8 chars, not guessable   (D-13, S-57)

students
  + date_of_birth        date, nullable                                  (D-13, Q-24)
  roster importer: + a DOB column and a tolerant date parser

parent auth
  login attempts locked per (student, ip) — reuse otp_codes' machinery   (S-56)
  what the "account" is now: guardian row? student claim? device?        (Q-27)

push
  parent push subscriptions — staff push already exists                  (D-14)
```

## 10 · Rough build order

| Step | Contents |
|---|---|
| 0 | answer `Q-24`, `Q-25`, `Q-27` — all three change the data model |
| 1 | `school_code` + `date_of_birth` + importer column + the "missing DOB" list in Setup |
| 2 | the login flow with `S-55` (type-to-search) and `S-56` (lockout) built in from the start |
| 3 | `D-14` parent web push + `S-61` Today-as-the-surface |
| 4 | Notifications tab as the archive + `S-62` "not reachable" list for the office |
