"""Article data models."""

from datetime import datetime

from pydantic import BaseModel


class ArticleSummary(BaseModel):
    """Article summary for feed display."""

    id: str
    title: str
    source: str
    source_url: str
    original_url: str
    published_at: datetime
    summary: str
    categories: list[str] = []
    image_url: str | None = None
    read_time_minutes: int | None = None


class Article(ArticleSummary):
    """Full article data."""

    ingested_at: datetime
    key_takeaways: list[str] = []


class ArticleIndex(BaseModel):
    """Article feed index."""

    articles: list[ArticleSummary]
    total: int
