"""Windowed trend data for goals metrics.

Provides 24h/7d/30d cumulative trend aggregation for issues, PRs,
and commits.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from api.services.http_client import fetch_merged_prs

from .goals_metrics_queries import _count_commits, _search_count

logger = logging.getLogger(__name__)


def _enforce_monotonic(values: list[int | None]) -> list[int]:
    """Ensure cumulative window values satisfy 24h <= 7d <= 30d.

    When an API call fails (None), fill it from its neighbours.  When
    a successful value is smaller than a shorter window, clamp it up.
    """
    v24, v7, v30 = values

    # Replace None with a safe substitute: propagate from neighbours
    if v24 is None and v7 is None and v30 is None:
        return [0, 0, 0]
    if v30 is None:
        v30 = v7 if v7 is not None else (v24 if v24 is not None else 0)
    if v7 is None:
        v7 = v24 if v24 is not None else v30
    if v24 is None:
        v24 = 0

    # Clamp so 24h <= 7d <= 30d
    v7 = max(v7, v24)
    v30 = max(v30, v7)
    return [v24, v7, v30]


async def _fetch_windowed_counts(repo: str, now: datetime) -> dict[str, dict[str, int]]:
    """Fetch cumulative issue/PR/commit counts for 24h, 7d, and 30d windows."""
    cutoffs = {
        "24h": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "7d": (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "30d": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Issue counts via Search API (is:closed works reliably)
    # Use full ISO timestamps to avoid date-only rounding (#239)
    # Merged PR counts via Pulls REST API (is:merged has indexing issues — #187)
    # Fetch merged PRs for the widest window (30d) and filter client-side
    issue_tasks = [
        _search_count(f"repo:{repo} is:issue is:closed closed:>={cutoffs[window]}")
        for window in ("24h", "7d", "30d")
    ]
    commit_tasks = [
        _count_commits(repo, cutoffs[window]) for window in ("24h", "7d", "30d")
    ]

    all_merged_prs, *rest = await asyncio.gather(
        fetch_merged_prs(repo, cutoffs["30d"]),
        *issue_tasks,
        *commit_tasks,
    )

    raw_issues = [rest[0], rest[1], rest[2]]
    raw_commits = [rest[3], rest[4], rest[5]]

    # Enforce monotonicity: 24h <= 7d <= 30d.  When an API call fails
    # (returns None), fill it from its neighbours so the response is
    # never internally contradictory.
    issues = _enforce_monotonic(raw_issues)
    commits = _enforce_monotonic(raw_commits)

    # Count merged PRs per window from the single fetch
    pr_counts: dict[str, int] = {"24h": 0, "7d": 0, "30d": 0}
    for pr in all_merged_prs or []:
        merged_at = pr.get("merged_at", "")
        if not merged_at:
            continue
        for window in ("24h", "7d", "30d"):
            if merged_at >= cutoffs[window]:
                pr_counts[window] += 1

    return {
        "issues_closed": {
            "24h": issues[0],
            "7d": issues[1],
            "30d": issues[2],
        },
        "prs_merged": pr_counts,
        "commits": {
            "24h": commits[0],
            "7d": commits[1],
            "30d": commits[2],
        },
    }
