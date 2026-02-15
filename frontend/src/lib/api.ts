/**
 * API client for communicating with the FastAPI backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ArticleSummary {
  id: string;
  title: string;
  source: string;
  source_url: string;
  original_url: string;
  published_at: string;
  summary: string;
  categories: string[];
  image_url?: string;
  read_time_minutes?: number;
}

export interface ActivityEvent {
  id: string;
  type: string;
  actor: string;
  description: string;
  timestamp: string;
  url?: string;
}

export async function fetchArticles(category?: string): Promise<{
  articles: ArticleSummary[];
  total: number;
}> {
  const url = new URL(`${API_URL}/api/articles`);
  if (category) {
    url.searchParams.set("category", category);
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchActivity(
  page = 1,
  perPage = 20
): Promise<{ events: ActivityEvent[]; page: number; per_page: number }> {
  const res = await fetch(
    `${API_URL}/api/activity?page=${page}&per_page=${perPage}`
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
