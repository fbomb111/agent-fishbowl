import type { Insight } from "@/lib/api";

const FRESH_THRESHOLD_MS = 6 * 60 * 60 * 1000; // 6 hours

function formatRelativeTime(dateStr: string): string | null {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return null;

  const now = Date.now();
  const diffMs = now - date.getTime();
  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function isFresh(dateStr: string): boolean {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return false;
  return Date.now() - date.getTime() < FRESH_THRESHOLD_MS;
}

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
  const relativeTime = formatRelativeTime(publishedAt);
  const fresh = isFresh(publishedAt);

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
        {relativeTime && (
          <>
            <span>&middot;</span>
            <span>{relativeTime}</span>
          </>
        )}
        {fresh && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Fresh
          </span>
        )}
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
