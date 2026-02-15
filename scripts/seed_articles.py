"""Seed test articles to Azure Blob Storage.

Usage:
    python -m scripts.seed_articles
"""

import json
import uuid
from datetime import datetime, timezone

from azure.storage.blob import ContainerClient, ContentSettings

from api.config import get_settings

JSON_CONTENT = ContentSettings(content_type="application/json")

SEED_ARTICLES = [
    {
        "id": str(uuid.uuid4()),
        "title": "Claude 4 Sets New Benchmarks Across Reasoning and Coding Tasks",
        "source": "The Verge",
        "source_url": "https://www.theverge.com",
        "original_url": "https://www.theverge.com/2026/2/10/claude-4-benchmarks",
        "published_at": "2026-02-10T14:30:00Z",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Anthropic's latest model demonstrates significant improvements in multi-step reasoning, code generation, and instruction following. Early benchmarks show it outperforming previous models on complex agentic tasks.",
        "key_takeaways": [
            "Claude 4 scores 92% on SWE-bench, up from 85% for Claude 3.5",
            "Multi-step reasoning improved by 18% on complex chain-of-thought tasks",
            "Agentic workflow completion rates doubled in internal testing",
        ],
        "categories": ["llm", "benchmarks", "anthropic"],
        "image_url": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=600&h=400&fit=crop",
        "read_time_minutes": 4,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "GitHub Launches Agentic Workflows: AI Teams That Build Software",
        "source": "TechCrunch",
        "source_url": "https://techcrunch.com",
        "original_url": "https://techcrunch.com/2026/2/13/github-agentic-workflows",
        "published_at": "2026-02-13T09:00:00Z",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "summary": "GitHub's new Agentic Workflows feature lets developers define AI agent teams in Markdown files that run as GitHub Actions. Agents can create issues, open PRs, review code, and respond to events — all within the existing GitHub ecosystem.",
        "key_takeaways": [
            "Workflows defined in .md files with YAML frontmatter",
            "Supports Claude, Copilot, and Codex as execution engines",
            "Safe-outputs system ensures agents can't merge their own PRs",
        ],
        "categories": ["agents", "devtools", "github"],
        "image_url": "https://images.unsplash.com/photo-1618401471353-b98afee0b2eb?w=600&h=400&fit=crop",
        "read_time_minutes": 6,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "The Rise of Multi-Agent Systems in Enterprise Software",
        "source": "MIT Technology Review",
        "source_url": "https://www.technologyreview.com",
        "original_url": "https://www.technologyreview.com/2026/2/11/multi-agent-enterprise",
        "published_at": "2026-02-11T11:00:00Z",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Enterprise adoption of multi-agent AI systems is accelerating, with companies deploying teams of specialized agents for customer support, code review, and content generation. The pattern mirrors human team structures with role separation and handoffs.",
        "key_takeaways": [
            "67% of Fortune 500 companies are piloting multi-agent systems",
            "Agent-to-agent communication protocols are emerging as a standard",
            "Key challenge: observability and debugging across agent boundaries",
        ],
        "categories": ["agents", "enterprise", "research"],
        "image_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=600&h=400&fit=crop",
        "read_time_minutes": 8,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "OpenAI Introduces GPT-5 with Native Tool Use and Memory",
        "source": "Ars Technica",
        "source_url": "https://arstechnica.com",
        "original_url": "https://arstechnica.com/2026/2/12/gpt-5-native-tools",
        "published_at": "2026-02-12T16:45:00Z",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "summary": "OpenAI's GPT-5 introduces native tool use capabilities and persistent memory across sessions. The model can autonomously decide when to search the web, write code, or access files without explicit tool configuration.",
        "key_takeaways": [
            "Built-in tool use eliminates need for external function calling setup",
            "Persistent memory retains context across conversations",
            "Available through ChatGPT Pro and API with tiered pricing",
        ],
        "categories": ["llm", "openai", "tools"],
        "image_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=600&h=400&fit=crop",
        "read_time_minutes": 5,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "How to Build an AI Agent Team: Patterns from Production",
        "source": "Hacker News",
        "source_url": "https://news.ycombinator.com",
        "original_url": "https://simonwillison.net/2026/Feb/9/agent-team-patterns/",
        "published_at": "2026-02-09T08:15:00Z",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Simon Willison breaks down the practical patterns emerging for multi-agent orchestration: role separation, shared context management, escalation paths, and the critical importance of human-in-the-loop review for production deployments.",
        "key_takeaways": [
            "Role separation > general-purpose agents for production systems",
            "Shared context via structured documents beats agent-to-agent chat",
            "Human review gates are essential — fully autonomous agents aren't ready",
        ],
        "categories": ["agents", "engineering", "patterns"],
        "image_url": "https://images.unsplash.com/photo-1516110833967-0b5716ca1387?w=600&h=400&fit=crop",
        "read_time_minutes": 7,
    },
]


def main():
    """Upload seed articles to blob storage."""
    from azure.identity import DefaultAzureCredential

    settings = get_settings()
    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"
    client = ContainerClient(
        account_url=account_url,
        container_name=settings.azure_storage_container,
        credential=DefaultAzureCredential(),
    )

    print(
        f"Seeding {len(SEED_ARTICLES)} articles to {settings.azure_storage_account}/{settings.azure_storage_container}..."
    )

    # Upload individual articles
    for article in SEED_ARTICLES:
        blob_name = f"{article['id']}.json"
        blob = client.get_blob_client(blob_name)
        blob.upload_blob(
            json.dumps(article, indent=2),
            overwrite=True,
            content_settings=JSON_CONTENT,
        )
        print(f"  Uploaded: {article['title'][:60]}...")

    # Build and upload index (summary fields only)
    index_fields = [
        "id",
        "title",
        "source",
        "source_url",
        "original_url",
        "published_at",
        "summary",
        "categories",
        "image_url",
        "read_time_minutes",
    ]
    index = [
        {k: v for k, v in article.items() if k in index_fields}
        for article in sorted(
            SEED_ARTICLES, key=lambda a: a["published_at"], reverse=True
        )
    ]

    index_blob = client.get_blob_client("index.json")
    index_blob.upload_blob(
        json.dumps(index, indent=2),
        overwrite=True,
        content_settings=JSON_CONTENT,
    )
    print(f"  Uploaded: index.json ({len(index)} articles)")

    client.close()
    print("Done!")


if __name__ == "__main__":
    main()
