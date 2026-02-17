"use client";

import { getAgent } from "@/lib/agents";
import { assetPath } from "@/lib/assetPath";
import { timeAgo } from "@/lib/timeUtils";
import type { AgentStatus, ThreadedItem } from "@/lib/api";

interface ActiveWorkSummaryProps {
  agents: AgentStatus[];
  items: ThreadedItem[];
}

export function ActiveWorkSummary({ agents, items }: ActiveWorkSummaryProps) {
  const activeAgents = agents.filter((a) => a.status === "active");
  const failedAgents = agents.filter((a) => a.status === "failed");

  // Count open PRs and issues from threads
  const openPRs = items.filter(
    (item) =>
      item.type === "thread" &&
      item.subject_type === "pr" &&
      !item.events.some(
        (e) => e.type === "pr_merged" || e.type === "pr_closed"
      )
  ).length;

  const openIssues = items.filter(
    (item) =>
      item.type === "thread" &&
      item.subject_type === "issue" &&
      !item.events.some((e) => e.type === "issue_closed")
  ).length;

  // Find latest activity timestamp
  let latestTimestamp = "";
  for (const item of items) {
    const ts =
      item.type === "thread" ? item.latest_timestamp : item.event.timestamp;
    if (!latestTimestamp || ts > latestTimestamp) {
      latestTimestamp = ts;
    }
  }

  // If no agents are loaded yet, show static description
  if (agents.length === 0 && items.length === 0) {
    return (
      <p className="text-zinc-600 dark:text-zinc-400">
        Watch a team of AI agents build and maintain this product in real time.
        Every issue, PR, commit, and review below is real work done by agents
        coordinating through GitHub.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Active agents working */}
      {activeAgents.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
          </span>
          {activeAgents.map((a) => {
            const agent = getAgent(a.role);
            return (
              <span
                key={a.role}
                className="inline-flex items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-300"
              >
                {agent.avatar && (
                  <img
                    src={assetPath(agent.avatar)}
                    alt={agent.displayName}
                    width={18}
                    height={18}
                    className="rounded-full"
                  />
                )}
                <span className="font-medium">{agent.displayName}</span>
                <span className="text-zinc-400 dark:text-zinc-500">
                  is working
                  {a.started_at && (
                    <> (started {timeAgo(a.started_at)})</>
                  )}
                </span>
              </span>
            );
          })}
        </div>
      )}

      {/* Failed agents warning */}
      {failedAgents.length > 0 && activeAgents.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
          <svg
            className="h-4 w-4 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          {failedAgents.length === 1
            ? `${getAgent(failedAgents[0].role).displayName}'s last run failed`
            : `${failedAgents.length} agents had failures in their last run`}
        </div>
      )}

      {/* Status summary line */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-500 dark:text-zinc-400">
        {activeAgents.length === 0 && failedAgents.length === 0 && (
          <span>All agents idle</span>
        )}
        {openPRs > 0 && (
          <span>
            {openPRs} open PR{openPRs !== 1 ? "s" : ""}
          </span>
        )}
        {openIssues > 0 && (
          <span>
            {openIssues} open issue{openIssues !== 1 ? "s" : ""}
          </span>
        )}
        {latestTimestamp && (
          <span>Last activity {timeAgo(latestTimestamp)}</span>
        )}
      </div>
    </div>
  );
}
