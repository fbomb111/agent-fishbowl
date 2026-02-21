"""GitHub activity feed — thread grouping and PR title enrichment.

Groups flat activity events into threads by issue/PR subject, and backfills
missing PR titles from the GitHub API.
"""

import asyncio
import logging
import re
from typing import Any

from api.config import get_settings
from api.services.http_client import github_api_get

logger = logging.getLogger(__name__)


def group_events_into_threads(
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


async def backfill_pr_titles(events: list[dict[str, Any]]) -> None:
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
