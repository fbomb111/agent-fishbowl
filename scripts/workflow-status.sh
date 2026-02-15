#!/bin/bash
# workflow-status.sh — GitHub Actions workflow status for Agent Fishbowl agents.
# Structured view of recent workflow runs with filtering.
# Outputs JSON to stdout. Uses GH_TOKEN from environment.
set -euo pipefail

# --- Defaults ---
WORKFLOW=""
FAILURES_ONLY=false
LAST=5

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/workflow-status.sh [OPTIONS]

Get structured GitHub Actions workflow run status.

Options:
  --workflow NAME       Filter by workflow file name (e.g., "deploy.yml")
  --failures-only       Only show failed runs
  --last N              Last N runs to check (default: 5)
  --help                Show this help

Examples:
  # Check all recent workflow runs
  scripts/workflow-status.sh

  # Check deploy workflow specifically
  scripts/workflow-status.sh --workflow deploy.yml

  # Find recent failures only
  scripts/workflow-status.sh --failures-only --last 20

Output: JSON with total_runs, failure count, and run details.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --workflow) WORKFLOW="$2"; shift 2 ;;
        --failures-only) FAILURES_ONLY=true; shift ;;
        --last) LAST="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Fetch workflow runs ---
GH_ARGS=(run list --limit "$LAST" --json workflowName,status,conclusion,createdAt,headBranch,event)

if [[ -n "$WORKFLOW" ]]; then
    GH_ARGS+=(--workflow "$WORKFLOW")
fi

RAW=$(gh "${GH_ARGS[@]}" 2>/dev/null || echo "[]")

# --- Filter and format ---
JQ_FILTER='.'

if [[ "$FAILURES_ONLY" == "true" ]]; then
    JQ_FILTER+=' | [.[] | select(.conclusion == "failure")]'
fi

FILTERED=$(echo "$RAW" | jq "$JQ_FILTER")

# --- Build output ---
echo "$FILTERED" | jq '{
    total_runs: length,
    failures: ([.[] | select(.conclusion == "failure")] | length),
    successes: ([.[] | select(.conclusion == "success")] | length),
    in_progress: ([.[] | select(.status == "in_progress" or .status == "queued")] | length),
    runs: [.[] | {
        workflow: .workflowName,
        status: .status,
        conclusion: .conclusion,
        created_at: .createdAt,
        branch: .headBranch,
        event: .event
    }]
}'
