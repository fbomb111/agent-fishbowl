"""Article feed endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
async def list_articles():
    """Get the article feed index."""
    # Phase 2: Read from blob storage
    return {"articles": [], "total": 0}


@router.get("/{article_id}")
async def get_article(article_id: str):
    """Get a single article by ID."""
    # Phase 2: Read from blob storage
    return {"error": "Not implemented yet"}, 501
