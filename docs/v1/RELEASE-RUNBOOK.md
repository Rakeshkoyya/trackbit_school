# v1 release runbook

Written at V1-13 close (2026-08-02). Everything in v1 is built, tested and committed; what is
left is a **deploy** sequence, not a build one. Nothing here was executed from the build session
— production was deliberately not touched.

---

## 0 · Where things stand

| | |
|---|---|
| Code | `main` — `841445d` (V1-7…V1-13) + `8b6be5d` (360px fixes) |
| Migration head in the repo | **`b0c1d2e3f4a5`** |
| Local dev + local test DB | at that head |
| DigitalOcean prod | at that head (applied 2026-08-02) |
| **V1-13's own migration** | **none — this packet added no schema** |

So there is **nothing to migrate for v1-13**. The only production change outstanding is the
app-role swap in §2.

`api/.env` is in **`ACTIVE: LOCAL`** mode. Read the `# ─── ACTIVE:` banner before running Alembic;
in prod mode a bare `alembic upgrade head` migrates production with no confirmation.

---

## 1 · Running it locally

```bash
# terminal 1 — API
cd api
uv run alembic upgrade head          # no-op if already at b0c1d2e3f4a5
uv run python -m scripts.seed        # the demo school
uv run python -m scripts.seed_midyear  # optional: the mid-year school
uv run uvicorn app.main:app --port 8000   # no --reload; restart after edits

# terminal 2 — web
cd web
npm run dev
```

Logins (all `demo1234`):

| Role | Who |
|---|---|
| admin | `kc@demo.trackbit.app` · `priya@demo.trackbit.app` |
| teacher | `ramesh@` (6-A Maths/Science + class teacher — the richest walk) · `anil@` · `sunita@` · `farhan@` · `meera@` · `kavya@` |
| super-admin | `super@trackbit.app` → lands on `/platform` |
| parent | school code `DEMO123` → class → section → child → date of birth |
| mid-year school | `head@midyear.trackbit.app` (admin) · `asha@midyear.trackbit.app` (teacher); school code `MIDYR26` |

`ENABLE_SCHEDULER=false` in `.env`. Turn it on only if you want the 19:00 daily report / 16:00
teacher reminder to fire; exactly one process may have it on.

---

## 2 · 🔴 The app-role swap (the last release item)

**The problem.** Production's `DATABASE_URL` is `doadmin`, and every managed-Postgres admin role
has `rolbypassrls = true`. So all 57 `org_isolation` policies are **inert in production**. Law 1
(app-layer org scoping from the verified token) still holds everywhere and is the primary guard —
but law 2's defence-in-depth is decorative there until this is done.

`scripts/provision_app_role.py` is idempotent, prints the generated password once, and **aborts if
the role it just made can still bypass RLS**. It also installs `ALTER DEFAULT PRIVILEGES`, so
tables created by future migrations are usable without re-granting.

### Steps

```powershell
cd api
$env:DO_ADMIN_BASE = 'postgresql://doadmin:PASSWORD@db-pgsql-blr1-99031-do-user-18242000-0.d.db.ondigitalocean.com:25060/'
uv run python -m scripts.provision_app_role
```

(trailing slash required; the password is in `api/.env`'s `PROD_*_BACKUP` comments)

It prints `trackbit_school_app rolbypassrls: False` and then a password. Then:

1. In **Dokploy**, set the API app's `DATABASE_URL` to
   `postgresql+psycopg2://trackbit_school_app:<printed password>@<private host>:25060/trackbit_school?sslmode=require`
   — the **private/VPC** host, which is what the container uses.
2. Leave `ADMIN_DATABASE_URL` as `doadmin`. Alembic must keep it: the restricted role does not own
   the tables and cannot `ALTER` them. This is why the two URLs exist.
3. Redeploy. `docker-entrypoint.sh` runs migrations (as the admin URL) then starts gunicorn.

### Verify it actually bit

```sql
-- as the app role
SELECT rolbypassrls FROM pg_roles WHERE rolname = 'trackbit_school_app';  -- must be false
```

Then log in as two different orgs and confirm neither sees the other's rows. Locally this is
already genuine — the local app role is NOBYPASSRLS — so `test_rls.py` passing locally is
meaningful evidence the policies themselves are right.

### If it goes wrong

Put `DATABASE_URL` back to the `doadmin` URL in Dokploy and redeploy. Nothing in the database was
altered by the swap — only a role was created and granted — so there is no data rollback.

**Most likely failure:** a table created outside a migration, or a sequence, that the role was not
granted. Symptom is `permission denied for table X` in the API logs. Re-running
`provision_app_role.py` re-grants over everything and fixes it.

---

## 3 · Known debt (reported, not fixed — neither is user-visible)

1. **~17 superseded GET routes have no web client** — `/fees/summary`,
   `/fees/overdue-students`, `/fees/installments/{id}/mark-paid`, `/classroom/compliance`,
   `/assessments/bands/config`, `/sessions/records`, `/homework/overview`,
   `/insights/attendance/streaks`, `/wizard/reset` and others. Each is covered by a test, so
   removing them is a ~17-route change across 8 test files. (Separately, `/billing/webhook` and
   `/ops/*` have no web client **correctly** — they are not web surfaces.)
2. **`PlannerService.topic_progress` is a sixth coverage definition.** It decides
   taught/in-progress/pending from lesson logs on its own rules rather than through
   `core/coverage.py`. No screen calls it — **Lucy does** — so she can describe a topic's progress
   on rules the coverage screens do not share. This is `S-51` with a tool for a hat, and it is the
   first thing to fix in v1.1.
3. `/dashboard/attendance` still measures 402px wide at a 360px viewport. Its two wide children
   (the SubTabs bar, the capture heatmap) are both correctly inside `overflow-x-auto`, so it is not
   an uncontained element; the remaining 42px was not traced. Every other route in all three roles
   fits 360 exactly.

---

## 4 · How v1 was verified

Not by inspection:

- **492 backend tests** on a real local Postgres where the app role genuinely cannot bypass RLS.
- **A route sweep driving the running server** — 131 GET routes × 3 roles against the seeded
  school. Admin 117×200 with **0 404s and 0 5xx**; teacher 38×403; **0 `/fees` routes reachable by
  a teacher**. This is the half a unit suite cannot reach: a guard that is wrong in the *wired*
  direction still returns 200 in a test that never wires it.
- **A browser walk at 360px** over 51 routes in 3 roles, failing a page on an uncaught error, a
  console error, an empty body or horizontal scroll. It found the nested-anchor hydration bug on
  the reach board and six pages that scrolled sideways.
- **The §5 mid-year acceptance test** against `scripts/seed_midyear.py`: no red rows, nothing
  claimed before `tracking_start_date`, the syllabus board showing the planned basis beside the
  whole-syllabus basis, and carried dues on their own labelled line.
