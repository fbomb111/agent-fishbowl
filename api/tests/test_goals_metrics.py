"""Tests for goals_metrics service — Search API counts, commit counting, agent stats."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.services.cache import TTLCache
from api.services.goals_metrics import (
    _agent_role,
    _count_commits,
    _fetch_agent_stats,
    _fetch_windowed_counts,
    _search_count,
    get_metrics,
)


class TestAgentRole:
    """Tests for _agent_role()."""

    def test_known_bot(self):
        assert _agent_role("fishbowl-engineer[bot]") == "engineer"

    def test_human(self):
        assert _agent_role("fbomb111") == "human"

    def test_unknown_login(self):
        assert _agent_role("random-user") is None

    def test_org_login(self):
        assert _agent_role("YourMoveLabs") == "org"


class TestSearchCount:
    """Tests for _search_count()."""

    @pytest.mark.asyncio
    async def test_returns_total_count(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json={"total_count": 42, "items": []})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _search_count("repo:test is:issue is:open")
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(403, json={"message": "rate limited"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _search_count("repo:test is:issue is:open")
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_exception(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _search_count("repo:test is:issue is:open")
        assert result == 0


class TestCountCommits:
    """Tests for _count_commits()."""

    @pytest.mark.asyncio
    async def test_uses_link_header(self, monkeypatch):
        """Parses last page number from Link header for total count."""
        link = (
            "<https://api.github.com/repos/test/commits?since=2026-01-01&per_page=1&page=37>; "
            'rel="last"'
        )

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[{}], headers={"Link": link})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result == 37

    @pytest.mark.asyncio
    async def test_no_link_header_counts_items(self, monkeypatch):
        """When no Link header, falls back to counting response items."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[{"sha": "a"}, {"sha": "b"}])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        # per_page=1 so only 1 item expected, but tests the fallback logic
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result == 2

    @pytest.mark.asyncio
    async def test_returns_zero_on_non_200(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_exception(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result == 0


class TestFetchWindowedCounts:
    """Tests for _fetch_windowed_counts()."""

    @pytest.mark.asyncio
    async def test_returns_all_windows(self):
        """All three windows and three metrics are returned."""
        now = datetime.now(UTC)

        with (
            patch(
                "api.services.goals_metrics._search_count",
                new_callable=AsyncMock,
                side_effect=[10, 5, 3, 20, 12, 8, 50, 30, 25],
            ),
            patch(
                "api.services.goals_metrics._count_commits",
                new_callable=AsyncMock,
                side_effect=[3, 8, 25],
            ),
        ):
            result = await _fetch_windowed_counts("test/repo", now)

        assert result["issues_closed"]["24h"] == 10
        assert result["issues_closed"]["7d"] == 20
        assert result["issues_closed"]["30d"] == 50
        assert result["prs_merged"]["24h"] == 5
        assert result["prs_merged"]["7d"] == 12
        assert result["prs_merged"]["30d"] == 30
        assert result["commits"]["24h"] == 3
        assert result["commits"]["7d"] == 8
        assert result["commits"]["30d"] == 25

    @pytest.mark.asyncio
    async def test_returns_all_windows_directly(self):
        """Verify correct index mapping by mocking at asyncio.gather level."""
        now = datetime.now(UTC)

        # The function creates 9 tasks in order:
        # 24h: issues_closed, prs_merged, commits
        # 7d:  issues_closed, prs_merged, commits
        # 30d: issues_closed, prs_merged, commits
        mock_results = [1, 2, 3, 4, 5, 6, 7, 8, 9]

        async def mock_search_count(query):
            return 0  # won't be called directly

        async def mock_count_commits(repo, since):
            return 0

        with patch(
            "api.services.goals_metrics.asyncio.gather",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            result = await _fetch_windowed_counts("test/repo", now)

        # Verify index mapping: results[0]=24h issues, [3]=7d issues, [6]=30d issues
        assert result["issues_closed"] == {"24h": 1, "7d": 4, "30d": 7}
        assert result["prs_merged"] == {"24h": 2, "7d": 5, "30d": 8}
        assert result["commits"] == {"24h": 3, "7d": 6, "30d": 9}


class TestFetchAgentStats:
    """Tests for _fetch_agent_stats()."""

    @pytest.mark.asyncio
    async def test_counts_issues_by_assignee(self):
        """Issues are attributed to the first assignee's agent role."""
        issues = [
            {
                "assignees": [{"login": "fishbowl-product-owner[bot]"}],
                "user": {"login": "fishbowl-triage[bot]"},
            },
        ]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[issues, []],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["po"]["issues_closed"] == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_user_login(self):
        """When no assignee, falls back to issue creator."""
        issues = [
            {
                "assignees": [],
                "user": {"login": "fishbowl-engineer[bot]"},
            },
        ]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[issues, []],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["issues_closed"] == 1

    @pytest.mark.asyncio
    async def test_counts_prs_by_author(self):
        """PRs are attributed to the PR author's agent role."""
        prs = [
            {"user": {"login": "fishbowl-engineer[bot]"}},
        ]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[[], prs],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["prs_merged"] == 1

    @pytest.mark.asyncio
    async def test_skips_unknown_logins(self):
        """Items from unknown logins are ignored."""
        issues = [
            {
                "assignees": [{"login": "random-user"}],
                "user": {"login": "random-user"},
            },
        ]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[issues, []],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_agents(self):
        """Stats are tracked per agent role."""
        issues = [
            {
                "assignees": [{"login": "fishbowl-engineer[bot]"}],
                "user": {"login": "fishbowl-engineer[bot]"},
            },
        ]
        prs = [
            {"user": {"login": "fishbowl-reviewer[bot]"}},
        ]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[issues, prs],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["issues_closed"] == 1
        assert result["reviewer"]["prs_merged"] == 1

    @pytest.mark.asyncio
    async def test_initializes_all_stat_fields(self):
        """Each agent entry has all six stat fields initialized."""
        prs = [{"user": {"login": "fishbowl-engineer[bot]"}}]

        with patch(
            "api.services.goals_metrics._search_items",
            new_callable=AsyncMock,
            side_effect=[[], prs],
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        expected_keys = {
            "issues_opened",
            "issues_closed",
            "prs_opened",
            "prs_merged",
            "reviews",
            "commits",
        }
        assert set(result["engineer"].keys()) == expected_keys


class TestGetMetrics:
    """Tests for get_metrics()."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        cache = TTLCache(ttl=300, max_size=10)
        fake_metrics = {"open_issues": 5}
        cache.set("metrics", fake_metrics)

        result = await get_metrics(cache)
        assert result == fake_metrics

    @pytest.mark.asyncio
    async def test_computes_from_api(self, mock_settings):
        """Fetches data via Search API and computes metrics."""
        windowed = {
            "issues_closed": {"24h": 1, "7d": 5, "30d": 10},
            "prs_merged": {"24h": 0, "7d": 3, "30d": 8},
            "commits": {"24h": 2, "7d": 12, "30d": 40},
        }
        agent_stats = {"engineer": {"issues_closed": 3, "prs_merged": 2}}

        with (
            patch(
                "api.services.goals_metrics._search_count",
                new_callable=AsyncMock,
                side_effect=[7, 2],  # open_issues, open_prs
            ),
            patch(
                "api.services.goals_metrics._fetch_windowed_counts",
                new_callable=AsyncMock,
                return_value=windowed,
            ),
            patch(
                "api.services.goals_metrics._fetch_agent_stats",
                new_callable=AsyncMock,
                return_value=agent_stats,
            ),
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_metrics(cache)

        assert result["open_issues"] == 7
        assert result["open_prs"] == 2
        assert result["issues_closed"]["7d"] == 5
        assert result["prs_merged"]["30d"] == 8
        assert result["commits"]["24h"] == 2
        assert result["by_agent"] == agent_stats

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_metrics(self, mock_settings):
        """HTTP errors produce empty metrics (graceful degradation)."""
        with patch(
            "api.services.goals_metrics._search_count",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPError("connection failed"),
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_metrics(cache)

        assert result["open_issues"] == 0
        assert result["open_prs"] == 0

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings):
        """Computed metrics are stored in cache."""
        windowed = {
            "issues_closed": {"24h": 0, "7d": 0, "30d": 0},
            "prs_merged": {"24h": 0, "7d": 0, "30d": 0},
            "commits": {"24h": 0, "7d": 0, "30d": 0},
        }

        with (
            patch(
                "api.services.goals_metrics._search_count",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "api.services.goals_metrics._fetch_windowed_counts",
                new_callable=AsyncMock,
                return_value=windowed,
            ),
            patch(
                "api.services.goals_metrics._fetch_agent_stats",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            cache = TTLCache(ttl=300, max_size=10)
            await get_metrics(cache)

        cached = cache.get("metrics")
        assert cached is not None
        assert "open_issues" in cached
