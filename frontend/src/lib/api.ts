/**
 * API client for communicating with the FastAPI backend.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8500";
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
  avatar_url?: string;
  description: string;
  timestamp: string;
  url?: string;
  subject_type?: "issue" | "pr";
  subject_number?: number;
  subject_title?: string;
  comment_body?: string;
  comment_url?: string;
  deploy_status?: string;
}

export interface ActivityThread {
  type: "thread";
  subject_type: "issue" | "pr";
  subject_number: number;
  subject_title: string;
  events: ActivityEvent[];
  latest_timestamp: string;
}

export interface StandaloneEvent {
  type: "standalone";
  event: ActivityEvent;
}

export type ThreadedItem = ActivityThread | StandaloneEvent;

export async function fetchArticles(
  category?: string,
  limit?: number,
  offset?: number,
  search?: string
): Promise<{
  articles: ArticleSummary[];
  total: number;
}> {
  const url = new URL(`${API_BASE}/articles`);
  if (category) {
    url.searchParams.set("category", category);
  }
  if (limit !== undefined) {
    url.searchParams.set("limit", String(limit));
  }
  if (offset !== undefined) {
    url.searchParams.set("offset", String(offset));
  }
  if (search) {
    url.searchParams.set("search", search);
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

export async function fetchThreadedActivity(
  perPage = 50
): Promise<{ threads: ThreadedItem[]; mode: string }> {
  const res = await fetch(
    `${API_BASE}/activity?mode=threaded&per_page=${perPage}`
  );
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

// Agent status types

export interface AgentUsage {
  cost_usd: number | null;
  num_turns: number | null;
  duration_s: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_creation_input_tokens: number | null;
  cache_read_input_tokens: number | null;
}

export interface AgentStatus {
  role: string;
  status: "active" | "idle" | "failed";
  has_run: boolean;
  started_at?: string;
  trigger?: string;
  last_completed_at?: string;
  last_conclusion?: string;
  usage?: AgentUsage;
  last_summary?: string;
}

export async function fetchAgentStatus(): Promise<{
  agents: AgentStatus[];
}> {
  const res = await fetch(`${API_BASE}/activity/agent-status`);
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

// Blog types

export interface BlogPost {
  id: string;
  title: string;
  slug: string;
  description: string;
  published_at: string;
  focus_keyphrase: string;
  author: string;
  category: string;
  preview_url: string;
  image_url?: string;
  read_time_minutes?: number;
}

export async function fetchBlogPosts(): Promise<{
  posts: BlogPost[];
  total: number;
}> {
  const res = await fetch(`${API_BASE}/blog`);
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

export async function fetchBlogPostBySlug(slug: string): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/blog/by-slug/${encodeURIComponent(slug)}`);
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

// Team stats types

export interface AgentActivity {
  role: string;
  issues_closed: number;
  prs_merged: number;
}

export interface TeamStatsResponse {
  issues_closed: number;
  prs_merged: number;
  avg_pr_cycle_hours: number | null;
  agents: AgentActivity[];
  period_start: string;
  period_end: string;
}

export async function fetchTeamStats(): Promise<TeamStatsResponse> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw apiError(res.status);
  return res.json();
}

// Board health types

export interface BoardHealthResponse {
  total_items: number;
  by_status: Record<string, number>;
  draft_items: number;
  untracked_issues: number;
}

export async function fetchBoardHealth(): Promise<BoardHealthResponse> {
  const res = await fetch(`${API_BASE}/board-health`);
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
