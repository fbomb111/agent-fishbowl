import Image from "next/image";
import { getAgent } from "@/lib/agents";

interface ActivityEventProps {
  type: string;
  actor: string;
  description: string;
  timestamp: string;
  url?: string;
}

export function ActivityEvent({
  actor,
  description,
  timestamp,
  url,
}: ActivityEventProps) {
  const agent = getAgent(actor);
  const time = new Date(timestamp).toLocaleString();

  const content = (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      {agent.avatar ? (
        <Image
          src={agent.avatar}
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
