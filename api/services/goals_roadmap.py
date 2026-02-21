"""Roadmap service — fetches roadmap snapshot from GitHub Project via GraphQL.

Provides active items and status counts, cached with a shared TTL cache.
Uses the GitHub GraphQL API directly instead of the `gh` CLI, so it works
with the API server's GITHUB_TOKEN (which may not be configured for `gh`).
"""

import logging
from dataclasses import dataclass
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.http_client import get_shared_client, github_headers

logger = logging.getLogger(__name__)

# GraphQL query to fetch ProjectV2 items with their field values.
_PROJECT_ITEMS_QUERY = """
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      items(first: 50) {
        nodes {
          content {
            ... on Issue { title }
            ... on PullRequest { title }
            ... on DraftIssue { title }
          }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
              }
              ... on ProjectV2ItemFieldTextValue {
                field { ... on ProjectV2Field { name } }
                text
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass
class RoadmapItem:
    title: str
    body: str = ""
    priority: str = ""
    goal: str = ""
    phase: str = ""
    status: str = ""


def _extract_field(field_values: list[dict[str, Any]], field_name: str) -> str:
    """Extract a named field value from a ProjectV2 item's fieldValues nodes."""
    for node in field_values:
        name = ""
        value = ""
        if "field" in node:
            field = node["field"]
            name = field.get("name", "")
        if "name" in node:
            value = node["name"]
        elif "text" in node:
            value = node["text"]
        if name.lower() == field_name.lower():
            return value
    return ""


async def get_roadmap_snapshot(cache: TTLCache) -> dict[str, Any]:
    """Fetch roadmap snapshot: active items + summary counts.

    Returns only what's actively being worked on, plus counts
    of how many items are in each status — a snapshot, not a mirror.
    """
    cached = cache.get("roadmap")
    if cached is not None:
        return cached

    empty: dict[str, Any] = {
        "active": [],
        "counts": {"proposed": 0, "active": 0, "done": 0, "deferred": 0},
    }

    settings = get_settings()
    owner = (
        settings.github_repo.split("/")[0] if settings.github_repo else "YourMoveLabs"
    )

    try:
        client = get_shared_client()
        headers = github_headers()
        resp = await client.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={
                "query": _PROJECT_ITEMS_QUERY,
                "variables": {"owner": owner, "number": 1},
            },
            timeout=15.0,
        )

        if resp.status_code != 200:
            logger.error("GraphQL roadmap request failed (HTTP %d)", resp.status_code)
            return empty

        data = resp.json()

        errors = data.get("errors")
        if errors:
            logger.error("GraphQL roadmap errors: %s", errors)
            return empty

        project = (
            data.get("data", {}).get("organization", {}).get("projectV2")
        )
        if project is None:
            logger.warning(
                "GraphQL returned no projectV2 data"
                " — token may lack read:project scope"
            )
            return empty

        items = project.get("items", {}).get("nodes", [])
        active_items: list[dict[str, Any]] = []
        counts: dict[str, int] = {
            "proposed": 0,
            "active": 0,
            "done": 0,
            "deferred": 0,
        }

        for item in items:
            content = item.get("content") or {}
            title = content.get("title", "")
            field_nodes = item.get("fieldValues", {}).get("nodes", [])

            status = _extract_field(field_nodes, "Roadmap Status").lower()

            if status in counts:
                counts[status] += 1

            if status == "active":
                active_items.append(
                    {
                        "title": title,
                        "priority": _extract_field(field_nodes, "Priority"),
                        "goal": _extract_field(field_nodes, "Goal"),
                        "phase": _extract_field(field_nodes, "Phase"),
                    }
                )

        result: dict[str, Any] = {"active": active_items, "counts": counts}
        cache.set("roadmap", result)
        return result

    except Exception:
        logger.exception("roadmap fetch failed")
        stale = cache.get_stale("roadmap")
        return stale if stale is not None else empty
