export interface AgentConfig {
  displayName: string;
  avatar: string;
  colorClass: string;
}

export const AGENTS: Record<string, AgentConfig> = {
  po: {
    displayName: "Product Owner",
    avatar: "/agents/fishbowl-po.png",
    colorClass:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  },
  engineer: {
    displayName: "Engineer",
    avatar: "/agents/fishbowl-engineer.png",
    colorClass:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  reviewer: {
    displayName: "Reviewer",
    avatar: "/agents/fishbowl-reviewer.png",
    colorClass:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  pm: {
    displayName: "PM",
    avatar: "/agents/fishbowl-pm.png",
    colorClass:
      "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  },
  "tech-lead": {
    displayName: "Tech Lead",
    avatar: "/agents/fishbowl-techlead.png",
    colorClass:
      "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300",
  },
  ux: {
    displayName: "UX",
    avatar: "/agents/fishbowl-ux.png",
    colorClass:
      "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  },
  triage: {
    displayName: "Triage",
    avatar: "/agents/fishbowl-triage.png",
    colorClass:
      "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300",
  },
  sre: {
    displayName: "SRE",
    avatar: "/agents/fishbowl-sre.png",
    colorClass: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
  human: {
    displayName: "Frankie",
    avatar: "/agents/fishbowl-human.png",
    colorClass:
      "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  },
  org: {
    displayName: "YourMoveLabs",
    avatar: "/agents/yourmove-org.png",
    colorClass:
      "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  },
};

/** Look up agent config with safe fallback for unknown keys. */
export function getAgent(key: string): AgentConfig {
  return (
    AGENTS[key] ?? {
      displayName: key,
      avatar: "",
      colorClass:
        "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    }
  );
}
