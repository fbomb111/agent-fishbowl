"""Goals metrics service — fetches GitHub data and computes agent activity metrics.

Provides windowed trend data (24h/7d/30d) and per-agent stats, cached with a shared TTL cache.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import ACTOR_MAP
from api.services.http_client import get_shared_client, github_headers

logger = logging.getLogger(__name__)


def _parse_event_timestamp(event: dict[str, Any]) -> float:
    """Parse GitHub event created_at to Unix timestamp."""
    ts_str = event.get("created_at", "")
    if not ts_str:
        return 0.0
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _bucket_event(event_ts: float, now: float) -> str | None:
    """Assign an event to a time window: 24h, 7d, or 30d."""
    age = now - event_ts
    if age <= 86400:
        return "24h"
    if age <= 604800:
        return "7d"
    if age <= 2592000:
        return "30d"
    return None


async def _fetch_github_data(
    headers: dict[str, str], repo: str
) -> tuple[list[Any], list[Any], list[Any]]:
    """Make the three parallel GitHub API calls for metrics.

    Returns:
        Tuple of (issues, prs, events) — each is a list of dicts or empty on error.
    """
    client = get_shared_client()
    base = f"https://api.github.com/repos/{repo}"

    issues_resp, prs_resp, events_resp = await asyncio.gather(
        client.get(
            f"{base}/issues",
            headers=headers,
            params={"state": "open", "per_page": "100"},
        ),
        client.get(
            f"{base}/pulls",
            headers=headers,
            params={"state": "open", "per_page": "100"},
        ),
        client.get(
            f"{base}/events",
            headers=headers,
            params={"per_page": "100"},
        ),
    )

    issues = issues_resp.json() if issues_resp.status_code == 200 else []
    prs = prs_resp.json() if prs_resp.status_code == 200 else []
    events = events_resp.json() if events_resp.status_code == 200 else []

    for name, resp in [
        ("issues", issues_resp),
        ("pulls", prs_resp),
        ("events", events_resp),
    ]:
        if resp.status_code != 200:
            logger.warning("GitHub %s API returned %d", name, resp.status_code)

    return issues, prs, events


def _process_events(
    events: list[dict[str, Any]], now: float
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Process GitHub events into bucketed metrics and per-agent stats.

    Returns:
        Tuple of (windowed_counts, agent_stats).
        windowed_counts has keys: issues_closed, prs_merged, commits — each with 24h/7d/30d.
        agent_stats is keyed by agent role with action counts.
    """
    empty_window: dict[str, int] = {"24h": 0, "7d": 0, "30d": 0}
    windowed: dict[str, dict[str, int]] = {
        "issues_closed": {**empty_window},
        "prs_merged": {**empty_window},
        "commits": {**empty_window},
    }
    agent_stats: dict[str, dict[str, int]] = {}

    for event in events:
        login = event.get("actor", {}).get("login", "unknown")
        role = ACTOR_MAP.get(login, login)
        if role == "org":
            continue
        event_type = event.get("type", "")
        payload = event.get("payload", {})
        event_ts = _parse_event_timestamp(event)
        bucket = _bucket_event(event_ts, now)

        if role not in agent_stats:
            agent_stats[role] = {
                "issues_opened": 0,
                "issues_closed": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "reviews": 0,
                "commits": 0,
            }

        if event_type == "IssuesEvent":
            action = payload.get("action", "")
            if action == "opened":
                agent_stats[role]["issues_opened"] += 1
            elif action == "closed":
                agent_stats[role]["issues_closed"] += 1
                if bucket:
                    windowed["issues_closed"][bucket] += 1
        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            if action == "opened":
                agent_stats[role]["prs_opened"] += 1
            elif action == "closed" and pr.get("merged"):
                agent_stats[role]["prs_merged"] += 1
                if bucket:
                    windowed["prs_merged"][bucket] += 1
        elif event_type == "PullRequestReviewEvent":
            agent_stats[role]["reviews"] += 1
        elif event_type == "PushEvent":
            commit_count = len(payload.get("commits", []))
            agent_stats[role]["commits"] += commit_count
            if bucket:
                windowed["commits"][bucket] += commit_count

    return windowed, agent_stats


async def get_metrics(cache: TTLCache) -> dict[str, Any]:
    """Compute agent metrics with trend windows (24h / 7d / 30d)."""
    cached = cache.get("metrics")
    if cached is not None:
        return cached

    settings = get_settings()
    headers = github_headers()
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
        now = time.time()
        issues, prs, events = await _fetch_github_data(headers, repo)

        metrics["open_issues"] = sum(1 for i in issues if "pull_request" not in i)
        metrics["open_prs"] = len(prs)

        if events:
            windowed, agent_stats = _process_events(events, now)
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
