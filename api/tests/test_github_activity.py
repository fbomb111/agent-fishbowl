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
        result = _group_events_into_threads(events)

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


class TestBackfillPrTitles:
    """Tests for _backfill_pr_titles() — fetching missing PR titles."""

    @pytest.mark.asyncio
    async def test_backfills_missing_pr_titles(self, mock_settings, monkeypatch):
        """Events with empty subject_title get backfilled from the PR API."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity import _backfill_pr_titles

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

        await _backfill_pr_titles(events)

        assert events[0]["subject_title"] == "Remove orphaned avatars"
        assert events[0]["description"] == "Merged PR #177: Remove orphaned avatars"

    @pytest.mark.asyncio
    async def test_skips_events_with_titles(self, mock_settings, monkeypatch):
        """Events that already have titles are not fetched."""
        from unittest.mock import AsyncMock

        from api.services.github_activity import _backfill_pr_titles

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

        await _backfill_pr_titles(events)

        # No API call should have been made
        mock_client.get.assert_not_called()
        assert events[0]["subject_title"] == "Already has title"

    @pytest.mark.asyncio
    async def test_handles_api_failure_gracefully(self, mock_settings, monkeypatch):
        """If the PR API returns an error, the event stays unchanged."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity import _backfill_pr_titles

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

        await _backfill_pr_titles(events)

        # Should remain empty — no crash
        assert events[0]["subject_title"] == ""


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


class TestFallbackEvents:
    """Tests for _fetch_fallback_events() — Issues/PRs API fallback."""

    @pytest.mark.asyncio
    async def test_fallback_returns_issue_events(self, mock_settings, monkeypatch):
        """Fallback creates events from the Issues REST API."""
        from unittest.mock import AsyncMock

        from api.services.github_activity import _fetch_fallback_events

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
            "api.services.github_activity.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
            AsyncMock(return_value=issues_response),
        )

        result = await _fetch_fallback_events(limit=30)

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

        from api.services.github_activity import _fetch_fallback_events

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
            "api.services.github_activity.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
            AsyncMock(return_value=issues_response),
        )

        result = await _fetch_fallback_events(limit=30)

        assert len(result) == 1
        assert result[0]["type"] == "pr_merged"
        assert result[0]["subject_number"] == 100
        assert result[0]["subject_title"] == "Add new endpoint"

    @pytest.mark.asyncio
    async def test_fallback_skips_closed_unmerged_prs(self, mock_settings, monkeypatch):
        """Closed but not merged PRs are skipped in fallback."""
        from unittest.mock import AsyncMock, MagicMock

        from api.services.github_activity import _fetch_fallback_events

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

        result = await _fetch_fallback_events(limit=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_empty_when_no_repo(self, mock_settings, monkeypatch):
        """Fallback returns empty when github_repo is not configured."""
        from api.services.github_activity import _fetch_fallback_events

        mock_settings.github_repo = ""

        result = await _fetch_fallback_events(limit=30)
        assert result == []


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
            "api.services.github_activity.github_api_get",
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
            "api.services.github_activity.get_settings", lambda: mock_settings
        )
        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
            mock_github_api_get,
        )

        result = await _get_events_with_fallback(per_page=30)

        assert len(result) == 1
        assert result[0]["type"] == "issue_created"
        assert result[0]["description"] == "Opened issue #50: Fallback issue"


class TestFetchDeployEvents:
    """Tests for _fetch_deploy_events() — deploy workflow runs."""

    @pytest.mark.asyncio
    async def test_returns_deploy_events_from_workflow_runs(
        self, mock_settings, monkeypatch
    ):
        """Completed workflow runs are converted to deploy events."""
        from api.services.github_activity import _fetch_deploy_events

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

        from unittest.mock import AsyncMock

        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
            AsyncMock(return_value=workflow_response),
        )

        result = await _fetch_deploy_events()

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

        from api.services.github_activity import _fetch_deploy_events

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
            "api.services.github_activity.github_api_get",
            AsyncMock(return_value=workflow_response),
        )

        result = await _fetch_deploy_events()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_api_failure(self, mock_settings, monkeypatch):
        """API failure returns empty list, no crash."""
        from unittest.mock import AsyncMock

        from api.services.github_activity import _fetch_deploy_events

        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
            AsyncMock(return_value=None),
        )

        result = await _fetch_deploy_events()
        assert result == []

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
                            "actor": {"login": "github-actions[bot]", "avatar_url": ""},
                        }
                    ]
                }
            return None

        monkeypatch.setattr(
            "api.services.github_activity.github_api_get",
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
