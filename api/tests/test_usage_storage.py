"""Tests for usage_storage service — blob reads, caching, error handling."""

import json
from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError

from api.services.usage_storage import get_recent_usage, get_run_usage


def _mock_blob_download(data):
    """Create a mock blob client whose download_blob().readall() returns JSON."""
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = json.dumps(
        data
    ).encode()
    return mock_blob


class TestGetRunUsage:
    """Tests for get_run_usage()."""

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_settings, monkeypatch):
        """Fetches usage data from blob storage."""
        usage_data = {"run_id": 123, "total_cost": 0.50}
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(usage_data)

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_run_usage(123)
        assert result == usage_data
        mock_container.get_blob_client.assert_called_with("123.json")

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, mock_settings, monkeypatch):
        """ResourceNotFoundError returns None."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_run_usage(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_not_found_is_cached(self, mock_settings, monkeypatch):
        """None results for missing blobs are cached (negative caching)."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        await get_run_usage(999)
        # Second call should use cache, not call blob again
        mock_container.get_blob_client.reset_mock()
        result = await get_run_usage(999)
        assert result is None
        mock_container.get_blob_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_azure_error_returns_none(self, mock_settings, monkeypatch):
        """AzureError returns None without caching."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = AzureError("connection failed")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_run_usage(456)
        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_none(self, mock_settings, monkeypatch):
        """Unexpected exceptions return None."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = RuntimeError("unexpected")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_run_usage(789)
        assert result is None

    @pytest.mark.asyncio
    async def test_result_is_cached(self, mock_settings, monkeypatch):
        """Successful result is cached for subsequent calls."""
        usage_data = {"run_id": 100, "total_cost": 1.00}
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(usage_data)

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        await get_run_usage(100)
        # Second call should use cache
        mock_container.get_blob_client.reset_mock()
        result = await get_run_usage(100)
        assert result == usage_data
        mock_container.get_blob_client.assert_not_called()


class TestGetRecentUsage:
    """Tests for get_recent_usage()."""

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_settings, monkeypatch):
        """Lists blobs, fetches each, returns sorted by run_id descending."""
        blob_list = [
            MagicMock(name="200.json"),
            MagicMock(name="100.json"),
            MagicMock(name="300.json"),
        ]
        # MagicMock.name is special — set it via configure_mock
        blob_list[0].configure_mock(name="200.json")
        blob_list[1].configure_mock(name="100.json")
        blob_list[2].configure_mock(name="300.json")

        usage_300 = {"run_id": 300, "cost": 3.0}
        usage_200 = {"run_id": 200, "cost": 2.0}
        usage_100 = {"run_id": 100, "cost": 1.0}

        def mock_get_blob_client(name):
            data_map = {
                "300.json": usage_300,
                "200.json": usage_200,
                "100.json": usage_100,
            }
            return _mock_blob_download(data_map[name])

        mock_container = MagicMock()
        mock_container.list_blobs.return_value = blob_list
        mock_container.get_blob_client.side_effect = mock_get_blob_client

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_recent_usage(limit=10)
        assert len(result) == 3
        # Sorted by run_id descending
        assert result[0]["run_id"] == 300
        assert result[1]["run_id"] == 200
        assert result[2]["run_id"] == 100

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_settings, monkeypatch):
        """Limit parameter restricts number of blobs fetched."""
        blob_list = [MagicMock() for _ in range(5)]
        for i, b in enumerate(blob_list):
            b.configure_mock(name=f"{(i + 1) * 100}.json")

        def mock_get_blob_client(name):
            run_id = int(name.replace(".json", ""))
            return _mock_blob_download({"run_id": run_id})

        mock_container = MagicMock()
        mock_container.list_blobs.return_value = blob_list
        mock_container.get_blob_client.side_effect = mock_get_blob_client

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_recent_usage(limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_blobs_error_returns_empty(self, mock_settings, monkeypatch):
        """AzureError from list_blobs returns empty list."""
        mock_container = MagicMock()
        mock_container.list_blobs.side_effect = AzureError("connection failed")

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_recent_usage()
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_none_results(self, mock_settings, monkeypatch):
        """Blobs that return None (not found) are excluded from results."""
        blob_list = [MagicMock(), MagicMock()]
        blob_list[0].configure_mock(name="100.json")
        blob_list[1].configure_mock(name="200.json")

        mock_blob_100 = MagicMock()
        mock_blob_100.download_blob.side_effect = ResourceNotFoundError("gone")

        def mock_get_blob_client(name):
            if name == "100.json":
                return mock_blob_100
            return _mock_blob_download({"run_id": 200})

        mock_container = MagicMock()
        mock_container.list_blobs.return_value = blob_list
        mock_container.get_blob_client.side_effect = mock_get_blob_client

        monkeypatch.setattr(
            "api.services.usage_storage._get_usage_client",
            lambda: mock_container,
        )

        result = await get_recent_usage()
        assert len(result) == 1
        assert result[0]["run_id"] == 200
