"""Goals service — parses goals.md, fetches roadmap from GitHub Project, computes metrics.

Data sources:
- Goals: Parsed from config/goals.md (static, cached indefinitely until file changes)
- Roadmap: GitHub Project #1 via `gh` CLI (cached 5 min)
- Metrics: GitHub API issues/PRs (cached 5 min)
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from api.config import get_settings
from api.services.github import ACTOR_MAP

# Cache TTL matches activity feed
CACHE_TTL = 300  # 5 minutes

_cache: dict[str, tuple[Any, float]] = {}


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


def parse_goals_file() -> dict[str, Any]:
    """Parse config/goals.md into structured data."""
    path = _find_goals_file()
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

    return {"mission": mission, "goals": goals, "constraints": constraints}


async def get_roadmap_snapshot() -> dict[str, Any]:
    """Fetch roadmap snapshot: active items + summary counts.

    Returns only what's actively being worked on, plus counts
    of how many items are in each status — a snapshot, not a mirror.
    """
    cache_key = "roadmap"
    if cache_key in _cache:
        data, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return data

    empty: dict[str, Any] = {
        "active": [],
        "counts": {"proposed": 0, "active": 0, "done": 0, "deferred": 0},
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            "gh",
            "project",
            "item-list",
            "1",
            "--owner",
            "YourMoveLabs",
            "--format",
            "json",
            "--limit",
            "50",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

        if proc.returncode != 0:
            if cache_key in _cache:
                return _cache[cache_key][0]
            return empty

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
        _cache[cache_key] = (result, time.time())
        return result

    except (asyncio.TimeoutError, FileNotFoundError, json.JSONDecodeError):
        if cache_key in _cache:
            return _cache[cache_key][0]
        return empty


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


async def get_metrics() -> dict[str, Any]:
    """Compute agent metrics with trend windows (24h / 7d / 30d)."""
    cache_key = "metrics"
    if cache_key in _cache:
        data, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return data

    settings = get_settings()
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    repo = settings.github_repo
    base = f"https://api.github.com/repos/{repo}"

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
        async with httpx.AsyncClient(timeout=10.0) as client:
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

            if issues_resp.status_code == 200:
                issues = issues_resp.json()
                metrics["open_issues"] = sum(
                    1 for i in issues if "pull_request" not in i
                )

            if prs_resp.status_code == 200:
                metrics["open_prs"] = len(prs_resp.json())

            if events_resp.status_code == 200:
                events = events_resp.json()
                agent_stats: dict[str, dict[str, int]] = {}

                for event in events:
                    login = event.get("actor", {}).get("login", "unknown")
                    role = ACTOR_MAP.get(login, login)
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
                                metrics["issues_closed"][bucket] += 1
                    elif event_type == "PullRequestEvent":
                        action = payload.get("action", "")
                        pr = payload.get("pull_request", {})
                        if action == "opened":
                            agent_stats[role]["prs_opened"] += 1
                        elif action == "closed" and pr.get("merged"):
                            agent_stats[role]["prs_merged"] += 1
                            if bucket:
                                metrics["prs_merged"][bucket] += 1
                    elif event_type == "PullRequestReviewEvent":
                        agent_stats[role]["reviews"] += 1
                    elif event_type == "PushEvent":
                        commit_count = len(payload.get("commits", []))
                        agent_stats[role]["commits"] += commit_count
                        if bucket:
                            metrics["commits"][bucket] += commit_count

                metrics["by_agent"] = agent_stats

    except (httpx.HTTPError, httpx.TimeoutException):
        if cache_key in _cache:
            return _cache[cache_key][0]

    _cache[cache_key] = (metrics, time.time())
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
