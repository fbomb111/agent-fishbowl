"""Blog post data models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

# The Agent Fishbowl repository was created on 2026-02-14T16:35:05Z.
# No content could have been published before this date.
PROJECT_CREATED_AT = datetime(2026, 2, 14, 16, 35, 5, tzinfo=timezone.utc)


class BlogPost(BaseModel):
    """Blog post metadata for index display."""

    id: str
    title: str
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", max_length=200)
    description: str
    published_at: datetime
    focus_keyphrase: str = ""
    author: str = "Fishbowl Writer"
    category: str = ""
    preview_url: str
    image_url: str | None = None
    read_time_minutes: int | None = None

    @model_validator(mode="after")
    def clamp_published_at(self) -> "BlogPost":
        """Clamp published_at to project creation date if it predates the project."""
        dt = self.published_at
        # Ensure timezone-aware for comparison
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < PROJECT_CREATED_AT:
            self.published_at = PROJECT_CREATED_AT
        return self


class BlogIndex(BaseModel):
    """Blog post index."""

    posts: list[BlogPost]
    total: int
