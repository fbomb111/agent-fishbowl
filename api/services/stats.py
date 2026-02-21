"""Agent team statistics — aggregates GitHub activity data.

Fetches issues closed, PRs merged, and per-agent activity from the GitHub API.
Results are cached with a 5-minute TTL.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import agent_role as _agent_role
from api.services.http_client import fetch_closed_issues, fetch_merged_prs

_cache = TTLCache(ttl=300, max_size=5)


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

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    since_str = since.strftime("%Y-%m-%d")

    # Fetch closed issues and merged PRs using REST APIs instead of Search API
    # (Search API can return 0 due to GitHub indexing issues — #186, #187, #338, #354)
    issues_items, prs_items = await asyncio.gather(
        fetch_closed_issues(repo, since_str),
        fetch_merged_prs(repo, since_str),
    )

    # If both API calls failed, serve stale cache rather than zeroed data (#223)
    if issues_items is None and prs_items is None:
        stale = _cache.get_stale(cache_key)
        if stale is not None:
            return stale

    # On partial failure, preserve stale values for the failed component
    # rather than reporting zeros (#302)
    issues_failed = issues_items is None
    prs_failed = prs_items is None
    stale = None
    if issues_failed or prs_failed:
        stale = _cache.get_stale(cache_key)

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

    # Substitute stale values for failed components (#302)
    if stale is not None:
        if issues_failed:
            result["issues_closed"] = stale.get("issues_closed", 0)
        if prs_failed:
            result["prs_merged"] = stale.get("prs_merged", 0)
            result["avg_pr_cycle_hours"] = stale.get("avg_pr_cycle_hours")
        # Merge per-agent data: use stale data for roles absent in fresh data
        if issues_failed or prs_failed:
            stale_agents = {a["role"]: a for a in stale.get("agents", [])}
            fresh_roles = {a["role"] for a in agents_list}
            for role, agent_data in stale_agents.items():
                if role not in fresh_roles:
                    agents_list.append(agent_data)
                else:
                    # Supplement missing fields from stale data
                    fresh_agent = next(a for a in agents_list if a["role"] == role)
                    if prs_failed:
                        fresh_agent["prs_merged"] = agent_data.get("prs_merged", 0)
                    if issues_failed:
                        fresh_agent["issues_closed"] = agent_data.get(
                            "issues_closed", 0
                        )
            agents_list.sort(key=lambda a: a["role"])
            result["agents"] = agents_list

    _cache.set(cache_key, result)
    return result
