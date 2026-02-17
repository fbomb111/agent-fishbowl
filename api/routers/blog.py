"""Blog post endpoints."""

from fastapi import APIRouter, HTTPException, Query

from api.models.blog import BlogIndex
from api.services.blob_storage import get_blog_index

router = APIRouter(prefix="/blog", tags=["blog"])


@router.get("", response_model=BlogIndex)
async def list_blog_posts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get the blog post index."""
    return await get_blog_index(limit=limit, offset=offset)


@router.get("/{post_id}")
async def get_blog_post(post_id: str):
    """Get a single blog post by ID.

    Returns the post metadata (not HTML content — frontend links to preview_url).
    """
    index = await get_blog_index()
    for post in index.posts:
        if post.id == post_id:
            return post
    raise HTTPException(status_code=404, detail="Blog post not found")
