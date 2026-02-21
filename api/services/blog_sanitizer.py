"""Blog HTML sanitization service.

Rewrites blog HTML to fix canonical URLs, og:url, dates, publisher names,
and CTA links that point to placeholder domains.
"""

import re
from datetime import datetime

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
