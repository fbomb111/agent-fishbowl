/**
 * Format a token count into a compact human-readable string.
 *
 * Examples: 842 → "842", 1500 → "1.5K", 42300 → "42.3K", 1500000 → "1.5M"
 */
export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
