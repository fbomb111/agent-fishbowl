"""Tests for the ingestion orchestrator — dedup, capping, failure handling."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from api.models.article import ArticleIndex, ArticleSummary
from api.services.ingestion.analyzer import AnalysisError, AnalysisResult
from api.services.ingestion.scraper import ScrapedArticle


def _make_parsed(article_id, title="Test Article"):
    return {
        "id": article_id,
        "title": title,
        "source": "Test",
        "source_url": "https://test.com/feed",
        "original_url": f"https://test.com/{article_id}",
        "published_at": datetime.now(timezone.utc),
        "summary": "A test article summary for testing purposes",
        "categories": ["ai"],
        "image_url": None,
    }


def _make_summary(article_id):
    return ArticleSummary(
        id=article_id,
        title="Existing",
        source="Test",
        source_url="https://test.com/feed",
        original_url=f"https://test.com/{article_id}",
        published_at=datetime.now(timezone.utc),
        description="Existing article",
        categories=["ai"],
    )


def _mock_orchestrator_deps(mocker, existing_ids=None, parsed_articles=None):
    """Set up all orchestrator external dependencies as mocks."""
    existing_ids = existing_ids or []
    parsed_articles = parsed_articles or []

    mocker.patch(
        "api.services.ingestion.orchestrator.load_sources",
        return_value=[
            {"name": "Test", "url": "https://test.com/feed", "categories": ["ai"]}
        ],
    )
    mocker.patch(
        "api.services.ingestion.orchestrator.fetch_all_sources",
        new_callable=AsyncMock,
        return_value=parsed_articles,
    )
    mocker.patch(
        "api.services.ingestion.orchestrator.get_article_index",
        new_callable=AsyncMock,
        return_value=ArticleIndex(
            articles=[_make_summary(aid) for aid in existing_ids],
            total=len(existing_ids),
        ),
    )
    # Default dedup mock: pass through all candidates (no duplicates)
    mocker.patch(
        "api.services.ingestion.orchestrator.deduplicate_candidates",
        side_effect=lambda candidates, existing: (candidates, []),
    )
    mocker.patch(
        "api.services.ingestion.orchestrator.scrape_article",
        new_callable=AsyncMock,
        return_value=ScrapedArticle(text="Scraped content here", word_count=50),
    )
    mock_analyze = mocker.patch(
        "api.services.ingestion.orchestrator.analyze_article",
        new_callable=AsyncMock,
        return_value=AnalysisResult(
            insights=[{"text": "Test insight", "category": "tool"}],
            ai_summary="Test summary of the article.",
            relevance_score=7,
        ),
    )
    mock_write_only = mocker.patch(
        "api.services.ingestion.orchestrator.write_article_only",
        new_callable=AsyncMock,
    )
    mock_write_index = mocker.patch(
        "api.services.ingestion.orchestrator.write_article_index",
        new_callable=AsyncMock,
    )
    # Eliminate sleep between articles in tests
    mocker.patch(
        "api.services.ingestion.orchestrator.asyncio.sleep", new_callable=AsyncMock
    )

    return mock_analyze, mock_write_only, mock_write_index


async def test_deduplicates_existing_articles(mocker):
    from api.services.ingestion.orchestrator import run_ingestion

    parsed = [
        _make_parsed("existing-1"),
        _make_parsed("existing-2"),
        _make_parsed("new-1"),
    ]
    mock_analyze, mock_write_only, mock_write_index = _mock_orchestrator_deps(
        mocker,
        existing_ids=["existing-1", "existing-2"],
        parsed_articles=parsed,
    )

    stats = await run_ingestion()

    assert stats.new == 1
    assert stats.skipped == 2
    assert stats.duplicates_removed == 0
    assert mock_analyze.call_count == 1
    assert mock_write_only.call_count == 1
    mock_write_index.assert_called_once()
    # The index should have 3 articles (1 new + 2 existing)
    written_articles = mock_write_index.call_args[0][0]
    assert len(written_articles) == 3


async def test_caps_at_max_new(mocker):
    from api.services.ingestion.orchestrator import run_ingestion

    parsed = [_make_parsed(f"article-{i}") for i in range(30)]
    mock_analyze, mock_write_only, _ = _mock_orchestrator_deps(
        mocker,
        existing_ids=[],
        parsed_articles=parsed,
    )

    stats = await run_ingestion(max_new=5)

    assert stats.new == 5
    assert mock_analyze.call_count == 5
    assert mock_write_only.call_count == 5


async def test_handles_analysis_failure_gracefully(mocker):
    from api.services.ingestion.orchestrator import run_ingestion

    parsed = [_make_parsed("fail-1"), _make_parsed("succeed-1")]

    _mock_orchestrator_deps(mocker, existing_ids=[], parsed_articles=parsed)

    # Override analyze_article to fail on first, succeed on second
    call_count = 0

    async def _analyze_side_effect(title, content):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AnalysisError("LLM timeout")
        return AnalysisResult(insights=[], ai_summary=None)

    mocker.patch(
        "api.services.ingestion.orchestrator.analyze_article",
        side_effect=_analyze_side_effect,
    )

    stats = await run_ingestion()

    assert stats.new == 1
    assert stats.failed == 1
    # Index should still be written for the successful article
    from api.services.ingestion.orchestrator import write_article_index

    write_article_index.assert_called_once()


async def test_topic_dedup_removes_duplicate_stories(mocker):
    """Topic-based dedup removes articles covering the same story."""
    from api.services.ingestion.orchestrator import run_ingestion

    parsed = [
        _make_parsed("article-a", title="OpenAI launches GPT-5"),
        _make_parsed("article-b", title="OpenAI launches GPT-5 today"),
        _make_parsed("article-c", title="Completely different story"),
    ]

    mock_analyze, mock_write_only, _ = _mock_orchestrator_deps(
        mocker, existing_ids=[], parsed_articles=parsed
    )

    # Override dedup mock to simulate removing one duplicate
    mocker.patch(
        "api.services.ingestion.orchestrator.deduplicate_candidates",
        return_value=(
            [parsed[0], parsed[2]],  # keep first and third
            [("OpenAI launches GPT-5 today", "OpenAI launches GPT-5")],
        ),
    )

    stats = await run_ingestion()

    assert stats.duplicates_removed == 1
    assert stats.new == 2
    assert mock_analyze.call_count == 2
    assert mock_write_only.call_count == 2


async def test_duplicates_removed_in_stats(mocker):
    """duplicates_removed field appears in stats dict."""
    from api.services.ingestion.orchestrator import run_ingestion

    _mock_orchestrator_deps(mocker, existing_ids=[], parsed_articles=[])

    stats = await run_ingestion()

    stats_dict = stats.to_dict()
    assert "duplicates_removed" in stats_dict
    assert stats_dict["duplicates_removed"] == 0


async def test_filters_low_relevance_articles(mocker):
    """Articles below the relevance threshold are filtered out."""
    from api.services.ingestion.orchestrator import run_ingestion

    parsed = [
        _make_parsed("low-relevance"),
        _make_parsed("high-relevance"),
    ]

    mock_analyze, mock_write_only, mock_write_index = _mock_orchestrator_deps(
        mocker, existing_ids=[], parsed_articles=parsed
    )

    # First article scores below threshold (3), second scores at threshold (4)
    mock_analyze.side_effect = [
        AnalysisResult(
            insights=[{"text": "Insight", "category": "tool"}],
            ai_summary="Summary",
            relevance_score=3,
        ),
        AnalysisResult(
            insights=[{"text": "Insight", "category": "tool"}],
            ai_summary="Summary",
            relevance_score=4,
        ),
    ]

    stats = await run_ingestion()

    assert stats.new == 1  # Only high-relevance article ingested
    assert stats.filtered == 1  # Low-relevance article filtered
    assert mock_analyze.call_count == 2  # Both analyzed
    assert mock_write_only.call_count == 1  # Only one written
    mock_write_index.assert_called_once()
