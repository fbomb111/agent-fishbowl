"""Tests for blob_storage service — article/blog index read/write, error handling."""

import json
from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from api.models.article import ArticleSummary
from api.services.blob_storage import (
    get_article,
    get_article_index,
    get_blog_index,
    write_article,
    write_article_only,
)


def _make_article_summary(
    article_id="art-1",
    title="Test Article",
    categories=None,
    description="A test article",
):
    """Build a minimal ArticleSummary dict."""
    return {
        "id": article_id,
        "title": title,
        "source": "Test Source",
        "source_url": "https://example.com",
        "original_url": "https://example.com/article",
        "published_at": "2026-01-15T10:00:00Z",
        "description": description,
        "categories": categories or [],
    }


def _make_article_data(article_id="art-1", title="Test Article", **kwargs):
    """Build a full Article dict (includes ingested_at)."""
    data = _make_article_summary(article_id=article_id, title=title, **kwargs)
    data["ingested_at"] = "2026-01-15T10:00:00Z"
    return data


def _make_blog_post(post_id="post-1", title="Test Post", slug="test-post"):
    """Build a minimal BlogPost dict."""
    return {
        "id": post_id,
        "title": title,
        "slug": slug,
        "description": "A test post",
        "published_at": "2026-01-15T10:00:00Z",
        "preview_url": "https://example.com/blog/test-post",
    }


def _mock_blob_download(data):
    """Create a mock blob client whose download_blob().readall() returns JSON."""
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = json.dumps(
        data
    ).encode()
    return mock_blob


class TestGetArticleIndex:
    """Tests for get_article_index()."""

    @pytest.mark.asyncio
    async def test_happy_path_list_format(self, mock_settings, monkeypatch):
        """Index stored as a list returns articles correctly."""
        articles = [_make_article_summary("a1"), _make_article_summary("a2")]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(articles)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index()
        assert result.total == 2
        assert len(result.articles) == 2
        assert result.articles[0].id == "a1"

    @pytest.mark.asyncio
    async def test_dict_format_index(self, mock_settings, monkeypatch):
        """Index stored as {"articles": [...]} is handled."""
        articles = [_make_article_summary("a1")]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(
            {"articles": articles}
        )

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index()
        assert result.total == 1
        assert result.articles[0].id == "a1"

    @pytest.mark.asyncio
    async def test_category_filter(self, mock_settings, monkeypatch):
        """Category filter narrows results (case-insensitive)."""
        articles = [
            _make_article_summary("a1", categories=["Python", "AI"]),
            _make_article_summary("a2", categories=["JavaScript"]),
        ]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(articles)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index(category="python")
        assert result.total == 1
        assert result.articles[0].id == "a1"

    @pytest.mark.asyncio
    async def test_search_filter(self, mock_settings, monkeypatch):
        """Search matches against title and description (case-insensitive)."""
        articles = [
            _make_article_summary(
                "a1", title="FastAPI Guide", description="Build APIs"
            ),
            _make_article_summary(
                "a2", title="React Tips", description="UI tricks"
            ),
        ]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(articles)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index(search="fastapi")
        assert result.total == 1
        assert result.articles[0].id == "a1"

    @pytest.mark.asyncio
    async def test_search_matches_description(self, mock_settings, monkeypatch):
        """Search also matches description field."""
        articles = [
            _make_article_summary("a1", title="Guide", description="Learn FastAPI"),
        ]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(articles)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index(search="fastapi")
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_offset_and_limit(self, mock_settings, monkeypatch):
        """Offset and limit slice the results; total reflects pre-slice count."""
        articles = [_make_article_summary(f"a{i}") for i in range(5)]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(articles)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index(offset=1, limit=2)
        assert result.total == 5
        assert len(result.articles) == 2
        assert result.articles[0].id == "a1"
        assert result.articles[1].id == "a2"

    @pytest.mark.asyncio
    async def test_resource_not_found_returns_empty(self, mock_settings, monkeypatch):
        """ResourceNotFoundError returns empty index."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index()
        assert result.total == 0
        assert result.articles == []

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, mock_settings, monkeypatch):
        """HttpResponseError returns empty index."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = HttpResponseError(message="server error")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article_index()
        assert result.total == 0
        assert result.articles == []


class TestGetArticle:
    """Tests for get_article()."""

    @pytest.mark.asyncio
    async def test_article_found(self, mock_settings, monkeypatch):
        """Returns Article when blob exists."""
        article_data = _make_article_data("art-1")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(article_data)

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article("art-1")
        assert result is not None
        assert result.id == "art-1"
        assert result.title == "Test Article"

    @pytest.mark.asyncio
    async def test_article_not_found(self, mock_settings, monkeypatch):
        """Returns None when blob does not exist."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_article_http_error(self, mock_settings, monkeypatch):
        """Returns None on HttpResponseError."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = HttpResponseError(message="error")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        result = await get_article("art-1")
        assert result is None


class TestWriteArticle:
    """Tests for write_article()."""

    @pytest.mark.asyncio
    async def test_new_article_added_to_index(self, mock_settings, monkeypatch):
        """New article is written and prepended to the index."""
        from api.models.article import Article, ArticleIndex

        article = Article(**_make_article_data("new-1", title="New Article"))

        # Track upload calls
        upload_calls = []
        mock_blob = MagicMock()
        mock_blob.upload_blob.side_effect = lambda *a, **kw: upload_calls.append(
            ("article", a, kw)
        )

        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        # Mock get_article_index to return empty index (must be async)
        async def mock_get_index(**kw):
            return ArticleIndex(articles=[], total=0)

        monkeypatch.setattr(
            "api.services.blob_storage.get_article_index", mock_get_index
        )

        # Mock write_article_index (must be async)
        written_articles = []

        async def mock_write_index(arts):
            written_articles.extend(arts)

        monkeypatch.setattr(
            "api.services.blob_storage.write_article_index", mock_write_index
        )

        await write_article(article)

        # Article blob was uploaded
        assert len(upload_calls) == 1
        # Index was updated with the new article
        assert len(written_articles) == 1
        assert written_articles[0].id == "new-1"

    @pytest.mark.asyncio
    async def test_existing_article_not_duplicated(self, mock_settings, monkeypatch):
        """Writing an article that already exists in the index doesn't duplicate it."""
        from api.models.article import Article, ArticleIndex

        article = Article(**_make_article_data("existing-1"))

        existing_summary = ArticleSummary(**_make_article_summary("existing-1"))

        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        async def mock_get_index(**kw):
            return ArticleIndex(articles=[existing_summary], total=1)

        monkeypatch.setattr(
            "api.services.blob_storage.get_article_index", mock_get_index
        )

        written_articles = []

        async def mock_write_index(arts):
            written_articles.extend(arts)

        monkeypatch.setattr(
            "api.services.blob_storage.write_article_index", mock_write_index
        )

        await write_article(article)

        # Index still has exactly one entry (no duplication)
        assert len(written_articles) == 1
        assert written_articles[0].id == "existing-1"


class TestWriteArticleOnly:
    """Tests for write_article_only()."""

    @pytest.mark.asyncio
    async def test_uploads_blob_without_index_update(self, mock_settings, monkeypatch):
        """Writes article blob but does not touch the index."""
        from api.models.article import Article

        article = Article(**_make_article_data("solo-1"))

        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_container_client",
            lambda: mock_container,
        )

        await write_article_only(article)

        mock_blob.upload_blob.assert_called_once()
        # Verify correct blob name
        mock_container.get_blob_client.assert_called_with("solo-1.json")


class TestGetBlogIndex:
    """Tests for get_blog_index()."""

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_settings, monkeypatch):
        """Returns blog posts from list-format index."""
        posts = [_make_blog_post("p1"), _make_blog_post("p2")]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(posts)

        monkeypatch.setattr(
            "api.services.blob_storage._get_blog_container_client",
            lambda: mock_container,
        )

        result = await get_blog_index()
        assert result.total == 2
        assert len(result.posts) == 2

    @pytest.mark.asyncio
    async def test_dict_format(self, mock_settings, monkeypatch):
        """Handles {"posts": [...]} format."""
        posts = [_make_blog_post("p1")]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(
            {"posts": posts}
        )

        monkeypatch.setattr(
            "api.services.blob_storage._get_blog_container_client",
            lambda: mock_container,
        )

        result = await get_blog_index()
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_offset_and_limit(self, mock_settings, monkeypatch):
        """Pagination works for blog index."""
        posts = [_make_blog_post(f"p{i}", slug=f"post-{i}") for i in range(4)]
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = _mock_blob_download(posts)

        monkeypatch.setattr(
            "api.services.blob_storage._get_blog_container_client",
            lambda: mock_container,
        )

        result = await get_blog_index(offset=1, limit=2)
        assert result.total == 4
        assert len(result.posts) == 2

    @pytest.mark.asyncio
    async def test_resource_not_found_returns_empty(self, mock_settings, monkeypatch):
        """ResourceNotFoundError returns empty blog index."""
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        monkeypatch.setattr(
            "api.services.blob_storage._get_blog_container_client",
            lambda: mock_container,
        )

        result = await get_blog_index()
        assert result.total == 0
        assert result.posts == []
