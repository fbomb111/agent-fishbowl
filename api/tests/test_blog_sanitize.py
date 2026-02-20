"""Tests for blog HTML sanitization."""

from datetime import datetime, timezone

from api.routers.blog import sanitize_blog_html


def _make_dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


class TestSanitizeBlogHtml:
    def test_fixes_canonical_url(self):
        html = '<link rel="canonical" href="https://codewithcaptain.com/avoid-projection-bias/index.html">'
        result = sanitize_blog_html(
            html, "avoid-projection-bias", _make_dt(2026, 2, 14)
        )
        assert (
            'href="https://agentfishbowl.com/blog/avoid-projection-bias/index.html"'
            in result
        )

    def test_fixes_example_com_canonical(self):
        html = '<link rel="canonical" href="https://example.com/testing-emergent-behavior-ai/index.html">'
        result = sanitize_blog_html(
            html, "testing-emergent-behavior-ai", _make_dt(2026, 2, 20)
        )
        assert (
            'href="https://agentfishbowl.com/blog/testing-emergent-behavior-ai/index.html"'
            in result
        )

    def test_fixes_og_url(self):
        html = '<meta property="og:url" content="https://codewithcaptain.com/old-post">'
        result = sanitize_blog_html(html, "my-post", _make_dt(2026, 2, 14))
        assert 'content="https://agentfishbowl.com/blog/my-post/index.html"' in result

    def test_fixes_json_ld_dates(self):
        html = '{"datePublished": "2024-12-24", "dateModified": "2024-12-24"}'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert '"datePublished": "2026-02-14"' in result
        assert '"dateModified": "2026-02-14"' in result

    def test_fixes_hero_date(self):
        html = '<div class="hero-date">December 24, 2024</div>'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert "February 14, 2026" in result

    def test_fixes_cta_href_codewithcaptain(self):
        html = '<a href="https://codewithcaptain.com/app">Try it</a>'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert 'href="https://agentfishbowl.com"' in result
        assert "codewithcaptain.com" not in result

    def test_fixes_cta_href_example_com(self):
        html = '<a href="https://example.com/signup">Sign up</a>'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert 'href="https://agentfishbowl.com"' in result
        assert "example.com" not in result

    def test_fixes_content_attr_example_com(self):
        html = '<meta itemprop="image" content="https://example.com/img.png">'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert 'content="https://agentfishbowl.com"' in result
        assert "example.com" not in result

    def test_preserves_correct_agentfishbowl_urls(self):
        html = '<a href="https://agentfishbowl.com/blog/some-post">Read more</a>'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert 'href="https://agentfishbowl.com/blog/some-post"' in result

    def test_preserves_legitimate_external_links(self):
        html = '<a href="https://github.com/some-project">GitHub</a>'
        result = sanitize_blog_html(html, "test", _make_dt(2026, 2, 14))
        assert 'href="https://github.com/some-project"' in result

    def test_full_document_sanitization(self):
        html = """<!DOCTYPE html>
<html>
<head>
<link rel="canonical" href="https://codewithcaptain.com/avoid-projection-bias/index.html">
<meta property="og:url" content="https://codewithcaptain.com/avoid-projection-bias">
<script type="application/ld+json">
{"@type": "Article", "datePublished": "2024-12-24", "dateModified": "2024-12-24"}
</script>
</head>
<body>
<div class="hero-date">December 24, 2024</div>
<a href="https://codewithcaptain.com/app">Try Captain AI</a>
<a href="https://github.com/real-project">Valid link</a>
</body>
</html>"""
        result = sanitize_blog_html(
            html, "avoid-projection-bias", _make_dt(2026, 2, 14)
        )
        assert "codewithcaptain.com" not in result
        assert "agentfishbowl.com/blog/avoid-projection-bias/index.html" in result
        assert '"datePublished": "2026-02-14"' in result
        assert "February 14, 2026" in result
        assert "github.com/real-project" in result

    def test_fixes_all_example_com_patterns_from_issue_237(self):
        """Regression test for issue #237: all example.com patterns."""
        slug = "testing-emergent-behavior-ai"
        bad = "https://example.com/" + slug + "/index.html"
        html = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f'<link rel="canonical" href="{bad}" />\n'
            f'<meta property="og:url" content="{bad}" />\n'
            '<meta itemprop="mainEntityOfPage"'
            f' content="{bad}" />\n'
            '<script type="application/ld+json">\n'
            '{"@type": "Article",'
            ' "mainEntityOfPage": {"@type": "WebPage",'
            f' "@id": "{bad}"}}}}\n'
            "</script>\n</head>\n<body>\n"
            '<a href="https://example.com" class="cta">'
            "Agent Fishbowl</a>\n"
            "</body>\n</html>"
        )
        result = sanitize_blog_html(html, slug, _make_dt(2026, 2, 20))
        assert "example.com" not in result
        canonical = f"https://agentfishbowl.com/blog/{slug}/index.html"
        assert f'href="{canonical}"' in result
        assert f'content="{canonical}"' in result
        assert f'"@id": "{canonical}"' in result
