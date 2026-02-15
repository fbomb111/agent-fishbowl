"""Shared test fixtures for API tests."""

import pytest

from api.services.ingestion.rss import SourceConfig


@pytest.fixture
def sample_source() -> SourceConfig:
    """Sample source configuration for testing."""
    return {
        "name": "Test Source",
        "url": "https://example.com/feed.xml",
        "categories": ["tech", "news"],
    }


@pytest.fixture
def sample_rss_feed() -> str:
    """Sample RSS 2.0 feed for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>Test Article One</title>
      <link>https://example.com/article-1</link>
      <description>&lt;p&gt;This is the &lt;b&gt;first&lt;/b&gt; article.&lt;/p&gt;</description>
      <pubDate>Sat, 15 Feb 2026 10:00:00 GMT</pubDate>
      <enclosure url="https://example.com/image1.jpg" type="image/jpeg" length="12345"/>
    </item>
    <item>
      <title>Test Article Two</title>
      <link>https://example.com/article-2</link>
      <description>This is the second article with no HTML.</description>
      <pubDate>Sat, 15 Feb 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_atom_feed() -> str:
    """Sample Atom feed for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
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
    """RSS feed with media:content element for image extraction testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
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
    """RSS feed with media:thumbnail element for image extraction testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
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
def feed_with_missing_dates() -> str:
    """RSS feed with entries missing publication dates."""
    return """<?xml version="1.0" encoding="UTF-8"?>
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


@pytest.fixture
def feed_with_long_summary() -> str:
    """RSS feed with a very long summary that should be truncated."""
    long_text = "A" * 600  # Longer than 500 char limit
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Long Summary Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article with Long Summary</title>
      <link>https://example.com/long-summary</link>
      <description>{long_text}</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def empty_feed() -> str:
    """RSS feed with no entries."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
    <link>https://example.com</link>
    <description>A feed with no items</description>
  </channel>
</rss>"""


@pytest.fixture
def feed_with_missing_required_fields() -> str:
    """RSS feed with entries missing required link or title."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Incomplete Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article Without Link</title>
      <description>This article has no link.</description>
    </item>
    <item>
      <link>https://example.com/no-title</link>
      <description>This article has no title.</description>
    </item>
    <item>
      <title>Complete Article</title>
      <link>https://example.com/complete</link>
      <description>This article has both.</description>
    </item>
  </channel>
</rss>"""

