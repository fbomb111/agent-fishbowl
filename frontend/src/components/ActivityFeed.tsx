"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ActivityEvent } from "./ActivityEvent";
import { ActivityThread } from "./ActivityThread";
import {
  fetchThreadedActivity,
  type ThreadedItem,
  type ActivityEvent as ActivityEventType,
} from "@/lib/api";

const POLL_INTERVAL = 30_000; // 30 seconds

export type TypeFilter = "all" | "issues" | "prs" | "standalone";

interface ActivityFeedProps {
  filterAgent?: string | null;
  filterType?: TypeFilter;
  onItemsLoaded?: (items: ThreadedItem[]) => void;
}

function filterThreadedItems(
  items: ThreadedItem[],
  agent: string
): ThreadedItem[] {
  return items.filter((item) => {
    if (item.type === "standalone") return item.event.actor === agent;
    // Show the full thread if the agent participated in any event
    return item.events.some((e) => e.actor === agent);
  });
}

function filterByType(items: ThreadedItem[], type: TypeFilter): ThreadedItem[] {
  if (type === "all") return items;
  return items.filter((item) => {
    if (type === "standalone") return item.type === "standalone";
    if (type === "issues")
      return item.type === "thread" && item.subject_type === "issue";
    if (type === "prs")
      return item.type === "thread" && item.subject_type === "pr";
    return true;
  });
}

export function ActivityFeed({
  filterAgent,
  filterType = "all",
  onItemsLoaded,
}: ActivityFeedProps) {
  const [items, setItems] = useState<ThreadedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isFirstLoad = useRef(true);

  const loadActivity = useCallback(async () => {
    if (isFirstLoad.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await fetchThreadedActivity(50);
      setItems(data.threads);
      onItemsLoaded?.(data.threads);
    } catch (err) {
      if (isFirstLoad.current) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setLoading(false);
      isFirstLoad.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadActivity();
    const interval = setInterval(loadActivity, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [loadActivity]);

  if (loading) {
    return (
      <div
        className="flex flex-col gap-4"
        aria-busy="true"
        aria-label="Loading activity"
      >
        {/* Skeleton thread card */}
        <div className="animate-pulse overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800">
            <div className="h-5 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
            <div className="h-4 w-48 rounded bg-zinc-100 dark:bg-zinc-800" />
          </div>
          <div className="space-y-4 px-4 py-3">
            {[1, 2].map((i) => (
              <div key={i} className="flex gap-3">
                <div className="h-6 w-6 shrink-0 rounded-full bg-zinc-100 dark:bg-zinc-800" />
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="h-5 w-20 rounded-full bg-zinc-100 dark:bg-zinc-800" />
                    <div className="h-4 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
                  </div>
                  <div className="h-4 w-3/4 rounded bg-zinc-100 dark:bg-zinc-800" />
                </div>
              </div>
            ))}
          </div>
        </div>
        {/* Skeleton standalone events */}
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex animate-pulse items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="mt-0.5 h-7 w-7 shrink-0 rounded-full bg-zinc-100 dark:bg-zinc-800" />
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-5 w-20 rounded-full bg-zinc-100 dark:bg-zinc-800" />
                <div className="h-4 w-16 rounded bg-zinc-100 dark:bg-zinc-800" />
              </div>
              <div className="h-4 w-3/4 rounded bg-zinc-100 dark:bg-zinc-800" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-12 text-center text-sm text-red-500">
        <p>Failed to load activity: {error}</p>
        <button
          onClick={loadActivity}
          className="mt-3 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:bg-red-700 dark:hover:bg-red-600"
        >
          Retry
        </button>
      </div>
    );
  }

  let displayed = filterAgent
    ? filterThreadedItems(items, filterAgent)
    : items;

  displayed = filterByType(displayed, filterType);

  if (displayed.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">
        {filterAgent || filterType !== "all"
          ? "No matching activity found."
          : "No agent activity yet. Once agents start working, their GitHub activity will appear here."}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 text-right text-[11px] text-zinc-400 dark:text-zinc-500">
        Auto-refreshing every 30s
      </div>
      <div className="flex flex-col gap-4">
        {displayed.map((item) => {
          if (item.type === "thread") {
            return (
              <ActivityThread
                key={`${item.subject_type}:${item.subject_number}`}
                subjectType={item.subject_type}
                subjectNumber={item.subject_number}
                subjectTitle={item.subject_title}
                events={item.events}
              />
            );
          }
          const evt = item.event as ActivityEventType;
          return (
            <ActivityEvent
              key={evt.id}
              type={evt.type}
              actor={evt.actor}
              description={evt.description}
              timestamp={evt.timestamp}
              url={evt.url}
              commentBody={evt.comment_body}
              commentUrl={evt.comment_url}
            />
          );
        })}
      </div>
    </div>
  );
}
