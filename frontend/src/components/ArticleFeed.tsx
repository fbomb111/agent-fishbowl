"use client";

import { useEffect, useState, useCallback } from "react";
import { ArticleCard } from "./ArticleCard";
import { CategoryFilter } from "./CategoryFilter";
import { fetchArticles, type ArticleSummary } from "@/lib/api";

export function ArticleFeed() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [allCategories, setAllCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadArticles = useCallback(async (category: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchArticles(category ?? undefined);
      setArticles(data.articles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchArticles()
      .then((data) => {
        setArticles(data.articles);
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-zinc-500 dark:text-zinc-400">
            No articles found in this category.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {articles.map((article) => (
            <ArticleCard
              key={article.id}
              title={article.title}
              source={article.source}
              summary={article.summary}
              originalUrl={article.original_url}
              publishedAt={article.published_at}
              categories={article.categories}
              imageUrl={article.image_url}
              readTimeMinutes={article.read_time_minutes}
            />
          ))}
        </div>
      )}
    </div>
  );
}
