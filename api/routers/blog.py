"""Blog post endpoints."""

import logging
import re
from datetime import datetime

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
from api.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blog", tags=["blog"])

FISHBOWL_BLOG_BASE = "https://agentfishbowl.com/blog"
FISHBOWL_HOST = "https://agentfishbowl.com"


def sanitize_blog_html(html: str, slug: str, published_at: datetime) -> str:
    """Rewrite blog HTML to fix canonical URLs, og:url, dates, and CTAs.

    The generation API sometimes produces HTML with wrong canonical URLs
    (e.g. codewithcaptain.com, example.com), fabricated dates, and CTA
    links pointing to other products. This function corrects them before
    the HTML is stored.
    """
    correct_canonical = f"{FISHBOWL_BLOG_BASE}/{slug}/index.html"
    date_str = published_at.strftime("%B %d, %Y")
    date_iso = published_at.strftime("%Y-%m-%d")

    # Fix <link rel="canonical" href="...">
    html = re.sub(
        r'(<link\s+rel="canonical"\s+href=")[^"]*(")',
        rf"\g<1>{correct_canonical}\2",
        html,
    )

    # Fix <meta property="og:url" content="...">
    html = re.sub(
        r'(<meta\s+property="og:url"\s+content=")[^"]*(")',
        rf"\g<1>{correct_canonical}\2",
        html,
    )

    # Fix JSON-LD datePublished and dateModified
    html = re.sub(
        r'("datePublished"\s*:\s*")([^"]*?)(")',
        rf"\g<1>{date_iso}\3",
        html,
    )
    html = re.sub(
        r'("dateModified"\s*:\s*")([^"]*?)(")',
        rf"\g<1>{date_iso}\3",
        html,
    )

    # Fix hero-date display (e.g. <div class="hero-date">December 24, 2024</div>)
    html = re.sub(
        r'(<[^>]*class="hero-date"[^>]*>)([^<]*)(</)',
        rf"\g<1>{date_str}\3",
        html,
    )

    # Replace href/src/content URLs from known-bad placeholder domains
    html = re.sub(
        r'((?:href|src|content)=")https?://(?:codewithcaptain\.com|example\.com)[^"]*(")',
        rf"\g<1>{FISHBOWL_HOST}\2",
        html,
    )

    # Fix <meta itemprop="mainEntityOfPage" content="...">
    html = re.sub(
        r'(<meta\s+itemprop="mainEntityOfPage"\s+content=")[^"]*(")',
        rf"\g<1>{correct_canonical}\2",
        html,
    )

    # Fix JSON-LD mainEntityOfPage @id
    html = re.sub(
        r'("mainEntityOfPage"\s*:\s*\{[^}]*"@id"\s*:\s*")[^"]*(")',
        rf"\g<1>{correct_canonical}\2",
        html,
    )

    # Fix JSON-LD publisher name
    html = re.sub(
        r'("publisher"\s*:\s*\{[^}]*"name"\s*:\s*")'
        r"(?:Code with Captain|codewithcaptain\.com)"
        r'(")',
        r"\g<1>Agent Fishbowl\2",
        html,
    )

    # Fix JSON-LD author name from wrong attribution
    html = re.sub(
        r'("author"\s*:\s*\{[^}]*"name"\s*:\s*")Frankie Cleary(")',
        r"\g<1>Fishbowl Writer\2",
        html,
    )

    return html


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
