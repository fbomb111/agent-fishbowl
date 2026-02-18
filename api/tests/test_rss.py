"""Unit tests for RSS ingestion — parsing, images, dates, sources, errors."""

import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import feedparser
import httpx
import pytest

from api.services.ingestion.rss import (
    MAX_SUMMARY_LENGTH,
    SourceConfig,
    _extract_image_url,
    _extract_summary,
    _generate_article_id,
    _parse_published_date,
    fetch_and_parse_source,
    load_sources,
    parse_feed_entries,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_source() -> SourceConfig:
    return {
        "name": "Test Source",
        "url": "https://example.com/feed.xml",
        "categories": ["tech", "news"],
    }


@pytest.fixture
def sample_rss_feed() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>RSS Article One</title>
      <link>https://example.com/rss-1</link>
      <description>First RSS article.</description>
      <pubDate>Sat, 15 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>RSS Article Two</title>
      <link>https://example.com/rss-2</link>
      <description>Second RSS article.</description>
      <pubDate>Sat, 15 Feb 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_atom_feed() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <link href="https://example.com"/>
  <updated>2026-02-15T10:00:00Z</updated>
  <entry>
    <title>Atom Article One</title>
    <link href="https://example.com/atom-1"/>
    <id>urn:uuid:atom-article-1</id>
    <updated>2026-02-15T10:00:00Z</updated>
    <summary>Summary of the first Atom article.</summary>
  </entry>
  <entry>
    <title>Atom Article Two</title>
    <link href="https://example.com/atom-2"/>
    <id>urn:uuid:atom-article-2</id>
    <updated>2026-02-15T08:00:00Z</updated>
    <content type="html">&lt;p&gt;Content of the second Atom article.&lt;/p&gt;</content>
  </entry>
</feed>"""


@pytest.fixture
def feed_with_media_content() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Media Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article with Media Content</title>
      <link>https://example.com/media-article</link>
      <description>Article with media content image.</description>
      <media:content url="https://example.com/media-image.jpg" type="image/jpeg"/>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def feed_with_thumbnail() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Thumbnail Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article with Thumbnail</title>
      <link>https://example.com/thumb-article</link>
      <description>Article with thumbnail.</description>
      <media:thumbnail url="https://example.com/thumbnail.jpg"/>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def feed_with_enclosure() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Enclosure Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article with Enclosure</title>
      <link>https://example.com/enc-article</link>
      <description>Has an image enclosure.</description>
      <enclosure url="https://example.com/image.jpg" type="image/jpeg" length="12345"/>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def feed_with_missing_dates() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>No Dates Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article Without Date</title>
      <link>https://example.com/no-date</link>
      <description>This article has no publication date.</description>
    </item>
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# parse_feed_entries — RSS
# ---------------------------------------------------------------------------


class TestParseFeedEntries:
    def test_extracts_articles(self, sample_rss_feed: str, sample_source: SourceConfig) -> None:
        articles = parse_feed_entries(sample_rss_feed, sample_source)
        assert len(articles) == 2
        assert articles[0]["title"] == "RSS Article One"
        assert articles[0]["source"] == "Test Source"
        assert articles[0]["categories"] == ["tech", "news"]
        assert articles[0]["original_url"] == "https://example.com/rss-1"
        # ID should be a hex string derived from the URL
        assert len(articles[0]["id"]) == 16

    def test_skips_entries_without_link(self, sample_source: SourceConfig) -> None:
        feed_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test</title>
    <item>
      <title>No Link Entry</title>
      <description>Missing link</description>
    </item>
    <item>
      <title>Valid Entry</title>
      <link>https://example.com/valid</link>
      <description>Has link</description>
    </item>
  </channel>
</rss>"""
        articles = parse_feed_entries(feed_xml, sample_source)
        assert len(articles) == 1
        assert articles[0]["title"] == "Valid Entry"


# ---------------------------------------------------------------------------
# parse_feed_entries — Atom
# ---------------------------------------------------------------------------


class TestAtomFeedParsing:
    def test_parses_atom_entries(
        self, sample_atom_feed: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(sample_atom_feed, sample_source)

        assert len(articles) == 2
        assert articles[0]["title"] == "Atom Article One"
        assert articles[0]["original_url"] == "https://example.com/atom-1"
        assert "first Atom article" in articles[0]["summary"]

    def test_atom_content_used_as_summary(
        self, sample_atom_feed: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(sample_atom_feed, sample_source)

        # Second entry uses <content> instead of <summary>
        assert "second Atom article" in articles[1]["summary"]
        assert "<p>" not in articles[1]["summary"]


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------


class TestExtractSummary:
    def test_strips_html_and_truncates(self) -> None:
        entry = feedparser.FeedParserDict(
            {"summary": "<p>Hello <b>world</b></p>" + "x" * MAX_SUMMARY_LENGTH}
        )
        result = _extract_summary(entry)
        assert "<p>" not in result
        assert "<b>" not in result
        assert len(result) <= MAX_SUMMARY_LENGTH
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# _generate_article_id
# ---------------------------------------------------------------------------


class TestGenerateArticleId:
    def test_is_deterministic(self) -> None:
        id1 = _generate_article_id("https://example.com/article")
        id2 = _generate_article_id("https://example.com/article")
        id3 = _generate_article_id("https://example.com/different")
        assert id1 == id2
        assert id1 != id3


# ---------------------------------------------------------------------------
# _extract_image_url
# ---------------------------------------------------------------------------


class TestExtractImageUrl:
    def test_media_content(
        self, feed_with_media_content: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(feed_with_media_content, sample_source)

        assert len(articles) == 1
        assert articles[0]["image_url"] == "https://example.com/media-image.jpg"

    def test_thumbnail(
        self, feed_with_thumbnail: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(feed_with_thumbnail, sample_source)

        assert len(articles) == 1
        assert articles[0]["image_url"] == "https://example.com/thumbnail.jpg"

    def test_enclosure(
        self, feed_with_enclosure: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(feed_with_enclosure, sample_source)

        assert len(articles) == 1
        assert articles[0]["image_url"] == "https://example.com/image.jpg"

    def test_no_image_returns_none(self) -> None:
        entry = feedparser.FeedParserDict({})
        assert _extract_image_url(entry) is None


# ---------------------------------------------------------------------------
# _parse_published_date
# ---------------------------------------------------------------------------


class TestParsePublishedDate:
    def test_rss_pubdate(
        self, sample_rss_feed: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(sample_rss_feed, sample_source)

        assert articles[0]["published_at"].year == 2026
        assert articles[0]["published_at"].month == 2
        assert articles[0]["published_at"].day == 15
        assert articles[0]["published_at"].tzinfo == timezone.utc

    def test_atom_updated(
        self, sample_atom_feed: str, sample_source: SourceConfig
    ) -> None:
        articles = parse_feed_entries(sample_atom_feed, sample_source)

        assert articles[0]["published_at"].year == 2026
        assert articles[0]["published_at"].month == 2
        assert articles[0]["published_at"].tzinfo == timezone.utc

    def test_missing_date_uses_now(
        self, feed_with_missing_dates: str, sample_source: SourceConfig
    ) -> None:
        before = datetime.now(timezone.utc)
        articles = parse_feed_entries(feed_with_missing_dates, sample_source)
        after = datetime.now(timezone.utc)

        assert len(articles) == 1
        assert before <= articles[0]["published_at"] <= after

    def test_direct_call_with_empty_entry(self) -> None:
        entry = feedparser.FeedParserDict({})
        before = datetime.now(timezone.utc)
        result = _parse_published_date(entry)
        after = datetime.now(timezone.utc)

        assert before <= result <= after


# ---------------------------------------------------------------------------
# load_sources
# ---------------------------------------------------------------------------


class TestLoadSources:
    def test_loads_valid_yaml(self) -> None:
        yaml_content = """\
sources:
  - name: "Feed A"
    url: "https://example.com/a.xml"
    categories: ["tech"]
  - name: "Feed B"
    url: "https://example.com/b.xml"
    categories: ["news", "ai"]
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            sources = load_sources(f.name)

        assert len(sources) == 2
        assert sources[0]["name"] == "Feed A"
        assert sources[1]["categories"] == ["news", "ai"]

    def test_missing_sources_key_returns_empty(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("other_key: value\n")
            f.flush()
            sources = load_sources(f.name)

        assert sources == []

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_sources("/nonexistent/path/sources.yaml")


# ---------------------------------------------------------------------------
# fetch_and_parse_source — error handling
# ---------------------------------------------------------------------------


class TestFetchAndParseSource:
    @pytest.mark.asyncio
    async def test_http_error_returns_empty(
        self, sample_source: SourceConfig
    ) -> None:
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
    async def test_connection_error_returns_empty(
        self, sample_source: SourceConfig
    ) -> None:
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(
        self, sample_source: SourceConfig
    ) -> None:
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_successful_fetch(
        self, sample_source: SourceConfig, sample_rss_feed: str
    ) -> None:
        with patch(
            "api.services.ingestion.rss.fetch_feed",
            return_value=sample_rss_feed,
        ):
            articles = await fetch_and_parse_source(sample_source)

        assert len(articles) == 2
        assert articles[0]["title"] == "RSS Article One"
