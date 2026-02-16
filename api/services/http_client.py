"""Shared HTTP client utilities — reusable httpx client and retry helper."""

import asyncio
import logging

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


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    **kwargs,
) -> httpx.Response:
    """Execute an HTTP request with exponential-backoff retry on 429/5xx.

    Args:
        client: The httpx.AsyncClient to use.
        method: HTTP method (GET, POST, etc.).
        url: Target URL.
        max_retries: Maximum number of retry attempts.
        backoff_base: Base seconds for exponential backoff.
        **kwargs: Forwarded to ``client.request()``.

    Returns:
        The httpx.Response from the first successful (non-retryable) attempt.

    Raises:
        httpx.HTTPStatusError: If the last attempt still fails with a
            retryable status code.
        httpx.HTTPError: On non-retryable transport errors.
    """
    last_response: httpx.Response | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)

            if response.status_code == 429 or response.status_code >= 500:
                last_response = response
                if attempt < max_retries:
                    delay = backoff_base * (2**attempt)
                    logger.warning(
                        "Retryable %d from %s %s (attempt %d/%d, sleeping %.1fs)",
                        response.status_code,
                        method,
                        url,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Last attempt — raise so caller sees the error
                response.raise_for_status()

            return response

        except httpx.TimeoutException:
            last_response = None
            if attempt < max_retries:
                delay = backoff_base * (2**attempt)
                logger.warning(
                    "Timeout on %s %s (attempt %d/%d, sleeping %.1fs)",
                    method,
                    url,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            raise

    # Should not be reached, but satisfy type checker
    assert last_response is not None
    last_response.raise_for_status()
    return last_response  # pragma: no cover
