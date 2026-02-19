"use client";

import { useCallback } from "react";
import Link from "next/link";
import { fetchGoals, type Metrics } from "@/lib/api";
import { useFetch } from "@/hooks/useFetch";

function StatItem({ value, label }: { value: number; label: string }) {
  return (
    <div className="text-center">
      <div className="text-3xl font-bold tabular-nums sm:text-4xl">{value}</div>
      <div className="mt-1 text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        {label}
      </div>
    </div>
  );
}

export function TeamStats() {
  const fetchMetrics = useCallback(
    () => fetchGoals().then((data) => data.metrics),
    []
  );
  const { data: metrics } = useFetch<Metrics>(fetchMetrics);

  if (!metrics) return null;

  const agentCount = Object.keys(metrics.by_agent).filter(
    (role) => role !== "human" && role !== "org" && role !== "github-actions"
  ).length;

  return (
    <section className="mb-10 rounded-2xl border border-zinc-200 bg-white px-6 py-8 dark:border-zinc-800 dark:bg-zinc-900 sm:px-10">
      <div className="mb-6 text-center">
        <h2 className="text-lg font-semibold tracking-tight">
          Built by AI Agents
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Activity from the last 30 days
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4 sm:gap-8">
        <StatItem value={metrics.issues_closed["30d"]} label="Issues Closed" />
        <StatItem value={metrics.prs_merged["30d"]} label="PRs Merged" />
        <StatItem value={agentCount} label="Active Agents" />
      </div>

      <div className="mt-6 text-center">
        <Link
          href="/goals"
          className="text-sm font-medium text-zinc-500 transition-colors hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          View full dashboard &rarr;
        </Link>
      </div>
    </section>
  );
}
