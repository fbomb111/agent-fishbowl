"""Goals service — aggregates goals, roadmap, and metrics into a single response.

This module owns the shared TTL cache and delegates to focused sub-modules:
- goals_parser: Parses config/goals.md
- goals_roadmap: Fetches roadmap from GitHub Project
- goals_metrics: Computes agent activity metrics from GitHub API
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from api.services.cache import TTLCache
from api.services.goals_metrics import get_metrics
from api.services.goals_parser import Goal, GoalsFileData, parse_goals_file
from api.services.goals_roadmap import RoadmapItem, get_roadmap_snapshot

# Re-export types so existing imports from api.services.goals still work
__all__ = [
    "Goal",
    "GoalsFileData",
    "RoadmapItem",
    "get_goals_data",
    "parse_goals_file",
]

# Shared TTL cache for roadmap and metrics data
_cache = TTLCache(ttl=300, max_size=10)


async def get_goals_data() -> dict[str, Any]:
    """Get all goals dashboard data in one call."""
    goals_data = parse_goals_file()
    roadmap_snapshot, agent_metrics = await asyncio.gather(
        get_roadmap_snapshot(_cache),
        get_metrics(_cache),
    )

    return {
        "mission": goals_data["mission"],
        "goals": goals_data["goals"],
        "constraints": goals_data["constraints"],
        "roadmap": roadmap_snapshot,
        "metrics": agent_metrics,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
