import { getAgent } from "@/lib/agents";
import { timeAgo } from "@/lib/timeUtils";

interface ActivityEventProps {
  type: string;
  actor: string;
  avatarUrl?: string;
  description: string;
  timestamp: string;
  url?: string;
  commentBody?: string;
  commentUrl?: string;
}

export function ActivityEvent({
  actor,
  avatarUrl,
  description,
  timestamp,
  url,
  commentBody,
  commentUrl,
}: ActivityEventProps) {
  const agent = getAgent(actor);
  const imgSrc = avatarUrl || agent.avatar;
  const time = timeAgo(timestamp);

  const content = (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      {imgSrc ? (
        <img
          src={imgSrc}
          alt={agent.displayName}
          width={28}
          height={28}
          className="mt-0.5 rounded-full"
        />
      ) : (
        <div className="mt-0.5 h-7 w-7 rounded-full bg-zinc-200 dark:bg-zinc-700" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${agent.colorClass}`}
          >
            {agent.displayName}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {time}
          </span>
        </div>
        <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
          {description}
        </p>
        {commentBody && (
          <div className="mt-2 rounded-md bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
            <p className="whitespace-pre-line">{commentBody}</p>
            {commentUrl && (
              <a
                href={commentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-blue-600 hover:text-blue-500 dark:text-blue-400"
              >
                View full comment on GitHub &rarr;
              </a>
            )}
          </div>
        )}
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
