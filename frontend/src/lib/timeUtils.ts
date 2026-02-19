/** Format an ISO timestamp as a human-friendly relative time string.
 *  When `verbose` is true, uses long-form units ("5 minutes ago" instead of "5m ago"). */
export function timeAgo(iso: string, verbose = false): string {
  const seconds = Math.floor(
    (Date.now() - new Date(iso).getTime()) / 1000
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    if (verbose) return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    if (verbose) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  if (verbose) return days === 1 ? "1 day ago" : `${days} days ago`;
  return `${days}d ago`;
}

/** Check if an ISO timestamp is within the last N hours (default 6). */
export function isFresh(iso: string, hoursThreshold = 6): boolean {
  const ms = Date.now() - new Date(iso).getTime();
  return ms >= 0 && ms < hoursThreshold * 60 * 60 * 1000;
}
