"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { API_URL, fetchBlogPostBySlug, type BlogPost } from "@/lib/api";
import { ErrorFallback } from "./ErrorFallback";
import { ShareButtons } from "./ShareButtons";
import { useFetch } from "@/hooks/useFetch";

export function BlogPostViewer({ slug }: { slug: string }) {
  const fetchPost = useCallback(
    () => fetchBlogPostBySlug(slug),
    [slug]
  );
  const { data: post, loading, error } = useFetch<BlogPost>(fetchPost);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(600);

  const handleIframeLoad = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (doc?.body) {
        setIframeHeight(doc.body.scrollHeight + 40);
      }
    } catch {
      // Cross-origin — keep default height
    }
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
        <div className="h-96 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900" />
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="space-y-6">
        <Link
          href="/blog"
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
        >
          &larr; Back to Blog
        </Link>
        <ErrorFallback message={error || "Blog post not found"} />
      </div>
    );
  }

  const date = new Date(post.published_at).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const contentUrl = `${API_URL}/api/fishbowl/blog/${encodeURIComponent(post.id)}/content`;
  const ogShareUrl = `${API_URL}/api/fishbowl/blog/by-slug/${encodeURIComponent(post.slug)}/og`;

  return (
    <div className="space-y-6">
      <Link
        href="/blog"
        className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
      >
        &larr; Back to Blog
      </Link>

      <article>
        <header className="mb-6">
          <h1 className="text-3xl font-bold leading-tight">{post.title}</h1>
          <div className="mt-3 flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span className="font-medium">{post.author}</span>
            <span>&middot;</span>
            <span>{date}</span>
            {post.read_time_minutes && (
              <>
                <span>&middot;</span>
                <span>{post.read_time_minutes} min read</span>
              </>
            )}
          </div>
          {post.category && (
            <div className="mt-3">
              <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                {post.category}
              </span>
            </div>
          )}
          <ShareButtons title={post.title} shareUrl={ogShareUrl} />
        </header>

        <iframe
          ref={iframeRef}
          src={contentUrl}
          title={post.title}
          onLoad={handleIframeLoad}
          className="w-full rounded-xl border border-zinc-200 bg-white dark:border-zinc-800"
          style={{ height: iframeHeight, border: "none" }}
          sandbox="allow-same-origin allow-popups"
        />
      </article>
    </div>
  );
}
