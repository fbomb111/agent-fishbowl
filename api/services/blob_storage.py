"""Azure Blob Storage service for reading/writing article data."""

import json
import logging

from azure.identity import ManagedIdentityCredential
from azure.storage.blob import ContainerClient

from api.config import get_settings
from api.models.article import Article, ArticleIndex, ArticleSummary

logger = logging.getLogger(__name__)

INDEX_BLOB = "index.json"


def _get_container_client() -> ContainerClient:
    """Create a blob container client using User-Assigned Managed Identity."""
    settings = get_settings()
    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"

    credential = ManagedIdentityCredential(
        client_id=settings.managed_identity_client_id
    )

    return ContainerClient(
        account_url=account_url,
        container_name=settings.azure_storage_container,
        credential=credential,
    )


async def get_article_index() -> ArticleIndex:
    """Read the article index from blob storage."""
    client = _get_container_client()
    try:
        blob = client.get_blob_client(INDEX_BLOB)
        data = blob.download_blob().readall()
        articles_data = json.loads(data)
        articles = [ArticleSummary(**a) for a in articles_data]
        return ArticleIndex(articles=articles, total=len(articles))
    except Exception as e:
        logger.warning("Failed to read article index: %s", e)
        return ArticleIndex(articles=[], total=0)
    finally:
        client.close()


async def get_article(article_id: str) -> Article | None:
    """Read a single article by ID from blob storage."""
    client = _get_container_client()
    try:
        # Articles stored under their ID
        blob = client.get_blob_client(f"{article_id}.json")
        data = blob.download_blob().readall()
        return Article(**json.loads(data))
    except Exception as e:
        logger.warning("Failed to read article %s: %s", article_id, e)
        return None
    finally:
        client.close()


async def write_article(article: Article) -> None:
    """Write an article to blob storage and update the index."""
    client = _get_container_client()
    try:
        # Write individual article
        blob = client.get_blob_client(f"{article.id}.json")
        blob.upload_blob(
            article.model_dump_json(indent=2),
            overwrite=True,
            content_settings={"content_type": "application/json"},
        )

        # Update index
        index = await get_article_index()
        # Remove existing entry if present, then prepend
        existing_ids = {a.id for a in index.articles}
        if article.id not in existing_ids:
            summary = ArticleSummary(**article.model_dump())
            index.articles.insert(0, summary)

        index_blob = client.get_blob_client(INDEX_BLOB)
        index_data = json.dumps(
            [a.model_dump(mode="json") for a in index.articles], indent=2
        )
        index_blob.upload_blob(
            index_data,
            overwrite=True,
            content_settings={"content_type": "application/json"},
        )
    finally:
        client.close()
