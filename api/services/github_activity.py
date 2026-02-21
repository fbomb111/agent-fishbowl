"""GitHub activity feed — orchestration and caching.

Thin aggregator that wires together fetching (github_activity_fetch) and
threading (github_activity_threading) with a TTL cache.  The public API
(get_activity_events, get_threaded_activity) is re-exported here so that
router imports remain unchanged.
"""

import asyncio
import logging
from typing import Any

from api.services.cache import TTLCache
from api.services.github_activity_fetch import (
    fetch_all_events,
    fetch_deploy_events,
    fetch_fallback_events,
)
from api.services.github_activity_threading import (
    backfill_pr_titles,
    group_events_into_threads,
)
from api.services.github_events import parse_events

logger = logging.getLogger(__name__)

# TTL cache for activity events (5 min)
_cache = TTLCache(ttl=300, max_size=20)


async def _get_events_with_fallback(per_page: int = 50) -> list[dict[str, Any]]:
    """Fetch activity events via Events API, falling back to Issues/PRs API.

    Also fetches deploy events from workflow runs and merges them in.
    """
    all_raw, deploy_events = await asyncio.gather(
        fetch_all_events(per_page),
        fetch_deploy_events(),
    )
    events = parse_events(all_raw)

    if not events:
        logger.info("Events API empty — using Issues/PRs API fallback")
        events = await fetch_fallback_events(per_page)

    # Merge deploy events into the feed
    events.extend(deploy_events)
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    await backfill_pr_titles(events)
    return events


async def get_activity_events(
    page: int = 1, per_page: int = 30
) -> list[dict[str, Any]]:
    """Fetch activity events from GitHub with caching.

    Fetches from both the project repo and harness repo, merges by timestamp.
    Falls back to Issues/PRs REST API when the Events API returns empty.
    """
    cache_key = f"flat:{page}:{per_page}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    events = await _get_events_with_fallback(per_page)

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
    Falls back to Issues/PRs REST API when the Events API returns empty.
    """
    cache_key = f"threaded:{per_page}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    events = await _get_events_with_fallback(per_page)
    threads = group_events_into_threads(events)

    if threads:
        _cache.set(cache_key, threads)
        return threads

    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []
