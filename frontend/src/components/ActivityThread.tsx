"use client";

import { useState } from "react";
import { getAgent } from "@/lib/agents";
import { assetPath } from "@/lib/assetPath";
import { timeAgo } from "@/lib/timeUtils";
import type { ActivityEvent as ActivityEventType } from "@/lib/api";

interface ThreadEventProps {
  event: ActivityEventType;
  isLast: boolean;
}

function ThreadEvent({ event, isLast }: ThreadEventProps) {
  const agent = getAgent(event.actor);
  const content = (
    <div className="flex gap-3">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        {agent.avatar ? (
          <img
            src={assetPath(agent.avatar)}
            alt={agent.displayName}
            width={24}
            height={24}
            className="rounded-full shrink-0"
          />
        ) : (
          <div className="h-6 w-6 rounded-full bg-zinc-200 dark:bg-zinc-700 shrink-0" />
        )}
        {!isLast && (
          <div className="mt-1 flex-1 w-px bg-zinc-200 dark:bg-zinc-700" />
        )}
      </div>
      {/* Event content */}
      <div className="min-w-0 flex-1 pb-4">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${agent.colorClass}`}
          >
            {agent.displayName}
          </span>
          <span className="text-[11px] text-zinc-400 dark:text-zinc-500">
            {timeAgo(event.timestamp)}
          </span>
        </div>
        <p className="mt-0.5 text-sm text-zinc-700 dark:text-zinc-300">
          {event.description}
        </p>
      </div>
    </div>
  );

  if (event.url) {
    return (
      <a
        href={event.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
      >
        {content}
      </a>
    );
  }
  return content;
}

interface ActivityThreadProps {
  subjectType: "issue" | "pr";
  subjectNumber: number;
  subjectTitle: string;
  events: ActivityEventType[];
}

export function ActivityThread({
  subjectType,
  subjectNumber,
  subjectTitle,
  events,
}: ActivityThreadProps) {
  const [expanded, setExpanded] = useState(events.length <= 4);

  // Determine thread status from the events
  const lastEvent = events[events.length - 1];
  const isClosed =
    lastEvent?.type === "issue_closed" || lastEvent?.type === "pr_merged";
  const isMerged = lastEvent?.type === "pr_merged";

  const visibleEvents = expanded ? events : events.slice(-2);
  const hiddenCount = events.length - visibleEvents.length;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
      {/* Thread header */}
      <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800">
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
            subjectType === "pr"
              ? isMerged
                ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300"
                : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
              : isClosed
                ? "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                : "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
          }`}
        >
          {subjectType === "pr" ? "PR" : "Issue"} #{subjectNumber}
        </span>
        <span className="min-w-0 text-sm font-medium text-zinc-800 dark:text-zinc-200">
          {subjectTitle}
        </span>
        {isMerged && (
          <span className="ml-auto shrink-0 text-[10px] font-medium text-purple-600 dark:text-purple-400">
            Merged
          </span>
        )}
        {isClosed && !isMerged && (
          <span className="ml-auto shrink-0 text-[10px] font-medium text-zinc-500">
            Closed
          </span>
        )}
      </div>

      {/* Thread events */}
      <div className="px-4 pt-3">
        {hiddenCount > 0 && (
          <button
            onClick={() => setExpanded(true)}
            className="mb-3 flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
          >
            <svg
              className="h-3 w-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 9l-7 7-7-7"
              />
            </svg>
            Show {hiddenCount} earlier{" "}
            {hiddenCount === 1 ? "event" : "events"}
          </button>
        )}
        {visibleEvents.map((event, idx) => (
          <ThreadEvent
            key={event.id}
            event={event}
            isLast={idx === visibleEvents.length - 1}
          />
        ))}
      </div>
    </div>
  );
}
