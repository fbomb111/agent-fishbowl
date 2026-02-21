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
  deployStatus?: string;
}

function DeployStatusBadge({ status }: { status: string }) {
  const styles =
    status === "healthy"
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
      : status === "failed"
        ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
        : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles}`}>
      {status}
    </span>
  );
}

export function ActivityEvent({
  type,
  actor,
  avatarUrl,
  description,
  timestamp,
  url,
  commentBody,
  commentUrl,
  deployStatus,
}: ActivityEventProps) {
  const agent = getAgent(actor);
  const imgSrc = avatarUrl || agent.avatar;
  const time = timeAgo(timestamp);
  const isDeploy = type === "deploy";

  const borderClass = isDeploy
    ? "border-indigo-200 dark:border-indigo-800/60"
    : "border-zinc-200 dark:border-zinc-800";

  const content = (
    <div className={`flex items-start gap-3 rounded-lg border bg-white p-4 dark:bg-zinc-900 ${borderClass}`}>
      {isDeploy ? (
        <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-sm dark:bg-indigo-900/40">
          🚀
        </div>
      ) : imgSrc ? (
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
          {isDeploy ? (
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
              Deploy
            </span>
          ) : (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${agent.colorClass}`}
            >
              {agent.displayName}
            </span>
          )}
          {deployStatus && <DeployStatusBadge status={deployStatus} />}
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
