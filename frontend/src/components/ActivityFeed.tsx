"use client";

import { useEffect, useState, useCallback } from "react";
import { ActivityEvent } from "./ActivityEvent";
import { fetchActivity, type ActivityEvent as ActivityEventType } from "@/lib/api";

export function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEventType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadActivity = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActivity(1, 30);
      setEvents(data.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActivity();
  }, [loadActivity]);

  if (loading) {
    return (
      <div className="py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">
        Loading activity...
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

  if (events.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">
        No agent activity yet. Once agents start working, their GitHub activity
        will appear here.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {events.map((event) => (
        <ActivityEvent
          key={event.id}
          type={event.type}
          actor={event.actor}
          description={event.description}
          timestamp={event.timestamp}
          url={event.url}
        />
      ))}
    </div>
  );
}
