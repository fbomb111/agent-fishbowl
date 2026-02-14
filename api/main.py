"""
Agent Fishbowl API

Thin FastAPI backend serving the AI news feed and activity data.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routers import articles, activity

settings = get_settings()


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(articles.router, prefix="/api")
app.include_router(activity.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "ok", "service": "agent-fishbowl-api", "version": "0.1.0"}
