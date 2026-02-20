"""Shared HTTP client utilities — reusable httpx client."""

import logging
from datetime import datetime
from typing import Any

import httpx

from api.config import get_settings

logger = logging.getLogger(__name__)

# Module-level shared client (created lazily, lives for the process lifetime)
_client: httpx.AsyncClient | None = None


def get_shared_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient, creating it on first call."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


def github_headers() -> dict[str, str]:
    """Build standard GitHub API request headers.

    Includes the Authorization header only when a token is configured.
    """
    settings = get_settings()
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def github_api_get(
    url: str,
    params: dict[str, str] | None = None,
    *,
    response_key: str | None = None,
    context: str = "",
) -> list[Any] | dict[str, Any] | None:
    """Fetch a GitHub API endpoint with standard error handling.

    Returns parsed JSON (or the value at response_key if specified).
    Returns None on any error so callers can apply their own fallback.
    """
    client = get_shared_client()
    headers = github_headers()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            logger.warning(
                "GitHub API %d for %s%s",
                resp.status_code,
                url,
                f" ({context})" if context else "",
            )
            return None
        data = resp.json()
        return data.get(response_key, []) if response_key else data
    except Exception:
        logger.exception(
            "GitHub API error for %s%s", url, f" ({context})" if context else ""
        )
        return None


async def fetch_closed_issues(repo: str, since: str) -> list[dict[str, Any]]:
    """Fetch issues closed since a date using the Issues REST API.

    Uses /repos/{owner}/{repo}/issues?state=closed instead of the Search API,
    which can return 0 items due to GitHub indexing issues.

    Args:
        repo: Owner/repo string (e.g. "YourMoveLabs/agent-fishbowl")
        since: ISO date string (e.g. "2026-02-13") — issues closed on or after
    """
    client = get_shared_client()
    headers = github_headers()
    url = f"https://api.github.com/repos/{repo}/issues"
    closed: list[dict[str, Any]] = []
    page = 1

    if "T" not in since:
        since_dt = datetime.fromisoformat(since + "T00:00:00+00:00")
    else:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))

    while True:
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": "100",
            "since": since_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page": str(page),
        }
        try:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "Issues API returned %d (page %d)", resp.status_code, page
                )
                break
            items = resp.json()
            if not items:
                break

            for issue in items:
                # Skip pull requests (Issues API includes them)
                if issue.get("pull_request"):
                    continue
                closed_at = issue.get("closed_at")
                if not closed_at:
                    continue
                closed_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                if closed_dt >= since_dt:
                    closed.append(issue)

            if len(items) < 100:
                break
            page += 1
        except Exception:
            logger.exception("Issues API error (page %d)", page)
            break

    return closed


async def fetch_merged_prs(repo: str, since: str) -> list[dict[str, Any]]:
    """Fetch merged PRs since a date using the Pulls REST API.

    Uses /repos/{owner}/{repo}/pulls?state=closed instead of the Search API
    is:merged qualifier, which can return 0 results due to GitHub indexing issues.

    Args:
        repo: Owner/repo string (e.g. "YourMoveLabs/agent-fishbowl")
        since: ISO date string (e.g. "2026-02-13") — PRs merged on or after
    """
    client = get_shared_client()
    headers = github_headers()
    url = f"https://api.github.com/repos/{repo}/pulls"
    merged: list[dict[str, Any]] = []
    page = 1

    if "T" not in since:
        since_dt = datetime.fromisoformat(since + "T00:00:00+00:00")
    else:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))

    while True:
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": "100",
            "page": str(page),
        }
        try:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "Pulls API returned %d (page %d)", resp.status_code, page
                )
                break
            items = resp.json()
            if not items:
                break

            stop_paging = False
            for pr in items:
                merged_at = pr.get("merged_at")
                if not merged_at:
                    continue
                pr_merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if pr_merged_dt >= since_dt:
                    merged.append(pr)

            # Stop if the oldest item on this page was updated before our window
            oldest_updated = items[-1].get("updated_at", "")
            if oldest_updated:
                oldest_dt = datetime.fromisoformat(
                    oldest_updated.replace("Z", "+00:00")
                )
                if oldest_dt < since_dt:
                    stop_paging = True

            if stop_paging or len(items) < 100:
                break
            page += 1
        except Exception:
            logger.exception("Pulls API error (page %d)", page)
            break

    return merged
