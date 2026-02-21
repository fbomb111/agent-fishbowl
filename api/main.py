"""
Agent Fishbowl API

Thin FastAPI backend serving the AI news feed and activity data.
"""

import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings
from api.middleware import RequestIDMiddleware
from api.routers import activity, articles, blog, board_health, feedback, goals, stats
from api.services.blob_storage import check_storage_connectivity

logger = logging.getLogger(__name__)

settings = get_settings()

# Health check cache: (result_dict, timestamp)
_health_cache: tuple[dict[str, Any], float] | None = None
_HEALTH_CACHE_TTL = 30  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    yield


app = FastAPI(
    title="Agent Fishbowl API",
    description="AI-curated news feed built and maintained by a team of AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Request ID (runs first — outermost middleware)
app.add_middleware(RequestIDMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(articles.router, prefix="/api/fishbowl")
app.include_router(activity.router, prefix="/api/fishbowl")
app.include_router(goals.router, prefix="/api/fishbowl")
app.include_router(feedback.router, prefix="/api/fishbowl")
app.include_router(blog.router, prefix="/api/fishbowl")
app.include_router(stats.router, prefix="/api/fishbowl")
app.include_router(board_health.router, prefix="/api/fishbowl")


def _check_config() -> str:
    """Verify required configuration is loaded. Returns 'ok' or 'fail'."""
    s = get_settings()
    if s.azure_storage_account and s.azure_storage_container:
        return "ok"
    return "fail"


def _run_health_checks() -> dict[str, Any]:
    """Run all health checks, returning the full response body."""
    global _health_cache
    now = time.time()
    if _health_cache is not None:
        cached_result, cached_at = _health_cache
        if now - cached_at < _HEALTH_CACHE_TTL:
            return cached_result

    config_status = _check_config()
    storage_status = "ok" if check_storage_connectivity() else "fail"

    checks = {"config": config_status, "storage": storage_status}
    failed = [k for k, v in checks.items() if v != "ok"]

    if failed:
        overall = "degraded"
        logger.warning("Health check degraded — failed: %s", ", ".join(failed))
    else:
        overall = "ok"

    result: dict[str, Any] = {
        "status": overall,
        "service": "agent-fishbowl-api",
        "version": "0.1.0",
        "checks": checks,
    }
    _health_cache = (result, now)
    return result


@app.get("/api/fishbowl/health")
async def health_check() -> JSONResponse:
    """Health check verifying service dependencies."""
    result = _run_health_checks()
    status_code = 200 if result["status"] in ("ok", "degraded") else 503
    return JSONResponse(content=result, status_code=status_code)
