"""Azure Blob Storage service for reading/writing article data."""

import json
import logging

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import ContainerClient, ContentSettings

from api.config import get_settings
from api.models.article import Article, ArticleIndex, ArticleSummary
from api.models.blog import BlogIndex, BlogPost

logger = logging.getLogger(__name__)

INDEX_BLOB = "index.json"
BLOG_INDEX_BLOB = "blog-index.json"

# Lazy singleton — lives for the process lifetime
_container_client: ContainerClient | None = None


def _get_container_client() -> ContainerClient:
    """Return a shared blob container client (lazy singleton).

    Uses User-Assigned Managed Identity for authentication.
    """
    global _container_client
    if _container_client is not None:
        return _container_client

    settings = get_settings()
    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"

    credential = ManagedIdentityCredential(
        client_id=settings.managed_identity_client_id
    )

    _container_client = ContainerClient(
        account_url=account_url,
        container_name=settings.azure_storage_container,
        credential=credential,
    )
    return _container_client


async def get_article_index(
    category: str | None = None,
    search: str | None = None,
    limit: int = 0,
    offset: int = 0,
) -> ArticleIndex:
    """Read the article index from blob storage.

    Args:
        category: Optional category to filter articles by (case-insensitive).
        search: Optional search query to match against title and description.
        limit: Maximum number of articles to return (0 = unlimited).
        offset: Number of articles to skip before returning results.
    """
    client = _get_container_client()
    try:
        blob = client.get_blob_client(INDEX_BLOB)
        data = blob.download_blob().readall()
        articles_data = json.loads(data)
        # Handle both list format and dict format ({"articles": [...]})
        if isinstance(articles_data, dict):
            articles_data = articles_data.get("articles", [])
        articles = [ArticleSummary(**a) for a in articles_data]

        if category:
            category_lower = category.lower()
            articles = [
                a
                for a in articles
                if category_lower in [c.lower() for c in a.categories]
            ]

        if search:
            search_lower = search.lower()
            articles = [
                a
                for a in articles
                if search_lower in a.title.lower()
                or search_lower in a.description.lower()
            ]

        total = len(articles)

        # Apply offset/limit slicing
        if offset > 0:
            articles = articles[offset:]
        if limit > 0:
            articles = articles[:limit]

        return ArticleIndex(articles=articles, total=total)
    except ResourceNotFoundError:
        return ArticleIndex(articles=[], total=0)
    except HttpResponseError as e:
        logger.warning("Azure API error reading article index: %s", e.message)
        return ArticleIndex(articles=[], total=0)
    except Exception as e:
        logger.error("Unexpected error reading article index: %s", e)
        return ArticleIndex(articles=[], total=0)


async def get_article(article_id: str) -> Article | None:
    """Read a single article by ID from blob storage."""
    client = _get_container_client()
    try:
        # Articles stored under their ID
        blob = client.get_blob_client(f"{article_id}.json")
        data = blob.download_blob().readall()
        return Article(**json.loads(data))
    except ResourceNotFoundError:
        return None
    except HttpResponseError as e:
        logger.warning("Azure API error reading article %s: %s", article_id, e.message)
        return None
    except Exception as e:
        logger.error("Unexpected error reading article %s: %s", article_id, e)
        return None


async def write_article(article: Article) -> None:
    """Write an article to blob storage and update the index."""
    client = _get_container_client()
    try:
        # Write individual article
        blob = client.get_blob_client(f"{article.id}.json")
        blob.upload_blob(
            article.model_dump_json(indent=2),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )

        # Update index
        index = await get_article_index()
        # Remove existing entry if present, then prepend
        existing_ids = {a.id for a in index.articles}
        if article.id not in existing_ids:
            summary = ArticleSummary(**article.model_dump())
            index.articles.insert(0, summary)

        await write_article_index(index.articles)
    except HttpResponseError as e:
        logger.warning("Azure API error writing article %s: %s", article.id, e.message)
        raise
    except Exception as e:
        logger.error("Unexpected error writing article %s: %s", article.id, e)
        raise


async def write_article_only(article: Article) -> None:
    """Write only the article JSON to blob storage (no index update).

    Used by the orchestrator during batch ingestion to avoid N+1 index writes.
    """
    client = _get_container_client()
    try:
        blob = client.get_blob_client(f"{article.id}.json")
        blob.upload_blob(
            article.model_dump_json(indent=2),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
    except HttpResponseError as e:
        logger.warning("Azure API error writing article %s: %s", article.id, e.message)
        raise
    except Exception as e:
        logger.error("Unexpected error writing article %s: %s", article.id, e)
        raise


async def get_blog_index(
    limit: int = 0,
    offset: int = 0,
) -> BlogIndex:
    """Read the blog post index from blob storage."""
    client = _get_container_client()
    try:
        blob = client.get_blob_client(BLOG_INDEX_BLOB)
        data = blob.download_blob().readall()
        posts_data = json.loads(data)
        if isinstance(posts_data, dict):
            posts_data = posts_data.get("posts", [])
        posts = [BlogPost(**p) for p in posts_data]

        total = len(posts)

        if offset > 0:
            posts = posts[offset:]
        if limit > 0:
            posts = posts[:limit]

        return BlogIndex(posts=posts, total=total)
    except ResourceNotFoundError:
        return BlogIndex(posts=[], total=0)
    except HttpResponseError as e:
        logger.warning("Azure API error reading blog index: %s", e.message)
        return BlogIndex(posts=[], total=0)
    except Exception as e:
        logger.error("Unexpected error reading blog index: %s", e)
        return BlogIndex(posts=[], total=0)


async def write_article_index(articles: list[ArticleSummary]) -> None:
    """Write the full article index to blob storage.

    Args:
        articles: Complete list of article summaries to persist.
    """
    client = _get_container_client()
    index_blob = client.get_blob_client(INDEX_BLOB)
    index_data = json.dumps([a.model_dump(mode="json") for a in articles], indent=2)
    index_blob.upload_blob(
        index_data,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
