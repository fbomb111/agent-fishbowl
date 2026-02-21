"""Tests for the blog OG meta endpoint."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from api.models.blog import BlogIndex, BlogPost


def _make_post(
    slug: str = "test-post",
    title: str = "Test Post Title",
    image_url: str | None = None,
) -> BlogPost:
    return BlogPost(
        id="post-1",
        title=title,
        slug=slug,
        description="A test blog post description.",
        published_at=datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc),
        preview_url="https://agentfishbowl.com/blog/test-post/index.html",
        image_url=image_url,
    )


async def test_og_endpoint_returns_meta_tags(mock_settings, mocker):
    post = _make_post()
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=BlogIndex(posts=[post], total=1),
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/fishbowl/blog/by-slug/test-post/og")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

    body = resp.text
    assert 'property="og:title" content="Test Post Title"' in body
    assert 'property="og:description"' in body
    assert 'property="og:type" content="article"' in body
    assert 'property="article:published_time" content="2026-02-18' in body
    assert 'name="twitter:card" content="summary"' in body
    assert 'rel="canonical" href="https://agentfishbowl.com/blog/test-post"' in body
    assert 'http-equiv="refresh"' in body


async def test_og_endpoint_includes_image_when_present(mock_settings, mocker):
    post = _make_post(image_url="https://images.example.com/hero.jpg")
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=BlogIndex(posts=[post], total=1),
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/fishbowl/blog/by-slug/test-post/og")

    assert resp.status_code == 200
    assert 'property="og:image" content="https://images.example.com/hero.jpg"' in resp.text


async def test_og_endpoint_omits_image_when_absent(mock_settings, mocker):
    post = _make_post(image_url=None)
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=BlogIndex(posts=[post], total=1),
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/fishbowl/blog/by-slug/test-post/og")

    assert resp.status_code == 200
    assert "og:image" not in resp.text


async def test_og_endpoint_returns_404_for_unknown_slug(mock_settings, mocker):
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=BlogIndex(posts=[], total=0),
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/fishbowl/blog/by-slug/nonexistent-post/og")

    assert resp.status_code == 404


async def test_og_endpoint_escapes_html_in_title(mock_settings, mocker):
    post = _make_post(title='Post with "quotes" & <tags>')
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=BlogIndex(posts=[post], total=1),
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/fishbowl/blog/by-slug/test-post/og")

    assert resp.status_code == 200
    body = resp.text
    # Should be HTML-escaped, not raw
    assert "&lt;tags&gt;" in body
    assert "&amp;" in body
    assert "<tags>" not in body
