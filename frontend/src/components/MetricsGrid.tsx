import type { Metrics, TrendWindow, AgentStats } from "@/lib/api";

function TrendBar({
  label,
  window,
}: {
  label: string;
  window: TrendWindow;
}) {
  const max = Math.max(window["24h"], window["7d"], window["30d"], 1);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        {label}
      </div>
      <div className="mt-3 space-y-2">
        {(["24h", "7d", "30d"] as const).map((period) => {
          const value = window[period];
          const pct = Math.round((value / max) * 100);
          return (
            <div key={period} className="flex items-center gap-2">
              <span className="w-7 text-right text-[11px] text-zinc-400 dark:text-zinc-500">
                {period}
              </span>
              <div className="flex-1 h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-500 dark:bg-blue-400 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-6 text-right text-xs font-semibold tabular-nums">
                {value}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

const AGENT_DISPLAY: Record<string, string> = {
  engineer: "Engineer",
  reviewer: "Reviewer",
  "tech-lead": "Tech Lead",
  pm: "PM",
  po: "Product Owner",
  triage: "Triage",
  "ux-reviewer": "UX Reviewer",
};

function AgentTable({ byAgent }: { byAgent: Record<string, AgentStats> }) {
  const agents = Object.entries(byAgent).sort(
    ([, a], [, b]) =>
      b.commits + b.prs_merged + b.issues_closed -
      (a.commits + a.prs_merged + a.issues_closed)
  );

  if (agents.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
        No agent activity yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-100 dark:border-zinc-800">
            <th className="px-4 py-2.5 text-left font-medium text-zinc-400 dark:text-zinc-500">
              Agent
            </th>
            <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
              Commits
            </th>
            <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
              PRs (m/o)
            </th>
            <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
              Issues (c/o)
            </th>
            <th className="px-3 py-2.5 text-right font-medium text-zinc-400 dark:text-zinc-500">
              Reviews
            </th>
          </tr>
        </thead>
        <tbody>
          {agents.map(([role, stats]) => (
            <tr
              key={role}
              className="border-b border-zinc-50 last:border-0 dark:border-zinc-800/50"
            >
              <td className="px-4 py-2 font-medium">
                {AGENT_DISPLAY[role] || role}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {stats.commits}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {stats.prs_merged}/{stats.prs_opened}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {stats.issues_closed}/{stats.issues_opened}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {stats.reviews}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface MetricsGridProps {
  metrics: Metrics;
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  return (
    <div className="space-y-4">
      {/* Current snapshot */}
      <div className="grid gap-4 grid-cols-2">
        <StatCard label="Open Issues" value={metrics.open_issues} />
        <StatCard label="Open PRs" value={metrics.open_prs} />
      </div>

      {/* Trend windows */}
      <div className="grid gap-4 sm:grid-cols-3">
        <TrendBar label="Issues Closed" window={metrics.issues_closed} />
        <TrendBar label="PRs Merged" window={metrics.prs_merged} />
        <TrendBar label="Commits" window={metrics.commits} />
      </div>

      {/* Agent breakdown */}
      <AgentTable byAgent={metrics.by_agent} />
    </div>
  );
}
