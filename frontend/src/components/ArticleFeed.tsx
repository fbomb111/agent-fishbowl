"use client";

import { useEffect, useState, useCallback } from "react";
import { ArticleCard } from "./ArticleCard";
import { CategoryFilter } from "./CategoryFilter";
import { fetchArticles, type ArticleSummary } from "@/lib/api";

const PAGE_SIZE = 20;

export function ArticleFeed() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [allCategories, setAllCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadArticles = useCallback(async (category: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchArticles(category ?? undefined, PAGE_SIZE, 0);
      setArticles(data.articles);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const data = await fetchArticles(
        selectedCategory ?? undefined,
        PAGE_SIZE,
        articles.length
      );
      setArticles((prev) => [...prev, ...data.articles]);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingMore(false);
    }
  }, [selectedCategory, articles.length]);

  useEffect(() => {
    fetchArticles(undefined, PAGE_SIZE, 0)
      .then((data) => {
        setArticles(data.articles);
        setTotal(data.total);
        const categories = new Set<string>();
        data.articles.forEach((article) => {
          article.categories.forEach((cat) => categories.add(cat));
        });
        setAllCategories(Array.from(categories).sort());
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleCategorySelect = (category: string | null) => {
    setSelectedCategory(category);
    loadArticles(category);
  };

  const hasMore = articles.length < total;

  if (loading && articles.length === 0) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-800" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950">
        <p className="text-sm text-red-600 dark:text-red-400">
          Failed to load articles: {error}
        </p>
        <button
          onClick={() => loadArticles(selectedCategory)}
          className="mt-3 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:bg-red-700 dark:hover:bg-red-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (articles.length === 0 && !selectedCategory) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-zinc-500 dark:text-zinc-400">
          No articles yet. The ingestion agents are being set up — check the
          Fishbowl to watch their progress.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <CategoryFilter
        categories={allCategories}
        selected={selectedCategory}
        onSelect={handleCategorySelect}
      />
      {loading ? (
        <div className="space-y-4">
          <div className="h-1 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
            <div className="h-full w-1/3 animate-[loading-bar_1s_ease-in-out_infinite] rounded-full bg-zinc-500 dark:bg-zinc-400" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-64 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900"
              />
            ))}
          </div>
        </div>
      ) : articles.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-zinc-500 dark:text-zinc-400">
            No articles found in this category. Try selecting a different
            category or clear filters to see all articles.
          </p>
          <button
            onClick={() => handleCategorySelect(null)}
            className="mt-3 text-sm font-medium text-zinc-700 underline hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                title={article.title}
                source={article.source}
                description={article.description}
                originalUrl={article.original_url}
                publishedAt={article.published_at}
                categories={article.categories}
                imageUrl={article.image_url}
                readTimeMinutes={article.read_time_minutes}
                insights={article.insights}
                aiSummary={article.ai_summary}
              />
            ))}
          </div>
          {hasMore && (
            <div className="flex flex-col items-center gap-2 pt-2">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-lg border border-zinc-300 px-6 py-2.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                {loadingMore ? "Loading..." : "Load More"}
              </button>
              <p className="text-xs text-zinc-400 dark:text-zinc-500">
                Showing {articles.length} of {total} articles
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
