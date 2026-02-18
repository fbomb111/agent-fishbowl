"""Article scraper — fetches full article text from URLs using readability-lxml."""

import logging
import re
from dataclasses import dataclass

import httpx
from readability import Document

from api.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT = 15.0

# Minimum text length (characters) for a scrape to be considered successful
MIN_TEXT_LENGTH = 100


@dataclass
class ScrapedArticle:
    """Result of scraping an article URL."""

    text: str
    word_count: int


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    # Remove tags, keeping newlines for block elements
    text = re.sub(r"<(br|p|div|h[1-6]|li)[^>]*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace within lines
    lines = []
    for line in text.split("\n"):
        cleaned = " ".join(line.split())
        if cleaned:
            lines.append(cleaned)
    return "\n\n".join(lines)


async def scrape_article(url: str) -> ScrapedArticle | None:
    """Fetch a URL and extract the main article text.

    Uses Mozilla's Readability algorithm (via readability-lxml) to identify
    the main content, then strips HTML to plain text.

    Returns None on any failure — scraping is best-effort.
    """
    try:
        client = get_shared_client()
        response = await client.get(
            url,
            timeout=SCRAPE_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "AgentFishbowl/1.0 (Article Scraper)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()

        # Extract main content with readability
        doc = Document(response.text)
        content_html = doc.summary()

        # Convert to plain text
        text = _html_to_text(content_html)

        if not text or len(text) < MIN_TEXT_LENGTH:
            logger.debug("Scrape produced too little text for %s", url[:80])
            return None

        word_count = len(text.split())

        return ScrapedArticle(text=text, word_count=word_count)

    except httpx.HTTPStatusError as e:
        logger.debug("HTTP %d scraping %s", e.response.status_code, url[:80])
        return None
    except httpx.TimeoutException:
        logger.debug("Timeout scraping %s", url[:80])
        return None
    except Exception as e:
        logger.debug("Scrape failed for %s: %s", url[:80], e)
        return None
