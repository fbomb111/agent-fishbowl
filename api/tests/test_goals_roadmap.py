"""Tests for goals_roadmap service.

Covers roadmap snapshot fetching, subprocess handling, and caching.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.cache import TTLCache
from api.services.goals_roadmap import RoadmapItem, get_roadmap_snapshot


def _make_subprocess_result(stdout_data: str, returncode: int = 0, stderr: str = ""):
    """Create a mock subprocess result."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout_data.encode(), stderr.encode()))
    proc.returncode = returncode
    return proc


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
    async def test_happy_path(self, mock_settings, monkeypatch):
        """Parses gh project output into active items and counts."""
        gh_output = json.dumps(
            {
                "items": [
                    {
                        "title": "Active Feature",
                        "roadmap Status": "Active",
                        "priority": "P1",
                        "goal": "Growth",
                        "phase": "Build",
                    },
                    {
                        "title": "Proposed Feature",
                        "roadmap Status": "Proposed",
                        "priority": "P2",
                    },
                    {
                        "title": "Done Feature",
                        "roadmap Status": "Done",
                    },
                ]
            }
        )

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result(gh_output)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

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
    async def test_empty_project(self, mock_settings, monkeypatch):
        """Empty project returns zero counts and no active items."""
        gh_output = json.dumps({"items": []})

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result(gh_output)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

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
    async def test_subprocess_failure_returns_empty(self, mock_settings, monkeypatch):
        """Non-zero return code returns empty snapshot."""

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result("", returncode=1, stderr="gh error")

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self, mock_settings, monkeypatch):
        """Invalid JSON from subprocess returns empty snapshot."""

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result("not valid json")

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_roadmap_snapshot(cache)

        assert result["active"] == []
        assert result["counts"]["active"] == 0

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, mock_settings, monkeypatch):
        """Subprocess timeout returns empty snapshot."""

        async def mock_create_subprocess_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            proc.returncode = 0
            return proc

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_roadmap_snapshot(cache)

        assert result["active"] == []

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings, monkeypatch):
        """Successful result is stored in cache."""
        gh_output = json.dumps({"items": []})

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result(gh_output)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        await get_roadmap_snapshot(cache)

        cached = cache.get("roadmap")
        assert cached is not None
        assert "active" in cached

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, mock_settings, monkeypatch):
        """Second call returns cached data without re-running subprocess."""
        gh_output = json.dumps({"items": []})
        call_count = 0

        async def mock_create_subprocess_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_subprocess_result(gh_output)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        await get_roadmap_snapshot(cache)
        await get_roadmap_snapshot(cache)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_status_field_fallback(self, mock_settings, monkeypatch):
        """Falls back to 'status' key when 'roadmap Status' is missing."""
        gh_output = json.dumps(
            {
                "items": [
                    {"title": "Item A", "status": "Active"},
                    {"title": "Item B", "status": "Done"},
                ]
            }
        )

        async def mock_create_subprocess_exec(*args, **kwargs):
            return _make_subprocess_result(gh_output)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", mock_create_subprocess_exec
        )

        cache = TTLCache(ttl=300, max_size=10)
        result = await get_roadmap_snapshot(cache)

        assert len(result["active"]) == 1
        assert result["counts"]["active"] == 1
        assert result["counts"]["done"] == 1
