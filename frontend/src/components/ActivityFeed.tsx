"use client";

import { ActivityEvent } from "./ActivityEvent";

// Placeholder until Phase 4 connects to the GitHub API
const PLACEHOLDER_EVENTS = [
  {
    id: "1",
    type: "workflow_run",
    actor: "pm-agent",
    description:
      "Agent workflows are being set up. Once active, you'll see a live stream of agent activity here — issues created, PRs opened, code reviewed, and deployments triggered.",
    timestamp: new Date().toISOString(),
  },
];

export function ActivityFeed() {
  return (
    <div className="flex flex-col gap-3">
      {PLACEHOLDER_EVENTS.map((event) => (
        <ActivityEvent
          key={event.id}
          type={event.type}
          actor={event.actor}
          description={event.description}
          timestamp={event.timestamp}
        />
      ))}
    </div>
  );
}
