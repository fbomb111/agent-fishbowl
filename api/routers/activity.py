"""Activity feed endpoints — proxies GitHub API data."""

from fastapi import APIRouter, Query

from api.services.github_activity import get_activity_events, get_threaded_activity
from api.services.github_status import get_agent_status
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


_ROLE_ALIASES: dict[str, str] = {
    "product-owner": "po",
    "product-manager": "pm",
    "site-reliability": "sre",
    "user-experience": "ux",
    "infra-engineer": "ops-engineer",
}


@router.get("/usage")
async def usage_summary(
    limit: int = Query(50, ge=1, le=200),
):
    """Aggregate token usage across recent agent runs."""
    recent = await get_recent_usage(limit=limit)

    by_role: dict[str, dict] = {}
    for run_data in recent:
        run_id = run_data.get("run_id", "")
        for agent in run_data.get("agents", []):
            role = agent.get("role", "unknown")
            role = _ROLE_ALIASES.get(role, role)
            cost = agent.get("total_cost_usd") or 0
            if role not in by_role:
                by_role[role] = {
                    "role": role,
                    "total_cost": 0.0,
                    "run_ids": set(),
                }
            by_role[role]["total_cost"] += cost
            by_role[role]["run_ids"].add(run_id)

    # Finalize: convert run_ids sets to counts, round costs
    for entry in by_role.values():
        entry["run_count"] = len(entry.pop("run_ids"))
        entry["total_cost"] = round(entry["total_cost"], 4)

    total_cost = round(sum(e["total_cost"] for e in by_role.values()), 2)

    return {
        "total_cost": total_cost,
        "total_runs": len(recent),
        "by_role": sorted(
            by_role.values(), key=lambda x: x["total_cost"], reverse=True
        ),
    }
