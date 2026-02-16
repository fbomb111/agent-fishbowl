"""GitHub API client for the activity feed.

Fetches repository events (issues, PRs, commits, reviews) and maps them
to ActivityEvent dicts for the frontend. Results are cached with a 5-min TTL.
"""

from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.http_client import get_shared_client, github_headers

# TTL cache for activity events
_cache = TTLCache(ttl=300, max_size=20)

# Map GitHub login to agent role for display
ACTOR_MAP: dict[str, str] = {
    "fishbowl-engineer[bot]": "engineer",
    "fishbowl-reviewer[bot]": "reviewer",
    "fishbowl-po[bot]": "po",
    "fishbowl-pm[bot]": "pm",
    "fishbowl-techlead[bot]": "tech-lead",
    "fishbowl-ux[bot]": "ux",
    "fishbowl-triage[bot]": "triage",
    "fishbowl-sre[bot]": "sre",
    "fbomb111": "human",
    "YourMoveLabs": "org",
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
            number = issue.get("number", "?")
            title = issue.get("title", "")
            if action == "opened":
                parsed.append(
                    {
                        "id": event["id"],
                        "type": "issue_created",
                        "actor": actor,
                        "description": f"Opened issue #{number}: {title}",
                        "timestamp": created_at,
                        "url": issue.get("html_url"),
                    }
                )
            elif action == "closed":
                parsed.append(
                    {
                        "id": event["id"],
                        "type": "issue_closed",
                        "actor": actor,
                        "description": f"Closed issue #{number}: {title}",
                        "timestamp": created_at,
                        "url": issue.get("html_url"),
                    }
                )

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            title = pr.get("title", "")
            number = pr.get("number", "?")
            url = pr.get("html_url")
            if action == "opened":
                parsed.append(
                    {
                        "id": event["id"],
                        "type": "pr_opened",
                        "actor": actor,
                        "description": f"Opened PR #{number}: {title}",
                        "timestamp": created_at,
                        "url": url,
                    }
                )
            elif action == "closed" and pr.get("merged"):
                parsed.append(
                    {
                        "id": event["id"],
                        "type": "pr_merged",
                        "actor": actor,
                        "description": f"Merged PR #{number}: {title}",
                        "timestamp": created_at,
                        "url": url,
                    }
                )

        elif event_type == "PullRequestReviewEvent":
            pr = payload.get("pull_request", {})
            review = payload.get("review", {})
            state = review.get("state", "")
            title = pr.get("title", "")
            number = pr.get("number", "?")
            if state == "approved":
                desc = f"Approved PR #{number}: {title}"
            elif state == "changes_requested":
                desc = f"Requested changes on PR #{number}: {title}"
            else:
                desc = f"Reviewed PR #{number}: {title}"
            parsed.append(
                {
                    "id": event["id"],
                    "type": "pr_reviewed",
                    "actor": actor,
                    "description": desc,
                    "timestamp": created_at,
                    "url": review.get("html_url") or pr.get("html_url"),
                }
            )

        elif event_type == "PushEvent":
            commits = payload.get("commits", [])
            if commits:
                # Show the most recent commit message
                msg = commits[-1].get("message", "").split("\n")[0]
                count = len(commits)
                suffix = f" (+{count - 1} more)" if count > 1 else ""
                parsed.append(
                    {
                        "id": event["id"],
                        "type": "commit",
                        "actor": actor,
                        "description": f"{msg}{suffix}",
                        "timestamp": created_at,
                        "url": f"https://github.com/{get_settings().github_repo}/commit/{commits[-1].get('sha', '')}",
                    }
                )

        elif event_type == "IssueCommentEvent":
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            body = comment.get("body", "")[:120]
            parsed.append(
                {
                    "id": event["id"],
                    "type": "comment",
                    "actor": actor,
                    "description": f"Commented on #{issue.get('number', '?')}: {body}",
                    "timestamp": created_at,
                    "url": comment.get("html_url"),
                }
            )

    return parsed


async def get_activity_events(
    page: int = 1, per_page: int = 30
) -> list[dict[str, Any]]:
    """Fetch activity events from GitHub with caching."""
    settings = get_settings()
    cache_key = f"{page}:{per_page}"

    # Check cache
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    headers = github_headers()

    url = f"https://api.github.com/repos/{settings.github_repo}/events"
    params = {"per_page": str(per_page), "page": str(page)}

    client = get_shared_client()
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        raw = resp.json()
        events = _parse_events(raw)
        _cache.set(cache_key, events)
        return events
    # On error, return cached data if available (stale), else empty
    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []
