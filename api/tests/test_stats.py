"""Tests for stats service — team statistics, PR cycle time, agent role mapping."""

import pytest

from api.services.stats import _agent_role, _compute_pr_cycle_hours, get_team_stats


class TestAgentRole:
    """Tests for _agent_role()."""

    def test_known_login(self):
        assert _agent_role("fishbowl-engineer[bot]") == "engineer"
        assert _agent_role("fishbowl-reviewer[bot]") == "reviewer"
        assert _agent_role("fishbowl-product-owner[bot]") == "product-owner"

    def test_unknown_login(self):
        assert _agent_role("some-random-user") is None

    def test_empty_string(self):
        assert _agent_role("") is None


class TestComputePrCycleHours:
    """Tests for _compute_pr_cycle_hours()."""

    def test_valid_dates(self):
        pr = {
            "created_at": "2026-01-15T10:00:00Z",
            "closed_at": "2026-01-15T12:30:00Z",
        }
        result = _compute_pr_cycle_hours(pr)
        assert result == 2.5

    def test_missing_created_at(self):
        pr = {"closed_at": "2026-01-15T12:00:00Z"}
        assert _compute_pr_cycle_hours(pr) is None

    def test_missing_closed_at(self):
        pr = {"created_at": "2026-01-15T10:00:00Z"}
        assert _compute_pr_cycle_hours(pr) is None

    def test_both_missing(self):
        assert _compute_pr_cycle_hours({}) is None

    def test_malformed_date(self):
        pr = {"created_at": "not-a-date", "closed_at": "2026-01-15T12:00:00Z"}
        assert _compute_pr_cycle_hours(pr) is None

    def test_none_values(self):
        pr = {"created_at": None, "closed_at": None}
        assert _compute_pr_cycle_hours(pr) is None


class TestGetTeamStats:
    """Tests for get_team_stats()."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        """Cache hit returns stored stats without API call."""
        from api.services.stats import _cache

        fake_stats = {"issues_closed": 5, "prs_merged": 3}
        _cache.set("team_stats", fake_stats)

        result = await get_team_stats()
        assert result == fake_stats

    @pytest.mark.asyncio
    async def test_computes_stats_from_api(self, mock_settings, monkeypatch):
        """Fetches issues and PRs from API, computes aggregates."""
        issues_items = [
            {
                "user": {"login": "fishbowl-product-owner[bot]"},
                "assignees": [{"login": "fishbowl-engineer[bot]"}],
            },
            {
                "user": {"login": "fishbowl-product-owner[bot]"},
                "assignees": [{"login": "fishbowl-engineer[bot]"}],
            },
        ]
        prs_items = [
            {
                "user": {"login": "fishbowl-engineer[bot]"},
                "created_at": "2026-01-15T10:00:00Z",
                "closed_at": "2026-01-15T12:00:00Z",
            },
        ]

        async def mock_fetch_closed_issues(repo, since):
            return issues_items

        async def mock_fetch_merged_prs(repo, since):
            return prs_items

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()

        assert result["issues_closed"] == 2
        assert result["prs_merged"] == 1
        assert result["avg_pr_cycle_hours"] == 2.0
        assert "agents" in result
        assert "period_start" in result
        assert "period_end" in result

        # Engineer should have 2 issues closed + 1 PR merged
        engineer = next(a for a in result["agents"] if a["role"] == "engineer")
        assert engineer["issues_closed"] == 2
        assert engineer["prs_merged"] == 1

    @pytest.mark.asyncio
    async def test_empty_data(self, mock_settings, monkeypatch):
        """Empty API responses produce zero counts and no agents."""

        async def mock_fetch_closed_issues(repo, since):
            return []

        async def mock_fetch_merged_prs(repo, since):
            return []

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()

        assert result["issues_closed"] == 0
        assert result["prs_merged"] == 0
        assert result["avg_pr_cycle_hours"] is None
        assert result["agents"] == []

    @pytest.mark.asyncio
    async def test_pr_without_cycle_time(self, mock_settings, monkeypatch):
        """PRs with missing dates don't break average calculation."""

        async def mock_fetch_closed_issues(repo, since):
            return []

        async def mock_fetch_merged_prs(repo, since):
            return [
                {
                    "user": {"login": "fishbowl-engineer[bot]"},
                    "created_at": "2026-01-15T10:00:00Z",
                    # No closed_at
                },
            ]

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()
        assert result["prs_merged"] == 1
        assert result["avg_pr_cycle_hours"] is None

    @pytest.mark.asyncio
    async def test_non_agent_users_excluded_from_agents_list(
        self, mock_settings, monkeypatch
    ):
        """Activity from non-agent users doesn't appear in agents list."""

        async def mock_fetch_closed_issues(repo, since):
            return [
                {
                    "user": {"login": "random-human"},
                    "assignees": [{"login": "random-human"}],
                },
            ]

        async def mock_fetch_merged_prs(repo, since):
            return []

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()
        assert result["issues_closed"] == 1
        assert result["agents"] == []

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings, monkeypatch):
        """Computed result is stored in cache."""
        from api.services.stats import _cache

        async def mock_fetch_closed_issues(repo, since):
            return []

        async def mock_fetch_merged_prs(repo, since):
            return []

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        await get_team_stats()

        cached = _cache.get("team_stats")
        assert cached is not None
        assert cached["issues_closed"] == 0

    @pytest.mark.asyncio
    async def test_partial_failure_preserves_stale_pr_data(
        self, mock_settings, monkeypatch
    ):
        """When fetch_merged_prs fails but stale cache exists, use stale prs_merged."""
        from api.services.stats import _cache

        # Seed stale cache with known good data
        stale_stats = {
            "issues_closed": 10,
            "prs_merged": 127,
            "avg_pr_cycle_hours": 1.5,
            "agents": [
                {"role": "engineer", "issues_closed": 5, "prs_merged": 96},
            ],
            "period_start": "2026-02-14T00:00:00+00:00",
            "period_end": "2026-02-21T00:00:00+00:00",
        }
        _cache.set("team_stats", stale_stats)
        # Expire the cache entry so get() returns None but get_stale() works
        _cache._store["team_stats"] = (stale_stats, 0)

        # Issues succeed, PRs fail (returns None = API error)
        async def mock_fetch_closed_issues(repo, since):
            return [
                {
                    "user": {"login": "fishbowl-product-owner[bot]"},
                    "assignees": [{"login": "fishbowl-engineer[bot]"}],
                },
            ]

        async def mock_fetch_merged_prs(repo, since):
            return None  # API failure

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()

        # Should use fresh issue count but preserve stale PR data
        assert result["issues_closed"] == 1
        assert result["prs_merged"] == 127, (
            "Stale prs_merged should be preserved on partial API failure"
        )

    @pytest.mark.asyncio
    async def test_partial_failure_issues_preserves_stale_issue_data(
        self, mock_settings, monkeypatch
    ):
        """Stale issues_closed preserved when fetch_closed_issues fails."""
        from api.services.stats import _cache

        stale_stats = {
            "issues_closed": 10,
            "prs_merged": 5,
            "avg_pr_cycle_hours": 2.0,
            "agents": [],
            "period_start": "2026-02-14T00:00:00+00:00",
            "period_end": "2026-02-21T00:00:00+00:00",
        }
        _cache.set("team_stats", stale_stats)
        _cache._store["team_stats"] = (stale_stats, 0)

        async def mock_fetch_closed_issues(repo, since):
            return None  # API failure

        async def mock_fetch_merged_prs(repo, since):
            return [
                {
                    "user": {"login": "fishbowl-engineer[bot]"},
                    "created_at": "2026-01-15T10:00:00Z",
                    "closed_at": "2026-01-15T12:00:00Z",
                },
            ]

        monkeypatch.setattr(
            "api.services.stats.fetch_closed_issues", mock_fetch_closed_issues
        )
        monkeypatch.setattr(
            "api.services.stats.fetch_merged_prs", mock_fetch_merged_prs
        )

        result = await get_team_stats()

        # Should use stale issue count but fresh PR data
        assert result["issues_closed"] == 10, (
            "Stale issues_closed should be preserved on partial API failure"
        )
        assert result["prs_merged"] == 1
