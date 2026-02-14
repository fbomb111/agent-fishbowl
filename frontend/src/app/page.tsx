import { ArticleFeed } from "@/components/ArticleFeed";

export default function FeedPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">AI News Feed</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          AI-curated articles on artificial intelligence, machine learning, and
          technology — aggregated, summarized, and presented by AI agents.
        </p>
      </div>
      <ArticleFeed />
    </div>
  );
}
