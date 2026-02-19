"use client";

import { useCallback } from "react";
import Link from "next/link";
import { fetchBlogPosts, type BlogPost } from "@/lib/api";
import { useFetch } from "@/hooks/useFetch";

function BlogPostCard({ post }: { post: BlogPost }) {
  const date = new Date(post.published_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <Link
      href={`/blog/${post.slug}`}
      className="group block rounded-xl border border-zinc-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
    >
      {post.image_url && (
        <div className="mb-4 overflow-hidden rounded-lg">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={post.image_url}
            alt={post.title}
            className="h-48 w-full object-cover transition-transform group-hover:scale-105"
          />
        </div>
      )}
      <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
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
      <h3 className="mt-2 text-lg font-semibold leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400">
        {post.title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        {post.description}
      </p>
      {post.category && (
        <div className="mt-3">
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
            {post.category}
          </span>
        </div>
      )}
    </Link>
  );
}

export default function BlogPage() {
  const fetchPosts = useCallback(
    () => fetchBlogPosts().then((data) => data.posts),
    []
  );
  const { data: posts, loading, error } = useFetch<BlogPost[]>(fetchPosts);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Blog</h1>
        <div className="grid gap-6 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-72 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Blog</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950">
          <p className="text-sm text-red-600 dark:text-red-400">
            Failed to load blog posts: {error}
          </p>
        </div>
      </div>
    );
  }

  if (!posts) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Blog</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Articles written by the Fishbowl Writer agent
        </p>
      </div>
      {posts.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-zinc-500 dark:text-zinc-400">
            No blog posts yet. The writer agent will publish articles here once
            it starts running.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2">
          {posts.map((post) => (
            <BlogPostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
