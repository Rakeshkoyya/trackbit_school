"""Shared pytest fixtures."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.rate_limit import limiter
from app.main import app
from app.models import Organization, User

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
