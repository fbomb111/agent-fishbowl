"""Tests for security headers middleware and CORS configuration."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present(mock_settings):
    """Every response includes security headers."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_cors_allows_explicit_methods(mock_settings):
    """CORS preflight returns explicit methods, not wildcard."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/fishbowl/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    allowed = response.headers.get("Access-Control-Allow-Methods", "")
    assert "GET" in allowed
    assert "POST" in allowed
    # Wildcard should not be present
    assert allowed != "*"


@pytest.mark.asyncio
async def test_cors_allows_explicit_headers(mock_settings):
    """CORS preflight returns explicit headers, not wildcard."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/fishbowl/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

    allowed = response.headers.get("Access-Control-Allow-Headers", "")
    assert "Content-Type" in allowed
    assert "X-Ingest-Key" in allowed
    assert allowed != "*"
