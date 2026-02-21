"""Tests for the blog post endpoints.

Covers blog list/get/create, HTML serving, image copying, and sanitization.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient


async def test_list_blog_posts(mock_settings, mocker):
    """Test blog index endpoint returns list of posts."""
    from api.models.blog import BlogIndex, BlogPost

    mock_posts = [
        BlogPost(
            id="post1",
            slug="first-post",
            title="First Blog Post",
            description="Introduction to our blog",
            preview_url="https://example.com/post1",
            published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        ),
        BlogPost(
            id="post2",
            slug="second-post",
            title="Second Blog Post",
            description="More insights",
            preview_url="https://example.com/post2",
            published_at=datetime(2026, 2, 19, 10, 0, tzinfo=timezone.utc),
        ),
    ]
    mock_index = BlogIndex(posts=mock_posts, total=2)
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog")

    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert len(data["posts"]) == 2


async def test_list_blog_posts_with_pagination(mock_settings, mocker):
    """Test blog index supports limit/offset pagination."""
    from api.models.blog import BlogIndex

    mock_index = BlogIndex(posts=[], total=0)
    mock_get_index = mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/blog", params={"limit": 10, "offset": 5}
        )

    assert response.status_code == 200
    # Verify pagination parameters were passed
    call_kwargs = mock_get_index.call_args.kwargs
    assert call_kwargs["limit"] == 10
    assert call_kwargs["offset"] == 5


async def test_get_blog_post_by_id(mock_settings, mocker):
    """Test getting a single blog post by ID."""
    from api.models.blog import BlogPost

    mock_posts = [
        BlogPost(
            id="post1",
            slug="first-post",
            title="First Blog Post",
            description="Introduction",
            preview_url="https://example.com/post1",
            published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        )
    ]
    mock_index = mocker.Mock()
    mock_index.posts = mock_posts
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/post1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "post1"
    assert data["title"] == "First Blog Post"


async def test_get_blog_post_not_found(mock_settings, mocker):
    """Test getting a non-existent blog post returns 404."""
    mock_index = mocker.Mock()
    mock_index.posts = []
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


async def test_get_blog_post_by_slug(mock_settings, mocker):
    """Test getting a blog post by slug."""
    from api.models.blog import BlogPost

    mock_posts = [
        BlogPost(
            id="post1",
            slug="first-post",
            title="First Blog Post",
            description="Introduction",
            preview_url="https://example.com/post1",
            published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        )
    ]
    mock_index = mocker.Mock()
    mock_index.posts = mock_posts
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/by-slug/first-post")

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "first-post"


async def test_get_blog_post_by_slug_not_found(mock_settings, mocker):
    """Test getting a non-existent blog post by slug returns 404."""
    mock_index = mocker.Mock()
    mock_index.posts = []
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/by-slug/nonexistent")

    assert response.status_code == 404


async def test_add_blog_post_requires_auth(mock_settings):
    """Test blog post creation rejects requests without valid API key."""
    from api.main import app

    post_data = {
        "id": "new-post",
        "slug": "new-post",
        "title": "New Post",
        "description": "Description",
        "preview_url": "https://example.com/post",
        "published_at": "2026-02-20T10:00:00Z",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # No header
        response = await client.post("/api/fishbowl/blog", json=post_data)
        assert response.status_code == 422  # Missing required header

        # Invalid key
        response = await client.post(
            "/api/fishbowl/blog",
            json=post_data,
            headers={"x-ingest-key": "wrong-key"},
        )
        assert response.status_code == 403


async def test_add_blog_post_returns_exists_if_duplicate(mock_settings, mocker):
    """Test blog post creation returns 'exists' status for duplicate ID."""
    from api.models.blog import BlogPost

    existing_post = BlogPost(
        id="existing-post",
        slug="existing-post",
        title="Existing Post",
        description="Already exists",
        preview_url="https://example.com/existing",
        published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
    )
    mock_index = mocker.Mock()
    mock_index.posts = [existing_post]
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    post_data = {
        "id": "existing-post",
        "slug": "duplicate-slug",
        "title": "Duplicate Post",
        "description": "Should be rejected",
        "preview_url": "https://example.com/duplicate",
        "published_at": "2026-02-20T10:00:00Z",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/blog",
            json=post_data,
            headers={"x-ingest-key": "test-ingest-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "exists"
    assert data["id"] == "existing-post"


async def test_add_blog_post_creates_new_post(mock_settings, mocker):
    """Test blog post creation adds new post and copies HTML."""
    mock_index = mocker.Mock()
    mock_index.posts = []
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    # Mock HTTP client for fetching preview HTML
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Blog content</body></html>"
    mock_response.raise_for_status = mocker.Mock()
    mock_client = mocker.Mock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mocker.patch("api.routers.blog.get_shared_client", return_value=mock_client)

    # Mock sanitization and upload
    mocker.patch(
        "api.routers.blog.sanitize_blog_html",
        return_value="<html>Sanitized content</html>",
    )
    mocker.patch("api.routers.blog.upload_blog_html", new_callable=AsyncMock)
    mocker.patch("api.routers.blog.write_blog_index", new_callable=AsyncMock)
    mocker.patch(
        "api.routers.blog._copy_blog_images",
        new_callable=AsyncMock,
        return_value=2,
    )

    from api.main import app

    post_data = {
        "id": "new-post",
        "slug": "new-post",
        "title": "New Post",
        "description": "A fresh post",
        "preview_url": "https://example.com/new-post/index.html",
        "published_at": "2026-02-20T10:00:00Z",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/blog",
            json=post_data,
            headers={"x-ingest-key": "test-ingest-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert data["id"] == "new-post"
    assert data["copied"] is True
    assert data["images_copied"] == 2


async def test_get_blog_post_content_serves_html(mock_settings, mocker):
    """Test blog post content endpoint serves HTML from blob storage."""
    from api.models.blog import BlogPost

    mock_posts = [
        BlogPost(
            id="post1",
            slug="first-post",
            title="First Post",
            description="Intro",
            preview_url="https://example.com/post1",
            published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        )
    ]
    mock_index = mocker.Mock()
    mock_index.posts = mock_posts
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )
    mocker.patch(
        "api.routers.blog.read_blog_html",
        new_callable=AsyncMock,
        return_value="<html>Blog content</html>",
    )
    mocker.patch(
        "api.routers.blog.sanitize_blog_html",
        return_value="<html>Sanitized</html>",
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/post1/content")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html>Sanitized</html>" in response.text


async def test_get_blog_post_content_not_found(mock_settings, mocker):
    """Test blog post content returns 404 for non-existent post."""
    mock_index = mocker.Mock()
    mock_index.posts = []
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/nonexistent/content")

    assert response.status_code == 404


async def test_resanitize_blog_posts_requires_auth(mock_settings):
    """Test resanitize endpoint rejects requests without valid API key."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/fishbowl/blog/resanitize")
        assert response.status_code == 422  # Missing required header

        response = await client.post(
            "/api/fishbowl/blog/resanitize", headers={"x-ingest-key": "wrong"}
        )
        assert response.status_code == 403


async def test_get_blog_post_og_metadata(mock_settings, mocker):
    """Test OG metadata endpoint returns HTML with OpenGraph tags."""
    from api.models.blog import BlogPost

    mock_posts = [
        BlogPost(
            id="post1",
            slug="test-slug",
            title="Test Post",
            description="Test description",
            preview_url="https://example.com/post1",
            published_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
            image_url="https://example.com/image.jpg",
        )
    ]
    mock_index = mocker.Mock()
    mock_index.posts = mock_posts
    mocker.patch(
        "api.routers.blog.get_blog_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/blog/by-slug/test-slug/og")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "og:title" in html
    assert "Test Post" in html
    assert "og:description" in html
    assert "Test description" in html
    assert "og:image" in html
    assert "https://example.com/image.jpg" in html
