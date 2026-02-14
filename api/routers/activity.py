"""Activity feed endpoints — proxies GitHub API data."""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def list_activity(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get the agent activity feed from GitHub."""
    # Phase 4: GitHub API client with caching
    return {"events": [], "page": page, "per_page": per_page}
