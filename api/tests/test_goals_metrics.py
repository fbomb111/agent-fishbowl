"""Tests for goals_metrics service — Search API counts, commit counting, agent stats."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.services.cache import TTLCache
from api.services.goals_metrics import (
    _agent_role,
    _count_commits,
    _enforce_monotonic,
    _fetch_agent_stats,
    _fetch_commits_by_agent,
    _fetch_review_counts,
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
    async def test_returns_total_count(self):
        with patch(
            "api.services.goals_metrics_queries.github_api_get",
            new_callable=AsyncMock,
            return_value={"total_count": 42, "items": []},
        ):
            result = await _search_count("repo:test is:issue is:open")
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        with patch(
            "api.services.goals_metrics_queries.github_api_get",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _search_count("repo:test is:issue is:open")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_zero_when_total_count_missing(self):
        with patch(
            "api.services.goals_metrics_queries.github_api_get",
            new_callable=AsyncMock,
            return_value={"items": []},
        ):
            result = await _search_count("repo:test is:issue is:open")
        assert result == 0


class TestCountCommits:
    """Tests for _count_commits()."""

    @pytest.mark.asyncio
    async def test_uses_link_header(self, monkeypatch):
        """Parses last page number from Link header for total count."""
        link = (
            "<https://api.github.com/repos/test/commits"
            "?since=2026-01-01&per_page=1&page=37>; "
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
    async def test_returns_none_on_non_200(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _count_commits("test/repo", "2026-01-01T00:00:00Z")
        assert result is None


class TestEnforceMonotonic:
    """Tests for _enforce_monotonic()."""

    def test_all_valid_ascending(self):
        assert _enforce_monotonic([3, 10, 25]) == [3, 10, 25]

    def test_all_none(self):
        assert _enforce_monotonic([None, None, None]) == [0, 0, 0]

    def test_7d_none_fills_from_24h(self):
        """When 7d fails, it should be at least 24h."""
        assert _enforce_monotonic([10, None, 50]) == [10, 10, 50]

    def test_24h_none_fills_with_zero(self):
        assert _enforce_monotonic([None, 20, 50]) == [0, 20, 50]

    def test_30d_none_fills_from_7d(self):
        assert _enforce_monotonic([5, 20, None]) == [5, 20, 20]

    def test_clamps_7d_up_to_24h(self):
        """Even with real data, 7d can't be less than 24h."""
        assert _enforce_monotonic([67, 0, 112]) == [67, 67, 112]

    def test_clamps_30d_up_to_7d(self):
        assert _enforce_monotonic([5, 20, 10]) == [5, 20, 20]

    def test_only_24h_available(self):
        assert _enforce_monotonic([42, None, None]) == [42, 42, 42]

    def test_only_30d_available(self):
        assert _enforce_monotonic([None, None, 100]) == [0, 100, 100]


class TestFetchWindowedCounts:
    """Tests for _fetch_windowed_counts()."""

    @pytest.mark.asyncio
    async def test_returns_all_windows(self):
        """All three windows and three metrics are returned."""
        now = datetime.now(timezone.utc)

        # Merged PRs with timestamps spanning multiple windows
        merged_prs = [
            {"merged_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")},  # within 24h
        ]

        with (
            patch(
                "api.services.goals_metrics_windows._search_count",
                new_callable=AsyncMock,
                side_effect=[3, 10, 25],  # issues_closed: 24h, 7d, 30d
            ),
            patch(
                "api.services.goals_metrics_windows._count_commits",
                new_callable=AsyncMock,
                side_effect=[3, 8, 25],  # commits: 24h, 7d, 30d
            ),
            patch(
                "api.services.goals_metrics_windows.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=merged_prs,
            ),
        ):
            result = await _fetch_windowed_counts("test/repo", now)

        assert result["issues_closed"]["24h"] == 3
        assert result["issues_closed"]["7d"] == 10
        assert result["issues_closed"]["30d"] == 25
        assert result["prs_merged"]["24h"] == 1
        assert result["prs_merged"]["7d"] == 1
        assert result["prs_merged"]["30d"] == 1
        assert result["commits"]["24h"] == 3
        assert result["commits"]["7d"] == 8
        assert result["commits"]["30d"] == 25

    @pytest.mark.asyncio
    async def test_returns_all_windows_directly(self):
        """Verify correct index mapping by mocking at asyncio.gather level."""
        now = datetime.now(timezone.utc)

        # The function creates 7 tasks via asyncio.gather:
        # [0]: fetch_merged_prs (list of PRs)
        # [1..3]: _search_count for issues_closed (24h, 7d, 30d)
        # [4..6]: _count_commits (24h, 7d, 30d)
        mock_results = [[], 2, 5, 10, 3, 8, 20]

        with patch(
            "api.services.goals_metrics_windows.asyncio.gather",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            result = await _fetch_windowed_counts("test/repo", now)

        assert result["issues_closed"] == {"24h": 2, "7d": 5, "30d": 10}
        assert result["prs_merged"] == {"24h": 0, "7d": 0, "30d": 0}
        assert result["commits"] == {"24h": 3, "7d": 8, "30d": 20}


class TestFetchReviewCounts:
    """Tests for _fetch_review_counts()."""

    @pytest.mark.asyncio
    async def test_counts_reviews_by_agent(self, monkeypatch):
        """Reviews are counted per agent role within the time window."""
        prs_response = [{"number": 10}]
        reviews_response = [
            {
                "user": {"login": "fishbowl-reviewer[bot]"},
                "submitted_at": "2026-01-05T12:00:00Z",
            },
            {
                "user": {"login": "fishbowl-reviewer[bot]"},
                "submitted_at": "2026-01-06T12:00:00Z",
            },
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/pulls" in url and "/reviews" in url:
                return httpx.Response(200, json=reviews_response)
            if "/pulls" in url:
                # Return PRs only for "open" state, empty for "closed"
                params = kwargs.get("params", {})
                if params.get("state") == "open":
                    return httpx.Response(200, json=prs_response)
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_review_counts("test/repo", "2026-01-01")
        assert result["reviewer"] == 2

    @pytest.mark.asyncio
    async def test_filters_by_date(self, monkeypatch):
        """Reviews before the since date are excluded."""
        prs_response = [{"number": 10, "updated_at": "2026-01-10T00:00:00Z"}]
        reviews_response = [
            {
                "user": {"login": "fishbowl-reviewer[bot]"},
                "submitted_at": "2025-12-25T12:00:00Z",
            },
            {
                "user": {"login": "fishbowl-reviewer[bot]"},
                "submitted_at": "2026-01-05T12:00:00Z",
            },
        ]

        async def mock_get(self, url, **kwargs):
            if "/pulls" in url and "/reviews" in url:
                return httpx.Response(200, json=reviews_response)
            if "/pulls" in url:
                params = kwargs.get("params", {})
                if params.get("state") == "open":
                    return httpx.Response(200, json=prs_response)
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_review_counts("test/repo", "2026-01-01")
        assert result["reviewer"] == 1

    @pytest.mark.asyncio
    async def test_skips_unknown_reviewers(self, monkeypatch):
        """Reviews from non-agent users are not counted."""
        prs_response = [{"number": 10, "updated_at": "2026-01-10T00:00:00Z"}]
        reviews_response = [
            {
                "user": {"login": "random-user"},
                "submitted_at": "2026-01-05T12:00:00Z",
            },
        ]

        async def mock_get(self, url, **kwargs):
            if "/pulls" in url and "/reviews" in url:
                return httpx.Response(200, json=reviews_response)
            if "/pulls" in url:
                params = kwargs.get("params", {})
                if params.get("state") == "open":
                    return httpx.Response(200, json=prs_response)
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_review_counts("test/repo", "2026-01-01")
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_when_no_prs(self, monkeypatch):
        """Returns empty dict when no PRs found."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_review_counts("test/repo", "2026-01-01")
        assert result == {}


class TestFetchCommitsByAgent:
    """Tests for _fetch_commits_by_agent()."""

    @pytest.mark.asyncio
    async def test_counts_commits_per_agent(self, monkeypatch):
        """Commits are attributed to agent roles by author login."""
        commits = [
            {"author": {"login": "fishbowl-engineer[bot]"}},
            {"author": {"login": "fishbowl-engineer[bot]"}},
            {"author": {"login": "fishbowl-reviewer[bot]"}},
            {"author": {"login": "fbomb111"}},
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=commits)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_commits_by_agent("test/repo", "2026-01-01")
        assert result["engineer"] == 2
        assert result["reviewer"] == 1
        assert result["human"] == 1

    @pytest.mark.asyncio
    async def test_skips_unknown_authors(self, monkeypatch):
        """Commits from unknown authors are not counted."""
        commits = [
            {"author": {"login": "random-user"}},
            {"author": None},
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=commits)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_commits_by_agent("test/repo", "2026-01-01")
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_when_no_commits(self, monkeypatch):
        """Returns empty dict when no commits found."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_commits_by_agent("test/repo", "2026-01-01")
        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_api_errors(self, monkeypatch):
        """API errors return empty counts."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_commits_by_agent("test/repo", "2026-01-01")
        assert result == {}

    @pytest.mark.asyncio
    async def test_paginates_commits(self, monkeypatch):
        """Fetches multiple pages of commits."""
        page1 = [{"author": {"login": "fishbowl-engineer[bot]"}}] * 100
        page2 = [{"author": {"login": "fishbowl-engineer[bot]"}}] * 20

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            return httpx.Response(200, json=page2)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_commits_by_agent("test/repo", "2026-01-01")
        assert result["engineer"] == 120


class TestFetchAgentStats:
    """Tests for _fetch_agent_stats()."""

    @pytest.mark.asyncio
    async def test_counts_issues_closed_by_assignee(self):
        """Closed issues are attributed to the first assignee's agent role."""
        closed_issues = [
            {
                "assignees": [{"login": "fishbowl-product-owner[bot]"}],
                "user": {"login": "fishbowl-triage[bot]"},
            },
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[closed_issues, [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["product-owner"]["issues_closed"] == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_user_login(self):
        """When no assignee, falls back to issue creator."""
        closed_issues = [
            {
                "assignees": [],
                "user": {"login": "fishbowl-engineer[bot]"},
            },
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[closed_issues, [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["issues_closed"] == 1

    @pytest.mark.asyncio
    async def test_counts_issues_opened_by_creator(self):
        """Opened issues are attributed to the issue creator."""
        opened_issues = [
            {"user": {"login": "fishbowl-tech-lead[bot]"}},
            {"user": {"login": "fishbowl-tech-lead[bot]"}},
            {"user": {"login": "fishbowl-triage[bot]"}},
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], opened_issues, []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["tech-lead"]["issues_opened"] == 2
        assert result["triage"]["issues_opened"] == 1

    @pytest.mark.asyncio
    async def test_counts_prs_opened_by_author(self):
        """Opened PRs are attributed to the PR author."""
        prs_opened = [
            {"user": {"login": "fishbowl-engineer[bot]"}},
            {"user": {"login": "fishbowl-engineer[bot]"}},
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], [], prs_opened],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["prs_opened"] == 2

    @pytest.mark.asyncio
    async def test_counts_prs_merged_by_author(self):
        """Merged PRs are attributed to the PR author's agent role."""
        prs = [
            {"user": {"login": "fishbowl-engineer[bot]"}},
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=prs,
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["prs_merged"] == 1

    @pytest.mark.asyncio
    async def test_skips_unknown_logins(self):
        """Items from unknown logins are ignored."""
        closed_issues = [
            {
                "assignees": [{"login": "random-user"}],
                "user": {"login": "random-user"},
            },
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[closed_issues, [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_agents(self):
        """Stats are tracked per agent role."""
        closed_issues = [
            {
                "assignees": [{"login": "fishbowl-engineer[bot]"}],
                "user": {"login": "fishbowl-engineer[bot]"},
            },
        ]
        prs = [
            {"user": {"login": "fishbowl-engineer[bot]"}},
        ]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[closed_issues, [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=prs,
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={"reviewer": 5},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["issues_closed"] == 1
        assert result["engineer"]["prs_merged"] == 1
        assert result["reviewer"]["reviews"] == 5

    @pytest.mark.asyncio
    async def test_initializes_all_stat_fields(self):
        """Each agent entry has all six stat fields initialized."""
        prs = [{"user": {"login": "fishbowl-engineer[bot]"}}]

        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=prs,
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
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

    @pytest.mark.asyncio
    async def test_review_counts_merged_into_stats(self):
        """Review counts from _fetch_review_counts are merged into agent stats."""
        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={"reviewer": 12, "human": 3},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["reviewer"]["reviews"] == 12
        assert result["human"]["reviews"] == 3
        assert result["reviewer"]["issues_closed"] == 0

    @pytest.mark.asyncio
    async def test_commit_counts_merged_into_stats(self):
        """Commit counts from _fetch_commits_by_agent are merged into agent stats."""
        with (
            patch(
                "api.services.goals_metrics_agents._search_items",
                new_callable=AsyncMock,
                side_effect=[[], [], []],
            ),
            patch(
                "api.services.goals_metrics_agents.fetch_merged_prs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_review_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "api.services.goals_metrics_agents._fetch_commits_by_agent",
                new_callable=AsyncMock,
                return_value={"engineer": 42, "reviewer": 3},
            ),
        ):
            result = await _fetch_agent_stats("test/repo", "2026-01-01")

        assert result["engineer"]["commits"] == 42
        assert result["reviewer"]["commits"] == 3


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
