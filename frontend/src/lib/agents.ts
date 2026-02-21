export interface AgentConfig {
  displayName: string;
  avatar: string;
  colorClass: string;
}

export const AGENTS: Record<string, AgentConfig> = {
  "product-owner": {
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
  "product-manager": {
    displayName: "Product Manager",
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
  "user-experience": {
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
  "site-reliability": {
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
  "qa-analyst": {
    displayName: "QA Analyst",
    avatar: "https://avatars.githubusercontent.com/in/2927068?v=4",
    colorClass:
      "bg-lime-100 text-lime-700 dark:bg-lime-900 dark:text-lime-300",
  },
  "customer-ops": {
    displayName: "Customer Ops",
    avatar: "https://avatars.githubusercontent.com/in/2927082?v=4",
    colorClass:
      "bg-sky-100 text-sky-700 dark:bg-sky-900 dark:text-sky-300",
  },
  "human-ops": {
    displayName: "Human Ops",
    avatar: "https://avatars.githubusercontent.com/in/2927102?v=4",
    colorClass:
      "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900 dark:text-fuchsia-300",
  },
  "escalation-lead": {
    displayName: "Escalation Lead",
    avatar: "https://avatars.githubusercontent.com/in/2927059?v=4",
    colorClass:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  },
  "financial-analyst": {
    displayName: "Financial Analyst",
    avatar: "https://avatars.githubusercontent.com/in/2927062?v=4",
    colorClass:
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  },
  "marketing-strategist": {
    displayName: "Marketing Strategist",
    avatar: "https://avatars.githubusercontent.com/in/2927065?v=4",
    colorClass:
      "bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300",
  },
  "product-analyst": {
    displayName: "Product Analyst",
    avatar: "https://avatars.githubusercontent.com/in/2927092?v=4",
    colorClass:
      "bg-stone-100 text-stone-700 dark:bg-stone-900 dark:text-stone-300",
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
