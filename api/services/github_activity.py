"""GitHub activity feed — fetching, threading, and caching of repo events.

Fetches repository events from the GitHub API, parses them into ActivityEvent
dicts, groups them into threads by issue/PR, and caches the results.
"""

import asyncio
import re
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import parse_events
from api.services.http_client import github_api_get

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
    for thread in threads.values():
        thread["events"].sort(key=lambda e: e["timestamp"])
        # Update latest_timestamp to actual latest event after sort
        if thread["events"]:
            thread["latest_timestamp"] = thread["events"][-1]["timestamp"]

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


async def _backfill_pr_titles(events: list[dict[str, Any]]) -> None:
    """Fetch titles for PR events where the Events API returned null.

    The GitHub Events API often returns null for pull_request.title.
    This fetches the actual titles and patches both subject_title and
    description on affected events.
    """
    settings = get_settings()
    repo = settings.github_repo

    # Collect PR numbers that need titles
    missing: set[int] = set()
    for evt in events:
        if (
            evt.get("subject_type") == "pr"
            and evt.get("subject_number") is not None
            and not evt.get("subject_title")
        ):
            missing.add(evt["subject_number"])

    if not missing:
        return

    # Fetch titles concurrently
    async def fetch_title(pr_number: int) -> tuple[int, str]:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        data = await github_api_get(url, context=f"PR #{pr_number} title")
        if data and isinstance(data, dict):
            return pr_number, data.get("title") or ""
        return pr_number, ""

    results = await asyncio.gather(*[fetch_title(n) for n in missing])
    titles = {num: title for num, title in results if title}

    if not titles:
        return

    # Patch events with fetched titles
    # Pattern: matches "... PR #123: " at the end of a description (missing title)
    for evt in events:
        num = evt.get("subject_number")
        if (
            evt.get("subject_type") == "pr"
            and num in titles
            and not evt.get("subject_title")
        ):
            evt["subject_title"] = titles[num]
            # Fix descriptions like "Merged PR #123: " → "Merged PR #123: actual title"
            desc = evt.get("description", "")
            evt["description"] = re.sub(
                rf"(PR #{num}: )$", rf"\g<1>{titles[num]}", desc
            )


async def _fetch_repo_events(
    repo: str, per_page: int, page: int
) -> list[dict[str, Any]]:
    """Fetch raw events from a single repo."""
    url = f"https://api.github.com/repos/{repo}/events"
    params = {"per_page": str(per_page), "page": str(page)}
    result = await github_api_get(url, params, context=repo)
    return result if result is not None else []


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
    await _backfill_pr_titles(events)

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
    await _backfill_pr_titles(events)
    threads = _group_events_into_threads(events)

    if threads:
        _cache.set(cache_key, threads)
        return threads

    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []
