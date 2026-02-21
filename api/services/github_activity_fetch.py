"""GitHub activity feed — raw event fetching from multiple API sources.

Fetches events from the GitHub Events API, Issues/PRs REST API (fallback),
and GitHub Actions deploy workflow runs.
"""

import asyncio
import logging
from typing import Any

from api.config import get_settings
from api.services.github_events import _map_actor
from api.services.http_client import github_api_get

logger = logging.getLogger(__name__)


async def fetch_repo_events(
    repo: str, per_page: int, page: int
) -> list[dict[str, Any]]:
    """Fetch raw events from a single repo."""
    url = f"https://api.github.com/repos/{repo}/events"
    params = {"per_page": str(per_page), "page": str(page)}
    result = await github_api_get(url, params, context=repo)
    return result if result is not None else []


async def fetch_all_events(per_page: int = 50) -> list[dict[str, Any]]:
    """Fetch raw events from all repos, merge and sort by timestamp."""
    settings = get_settings()
    repos = [r for r in [settings.github_repo, settings.harness_repo] if r]

    if not repos:
        logger.warning("No repos configured for activity feed (GITHUB_REPO is empty)")
        return []

    raw_results = await asyncio.gather(
        *[fetch_repo_events(repo, per_page, 1) for repo in repos]
    )

    all_raw: list[dict[str, Any]] = []
    for raw in raw_results:
        all_raw.extend(raw)

    if not all_raw:
        logger.warning(
            "Events API returned 0 events from %d repo(s): %s",
            len(repos),
            ", ".join(repos),
        )

    all_raw.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return all_raw[:per_page]


async def fetch_fallback_events(limit: int = 30) -> list[dict[str, Any]]:
    """Build activity events from Issues/PRs REST API when Events API is empty.

    The GitHub Events API is best-effort and can return empty due to rate
    limits, token scope, or lag. This fallback queries the Issues and PRs
    APIs directly to construct a basic activity feed.
    """
    settings = get_settings()
    repo = settings.github_repo
    if not repo:
        return []

    issues_url = f"https://api.github.com/repos/{repo}/issues"
    params = {
        "state": "all",
        "sort": "updated",
        "direction": "desc",
        "per_page": str(limit),
    }
    raw = await github_api_get(issues_url, params, context="activity fallback")
    if not raw or not isinstance(raw, list):
        return []

    events: list[dict[str, Any]] = []
    for item in raw:
        is_pr = "pull_request" in item
        number = item.get("number")
        title = item.get("title", "")
        state = item.get("state", "")
        user = item.get("user", {})
        login = user.get("login", "unknown")
        avatar = user.get("avatar_url")

        actor = _map_actor(login)

        if is_pr:
            pr_data = item.get("pull_request", {})
            merged = pr_data.get("merged_at") is not None
            if merged:
                evt_type = "pr_merged"
                desc = f"Merged PR #{number}: {title}"
                ts = pr_data.get("merged_at") or item.get("updated_at", "")
            elif state == "open":
                evt_type = "pr_opened"
                desc = f"Opened PR #{number}: {title}"
                ts = item.get("created_at", "")
            else:
                continue
            events.append(
                {
                    "id": f"fallback-pr-{number}",
                    "type": evt_type,
                    "actor": actor,
                    "avatar_url": avatar,
                    "description": desc,
                    "timestamp": ts,
                    "url": item.get("html_url"),
                    "subject_type": "pr",
                    "subject_number": number,
                    "subject_title": title,
                }
            )
        else:
            if state == "open":
                evt_type = "issue_created"
                desc = f"Opened issue #{number}: {title}"
                ts = item.get("created_at", "")
            elif state == "closed":
                evt_type = "issue_closed"
                desc = f"Closed issue #{number}: {title}"
                ts = item.get("closed_at") or item.get("updated_at", "")
            else:
                continue
            events.append(
                {
                    "id": f"fallback-issue-{number}",
                    "type": evt_type,
                    "actor": actor,
                    "avatar_url": avatar,
                    "description": desc,
                    "timestamp": ts,
                    "url": item.get("html_url"),
                    "subject_type": "issue",
                    "subject_number": number,
                    "subject_title": title,
                }
            )

    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events[:limit]


async def fetch_deploy_events(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent deploy workflow runs and convert them to activity events.

    Queries the GitHub Actions API for the deploy.yml workflow runs and
    creates standalone deploy events with status (success/failure).
    """
    settings = get_settings()
    repo = settings.github_repo
    if not repo:
        return []

    url = f"https://api.github.com/repos/{repo}/actions/workflows/deploy.yml/runs"
    data = await github_api_get(
        url,
        params={"per_page": str(limit)},
        context="deploy workflow runs",
    )
    if not data or not isinstance(data, dict):
        return []

    runs = data.get("workflow_runs", [])
    events: list[dict[str, Any]] = []
    for run in runs:
        if run.get("status") != "completed":
            continue

        conclusion = run.get("conclusion", "unknown")
        head_sha = run.get("head_sha", "")[:7]
        title = run.get("display_title", "")
        run_url = run.get("html_url", "")
        created_at = run.get("created_at", "")
        actor_login = run.get("actor", {}).get("login", "")
        actor_avatar = run.get("actor", {}).get("avatar_url")

        if conclusion == "success":
            status_label = "healthy"
            desc = f"Deployed {head_sha}: {title}"
        elif conclusion == "failure":
            status_label = "failed"
            desc = f"Deploy failed {head_sha}: {title}"
        else:
            status_label = conclusion
            desc = f"Deploy {conclusion} {head_sha}: {title}"

        events.append(
            {
                "id": f"deploy-{run.get('id', '')}",
                "type": "deploy",
                "actor": _map_actor(actor_login),
                "avatar_url": actor_avatar,
                "description": desc,
                "timestamp": created_at,
                "url": run_url,
                "deploy_status": status_label,
            }
        )

    return events
