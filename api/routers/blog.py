"""Blog post endpoints."""

import html
import logging

import httpx
from fastapi import APIRouter, Header, HTTPException, Path, Query
from fastapi.responses import HTMLResponse

from api.config import get_settings
from api.models.blog import BlogIndex, BlogPost
from api.services.blob_storage import (
    get_blog_index,
    read_blog_html,
    upload_blog_html,
    write_blog_index,
)
from api.services.blog_sanitizer import FISHBOWL_BLOG_BASE, sanitize_blog_html
from api.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

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
        html = sanitize_blog_html(resp.text, post.slug, post.published_at)
        await upload_blog_html(post.slug, html)
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


@router.post("/resanitize")
async def resanitize_blog_posts(x_ingest_key: str = Header()):
    """Re-sanitize all stored blog HTML to fix placeholder URLs.

    Reads each blog post's HTML from blob storage, applies sanitization,
    and re-uploads the cleaned version. Protected by the ingest API key.
    """
    settings = get_settings()
    if not settings.ingest_api_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(status_code=403, detail="Invalid ingest key")

    index = await get_blog_index()
    fixed = []
    skipped = []
    for post in index.posts:
        html = await read_blog_html(post.slug)
        if not html:
            skipped.append(post.slug)
            continue
        sanitized = sanitize_blog_html(html, post.slug, post.published_at)
        if sanitized != html:
            await upload_blog_html(post.slug, sanitized)
            fixed.append(post.slug)
    return {"fixed": fixed, "skipped": skipped, "total": len(index.posts)}


@router.get("/by-slug/{slug}")
async def get_blog_post_by_slug(
    slug: str = Path(..., pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", max_length=200),
):
    """Get a single blog post by its slug."""
    index = await get_blog_index()
    for post in index.posts:
        if post.slug == slug:
            return post
    raise HTTPException(status_code=404, detail="Blog post not found")


SITE_URL = "https://agentfishbowl.com"


@router.get("/by-slug/{slug}/og")
async def get_blog_post_og(
    slug: str = Path(..., pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", max_length=200),
):
    """Serve a minimal HTML page with OpenGraph meta tags for social sharing.

    Social media crawlers don't execute JavaScript, so the static-exported SPA
    can't provide per-post OG tags.  This endpoint returns a lightweight HTML
    document with the correct og:title, og:description, og:image, and
    article:published_time.  Human visitors are redirected to the SPA page.
    """
    index = await get_blog_index()
    post = None
    for p in index.posts:
        if p.slug == slug:
            post = p
            break
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    canonical = f"{SITE_URL}/blog/{slug}"
    title_esc = html.escape(post.title)
    desc_esc = html.escape(post.description)
    published = post.published_at.isoformat()

    image_tag = ""
    if post.image_url:
        image_esc = html.escape(post.image_url)
        image_tag = f'<meta property="og:image" content="{image_esc}" />'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title_esc} — Agent Fishbowl Blog</title>
<meta name="description" content="{desc_esc}" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{title_esc}" />
<meta property="og:description" content="{desc_esc}" />
<meta property="og:url" content="{canonical}" />
<meta property="og:site_name" content="Agent Fishbowl" />
<meta property="article:published_time" content="{published}" />
{image_tag}<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{title_esc}" />
<meta name="twitter:description" content="{desc_esc}" />
<link rel="canonical" href="{canonical}" />
<meta http-equiv="refresh" content="0;url={canonical}" />
</head>
<body>
<p>Redirecting to <a href="{canonical}">{title_esc}</a>...</p>
</body>
</html>"""
    return HTMLResponse(content=page)


@router.get("/{post_id}/content")
async def get_blog_post_content(
    post_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]+$", max_length=200),
):
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
        return HTMLResponse(
            content=sanitize_blog_html(html, post.slug, post.published_at)
        )

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

    return HTMLResponse(
        content=sanitize_blog_html(resp.text, post.slug, post.published_at)
    )


@router.get("/{post_id}")
async def get_blog_post(
    post_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]+$", max_length=200),
):
    """Get a single blog post by ID.

    Returns the post metadata (not HTML content — frontend links to preview_url).
    """
    index = await get_blog_index()
    for post in index.posts:
        if post.id == post_id:
            return post
    raise HTTPException(status_code=404, detail="Blog post not found")
