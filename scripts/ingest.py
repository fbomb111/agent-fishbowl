"""Run article ingestion from the command line.

Usage:
    python -m scripts.ingest
"""

import asyncio
import logging
import sys

from api.services.ingestion.orchestrator import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> int:
    print("Starting article ingestion...")
    stats = await run_ingestion()

    print("\nIngestion complete:")
    print(f"  Sources:  {stats.sources}")
    print(f"  Fetched:  {stats.fetched}")
    print(f"  New:      {stats.new}")
    print(f"  Skipped:  {stats.skipped}")
    print(f"  Failed:   {stats.failed}")

    return 1 if stats.failed > 0 and stats.new == 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
