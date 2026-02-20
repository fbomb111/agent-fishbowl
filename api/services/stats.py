"""Agent team statistics — aggregates GitHub activity data.

Fetches issues closed, PRs merged, and per-agent activity from the GitHub API.
Results are cached with a 5-minute TTL.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import ACTOR_MAP
from api.services.http_client import fetch_closed_issues, fetch_merged_prs

_cache = TTLCache(ttl=300, max_size=5)


def _agent_role(login: str) -> str | None:
    """Map a GitHub login to an agent role, or None if not a known actor."""
    if login == "fbomb111":
        return "human"
    return ACTOR_MAP.get(login)


def _compute_pr_cycle_hours(pr: dict[str, Any]) -> float | None:
    """Compute hours between PR creation and merge."""
    created = pr.get("created_at")
    merged = pr.get("merged_at") or pr.get("closed_at")
    if not created or not merged:
        return None
    try:
        t_created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        t_merged = datetime.fromisoformat(merged.replace("Z", "+00:00"))
        return (t_merged - t_created).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


async def get_team_stats() -> dict[str, Any]:
    """Compute aggregate agent team statistics for the last 7 days.

    Returns a dict with:
    - issues_closed: total issues closed in last 7 days
    - prs_merged: total PRs merged in last 7 days
    - avg_pr_cycle_hours: average hours from PR open to merge
    - agents: per-agent activity counts
    - period_start: ISO timestamp of the 7-day window start
    - period_end: ISO timestamp of now
    """
    cache_key = "team_stats"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()
    repo = settings.github_repo

    now = datetime.now(UTC)
    since = now - timedelta(days=7)
    since_str = since.strftime("%Y-%m-%d")

    # Fetch closed issues and merged PRs using REST APIs instead of Search API
    # (Search API items can return 0 due to GitHub indexing issues — #186, #187)
    issues_items, prs_items = await asyncio.gather(
        fetch_closed_issues(repo, since_str),
        fetch_merged_prs(repo, since_str),
    )

    # If both API calls failed, serve stale cache rather than zeroed data (#223)
    if issues_items is None and prs_items is None:
        stale = _cache.get_stale(cache_key)
        if stale is not None:
            return stale
    # Treat None as empty for the computation below (partial failure is better
    # than returning stale data for everything)
    if issues_items is None:
        issues_items = []
    if prs_items is None:
        prs_items = []

    # Per-agent activity counts
    agent_activity: dict[str, dict[str, int]] = {}

    for item in issues_items:
        closer = item.get("user", {}).get("login", "")
        # Use assignee as the closer if available (more accurate for agent work)
        assignees = item.get("assignees", [])
        if assignees:
            closer = assignees[0].get("login", closer)
        role = _agent_role(closer)
        if role:
            agent_activity.setdefault(role, {"issues_closed": 0, "prs_merged": 0})
            agent_activity[role]["issues_closed"] += 1

    cycle_times: list[float] = []
    for item in prs_items:
        author = item.get("user", {}).get("login", "")
        role = _agent_role(author)
        if role:
            agent_activity.setdefault(role, {"issues_closed": 0, "prs_merged": 0})
            agent_activity[role]["prs_merged"] += 1

        hours = _compute_pr_cycle_hours(item)
        if hours is not None:
            cycle_times.append(hours)

    avg_cycle = round(sum(cycle_times) / len(cycle_times), 1) if cycle_times else None

    # Build per-agent list sorted by role name
    agents_list = [
        {"role": role, **counts} for role, counts in sorted(agent_activity.items())
    ]

    result: dict[str, Any] = {
        "issues_closed": len(issues_items),
        "prs_merged": len(prs_items),
        "avg_pr_cycle_hours": avg_cycle,
        "agents": agents_list,
        "period_start": since.isoformat(),
        "period_end": now.isoformat(),
    }

    _cache.set(cache_key, result)
    return result
