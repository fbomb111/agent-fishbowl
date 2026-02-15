"""Article feed endpoints."""

from fastapi import APIRouter, HTTPException, Query

from api.models.article import Article, ArticleIndex
from api.services.blob_storage import get_article, get_article_index

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticleIndex)
async def list_articles(
    category: str | None = Query(
        default=None,
        description="Filter articles by category (case-insensitive)",
    ),
):
    """Get the article feed index, optionally filtered by category."""
    return await get_article_index(category=category)


@router.get("/{article_id}", response_model=Article)
async def get_article_by_id(article_id: str):
    """Get a single article by ID."""
    article = await get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
