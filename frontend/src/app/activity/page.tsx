"use client";

import { useState, useEffect } from "react";
import { ActivityFeed, type TypeFilter } from "@/components/ActivityFeed";
import { AgentStatusBar } from "@/components/AgentStatusBar";
import { ActiveWorkSummary } from "@/components/ActiveWorkSummary";
import { ActivityTeamStats } from "@/components/ActivityTeamStats";
import { fetchAgentStatus, type AgentStatus, type ThreadedItem } from "@/lib/api";
import { GITHUB_REPO_URL } from "@/lib/constants";

const STATUS_POLL_INTERVAL = 30_000;

export default function ActivityPage() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [statusError, setStatusError] = useState(false);
  const [filterAgent, setFilterAgent] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<TypeFilter>("all");
  const [activityItems, setActivityItems] = useState<ThreadedItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadAgentStatus() {
      try {
        const data = await fetchAgentStatus();
        if (!cancelled) {
          setAgents(data.agents);
          setStatusError(false);
        }
      } catch {
        if (!cancelled) setStatusError(true);
      }
    }

    loadAgentStatus();
    const interval = setInterval(loadAgentStatus, STATUS_POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const typeFilters: { label: string; value: TypeFilter }[] = [
    { label: "All", value: "all" },
    { label: "Issues", value: "issues" },
    { label: "Pull Requests", value: "prs" },
    { label: "Deploys", value: "deploys" },
    { label: "Other", value: "standalone" },
  ];

  const hasActiveFilters = filterAgent !== null || filterType !== "all";

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">The Fishbowl</h1>

        <div className="mt-4">
          <ActiveWorkSummary agents={agents} items={activityItems} />
        </div>

        <a
          href={GITHUB_REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
        >
          <svg
            className="h-4 w-4"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
          </svg>
          View the public repository
        </a>
      </div>

      {/* Agent status bar */}
      <div className="mb-6">
        {statusError && agents.length === 0 && (
          <p className="mb-2 text-xs text-red-500 dark:text-red-400">
            Unable to load agent status
          </p>
        )}
        <AgentStatusBar
          agents={agents}
          activeFilter={filterAgent}
          onFilterChange={setFilterAgent}
        />
      </div>

      {/* Team performance stats */}
      <ActivityTeamStats />

      {/* Type filter pills */}
      <div className="mb-4 flex items-center gap-2">
        {typeFilters.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => setFilterType(value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              filterType === value
                ? "bg-zinc-800 text-white dark:bg-zinc-200 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
            }`}
          >
            {label}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={() => {
              setFilterAgent(null);
              setFilterType("all");
            }}
            className="ml-2 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
          >
            Clear all filters
          </button>
        )}
      </div>

      <ActivityFeed
        filterAgent={filterAgent}
        filterType={filterType}
        onItemsLoaded={setActivityItems}
      />
    </div>
  );
}
