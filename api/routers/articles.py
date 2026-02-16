"""Article feed endpoints."""

from fastapi import APIRouter, Header, HTTPException, Query

from api.config import get_settings
from api.models.article import Article, ArticleIndex
from api.services.blob_storage import get_article, get_article_index
from api.services.ingestion.orchestrator import run_ingestion

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticleIndex)
async def list_articles(
    category: str | None = Query(
        default=None,
        description="Filter articles by category (case-insensitive)",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of articles to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of articles to skip",
    ),
):
    """Get the article feed index, optionally filtered by category."""
    return await get_article_index(category=category, limit=limit, offset=offset)


@router.get("/{article_id}", response_model=Article)
async def get_article_by_id(article_id: str):
    """Get a single article by ID."""
    article = await get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/ingest")
async def trigger_ingestion(x_ingest_key: str = Header()):
    """Trigger an article ingestion run. Protected by API key."""
    settings = get_settings()
    if not settings.ingest_api_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=403, detail="Invalid ingest key")

    stats = await run_ingestion()
    return stats.to_dict()
