"use client";

import { useEffect, useState } from "react";
import { ActivityEvent } from "./ActivityEvent";
import { fetchActivity, type ActivityEvent as ActivityEventType } from "@/lib/api";

export function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEventType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchActivity(1, 30)
      .then((data) => {
        setEvents(data.events);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

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
        Failed to load activity: {error}
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
