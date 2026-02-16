/**
 * API client for communicating with the FastAPI backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8500";
const API_BASE = `${API_URL}/api/fishbowl`;

function apiError(status: number): Error {
  switch (status) {
    case 429:
      return new Error("Too many requests. Please try again later.");
    case 500:
      return new Error("Server error. Please try again later.");
    case 502:
    case 503:
      return new Error("Service temporarily unavailable. Please try again.");
    case 404:
      return new Error("The requested resource was not found.");
    default:
      return new Error("Something went wrong. Please try again.");
  }
}

export interface Insight {
  text: string;
  category: string;
}

export interface ArticleSummary {
  id: string;
  title: string;
  source: string;
  source_url: string;
  original_url: string;
  published_at: string;
  description: string;
  categories: string[];
  image_url?: string;
  read_time_minutes?: number;
  insights?: Insight[];
  ai_summary?: string;
  has_full_text?: boolean;
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
  const url = new URL(`${API_BASE}/articles`);
  if (category) {
    url.searchParams.set("category", category);
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

export async function fetchActivity(
  page = 1,
  perPage = 20
): Promise<{ events: ActivityEvent[]; page: number; per_page: number }> {
  const res = await fetch(
    `${API_BASE}/activity?page=${page}&per_page=${perPage}`
  );
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

// Goals dashboard types

export interface Goal {
  number: number;
  title: string;
  summary: string;
  examples: string[];
}

export interface RoadmapItem {
  title: string;
  priority: string;
  goal: string;
  phase: string;
}

export interface RoadmapSnapshot {
  active: RoadmapItem[];
  counts: {
    proposed: number;
    active: number;
    done: number;
    deferred: number;
  };
}

export interface TrendWindow {
  "24h": number;
  "7d": number;
  "30d": number;
}

export interface AgentStats {
  issues_opened: number;
  issues_closed: number;
  prs_opened: number;
  prs_merged: number;
  reviews: number;
  commits: number;
}

export interface Metrics {
  open_issues: number;
  open_prs: number;
  issues_closed: TrendWindow;
  prs_merged: TrendWindow;
  commits: TrendWindow;
  by_agent: Record<string, AgentStats>;
}

export interface GoalsResponse {
  mission: string;
  goals: Goal[];
  constraints: string[];
  roadmap: RoadmapSnapshot;
  metrics: Metrics;
  fetched_at: string;
}

export async function fetchGoals(): Promise<GoalsResponse> {
  const res = await fetch(`${API_BASE}/goals`);
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

// Feedback types

export interface FeedbackSubmission {
  title: string;
  description: string;
  email?: string;
  website?: string;
}

export interface FeedbackResponse {
  issue_url: string;
  issue_number: number;
  message: string;
}

export async function submitFeedback(
  submission: FeedbackSubmission
): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
  if (!res.ok) throw apiError(res.status);
  return res.json();
}
