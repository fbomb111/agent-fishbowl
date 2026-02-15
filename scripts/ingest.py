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
    try:
        blob = client.get_blob_client(INDEX_BLOB)
        blob.upload_blob(
            "[]",
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        print("Cleared article index.")
    finally:
        client.close()


async def main() -> int:
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
    print(f"  Failed:   {stats.failed}")

    return 1 if stats.failed > 0 and stats.new == 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
