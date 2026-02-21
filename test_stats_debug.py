"""Debug script to test stats endpoint PR counting."""

import asyncio
from datetime import datetime, timedelta, timezone
from api.services.http_client import fetch_merged_prs
from api.config import get_settings


async def main():
    settings = get_settings()
    repo = settings.github_repo

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    since_str = since.strftime("%Y-%m-%d")

    print(f"Fetching PRs for repo: {repo}")
    print(f"Since: {since_str}")
    print(f"Now: {now.isoformat()}")

    prs = await fetch_merged_prs(repo, since_str)

    if prs is None:
        print("\nERROR: fetch_merged_prs returned None")
    elif len(prs) == 0:
        print("\nWARNING: fetch_merged_prs returned empty list")
    else:
        print(f"\nSUCCESS: Found {len(prs)} merged PRs")
        for pr in prs[:5]:
            print(f"  PR #{pr.get('number')}: merged_at={pr.get('merged_at')}")


if __name__ == "__main__":
    asyncio.run(main())
