import type { Goal } from "@/lib/api";

const GOAL_ACCENTS: Record<number, string> = {
  1: "border-l-blue-500",
  2: "border-l-amber-500",
  3: "border-l-green-500",
  4: "border-l-purple-500",
};

interface GoalCardProps {
  goal: Goal;
}

export function GoalCard({ goal }: GoalCardProps) {
  const accent = GOAL_ACCENTS[goal.number] || "border-l-zinc-400";

  return (
    <div
      className={`rounded-xl border border-zinc-200 bg-white p-5 border-l-4 ${accent} dark:border-zinc-800 dark:bg-zinc-900`}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
          Goal {goal.number}
        </span>
      </div>
      <h3 className="mt-1 text-lg font-semibold leading-snug">{goal.title}</h3>
      {goal.summary && (
        <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {goal.summary}
        </p>
      )}
      {goal.examples.length > 0 && (
        <ul className="mt-3 space-y-1">
          {goal.examples.map((ex, i) => (
            <li
              key={i}
              className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400"
            >
              <span className="mr-1.5 text-zinc-300 dark:text-zinc-600">
                &bull;
              </span>
              {ex}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
