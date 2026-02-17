"""Article deduplication — detect duplicate coverage across sources."""

import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from api.models.article import ArticleSummary
from api.services.ingestion.rss import ParsedArticle

logger = logging.getLogger(__name__)

# Minimum title similarity ratio to consider articles as duplicates
TITLE_SIMILARITY_THRESHOLD = 0.6

# Combined (title + summary) similarity threshold
COMBINED_SIMILARITY_THRESHOLD = 0.5

# How far back to check for duplicates
DEDUP_WINDOW_HOURS = 48


def _normalize(text: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    return text.strip().lower()


def _title_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two titles."""
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _summary_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two summaries."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _is_duplicate(
    candidate_title: str,
    candidate_summary: str,
    existing_title: str,
    existing_summary: str,
) -> bool:
    """Check if a candidate article is a duplicate of an existing one.

    Uses a combination of title and summary similarity.
    """
    title_sim = _title_similarity(candidate_title, existing_title)

    # High title similarity alone is enough
    if title_sim >= TITLE_SIMILARITY_THRESHOLD:
        return True

    # Check combined similarity for borderline title matches
    summary_sim = _summary_similarity(candidate_summary, existing_summary)
    combined = (title_sim * 0.7) + (summary_sim * 0.3)
    return combined >= COMBINED_SIMILARITY_THRESHOLD


def deduplicate_candidates(
    candidates: list[ParsedArticle],
    existing_articles: list[ArticleSummary],
) -> tuple[list[ParsedArticle], list[tuple[str, str]]]:
    """Remove candidate articles that duplicate existing or other candidate articles.

    Compares each candidate against:
    1. Existing articles from the index (published within the dedup window)
    2. Earlier candidates in the same batch (to avoid ingesting two versions
       of the same story from different sources in the same run)

    When a duplicate is found, the existing/earlier article is kept.

    Args:
        candidates: New articles to check for duplicates.
        existing_articles: Articles already in the index.

    Returns:
        Tuple of (unique candidates, list of (skipped_title, matched_title) pairs).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)

    # Filter existing articles to the dedup window
    recent_existing = [
        a for a in existing_articles if a.published_at >= cutoff
    ]

    unique: list[ParsedArticle] = []
    skipped: list[tuple[str, str]] = []

    for candidate in candidates:
        matched_title: str | None = None

        # Check against recent existing articles
        for existing in recent_existing:
            if _is_duplicate(
                candidate["title"],
                candidate["summary"],
                existing.title,
                existing.description,
            ):
                matched_title = existing.title
                break

        # Check against already-accepted candidates in this batch
        if matched_title is None:
            for accepted in unique:
                if _is_duplicate(
                    candidate["title"],
                    candidate["summary"],
                    accepted["title"],
                    accepted["summary"],
                ):
                    matched_title = accepted["title"]
                    break

        if matched_title is not None:
            skipped.append((candidate["title"], matched_title))
            logger.info(
                "Duplicate skipped: '%s' matches '%s'",
                candidate["title"][:60],
                matched_title[:60],
            )
        else:
            unique.append(candidate)

    return unique, skipped
