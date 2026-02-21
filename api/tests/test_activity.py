"""Tests for the activity feed endpoints.

Covers threaded/flat modes, pagination, agent status, and usage summary.
"""

from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient


async def test_list_activity_flat_mode(mock_settings, mocker):
    """Test activity feed in flat mode returns a simple list of events."""
    mock_events = [
        {
            "id": "event1",
            "type": "IssuesEvent",
            "actor": {"login": "fishbowl-engineer[bot]"},
            "created_at": "2026-02-20T10:00:00Z",
        },
        {
            "id": "event2",
            "type": "PullRequestEvent",
            "actor": {"login": "fishbowl-reviewer[bot]"},
            "created_at": "2026-02-20T09:00:00Z",
        },
    ]
    mocker.patch(
        "api.routers.activity.get_activity_events",
        new_callable=AsyncMock,
        return_value=mock_events,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/activity", params={"mode": "flat", "page": 1, "per_page": 20}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "flat"
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert len(data["events"]) == 2


async def test_list_activity_threaded_mode(mock_settings, mocker):
    """Test activity feed in threaded mode groups events by issue/PR."""
    mock_threads = [
        {
            "issue_number": 42,
            "issue_title": "Add feature X",
            "events": [
                {"type": "IssuesEvent", "actor": {"login": "fishbowl-po[bot]"}},
                {
                    "type": "IssueCommentEvent",
                    "actor": {"login": "fishbowl-engineer[bot]"},
                },
            ],
        },
        {
            "pr_number": 43,
            "pr_title": "Fix bug Y",
            "events": [
                {
                    "type": "PullRequestEvent",
                    "actor": {"login": "fishbowl-engineer[bot]"},
                },
            ],
        },
    ]
    mocker.patch(
        "api.routers.activity.get_threaded_activity",
        new_callable=AsyncMock,
        return_value=mock_threads,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/activity", params={"mode": "threaded"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "threaded"
    assert len(data["threads"]) == 2
    assert data["threads"][0]["issue_number"] == 42


async def test_list_activity_defaults_to_threaded(mock_settings, mocker):
    """Test activity feed defaults to threaded mode when mode is not specified."""
    mocker.patch(
        "api.routers.activity.get_threaded_activity",
        new_callable=AsyncMock,
        return_value=[],
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/activity")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "threaded"


async def test_agent_status_endpoint(mock_settings, mocker):
    """Test agent status endpoint returns workflow run status for each agent."""
    mock_agents = [
        {
            "role": "engineer",
            "status": "success",
            "last_run": "2026-02-20T10:00:00Z",
            "conclusion": "success",
        },
        {
            "role": "reviewer",
            "status": "in_progress",
            "last_run": "2026-02-20T09:30:00Z",
            "conclusion": None,
        },
    ]
    mocker.patch(
        "api.routers.activity.get_agent_status",
        new_callable=AsyncMock,
        return_value=mock_agents,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/activity/agent-status")

    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert len(data["agents"]) == 2
    assert data["agents"][0]["role"] == "engineer"


async def test_usage_summary_endpoint(mock_settings, mocker):
    """Test usage summary aggregates token costs across runs."""
    mock_usage = [
        {
            "run_id": "run1",
            "agents": [
                {"role": "engineer", "total_cost_usd": 0.15},
                {"role": "reviewer", "total_cost_usd": 0.05},
            ],
        },
        {
            "run_id": "run2",
            "agents": [
                {"role": "engineer", "total_cost_usd": 0.10},
            ],
        },
    ]
    mocker.patch(
        "api.routers.activity.get_recent_usage",
        new_callable=AsyncMock,
        return_value=mock_usage,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/activity/usage", params={"limit": 50}
        )

    assert response.status_code == 200
    data = response.json()
    assert "total_cost" in data
    assert "total_runs" in data
    assert "by_role" in data
    assert data["total_runs"] == 2
    # Engineer: 0.15 + 0.10 = 0.25, Reviewer: 0.05
    assert data["total_cost"] == 0.30


async def test_usage_summary_handles_role_aliases(mock_settings, mocker):
    """Test usage summary normalizes role aliases (po -> product-owner, etc)."""
    mock_usage = [
        {
            "run_id": "run1",
            "agents": [
                {"role": "po", "total_cost_usd": 0.10},  # Alias
                {"role": "product-owner", "total_cost_usd": 0.05},  # Full name
            ],
        },
    ]
    mocker.patch(
        "api.routers.activity.get_recent_usage",
        new_callable=AsyncMock,
        return_value=mock_usage,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/activity/usage")

    assert response.status_code == 200
    data = response.json()
    # Both should be aggregated under "product-owner"
    assert len(data["by_role"]) == 1
    assert data["by_role"][0]["role"] == "product-owner"
    assert data["by_role"][0]["total_cost"] == 0.15
