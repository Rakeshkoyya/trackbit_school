#!/bin/sh
set -e

# ─────────────────────────────────────────────────────────────────────────
# TrackBit API container start.
#
#   1. apply migrations
#   2. decide the worker count
#   3. exec gunicorn (exec, so it becomes PID 1 and receives SIGTERM directly —
#      otherwise the shell swallows it and the platform kills the container
#      after the grace period instead of letting it drain)
#
# The worker count is not a free choice. APScheduler starts *inside each
# worker process*, so a container with ENABLE_SCHEDULER=true and two workers
# runs every cron job twice: two daily reports, two teacher reminders, and —
# the one that actually reaches a human — two absence alerts per absent
# student, to their guardian's phone.
#
# So: when the scheduler is on, this container serves with exactly one worker.
# Run ONE such instance, and scale the rest with ENABLE_SCHEDULER unset.
# ─────────────────────────────────────────────────────────────────────────

: "${WEB_CONCURRENCY:=2}"
: "${PORT:=8000}"

case "$(printf '%s' "${ENABLE_SCHEDULER:-false}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|on)
    if [ "$WEB_CONCURRENCY" != "1" ]; then
      echo "[entrypoint] ENABLE_SCHEDULER is on — forcing 1 worker (was ${WEB_CONCURRENCY})"
      echo "[entrypoint]   background jobs run per-worker; >1 would duplicate every job"
    fi
    WEB_CONCURRENCY=1
    ;;
esac

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
fi

echo "[entrypoint] gunicorn on :${PORT} with ${WEB_CONCURRENCY} worker(s)"
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w "$WEB_CONCURRENCY" \
  -b "0.0.0.0:${PORT}" \
  --access-logfile - \
  --error-logfile - \
  --timeout 120 \
  --graceful-timeout 30
