"use client";

interface CategoryFilterProps {
  categories: string[];
  selected: string | null;
  onSelect: (category: string | null) => void;
}

export function CategoryFilter({
  categories,
  selected,
  onSelect,
}: CategoryFilterProps) {
  if (categories.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2.5 sm:gap-2">
      <button
        onClick={() => onSelect(null)}
        aria-pressed={selected === null}
        className={`min-h-[44px] rounded-full px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 sm:min-h-0 sm:px-3 sm:py-1.5 dark:focus:ring-zinc-400 dark:focus:ring-offset-zinc-900 ${
          selected === null
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
            : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
        }`}
      >
        All
      </button>
      {categories.map((category) => (
        <button
          key={category}
          onClick={() => onSelect(category)}
          aria-pressed={selected === category}
          className={`min-h-[44px] rounded-full px-4 py-2 text-sm font-medium capitalize transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 sm:min-h-0 sm:px-3 sm:py-1.5 dark:focus:ring-zinc-400 dark:focus:ring-offset-zinc-900 ${
            selected === category
              ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
              : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
          }`}
        >
          {category}
        </button>
      ))}
    </div>
  );
}
