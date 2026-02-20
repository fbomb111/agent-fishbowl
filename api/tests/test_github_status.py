"""Tests for GitHub agent status — workflow-to-agent mapping, caching, errors."""

from unittest.mock import AsyncMock, MagicMock

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
        }
        assert set(WORKFLOW_AGENT_MAP.keys()) == expected_workflows

    def test_scans_maps_to_multiple_agents(self):
        assert WORKFLOW_AGENT_MAP["agent-scans.yml"] == ["tech-lead", "ux"]

    def test_single_agent_workflows(self):
        assert WORKFLOW_AGENT_MAP["agent-engineer.yml"] == ["engineer"]
        assert WORKFLOW_AGENT_MAP["agent-reviewer.yml"] == ["reviewer"]
        assert WORKFLOW_AGENT_MAP["agent-strategic.yml"] == ["pm"]


class TestGetAgentStatus:
    """Tests for get_agent_status() — fetching, mapping, and caching."""

    def _make_workflow_run(
        self,
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
        runs = [
            self._make_workflow_run(
                "agent-engineer.yml", status="in_progress", conclusion=None
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": runs}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
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
        runs = [
            self._make_workflow_run(
                "agent-reviewer.yml", status="completed", conclusion="failure"
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": runs}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
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
        runs = [
            self._make_workflow_run(
                "agent-product-owner.yml", status="completed", conclusion="success"
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": runs}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        po = next(r for r in result if r["role"] == "po")
        assert po["status"] == "idle"
        assert po["last_conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_unmapped_agents_are_idle(self, mock_settings, monkeypatch):
        """Agents with no matching workflow run show as 'idle'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": []}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_agent_status()
        for entry in result:
            assert entry["status"] == "idle"

    @pytest.mark.asyncio
    async def test_all_roles_present_in_output(self, mock_settings, monkeypatch):
        """Output always includes all 10 agent roles."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": []}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_agent_status()
        roles = {r["role"] for r in result}
        expected_roles = {
            "po",
            "engineer",
            "ops-engineer",
            "reviewer",
            "triage",
            "sre",
            "pm",
            "tech-lead",
            "ux",
            "content-creator",
        }
        assert roles == expected_roles

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty(self, mock_settings, monkeypatch):
        """Non-200 API response returns empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_agent_status()
        assert result == []

    @pytest.mark.asyncio
    async def test_api_exception_returns_empty(self, mock_settings, monkeypatch):
        """Network exception returns empty list."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_agent_status()
        assert result == []

    @pytest.mark.asyncio
    async def test_scans_workflow_maps_to_both_roles(self, mock_settings, monkeypatch):
        """agent-scans.yml maps to both tech-lead and ux roles."""
        runs = [
            self._make_workflow_run(
                "agent-scans.yml", status="in_progress", conclusion=None
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": runs}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )
        monkeypatch.setattr(
            "api.services.github_status.get_run_usage", AsyncMock(return_value=None)
        )

        result = await get_agent_status()
        tech_lead = next(r for r in result if r["role"] == "tech-lead")
        ux = next(r for r in result if r["role"] == "ux")
        assert tech_lead["status"] == "active"
        assert ux["status"] == "active"

    @pytest.mark.asyncio
    async def test_usage_data_enriches_completed_run(self, mock_settings, monkeypatch):
        """Completed runs are enriched with usage data from blob storage."""
        runs = [
            self._make_workflow_run(
                "agent-engineer.yml",
                status="completed",
                conclusion="success",
                run_id=5000,
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_runs": runs}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

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
            "api.services.http_client.get_shared_client", lambda: mock_client
        )
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
