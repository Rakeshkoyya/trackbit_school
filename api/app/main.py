"""TrackBit API entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s %s starting", settings.APP_NAME, settings.APP_VERSION)
    from app.core.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # --- The agent surface, mounted at the ROOT, not under /api/v1 -------
    # RFC 9728/8414 require the metadata at `/.well-known/...` on the origin,
    # and the issuer those documents advertise is the bare origin — so the
    # OAuth and MCP endpoints have to live beside /health rather than under the
    # versioned prefix. Claude reads that metadata to find them (`D-99`).
    from app.api.v1.endpoints.oauth import root_router as oauth_root_router
    from app.mcp import mcp_router, well_known_router

    app.include_router(well_known_router, tags=["mcp"])
    app.include_router(oauth_root_router, tags=["mcp"])
    app.include_router(mcp_router, tags=["mcp"])

    # Local-disk attachment serving (dev/stub mode). In production, R2 serves
    # objects directly and this mount is skipped.
    if not settings.storage_configured:
        from pathlib import Path

        from fastapi.staticfiles import StaticFiles

        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "name": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/health/metrics")
    def health_metrics() -> dict:
        # Launch requirement: monitor failed notification deliveries (plan §8.5).
        from app.services.jobs import failed_count

        return {"failed_notifications": failed_count()}

    return app


app = create_app()
