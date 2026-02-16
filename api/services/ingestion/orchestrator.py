"""Article ingestion orchestrator — ties fetch, dedup, scrape, analyze, and write together."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from api.models.article import Article, ArticleSummary
from api.services.blob_storage import (
    get_article_index,
    write_article_index,
    write_article_only,
)
from api.services.ingestion.analyzer import AnalysisError, analyze_article
from api.services.ingestion.rss import fetch_all_sources, load_sources
from api.services.ingestion.scraper import scrape_article

logger = logging.getLogger(__name__)

# Cap new articles per run to limit AI API costs
MAX_NEW_ARTICLES_PER_RUN = 20

# Delay between articles to respect rate limits
INTER_ARTICLE_DELAY = 1.5


@dataclass
class IngestionStats:
    """Stats from an ingestion run."""

    sources: int
    fetched: int
    new: int
    scraped: int
    skipped: int
    failed: int

    def to_dict(self) -> dict:
        return {
            "sources": self.sources,
            "fetched": self.fetched,
            "new": self.new,
            "scraped": self.scraped,
            "skipped": self.skipped,
            "failed": self.failed,
        }


async def run_ingestion(max_new: int = MAX_NEW_ARTICLES_PER_RUN) -> IngestionStats:
    """Run a full ingestion cycle: fetch -> dedup -> scrape -> analyze -> write.

    Args:
        max_new: Maximum number of new articles to process per run.

    Returns:
        Stats from the ingestion run.
    """
    # 1. Load sources and fetch all RSS feeds
    logger.info("Starting ingestion run")
    sources = load_sources()
    source_count = len(sources)
    all_parsed = await fetch_all_sources(sources=sources)
    fetched_count = len(all_parsed)
    logger.info("Fetched %d articles from %d RSS sources", fetched_count, source_count)

    # 2. Load existing index for dedup
    index = await get_article_index()
    existing_ids = {a.id for a in index.articles}
    logger.info("Existing index has %d articles", len(existing_ids))

    # Keep a mutable copy of the index articles for batch update
    index_articles = list(index.articles)

    # 3. Filter to new articles only
    new_parsed = [a for a in all_parsed if a["id"] not in existing_ids]
    skipped = fetched_count - len(new_parsed)
    logger.info("%d new articles, %d already indexed", len(new_parsed), skipped)

    # 4. Cap to max_new
    if len(new_parsed) > max_new:
        logger.info("Capping to %d new articles (had %d)", max_new, len(new_parsed))
        new_parsed = new_parsed[:max_new]

    # 5. Scrape, analyze, and write each new article
    new_count = 0
    scraped_count = 0
    failed_count = 0

    for i, parsed in enumerate(new_parsed):
        try:
            # Rate limiting between articles
            if i > 0:
                await asyncio.sleep(INTER_ARTICLE_DELAY)

            # RSS description is always available for preview
            description = parsed["summary"]

            # Try scraping full article text
            scraped = await scrape_article(parsed["original_url"])
            has_full_text = scraped is not None
            if has_full_text:
                scraped_count += 1
                logger.info(
                    "Scraped %d words from: %s",
                    scraped.word_count,
                    parsed["title"][:60],
                )

            # Analyze with AI — full text if available, RSS description as fallback
            content_for_ai = scraped.text if has_full_text else description
            analysis = await analyze_article(
                title=parsed["title"],
                content=content_for_ai,
            )

            article = Article(
                id=parsed["id"],
                title=parsed["title"],
                source=parsed["source"],
                source_url=parsed["source_url"],
                original_url=parsed["original_url"],
                published_at=parsed["published_at"],
                description=description,
                categories=parsed["categories"],
                image_url=parsed["image_url"],
                insights=[
                    {"text": ins["text"], "category": ins["category"]}
                    for ins in analysis.insights
                ],
                ai_summary=analysis.ai_summary,
                has_full_text=has_full_text,
                ingested_at=datetime.now(timezone.utc),
            )

            # Write article JSON only (no index update per article)
            await write_article_only(article)
            new_count += 1

            # Update in-memory index
            summary = ArticleSummary(**article.model_dump())
            index_articles.insert(0, summary)

            insight_count = len(analysis.insights)
            logger.info(
                "Ingested: %s (%d insights, %s)",
                parsed["title"][:60],
                insight_count,
                "full text" if has_full_text else "RSS only",
            )

        except AnalysisError as e:
            failed_count += 1
            logger.error("Analysis failed for '%s': %s", parsed["title"][:60], e)
        except Exception as e:
            failed_count += 1
            logger.error("Failed to ingest '%s': %s", parsed["title"][:60], e)

    # 6. Flush index once after all articles are processed
    if new_count > 0:
        await write_article_index(index_articles)
        logger.info("Index updated with %d new articles", new_count)

    stats = IngestionStats(
        sources=source_count,
        fetched=fetched_count,
        new=new_count,
        scraped=scraped_count,
        skipped=skipped,
        failed=failed_count,
    )

    logger.info(
        "Ingestion complete: %d new, %d scraped, %d skipped, %d failed",
        new_count,
        scraped_count,
        skipped,
        failed_count,
    )

    return stats
