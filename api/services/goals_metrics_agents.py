"""Per-agent activity stats for goals metrics.

Review counting, commit attribution, and per-agent stats assembly.
"""

import asyncio
import logging
from typing import Any

from api.services.github_events import agent_role as _agent_role
from api.services.http_client import (
    fetch_merged_prs,
    get_shared_client,
    github_api_get,
    github_headers,
)

from .goals_metrics_queries import _search_items

logger = logging.getLogger(__name__)


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
