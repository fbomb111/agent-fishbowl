"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Feed" },
  { href: "/activity", label: "Fishbowl" },
  { href: "/goals", label: "Goals" },
  { href: "/feedback", label: "Feedback" },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Agent Fishbowl
        </Link>
        <nav className="flex gap-6">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`text-sm font-medium transition-colors ${
                pathname === item.href
                  ? "text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
              }`}
            >
              {item.label}
            </Link>
          ))}
          <a
            href="https://github.com/YourMoveLabs/agent-fishbowl"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
