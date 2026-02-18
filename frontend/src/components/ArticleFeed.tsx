"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ArticleCard } from "./ArticleCard";
import { CategoryFilter } from "./CategoryFilter";
import { fetchArticles, type ArticleSummary } from "@/lib/api";

const PAGE_SIZE = 20;

export function ArticleFeed() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [allCategories, setAllCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadArticles = useCallback(
    async (category: string | null, search?: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchArticles(
          category ?? undefined,
          PAGE_SIZE,
          0,
          search || undefined
        );
        setArticles(data.articles);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const data = await fetchArticles(
        selectedCategory ?? undefined,
        PAGE_SIZE,
        articles.length,
        searchQuery || undefined
      );
      setArticles((prev) => [...prev, ...data.articles]);
      setTotal(data.total);
    } catch (err) {
      setLoadMoreError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingMore(false);
    }
  }, [selectedCategory, articles.length, searchQuery]);

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
    loadArticles(category, searchQuery);
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    debounceTimer.current = setTimeout(() => {
      loadArticles(selectedCategory, value);
    }, 300);
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
          onClick={() => loadArticles(selectedCategory, searchQuery)}
          className="mt-3 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:bg-red-700 dark:hover:bg-red-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (articles.length === 0 && !selectedCategory && !searchQuery) {
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
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search articles..."
          aria-label="Search articles"
          className="w-full rounded-lg border border-zinc-200 bg-white px-4 py-2.5 pl-10 text-sm text-zinc-900 placeholder-zinc-400 focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-500/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder-zinc-500 dark:focus:border-zinc-500 dark:focus:ring-zinc-400/20"
        />
        <svg
          className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400 dark:text-zinc-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
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
            {searchQuery
              ? `No articles found for "${searchQuery}". Try a different search term.`
              : "No articles found in this category. Try selecting a different category or clear filters to see all articles."}
          </p>
          <button
            onClick={() => {
              setSearchQuery("");
              handleCategorySelect(null);
            }}
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
              {loadMoreError && (
                <p className="text-sm text-red-600 dark:text-red-400">
                  Failed to load more articles: {loadMoreError}
                </p>
              )}
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-lg border border-zinc-300 px-6 py-2.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                {loadingMore ? "Loading..." : loadMoreError ? "Retry" : "Load More"}
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
