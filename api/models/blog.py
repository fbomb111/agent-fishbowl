"""Blog post data models."""

from datetime import datetime

from pydantic import BaseModel


class BlogPost(BaseModel):
    """Blog post metadata for index display."""

    id: str
    title: str
    slug: str
    description: str
    published_at: datetime
    focus_keyphrase: str = ""
    author: str = "Fishbowl Writer"
    category: str = ""
    preview_url: str
    image_url: str | None = None
    read_time_minutes: int | None = None


class BlogIndex(BaseModel):
    """Blog post index."""

    posts: list[BlogPost]
    total: int
