"""Tests for GitHub activity fetch — fallback events and deploy events."""

import pytest


def _make_activity_event(
    event_type,
    timestamp="2026-01-15T10:00:00Z",
    subject_type=None,
    subject_number=None,
    subject_title="",
    description="",
):
    """Build a minimal ActivityEvent dict matching parse_events output."""
    return {
        "type": event_type,
        "timestamp": timestamp,
        "actor": "engineer",
        "description": description,
        "url": "https://github.com/test/repo",
        "subject_type": subject_type,
        "subject_number": subject_number,
        "subject_title": subject_title,
    }


class TestFallbackEvents:
    """Tests for fetch_fallback_events() — Issues/PRs API fallback."""

    @pytest.mark.asyncio
    async def test_fallback_returns_issue_events(self, mock_settings, monkeypatch):
        """Fallback creates events from the Issues REST API."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_fetch import fetch_fallback_events

        issues_response = [
            {
                "number": 42,
                "title": "Fix the bug",
                "state": "closed",
                "closed_at": "2026-02-20T10:00:00Z",
                "created_at": "2026-02-20T08:00:00Z",
                "updated_at": "2026-02-20T10:00:00Z",
                "html_url": "https://github.com/testowner/testrepo/issues/42",
                "user": {
                    "login": "fishbowl-engineer[bot]",
                    "avatar_url": "https://example.com/avatar.png",
                },
            },
            {
                "number": 43,
                "title": "Add feature",
                "state": "open",
                "created_at": "2026-02-20T12:00:00Z",
                "updated_at": "2026-02-20T12:00:00Z",
                "html_url": "https://github.com/testowner/testrepo/issues/43",
                "user": {
                    "login": "fishbowl-product-owner[bot]",
                    "avatar_url": "https://example.com/po.png",
                },
            },
        ]

        monkeypatch.setattr(
            "api.services.github_activity_fetch.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            AsyncMock(return_value=issues_response),
        )

        result = await fetch_fallback_events(limit=30)

        assert len(result) == 2
        # Most recent first
        assert result[0]["type"] == "issue_created"
        assert result[0]["subject_number"] == 43
        assert result[0]["actor"] == "product-owner"
        assert result[1]["type"] == "issue_closed"
        assert result[1]["subject_number"] == 42
        assert result[1]["actor"] == "engineer"

    @pytest.mark.asyncio
    async def test_fallback_returns_pr_events(self, mock_settings, monkeypatch):
        """Fallback creates PR events from the Issues REST API."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_fetch import fetch_fallback_events

        issues_response = [
            {
                "number": 100,
                "title": "Add new endpoint",
                "state": "closed",
                "created_at": "2026-02-20T08:00:00Z",
                "updated_at": "2026-02-20T10:00:00Z",
                "html_url": "https://github.com/testowner/testrepo/pull/100",
                "user": {
                    "login": "fishbowl-engineer[bot]",
                    "avatar_url": "https://example.com/avatar.png",
                },
                "pull_request": {
                    "merged_at": "2026-02-20T10:00:00Z",
                },
            },
        ]

        monkeypatch.setattr(
            "api.services.github_activity_fetch.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            AsyncMock(return_value=issues_response),
        )

        result = await fetch_fallback_events(limit=30)

        assert len(result) == 1
        assert result[0]["type"] == "pr_merged"
        assert result[0]["subject_number"] == 100
        assert result[0]["subject_title"] == "Add new endpoint"

    @pytest.mark.asyncio
    async def test_fallback_skips_closed_unmerged_prs(self, mock_settings, monkeypatch):
        """Closed but not merged PRs are skipped in fallback."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity_fetch import fetch_fallback_events

        issues_response = [
            {
                "number": 101,
                "title": "Abandoned PR",
                "state": "closed",
                "created_at": "2026-02-20T08:00:00Z",
                "updated_at": "2026-02-20T10:00:00Z",
                "html_url": "https://github.com/testowner/testrepo/pull/101",
                "user": {"login": "fishbowl-engineer[bot]", "avatar_url": ""},
                "pull_request": {"merged_at": None},
            },
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = issues_response

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await fetch_fallback_events(limit=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_empty_when_no_repo(self, mock_settings, monkeypatch):
        """Fallback returns empty when github_repo is not configured."""
        from api.services.github_activity_fetch import fetch_fallback_events

        mock_settings.github_repo = ""

        result = await fetch_fallback_events(limit=30)
        assert result == []


class TestFetchDeployEvents:
    """Tests for fetch_deploy_events() — deploy workflow runs."""

    @pytest.mark.asyncio
    async def test_returns_deploy_events_from_workflow_runs(
        self, mock_settings, monkeypatch
    ):
        """Completed workflow runs are converted to deploy events."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_fetch import fetch_deploy_events

        workflow_response = {
            "workflow_runs": [
                {
                    "id": 12345,
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "abc1234def5678",
                    "display_title": "feat(api): add deploy events (#92)",
                    "html_url": "https://github.com/test/actions/runs/12345",
                    "created_at": "2026-02-20T10:00:00Z",
                    "actor": {
                        "login": "github-actions[bot]",
                        "avatar_url": "https://example.com/actions.png",
                    },
                },
                {
                    "id": 12346,
                    "status": "completed",
                    "conclusion": "failure",
                    "head_sha": "def5678abc1234",
                    "display_title": "fix(api): broken deploy",
                    "html_url": "https://github.com/test/actions/runs/12346",
                    "created_at": "2026-02-20T09:00:00Z",
                    "actor": {
                        "login": "github-actions[bot]",
                        "avatar_url": "https://example.com/actions.png",
                    },
                },
            ]
        }

        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            AsyncMock(return_value=workflow_response),
        )

        result = await fetch_deploy_events()

        assert len(result) == 2
        assert result[0]["type"] == "deploy"
        assert result[0]["deploy_status"] == "healthy"
        assert "abc1234" in result[0]["description"]
        assert result[1]["type"] == "deploy"
        assert result[1]["deploy_status"] == "failed"

    @pytest.mark.asyncio
    async def test_skips_in_progress_runs(self, mock_settings, monkeypatch):
        """Runs that haven't completed yet are excluded."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_fetch import fetch_deploy_events

        workflow_response = {
            "workflow_runs": [
                {
                    "id": 99999,
                    "status": "in_progress",
                    "conclusion": None,
                    "head_sha": "abc1234",
                    "display_title": "Still running",
                    "html_url": "https://github.com/test/actions/runs/99999",
                    "created_at": "2026-02-20T10:00:00Z",
                    "actor": {"login": "github-actions[bot]", "avatar_url": ""},
                },
            ]
        }

        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            AsyncMock(return_value=workflow_response),
        )

        result = await fetch_deploy_events()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_api_failure(self, mock_settings, monkeypatch):
        """API failure returns empty list, no crash."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_fetch import fetch_deploy_events

        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            AsyncMock(return_value=None),
        )

        result = await fetch_deploy_events()
        assert result == []
