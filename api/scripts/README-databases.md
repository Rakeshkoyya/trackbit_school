# Which database am I talking to?

`api/.env` is the single source of truth, it is gitignored, and **it says which mode it is in** —
look for the `# ─── ACTIVE: …` banner at the top of the `DATABASE_URL` block. The inactive URLs sit
beside it as `# LOCAL_*_BACKUP=` / `# PROD_*_BACKUP=` comments. Those prod comments are the only
copy of the credentials outside Dokploy: **do not delete them.**

## The three URLs

| var | local mode | prod mode | used by |
|---|---|---|---|
| `DATABASE_URL` | `trackbit_school_app` (**NOBYPASSRLS**) @ localhost | `doadmin` @ DigitalOcean | the app |
| `ADMIN_DATABASE_URL` | `postgres` @ localhost | `doadmin` @ DigitalOcean | Alembic only |
| `TEST_DATABASE_URL` | `trackbit_school_app` @ `localhost/trackbit_school_test` | **stays local** | pytest |

🚨 **`TEST_DATABASE_URL` never leaves the local test database.** The suite creates and hard-deletes
organizations. `conftest.py` refuses to run if it resolves to the same host+database as
`DATABASE_URL`, but it cannot know that some *other* remote database is precious — so treat that
line as read-only. In prod mode especially: do not run `pytest` without re-checking it.

Never point the app or the tests at `postgres` either: a superuser bypasses RLS entirely — `FORCE
ROW LEVEL SECURITY` does not stop it — and `test_rls.py` then fails for reasons unrelated to the
code. (In prod mode the app runs as `doadmin`, which also bypasses RLS, so prefer local for
anything security-related.)

## Talking to the other database without editing `.env`

Environment variables win over `.env`, so a one-off command can target prod while the file keeps
pointing at local:

```bash
# read the parked prod URL out of .env, use it for ONE command
PROD=$(python -c "import re,pathlib;print(re.search(r'^# PROD_DATABASE_URL_BACKUP=(.*)$',
  pathlib.Path('.env').read_text(encoding='utf-8'),flags=re.M).group(1))")

DATABASE_URL="$PROD" uv run python -m scripts.demo_activity --org sunrise
ALEMBIC_DATABASE_URL="$PROD" uv run alembic current      # alembic reads its own override
```

To point the running app at prod, swap `DATABASE_URL` in `.env` to the parked value and restart
uvicorn. Swap it back afterwards — and **never** run pytest while `.env` points at prod.

## Populating a school with activity

`scripts/seed.py` builds the school (year, classes, students, timetable, plans).
`scripts/demo_activity.py` fills in what a school *does with it*, which is what the dashboard
reads: marked periods, lesson logs, homework checks, staff attendance, timesheets, leave, checks.

```bash
uv run python -m scripts.demo_activity                     # active org, 10 school days
uv run python -m scripts.demo_activity --org sunrise --days 8
```

Every write goes through the real service, so the data is shaped exactly the way the app would
write it. It is idempotent (full-replace / get-or-create) and deterministic (RNG seeded from the
org id), and it commits per phase — against a remote database it runs for many minutes, and a
dropped connection should not throw the whole run away. Re-running resumes.

It deliberately leaves gaps: ~12% of periods uncaptured, ~25% of homework unchecked, and most free
periods without a timesheet entry. A board where everything is green tells you nothing about
whether it works.
