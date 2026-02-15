"""Unit tests for the RSS ingestion service."""

import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from api.services.ingestion.rss import (
    SourceConfig,
    _extract_image_url,
    _extract_summary,
    fetch_and_parse_source,
    load_sources,
    parse_feed_entries,
)


class TestLoadSources:
    """Tests for load_sources function."""

    def test_load_sources_from_valid_file(self) -> None:
        """Test loading sources from a valid YAML file."""
        yaml_content = """
sources:
  - name: "Test Feed"
    url: "https://example.com/feed.xml"
    categories: ["tech"]
  - name: "Another Feed"
    url: "https://example.com/another.xml"
    categories: ["news", "ai"]
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            sources = load_sources(f.name)

        assert len(sources) == 2
        assert sources[0]["name"] == "Test Feed"
        assert sources[0]["url"] == "https://example.com/feed.xml"
        assert sources[0]["categories"] == ["tech"]
        assert sources[1]["name"] == "Another Feed"

    def test_load_sources_empty_file(self) -> None:
        """Test loading from a file with no sources key returns empty list."""
        yaml_content = "other_key: value\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            sources = load_sources(f.name)

        assert sources == []

    def test_load_sources_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            load_sources("/nonexistent/path/sources.yaml")


class TestParseFeedEntries:
    """Tests for parse_feed_entries function."""

    def test_parse_rss_feed(
        self, sample_rss_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test parsing a valid RSS 2.0 feed."""
        articles = parse_feed_entries(sample_rss_feed, sample_source)

        assert len(articles) == 2

        # First article
        assert articles[0]["title"] == "Test Article One"
        assert articles[0]["original_url"] == "https://example.com/article-1"
        assert articles[0]["source"] == "Test Source"
        assert articles[0]["categories"] == ["tech", "news"]
        # HTML should be stripped from description
        assert "first" in articles[0]["summary"]
        assert "<b>" not in articles[0]["summary"]

        # Second article
        assert articles[1]["title"] == "Test Article Two"
        assert articles[1]["original_url"] == "https://example.com/article-2"

    def test_parse_atom_feed(
        self, sample_atom_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test parsing a valid Atom feed."""
        articles = parse_feed_entries(sample_atom_feed, sample_source)

        assert len(articles) == 2

        # First article
        assert articles[0]["title"] == "Atom Article One"
        assert articles[0]["original_url"] == "https://example.com/atom-1"
        assert "first Atom article" in articles[0]["summary"]

        # Second article (uses content instead of summary)
        assert articles[1]["title"] == "Atom Article Two"
        assert "second Atom article" in articles[1]["summary"]
        # HTML should be stripped
        assert "<p>" not in articles[1]["summary"]

    def test_parse_empty_feed(
        self, empty_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test parsing a feed with no entries returns empty list."""
        articles = parse_feed_entries(empty_feed, sample_source)

        assert articles == []

    def test_skip_entries_missing_required_fields(
        self, feed_with_missing_required_fields: str, sample_source: SourceConfig
    ) -> None:
        """Test that entries without link or title are skipped."""
        articles = parse_feed_entries(
            feed_with_missing_required_fields, sample_source
        )

        # Only the complete article should be included
        assert len(articles) == 1
        assert articles[0]["title"] == "Complete Article"

    def test_article_id_is_generated(
        self, sample_rss_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test that articles get stable IDs generated from URL."""
        articles = parse_feed_entries(sample_rss_feed, sample_source)

        assert articles[0]["id"]
        assert len(articles[0]["id"]) == 16  # SHA256 hash truncated to 16 chars

        # Same URL should produce same ID
        articles_again = parse_feed_entries(sample_rss_feed, sample_source)
        assert articles[0]["id"] == articles_again[0]["id"]


class TestExtractSummary:
    """Tests for _extract_summary function."""

    def test_strips_html_tags(self) -> None:
        """Test that HTML tags are removed from summary."""
        import feedparser

        entry = feedparser.FeedParserDict(
            {"summary": "<p>Hello <b>world</b>!</p>"}
        )
        result = _extract_summary(entry)

        assert result == "Hello world!"
        assert "<" not in result
        assert ">" not in result

    def test_truncates_long_text(
        self, feed_with_long_summary: str, sample_source: SourceConfig
    ) -> None:
        """Test that summaries longer than 500 chars are truncated."""
        articles = parse_feed_entries(feed_with_long_summary, sample_source)

        assert len(articles) == 1
        assert len(articles[0]["summary"]) == 500  # 497 + "..."
        assert articles[0]["summary"].endswith("...")

    def test_uses_description_fallback(self) -> None:
        """Test using description when summary is not available."""
        import feedparser

        entry = feedparser.FeedParserDict({"description": "Fallback text"})
        result = _extract_summary(entry)

        assert result == "Fallback text"

    def test_uses_content_fallback(self) -> None:
        """Test using content when summary and description are not available."""
        import feedparser

        entry = feedparser.FeedParserDict(
            {"content": [{"value": "Content text"}]}
        )
        result = _extract_summary(entry)

        assert result == "Content text"

    def test_empty_entry_returns_empty_string(self) -> None:
        """Test that an entry with no summary-like fields returns empty string."""
        import feedparser

        entry = feedparser.FeedParserDict({})
        result = _extract_summary(entry)

        assert result == ""


class TestExtractImageUrl:
    """Tests for _extract_image_url function."""

    def test_extract_from_media_content(
        self, feed_with_media_content: str, sample_source: SourceConfig
    ) -> None:
        """Test extracting image from media:content element."""
        articles = parse_feed_entries(feed_with_media_content, sample_source)

        assert len(articles) == 1
        assert articles[0]["image_url"] == "https://example.com/media-image.jpg"

    def test_extract_from_thumbnail(
        self, feed_with_thumbnail: str, sample_source: SourceConfig
    ) -> None:
        """Test extracting image from media:thumbnail element."""
        articles = parse_feed_entries(feed_with_thumbnail, sample_source)

        assert len(articles) == 1
        assert articles[0]["image_url"] == "https://example.com/thumbnail.jpg"

    def test_extract_from_enclosure(
        self, sample_rss_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test extracting image from enclosure element."""
        articles = parse_feed_entries(sample_rss_feed, sample_source)

        # First article has an enclosure
        assert articles[0]["image_url"] == "https://example.com/image1.jpg"
        # Second article has no image
        assert articles[1]["image_url"] is None

    def test_no_image_returns_none(self) -> None:
        """Test that entry without image returns None."""
        import feedparser

        entry = feedparser.FeedParserDict({})
        result = _extract_image_url(entry)

        assert result is None


class TestParsePublishedDate:
    """Tests for _parse_published_date function."""

    def test_parse_rss_date(
        self, sample_rss_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test parsing RSS 2.0 pubDate format."""
        articles = parse_feed_entries(sample_rss_feed, sample_source)

        assert articles[0]["published_at"].year == 2026
        assert articles[0]["published_at"].month == 2
        assert articles[0]["published_at"].day == 15
        assert articles[0]["published_at"].tzinfo == timezone.utc

    def test_parse_atom_date(
        self, sample_atom_feed: str, sample_source: SourceConfig
    ) -> None:
        """Test parsing Atom updated date format."""
        articles = parse_feed_entries(sample_atom_feed, sample_source)

        assert articles[0]["published_at"].year == 2026
        assert articles[0]["published_at"].month == 2
        assert articles[0]["published_at"].tzinfo == timezone.utc

    def test_missing_date_uses_current_time(
        self, feed_with_missing_dates: str, sample_source: SourceConfig
    ) -> None:
        """Test that missing date falls back to current time."""
        before = datetime.now(timezone.utc)
        articles = parse_feed_entries(feed_with_missing_dates, sample_source)
        after = datetime.now(timezone.utc)

        assert len(articles) == 1
        assert before <= articles[0]["published_at"] <= after


class TestFetchAndParseSource:
    """Tests for fetch_and_parse_source function."""

    @pytest.mark.asyncio
    async def test_handles_http_error_gracefully(
        self, sample_source: SourceConfig
    ) -> None:
        """Test that HTTP errors return empty list instead of raising."""
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("GET", sample_source["url"]),
                response=httpx.Response(404),
            ),
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_handles_connection_error_gracefully(
        self, sample_source: SourceConfig
    ) -> None:
        """Test that connection errors return empty list instead of raising."""
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_handles_timeout_gracefully(
        self, sample_source: SourceConfig
    ) -> None:
        """Test that timeouts return empty list instead of raising."""
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_successful_fetch_returns_articles(
        self, sample_source: SourceConfig, sample_rss_feed: str
    ) -> None:
        """Test successful fetch and parse returns articles."""
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            return_value=sample_rss_feed,
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert len(articles) == 2
        assert articles[0]["title"] == "Test Article One"

