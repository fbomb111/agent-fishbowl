"""RSS feed ingestion service for fetching and parsing articles."""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import feedparser
import httpx
import yaml

from api.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests
REQUEST_TIMEOUT = 30.0

# Maximum length for article summaries before truncation
MAX_SUMMARY_LENGTH = 500


class SourceConfig(TypedDict):
    """RSS source configuration from sources.yaml."""

    name: str
    url: str
    categories: list[str]


class ParsedArticle(TypedDict):
    """Parsed article data from RSS feed."""

    id: str
    title: str
    source: str
    source_url: str
    original_url: str
    published_at: datetime
    summary: str
    categories: list[str]
    image_url: str | None


def load_sources(config_path: str | None = None) -> list[SourceConfig]:
    """Load RSS sources from config/sources.yaml.

    Args:
        config_path: Optional path to sources.yaml. Defaults to config/sources.yaml.

    Returns:
        List of source configurations.

    Raises:
        FileNotFoundError: If the sources file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    if config_path is None:
        # Default to project root config/sources.yaml
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = str(project_root / "config" / "sources.yaml")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("sources", [])


def _generate_article_id(url: str) -> str:
    """Generate a stable article ID from its URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_published_date(entry: feedparser.FeedParserDict) -> datetime:
    """Parse the published date from a feed entry.

    Handles both RSS 2.0 (published_parsed) and Atom (updated_parsed) formats.
    Falls back to current time if no date is available.
    """
    # Try published_parsed first (RSS 2.0), then updated_parsed (Atom)
    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")

    if time_struct:
        try:
            return datetime(*time_struct[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError) as e:
            logger.warning("Failed to parse date from entry: %s", e)

    return datetime.now(timezone.utc)


def _extract_image_url(entry: feedparser.FeedParserDict) -> str | None:
    """Extract image URL from feed entry if available.

    Checks media_content, media_thumbnail, and enclosures.
    """
    # Check media_content (common in media RSS extensions)
    media_content = entry.get("media_content", [])
    for media in media_content:
        if media.get("type", "").startswith("image/"):
            return media.get("url")

    # Check media_thumbnail
    media_thumbnails = entry.get("media_thumbnail", [])
    if media_thumbnails:
        return media_thumbnails[0].get("url")

    # Check enclosures
    enclosures = entry.get("enclosures", [])
    for enclosure in enclosures:
        if enclosure.get("type", "").startswith("image/"):
            return enclosure.get("href")

    return None


def _extract_summary(entry: feedparser.FeedParserDict) -> str:
    """Extract summary/description from feed entry.

    Tries summary first, then description, then content.
    Strips HTML tags for plain text output.
    """
    # Try summary first (Atom), then description (RSS 2.0)
    summary = entry.get("summary") or entry.get("description") or ""

    # If content is available and summary is empty, use first content block
    if not summary and entry.get("content"):
        content = entry.get("content", [])
        if content:
            summary = content[0].get("value", "")

    # Basic HTML stripping - feedparser often returns HTML
    # A more robust solution would use a proper HTML parser
    if summary:
        summary = re.sub(r"<[^>]+>", "", summary)
        summary = summary.strip()

        # Truncate to reasonable length
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[: MAX_SUMMARY_LENGTH - 3] + "..."

    return summary


def parse_feed_entries(
    feed_data: str,
    source: SourceConfig,
) -> list[ParsedArticle]:
    """Parse RSS/Atom feed data into article structures.

    Args:
        feed_data: Raw feed XML/data as string.
        source: Source configuration containing name, url, and categories.

    Returns:
        List of parsed articles.
    """
    parsed = feedparser.parse(feed_data)

    if parsed.bozo and parsed.bozo_exception:
        logger.warning(
            "Feed parsing warning for %s: %s",
            source["name"],
            parsed.bozo_exception,
        )

    articles: list[ParsedArticle] = []

    for entry in parsed.entries:
        # Skip entries without required fields
        link = entry.get("link")
        title = entry.get("title")

        if not link or not title:
            logger.debug("Skipping entry without link or title")
            continue

        article: ParsedArticle = {
            "id": _generate_article_id(link),
            "title": title.strip(),
            "source": source["name"],
            "source_url": source["url"],
            "original_url": link,
            "published_at": _parse_published_date(entry),
            "summary": _extract_summary(entry),
            "categories": source.get("categories", []),
            "image_url": _extract_image_url(entry),
        }

        articles.append(article)

    return articles


async def fetch_feed(url: str, timeout: float = REQUEST_TIMEOUT) -> str:
    """Fetch RSS feed content from URL.

    Args:
        url: The RSS feed URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Feed content as string.

    Raises:
        httpx.HTTPError: On network or HTTP errors.
    """
    client = get_shared_client()
    response = await client.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": "AgentFishbowl/1.0 (RSS Aggregator)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    response.raise_for_status()
    return response.text


async def fetch_and_parse_source(source: SourceConfig) -> list[ParsedArticle]:
    """Fetch and parse articles from a single RSS source.

    Args:
        source: Source configuration with name, url, and categories.

    Returns:
        List of parsed articles from the source.
        Returns empty list on error (logged, not raised).
    """
    try:
        feed_data = await fetch_feed(source["url"])
        articles = parse_feed_entries(feed_data, source)
        logger.info(
            "Fetched %d articles from %s",
            len(articles),
            source["name"],
        )
        return articles
    except httpx.HTTPError as e:
        logger.error(
            "HTTP error fetching %s: %s",
            source["name"],
            e,
        )
        return []
    except Exception as e:
        logger.error(
            "Unexpected error processing %s: %s",
            source["name"],
            e,
        )
        return []


async def fetch_all_sources(
    sources: list[SourceConfig] | None = None,
) -> list[ParsedArticle]:
    """Fetch and parse articles from all configured RSS sources.

    Args:
        sources: Optional list of sources. If not provided, loads from config.

    Returns:
        Combined list of all parsed articles from all sources.
    """
    if sources is None:
        sources = load_sources()

    results = await asyncio.gather(
        *[fetch_and_parse_source(source) for source in sources],
        return_exceptions=True,
    )

    all_articles: list[ParsedArticle] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Unexpected error during parallel fetch: %s", result)
            continue
        all_articles.extend(result)

    # Sort by published date, newest first
    all_articles.sort(key=lambda a: a["published_at"], reverse=True)

    logger.info("Total articles fetched: %d", len(all_articles))
    return all_articles
