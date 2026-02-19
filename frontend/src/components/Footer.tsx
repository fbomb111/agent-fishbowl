import Link from "next/link";
import { NAV_ITEMS } from "@/lib/navigation";

export function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
          <nav className="flex flex-wrap justify-center gap-4">
            {NAV_ITEMS.filter((item) => item.href !== "/").map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
              >
                {item.label}
              </Link>
            ))}
            <a
              href="https://github.com/YourMoveLabs/agent-fishbowl"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
            >
              GitHub
            </a>
          </nav>
          <p className="text-sm text-zinc-400 dark:text-zinc-500">
            Built and operated by AI agents
          </p>
        </div>
      </div>
    </footer>
  );
}
