"""GitHub agent status — fetches workflow run status for each agent role.

Polls the GitHub Actions API for recent workflow runs and maps them to
agent roles. Results are cached with a 60-second TTL for live status display.
"""

import asyncio
from typing import Any

from api.config import get_settings
from api.services.cache import TTLCache
from api.services.http_client import github_api_get
from api.services.usage_storage import get_run_usage

# TTL cache for agent status (60s — the "live" signal)
_status_cache = TTLCache(ttl=60, max_size=5)

# Map workflow filenames to agent roles
WORKFLOW_AGENT_MAP: dict[str, list[str]] = {
    "agent-engineer.yml": ["engineer"],
    "agent-ops-engineer.yml": ["ops-engineer"],
    "agent-reviewer.yml": ["reviewer"],
    "agent-product-owner.yml": ["product-owner"],
    "agent-triage.yml": ["triage"],
    "agent-site-reliability.yml": ["site-reliability"],
    "agent-scans.yml": ["tech-lead", "user-experience"],
    "agent-strategic.yml": ["product-manager"],
    "agent-content-creator.yml": ["content-creator"],
    "agent-qa-analyst.yml": ["qa-analyst"],
    "agent-customer-ops.yml": ["customer-ops"],
    "agent-human-ops.yml": ["human-ops"],
}


async def _fetch_workflow_runs(
    repo: str,
    workflow_file: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch the most recent run for a single workflow file.

    Returns (workflow_file, runs) so callers can map results back.
    """
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs"
    params = {"per_page": "1"}
    result = await github_api_get(
        url, params, response_key="workflow_runs", context=workflow_file
    )
    return (workflow_file, result if result is not None else [])


async def get_agent_status() -> list[dict[str, Any]]:
    """Fetch the current status of each agent from GitHub Actions workflow runs.

    Queries each workflow individually (per_page=1) to guarantee that
    infrequent agents are never pushed out of the result window by
    high-frequency agents like reviewer or engineer.

    Returns a list of agent status dicts with role, status, timing, etc.
    Cached with 60s TTL.
    """
    cache_key = "agent_status"
    cached = _status_cache.get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()

    # Fetch latest run for each workflow concurrently
    fetch_results = await asyncio.gather(
        *(_fetch_workflow_runs(settings.github_repo, wf) for wf in WORKFLOW_AGENT_MAP),
        return_exceptions=True,
    )

    # Build a map of agent role -> most recent run
    agent_runs: dict[str, dict[str, Any]] = {}
    any_success = False

    for item in fetch_results:
        if isinstance(item, Exception):
            continue
        # At least one fetch completed without raising — API is reachable
        any_success = True
        workflow_file, runs = item
        if runs:
            roles = WORKFLOW_AGENT_MAP.get(workflow_file, [])
            for role in roles:
                if role not in agent_runs:
                    agent_runs[role] = runs[0]

    if not any_success:
        stale = _status_cache.get_stale(cache_key)
        return stale if stale is not None else []

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
    all_roles = [
        "product-owner",
        "product-manager",
        "engineer",
        "ops-engineer",
        "reviewer",
        "tech-lead",
        "triage",
        "site-reliability",
        "user-experience",
        "content-creator",
        "qa-analyst",
        "customer-ops",
        "human-ops",
        "escalation-lead",
        "financial-analyst",
        "marketing-strategist",
        "product-analyst",
    ]

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
                # Alias old short-form role names from legacy blobs to canonical names
                _BLOB_ROLE_ALIASES: dict[str, str] = {
                    "po": "product-owner",
                    "pm": "product-manager",
                    "sre": "site-reliability",
                    "ux": "user-experience",
                    "infra-engineer": "ops-engineer",
                }
                role_usage = next(
                    (
                        a
                        for a in agents_list
                        if _BLOB_ROLE_ALIASES.get(a.get("role", ""), a.get("role", ""))
                        == role
                    ),
                    None,
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
                    summary = role_usage.get("result_summary")
                    if summary:
                        entry["last_summary"] = summary

        result.append(entry)

    _status_cache.set(cache_key, result)
    return result
