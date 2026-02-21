"""Tests for http_client module — pagination, error handling, GitHub API wrappers."""

import httpx
import pytest

from api.services.http_client import (
    fetch_closed_issues,
    fetch_merged_prs,
    github_api_get,
    github_headers,
    paginated_github_search,
)


class TestGitHubHeaders:
    """Tests for github_headers()."""

    def test_includes_accept_and_api_version(self, mock_settings):
        headers = github_headers()
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_includes_auth_when_token_present(self, mock_settings):
        mock_settings.github_token = "test_token"  # noqa: S105
        headers = github_headers()
        assert headers["Authorization"] == "Bearer test_token"

    def test_omits_auth_when_no_token(self, mock_settings):
        mock_settings.github_token = None
        headers = github_headers()
        assert "Authorization" not in headers


class TestGitHubApiGet:
    """Tests for github_api_get()."""

    @pytest.mark.asyncio
    async def test_returns_json_on_success(self, monkeypatch):
        """Successful response returns parsed JSON."""
        expected_data = {"items": [{"id": 1}], "total_count": 1}

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=expected_data)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await github_api_get("https://api.github.com/test")
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_extracts_response_key_when_specified(self, monkeypatch):
        """When response_key is provided, return value at that key."""
        data = {"items": [{"id": 1}], "meta": {"count": 1}}

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=data)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await github_api_get(
            "https://api.github.com/test", response_key="items"
        )
        assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_missing_response_key(self, monkeypatch):
        """When response_key is missing from response, return empty list."""
        data = {"other": "data"}

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=data)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await github_api_get(
            "https://api.github.com/test", response_key="items"
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self, monkeypatch):
        """Non-200 status codes return None."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(404, json={"message": "not found"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await github_api_get("https://api.github.com/test")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        """Network errors return None."""

        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await github_api_get("https://api.github.com/test")
        assert result is None

    @pytest.mark.asyncio
    async def test_passes_params_to_request(self, monkeypatch):
        """Query params are passed through to the request."""
        captured_params = None

        async def mock_get(self, url, **kwargs):
            nonlocal captured_params
            captured_params = kwargs.get("params")
            return httpx.Response(200, json={})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        await github_api_get(
            "https://api.github.com/test", params={"q": "test", "per_page": "50"}
        )
        assert captured_params == {"q": "test", "per_page": "50"}


class TestPaginatedGitHubSearch:
    """Tests for paginated_github_search()."""

    @pytest.mark.asyncio
    async def test_single_page_returns_all_items(self, monkeypatch):
        """When all items fit on one page, return them."""
        page1 = {"items": [{"id": 1}, {"id": 2}], "total_count": 2}

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=page1)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_paginates_multiple_pages(self, monkeypatch):
        """Fetches all pages until total_count is reached."""
        # Use full pages (100 items each) to trigger pagination
        page1 = {
            "items": [{"id": i} for i in range(100)],
            "total_count": 150,
        }
        page2 = {
            "items": [{"id": i} for i in range(100, 150)],
            "total_count": 150,
        }

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=page1 if call_count == 1 else page2)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert len(result) == 150
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stops_when_items_less_than_per_page(self, monkeypatch):
        """Stops paginating when a page returns fewer items than per_page."""
        page1 = {"items": [{"id": i} for i in range(100)], "total_count": 150}
        page2 = {"items": [{"id": i} for i in range(100, 125)], "total_count": 150}

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=page1 if call_count == 1 else page2)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}, per_page=100
        )
        assert len(result) == 125
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_on_first_page_failure(self, monkeypatch):
        """Returns None when the first page fails."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "server error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_partial_results_on_later_page_failure(self, monkeypatch):
        """Returns partial results when a later page fails."""
        page1 = {"items": [{"id": 1}, {"id": 2}], "total_count": 300}

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_returns_none_on_first_page_exception(self, monkeypatch):
        """Returns None when first page request raises an exception."""

        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_partial_on_later_page_exception(self, monkeypatch):
        """Returns partial results when a later page raises an exception."""
        page1 = {"items": [{"id": 1}], "total_count": 200}

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            raise httpx.HTTPError("timeout")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_handles_missing_total_count(self, monkeypatch):
        """When total_count is missing, returns items from first page."""
        page1 = {"items": [{"id": 1}, {"id": 2}]}

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=page1)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await paginated_github_search(
            "https://api.github.com/search/issues", params={"q": "test"}
        )
        assert result == [{"id": 1}, {"id": 2}]


class TestFetchMergedPrs:
    """Tests for fetch_merged_prs()."""

    @pytest.mark.asyncio
    async def test_returns_merged_prs_after_since_date(self, monkeypatch):
        """Returns PRs merged on or after the since date."""
        prs = [
            {
                "number": 1,
                "merged_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            },
            {
                "number": 2,
                "merged_at": "2026-02-16T12:00:00Z",
                "updated_at": "2026-02-16T12:00:00Z",
            },
            {
                "number": 3,
                "merged_at": None,
                "updated_at": "2026-02-17T00:00:00Z",
            },  # not merged
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=prs)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    @pytest.mark.asyncio
    async def test_filters_out_prs_before_since_date(self, monkeypatch):
        """Excludes PRs merged before the since date."""
        prs = [
            {
                "number": 1,
                "merged_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:00:00Z",
            },
            {
                "number": 2,
                "merged_at": "2026-02-16T12:00:00Z",
                "updated_at": "2026-02-16T12:00:00Z",
            },
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=prs)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert len(result) == 1
        assert result[0]["number"] == 2

    @pytest.mark.asyncio
    async def test_handles_iso_timestamp_since(self, monkeypatch):
        """Accepts ISO timestamp with time for since parameter."""
        prs = [
            {
                "number": 1,
                "merged_at": "2026-02-15T15:00:00Z",
                "updated_at": "2026-02-15T15:00:00Z",
            },
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=prs)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15T12:00:00Z")
        assert len(result) == 1
        assert result[0]["number"] == 1

    @pytest.mark.asyncio
    async def test_paginates_multiple_pages(self, monkeypatch):
        """Fetches multiple pages of PRs."""
        page1 = [
            {
                "number": i,
                "merged_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            }
            for i in range(100)
        ]
        page2 = [
            {
                "number": i,
                "merged_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            }
            for i in range(100, 120)
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=page1 if call_count == 1 else page2)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert len(result) == 120  # 100 from page1 + 20 from page2

    @pytest.mark.asyncio
    async def test_stops_when_oldest_updated_before_since(self, monkeypatch):
        """Stops pagination when oldest item on page was updated before since."""
        page1 = [
            {
                "number": 1,
                "merged_at": "2026-02-16T00:00:00Z",
                "updated_at": "2026-02-16T00:00:00Z",
            },
            {
                "number": 2,
                "merged_at": "2026-02-15T00:00:00Z",
                "updated_at": "2026-02-14T00:00:00Z",
            },  # updated before since
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=page1)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert len(result) == 2  # Still includes the merged PR from 2026-02-15
        assert call_count == 1  # Stopped after first page

    @pytest.mark.asyncio
    async def test_returns_none_on_first_page_failure(self, monkeypatch):
        """Returns None when first page fails."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_partial_on_later_page_failure(self, monkeypatch):
        """Returns partial results when a later page fails."""
        page1 = [
            {
                "number": 1,
                "merged_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            }
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert result == page1

    @pytest.mark.asyncio
    async def test_returns_none_on_first_page_exception(self, monkeypatch):
        """Returns None when first page request raises an exception."""

        async def mock_get(self, url, **kwargs):
            raise httpx.HTTPError("connection failed")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_merged_prs("test/repo", "2026-02-15")
        assert result is None


class TestFetchClosedIssues:
    """Tests for fetch_closed_issues()."""

    @pytest.mark.asyncio
    async def test_returns_closed_issues_after_since_date(self, monkeypatch):
        """Returns issues closed on or after the since date."""
        issues = [
            {
                "number": 1,
                "closed_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            },
            {
                "number": 2,
                "closed_at": "2026-02-16T12:00:00Z",
                "updated_at": "2026-02-16T12:00:00Z",
            },
            {
                "number": 3,
                "closed_at": None,
                "updated_at": "2026-02-17T00:00:00Z",
            },  # not closed
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=issues)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    @pytest.mark.asyncio
    async def test_filters_out_pull_requests(self, monkeypatch):
        """Excludes PRs (Issues API includes them)."""
        issues = [
            {
                "number": 1,
                "closed_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            },
            {
                "number": 2,
                "closed_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
                "pull_request": {},
            },
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=issues)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert len(result) == 1
        assert result[0]["number"] == 1

    @pytest.mark.asyncio
    async def test_filters_out_issues_before_since_date(self, monkeypatch):
        """Excludes issues closed before the since date."""
        issues = [
            {
                "number": 1,
                "closed_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:00:00Z",
            },
            {
                "number": 2,
                "closed_at": "2026-02-16T12:00:00Z",
                "updated_at": "2026-02-16T12:00:00Z",
            },
        ]

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, json=issues)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert len(result) == 1
        assert result[0]["number"] == 2

    @pytest.mark.asyncio
    async def test_stops_when_oldest_updated_before_since(self, monkeypatch):
        """Stops pagination when oldest item on page was updated before since."""
        page1 = [
            {
                "number": 1,
                "closed_at": "2026-02-16T00:00:00Z",
                "updated_at": "2026-02-16T00:00:00Z",
            },
            {
                "number": 2,
                "closed_at": "2026-02-15T00:00:00Z",
                "updated_at": "2026-02-14T00:00:00Z",
            },
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=page1)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert len(result) == 2
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_returns_none_on_first_page_failure(self, monkeypatch):
        """Returns None when first page fails."""

        async def mock_get(self, url, **kwargs):
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_partial_on_later_page_failure(self, monkeypatch):
        """Returns partial results when a later page fails."""
        page1 = [
            {
                "number": 1,
                "closed_at": "2026-02-15T10:00:00Z",
                "updated_at": "2026-02-15T10:00:00Z",
            }
        ]

        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=page1)
            return httpx.Response(500, json={"message": "error"})

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await fetch_closed_issues("test/repo", "2026-02-15")
        assert result == page1
