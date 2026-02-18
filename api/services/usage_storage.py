"""Azure Blob Storage service for reading agent usage data."""

import json
import logging
from typing import Any

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import ContainerClient

from api.config import get_settings

logger = logging.getLogger(__name__)

# Lazy singleton — lives for the process lifetime
_usage_client: ContainerClient | None = None


def _get_usage_client() -> ContainerClient:
    """Return a shared blob container client for agent-usage (lazy singleton)."""
    global _usage_client
    if _usage_client is not None:
        return _usage_client

    settings = get_settings()
    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"

    credential = ManagedIdentityCredential(
        client_id=settings.managed_identity_client_id
    )

    _usage_client = ContainerClient(
        account_url=account_url,
        container_name=settings.azure_usage_container,
        credential=credential,
    )
    return _usage_client


# In-memory cache: run_id -> usage dict (completed runs are immutable, never expires)
_usage_cache: dict[int, dict[str, Any] | None] = {}


async def get_run_usage(run_id: int) -> dict[str, Any] | None:
    """Fetch usage data for a specific workflow run from blob storage.

    Returns the usage envelope dict or None if not found.
    Results are permanently cached (completed runs are immutable).
    """
    if run_id in _usage_cache:
        return _usage_cache[run_id]

    client = _get_usage_client()
    try:
        blob = client.get_blob_client(f"{run_id}.json")
        data = json.loads(blob.download_blob().readall())
        _usage_cache[run_id] = data
        return data
    except ResourceNotFoundError:
        _usage_cache[run_id] = None
        return None
    except AzureError as e:
        logger.warning("Failed to fetch usage for run %d: %s", run_id, e)
        return None
    except Exception as e:
        logger.error("Unexpected error fetching usage for run %d: %s", run_id, e)
        return None


async def get_recent_usage(limit: int = 50) -> list[dict[str, Any]]:
    """List recent usage blobs for aggregation.

    Returns usage envelopes sorted by run_id descending (most recent first).
    """
    client = _get_usage_client()
    try:
        blob_names: list[str] = []
        for blob_props in client.list_blobs():
            blob_names.append(blob_props.name)
        # Sort by run_id (numeric) descending, take most recent
        blob_names.sort(key=lambda n: int(n.replace(".json", "")), reverse=True)
        blob_names = blob_names[:limit]
    except AzureError as e:
        logger.warning("Failed to list usage blobs: %s", e)
        return []

    results: list[dict[str, Any]] = []
    for name in blob_names:
        run_id = int(name.replace(".json", ""))
        usage = await get_run_usage(run_id)
        if usage:
            results.append(usage)
    return results
