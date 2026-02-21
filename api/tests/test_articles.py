"""Tests for the articles feed endpoints.

Covers article list/get, filtering, pagination, and error cases.
"""

from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient


async def test_list_articles(mock_settings, mocker):
    """Test articles list endpoint returns the article index."""
    from api.models.article import ArticleIndex, ArticleSummary

    mock_articles = [
        ArticleSummary(
            id="article1",
            title="Understanding AsyncIO",
            description="A deep dive into Python's async features",
            source="example.com",
            source_url="https://example.com/asyncio",
            original_url="https://example.com/asyncio",
            published_at="2026-02-20T10:00:00Z",
            categories=["Python"],
        ),
        ArticleSummary(
            id="article2",
            title="FastAPI Best Practices",
            description="Building scalable APIs with FastAPI",
            source="example.com",
            source_url="https://example.com/fastapi",
            original_url="https://example.com/fastapi",
            published_at="2026-02-19T10:00:00Z",
            categories=["Python"],
        ),
    ]
    mock_index = ArticleIndex(articles=mock_articles, total=2)
    mocker.patch(
        "api.routers.articles.get_article_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/articles")

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data
    assert len(data["articles"]) == 2


async def test_list_articles_with_category_filter(mock_settings, mocker):
    """Test articles list supports category filtering."""
    from api.models.article import ArticleIndex, ArticleSummary

    mock_articles = [
        ArticleSummary(
            id="article1",
            title="Understanding AsyncIO",
            description="Python async features",
            source="example.com",
            source_url="https://example.com/asyncio",
            original_url="https://example.com/asyncio",
            published_at="2026-02-20T10:00:00Z",
            categories=["Python"],
        )
    ]
    mock_index = ArticleIndex(articles=mock_articles, total=1)
    mock_get_index = mocker.patch(
        "api.routers.articles.get_article_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/articles", params={"category": "Python"}
        )

    assert response.status_code == 200
    # Verify the service was called with the category filter
    mock_get_index.assert_called_once()
    call_kwargs = mock_get_index.call_args.kwargs
    assert call_kwargs["category"] == "Python"


async def test_list_articles_with_search(mock_settings, mocker):
    """Test articles list supports search query."""
    from api.models.article import ArticleIndex

    mock_index = ArticleIndex(articles=[], total=0)
    mock_get_index = mocker.patch(
        "api.routers.articles.get_article_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/articles", params={"search": "async"}
        )

    assert response.status_code == 200
    # Verify the service was called with the search filter
    call_kwargs = mock_get_index.call_args.kwargs
    assert call_kwargs["search"] == "async"


async def test_list_articles_with_pagination(mock_settings, mocker):
    """Test articles list supports limit/offset pagination."""
    from api.models.article import ArticleIndex

    mock_index = ArticleIndex(articles=[], total=100)
    mock_get_index = mocker.patch(
        "api.routers.articles.get_article_index",
        new_callable=AsyncMock,
        return_value=mock_index,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/fishbowl/articles", params={"limit": 10, "offset": 20}
        )

    assert response.status_code == 200
    # Verify pagination parameters were passed
    call_kwargs = mock_get_index.call_args.kwargs
    assert call_kwargs["limit"] == 10
    assert call_kwargs["offset"] == 20


async def test_get_article_by_id(mock_settings, mocker):
    """Test getting a single article by ID."""
    from api.models.article import Article

    mock_article = Article(
        id="article1",
        title="Understanding AsyncIO",
        description="A deep dive into Python's async features",
        source="example.com",
        source_url="https://example.com/asyncio",
        original_url="https://example.com/asyncio",
        published_at="2026-02-20T10:00:00Z",
        ingested_at="2026-02-20T11:00:00Z",
        categories=["Python"],
    )
    mocker.patch(
        "api.routers.articles.get_article",
        new_callable=AsyncMock,
        return_value=mock_article,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/articles/article1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "article1"
    assert data["title"] == "Understanding AsyncIO"


async def test_get_article_not_found(mock_settings, mocker):
    """Test getting a non-existent article returns 404."""
    mocker.patch(
        "api.routers.articles.get_article",
        new_callable=AsyncMock,
        return_value=None,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/fishbowl/articles/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


async def test_trigger_ingestion_requires_auth(mock_settings):
    """Test ingest endpoint rejects requests without valid API key."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # No header
        response = await client.post("/api/fishbowl/articles/ingest")
        assert response.status_code == 422  # Missing required header

        # Invalid key
        response = await client.post(
            "/api/fishbowl/articles/ingest", headers={"x-ingest-key": "wrong-key"}
        )
        assert response.status_code == 403


async def test_trigger_ingestion_success(mock_settings, mocker):
    """Test ingest endpoint runs ingestion and returns stats."""
    mock_stats = mocker.Mock()
    mock_stats.to_dict.return_value = {
        "articles_added": 5,
        "articles_updated": 2,
        "sources_fetched": 3,
    }
    mocker.patch(
        "api.routers.articles.run_ingestion",
        new_callable=AsyncMock,
        return_value=mock_stats,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/articles/ingest",
            headers={"x-ingest-key": "test-ingest-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["articles_added"] == 5
    assert data["articles_updated"] == 2
