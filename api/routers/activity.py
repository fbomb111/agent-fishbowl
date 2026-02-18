"""Activity feed endpoints — proxies GitHub API data."""

from fastapi import APIRouter, Query

from api.services.github import (
    get_activity_events,
    get_agent_status,
    get_threaded_activity,
)
from api.services.usage_storage import get_recent_usage

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


@router.get("/usage")
async def usage_summary(
    limit: int = Query(50, ge=1, le=200),
):
    """Aggregate token usage across recent agent runs."""
    recent = await get_recent_usage(limit=limit)

    by_role: dict[str, dict] = {}
    total_cost = 0.0
    for run_data in recent:
        for agent in run_data.get("agents", []):
            role = agent.get("role", "unknown")
            cost = agent.get("total_cost_usd") or 0
            total_cost += cost
            if role not in by_role:
                by_role[role] = {"role": role, "total_cost": 0.0, "run_count": 0}
            by_role[role]["total_cost"] = round(by_role[role]["total_cost"] + cost, 4)
            by_role[role]["run_count"] += 1

    return {
        "total_cost": round(total_cost, 2),
        "total_runs": len(recent),
        "by_role": sorted(
            by_role.values(), key=lambda x: x["total_cost"], reverse=True
        ),
    }
