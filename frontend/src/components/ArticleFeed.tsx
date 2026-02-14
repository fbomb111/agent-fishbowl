"use client";

import { ArticleCard } from "./ArticleCard";

// Placeholder data until Phase 2 connects to the API
const PLACEHOLDER_ARTICLES = [
  {
    id: "1",
    title: "Coming Soon: AI-Curated News",
    source: "Agent Fishbowl",
    summary:
      "This feed will be populated by AI agents that ingest, summarize, and categorize articles from top AI and technology publications. Check back soon or watch the Fishbowl to see agents building this feature.",
    originalUrl: "#",
    publishedAt: new Date().toISOString(),
    categories: ["meta", "agents"],
  },
];

export function ArticleFeed() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {PLACEHOLDER_ARTICLES.map((article) => (
        <ArticleCard
          key={article.id}
          title={article.title}
          source={article.source}
          summary={article.summary}
          originalUrl={article.originalUrl}
          publishedAt={article.publishedAt}
          categories={article.categories}
        />
      ))}
    </div>
  );
}
