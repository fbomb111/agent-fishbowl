"""Tests for RSS feed parsing — pure functions, no external calls."""

from api.services.ingestion.rss import (
    MAX_SUMMARY_LENGTH,
    _extract_summary,
    _generate_article_id,
    parse_feed_entries,
)

# Minimal valid RSS for feedparser
_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Article</title>
      <link>https://example.com/article-1</link>
      <description>Description one</description>
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/article-2</link>
      <description>Description two</description>
    </item>
  </channel>
</rss>
"""

_SOURCE = {
    "name": "Test Source",
    "url": "https://example.com/feed",
    "categories": ["ai", "dev"],
}


def test_parse_feed_entries_extracts_articles():
    articles = parse_feed_entries(_FEED_XML, _SOURCE)
    assert len(articles) == 2
    assert articles[0]["title"] == "First Article"
    assert articles[0]["source"] == "Test Source"
    assert articles[0]["categories"] == ["ai", "dev"]
    assert articles[0]["original_url"] == "https://example.com/article-1"
    # ID should be a hex string derived from the URL
    assert len(articles[0]["id"]) == 16


def test_skips_entries_without_link():
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
</rss>
"""
    articles = parse_feed_entries(feed_xml, _SOURCE)
    assert len(articles) == 1
    assert articles[0]["title"] == "Valid Entry"


def test_extract_summary_strips_html_and_truncates():
    # Create a feedparser-like dict with HTML content
    entry = {"summary": "<p>Hello <b>world</b></p>" + "x" * MAX_SUMMARY_LENGTH}
    result = _extract_summary(entry)
    assert "<p>" not in result
    assert "<b>" not in result
    assert len(result) <= MAX_SUMMARY_LENGTH
    assert result.endswith("...")


def test_generate_article_id_is_deterministic():
    id1 = _generate_article_id("https://example.com/article")
    id2 = _generate_article_id("https://example.com/article")
    id3 = _generate_article_id("https://example.com/different")
    assert id1 == id2
    assert id1 != id3
