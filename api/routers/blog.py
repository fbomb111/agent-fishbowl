"""Blog post endpoints."""

from fastapi import APIRouter, Header, HTTPException, Query

from api.config import get_settings
from api.models.blog import BlogIndex, BlogPost
from api.services.blob_storage import get_blog_index, write_blog_index

router = APIRouter(prefix="/blog", tags=["blog"])


@router.get("", response_model=BlogIndex)
async def list_blog_posts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get the blog post index."""
    return await get_blog_index(limit=limit, offset=offset)


@router.post("")
async def add_blog_post(post: BlogPost, x_ingest_key: str = Header()):
    """Add a new blog post to the index. Protected by API key."""
    settings = get_settings()
    if not settings.ingest_api_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=403, detail="Invalid ingest key")

    index = await get_blog_index()
    if any(p.id == post.id for p in index.posts):
        return {"status": "exists", "id": post.id}

    index.posts.insert(0, post)
    await write_blog_index(index.posts)
    return {"status": "created", "id": post.id}


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
