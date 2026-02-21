"""Run article ingestion from the command line.

Usage:
    python -m scripts.ingest           # Normal run (skips existing articles)
    python -m scripts.ingest --force   # Clear index and re-ingest all
"""

import asyncio
import logging
import sys

from api.services.ingestion.orchestrator import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def _clear_index() -> None:
    """Clear the article index to force re-ingestion."""
    from api.services.blob_storage import _get_container_client, INDEX_BLOB
    from azure.storage.blob import ContentSettings

    client = _get_container_client()
    blob = client.get_blob_client(INDEX_BLOB)
    blob.upload_blob(
        "[]",
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    print("Cleared article index.")


async def main() -> int:
    from datetime import datetime, timezone

    force = "--force" in sys.argv

    if force:
        print("Force mode: clearing article index...")
        await _clear_index()

    print("Starting article ingestion...")
    stats = await run_ingestion()

    print("\nIngestion complete:")
    print(f"  Sources:  {stats.sources}")
    print(f"  Fetched:  {stats.fetched}")
    print(f"  New:      {stats.new}")
    print(f"  Scraped:  {stats.scraped}")
    print(f"  Skipped:  {stats.skipped}")
    print(f"  Dupes:    {stats.duplicates_removed}")
    print(f"  Filtered: {stats.filtered}")
    print(f"  Failed:   {stats.failed}")

    # Check article freshness
    from api.services.blob_storage import get_article_index

    index = await get_article_index()
    if index.articles:
        newest = max(index.articles, key=lambda a: a.published_at)
        hours_old = (datetime.now(timezone.utc) - newest.published_at).total_seconds() / 3600
        print(f"\nNewest article: {newest.published_at.isoformat()} ({hours_old:.1f}h ago)")

        if hours_old > 48:
            print(f"ERROR: Articles critically stale (>{hours_old:.1f}h old)")
            return 1

    # Fail if there were failures and no new articles
    if stats.failed > 0 and stats.new == 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
