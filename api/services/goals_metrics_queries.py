"""GitHub API query helpers for goals metrics.

Generic paginated search/count wrappers used by the metrics pipeline.
"""

import logging
from typing import Any

from api.services.http_client import get_shared_client, github_api_get, github_headers

logger = logging.getLogger(__name__)


async def _search_count(query: str) -> int | None:
    """Run a GitHub search and return the total_count.

    Returns None on API errors so callers can distinguish "zero results"
    from "request failed".
    """
    data = await github_api_get(
        "https://api.github.com/search/issues",
        params={"q": query, "per_page": "1"},
        context=f"search count: {query}",
    )
    if data is None:
        return None
    return data.get("total_count", 0) if isinstance(data, dict) else 0


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

    Uses raw httpx instead of github_api_get because it needs the Link
    response header to extract the total page count without fetching all
    commits. github_api_get only returns parsed JSON bodies.
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
