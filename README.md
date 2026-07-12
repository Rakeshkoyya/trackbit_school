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

We use a **managed Postgres (Aiven)**. You do not install or run Postgres — you
connect to the shared one. Two URLs, and the split is load-bearing:

- `DATABASE_URL` → a **restricted** role (`NOBYPASSRLS`). The app uses this, so
  Row-Level Security actually applies.
- `ADMIN_DATABASE_URL` → the schema owner. **Alembic only.**

Pointing the app at the admin URL would silently disable every RLS policy. Don't.

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

There are two roles: **admin** (runs the school) and **teacher**. Teachers never see
fees. Parents have no login at all — guardians only receive outbound notifications.

---

## ⚠️ Read this before you run the tests

The test suite needs a real Postgres and **currently runs against the shared
development database** — the same one the seed and your running app use.

`TEST_DATABASE_URL` exists in `config.py` but **nothing reads it**; `pytest` connects
via `DATABASE_URL`. The suite **creates and hard-deletes organisations**.

So:

- **Coordinate before running `uv run pytest`.** If a teammate is mid-demo on the
  shared dev DB, your test run can delete data out from under them.
- **Never point `DATABASE_URL` at production and run the suite.** There is no safety
  net today. Wiring `conftest.py` to honour `TEST_DATABASE_URL` is a known TODO and
  must land before a production database exists.
- The Aiven instance caps `max_connections` at **20**. Don't run the API server and
  the full suite at the same time, and kill stale idle sessions if you hit
  "too many connections".

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

- **`CLAUDE.md`** — the six architectural laws and five product principles. Read it
  before writing backend code; they are load-bearing, not slogans.
- **`docs/trackbit-school-prd-v2.md`** — the current build spec (SPRD v2).
- **`docs/trackbit-product-architecture.md`** — the "why": principles and fences.

Conflict order: **SPRD2 > architecture doc > SPRD v1**.
