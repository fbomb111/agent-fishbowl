"""Shared HTTP client utilities — reusable httpx client."""

import logging
from typing import Any

import httpx

from api.config import get_settings

logger = logging.getLogger(__name__)

# Module-level shared client (created lazily, lives for the process lifetime)
_client: httpx.AsyncClient | None = None


def get_shared_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient, creating it on first call."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


def github_headers() -> dict[str, str]:
    """Build standard GitHub API request headers.

    Includes the Authorization header only when a token is configured.
    """
    settings = get_settings()
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def github_api_get(
    url: str,
    params: dict[str, str] | None = None,
    *,
    response_key: str | None = None,
    context: str = "",
) -> list[Any] | dict[str, Any] | None:
    """Fetch a GitHub API endpoint with standard error handling.

    Returns parsed JSON (or the value at response_key if specified).
    Returns None on any error so callers can apply their own fallback.
    """
    client = get_shared_client()
    headers = github_headers()
    try:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            logger.warning(
                "GitHub API %d for %s%s",
                resp.status_code,
                url,
                f" ({context})" if context else "",
            )
            return None
        data = resp.json()
        return data.get(response_key, []) if response_key else data
    except Exception:
        logger.exception(
            "GitHub API error for %s%s", url, f" ({context})" if context else ""
        )
        return None
