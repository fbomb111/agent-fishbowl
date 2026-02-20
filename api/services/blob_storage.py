"""Azure Blob Storage service for reading/writing article data."""

import json
import logging
import re

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import ContainerClient, ContentSettings

from api.config import get_settings
from api.models.article import Article, ArticleIndex, ArticleSummary
from api.models.blog import BlogIndex, BlogPost

logger = logging.getLogger(__name__)

_SAFE_PATH_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def validate_blob_path_segment(segment: str) -> str:
    """Validate a user-supplied blob path segment.

    Rejects inputs containing path traversal sequences (..), slashes,
    backslashes, or other unsafe characters. Returns the segment unchanged
    if valid; raises ValueError otherwise.
    """
    if not segment or not _SAFE_PATH_SEGMENT_RE.match(segment):
        raise ValueError(f"Invalid blob path segment: {segment!r}")
    return segment

INDEX_BLOB = "index.json"
BLOG_INDEX_BLOB = "blog-index.json"

# Lazy singletons — live for the process lifetime
_container_client: ContainerClient | None = None
_blog_container_client: ContainerClient | None = None


def _get_credential() -> ManagedIdentityCredential:
    """Return Managed Identity credential."""
    settings = get_settings()
    return ManagedIdentityCredential(client_id=settings.managed_identity_client_id)


def create_container_client(container_name: str) -> ContainerClient:
    """Create a ContainerClient for the given container."""
    settings = get_settings()
    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"
    return ContainerClient(
        account_url=account_url,
        container_name=container_name,
        credential=_get_credential(),
    )


def _get_container_client() -> ContainerClient:
    """Return a shared blob container client for articles (lazy singleton)."""
    global _container_client
    if _container_client is None:
        _container_client = create_container_client(
            get_settings().azure_storage_container
        )
    return _container_client


def _get_blog_container_client() -> ContainerClient:
    """Return a shared blob container client for blog content ($web)."""
    global _blog_container_client
    if _blog_container_client is None:
        _blog_container_client = create_container_client(
            get_settings().azure_blog_container
        )
    return _blog_container_client


def check_storage_connectivity() -> bool:
    """Lightweight storage connectivity check — lists 1 blob."""
    try:
        client = _get_container_client()
        next(client.list_blobs(results_per_page=1).__iter__())
        return True
    except StopIteration:
        # Container exists but is empty — still connected
        return True
    except Exception:
        return False


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
    validate_blob_path_segment(article_id)
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
    """Read the blog post index from the $web container."""
    client = _get_blog_container_client()
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


async def write_blog_index(posts: list[BlogPost]) -> None:
    """Write the full blog post index to the $web container."""
    client = _get_blog_container_client()
    index_blob = client.get_blob_client(BLOG_INDEX_BLOB)
    index_data = json.dumps([p.model_dump(mode="json") for p in posts], indent=2)
    index_blob.upload_blob(
        index_data,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )


async def upload_blog_html(slug: str, html: str) -> None:
    """Upload blog post HTML to $web/blog/{slug}/index.html."""
    validate_blob_path_segment(slug)
    client = _get_blog_container_client()
    blob = client.get_blob_client(f"blog/{slug}/index.html")
    blob.upload_blob(
        html,
        overwrite=True,
        content_settings=ContentSettings(content_type="text/html"),
    )


async def read_blog_html(slug: str) -> str | None:
    """Read blog post HTML from $web/blog/{slug}/index.html. Returns None if not found."""
    validate_blob_path_segment(slug)
    client = _get_blog_container_client()
    try:
        blob = client.get_blob_client(f"blog/{slug}/index.html")
        return blob.download_blob().readall().decode("utf-8")
    except ResourceNotFoundError:
        return None
    except Exception as e:
        logger.warning("Could not read blog HTML for %s: %s", slug, e)
        return None


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
