"""Tests for goals_metrics service — timestamp parsing, event bucketing, metrics aggregation."""

import time

import httpx
import pytest

from api.services.cache import TTLCache
from api.services.goals_metrics import (
    _bucket_event,
    _parse_event_timestamp,
    _process_events,
    get_metrics,
)


class TestParseEventTimestamp:
    """Tests for _parse_event_timestamp()."""

    def test_valid_iso_timestamp(self):
        event = {"created_at": "2026-01-15T10:00:00Z"}
        ts = _parse_event_timestamp(event)
        assert ts > 0

    def test_valid_iso_with_offset(self):
        event = {"created_at": "2026-01-15T10:00:00+00:00"}
        ts = _parse_event_timestamp(event)
        assert ts > 0

    def test_empty_string(self):
        event = {"created_at": ""}
        assert _parse_event_timestamp(event) == 0.0

    def test_missing_key(self):
        assert _parse_event_timestamp({}) == 0.0

    def test_malformed_string(self):
        event = {"created_at": "not-a-date"}
        assert _parse_event_timestamp(event) == 0.0

    def test_none_value(self):
        event = {"created_at": None}
        assert _parse_event_timestamp(event) == 0.0

    def test_z_suffix_replaced(self):
        """Z suffix is handled correctly via replace("Z", "+00:00")."""
        event_z = {"created_at": "2026-01-15T10:00:00Z"}
        event_offset = {"created_at": "2026-01-15T10:00:00+00:00"}
        assert _parse_event_timestamp(event_z) == _parse_event_timestamp(event_offset)


class TestBucketEvent:
    """Tests for _bucket_event()."""

    def test_within_24h(self):
        now = time.time()
        event_ts = now - 3600  # 1 hour ago
        assert _bucket_event(event_ts, now) == "24h"

    def test_within_7d(self):
        now = time.time()
        event_ts = now - 172800  # 2 days ago
        assert _bucket_event(event_ts, now) == "7d"

    def test_within_30d(self):
        now = time.time()
        event_ts = now - 1209600  # 14 days ago
        assert _bucket_event(event_ts, now) == "30d"

    def test_older_than_30d(self):
        now = time.time()
        event_ts = now - 3000000  # ~35 days ago
        assert _bucket_event(event_ts, now) is None

    def test_exactly_24h_boundary(self):
        now = time.time()
        event_ts = now - 86400  # exactly 24h
        assert _bucket_event(event_ts, now) == "24h"

    def test_just_over_24h(self):
        now = time.time()
        event_ts = now - 86401  # 24h + 1s
        assert _bucket_event(event_ts, now) == "7d"

    def test_zero_age(self):
        now = time.time()
        assert _bucket_event(now, now) == "24h"


class TestProcessEvents:
    """Tests for _process_events()."""

    def test_issues_closed(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-po[bot]"},
                "type": "IssuesEvent",
                "payload": {"action": "closed"},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        windowed, agent_stats = _process_events(events, now)
        assert agent_stats["po"]["issues_closed"] == 1

    def test_issues_opened(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-po[bot]"},
                "type": "IssuesEvent",
                "payload": {"action": "opened"},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["po"]["issues_opened"] == 1

    def test_pr_merged(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-reviewer[bot]"},
                "type": "PullRequestEvent",
                "payload": {
                    "action": "closed",
                    "pull_request": {"merged": True},
                },
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["reviewer"]["prs_merged"] == 1

    def test_pr_closed_not_merged(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "PullRequestEvent",
                "payload": {
                    "action": "closed",
                    "pull_request": {"merged": False},
                },
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["engineer"]["prs_merged"] == 0

    def test_pr_opened(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "PullRequestEvent",
                "payload": {"action": "opened", "pull_request": {}},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["engineer"]["prs_opened"] == 1

    def test_review_event(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-reviewer[bot]"},
                "type": "PullRequestReviewEvent",
                "payload": {},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["reviewer"]["reviews"] == 1

    def test_push_event_counts_commits(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "PushEvent",
                "payload": {"commits": [{}, {}, {}]},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats["engineer"]["commits"] == 3

    def test_org_events_skipped(self):
        now = time.time()
        events = [
            {
                "actor": {"login": "YourMoveLabs"},
                "type": "PushEvent",
                "payload": {"commits": [{}]},
                "created_at": "2026-01-15T10:00:00Z",
            }
        ]
        _, agent_stats = _process_events(events, now)
        assert agent_stats == {}

    def test_windowed_counts_recent_event(self):
        """Recent event within 24h appears in the 24h window."""
        now = time.time()
        from datetime import datetime, timezone

        recent_ts = datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat()
        events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "PushEvent",
                "payload": {"commits": [{}, {}]},
                "created_at": recent_ts,
            }
        ]
        windowed, _ = _process_events(events, now)
        assert windowed["commits"]["24h"] == 2

    def test_empty_events(self):
        now = time.time()
        windowed, agent_stats = _process_events([], now)
        assert agent_stats == {}
        assert windowed["issues_closed"] == {"24h": 0, "7d": 0, "30d": 0}

    def test_multiple_agents(self):
        now = time.time()
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(now - 100, tz=timezone.utc).isoformat()
        events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "IssuesEvent",
                "payload": {"action": "closed"},
                "created_at": ts,
            },
            {
                "actor": {"login": "fishbowl-po[bot]"},
                "type": "IssuesEvent",
                "payload": {"action": "opened"},
                "created_at": ts,
            },
        ]
        windowed, agent_stats = _process_events(events, now)
        assert "engineer" in agent_stats
        assert "po" in agent_stats
        assert windowed["issues_closed"]["24h"] == 1


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
    async def test_computes_from_api(self, mock_settings, monkeypatch):
        """Fetches data and computes metrics."""
        from datetime import datetime, timezone

        now = time.time()
        recent_ts = datetime.fromtimestamp(now - 100, tz=timezone.utc).isoformat()

        mock_issues = [
            {"id": 1, "title": "Issue 1"},
            {"id": 2, "title": "Issue 2", "pull_request": {}},
        ]
        mock_prs = [{"id": 10}]
        mock_events = [
            {
                "actor": {"login": "fishbowl-engineer[bot]"},
                "type": "PushEvent",
                "payload": {"commits": [{}]},
                "created_at": recent_ts,
            }
        ]

        responses = iter(
            [
                httpx.Response(200, json=mock_issues),
                httpx.Response(200, json=mock_prs),
                httpx.Response(200, json=mock_events),
            ]
        )

        async def mock_get(self, url, **kwargs):
            return next(responses)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_metrics(cache)

        # 1 issue without pull_request key
        assert result["open_issues"] == 1
        assert result["open_prs"] == 1
        assert "by_agent" in result
        assert "engineer" in result["by_agent"]

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_metrics(self, mock_settings, monkeypatch):
        """HTTP errors produce empty metrics (graceful degradation)."""

        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_metrics(cache)

        assert result["open_issues"] == 0
        assert result["open_prs"] == 0

    @pytest.mark.asyncio
    async def test_non_200_responses_degrade_gracefully(
        self, mock_settings, monkeypatch
    ):
        """Non-200 status codes return empty lists, not crashes."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_metrics(cache)

        assert result["open_issues"] == 0
        assert result["open_prs"] == 0

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings, monkeypatch):
        """Computed metrics are stored in cache."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        cache = TTLCache(ttl=300, max_size=10)
        await get_metrics(cache)

        cached = cache.get("metrics")
        assert cached is not None
        assert "open_issues" in cached
