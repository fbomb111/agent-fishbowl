"""GitHub activity feed — fetching, threading, and caching of repo events.

Fetches repository events from the GitHub API, parses them into ActivityEvent
dicts, groups them into threads by issue/PR, and caches the results.
"""

import asyncio
import logging
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import parse_events
from api.services.http_client import get_shared_client, github_headers

logger = logging.getLogger(__name__)

# TTL cache for activity events (5 min)
_cache = TTLCache(ttl=300, max_size=20)


def _group_events_into_threads(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group events by their subject (issue/PR number) into threads.

    Returns a list of thread objects, each containing a subject and its events,
    plus any standalone events interleaved by timestamp.
    """
    threads: dict[str, dict[str, Any]] = {}  # key = "issue:42" or "pr:15"
    standalone: list[dict[str, Any]] = []

    for evt in events:
        subj_type = evt.get("subject_type")
        subj_num = evt.get("subject_number")

        if subj_type and subj_num is not None:
            key = f"{subj_type}:{subj_num}"
            if key not in threads:
                threads[key] = {
                    "type": "thread",
                    "subject_type": subj_type,
                    "subject_number": subj_num,
                    "subject_title": evt.get("subject_title", ""),
                    "events": [],
                    "latest_timestamp": evt["timestamp"],
                }
            thread = threads[key]
            thread["events"].append(evt)
            # Keep the title from the earliest event that has one
            if not thread["subject_title"] and evt.get("subject_title"):
                thread["subject_title"] = evt["subject_title"]
        else:
            standalone.append({"type": "standalone", "event": evt})

    # Sort events within each thread chronologically (oldest first)
    # and deduplicate label events (GitHub fires multiple events for same label)
    for thread in threads.values():
        thread["events"].sort(key=lambda e: e["timestamp"])
        seen_labels: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for evt in thread["events"]:
            if evt["type"] == "issue_labeled":
                if evt["description"] in seen_labels:
                    continue
                seen_labels.add(evt["description"])
            deduped.append(evt)
        thread["events"] = deduped

    # Merge threads and standalone events, sorted by most recent activity
    result: list[dict[str, Any]] = []
    for thread in threads.values():
        result.append(thread)
    for item in standalone:
        result.append(item)

    # Sort by latest timestamp descending
    def sort_key(item: dict[str, Any]) -> str:
        if item["type"] == "thread":
            return item["latest_timestamp"]
        return item["event"]["timestamp"]

    result.sort(key=sort_key, reverse=True)
    return result


async def _fetch_repo_events(
    repo: str, per_page: int, page: int
) -> list[dict[str, Any]]:
    """Fetch raw events from a single repo."""
    headers = github_headers()
    url = f"https://api.github.com/repos/{repo}/events"
    params = {"per_page": str(per_page), "page": str(page)}
    client = get_shared_client()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to fetch events for %s: %d", repo, resp.status_code)
        return []
    except Exception:
        logger.exception("Error fetching events for %s", repo)
        return []


async def _fetch_all_events(per_page: int = 50) -> list[dict[str, Any]]:
    """Fetch raw events from all repos, merge and sort by timestamp."""
    settings = get_settings()
    repos = [settings.github_repo]
    if settings.harness_repo:
        repos.append(settings.harness_repo)

    raw_results = await asyncio.gather(
        *[_fetch_repo_events(repo, per_page, 1) for repo in repos]
    )

    all_raw: list[dict[str, Any]] = []
    for raw in raw_results:
        all_raw.extend(raw)
    all_raw.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return all_raw[:per_page]


async def get_activity_events(
    page: int = 1, per_page: int = 30
) -> list[dict[str, Any]]:
    """Fetch activity events from GitHub with caching.

    Fetches from both the project repo and harness repo, merges by timestamp.
    """
    cache_key = f"flat:{page}:{per_page}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    all_raw = await _fetch_all_events(per_page)
    events = parse_events(all_raw)

    if events:
        _cache.set(cache_key, events)
        return events

    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []


async def get_threaded_activity(
    per_page: int = 50,
) -> list[dict[str, Any]]:
    """Fetch activity events and group them into threads by issue/PR.

    Returns a list of thread objects and standalone events sorted by recency.
    """
    cache_key = f"threaded:{per_page}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    all_raw = await _fetch_all_events(per_page)
    events = parse_events(all_raw)
    threads = _group_events_into_threads(events)

    if threads:
        _cache.set(cache_key, threads)
        return threads

    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []
