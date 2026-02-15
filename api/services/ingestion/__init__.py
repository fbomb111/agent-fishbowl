"""Ingestion services for fetching and processing articles."""

from api.services.ingestion.rss import (
    ParsedArticle,
    SourceConfig,
    fetch_all_sources,
    fetch_and_parse_source,
    fetch_feed,
    load_sources,
    parse_feed_entries,
)
from api.services.ingestion.summarizer import (
    SummarizationError,
    SummarizationResult,
    summarize_article,
)

__all__ = [
    "ParsedArticle",
    "SourceConfig",
    "SummarizationError",
    "SummarizationResult",
    "fetch_all_sources",
    "fetch_and_parse_source",
    "fetch_feed",
    "load_sources",
    "parse_feed_entries",
    "summarize_article",
]
