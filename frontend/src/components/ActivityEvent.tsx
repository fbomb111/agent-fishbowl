import Image from "next/image";
import { getAgent } from "@/lib/agents";

interface ActivityEventProps {
  type: string;
  actor: string;
  description: string;
  timestamp: string;
  url?: string;
}

const EVENT_ICONS: Record<string, { emoji: string; label: string }> = {
  issue_created: { emoji: "\uD83D\uDCCB", label: "Issue created" },
  issue_closed: { emoji: "\u2705", label: "Issue closed" },
  pr_opened: { emoji: "\uD83D\uDD00", label: "Pull request opened" },
  pr_merged: { emoji: "\uD83D\uDFE3", label: "Pull request merged" },
  pr_reviewed: { emoji: "\uD83D\uDC40", label: "Pull request reviewed" },
  commit: { emoji: "\uD83D\uDCBE", label: "Commit" },
  comment: { emoji: "\uD83D\uDCAC", label: "Comment" },
  workflow_run: { emoji: "\u2699\uFE0F", label: "Workflow run" },
};

export function ActivityEvent({
  type,
  actor,
  description,
  timestamp,
  url,
}: ActivityEventProps) {
  const eventIcon = EVENT_ICONS[type] || { emoji: "\uD83D\uDCCC", label: "Event" };
  const agent = getAgent(actor);
  const time = new Date(timestamp).toLocaleString();

  const content = (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <span className="text-xl" role="img" aria-label={eventIcon.label}>{eventIcon.emoji}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {agent.avatar && (
            <Image
              src={agent.avatar}
              alt={agent.displayName}
              width={24}
              height={24}
              className="rounded-full"
            />
          )}
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
