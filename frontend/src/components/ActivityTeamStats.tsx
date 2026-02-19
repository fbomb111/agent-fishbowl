"use client";

import { fetchTeamStats, type TeamStatsResponse } from "@/lib/api";
import { getAgent } from "@/lib/agents";
import { assetPath } from "@/lib/assetPath";
import { useFetch } from "@/hooks/useFetch";
import { ErrorFallback } from "./ErrorFallback";

export function ActivityTeamStats() {
  const { data: stats, error, retry } = useFetch<TeamStatsResponse>(fetchTeamStats);

  if (error) {
    return (
      <div className="mb-6">
        <ErrorFallback message="Unable to load team stats" onRetry={retry} />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="mb-6 animate-pulse">
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      </div>
    );
  }

  const sortedAgents = [...stats.agents].sort(
    (a, b) => b.issues_closed + b.prs_merged - (a.issues_closed + a.prs_merged)
  );

  return (
    <div className="mb-6 space-y-4">
      <h2 className="text-sm font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        Last 7 Days
      </h2>

      {/* Summary stat cards */}
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Issues Closed
          </div>
          <div className="mt-1 text-2xl font-bold tabular-nums">
            {stats.issues_closed}
          </div>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            PRs Merged
          </div>
          <div className="mt-1 text-2xl font-bold tabular-nums">
            {stats.prs_merged}
          </div>
        </div>
        {stats.avg_pr_cycle_hours !== null && (
          <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              Avg PR Cycle
            </div>
            <div className="mt-1 text-2xl font-bold tabular-nums">
              {stats.avg_pr_cycle_hours < 1
                ? `${Math.round(stats.avg_pr_cycle_hours * 60)}m`
                : `${stats.avg_pr_cycle_hours}h`}
            </div>
          </div>
        )}
      </div>

      {/* Per-agent breakdown */}
      {sortedAgents.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-100 dark:border-zinc-800">
                <th className="px-4 py-2.5 text-left font-medium text-zinc-400 dark:text-zinc-500">
                  Agent
                </th>
                <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
                  Issues Closed
                </th>
                <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
                  PRs Merged
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedAgents.map((agentStats) => {
                const agent = getAgent(agentStats.role);
                return (
                  <tr
                    key={agentStats.role}
                    className="border-b border-zinc-50 last:border-0 dark:border-zinc-800/50"
                  >
                    <td className="px-4 py-2 font-medium">
                      <div className="flex items-center gap-2">
                        {agent.avatar && (
                          <img
                            src={assetPath(agent.avatar)}
                            alt={agent.displayName}
                            width={20}
                            height={20}
                            className="rounded-full"
                          />
                        )}
                        {agent.displayName}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {agentStats.issues_closed}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {agentStats.prs_merged}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
