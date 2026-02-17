import Image from "next/image";
import { AGENTS } from "@/lib/agents";

interface TeamMember {
  key: string;
  role: string;
  description: string;
  responsibilities: string[];
}

const TEAM: TeamMember[] = [
  {
    key: "po",
    role: "Product Owner",
    description:
      "Central intake funnel. Triages all inputs into a prioritized backlog and decides what gets built next.",
    responsibilities: [
      "Prioritizes issues from all intake sources",
      "Creates actionable issues from roadmap items",
      "Dispatches work to the Engineer",
      "Manages the feedback loop with the PM",
    ],
  },
  {
    key: "engineer",
    role: "Engineer",
    description:
      "Picks issues, implements code changes, and opens pull requests. The builder of the team.",
    responsibilities: [
      "Claims and implements issues from the backlog",
      "Opens pull requests with passing quality checks",
      "Addresses review feedback from the Reviewer",
      "Follows project conventions and coding standards",
    ],
  },
  {
    key: "reviewer",
    role: "Reviewer",
    description:
      "Reviews pull requests for quality, correctness, and adherence to standards. The quality gate.",
    responsibilities: [
      "Reviews all incoming pull requests",
      "Approves and merges PRs that meet standards",
      "Requests changes with specific, actionable feedback",
      "Files backlog issues for improvements found during review",
    ],
  },
  {
    key: "pm",
    role: "Product Manager",
    description:
      "Sets strategic direction and manages the product roadmap. Thinks about where the product should go.",
    responsibilities: [
      "Maintains the GitHub Project roadmap",
      "Reviews issues for strategic alignment",
      "Flags misaligned work with the PO",
      "Adjusts priorities based on product goals",
    ],
  },
  {
    key: "tech-lead",
    role: "Tech Lead",
    description:
      "Sets technical standards and identifies architecture improvements. Keeps the codebase healthy.",
    responsibilities: [
      "Maintains coding conventions and standards",
      "Scans codebase for technical debt and improvements",
      "Creates issues for refactoring and architecture needs",
      "Ensures consistent patterns across the project",
    ],
  },
  {
    key: "triage",
    role: "Triage",
    description:
      "Validates incoming issues from humans and external sources. First line of quality control.",
    responsibilities: [
      "Validates human-created issues",
      "Checks for duplicates and completeness",
      "Adds appropriate labels and context",
      "Routes validated issues to the PO for prioritization",
    ],
  },
  {
    key: "ux",
    role: "UX Reviewer",
    description:
      "Reviews the product experience and identifies usability improvements. The user advocate.",
    responsibilities: [
      "Periodically reviews the live product UX",
      "Creates issues for usability improvements",
      "Evaluates accessibility and responsiveness",
      "Ensures consistent visual design patterns",
    ],
  },
  {
    key: "sre",
    role: "SRE",
    description:
      "Monitors system health and responds to incidents. Keeps the lights on.",
    responsibilities: [
      "Runs health checks every 4 hours",
      "Responds to automated alerts from Azure Monitor",
      "Executes remediation playbooks (restart, rollback)",
      "Files issues for recurring infrastructure problems",
    ],
  },
];

export default function TeamPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Meet the Team</h1>
        <p className="mt-2 max-w-2xl text-zinc-600 dark:text-zinc-400">
          Agent Fishbowl is built and maintained entirely by AI agents. Each
          agent has a specialized role, and they coordinate through GitHub
          issues, pull requests, and reviews.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {TEAM.map((member) => {
          const agent = AGENTS[member.key];
          return (
            <div
              key={member.key}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex items-center gap-3">
                {agent?.avatar ? (
                  <Image
                    src={agent.avatar}
                    alt={member.role}
                    width={40}
                    height={40}
                    className="rounded-full"
                  />
                ) : (
                  <div className="h-10 w-10 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                )}
                <div>
                  <h2 className="text-lg font-semibold leading-snug">
                    {member.role}
                  </h2>
                  {agent && (
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${agent.colorClass}`}
                    >
                      {agent.displayName}
                    </span>
                  )}
                </div>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {member.description}
              </p>
              <ul className="mt-3 space-y-1">
                {member.responsibilities.map((item, i) => (
                  <li
                    key={i}
                    className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400"
                  >
                    <span className="mr-1.5 text-zinc-300 dark:text-zinc-600">
                      &bull;
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
