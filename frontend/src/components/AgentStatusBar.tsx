"use client";

import { useState } from "react";
import { getAgent, AGENTS } from "@/lib/agents";
import { assetPath } from "@/lib/assetPath";
import { timeAgo } from "@/lib/timeUtils";
import type { AgentStatus } from "@/lib/api";
import { formatTokens } from "@/lib/formatTokens";

const SUMMARY_PREVIEW_LINES = 4;

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
  const [expanded, setExpanded] = useState(false);

  // Build a lookup from the status list
  const statusMap = new Map(agents.map((a) => [a.role, a]));

  // Show all known agents in a fixed order (exclude non-agent roles)
  const roles = Object.keys(AGENTS).filter(
    (r) => r !== "human" && r !== "org" && r !== "github-actions"
  );

  // Get the summary for the currently filtered agent
  const filteredStatus = activeFilter ? statusMap.get(activeFilter) : null;
  const summary = filteredStatus?.last_summary || "";
  const summaryLines = summary.split("\n");
  const isLong = summaryLines.length > SUMMARY_PREVIEW_LINES;
  const displayText = expanded
    ? summary
    : summaryLines.slice(0, SUMMARY_PREVIEW_LINES).join("\n");

  // Reset expanded state when filter changes
  const handleFilterChange = (role: string | null) => {
    setExpanded(false);
    onFilterChange(role);
  };

  return (
    <div>
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
              onClick={() => handleFilterChange(isFiltered ? null : role)}
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

      {/* Agent decision summary panel */}
      {activeFilter && summary && (
        <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800/50">
          <p className="mb-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {getAgent(activeFilter).displayName}&apos;s last report
          </p>
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-zinc-700 dark:text-zinc-300 font-sans">
            {displayText}
          </pre>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
