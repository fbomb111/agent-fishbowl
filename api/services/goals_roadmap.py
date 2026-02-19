"""Roadmap service — fetches roadmap snapshot from GitHub Project via `gh` CLI.

Provides active items and status counts, cached with a shared TTL cache.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache

logger = logging.getLogger(__name__)


@dataclass
class RoadmapItem:
    title: str
    body: str = ""
    priority: str = ""
    goal: str = ""
    phase: str = ""
    status: str = ""


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
        proc = await asyncio.create_subprocess_exec(
            "gh",
            "project",
            "item-list",
            "1",
            "--owner",
            owner,
            "--format",
            "json",
            "--limit",
            "50",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

        if proc.returncode != 0:
            logger.error(
                "gh project item-list failed (rc=%d): %s",
                proc.returncode,
                stderr.decode().strip(),
            )
            stale = cache.get("roadmap")
            return stale if stale is not None else empty

        raw = json.loads(stdout.decode())
        active_items: list[dict[str, Any]] = []
        counts: dict[str, int] = {"proposed": 0, "active": 0, "done": 0, "deferred": 0}

        for item in raw.get("items", []):
            status = item.get("roadmap Status", item.get("status", "")).lower()

            # Count all items by status
            if status in counts:
                counts[status] += 1

            # Only include Active items in the detail list
            if status == "active":
                active_items.append(
                    {
                        "title": item.get("title", ""),
                        "priority": item.get("priority", ""),
                        "goal": item.get("goal", ""),
                        "phase": item.get("phase", ""),
                    }
                )

        result: dict[str, Any] = {"active": active_items, "counts": counts}
        cache.set("roadmap", result)
        return result

    except (asyncio.TimeoutError, FileNotFoundError, json.JSONDecodeError):
        logger.exception("roadmap fetch failed")
        stale = cache.get("roadmap")
        return stale if stale is not None else empty
