"""Tests for goals_roadmap service.

Covers roadmap snapshot fetching via GraphQL, error handling, and caching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.cache import TTLCache
from api.services.goals_roadmap import (
    RoadmapItem,
    _extract_field,
    get_roadmap_snapshot,
)


def _graphql_response(items: list[dict]) -> dict:
    """Build a mock GraphQL response with ProjectV2 items."""
    nodes = []
    for item in items:
        field_values = []
        for field_name, value in item.items():
            if field_name == "title":
                continue
            field_values.append(
                {
                    "field": {"name": field_name},
                    "name": value,
                }
            )
        nodes.append(
            {
                "content": {"title": item.get("title", "")},
                "fieldValues": {"nodes": field_values},
            }
        )
    return {
        "data": {
            "organization": {
                "projectV2": {
                    "items": {"nodes": nodes},
                }
            }
        }
    }


def _mock_http_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


class TestRoadmapItem:
    """Tests for RoadmapItem dataclass."""

    def test_defaults(self):
        item = RoadmapItem(title="Test")
        assert item.title == "Test"
        assert item.body == ""
        assert item.priority == ""
        assert item.goal == ""
        assert item.phase == ""
        assert item.status == ""

    def test_all_fields(self):
        item = RoadmapItem(
            title="Feature X",
            body="Details",
            priority="P1",
            goal="Revenue",
            phase="Build",
            status="Active",
        )
        assert item.title == "Feature X"
        assert item.priority == "P1"


class TestExtractField:
    """Tests for _extract_field helper."""

    def test_extracts_single_select(self):
        nodes = [{"field": {"name": "Priority"}, "name": "P1"}]
        assert _extract_field(nodes, "Priority") == "P1"

    def test_extracts_text_field(self):
        nodes = [{"field": {"name": "Goal"}, "text": "Revenue"}]
        assert _extract_field(nodes, "Goal") == "Revenue"

    def test_case_insensitive(self):
        nodes = [{"field": {"name": "Roadmap Status"}, "name": "Active"}]
        assert _extract_field(nodes, "roadmap status") == "Active"

    def test_missing_field_returns_empty(self):
        nodes = [{"field": {"name": "Priority"}, "name": "P1"}]
        assert _extract_field(nodes, "NonExistent") == ""

    def test_empty_nodes(self):
        assert _extract_field([], "Priority") == ""


class TestGetRoadmapSnapshot:
    """Tests for get_roadmap_snapshot()."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        cache = TTLCache(ttl=300, max_size=10)
        fake_snapshot = {"active": [{"title": "Cached Item"}], "counts": {}}
        cache.set("roadmap", fake_snapshot)

        result = await get_roadmap_snapshot(cache)
        assert result == fake_snapshot

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_settings):
        """Parses GraphQL response into active items and counts."""
        graphql_data = _graphql_response(
            [
                {
                    "title": "Active Feature",
                    "Roadmap Status": "Active",
                    "Priority": "P1",
                    "Goal": "Growth",
                    "Phase": "Build",
                },
                {
                    "title": "Proposed Feature",
                    "Roadmap Status": "Proposed",
                    "Priority": "P2",
                },
                {
                    "title": "Done Feature",
                    "Roadmap Status": "Done",
                },
            ]
        )

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(graphql_data)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert len(result["active"]) == 1
        assert result["active"][0]["title"] == "Active Feature"
        assert result["active"][0]["priority"] == "P1"
        assert result["counts"]["active"] == 1
        assert result["counts"]["proposed"] == 1
        assert result["counts"]["done"] == 1
        assert result["counts"]["deferred"] == 0

    @pytest.mark.asyncio
    async def test_empty_project(self, mock_settings):
        """Empty project returns zero counts and no active items."""
        graphql_data = _graphql_response([])

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(graphql_data)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"] == {
            "proposed": 0,
            "active": 0,
            "done": 0,
            "deferred": 0,
        }

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, mock_settings):
        """Non-200 HTTP status returns empty snapshot."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response({}, status_code=401)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_graphql_errors_returns_empty(self, mock_settings):
        """GraphQL errors in response returns empty snapshot."""
        error_data = {
            "errors": [{"message": "Could not resolve to a ProjectV2"}],
            "data": None,
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(error_data)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_no_project_data_returns_empty(self, mock_settings):
        """Missing projectV2 in response returns empty snapshot (token scope issue)."""
        no_project = {
            "data": {"organization": {"projectV2": None}}
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(no_project)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, mock_settings):
        """Network exception returns empty snapshot."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings):
        """Successful result is stored in cache."""
        graphql_data = _graphql_response([])
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(graphql_data)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            await get_roadmap_snapshot(cache)

        cached = cache.get("roadmap")
        assert cached is not None
        assert "active" in cached

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, mock_settings):
        """Second call returns cached data without re-calling GraphQL."""
        graphql_data = _graphql_response([])
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_http_response(graphql_data)
        )

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            cache = TTLCache(ttl=300, max_size=10)
            await get_roadmap_snapshot(cache)
            await get_roadmap_snapshot(cache)

        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_exception_returns_stale_cache(self, mock_settings):
        """When GraphQL fails and stale cache exists, returns stale data."""
        cache = TTLCache(ttl=0, max_size=10)
        stale = {"active": [{"title": "Stale"}], "counts": {"proposed": 0, "active": 1, "done": 0, "deferred": 0}}
        cache._store["roadmap"] = (stale, 0)  # expired entry

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch(
            "api.services.goals_roadmap.get_shared_client",
            return_value=mock_client,
        ):
            result = await get_roadmap_snapshot(cache)

        assert result == stale
