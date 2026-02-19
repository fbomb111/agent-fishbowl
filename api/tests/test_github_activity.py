"""Tests for GitHub activity feed — threading, caching, and event grouping."""

import pytest

from api.services.github_activity import _group_events_into_threads


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


class TestGroupEventsIntoThreads:
    """Tests for _group_events_into_threads()."""

    def test_empty_input(self):
        result = _group_events_into_threads([])
        assert result == []

    def test_single_thread(self):
        events = [
            _make_activity_event(
                "issue_created",
                timestamp="2026-01-15T10:00:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Fix the bug",
            ),
            _make_activity_event(
                "issue_comment",
                timestamp="2026-01-15T11:00:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Fix the bug",
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 1
        thread = result[0]
        assert thread["type"] == "thread"
        assert thread["subject_type"] == "issue"
        assert thread["subject_number"] == 42
        assert thread["subject_title"] == "Fix the bug"
        assert len(thread["events"]) == 2
        # Events sorted oldest first within thread
        assert thread["events"][0]["timestamp"] == "2026-01-15T10:00:00Z"
        assert thread["events"][1]["timestamp"] == "2026-01-15T11:00:00Z"
        # latest_timestamp reflects most recent event
        assert thread["latest_timestamp"] == "2026-01-15T11:00:00Z"

    def test_multiple_threads_sorted_by_recency(self):
        events = [
            _make_activity_event(
                "issue_created",
                timestamp="2026-01-15T08:00:00Z",
                subject_type="issue",
                subject_number=10,
                subject_title="Old issue",
            ),
            _make_activity_event(
                "pr_opened",
                timestamp="2026-01-15T12:00:00Z",
                subject_type="pr",
                subject_number=20,
                subject_title="New PR",
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 2
        # Most recent thread first
        assert result[0]["subject_number"] == 20
        assert result[1]["subject_number"] == 10

    def test_standalone_events(self):
        events = [
            _make_activity_event(
                "push",
                timestamp="2026-01-15T10:00:00Z",
                # No subject_type/subject_number -> standalone
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 1
        assert result[0]["type"] == "standalone"
        assert result[0]["event"]["type"] == "push"

    def test_mixed_threads_and_standalone(self):
        events = [
            _make_activity_event(
                "issue_created",
                timestamp="2026-01-15T10:00:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Bug fix",
            ),
            _make_activity_event(
                "push",
                timestamp="2026-01-15T12:00:00Z",
            ),
            _make_activity_event(
                "issue_comment",
                timestamp="2026-01-15T09:00:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Bug fix",
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 2
        # Standalone push (12:00) is more recent than thread (latest event=10:00)
        assert result[0]["type"] == "standalone"
        assert result[1]["type"] == "thread"
        assert result[1]["subject_number"] == 42
        assert len(result[1]["events"]) == 2

    def test_deduplicates_label_events(self):
        events = [
            _make_activity_event(
                "issue_labeled",
                timestamp="2026-01-15T10:00:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Test",
                description="priority/high",
            ),
            _make_activity_event(
                "issue_labeled",
                timestamp="2026-01-15T10:01:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Test",
                description="priority/high",
            ),
            _make_activity_event(
                "issue_labeled",
                timestamp="2026-01-15T10:02:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Test",
                description="type/bug",
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 1
        thread = result[0]
        # Should keep one "priority/high" and one "type/bug"
        assert len(thread["events"]) == 2
        descriptions = [e["description"] for e in thread["events"]]
        assert "priority/high" in descriptions
        assert "type/bug" in descriptions

    def test_latest_timestamp_reflects_most_recent_event(self):
        events = [
            _make_activity_event(
                "issue_created",
                timestamp="2026-01-15T08:00:00Z",
                subject_type="issue",
                subject_number=1,
                subject_title="Old issue",
            ),
            _make_activity_event(
                "issue_comment",
                timestamp="2026-01-15T14:00:00Z",
                subject_type="issue",
                subject_number=1,
                subject_title="Old issue",
            ),
            _make_activity_event(
                "pr_opened",
                timestamp="2026-01-15T12:00:00Z",
                subject_type="pr",
                subject_number=5,
                subject_title="Newer PR",
            ),
        ]
        result = _group_events_into_threads(events)

        assert len(result) == 2
        # Issue thread has latest event at 14:00, PR at 12:00
        # So issue thread should sort first (most recent)
        assert result[0]["subject_number"] == 1
        assert result[0]["latest_timestamp"] == "2026-01-15T14:00:00Z"
        assert result[1]["subject_number"] == 5
        assert result[1]["latest_timestamp"] == "2026-01-15T12:00:00Z"

    def test_subject_title_from_earliest_event(self):
        events = [
            _make_activity_event(
                "issue_comment",
                timestamp="2026-01-15T10:00:00Z",
                subject_type="issue",
                subject_number=5,
                subject_title="",  # No title on first event
            ),
            _make_activity_event(
                "issue_created",
                timestamp="2026-01-15T09:00:00Z",
                subject_type="issue",
                subject_number=5,
                subject_title="The real title",
            ),
        ]
        result = _group_events_into_threads(events)

        # The thread picks title from the first event with one
        # (first in input order, which has empty title, so falls back)
        thread = result[0]
        assert thread["subject_title"] == "The real title"


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
    async def test_empty_response_not_cached(self, mock_settings, monkeypatch):
        """Empty API response is not stored in cache."""
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
