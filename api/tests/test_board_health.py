"""Tests for board_health service — project board metrics."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.services.board_health import (
    _compute_board_health,
    _fetch_open_issue_numbers,
    _fetch_project_items,
    get_board_health,
)
from api.services.cache import TTLCache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the board health cache before each test."""
    import api.services.board_health as bh

    bh._cache = TTLCache(ttl=600, max_size=5)


@pytest.fixture
def mock_settings(monkeypatch):
    """Provide a mock Settings with github_repo set."""

    class FakeSettings:
        github_repo = "YourMoveLabs/agent-fishbowl"
        github_token = "fake-token"  # noqa: S105

    monkeypatch.setattr(
        "api.services.board_health.get_settings",
        lambda: FakeSettings(),
    )
    monkeypatch.setattr(
        "api.services.http_client.get_settings",
        lambda: FakeSettings(),
    )
    return FakeSettings()


def _make_item(
    status: str | None = None,
    item_type: str = "ISSUE",
    number: int | None = None,
) -> dict:
    """Create a mock project item."""
    item: dict = {"type": item_type}
    if status:
        item["fieldValueByName"] = {"name": status}
    else:
        item["fieldValueByName"] = None
    if item_type == "DRAFT_ISSUE":
        item["content"] = {"title": "Draft item"}
    else:
        content: dict = {"state": "OPEN"}
        if number is not None:
            content["number"] = number
        item["content"] = content
    return item


class TestComputeBoardHealth:
    """Tests for _compute_board_health()."""

    def test_counts_by_status(self):
        items = [
            _make_item("Todo"),
            _make_item("Todo"),
            _make_item("In Progress"),
            _make_item("Done"),
            _make_item("Done"),
            _make_item("Done"),
        ]
        result = _compute_board_health(items)
        assert result["total_items"] == 6
        assert result["by_status"]["Todo"] == 2
        assert result["by_status"]["In Progress"] == 1
        assert result["by_status"]["Done"] == 3

    def test_counts_draft_items(self):
        items = [
            _make_item("Todo"),
            _make_item("Todo", item_type="DRAFT_ISSUE"),
            _make_item("In Progress"),
        ]
        result = _compute_board_health(items)
        assert result["draft_items"] == 1
        assert result["total_items"] == 3

    def test_untracked_count_passed_through(self):
        items = [_make_item("Todo")]
        result = _compute_board_health(items, untracked_count=3)
        assert result["untracked_issues"] == 3

    def test_untracked_defaults_to_zero(self):
        items = [_make_item("Todo")]
        result = _compute_board_health(items)
        assert result["untracked_issues"] == 0

    def test_empty_items(self):
        result = _compute_board_health([])
        assert result["total_items"] == 0
        assert result["by_status"] == {}
        assert result["draft_items"] == 0
        assert result["untracked_issues"] == 0

    def test_items_without_status(self):
        items = [_make_item(None), _make_item("Todo")]
        result = _compute_board_health(items)
        assert result["total_items"] == 2
        assert result["by_status"] == {"Todo": 1}


class TestFetchProjectItems:
    """Tests for _fetch_project_items()."""

    @pytest.mark.asyncio
    async def test_fetches_items_successfully(self, monkeypatch):
        """Returns items from GraphQL response."""
        graphql_response = {
            "data": {
                "organization": {
                    "projectV2": {
                        "items": {
                            "totalCount": 2,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                _make_item("Todo"),
                                _make_item("Done"),
                            ],
                        }
                    }
                }
            }
        }

        async def mock_post(self, url, **kwargs):
            return httpx.Response(200, json=graphql_response)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is not None
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self, monkeypatch):
        """API errors return None."""

        async def mock_post(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_graphql_errors(self, monkeypatch):
        """GraphQL errors return None."""
        graphql_response = {"errors": [{"message": "Not found"}]}

        async def mock_post(self, url, **kwargs):
            return httpx.Response(200, json=graphql_response)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_project_not_found(self, monkeypatch):
        """Missing project returns None."""
        graphql_response = {"data": {"organization": {"projectV2": None}}}

        async def mock_post(self, url, **kwargs):
            return httpx.Response(200, json=graphql_response)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_paginates_results(self, monkeypatch):
        """Fetches multiple pages of items."""
        call_count = 0

        async def mock_post(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "organization": {
                                "projectV2": {
                                    "items": {
                                        "totalCount": 3,
                                        "pageInfo": {
                                            "hasNextPage": True,
                                            "endCursor": "cursor1",
                                        },
                                        "nodes": [
                                            _make_item("Todo"),
                                            _make_item("Done"),
                                        ],
                                    }
                                }
                            }
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "organization": {
                            "projectV2": {
                                "items": {
                                    "totalCount": 3,
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                    "nodes": [_make_item("In Progress")],
                                }
                            }
                        }
                    }
                },
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is not None
        assert len(result) == 3
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        """Network exceptions return None."""

        async def mock_post(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        result = await _fetch_project_items("YourMoveLabs", 1)
        assert result is None


class TestFetchOpenIssueNumbers:
    """Tests for _fetch_open_issue_numbers()."""

    @pytest.mark.asyncio
    async def test_fetches_issue_numbers(self, monkeypatch):
        """Returns open issue numbers, excluding PRs."""
        api_response = [
            {"number": 1, "title": "Issue 1"},
            {"number": 2, "title": "PR 1", "pull_request": {"url": "..."}},
            {"number": 3, "title": "Issue 2"},
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=api_response)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_open_issue_numbers("YourMoveLabs/agent-fishbowl")
        assert result == {1, 3}

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self, monkeypatch):
        """API error returns None."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_open_issue_numbers("YourMoveLabs/agent-fishbowl")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_issues(self, monkeypatch):
        """Returns empty set when there are no open issues."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await _fetch_open_issue_numbers("YourMoveLabs/agent-fishbowl")
        assert result == set()


class TestGetBoardHealth:
    """Tests for get_board_health()."""

    @pytest.mark.asyncio
    async def test_returns_metrics(self, mock_settings):
        """Computes and returns board health metrics."""
        items = [_make_item("Todo", number=1), _make_item("Done", number=2)]

        with (
            patch(
                "api.services.board_health._fetch_project_items",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch(
                "api.services.board_health._fetch_open_issue_numbers",
                new_callable=AsyncMock,
                return_value={1, 2},
            ),
        ):
            result = await get_board_health()

        assert result["total_items"] == 2
        assert result["by_status"]["Todo"] == 1
        assert result["by_status"]["Done"] == 1
        assert result["untracked_issues"] == 0

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_repo(self, monkeypatch):
        """Returns empty result when github_repo is not configured."""

        class NoRepoSettings:
            github_repo = ""
            github_token = ""

        monkeypatch.setattr(
            "api.services.board_health.get_settings", lambda: NoRepoSettings()
        )
        result = await get_board_health()
        assert result["total_items"] == 0
        assert result["untracked_issues"] == 0

    @pytest.mark.asyncio
    async def test_returns_cached_data(self, mock_settings):
        """Returns cached data on subsequent calls."""
        items = [_make_item("Todo", number=1)]

        with (
            patch(
                "api.services.board_health._fetch_project_items",
                new_callable=AsyncMock,
                return_value=items,
            ) as mock_fetch,
            patch(
                "api.services.board_health._fetch_open_issue_numbers",
                new_callable=AsyncMock,
                return_value={1},
            ),
        ):
            result1 = await get_board_health()
            result2 = await get_board_health()

        assert result1 == result2
        assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_empty_on_api_failure(self, mock_settings):
        """API failure returns empty metrics when no stale cache."""
        with patch(
            "api.services.board_health._fetch_project_items",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_board_health()

        assert result["total_items"] == 0
        assert result["by_status"] == {}
        assert result["untracked_issues"] == 0

    @pytest.mark.asyncio
    async def test_counts_untracked_issues(self, mock_settings):
        """Detects issues not present on the project board."""
        # Board has issues 1 and 2, but open issues include 1, 2, 3
        items = [_make_item("Todo", number=1), _make_item("Done", number=2)]

        with (
            patch(
                "api.services.board_health._fetch_project_items",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch(
                "api.services.board_health._fetch_open_issue_numbers",
                new_callable=AsyncMock,
                return_value={1, 2, 3},
            ),
        ):
            result = await get_board_health()

        assert result["untracked_issues"] == 1

    @pytest.mark.asyncio
    async def test_untracked_zero_when_fetch_fails(self, mock_settings):
        """Untracked issues defaults to 0 when REST API fails."""
        items = [_make_item("Todo", number=1)]

        with (
            patch(
                "api.services.board_health._fetch_project_items",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch(
                "api.services.board_health._fetch_open_issue_numbers",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await get_board_health()

        assert result["untracked_issues"] == 0
