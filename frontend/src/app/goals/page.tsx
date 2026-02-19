"use client";

import { useEffect, useState } from "react";
import { fetchGoals, type GoalsResponse } from "@/lib/api";
import { GoalCard } from "@/components/GoalCard";
import { RoadmapList } from "@/components/RoadmapList";
import { MetricsGrid } from "@/components/MetricsGrid";
import { timeAgo } from "@/lib/timeUtils";

function LoadingSkeleton() {
  return (
    <div className="space-y-10" aria-busy="true" aria-label="Loading dashboard data">
      {/* Title + mission */}
      <div>
        <div className="h-9 w-32 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-800" />
        <div className="mt-3 h-5 w-full max-w-xl animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
        <div className="mt-2 h-5 w-3/4 max-w-md animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
      </div>

      {/* Goal cards 2x2 */}
      <div className="grid gap-4 sm:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-44 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800"
          />
        ))}
      </div>

      {/* Roadmap */}
      <div>
        <div className="mb-4 h-7 w-28 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-lg border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800"
            />
          ))}
        </div>
      </div>

      {/* Metrics */}
      <div>
        <div className="mb-4 h-7 w-36 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
        <div className="grid gap-4 grid-cols-2">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800"
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function GoalsPage() {
  const [data, setData] = useState<GoalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGoals()
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <LoadingSkeleton />;

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900/30 dark:bg-red-950/30">
        <p className="text-sm text-red-600 dark:text-red-400">
          Failed to load goals: {error}
        </p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-10">
      {/* Mission */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Goals</h1>
        {data.mission && (
          <p className="mt-2 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
            {data.mission}
          </p>
        )}
      </div>

      {/* Goal cards */}
      <section>
        {data.goals.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {data.goals.map((goal) => (
              <GoalCard key={goal.number} goal={goal} />
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
            No goals defined yet. Goals will appear here once configured.
          </p>
        )}
        {data.constraints.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {data.constraints.map((c) => (
              <span
                key={c}
                className="rounded-full border border-zinc-200 px-3 py-1 text-xs font-medium text-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
              >
                {c}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Roadmap snapshot */}
      <section>
        <h2 className="mb-4 text-xl font-semibold tracking-tight">Roadmap</h2>
        <RoadmapList roadmap={data.roadmap} />
      </section>

      {/* Metrics */}
      <section>
        <h2 className="mb-4 text-xl font-semibold tracking-tight">
          Agent Metrics
        </h2>
        <MetricsGrid metrics={data.metrics} />
      </section>

      {/* Freshness */}
      {data.fetched_at && (
        <p className="text-center text-xs text-zinc-400 dark:text-zinc-500">
          Updated {timeAgo(data.fetched_at, true)}
        </p>
      )}
    </div>
  );
}
