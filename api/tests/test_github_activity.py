"""Tests for GitHub activity feed — orchestration and caching."""

import pytest


class TestGetActivityEventsCaching:
    """Tests for get_activity_events() cache behavior."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        """Cache hit returns stored events without API call."""
        from api.services.github_activity import _cache, get_activity_events

        fake_events = [{"type": "test", "timestamp": "2026-01-15T10:00:00Z"}]
        _cache.set("flat:1:30", fake_events)

        result = await get_activity_events(page=1, per_page=30)
        assert result == fake_events

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_and_caches(self, mock_settings, monkeypatch):
        """Cache miss triggers API fetch, result is cached."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity import _cache, get_activity_events

        raw_events = [
            {
                "id": "1",
                "type": "IssuesEvent",
                "actor": {"login": "fishbowl-engineer[bot]"},
                "payload": {
                    "action": "opened",
                    "issue": {
                        "title": "Test issue",
                        "html_url": "https://github.com/test/repo/issues/1",
                    },
                },
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = raw_events

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_activity_events(page=1, per_page=30)
        assert len(result) == 1
        assert result[0]["type"] == "issue_created"

        # Verify it's now cached
        cached = _cache.get("flat:1:30")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_empty_events_and_fallback_both_empty(
        self, mock_settings, monkeypatch
    ):
        """When both Events API and fallback return empty, result is not cached."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity import _cache, get_activity_events

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        result = await get_activity_events(page=1, per_page=30)
        assert result == []

        # Empty result should not be cached
        cached = _cache.get("flat:1:30")
        assert cached is None


class TestEventsWithFallback:
    """Tests for _get_events_with_fallback() — primary + fallback path."""

    @pytest.mark.asyncio
    async def test_uses_events_api_when_available(self, mock_settings, monkeypatch):
        """When Events API returns data, fallback is not called."""
        from api.services.github_activity import _get_events_with_fallback

        raw_events = [
            {
                "id": "1",
                "type": "IssuesEvent",
                "actor": {"login": "fishbowl-engineer[bot]"},
                "payload": {
                    "action": "opened",
                    "issue": {
                        "number": 10,
                        "title": "Test",
                        "html_url": "https://github.com/test/repo/issues/10",
                    },
                },
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]

        async def mock_github_api_get(url, params=None, **kwargs):
            if "/events" in url:
                return raw_events
            if "/actions/workflows/" in url:
                return {"workflow_runs": []}
            return None

        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            mock_github_api_get,
        )

        result = await _get_events_with_fallback(per_page=30)

        assert len(result) == 1
        assert result[0]["type"] == "issue_created"

    @pytest.mark.asyncio
    async def test_falls_back_when_events_api_empty(self, mock_settings, monkeypatch):
        """When Events API returns empty, falls back to Issues API."""
        from api.services.github_activity import _get_events_with_fallback

        async def mock_github_api_get(url, params=None, **kwargs):
            if "/events" in url:
                return []
            if "/actions/workflows/" in url:
                return {"workflow_runs": []}
            if "/issues" in url:
                return [
                    {
                        "number": 50,
                        "title": "Fallback issue",
                        "state": "open",
                        "created_at": "2026-02-20T12:00:00Z",
                        "updated_at": "2026-02-20T12:00:00Z",
                        "html_url": "https://github.com/test/issues/50",
                        "user": {
                            "login": "fishbowl-engineer[bot]",
                            "avatar_url": "",
                        },
                    }
                ]
            return None

        monkeypatch.setattr(
            "api.services.github_activity_fetch.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            mock_github_api_get,
        )

        result = await _get_events_with_fallback(per_page=30)

        assert len(result) == 1
        assert result[0]["type"] == "issue_created"
        assert result[0]["description"] == "Opened issue #50: Fallback issue"

    @pytest.mark.asyncio
    async def test_deploy_events_merged_into_feed(self, mock_settings, monkeypatch):
        """Deploy events appear in _get_events_with_fallback output."""
        from api.services.github_activity import _get_events_with_fallback

        raw_events = [
            {
                "id": "1",
                "type": "IssuesEvent",
                "actor": {"login": "fishbowl-engineer[bot]"},
                "payload": {
                    "action": "opened",
                    "issue": {
                        "number": 10,
                        "title": "Test",
                        "html_url": "https://github.com/test/repo/issues/10",
                    },
                },
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]

        async def mock_github_api_get(url, params=None, **kwargs):
            if "/events" in url:
                return raw_events
            if "/actions/workflows/" in url:
                return {
                    "workflow_runs": [
                        {
                            "id": 555,
                            "status": "completed",
                            "conclusion": "success",
                            "head_sha": "abc1234",
                            "display_title": "Deploy test",
                            "html_url": "https://github.com/test/runs/555",
                            "created_at": "2026-01-15T11:00:00Z",
                            "actor": {
                                "login": "github-actions[bot]",
                                "avatar_url": "",
                            },
                        }
                    ]
                }
            return None

        monkeypatch.setattr(
            "api.services.github_activity_fetch.github_api_get",
            mock_github_api_get,
        )

        result = await _get_events_with_fallback(per_page=30)

        # Should have both the issue event and the deploy event
        assert len(result) == 2
        types = {e["type"] for e in result}
        assert "issue_created" in types
        assert "deploy" in types
        # Deploy event (11:00) is more recent, so it should be first
        assert result[0]["type"] == "deploy"


class TestGetThreadedActivityCaching:
    """Tests for get_threaded_activity() cache behavior."""

    @pytest.mark.asyncio
    async def test_returns_cached_threads(self):
        """Cache hit returns stored threads without API call."""
        from api.services.github_activity import _cache, get_threaded_activity

        fake_threads = [{"type": "thread", "subject_number": 1, "events": []}]
        _cache.set("threaded:50", fake_threads)

        result = await get_threaded_activity(per_page=50)
        assert result == fake_threads
