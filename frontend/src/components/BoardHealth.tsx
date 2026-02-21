"use client";

import { useCallback } from "react";
import { fetchBoardHealth, type BoardHealthResponse } from "@/lib/api";
import { useFetch } from "@/hooks/useFetch";
import { ErrorFallback } from "./ErrorFallback";

const STATUS_COLORS: Record<string, string> = {
  Done: "bg-emerald-500 dark:bg-emerald-400",
  "In Progress": "bg-blue-500 dark:bg-blue-400",
  Todo: "bg-zinc-300 dark:bg-zinc-600",
};

function StatusBar({ byStatus, total }: { byStatus: Record<string, number>; total: number }) {
  if (total === 0) return null;

  const ordered = ["Done", "In Progress", "Todo"];
  const segments = ordered
    .filter((s) => byStatus[s])
    .map((status) => ({
      status,
      count: byStatus[status],
      pct: Math.round((byStatus[status] / total) * 100),
    }));

  // Include any statuses not in the ordered list
  for (const [status, count] of Object.entries(byStatus)) {
    if (!ordered.includes(status)) {
      segments.push({ status, count, pct: Math.round((count / total) * 100) });
    }
  }

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        {segments.map(({ status, pct }) => (
          <div
            key={status}
            className={`h-full transition-all ${STATUS_COLORS[status] || "bg-zinc-400 dark:bg-zinc-500"}`}
            style={{ width: `${pct}%` }}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {segments.map(({ status, count }) => (
          <div key={status} className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
            <div
              className={`h-2 w-2 rounded-full ${STATUS_COLORS[status] || "bg-zinc-400 dark:bg-zinc-500"}`}
            />
            <span>
              {status}: {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function BoardHealth() {
  const fetchData = useCallback(() => fetchBoardHealth(), []);
  const { data, error, retry } = useFetch<BoardHealthResponse>(fetchData);

  if (error) {
    return <ErrorFallback message="Unable to load board health" onRetry={retry} />;
  }

  if (!data) return null;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
          Board Health
        </div>
        <span className="text-xs tabular-nums text-zinc-400 dark:text-zinc-500">
          {data.total_items} items
        </span>
      </div>
      <StatusBar byStatus={data.by_status} total={data.total_items} />
      {data.draft_items > 0 && (
        <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
          {data.draft_items} draft {data.draft_items === 1 ? "item" : "items"} (not yet converted to issues)
        </p>
      )}
    </div>
  );
}
