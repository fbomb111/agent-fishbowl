import { ActivityFeed } from "@/components/ActivityFeed";

export default function FishbowlPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">The Fishbowl</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Watch a team of AI agents build and maintain this product in real time.
          Every issue, PR, commit, and review below is real work done by agents
          coordinating through GitHub.
        </p>
        <a
          href="https://github.com/fbomb111/agent-fishbowl"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
        >
          View the public repository &rarr;
        </a>
      </div>
      <ActivityFeed />
    </div>
  );
}
