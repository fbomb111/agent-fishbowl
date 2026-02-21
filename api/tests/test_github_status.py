"""Tests for GitHub agent status — workflow-to-agent mapping, caching, errors."""

from unittest.mock import AsyncMock

import pytest

from api.services.github_status import WORKFLOW_AGENT_MAP, get_agent_status


class TestWorkflowAgentMap:
    """Tests for the WORKFLOW_AGENT_MAP constant."""

    def test_all_agent_workflows_mapped(self):
        expected_workflows = {
            "agent-engineer.yml",
            "agent-ops-engineer.yml",
            "agent-reviewer.yml",
            "agent-product-owner.yml",
            "agent-triage.yml",
            "agent-site-reliability.yml",
            "agent-scans.yml",
            "agent-strategic.yml",
            "agent-content-creator.yml",
            "agent-qa-analyst.yml",
            "agent-customer-ops.yml",
            "agent-human-ops.yml",
        }
        assert set(WORKFLOW_AGENT_MAP.keys()) == expected_workflows

    def test_scans_maps_to_multiple_agents(self):
        assert WORKFLOW_AGENT_MAP["agent-scans.yml"] == ["tech-lead", "user-experience"]

    def test_single_agent_workflows(self):
        assert WORKFLOW_AGENT_MAP["agent-engineer.yml"] == ["engineer"]
        assert WORKFLOW_AGENT_MAP["agent-reviewer.yml"] == ["reviewer"]
        assert WORKFLOW_AGENT_MAP["agent-strategic.yml"] == ["product-manager"]


def _make_workflow_run(
    workflow_file,
    status="completed",
    conclusion="success",
    run_id=1000,
    updated_at="2026-01-15T10:00:00Z",
    run_started_at="2026-01-15T09:55:00Z",
    event="workflow_dispatch",
):
    return {
        "id": run_id,
        "path": f".github/workflows/{workflow_file}",
        "status": status,
        "conclusion": conclusion,
        "updated_at": updated_at,
        "run_started_at": run_started_at,
        "event": event,
    }


def _mock_fetch(workflow_runs: dict[str, list[dict]]):
    """Build a mock _fetch_workflow_runs that returns runs per workflow.

    Args:
        workflow_runs: mapping of workflow filename -> list of run dicts
    """

    async def fake_fetch(repo: str, workflow_file: str):
        return (workflow_file, workflow_runs.get(workflow_file, []))

    return fake_fetch


class TestGetAgentStatus:
    """Tests for get_agent_status() — fetching, mapping, and caching."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        """Cache hit returns stored status without API call."""
        from api.services.github_status import _status_cache

        fake_status = [{"role": "engineer", "status": "active"}]
        _status_cache.set("agent_status", fake_status)

        result = await get_agent_status()
        assert result == fake_status

    @pytest.mark.asyncio
    async def test_maps_active_workflow_to_active_status(
        self, mock_settings, monkeypatch
    ):
        """In-progress workflow run maps to 'active' agent status."""
        run = _make_workflow_run(
            "agent-engineer.yml", status="in_progress", conclusion=None
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-engineer.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        engineer = next(r for r in result if r["role"] == "engineer")
        assert engineer["status"] == "active"
        assert "started_at" in engineer
        assert "trigger" in engineer

    @pytest.mark.asyncio
    async def test_maps_failed_workflow_to_failed_status(
        self, mock_settings, monkeypatch
    ):
        """Failed workflow run maps to 'failed' agent status."""
        run = _make_workflow_run(
            "agent-reviewer.yml", status="completed", conclusion="failure"
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-reviewer.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        reviewer = next(r for r in result if r["role"] == "reviewer")
        assert reviewer["status"] == "failed"

    @pytest.mark.asyncio
    async def test_maps_success_workflow_to_idle_status(
        self, mock_settings, monkeypatch
    ):
        """Completed-success workflow run maps to 'idle' agent status."""
        run = _make_workflow_run(
            "agent-product-owner.yml", status="completed", conclusion="success"
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-product-owner.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        po = next(r for r in result if r["role"] == "product-owner")
        assert po["status"] == "idle"
        assert po["last_conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_unmapped_agents_are_idle(self, mock_settings, monkeypatch):
        """Agents with no matching workflow run show as 'idle'."""
        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({}),
        )

        result = await get_agent_status()
        for entry in result:
            assert entry["status"] == "idle"

    @pytest.mark.asyncio
    async def test_unmapped_agents_idle_when_some_have_runs(
        self, mock_settings, monkeypatch
    ):
        """Agents with no matching run show 'idle' when others have runs."""
        run = _make_workflow_run(
            "agent-engineer.yml", status="completed", conclusion="success"
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-engineer.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        sre = next(r for r in result if r["role"] == "site-reliability")
        assert sre["status"] == "idle"

    @pytest.mark.asyncio
    async def test_all_roles_present_in_output(self, mock_settings, monkeypatch):
        """Output always includes all 17 agent roles."""
        # Need at least one run so any_success is True
        run = _make_workflow_run(
            "agent-engineer.yml", status="completed", conclusion="success"
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-engineer.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        roles = {r["role"] for r in result}
        expected_roles = {
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
        }
        assert roles == expected_roles

    @pytest.mark.asyncio
    async def test_all_fetches_fail_returns_empty(self, mock_settings, monkeypatch):
        """When all per-workflow fetches fail, returns empty list."""

        async def failing_fetch(repo, workflow_file):
            raise Exception("Connection refused")

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            failing_fetch,
        )

        result = await get_agent_status()
        assert result == []

    @pytest.mark.asyncio
    async def test_partial_fetch_failure_still_works(self, mock_settings, monkeypatch):
        """When some per-workflow fetches fail, others still populate."""
        run = _make_workflow_run(
            "agent-engineer.yml", status="completed", conclusion="success"
        )

        call_count = 0

        async def partial_fetch(repo, workflow_file):
            nonlocal call_count
            call_count += 1
            if workflow_file == "agent-engineer.yml":
                return ("agent-engineer.yml", [run])
            if workflow_file == "agent-reviewer.yml":
                raise Exception("timeout")
            return (workflow_file, [])

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            partial_fetch,
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        engineer = next(r for r in result if r["role"] == "engineer")
        assert engineer["status"] == "idle"
        assert engineer["last_conclusion"] == "success"
        # Reviewer should be idle (fetch failed, no data)
        reviewer = next(r for r in result if r["role"] == "reviewer")
        assert reviewer["status"] == "idle"

    @pytest.mark.asyncio
    async def test_scans_workflow_maps_to_both_roles(self, mock_settings, monkeypatch):
        """agent-scans.yml maps to both tech-lead and ux roles."""
        run = _make_workflow_run(
            "agent-scans.yml", status="in_progress", conclusion=None
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-scans.yml": [run]}),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        tech_lead = next(r for r in result if r["role"] == "tech-lead")
        ux = next(r for r in result if r["role"] == "user-experience")
        assert tech_lead["status"] == "active"
        assert ux["status"] == "active"

    @pytest.mark.asyncio
    async def test_usage_data_enriches_completed_run(self, mock_settings, monkeypatch):
        """Completed runs are enriched with usage data from blob storage."""
        run = _make_workflow_run(
            "agent-engineer.yml",
            status="completed",
            conclusion="success",
            run_id=5000,
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch({"agent-engineer.yml": [run]}),
        )

        usage_data = {
            "agents": [
                {
                    "role": "engineer",
                    "total_cost_usd": 0.42,
                    "num_turns": 15,
                    "duration_api_ms": 120000,
                    "usage": {
                        "input_tokens": 50000,
                        "output_tokens": 10000,
                        "cache_creation_input_tokens": 5000,
                        "cache_read_input_tokens": 3000,
                    },
                    "result_summary": "Implemented feature X",
                }
            ]
        }

        monkeypatch.setattr(
            "api.services.github_status.get_run_usage",
            AsyncMock(return_value=usage_data),
        )

        result = await get_agent_status()
        engineer = next(r for r in result if r["role"] == "engineer")
        assert "usage" in engineer
        assert engineer["usage"]["cost_usd"] == 0.42
        assert engineer["usage"]["num_turns"] == 15
        assert engineer["usage"]["duration_s"] == 120
        assert engineer["last_summary"] == "Implemented feature X"

    @pytest.mark.asyncio
    async def test_per_workflow_fetch_finds_infrequent_agents(
        self, mock_settings, monkeypatch
    ):
        """Regression: infrequent agents (SRE) are found even when
        frequent agents (reviewer, engineer) have many more runs.

        This is the core bug from issue #233 — the old 50-run window
        approach missed infrequent agents entirely.
        """
        sre_run = _make_workflow_run(
            "agent-site-reliability.yml",
            status="completed",
            conclusion="failure",
            run_id=2000,
        )
        engineer_run = _make_workflow_run(
            "agent-engineer.yml",
            status="completed",
            conclusion="success",
            run_id=3000,
        )

        monkeypatch.setattr(
            "api.services.github_status._fetch_workflow_runs",
            _mock_fetch(
                {
                    "agent-site-reliability.yml": [sre_run],
                    "agent-engineer.yml": [engineer_run],
                }
            ),
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        sre = next(r for r in result if r["role"] == "site-reliability")
        assert sre["status"] == "failed"
        assert sre["last_conclusion"] == "failure"
