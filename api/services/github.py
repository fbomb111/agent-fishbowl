"""GitHub API client for the activity feed.

Fetches repository events (issues, PRs, commits, reviews) and maps them
to ActivityEvent dicts for the frontend. Results are cached with a 5-min TTL.
"""

import time
from typing import Any

import httpx

from api.config import get_settings

# Simple in-memory cache: (events, timestamp)
_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}
CACHE_TTL = 300  # 5 minutes

# Map GitHub login to agent role for display
ACTOR_MAP: dict[str, str] = {
    "fishbowl-engineer[bot]": "engineer",
    "fishbowl-reviewer[bot]": "reviewer",
    "fishbowl-pm[bot]": "pm",
}


def _map_actor(login: str) -> str:
    """Map a GitHub login to a friendly agent name."""
    return ACTOR_MAP.get(login, login)


def _parse_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert GitHub API events into ActivityEvent dicts."""
    parsed: list[dict[str, Any]] = []

    for event in raw_events:
        event_type = event.get("type", "")
        actor = _map_actor(event.get("actor", {}).get("login", "unknown"))
        payload = event.get("payload", {})
        created_at = event.get("created_at", "")

        if event_type == "IssuesEvent":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            if action == "opened":
                parsed.append({
                    "id": event["id"],
                    "type": "issue_created",
                    "actor": actor,
                    "description": f"Opened issue: {issue.get('title', '')}",
                    "timestamp": created_at,
                    "url": issue.get("html_url"),
                })
            elif action == "closed":
                parsed.append({
                    "id": event["id"],
                    "type": "issue_closed",
                    "actor": actor,
                    "description": f"Closed issue: {issue.get('title', '')}",
                    "timestamp": created_at,
                    "url": issue.get("html_url"),
                })

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            title = pr.get("title", "")
            url = pr.get("html_url")
            if action == "opened":
                parsed.append({
                    "id": event["id"],
                    "type": "pr_opened",
                    "actor": actor,
                    "description": f"Opened PR: {title}",
                    "timestamp": created_at,
                    "url": url,
                })
            elif action == "closed" and pr.get("merged"):
                parsed.append({
                    "id": event["id"],
                    "type": "pr_merged",
                    "actor": actor,
                    "description": f"Merged PR: {title}",
                    "timestamp": created_at,
                    "url": url,
                })

        elif event_type == "PullRequestReviewEvent":
            pr = payload.get("pull_request", {})
            review = payload.get("review", {})
            state = review.get("state", "")
            title = pr.get("title", "")
            if state == "approved":
                desc = f"Approved PR: {title}"
            elif state == "changes_requested":
                desc = f"Requested changes on PR: {title}"
            else:
                desc = f"Reviewed PR: {title}"
            parsed.append({
                "id": event["id"],
                "type": "pr_reviewed",
                "actor": actor,
                "description": desc,
                "timestamp": created_at,
                "url": review.get("html_url") or pr.get("html_url"),
            })

        elif event_type == "PushEvent":
            commits = payload.get("commits", [])
            if commits:
                # Show the most recent commit message
                msg = commits[-1].get("message", "").split("\n")[0]
                count = len(commits)
                suffix = f" (+{count - 1} more)" if count > 1 else ""
                parsed.append({
                    "id": event["id"],
                    "type": "commit",
                    "actor": actor,
                    "description": f"{msg}{suffix}",
                    "timestamp": created_at,
                    "url": f"https://github.com/{get_settings().github_repo}/commit/{commits[-1].get('sha', '')}",
                })

        elif event_type == "IssueCommentEvent":
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            body = comment.get("body", "")[:120]
            parsed.append({
                "id": event["id"],
                "type": "comment",
                "actor": actor,
                "description": f"Commented on #{issue.get('number', '?')}: {body}",
                "timestamp": created_at,
                "url": comment.get("html_url"),
            })

    return parsed


async def get_activity_events(page: int = 1, per_page: int = 30) -> list[dict[str, Any]]:
    """Fetch activity events from GitHub with caching."""
    settings = get_settings()
    cache_key = f"{page}:{per_page}"

    # Check cache
    if cache_key in _cache:
        events, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return events

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    url = f"https://api.github.com/repos/{settings.github_repo}/events"
    params = {"per_page": str(per_page), "page": str(page)}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            raw = resp.json()
            events = _parse_events(raw)
            _cache[cache_key] = (events, time.time())
            return events
        # On error, return cached data if available (stale), else empty
        if cache_key in _cache:
            return _cache[cache_key][0]
        return []

