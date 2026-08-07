# TrackBit School

The school's daily operating system: it plans the academic year down to the period,
captures each day with near-zero teacher effort, knows what every student is doing
during school and hostel hours, and writes the school's daily report itself.

Monorepo:

```
api/       FastAPI + SQLAlchemy 2 (sync) + PostgreSQL      → the backend
web/       Next.js 16 + React 19 + Tailwind v4             → the frontend
docs/      the product spec (SPRD v2 is the current build spec)
test_doc/  a generator for mock setup data (see test_doc/new_org/README.md)
```

---

## Before you start

| Need | Version | Notes |
|---|---|---|
| Python | 3.12 | managed with **uv**, not pip/poetry |
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` or see their docs |
| Node | 20+ | for `web/` |
| PostgreSQL | — | **you do not run one locally** — see below |

> **Docker is not used in this project.** There is no local Postgres container.
> `api/docker-compose.yml` is dead; the Dockerfiles exist only so Dokploy can build
> remotely. Don't try to `docker compose up`.

### The database

You run **Postgres locally** (installed directly — there is no container). The
Aiven instance the project used to share has been retired for development: its
app role did not own `organizations`, so `alembic upgrade` failed there and the
test suite had never actually run — which is how three real bugs reached main.

`api/.env` **switches between LOCAL and PROD and says which mode it is in** —
look for the `# --- ACTIVE: ...` banner before running anything. Three URLs, and
the split is load-bearing:

- `DATABASE_URL` → a **restricted** role (`NOBYPASSRLS`). The app uses this, so
  Row-Level Security actually applies.
- `ADMIN_DATABASE_URL` → the schema owner. **Alembic only.**
- `TEST_DATABASE_URL` → a **separate local database** (`trackbit_school_test`).
  It stays local in *both* modes.

Pointing the app at the admin URL would silently disable every RLS policy. Don't.

> ⚠️ `.env` currently ships in **`ACTIVE: PRODUCTION`** mode, so every click in
> the app writes to the real database and `alembic upgrade head` migrates
> production with no confirmation. Never run `scripts.seed` in this mode, and
> keep `ENABLE_SCHEDULER=false`. See `CLAUDE.md` → "Database" for the full rules.

---

## Setup

### 1. Get the secrets

`.env` files are **not** in git. Ask the team lead for **one** file:

- **`api/.env`** — the only file with real secrets (DB URLs, JWT secret, API keys).

That's it. The frontend's config is not secret — you create it yourself in step 3.

### 2. Backend

```bash
cd api
cp .env.example .env          # then paste in the values you were sent
                              # Windows PowerShell: Copy-Item .env.example .env

uv sync --extra dev           # install dependencies
uv run alembic upgrade head   # apply migrations
uv run python -m scripts.seed # demo org + demo data

uv run uvicorn app.main:app --port 8000
```

> No `--reload`. Restart the server yourself after edits.

Everything marked OPTIONAL in `.env.example` can stay empty — the app falls back to a
safe dev behaviour (emails print to the console, files go to local disk, AI calls
short-circuit to deterministic heuristics). **The app runs fully with no AI key.**

### 3. Frontend

```bash
cd web
cp .env.example .env.local    # Windows PowerShell: Copy-Item .env.example .env.local
npm install
npm run dev                   # needs the API already running
```

`.env.local` holds exactly one line and no secrets:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

It **must** end in `/api/v1`.

### 4. Log in

http://localhost:3000 — all demo passwords are `demo1234`:

| Login | Role | Lands on |
|---|---|---|
| `kc@demo.trackbit.app` | admin | Dashboard |
| `ramesh@demo.trackbit.app` | teacher | My Day |
| `anil@demo.trackbit.app` | teacher | My Day |

There are two staff roles: **admin** (runs the school) and **teacher**. Teachers
never see fees.

**Parents have their own read-only portal** at `/parent` — not a membership.
A guardian signs in with the school code, then class → section → child → the
child's date of birth (phone-OTP is the recovery path). The demo school's code
is `DEMO123`. Everything a parent sees goes through a curated allowlist, so
bands, skills, raw observations and check flags never reach them.

The **platform operator** (`super@trackbit.app`) creates schools and lands on
`/platform` — schools do not self-onboard.

---

## ⚠️ Read this before you run the tests

The test suite needs a real Postgres, and it **creates and hard-deletes
organisations**. It runs against `TEST_DATABASE_URL` — a separate local
database, never the one your app is pointed at.

`conftest.py` honours `TEST_DATABASE_URL` and **refuses to start** if it
resolves to the same host+database as `DATABASE_URL` (escape hatch:
`ALLOW_TESTS_ON_DATABASE_URL=1`). Both engines, including the privileged cleanup
engine that reads `ADMIN_DATABASE_URL`, are redirected at the test database.

That guard is real, but it is not a licence to be careless:

- **It cannot know that some *other* remote URL is precious.** It compares
  against `DATABASE_URL` only. Never edit `TEST_DATABASE_URL` to point at
  anything you would mind losing — and note that `.env` currently ships in
  PRODUCTION mode, so `DATABASE_URL` *is* the production database.
- **Never point it at a superuser.** A superuser bypasses RLS even with
  `FORCE ROW LEVEL SECURITY`, so `test_rls.py` fails for reasons that have
  nothing to do with your code. The restricted role needs
  `GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public` plus
  matching `ALTER DEFAULT PRIVILEGES`, so tables from future migrations work
  without re-granting.
- Bring the test database up to head before running:
  `ALEMBIC_DATABASE_URL="postgresql+psycopg2://postgres:PASSWORD@localhost:5432/trackbit_school_test" uv run alembic upgrade head`

---

## Commands

Backend (from `api/`):

```bash
uv run uvicorn app.main:app --port 8000   # run the API
uv run pytest -q                          # full suite (see the warning above)
uv run pytest tests/test_lucy.py          # one file
uv run ruff check app tests               # lint (--fix to auto-fix)
uv run alembic upgrade head               # migrations
uv run alembic current                    # where the schema is
uv run python -m scripts.seed             # reseed demo data
```

Frontend (from `web/`):

```bash
npm run dev
npm run build
npm run lint
npx tsc --noEmit
```

The green bar for any change: backend = `pytest` + `ruff`; frontend = `tsc --noEmit`
+ `eslint` + `next build`.

---

## Mock data for testing setup

`test_doc/new_org/` generates a complete, valid setup pack — teachers, students and a
per-class-per-subject syllabus — for walking a **fresh organisation** through the setup
wizard. It invents a **different school every run**:

```bash
cd api && uv run python ../test_doc/new_org/generate.py
```

Then read the `SETUP.md` it writes: that's the step-by-step for the school it just
made. See `test_doc/new_org/README.md` for `--seed` and `--messy`.

---

## Where the rules are

- **`CLAUDE.md`** — the six architectural laws and five product principles, the
  database safety rules, and the `core/` vocabulary you must import rather than
  re-derive. Read it before writing backend code; they are load-bearing, not slogans.
- **`docs/architecture/FEATURE-MAP.md`** — where every feature lives, which endpoints
  serve it, and what an admin / teacher / class teacher / parent / operator can see.
- **`docs/trackbit-school-prd-v2.md`** — the current build spec (SPRD v2).
- **`docs/trackbit-product-architecture.md`** — the "why": principles and fences.
- **`docs/logs/packet-log.md`** — why a design is the way it is. History, not state:
  `Ctrl-F` the module you are touching, then stop.

Conflict order: **SPRD2 > architecture doc > SPRD v1**.
