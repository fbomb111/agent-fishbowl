"""GitHub API client for the activity feed and agent status.

Fetches repository events (issues, PRs, commits, reviews) and maps them
to ActivityEvent dicts for the frontend. Also fetches workflow run status
to show which agents are currently active. Results are cached with TTLs.
"""

import asyncio
import logging
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.http_client import get_shared_client, github_headers
from api.services.usage_storage import get_run_usage

logger = logging.getLogger(__name__)

# TTL cache for activity events (5 min)
_cache = TTLCache(ttl=300, max_size=20)

# TTL cache for agent status (60s — the "live" signal)
_status_cache = TTLCache(ttl=60, max_size=5)

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
    "fishbowl-writer[bot]": "writer",
    "github-actions[bot]": "github-actions",
    "YourMoveLabs": "org",
}

# Event types that represent interactive human actions (issues, comments, reviews)
_HUMAN_EVENT_TYPES = {
    "IssuesEvent",
    "IssueCommentEvent",
    "PullRequestEvent",
    "PullRequestReviewEvent",
    "PullRequestReviewCommentEvent",
}


def _map_actor(login: str, event_type: str = "") -> str:
    """Map a GitHub login to a friendly agent name.

    For fbomb111 (Frankie), we split attribution based on event type:
    interactive actions (issues, comments, reviews) → "human",
    process actions (releases, pushes, branch ops) → "org".
    """
    if login == "fbomb111":
        return "human" if event_type in _HUMAN_EVENT_TYPES else "org"
    return ACTOR_MAP.get(login, login)


def _make_event(
    event: dict[str, Any],
    *,
    event_type: str,
    actor: str,
    description: str,
    url: str | None = None,
    subject_type: str | None = None,
    subject_number: int | None = None,
    subject_title: str | None = None,
    comment_body: str | None = None,
    comment_url: str | None = None,
) -> dict[str, Any]:
    """Build a parsed event dict with optional subject fields."""
    entry: dict[str, Any] = {
        "id": event["id"],
        "type": event_type,
        "actor": actor,
        "description": description,
        "timestamp": event.get("created_at", ""),
        "url": url,
    }
    if subject_type:
        entry["subject_type"] = subject_type
    if subject_number is not None:
        entry["subject_number"] = subject_number
    if subject_title:
        entry["subject_title"] = subject_title
    if comment_body:
        entry["comment_body"] = comment_body
    if comment_url:
        entry["comment_url"] = comment_url
    return entry


# Labels worth surfacing in the feed (others are noise)
_INTERESTING_LABELS = {
    "status/in-progress",
    "review/approved",
    "review/changes-requested",
    "pm/misaligned",
}
_INTERESTING_LABEL_PREFIXES = ("priority/", "source/")


def _is_interesting_label(label_name: str) -> bool:
    if label_name in _INTERESTING_LABELS:
        return True
    return any(label_name.startswith(p) for p in _INTERESTING_LABEL_PREFIXES)


def _parse_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert GitHub API events into ActivityEvent dicts."""
    parsed: list[dict[str, Any]] = []

    for event in raw_events:
        event_type = event.get("type", "")
        actor = _map_actor(event.get("actor", {}).get("login", "unknown"), event_type)
        payload = event.get("payload", {})

        if event_type == "IssuesEvent":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            number = issue.get("number")
            title = issue.get("title", "")
            subject = dict(
                subject_type="issue",
                subject_number=number,
                subject_title=title,
            )

            if action == "opened":
                parsed.append(
                    _make_event(
                        event,
                        event_type="issue_created",
                        actor=actor,
                        description=f"Opened issue #{number}: {title}",
                        url=issue.get("html_url"),
                        **subject,
                    )
                )
            elif action == "closed":
                parsed.append(
                    _make_event(
                        event,
                        event_type="issue_closed",
                        actor=actor,
                        description=f"Closed issue #{number}: {title}",
                        url=issue.get("html_url"),
                        **subject,
                    )
                )
            elif action == "labeled":
                label_name = payload.get("label", {}).get("name", "")
                if _is_interesting_label(label_name):
                    parsed.append(
                        _make_event(
                            event,
                            event_type="issue_labeled",
                            actor=actor,
                            description=f"Labeled #{number} with {label_name}",
                            url=issue.get("html_url"),
                            **subject,
                        )
                    )

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            title = pr.get("title", "")
            number = pr.get("number")
            url = pr.get("html_url")
            subject = dict(
                subject_type="pr",
                subject_number=number,
                subject_title=title,
            )

            if action == "opened":
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_opened",
                        actor=actor,
                        description=f"Opened PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )
            elif action == "closed" and pr.get("merged"):
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_merged",
                        actor=actor,
                        description=f"Merged PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )
            elif action == "closed" and not pr.get("merged"):
                parsed.append(
                    _make_event(
                        event,
                        event_type="pr_closed",
                        actor=actor,
                        description=f"Closed PR #{number}: {title}",
                        url=url,
                        **subject,
                    )
                )

        elif event_type == "PullRequestReviewEvent":
            pr = payload.get("pull_request", {})
            review = payload.get("review", {})
            state = review.get("state", "")
            title = pr.get("title", "")
            number = pr.get("number")
            subject = dict(
                subject_type="pr",
                subject_number=number,
                subject_title=title,
            )

            if state == "approved":
                desc = f"Approved PR #{number}: {title}"
            elif state == "changes_requested":
                desc = f"Requested changes on PR #{number}: {title}"
            else:
                desc = f"Reviewed PR #{number}: {title}"

            # Include review body text (up to 500 chars)
            review_body_raw = review.get("body") or ""
            review_body = review_body_raw[:500]
            review_url = review.get("html_url") or pr.get("html_url")

            parsed.append(
                _make_event(
                    event,
                    event_type="pr_reviewed",
                    actor=actor,
                    description=desc,
                    url=review_url,
                    comment_body=review_body if review_body else None,
                    comment_url=review_url
                    if review_body_raw and len(review_body_raw) > 500
                    else None,
                    **subject,
                )
            )

        elif event_type == "PushEvent":
            commits = payload.get("commits", [])
            if commits:
                msg = commits[-1].get("message", "").split("\n")[0]
                count = len(commits)
                suffix = f" (+{count - 1} more)" if count > 1 else ""
                parsed.append(
                    _make_event(
                        event,
                        event_type="commit",
                        actor=actor,
                        description=f"{msg}{suffix}",
                        url=f"https://github.com/{get_settings().github_repo}/commit/{commits[-1].get('sha', '')}",
                    )
                )

        elif event_type == "IssueCommentEvent":
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            number = issue.get("number")
            title = issue.get("title", "")
            body_raw = comment.get("body", "")
            body = body_raw[:300]
            is_pr = "pull_request" in issue
            html_url = comment.get("html_url")
            parsed.append(
                _make_event(
                    event,
                    event_type="comment",
                    actor=actor,
                    description=f"Commented on #{number}: {title}",
                    url=html_url,
                    subject_type="pr" if is_pr else "issue",
                    subject_number=number,
                    subject_title=title,
                    comment_body=body if body else None,
                    comment_url=html_url if len(body_raw) > 300 else None,
                )
            )

        elif event_type == "ReleaseEvent":
            action = payload.get("action", "")
            release = payload.get("release", {})
            tag = release.get("tag_name", "")
            name = release.get("name", tag)
            if action == "published":
                parsed.append(
                    _make_event(
                        event,
                        event_type="release",
                        actor=actor,
                        description=f"Published release: {name}",
                        url=release.get("html_url"),
                    )
                )

    return parsed


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
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
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
    events = _parse_events(all_raw)

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
    events = _parse_events(all_raw)
    threads = _group_events_into_threads(events)

    if threads:
        _cache.set(cache_key, threads)
        return threads

    stale = _cache.get(cache_key)
    if stale is not None:
        return stale
    return []


# ---------------------------------------------------------------------------
# Agent status (workflow runs)
# ---------------------------------------------------------------------------

# Map workflow filenames to agent roles
WORKFLOW_AGENT_MAP: dict[str, list[str]] = {
    "agent-engineer.yml": ["engineer"],
    "agent-reviewer.yml": ["reviewer"],
    "agent-po.yml": ["po"],
    "agent-triage.yml": ["triage"],
    "agent-sre.yml": ["sre"],
    "agent-scans.yml": ["tech-lead", "ux"],
    "agent-strategic.yml": ["pm"],
}


async def get_agent_status() -> list[dict[str, Any]]:
    """Fetch the current status of each agent from GitHub Actions workflow runs.

    Returns a list of agent status dicts with role, status, timing, etc.
    Cached with 60s TTL.
    """
    cache_key = "agent_status"
    cached = _status_cache.get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()
    client = get_shared_client()
    headers = github_headers()

    url = f"https://api.github.com/repos/{settings.github_repo}/actions/runs"
    params = {"per_page": "50"}

    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            logger.warning("Failed to fetch workflow runs: %d", resp.status_code)
            stale = _status_cache.get(cache_key)
            return stale if stale is not None else []
        runs = resp.json().get("workflow_runs", [])
    except Exception:
        logger.exception("Error fetching workflow runs")
        stale = _status_cache.get(cache_key)
        return stale if stale is not None else []

    # Build a map of agent role -> most recent run
    agent_runs: dict[str, dict[str, Any]] = {}

    for run in runs:
        # Extract workflow filename from path (e.g. ".github/workflows/agent-engineer.yml")
        workflow_path = run.get("path", "")
        workflow_file = (
            workflow_path.split("/")[-1] if "/" in workflow_path else workflow_path
        )
        roles = WORKFLOW_AGENT_MAP.get(workflow_file, [])

        for role in roles:
            if role not in agent_runs:
                agent_runs[role] = run

    # Fetch usage data for completed runs (from blob storage, permanently cached)
    completed_run_ids: set[int] = set()
    for run in agent_runs.values():
        if run.get("status") == "completed" and run.get("id"):
            completed_run_ids.add(run["id"])

    # Fetch all uncached usage in parallel
    if completed_run_ids:
        await asyncio.gather(
            *(get_run_usage(rid) for rid in completed_run_ids),
            return_exceptions=True,
        )

    # Convert to response format
    result: list[dict[str, Any]] = []
    all_roles = ["po", "engineer", "reviewer", "triage", "sre", "pm", "tech-lead", "ux"]

    for role in all_roles:
        run = agent_runs.get(role)
        if run is None:
            result.append({"role": role, "status": "idle"})
            continue

        run_status = run.get("status", "")  # queued, in_progress, completed
        conclusion = run.get("conclusion")  # success, failure, cancelled, null

        if run_status in ("queued", "in_progress"):
            status = "active"
        elif conclusion == "failure":
            status = "failed"
        else:
            status = "idle"

        entry: dict[str, Any] = {
            "role": role,
            "status": status,
        }

        if run_status in ("queued", "in_progress"):
            entry["started_at"] = run.get("run_started_at")
            entry["trigger"] = run.get("event", "")

        if run_status == "completed":
            entry["last_completed_at"] = run.get("updated_at")
            entry["last_conclusion"] = conclusion

        # For idle agents, always include when they last ran
        if status == "idle" and run.get("updated_at"):
            entry["last_completed_at"] = run.get("updated_at")
            entry["last_conclusion"] = conclusion

        # Enrich with usage data from the most recent completed run
        if run.get("status") == "completed" and run.get("id"):
            usage_data = await get_run_usage(run["id"])
            if usage_data:
                agents_list = usage_data.get("agents", [])
                role_usage = next(
                    (a for a in agents_list if a.get("role") == role), None
                )
                if role_usage:
                    raw_usage = role_usage.get("usage") or {}
                    entry["usage"] = {
                        "cost_usd": role_usage.get("total_cost_usd"),
                        "num_turns": role_usage.get("num_turns"),
                        "duration_s": round(
                            (role_usage.get("duration_api_ms") or 0) / 1000
                        ),
                        "input_tokens": raw_usage.get("input_tokens"),
                        "output_tokens": raw_usage.get("output_tokens"),
                        "cache_creation_input_tokens": raw_usage.get(
                            "cache_creation_input_tokens"
                        ),
                        "cache_read_input_tokens": raw_usage.get(
                            "cache_read_input_tokens"
                        ),
                    }

        result.append(entry)

    _status_cache.set(cache_key, result)
    return result
