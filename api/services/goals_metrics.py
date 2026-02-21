"""Goals metrics service — GitHub data and agent activity metrics.

Thin aggregator that delegates to focused submodules:
- goals_metrics_queries: GitHub API search/count helpers
- goals_metrics_windows: Windowed trend data (24h/7d/30d)
- goals_metrics_agents: Per-agent activity stats

Re-exports all public symbols so existing imports from
``api.services.goals_metrics`` continue to work unchanged.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import agent_role as _agent_role  # noqa: F401

# Re-export submodule symbols at the original path so that existing
# imports (``from api.services.goals_metrics import _search_count``)
# and mock targets (``api.services.goals_metrics._search_count``)
# keep working without changes to callers or tests.
from api.services.goals_metrics_queries import (  # noqa: F401
    _count_commits,
    _search_count,
    _search_items,
)
from api.services.goals_metrics_agents import (  # noqa: F401
    _empty_agent_stats,
    _fetch_agent_stats,
    _fetch_commits_by_agent,
    _fetch_review_counts,
)
from api.services.goals_metrics_windows import (  # noqa: F401
    _enforce_monotonic,
    _fetch_windowed_counts,
)
from api.services.http_client import fetch_merged_prs  # noqa: F401

logger = logging.getLogger(__name__)


async def get_metrics(cache: TTLCache) -> dict[str, Any]:
    """Compute agent metrics with trend windows (24h / 7d / 30d)."""
    cached = cache.get("metrics")
    if cached is not None:
        return cached

    settings = get_settings()
    repo = settings.github_repo

    empty_window: dict[str, int] = {"24h": 0, "7d": 0, "30d": 0}
    metrics: dict[str, Any] = {
        "open_issues": 0,
        "open_prs": 0,
        "issues_closed": {**empty_window},
        "prs_merged": {**empty_window},
        "commits": {**empty_window},
        "by_agent": {},
    }

    try:
        now = datetime.now(timezone.utc)
        since_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Fetch open issues/PRs counts, windowed metrics, and agent stats in parallel
        open_issues_task = _search_count(f"repo:{repo} is:issue is:open")
        open_prs_task = _search_count(f"repo:{repo} is:pr is:open")
        windowed_task = _fetch_windowed_counts(repo, now)
        agent_stats_task = _fetch_agent_stats(repo, since_7d)

        open_issues, open_prs, windowed, agent_stats = await asyncio.gather(
            open_issues_task, open_prs_task, windowed_task, agent_stats_task
        )

        metrics["open_issues"] = open_issues if open_issues is not None else 0
        metrics["open_prs"] = open_prs if open_prs is not None else 0
        metrics["issues_closed"] = windowed["issues_closed"]
        metrics["prs_merged"] = windowed["prs_merged"]
        metrics["commits"] = windowed["commits"]
        metrics["by_agent"] = agent_stats

    except (httpx.HTTPError, httpx.TimeoutException):
        logger.exception("metrics fetch failed")
        stale = cache.get("metrics")
        if stale is not None:
            return stale

    cache.set("metrics", metrics)
    return metrics
