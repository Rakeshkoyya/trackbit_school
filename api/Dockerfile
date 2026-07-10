# syntax=docker/dockerfile:1
#
# TrackBit API — production image.
# Build context: `api/`. Built by Dokploy from this Dockerfile.
#
# Runtime configuration (DATABASE_URL, ADMIN_DATABASE_URL, JWT_SECRET_KEY,
# OPENROUTER_API_KEY, ...) is injected as environment variables by the platform
# and never baked into the image — `.env` is excluded via .dockerignore.
#
# The database is a managed Postgres (Aiven); its URL must carry `?sslmode=require`.
# Two roles: ADMIN_DATABASE_URL owns the schema and runs Alembic, DATABASE_URL is a
# restricted NOBYPASSRLS role so the row-level-security policies actually apply.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# uv: fast, reproducible installs straight from the committed lock file.
RUN pip install --no-cache-dir uv

# 1) Dependencies only. Resolved from uv.lock (no dev tools, project excluded)
#    into the system Python so console scripts (alembic, gunicorn, uvicorn)
#    land on PATH. This layer is cached until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt

# 2) Application source. We run the app from /app directly (uvicorn imports
#    app.main:app), so the project itself does not need to be pip-installed.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Run as a non-root user. Nothing is written to the image at runtime — media and
# uploads go to R2 — so the whole tree can stay read-only to the app user.
RUN useradd --system --uid 1001 --create-home trackbit
USER trackbit

EXPOSE 8000

# The platform's own probe should hit /health (NOT /api/v1/health — the health
# route is mounted on the app root, outside the versioned router).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=4).status==200 else 1)"

# Migrations, worker-count safety, then exec gunicorn — see docker-entrypoint.sh.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
