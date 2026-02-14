interface ArticleCardProps {
  title: string;
  source: string;
  summary: string;
  originalUrl: string;
  publishedAt: string;
  categories: string[];
  imageUrl?: string;
  readTimeMinutes?: number;
}

export function ArticleCard({
  title,
  source,
  summary,
  originalUrl,
  publishedAt,
  categories,
  imageUrl,
  readTimeMinutes,
}: ArticleCardProps) {
  const date = new Date(publishedAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

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
            alt=""
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
        {summary}
      </p>
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
