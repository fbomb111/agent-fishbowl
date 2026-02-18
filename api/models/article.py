"""Article data models."""

from datetime import datetime

from pydantic import BaseModel, model_validator


class Insight(BaseModel):
    """A single actionable insight extracted by AI."""

    text: str
    category: str = "concept"  # tool, pattern, trend, technique, concept


class ArticleSummary(BaseModel):
    """Article summary for feed display."""

    id: str
    title: str
    source: str
    source_url: str
    original_url: str
    published_at: datetime
    description: str
    categories: list[str] = []
    image_url: str | None = None
    read_time_minutes: int | None = None
    insights: list[Insight] = []
    ai_summary: str | None = None
    has_full_text: bool = False
    relevance_score: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_old_fields(cls, data: dict) -> dict:
        """Backward compat: map old field names from existing blob data."""
        if isinstance(data, dict):
            # summary → description
            if "summary" in data and "description" not in data:
                data["description"] = data.pop("summary")
            # key_takeaways → insights (convert strings to Insight objects)
            if "key_takeaways" in data and "insights" not in data:
                takeaways = data.pop("key_takeaways")
                data["insights"] = [
                    {"text": t, "category": "concept"} if isinstance(t, str) else t
                    for t in takeaways
                ]
        return data


class Article(ArticleSummary):
    """Full article data."""

    ingested_at: datetime


class ArticleIndex(BaseModel):
    """Article feed index."""

    articles: list[ArticleSummary]
    total: int
