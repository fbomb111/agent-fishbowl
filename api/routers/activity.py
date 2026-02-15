"""Activity feed endpoints — proxies GitHub API data."""

from fastapi import APIRouter, Query

from api.services.github import get_activity_events

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def list_activity(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get the agent activity feed from GitHub."""
    events = await get_activity_events(page=page, per_page=per_page)
    return {"events": events, "page": page, "per_page": per_page}
