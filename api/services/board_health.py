"""Board health service — GitHub Project board metrics.

Fetches project board items via the GitHub GraphQL API, computes
work distribution (Todo/In Progress/Done) and board hygiene metrics,
and caches the results with a shared TTL cache.
"""

import logging
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.http_client import get_shared_client, github_api_get, github_headers

logger = logging.getLogger(__name__)

_cache = TTLCache(ttl=600, max_size=5)

# GraphQL query to fetch project items with status field
_PROJECT_ITEMS_QUERY = """
query($owner: String!, $number: Int!, $cursor: String) {
  organization(login: $owner) {
    projectV2(number: $number) {
      items(first: 100, after: $cursor) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          type
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          content {
            ... on Issue {
              state
              number
            }
            ... on DraftIssue {
              title
            }
          }
        }
      }
    }
  }
}
"""


async def _fetch_project_items(
    owner: str, project_number: int
) -> list[dict[str, Any]] | None:
    """Fetch all project board items via GitHub GraphQL API.

    Returns None on API error so callers can fall back to stale cache.
    """
    client = get_shared_client()
    headers = github_headers()
    headers["Content-Type"] = "application/json"
    url = "https://api.github.com/graphql"

    all_items: list[dict[str, Any]] = []
    cursor = None

    while True:
        variables: dict[str, Any] = {"owner": owner, "number": project_number}
        if cursor:
            variables["cursor"] = cursor

        try:
            resp = await client.post(
                url,
                headers=headers,
                json={"query": _PROJECT_ITEMS_QUERY, "variables": variables},
            )
            if resp.status_code != 200:
                logger.warning(
                    "GraphQL API returned %d for project items",
                    resp.status_code,
                )
                return None if not all_items else all_items

            data = resp.json()
            errors = data.get("errors")
            if errors:
                logger.warning("GraphQL errors: %s", errors)
                return None if not all_items else all_items

            project = data.get("data", {}).get("organization", {}).get("projectV2")
            if not project:
                logger.warning("Project not found: %s/%d", owner, project_number)
                return None

            items_data = project.get("items", {})
            nodes = items_data.get("nodes", [])
            all_items.extend(nodes)

            page_info = items_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        except Exception:
            logger.exception("GraphQL error fetching project items")
            return None if not all_items else all_items

    return all_items


async def _fetch_open_issue_numbers(repo: str) -> set[int] | None:
    """Fetch all open issue numbers via the GitHub REST API.

    Pages through results to collect every open issue number.
    Returns None on API error so callers can skip the untracked check.
    """
    url = f"https://api.github.com/repos/{repo}/issues"
    all_numbers: set[int] = set()
    page = 1

    while True:
        params = {
            "state": "open",
            "per_page": "100",
            "page": str(page),
        }
        data = await github_api_get(url, params, context=f"open issues page {page}")
        if data is None:
            return None if not all_numbers else all_numbers

        items: list[dict[str, Any]] = data if isinstance(data, list) else []
        if not items:
            break

        for item in items:
            # The issues endpoint also returns PRs; filter them out
            if "pull_request" not in item:
                all_numbers.add(item["number"])

        if len(items) < 100:
            break
        page += 1

    return all_numbers


def _compute_board_health(
    items: list[dict[str, Any]],
    untracked_count: int | None = None,
) -> dict[str, Any]:
    """Compute board health metrics from project items."""
    status_counts: dict[str, int] = {}
    total = len(items)
    draft_count = 0

    for item in items:
        # Get status field value
        field_value = item.get("fieldValueByName")
        status = field_value.get("name") if field_value else None
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1

        # Check if item is a draft issue (not converted to a real issue)
        if item.get("type") == "DRAFT_ISSUE":
            draft_count += 1

    result: dict[str, Any] = {
        "total_items": total,
        "by_status": status_counts,
        "draft_items": draft_count,
        "untracked_issues": untracked_count if untracked_count is not None else 0,
    }
    return result


def _empty_result() -> dict[str, Any]:
    return {"total_items": 0, "by_status": {}, "draft_items": 0, "untracked_issues": 0}


async def get_board_health() -> dict[str, Any]:
    """Get board health metrics, using cache when available."""
    cached = _cache.get("board_health")
    if cached is not None:
        return cached

    settings = get_settings()
    repo = settings.github_repo
    if not repo:
        return _empty_result()

    owner = repo.split("/")[0]
    project_number = 1  # From CLAUDE.md: PROJECT_NUMBER: 1

    items = await _fetch_project_items(owner, project_number)

    if items is None:
        stale = _cache.get_stale("board_health")
        if stale is not None:
            return stale
        return _empty_result()

    # Compute untracked issues: open issues not present on the board
    untracked_count = 0
    open_issue_numbers = await _fetch_open_issue_numbers(repo)
    if open_issue_numbers is not None:
        board_issue_numbers: set[int] = set()
        for item in items:
            content = item.get("content")
            if content and "number" in content:
                board_issue_numbers.add(content["number"])
        untracked_count = len(open_issue_numbers - board_issue_numbers)

    result = _compute_board_health(items, untracked_count)
    _cache.set("board_health", result)
    return result
