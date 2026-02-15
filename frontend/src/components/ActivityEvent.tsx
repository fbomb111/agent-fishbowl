interface ActivityEventProps {
  type: string;
  actor: string;
  description: string;
  timestamp: string;
  url?: string;
}

const EVENT_ICONS: Record<string, string> = {
  issue_created: "📋",
  issue_closed: "✅",
  pr_opened: "🔀",
  pr_merged: "🟣",
  pr_reviewed: "👀",
  commit: "💾",
  comment: "💬",
  workflow_run: "⚙️",
};

const AGENT_COLORS: Record<string, string> = {
  pm: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  engineer:
    "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  reviewer: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

export function ActivityEvent({
  type,
  actor,
  description,
  timestamp,
  url,
}: ActivityEventProps) {
  const icon = EVENT_ICONS[type] || "📌";
  const colorClass =
    AGENT_COLORS[actor] ||
    "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  const time = new Date(timestamp).toLocaleString();

  const content = (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <span className="text-xl">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
          >
            {actor}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {time}
          </span>
        </div>
        <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
          {description}
        </p>
      </div>
    </div>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="block transition-shadow hover:shadow-md"
      >
        {content}
      </a>
    );
  }

  return content;
}
