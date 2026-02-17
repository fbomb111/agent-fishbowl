"""Activity feed endpoints — proxies GitHub API data."""

from fastapi import APIRouter, Query

from api.services.github import (
    get_activity_events,
    get_agent_status,
    get_threaded_activity,
)

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def list_activity(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    mode: str = Query("threaded", regex="^(flat|threaded)$"),
):
    """Get the agent activity feed from GitHub.

    mode=flat returns a simple list of events.
    mode=threaded (default) groups events by issue/PR into threads.
    """
    if mode == "threaded":
        threads = await get_threaded_activity(per_page=per_page)
        return {"threads": threads, "mode": "threaded"}

    events = await get_activity_events(page=page, per_page=per_page)
    return {"events": events, "page": page, "per_page": per_page, "mode": "flat"}


@router.get("/agent-status")
async def agent_status():
    """Get current status of each agent from workflow runs."""
    agents = await get_agent_status()
    return {"agents": agents}
