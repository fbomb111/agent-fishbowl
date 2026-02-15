"""Article ingestion orchestrator — ties fetch, dedup, summarize, and write together."""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

from api.models.article import Article
from api.services.blob_storage import get_article_index, write_article
from api.services.ingestion.rss import fetch_all_sources
from api.services.ingestion.summarizer import summarize_article, SummarizationError

logger = logging.getLogger(__name__)

# Cap new articles per run to limit AI API costs
MAX_NEW_ARTICLES_PER_RUN = 20


@dataclass
class IngestionStats:
    """Stats from an ingestion run."""

    sources: int
    fetched: int
    new: int
    skipped: int
    failed: int

    def to_dict(self) -> dict:
        return {
            "sources": self.sources,
            "fetched": self.fetched,
            "new": self.new,
            "skipped": self.skipped,
            "failed": self.failed,
        }


async def run_ingestion(max_new: int = MAX_NEW_ARTICLES_PER_RUN) -> IngestionStats:
    """Run a full ingestion cycle: fetch → dedup → summarize → write.

    Args:
        max_new: Maximum number of new articles to process per run.

    Returns:
        Stats from the ingestion run.
    """
    # 1. Fetch all RSS feeds
    logger.info("Starting ingestion run")
    all_parsed = await fetch_all_sources()
    fetched_count = len(all_parsed)
    logger.info("Fetched %d articles from RSS feeds", fetched_count)

    # 2. Load existing index for dedup
    index = await get_article_index()
    existing_ids = {a.id for a in index.articles}
    logger.info("Existing index has %d articles", len(existing_ids))

    # 3. Filter to new articles only
    new_parsed = [a for a in all_parsed if a["id"] not in existing_ids]
    skipped = fetched_count - len(new_parsed)
    logger.info("%d new articles, %d already indexed", len(new_parsed), skipped)

    # 4. Cap to max_new
    if len(new_parsed) > max_new:
        logger.info("Capping to %d new articles (had %d)", max_new, len(new_parsed))
        new_parsed = new_parsed[:max_new]

    # 5. Summarize and write each new article
    new_count = 0
    failed_count = 0

    for parsed in new_parsed:
        try:
            result = await summarize_article(
                title=parsed["title"],
                content=parsed["summary"],
            )

            article = Article(
                id=parsed["id"],
                title=parsed["title"],
                source=parsed["source"],
                source_url=parsed["source_url"],
                original_url=parsed["original_url"],
                published_at=parsed["published_at"],
                summary=result.summary,
                key_takeaways=result.key_takeaways,
                categories=parsed["categories"],
                image_url=parsed["image_url"],
                ingested_at=datetime.now(timezone.utc),
            )

            await write_article(article)
            new_count += 1
            logger.info("Ingested: %s", parsed["title"][:80])

        except SummarizationError as e:
            failed_count += 1
            logger.error("Summarization failed for '%s': %s", parsed["title"][:60], e)
        except Exception as e:
            failed_count += 1
            logger.error("Failed to ingest '%s': %s", parsed["title"][:60], e)

    stats = IngestionStats(
        sources=5,  # from config/sources.yaml
        fetched=fetched_count,
        new=new_count,
        skipped=skipped,
        failed=failed_count,
    )

    logger.info(
        "Ingestion complete: %d new, %d skipped, %d failed",
        new_count,
        skipped,
        failed_count,
    )

    return stats
