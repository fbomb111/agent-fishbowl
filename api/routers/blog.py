"""Blog post endpoints."""

import logging

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from api.config import get_settings
from api.models.blog import BlogIndex, BlogPost
from api.services.blob_storage import (
    get_blog_index,
    read_blog_html,
    upload_blog_html,
    write_blog_index,
)
from api.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blog", tags=["blog"])

FISHBOWL_BLOG_BASE = "https://agentfishbowl.com/blog"


@router.get("", response_model=BlogIndex)
async def list_blog_posts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get the blog post index."""
    return await get_blog_index(limit=limit, offset=offset)


@router.post("")
async def add_blog_post(post: BlogPost, x_ingest_key: str = Header()):
    """Add a new blog post to the index and copy HTML to fishbowl storage."""
    settings = get_settings()
    if not settings.ingest_api_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=403, detail="Invalid ingest key")

    index = await get_blog_index()
    if any(p.id == post.id for p in index.posts):
        return {"status": "exists", "id": post.id}

    # Copy HTML from source preview_url to fishbowl storage
    copied = False
    try:
        client = get_shared_client()
        resp = await client.get(post.preview_url)
        resp.raise_for_status()
        await upload_blog_html(post.slug, resp.text)
        post.preview_url = f"{FISHBOWL_BLOG_BASE}/{post.slug}/index.html"
        copied = True
        logger.info("Copied blog HTML for %s to fishbowl storage", post.slug)
    except Exception:
        logger.warning(
            "Could not copy blog HTML for %s from %s — registering with original URL",
            post.slug,
            post.preview_url,
            exc_info=True,
        )

    index.posts.insert(0, post)
    await write_blog_index(index.posts)
    return {"status": "created", "id": post.id, "copied": copied}


@router.get("/by-slug/{slug}")
async def get_blog_post_by_slug(slug: str):
    """Get a single blog post by its slug."""
    index = await get_blog_index()
    for post in index.posts:
        if post.slug == slug:
            return post
    raise HTTPException(status_code=404, detail="Blog post not found")


@router.get("/{post_id}/content")
async def get_blog_post_content(post_id: str):
    """Serve blog post HTML — reads from local blob, falls back to proxy."""
    index = await get_blog_index()
    post = None
    for p in index.posts:
        if p.id == post_id:
            post = p
            break
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    # Try local blob first
    html = await read_blog_html(post.slug)
    if html:
        return HTMLResponse(content=html)

    # Fallback: proxy from preview_url
    try:
        client = get_shared_client()
        resp = await client.get(post.preview_url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch blog content from %s", post.preview_url)
        raise HTTPException(
            status_code=502, detail="Failed to fetch blog content"
        ) from exc

    return HTMLResponse(content=resp.text)


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
