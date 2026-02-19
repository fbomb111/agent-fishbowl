"""Shared HTTP client utilities — reusable httpx client."""

import httpx

from api.config import get_settings

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
