import type { Insight } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  tool: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  pattern: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  trend: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  technique: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  concept: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

interface ArticleCardProps {
  title: string;
  source: string;
  description: string;
  originalUrl: string;
  publishedAt: string;
  categories: string[];
  imageUrl?: string;
  readTimeMinutes?: number;
  insights?: Insight[];
  aiSummary?: string;
}

export function ArticleCard({
  title,
  source,
  description,
  originalUrl,
  publishedAt,
  categories,
  imageUrl,
  readTimeMinutes,
  insights,
  aiSummary,
}: ArticleCardProps) {
  const date = new Date(publishedAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const displayInsights = insights?.filter((i) => i.text) ?? [];

  return (
    <a
      href={originalUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-zinc-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
    >
      {imageUrl && (
        <div className="mb-4 overflow-hidden rounded-lg">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={title}
            className="h-40 w-full object-cover transition-transform group-hover:scale-105"
          />
        </div>
      )}
      <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
        <span className="font-medium">{source}</span>
        <span>&middot;</span>
        <span>{date}</span>
        {readTimeMinutes && (
          <>
            <span>&middot;</span>
            <span>{readTimeMinutes} min read</span>
          </>
        )}
      </div>
      <h3 className="mt-2 text-lg font-semibold leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        {aiSummary || description}
      </p>
      {displayInsights.length > 0 && (
        <div className="mt-3 space-y-1.5 border-l-2 border-blue-200 pl-3 dark:border-blue-800">
          {displayInsights.map((insight, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <span
                className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium leading-tight ${CATEGORY_COLORS[insight.category] || CATEGORY_COLORS.concept}`}
              >
                {insight.category}
              </span>
              <span className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                {insight.text}
              </span>
            </div>
          ))}
        </div>
      )}
      {categories.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {categories.map((cat) => (
            <span
              key={cat}
              className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            >
              {cat}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}
