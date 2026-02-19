"""Goals service — parses goals.md, fetches roadmap from GitHub Project, computes metrics.

Data sources:
- Goals: Parsed from config/goals.md (static, cached by file mtime)
- Roadmap: GitHub Project #1 via `gh` CLI (cached 5 min)
- Metrics: GitHub API issues/PRs (cached 5 min)
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, TypedDict

import httpx

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.github_events import ACTOR_MAP
from api.services.http_client import get_shared_client, github_headers

# Shared TTL cache for all goals-related data
_cache = TTLCache(ttl=300, max_size=10)

# File-based cache for goals.md (keyed by mtime)
_goals_file_cache: dict[str, Any] | None = None
_goals_file_mtime: float = 0.0


class GoalsFileData(TypedDict):
    """Parsed structure of goals.md."""

    mission: str
    goals: list[dict[str, Any]]
    constraints: list[str]


@dataclass
class Goal:
    number: int
    title: str
    summary: str
    examples: list[str] = field(default_factory=list)


@dataclass
class RoadmapItem:
    title: str
    body: str = ""
    priority: str = ""
    goal: str = ""
    phase: str = ""
    status: str = ""


def _find_goals_file() -> str:
    """Find config/goals.md relative to the project root."""
    # Walk up from this file to find the project root (contains config/)
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidate = os.path.join(current, "config", "goals.md")
        if os.path.exists(candidate):
            return candidate
        current = os.path.dirname(current)
    return os.path.join("config", "goals.md")


def parse_goals_file() -> GoalsFileData:
    """Parse config/goals.md into structured data.

    Results are cached based on file modification time so the file is only
    read and parsed once unless it changes on disk.
    """
    global _goals_file_cache, _goals_file_mtime

    path = _find_goals_file()

    # Check mtime to avoid re-reading an unchanged file
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        return {"mission": "", "goals": [], "constraints": []}

    if _goals_file_cache is not None and current_mtime == _goals_file_mtime:
        return _goals_file_cache

    try:
        with open(path) as f:
            content = f.read()
    except FileNotFoundError:
        return {"mission": "", "goals": [], "constraints": []}

    # Extract mission (text between ## Mission and next ##)
    mission_match = re.search(r"## Mission\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    mission = mission_match.group(1).strip() if mission_match else ""

    # Extract goals (## Goal N: Title)
    goals: list[dict[str, Any]] = []
    goal_pattern = re.compile(r"## Goal (\d+): (.+?)\s*\n(.*?)(?=\n## |\Z)", re.DOTALL)
    for match in goal_pattern.finditer(content):
        number = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()

        # Split body into summary (paragraphs before bullet list) and examples (bullets)
        lines = body.split("\n")
        summary_lines: list[str] = []
        examples: list[str] = []
        in_examples = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                in_examples = True
                examples.append(stripped[2:])
            elif in_examples and stripped == "":
                continue
            elif not in_examples and stripped:
                # Skip lines that are just headers for examples
                if (
                    "examples of" in stripped.lower()
                    or "example categories" in stripped.lower()
                ):
                    continue
                if "pm" in stripped.lower() and (
                    "decides" in stripped.lower()
                    or "chooses" in stripped.lower()
                    or "should" in stripped.lower()
                ):
                    continue
                if "metrics will sometimes" in stripped.lower():
                    continue
                summary_lines.append(stripped)

        goals.append(
            {
                "number": number,
                "title": title,
                "summary": " ".join(summary_lines),
                "examples": examples,
            }
        )

    # Extract constraints
    constraints: list[str] = []
    constraints_match = re.search(
        r"## Constraints\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if constraints_match:
        for line in constraints_match.group(1).strip().split("\n"):
            stripped = line.strip()
            if stripped.startswith("- **"):
                # Extract bold text as the constraint name
                bold_match = re.match(r"- \*\*(.+?)\*\*", stripped)
                if bold_match:
                    constraints.append(bold_match.group(1).rstrip("."))

    result: GoalsFileData = {
        "mission": mission,
        "goals": goals,
        "constraints": constraints,
    }
    _goals_file_cache = result
    _goals_file_mtime = current_mtime
    return result


async def get_roadmap_snapshot() -> dict[str, Any]:
    """Fetch roadmap snapshot: active items + summary counts.

    Returns only what's actively being worked on, plus counts
    of how many items are in each status — a snapshot, not a mirror.
    """
    cached = _cache.get("roadmap")
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
            stale = _cache.get("roadmap")
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
        _cache.set("roadmap", result)
        return result

    except (asyncio.TimeoutError, FileNotFoundError, json.JSONDecodeError):
        stale = _cache.get("roadmap")
        return stale if stale is not None else empty


def _parse_event_timestamp(event: dict[str, Any]) -> float:
    """Parse GitHub event created_at to Unix timestamp."""
    ts_str = event.get("created_at", "")
    if not ts_str:
        return 0.0
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _bucket_event(event_ts: float, now: float) -> str | None:
    """Assign an event to a time window: 24h, 7d, or 30d."""
    age = now - event_ts
    if age <= 86400:
        return "24h"
    if age <= 604800:
        return "7d"
    if age <= 2592000:
        return "30d"
    return None


async def _fetch_github_data(
    headers: dict[str, str], repo: str
) -> tuple[list[Any], list[Any], list[Any]]:
    """Make the three parallel GitHub API calls for metrics.

    Returns:
        Tuple of (issues, prs, events) — each is a list of dicts or empty on error.
    """
    client = get_shared_client()
    base = f"https://api.github.com/repos/{repo}"

    issues_resp, prs_resp, events_resp = await asyncio.gather(
        client.get(
            f"{base}/issues",
            headers=headers,
            params={"state": "open", "per_page": "100"},
        ),
        client.get(
            f"{base}/pulls",
            headers=headers,
            params={"state": "open", "per_page": "100"},
        ),
        client.get(
            f"{base}/events",
            headers=headers,
            params={"per_page": "100"},
        ),
    )

    issues = issues_resp.json() if issues_resp.status_code == 200 else []
    prs = prs_resp.json() if prs_resp.status_code == 200 else []
    events = events_resp.json() if events_resp.status_code == 200 else []

    return issues, prs, events


def _process_events(
    events: list[dict[str, Any]], now: float
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Process GitHub events into bucketed metrics and per-agent stats.

    Returns:
        Tuple of (windowed_counts, agent_stats).
        windowed_counts has keys: issues_closed, prs_merged, commits — each with 24h/7d/30d.
        agent_stats is keyed by agent role with action counts.
    """
    empty_window: dict[str, int] = {"24h": 0, "7d": 0, "30d": 0}
    windowed: dict[str, dict[str, int]] = {
        "issues_closed": {**empty_window},
        "prs_merged": {**empty_window},
        "commits": {**empty_window},
    }
    agent_stats: dict[str, dict[str, int]] = {}

    for event in events:
        login = event.get("actor", {}).get("login", "unknown")
        role = ACTOR_MAP.get(login, login)
        if role == "org":
            continue
        event_type = event.get("type", "")
        payload = event.get("payload", {})
        event_ts = _parse_event_timestamp(event)
        bucket = _bucket_event(event_ts, now)

        if role not in agent_stats:
            agent_stats[role] = {
                "issues_opened": 0,
                "issues_closed": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "reviews": 0,
                "commits": 0,
            }

        if event_type == "IssuesEvent":
            action = payload.get("action", "")
            if action == "opened":
                agent_stats[role]["issues_opened"] += 1
            elif action == "closed":
                agent_stats[role]["issues_closed"] += 1
                if bucket:
                    windowed["issues_closed"][bucket] += 1
        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            if action == "opened":
                agent_stats[role]["prs_opened"] += 1
            elif action == "closed" and pr.get("merged"):
                agent_stats[role]["prs_merged"] += 1
                if bucket:
                    windowed["prs_merged"][bucket] += 1
        elif event_type == "PullRequestReviewEvent":
            agent_stats[role]["reviews"] += 1
        elif event_type == "PushEvent":
            commit_count = len(payload.get("commits", []))
            agent_stats[role]["commits"] += commit_count
            if bucket:
                windowed["commits"][bucket] += commit_count

    return windowed, agent_stats


async def get_metrics() -> dict[str, Any]:
    """Compute agent metrics with trend windows (24h / 7d / 30d)."""
    cached = _cache.get("metrics")
    if cached is not None:
        return cached

    settings = get_settings()
    headers = github_headers()
    repo = settings.github_repo

    empty_window: dict[str, int] = {"24h": 0, "7d": 0, "30d": 0}
    metrics: dict[str, Any] = {
        "open_issues": 0,
        "open_prs": 0,
        "issues_closed": {**empty_window},
        "prs_merged": {**empty_window},
        "commits": {**empty_window},
        "by_agent": {},
    }

    try:
        now = time.time()
        issues, prs, events = await _fetch_github_data(headers, repo)

        metrics["open_issues"] = sum(1 for i in issues if "pull_request" not in i)
        metrics["open_prs"] = len(prs)

        if events:
            windowed, agent_stats = _process_events(events, now)
            metrics["issues_closed"] = windowed["issues_closed"]
            metrics["prs_merged"] = windowed["prs_merged"]
            metrics["commits"] = windowed["commits"]
            metrics["by_agent"] = agent_stats

    except (httpx.HTTPError, httpx.TimeoutException):
        stale = _cache.get("metrics")
        if stale is not None:
            return stale

    _cache.set("metrics", metrics)
    return metrics


async def get_goals_data() -> dict[str, Any]:
    """Get all goals dashboard data in one call."""
    from datetime import datetime, timezone

    goals_data = parse_goals_file()
    roadmap_snapshot, agent_metrics = await asyncio.gather(
        get_roadmap_snapshot(),
        get_metrics(),
    )

    return {
        "mission": goals_data["mission"],
        "goals": goals_data["goals"],
        "constraints": goals_data["constraints"],
        "roadmap": roadmap_snapshot,
        "metrics": agent_metrics,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
