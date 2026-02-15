"""Ingestion services for fetching, scraping, and analyzing articles."""

from api.services.ingestion.analyzer import (
    AnalysisError,
    AnalysisResult,
    analyze_article,
)
from api.services.ingestion.rss import (
    ParsedArticle,
    SourceConfig,
    fetch_all_sources,
    fetch_and_parse_source,
    fetch_feed,
    load_sources,
    parse_feed_entries,
)
from api.services.ingestion.scraper import (
    ScrapedArticle,
    scrape_article,
)

__all__ = [
    "AnalysisError",
    "AnalysisResult",
    "ParsedArticle",
    "ScrapedArticle",
    "SourceConfig",
    "analyze_article",
    "fetch_all_sources",
    "fetch_and_parse_source",
    "fetch_feed",
    "load_sources",
    "parse_feed_entries",
    "scrape_article",
]
