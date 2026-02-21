"""Goals metrics service — GitHub data and agent activity metrics.

Provides windowed trend data (24h/7d/30d) and per-agent stats,
cached with a shared TTL cache. Uses the GitHub Search API for
accurate issue/PR counts (the Events API is capped at ~300 events).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import agent_role as _agent_role
from api.services.http_client import (
    fetch_merged_prs,
    get_shared_client,
    github_api_get,
    github_headers,
)

logger = logging.getLogger(__name__)


async def _search_count(query: str) -> int | None:
    """Run a GitHub search and return the total_count.

    Returns None on API errors so callers can distinguish "zero results"
    from "request failed".
    """
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
    return None


async def _search_items(query: str) -> list[dict[str, Any]] | None:
    """Run a GitHub search and return all items, paginating if needed.

    The GitHub Search API returns at most 100 items per page (max 1000 total).
    This function fetches successive pages until all results are collected.

    Returns None on API errors so callers can distinguish "no results"
    from "request failed".
    """
    client = get_shared_client()
    headers = github_headers()
    url = "https://api.github.com/search/issues"
    all_items: list[dict[str, Any]] = []
    page = 1

    while True:
        params = {"q": query, "per_page": "100", "page": str(page)}
        try:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "GitHub search API returned %d for: %s (page %d)",
                    resp.status_code,
                    query,
                    page,
                )
                return None if not all_items else all_items
            data = resp.json()
            items = data.get("items", [])
            all_items.extend(items)
            total_count = data.get("total_count", 0)
            if len(all_items) >= total_count or len(items) < 100:
                break
            page += 1
        except Exception:
            logger.exception("GitHub search error for: %s (page %d)", query, page)
            return None if not all_items else all_items

    return all_items


async def _count_commits(repo: str, since: str) -> int | None:
    """Count commits on default branch since a given ISO date.

    Returns None on API errors so callers can distinguish "zero commits"
    from "request failed".
    """
    url = f"https://api.github.com/repos/{repo}/commits"
    params = {"since": since, "per_page": "1"}
    client = get_shared_client()
    headers = github_headers()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return None
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
        return None


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


def _empty_agent_stats() -> dict[str, int]:
    """Return a fresh per-agent stats dict."""
    return {
        "issues_opened": 0,
        "issues_closed": 0,
        "prs_opened": 0,
        "prs_merged": 0,
        "reviews": 0,
        "commits": 0,
    }


async def _fetch_review_counts(repo: str, since_str: str) -> dict[str, int]:
    """Count PR reviews per agent role within the time window.

    Fetches recently updated PRs (open and closed), then fetches reviews
    for each and counts those submitted on or after since_str.
    """
    # Fetch recently updated PRs (both open and closed) to find review activity
    client = get_shared_client()
    headers = github_headers()
    pr_numbers: list[int] = []

    if "T" not in since_str:
        since_iso = since_str + "T00:00:00Z"
    else:
        since_iso = since_str

    for state in ("open", "closed"):
        page = 1
        while True:
            url = f"https://api.github.com/repos/{repo}/pulls"
            params = {
                "state": state,
                "sort": "updated",
                "direction": "desc",
                "per_page": "100",
                "page": str(page),
            }
            try:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    break
                items = resp.json()
                if not items:
                    break
                for pr in items:
                    pr_numbers.append(pr["number"])
                # Stop if oldest item on this page was updated before our window
                oldest_updated = items[-1].get("updated_at", "")
                if oldest_updated and oldest_updated < since_iso:
                    break
                if len(items) < 100:
                    break
                page += 1
            except Exception:
                logger.exception("PR list error (state=%s, page=%d)", state, page)
                break

    if not pr_numbers:
        return {}

    # Fetch reviews for each PR in parallel
    async def _get_reviews(pr_number: int) -> list[dict[str, Any]]:
        result = await github_api_get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
            context=f"reviews for PR #{pr_number}",
        )
        return result if isinstance(result, list) else []

    all_reviews = await asyncio.gather(*[_get_reviews(n) for n in pr_numbers])

    # Count reviews per agent role, filtering by submission date
    counts: dict[str, int] = {}
    for reviews in all_reviews:
        for review in reviews:
            submitted_at = review.get("submitted_at", "")
            if not submitted_at or submitted_at < since_iso:
                continue
            login = review.get("user", {}).get("login", "")
            role = _agent_role(login)
            if not role:
                continue
            counts[role] = counts.get(role, 0) + 1

    return counts


async def _fetch_commits_by_agent(repo: str, since_str: str) -> dict[str, int]:
    """Count commits per agent role within the time window.

    Fetches all commits in the window and attributes them client-side
    using commit.author.login. The GitHub Commits API author parameter
    does not work for bot accounts, so we fetch all and filter locally.
    """
    if "T" not in since_str:
        since_iso = since_str + "T00:00:00Z"
    else:
        since_iso = since_str

    client = get_shared_client()
    headers = github_headers()
    all_commits: list[dict[str, Any]] = []
    page = 1

    while True:
        url = f"https://api.github.com/repos/{repo}/commits"
        params = {"since": since_iso, "per_page": "100", "page": str(page)}
        try:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break
            all_commits.extend(items)
            if len(items) < 100:
                break
            page += 1
        except Exception:
            logger.exception("Commits fetch error (page=%d)", page)
            break

    counts: dict[str, int] = {}
    for commit in all_commits:
        login = (commit.get("author") or {}).get("login", "")
        role = _agent_role(login)
        if not role:
            continue
        counts[role] = counts.get(role, 0) + 1
    return counts


async def _fetch_agent_stats(repo: str, since_str: str) -> dict[str, dict[str, int]]:
    """Fetch per-agent activity stats for the last 7 days."""
    issues_closed_query = f"repo:{repo} is:issue is:closed closed:>={since_str}"
    issues_opened_query = f"repo:{repo} is:issue created:>={since_str}"
    prs_opened_query = f"repo:{repo} is:pr created:>={since_str}"

    (
        issues_closed_items,
        issues_opened_items,
        prs_opened_items,
        prs_merged_items,
        review_counts,
        commit_counts,
    ) = await asyncio.gather(
        _search_items(issues_closed_query),
        _search_items(issues_opened_query),
        _search_items(prs_opened_query),
        fetch_merged_prs(repo, since_str),
        _fetch_review_counts(repo, since_str),
        _fetch_commits_by_agent(repo, since_str),
    )

    agent_stats: dict[str, dict[str, int]] = {}

    # Only process each category if its API call succeeded (not None).
    # Skipping failed categories avoids overwriting real data with zeros.
    if issues_closed_items is not None:
        for item in issues_closed_items:
            # Use assignee as closer (more accurate for agent work)
            assignees = item.get("assignees", [])
            login = assignees[0].get("login", "") if assignees else ""
            if not login:
                login = item.get("user", {}).get("login", "")
            role = _agent_role(login)
            if not role:
                continue
            if role not in agent_stats:
                agent_stats[role] = _empty_agent_stats()
            agent_stats[role]["issues_closed"] += 1

    if issues_opened_items is not None:
        for item in issues_opened_items:
            login = item.get("user", {}).get("login", "")
            role = _agent_role(login)
            if not role:
                continue
            if role not in agent_stats:
                agent_stats[role] = _empty_agent_stats()
            agent_stats[role]["issues_opened"] += 1

    if prs_opened_items is not None:
        for item in prs_opened_items:
            login = item.get("user", {}).get("login", "")
            role = _agent_role(login)
            if not role:
                continue
            if role not in agent_stats:
                agent_stats[role] = _empty_agent_stats()
            agent_stats[role]["prs_opened"] += 1

    for item in prs_merged_items or []:
        login = item.get("user", {}).get("login", "")
        role = _agent_role(login)
        if not role:
            continue
        if role not in agent_stats:
            agent_stats[role] = _empty_agent_stats()
        agent_stats[role]["prs_merged"] += 1

    # Merge review counts into agent stats
    for role, count in review_counts.items():
        if role not in agent_stats:
            agent_stats[role] = _empty_agent_stats()
        agent_stats[role]["reviews"] = count

    # Merge commit counts into agent stats
    for role, count in commit_counts.items():
        if role not in agent_stats:
            agent_stats[role] = _empty_agent_stats()
        agent_stats[role]["commits"] = count

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
