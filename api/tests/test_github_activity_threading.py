"""Tests for GitHub activity threading — event grouping and PR title backfill."""

import pytest

from api.services.github_activity_threading import group_events_into_threads


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
    """Tests for group_events_into_threads()."""

    def test_empty_input(self):
        result = group_events_into_threads([])
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
        result = group_events_into_threads(events)

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
        result = group_events_into_threads(events)

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
        result = group_events_into_threads(events)

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
        result = group_events_into_threads(events)

        assert len(result) == 2
        # Standalone push (12:00) is more recent than thread (latest event=10:00)
        assert result[0]["type"] == "standalone"
        assert result[1]["type"] == "thread"
        assert result[1]["subject_number"] == 42
        assert len(result[1]["events"]) == 2

    def test_threads_all_label_events(self):
        """Label dedup happens in parse_events, so threading keeps all events."""
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
                timestamp="2026-01-15T10:02:00Z",
                subject_type="issue",
                subject_number=42,
                subject_title="Test",
                description="type/bug",
            ),
        ]
        result = group_events_into_threads(events)

        assert len(result) == 1
        thread = result[0]
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
        result = group_events_into_threads(events)

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
        result = group_events_into_threads(events)

        # The thread picks title from the first event with one
        # (first in input order, which has empty title, so falls back)
        thread = result[0]
        assert thread["subject_title"] == "The real title"


class TestBackfillPrTitles:
    """Tests for backfill_pr_titles() — fetching missing PR titles."""

    @pytest.mark.asyncio
    async def test_backfills_missing_pr_titles(self, mock_settings, monkeypatch):
        """Events with empty subject_title get backfilled from the PR API."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity_threading import backfill_pr_titles

        events = [
            _make_activity_event(
                "pr_merged",
                subject_type="pr",
                subject_number=177,
                subject_title="",
                description="Merged PR #177: ",
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Remove orphaned avatars"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        await backfill_pr_titles(events)

        assert events[0]["subject_title"] == "Remove orphaned avatars"
        assert events[0]["description"] == "Merged PR #177: Remove orphaned avatars"

    @pytest.mark.asyncio
    async def test_skips_events_with_titles(self, mock_settings, monkeypatch):
        """Events that already have titles are not fetched."""
        from unittest.mock import AsyncMock

        from api.services.github_activity_threading import backfill_pr_titles

        events = [
            _make_activity_event(
                "pr_opened",
                subject_type="pr",
                subject_number=10,
                subject_title="Already has title",
                description="Opened PR #10: Already has title",
            ),
        ]

        mock_client = AsyncMock()
        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        await backfill_pr_titles(events)

        # No API call should have been made
        mock_client.get.assert_not_called()
        assert events[0]["subject_title"] == "Already has title"

    @pytest.mark.asyncio
    async def test_handles_api_failure_gracefully(self, mock_settings, monkeypatch):
        """If the PR API returns an error, the event stays unchanged."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity_threading import backfill_pr_titles

        events = [
            _make_activity_event(
                "pr_reviewed",
                subject_type="pr",
                subject_number=999,
                subject_title="",
                description="Approved PR #999: ",
            ),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        monkeypatch.setattr(
            "api.services.http_client.get_shared_client", lambda: mock_client
        )

        await backfill_pr_titles(events)

        # Should remain empty — no crash
        assert events[0]["subject_title"] == ""
