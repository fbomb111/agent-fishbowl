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


async def paginated_github_search(
    url: str,
    params: dict[str, str],
    *,
    items_key: str = "items",
    total_key: str = "total_count",
    per_page: int = 100,
    context: str = "",
) -> list[dict[str, Any]] | None:
    """Paginate through a GitHub Search API endpoint, returning all items.

    Returns None on first-page failure so callers can fall back to stale cache.
    Partial results from later-page failures are returned as-is.

    Args:
        url: The API endpoint URL.
        params: Base query parameters (pagination params are added automatically).
        items_key: Key in the response JSON containing the result list.
        total_key: Key in the response JSON containing the total result count.
        per_page: Number of results per page (max 100 for Search API).
        context: Description for log messages.
    """
    client = get_shared_client()
    headers = github_headers()
    all_items: list[dict[str, Any]] = []
    page = 1

    while True:
        page_params = {**params, "per_page": str(per_page), "page": str(page)}
        try:
            resp = await client.get(url, headers=headers, params=page_params)
            if resp.status_code != 200:
                logger.warning(
                    "GitHub API %d for %s (page %d)%s",
                    resp.status_code,
                    url,
                    page,
                    f" ({context})" if context else "",
                )
                return None if not all_items else all_items
            data = resp.json()
            items = data.get(items_key, [])
            all_items.extend(items)
            total_count = data.get(total_key, 0)
            if len(all_items) >= total_count or len(items) < per_page:
                break
            page += 1
        except Exception:
            logger.exception(
                "GitHub API error for %s (page %d)%s",
                url,
                page,
                f" ({context})" if context else "",
            )
            return None if not all_items else all_items

    return all_items


async def fetch_closed_issues(repo: str, since: str) -> list[dict[str, Any]] | None:
    """Fetch issues closed since a date using the Issues REST API.

    Uses /repos/{owner}/{repo}/issues?state=closed instead of the Search API
    is:closed qualifier, which can return 0 due to indexing (#354, #338).

    Filters out pull requests (GitHub's Issues API includes PRs) by checking
    that pull_request key is absent.  Filters by closed_at timestamp to get
    accurate date filtering.

    Returns None if the first page fails (callers should fall back to stale
    cache).  Partial results from later-page failures are returned as-is.

    Args:
        repo: Owner/repo string (e.g. "YourMoveLabs/agent-fishbowl")
        since: ISO date string (e.g. "2026-02-13") — issues closed on or after
    """
    client = get_shared_client()
    headers = github_headers()
    url = f"https://api.github.com/repos/{repo}/issues"
    closed_issues: list[dict[str, Any]] = []
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
                    "Issues API returned %d (page %d)", resp.status_code, page
                )
                return None if page == 1 else closed_issues
            items = resp.json()
            if not items:
                break

            for issue in items:
                # Filter out PRs (Issues API includes them)
                if "pull_request" in issue:
                    continue

                closed_at = issue.get("closed_at")
                if not closed_at:
                    continue
                issue_closed_dt = datetime.fromisoformat(
                    closed_at.replace("Z", "+00:00")
                )
                if issue_closed_dt >= since_dt:
                    closed_issues.append(issue)

            # Stop if the oldest item on this page was updated before our window
            oldest_updated = items[-1].get("updated_at", "")
            if oldest_updated:
                oldest_dt = datetime.fromisoformat(
                    oldest_updated.replace("Z", "+00:00")
                )
                if oldest_dt < since_dt:
                    break

            if len(items) < 100:
                break
            page += 1
        except Exception:
            logger.exception("Issues API error (page %d)", page)
            return None if page == 1 else closed_issues

    return closed_issues


async def fetch_merged_prs(repo: str, since: str) -> list[dict[str, Any]] | None:
    """Fetch merged PRs since a date using the Pulls REST API.

    Uses /repos/{owner}/{repo}/pulls?state=closed instead of the Search API
    is:merged qualifier, which can return 0 results due to GitHub indexing issues.

    Returns None if the first page fails (callers should fall back to stale
    cache).  Partial results from later-page failures are returned as-is.

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
                return None if page == 1 else merged
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
            return None if page == 1 else merged

    return merged
