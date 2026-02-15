import type { RoadmapSnapshot } from "@/lib/api";

const PRIORITY_STYLES: Record<string, string> = {
  "P1 - Must Have":
    "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  "P2 - Should Have":
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  "P3 - Nice to Have":
    "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

function PriorityBadge({ priority }: { priority: string }) {
  const label = priority.split(" - ")[0] || priority;
  const style =
    PRIORITY_STYLES[priority] ||
    "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style}`}>
      {label}
    </span>
  );
}

interface RoadmapListProps {
  roadmap: RoadmapSnapshot;
}

export function RoadmapList({ roadmap }: RoadmapListProps) {
  const { active, counts } = roadmap;
  const total = counts.proposed + counts.active + counts.done + counts.deferred;

  return (
    <div>
      {/* Summary bar */}
      <div className="mb-4 flex flex-wrap gap-3 text-xs">
        <span className="rounded-full bg-blue-100 px-2.5 py-1 font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
          {counts.active} active
        </span>
        <span className="rounded-full bg-zinc-100 px-2.5 py-1 font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
          {counts.proposed} proposed
        </span>
        <span className="rounded-full bg-green-100 px-2.5 py-1 font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300">
          {counts.done} done
        </span>
        {counts.deferred > 0 && (
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500">
            {counts.deferred} deferred
          </span>
        )}
        <span className="ml-auto text-zinc-400 dark:text-zinc-500">
          {total} total items
        </span>
      </div>

      {/* Active items */}
      {active.length === 0 ? (
        <p className="py-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
          No active roadmap items right now.
        </p>
      ) : (
        <div className="space-y-2">
          {active.map((item, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <span className="flex-1 text-sm font-medium">{item.title}</span>
              <div className="flex shrink-0 items-center gap-2">
                {item.priority && <PriorityBadge priority={item.priority} />}
                {item.goal && (
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                    {item.goal}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
