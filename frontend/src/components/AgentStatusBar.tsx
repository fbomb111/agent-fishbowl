"use client";

import { getAgent, AGENTS } from "@/lib/agents";
import { assetPath } from "@/lib/assetPath";
import { timeAgo } from "@/lib/timeUtils";
import type { AgentStatus } from "@/lib/api";
import { formatTokens } from "@/lib/formatTokens";

interface AgentStatusBarProps {
  agents: AgentStatus[];
  activeFilter: string | null;
  onFilterChange: (role: string | null) => void;
}

export function AgentStatusBar({
  agents,
  activeFilter,
  onFilterChange,
}: AgentStatusBarProps) {
  // Build a lookup from the status list
  const statusMap = new Map(agents.map((a) => [a.role, a]));

  // Show all known agents in a fixed order (exclude non-agent roles)
  const roles = Object.keys(AGENTS).filter(
    (r) => r !== "human" && r !== "org" && r !== "github-actions"
  );

  return (
    <div className="grid grid-cols-4 gap-2 sm:flex sm:gap-3 sm:overflow-x-auto sm:pb-2">
      {roles.map((role) => {
        const agent = getAgent(role);
        const status = statusMap.get(role);
        const isActive = status?.status === "active";
        const isFailed = status?.status === "failed";
        const isFiltered = activeFilter === role;

        let lastSeen = "";
        if (isActive && status?.started_at) {
          lastSeen = "active now";
        } else if (status?.last_completed_at) {
          lastSeen = timeAgo(status.last_completed_at);
        }

        return (
          <button
            key={role}
            onClick={() => onFilterChange(isFiltered ? null : role)}
            className={`flex flex-col items-center gap-1 rounded-lg px-3 py-2 transition-colors ${
              isFiltered
                ? "bg-zinc-200 dark:bg-zinc-700"
                : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
            }`}
          >
            <div className="relative">
              {agent.avatar ? (
                <img
                  src={assetPath(agent.avatar)}
                  alt={agent.displayName}
                  width={32}
                  height={32}
                  className="rounded-full"
                />
              ) : (
                <div className="h-8 w-8 rounded-full bg-zinc-300 dark:bg-zinc-600" />
              )}
              {/* Status dot */}
              <span
                className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white dark:border-zinc-900 ${
                  isActive
                    ? "bg-green-500 animate-pulse"
                    : isFailed
                      ? "bg-red-500"
                      : "bg-zinc-300 dark:bg-zinc-600"
                }`}
              />
            </div>
            <span className="text-[10px] font-medium text-zinc-600 dark:text-zinc-400 whitespace-nowrap">
              {agent.displayName}
            </span>
            {lastSeen && (
              <span className="text-[9px] text-zinc-400 dark:text-zinc-500 whitespace-nowrap">
                {lastSeen}
              </span>
            )}
            {status?.usage &&
              (status.usage.input_tokens != null ||
                status.usage.output_tokens != null) && (
                <span className="text-[9px] text-zinc-500 dark:text-zinc-400 whitespace-nowrap font-mono">
                  {status.usage.input_tokens != null && (
                    <>↑{formatTokens(status.usage.input_tokens)}</>
                  )}{" "}
                  {status.usage.output_tokens != null && (
                    <>↓{formatTokens(status.usage.output_tokens)}</>
                  )}
                </span>
              )}
            {status?.usage?.cost_usd != null && (
              <span className="text-[9px] text-emerald-600 dark:text-emerald-400 whitespace-nowrap font-mono">
                ${status.usage.cost_usd.toFixed(2)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
