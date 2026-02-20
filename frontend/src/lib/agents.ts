export interface AgentConfig {
  displayName: string;
  avatar: string;
  colorClass: string;
}

export const AGENTS: Record<string, AgentConfig> = {
  po: {
    displayName: "Product Owner",
    avatar: "https://avatars.githubusercontent.com/in/2868620?v=4",
    colorClass:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  },
  engineer: {
    displayName: "Engineer",
    avatar: "https://avatars.githubusercontent.com/in/2866317?v=4",
    colorClass:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  reviewer: {
    displayName: "Reviewer",
    avatar: "https://avatars.githubusercontent.com/in/2866348?v=4",
    colorClass:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  pm: {
    displayName: "PM",
    avatar: "https://avatars.githubusercontent.com/in/2866375?v=4",
    colorClass:
      "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  },
  "tech-lead": {
    displayName: "Tech Lead",
    avatar: "https://avatars.githubusercontent.com/in/2868643?v=4",
    colorClass:
      "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300",
  },
  ux: {
    displayName: "UX",
    avatar: "https://avatars.githubusercontent.com/in/2868667?v=4",
    colorClass:
      "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  },
  triage: {
    displayName: "Triage",
    avatar: "https://avatars.githubusercontent.com/in/2868661?v=4",
    colorClass:
      "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300",
  },
  "ops-engineer": {
    displayName: "Ops Engineer",
    avatar: "https://avatars.githubusercontent.com/in/2902244?v=4",
    colorClass:
      "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  },
  sre: {
    displayName: "SRE",
    avatar: "https://avatars.githubusercontent.com/in/2868629?v=4",
    colorClass: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
  "content-creator": {
    displayName: "Content Creator",
    avatar: "https://avatars.githubusercontent.com/in/2881943?v=4",
    colorClass:
      "bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-300",
  },
  writer: {
    displayName: "Writer",
    avatar: "https://avatars.githubusercontent.com/in/2881943?v=4",
    colorClass:
      "bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-300",
  },
  "github-actions": {
    displayName: "GitHub Actions",
    avatar: "https://avatars.githubusercontent.com/in/15368?v=4",
    colorClass:
      "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  },
  human: {
    displayName: "Frankie",
    avatar: "https://avatars.githubusercontent.com/u/482183?v=4",
    colorClass:
      "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  },
  org: {
    displayName: "YourMoveLabs",
    avatar: "https://avatars.githubusercontent.com/u/261773100?v=4",
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
