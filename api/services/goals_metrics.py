"""Goals metrics service — GitHub data and agent activity metrics.

Provides windowed trend data (24h/7d/30d) and per-agent stats,
cached with a shared TTL cache. Uses the GitHub Search API for
accurate issue/PR counts (the Events API is capped at ~300 events).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import ACTOR_MAP
from api.services.http_client import get_shared_client, github_api_get, github_headers

logger = logging.getLogger(__name__)


def _agent_role(login: str) -> str | None:
    """Map a GitHub login to an agent role, or None if not a known agent."""
    if login == "fbomb111":
        return "human"
    return ACTOR_MAP.get(login)


async def _search_count(query: str) -> int:
    """Run a GitHub search and return the total_count."""
    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": "1"}
    client = get_shared_client()
    headers = github_headers()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json().get("total_count", 0)
        logger.warning("GitHub search API returned %d for: %s", resp.status_code, query)
    except Exception:
        logger.exception("GitHub search error for: %s", query)
    return 0


async def _search_items(query: str) -> list[dict[str, Any]]:
    """Run a GitHub search and return all items (up to 100)."""
    result = await github_api_get(
        "https://api.github.com/search/issues",
        {"q": query, "per_page": "100"},
        response_key="items",
        context=query,
    )
    return result if result is not None else []


async def _count_commits(repo: str, since: str) -> int:
    """Count commits on default branch since a given ISO date."""
    url = f"https://api.github.com/repos/{repo}/commits"
    params = {"since": since, "per_page": "1"}
    client = get_shared_client()
    headers = github_headers()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return 0
        # Use the Link header to get total count if available
        # Otherwise fall back to fetching all and counting
        link = resp.headers.get("Link", "")
        if 'rel="last"' in link:
            # Parse last page number from Link header
            for part in link.split(","):
                if 'rel="last"' in part:
                    url_part = part.split(";")[0].strip().strip("<>")
                    for param in url_part.split("?")[1].split("&"):
                        if param.startswith("page="):
                            return int(param.split("=")[1])
        # If no Link header, the result fits in one page
        return len(resp.json())
    except Exception:
        logger.exception("Commits count error")
        return 0


async def _fetch_windowed_counts(repo: str, now: datetime) -> dict[str, dict[str, int]]:
    """Fetch cumulative issue/PR/commit counts for 24h, 7d, and 30d windows."""
    cutoffs = {
        "24h": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "7d": (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "30d": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    date_cutoffs = {
        "24h": (now - timedelta(hours=24)).strftime("%Y-%m-%d"),
        "7d": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
        "30d": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
    }

    # Build all search queries — 6 searches for issues/PRs + 3 commit counts
    tasks = []
    for window in ("24h", "7d", "30d"):
        tasks.append(
            _search_count(
                f"repo:{repo} is:issue is:closed closed:>={date_cutoffs[window]}"
            )
        )
        tasks.append(
            _search_count(
                f"repo:{repo} is:pr is:merged merged:>={date_cutoffs[window]}"
            )
        )
        tasks.append(_count_commits(repo, cutoffs[window]))

    results = await asyncio.gather(*tasks)

    return {
        "issues_closed": {
            "24h": results[0],
            "7d": results[3],
            "30d": results[6],
        },
        "prs_merged": {
            "24h": results[1],
            "7d": results[4],
            "30d": results[7],
        },
        "commits": {
            "24h": results[2],
            "7d": results[5],
            "30d": results[8],
        },
    }


async def _fetch_agent_stats(repo: str, since_str: str) -> dict[str, dict[str, int]]:
    """Fetch per-agent activity stats for the last 7 days using the Search API."""
    issues_query = f"repo:{repo} is:issue is:closed closed:>={since_str}"
    prs_query = f"repo:{repo} is:pr is:merged merged:>={since_str}"

    issues_items, prs_items = await asyncio.gather(
        _search_items(issues_query),
        _search_items(prs_query),
    )

    agent_stats: dict[str, dict[str, int]] = {}

    for item in issues_items:
        # Use assignee as closer (more accurate for agent work)
        assignees = item.get("assignees", [])
        login = assignees[0].get("login", "") if assignees else ""
        if not login:
            login = item.get("user", {}).get("login", "")
        role = _agent_role(login)
        if not role:
            continue
        if role not in agent_stats:
            agent_stats[role] = {
                "issues_opened": 0,
                "issues_closed": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "reviews": 0,
                "commits": 0,
            }
        agent_stats[role]["issues_closed"] += 1

    for item in prs_items:
        login = item.get("user", {}).get("login", "")
        role = _agent_role(login)
        if not role:
            continue
        if role not in agent_stats:
            agent_stats[role] = {
                "issues_opened": 0,
                "issues_closed": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "reviews": 0,
                "commits": 0,
            }
        agent_stats[role]["prs_merged"] += 1

    return agent_stats


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
        now = datetime.now(UTC)
        since_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # Fetch open issues/PRs counts, windowed metrics, and agent stats in parallel
        open_issues_task = _search_count(f"repo:{repo} is:issue is:open")
        open_prs_task = _search_count(f"repo:{repo} is:pr is:open")
        windowed_task = _fetch_windowed_counts(repo, now)
        agent_stats_task = _fetch_agent_stats(repo, since_7d)

        open_issues, open_prs, windowed, agent_stats = await asyncio.gather(
            open_issues_task, open_prs_task, windowed_task, agent_stats_task
        )

        metrics["open_issues"] = open_issues
        metrics["open_prs"] = open_prs
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
