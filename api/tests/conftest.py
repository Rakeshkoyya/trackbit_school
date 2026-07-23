"""Shared pytest fixtures."""

import os
import uuid
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ─────────────────────────────────────────────────────────────────────────
# Test-database guard — MUST run before anything imports app.core.database,
# because that module builds the engine from settings.DATABASE_URL at import.
#
# The `cleanup` fixture below hard-deletes organizations and users, and the
# suite creates orgs freely. That was safe only while DATABASE_URL pointed at
# a throwaway dev database. It now points at production (DigitalOcean), so the
# suite runs against TEST_DATABASE_URL and refuses to start if that would be
# the same database as DATABASE_URL.
#
# Escape hatch for a dev-only machine where both URLs are the same throwaway
# database: ALLOW_TESTS_ON_DATABASE_URL=1.
# ─────────────────────────────────────────────────────────────────────────


def _target(url: str) -> tuple:
    """(host, port, database) — the identity that matters for "is this the same DB"."""
    parts = urlsplit(url)
    return (parts.hostname, parts.port, parts.path)


_APP_URL = settings.DATABASE_URL
_TEST_URL = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL

if os.environ.get("ALLOW_TESTS_ON_DATABASE_URL") != "1":
    if not _TEST_URL:
        pytest.exit(
            "TEST_DATABASE_URL is not set. The suite hard-deletes orgs and users, and "
            "DATABASE_URL currently points at production. Set TEST_DATABASE_URL in "
            "api/.env to a throwaway database, or export ALLOW_TESTS_ON_DATABASE_URL=1 "
            "if DATABASE_URL really is disposable.",
            returncode=4,
        )
    if _target(_TEST_URL) == _target(_APP_URL):
        pytest.exit(
            f"TEST_DATABASE_URL and DATABASE_URL are the same database "
            f"({_target(_APP_URL)[0]}{_target(_APP_URL)[2]}). The suite would hard-delete "
            "orgs out of it. Point TEST_DATABASE_URL somewhere disposable.",
            returncode=4,
        )

# Redirect BOTH engines at the test database. `migration_database_url` (used by
# the privileged cleanup engine below) reads ADMIN_DATABASE_URL first, so it has
# to move too — otherwise cleanup would delete from production.
settings.DATABASE_URL = _TEST_URL
settings.ADMIN_DATABASE_URL = _TEST_URL

from fastapi.testclient import TestClient  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Organization, User  # noqa: E402

# Privileged session for setup/teardown (bypasses RLS) — never used by app code.
# One connection at a time is plenty: this engine only runs the cleanup deletes, and
# the server it talks to allows 20 connections in total, which the app's own pool and
# a running dev server are already drawing on.
_admin_engine = create_engine(
    settings.migration_database_url, pool_pre_ping=True, pool_size=1, max_overflow=1)
AdminSession = sessionmaker(bind=_admin_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """Keep functional tests deterministic; the 429 path is tested explicitly."""
    prev = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = prev


@pytest.fixture(autouse=True)
def _no_real_email():
    """Force the console-stub email adapter so tests never hit Resend."""
    prev = settings.RESEND_API_KEY
    settings.RESEND_API_KEY = ""
    yield
    settings.RESEND_API_KEY = prev


@pytest.fixture(autouse=True)
def _no_real_ai():
    """Force the deterministic heuristic path so tests never call OpenRouter.

    `settings.ai_configured` is just `bool(OPENROUTER_API_KEY)`, and a real key now
    lives in `api/.env`. Without this, every importer test silently posts the fixture
    to a live model: slow, costly, non-deterministic, and it fails offline. Tests that
    exercise the AI branch set the key themselves, after this fixture has run."""
    prev = settings.OPENROUTER_API_KEY
    settings.OPENROUTER_API_KEY = ""
    yield
    settings.OPENROUTER_API_KEY = prev


@pytest.fixture(autouse=True)
def _no_real_storage():
    """Force the local-disk fallback so tests never touch the real R2 bucket.

    `settings.storage_configured` is just "are all four R2_* set", and real keys now
    live in `api/.env`. Without this, every attachment/session-media test uploads a
    fixture into the production bucket — orphaned objects nobody ever cleans up — and
    the assertions expecting a local MEDIA_BASE_URL fail, because they get a presigned
    r2.cloudflarestorage.com URL back instead. Same reasoning as `_no_real_ai`.
    Tests that exercise the R2 branch set the keys themselves, after this has run."""
    prev = (settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET)
    settings.R2_ACCOUNT_ID = ""
    settings.R2_ACCESS_KEY_ID = ""
    settings.R2_SECRET_ACCESS_KEY = ""
    settings.R2_BUCKET = ""
    yield
    (settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID,
     settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET) = prev


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def cleanup():
    """Track org/user ids created during a test and hard-delete them afterwards."""
    org_ids: list[uuid.UUID] = []
    user_ids: list[uuid.UUID] = []
    yield {"orgs": org_ids, "users": user_ids}

    db = AdminSession()
    try:
        # Orgs first (cascades boards/tasks/memberships), then global users.
        for oid in org_ids:
            db.execute(delete(Organization).where(Organization.id == oid))
        for uid in user_ids:
            db.execute(delete(User).where(User.id == uid))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    """A direct app-role session for service-level unit tests. These pass explicit
    org/user ids; the `cleanup` fixture hard-deletes them afterwards."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()
