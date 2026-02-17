"""Tests for article deduplication logic."""

from datetime import datetime, timedelta, timezone

from api.models.article import ArticleSummary
from api.services.ingestion.dedup import (
    deduplicate_candidates,
    _is_duplicate,
    _title_similarity,
)
from api.services.ingestion.rss import ParsedArticle


def _make_parsed(article_id: str, title: str, summary: str = "") -> ParsedArticle:
    return {
        "id": article_id,
        "title": title,
        "source": "TestSource",
        "source_url": "https://test.com/feed",
        "original_url": f"https://test.com/{article_id}",
        "published_at": datetime.now(timezone.utc),
        "summary": summary,
        "categories": ["ai"],
        "image_url": None,
    }


def _make_existing(
    article_id: str,
    title: str,
    description: str = "",
    hours_ago: int = 0,
) -> ArticleSummary:
    return ArticleSummary(
        id=article_id,
        title=title,
        source="TestSource",
        source_url="https://test.com/feed",
        original_url=f"https://test.com/{article_id}",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        description=description,
        categories=["ai"],
    )


def test_identical_titles_are_duplicates():
    assert _is_duplicate("OpenAI launches GPT-5", "", "OpenAI launches GPT-5", "")


def test_very_similar_titles_are_duplicates():
    assert _is_duplicate(
        "OpenAI launches GPT-5 model",
        "",
        "OpenAI launches GPT-5",
        "",
    )


def test_completely_different_titles_are_not_duplicates():
    assert not _is_duplicate(
        "New Python release adds pattern matching",
        "",
        "OpenAI launches GPT-5",
        "",
    )


def test_title_similarity_identical():
    assert _title_similarity("hello world", "hello world") == 1.0


def test_title_similarity_different():
    assert _title_similarity("hello world", "goodbye universe") < 0.4


def test_dedup_removes_duplicate_from_existing():
    candidates = [
        _make_parsed("new-1", "OpenAI releases GPT-5"),
    ]
    existing = [
        _make_existing("old-1", "OpenAI releases GPT-5 today", hours_ago=12),
    ]

    unique, skipped = deduplicate_candidates(candidates, existing)

    assert len(unique) == 0
    assert len(skipped) == 1
    assert skipped[0][0] == "OpenAI releases GPT-5"


def test_dedup_keeps_unique_articles():
    candidates = [
        _make_parsed("new-1", "Python 3.13 released with new features"),
        _make_parsed("new-2", "Rust 2.0 announcement shakes systems programming"),
    ]
    existing = [
        _make_existing("old-1", "OpenAI releases GPT-5", hours_ago=12),
    ]

    unique, skipped = deduplicate_candidates(candidates, existing)

    assert len(unique) == 2
    assert len(skipped) == 0


def test_dedup_within_same_batch():
    candidates = [
        _make_parsed("src-a", "OpenAI launches GPT-5"),
        _make_parsed("src-b", "OpenAI launches GPT-5 model"),
    ]

    unique, skipped = deduplicate_candidates(candidates, [])

    assert len(unique) == 1
    assert len(skipped) == 1
    assert unique[0]["id"] == "src-a"  # First one kept


def test_dedup_ignores_old_existing_articles():
    """Articles outside the 48-hour window should not trigger dedup."""
    candidates = [
        _make_parsed("new-1", "OpenAI releases GPT-5"),
    ]
    existing = [
        _make_existing("old-1", "OpenAI releases GPT-5", hours_ago=72),
    ]

    unique, skipped = deduplicate_candidates(candidates, existing)

    assert len(unique) == 1
    assert len(skipped) == 0


def test_dedup_returns_match_info():
    candidates = [
        _make_parsed("new-1", "Google announces Gemini 3"),
    ]
    existing = [
        _make_existing("old-1", "Google announces Gemini 3 model", hours_ago=6),
    ]

    _, skipped = deduplicate_candidates(candidates, existing)

    assert len(skipped) == 1
    skipped_title, matched_title = skipped[0]
    assert skipped_title == "Google announces Gemini 3"
    assert matched_title == "Google announces Gemini 3 model"
