#!/bin/bash
# find-prs.sh — Deterministic PR query helper for Agent Fishbowl agents.
# Wraps `gh pr list` with structured filtering, computed reviewRound and linkedIssue fields.
# Outputs JSON to stdout. Uses GH_TOKEN from environment.
set -euo pipefail

# --- Defaults ---
STATE="open"
LIMIT=10
REVIEWABLE=false
NEEDS_FIX=false
AUTHOR=""

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/find-prs.sh [OPTIONS]

Find GitHub pull requests with filtering and computed metadata.

Options:
  --reviewable          Not draft, not approved, not authored by current user
  --needs-fix           Authored by current user with CHANGES_REQUESTED
  --state STATE         open (default), merged, closed, all
  --author AUTHOR       Filter by author login
  --limit N             Max results (default: 10)
  --help                Show this help

Computed fields in output:
  reviewRound   Number of CHANGES_REQUESTED reviews from fishbowl-reviewer[bot]
  linkedIssue   Issue number extracted from "Closes #N" in PR body (null if not found)

Examples:
  # Find PRs the engineer needs to fix (engineer Step 0)
  scripts/find-prs.sh --needs-fix

  # Find PRs ready for review (reviewer Step 1)
  scripts/find-prs.sh --reviewable

  # Find recently merged PRs (tech lead review)
  scripts/find-prs.sh --state merged --limit 10

Output: JSON array of PR objects.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --reviewable) REVIEWABLE=true; shift ;;
        --needs-fix) NEEDS_FIX=true; shift ;;
        --state) STATE="$2"; shift 2 ;;
        --author) AUTHOR="$2"; shift 2 ;;
        --limit) LIMIT="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Fetch PRs ---
GH_ARGS=(pr list --state "$STATE" --json "number,title,author,isDraft,reviewDecision,headRefName,body,reviews" --limit 100)

if [[ -n "$AUTHOR" ]]; then
    GH_ARGS+=(--author "$AUTHOR")
fi

RAW=$(gh "${GH_ARGS[@]}" 2>/dev/null || echo "[]")

# --- Compute additional fields and apply filters ---
# Extract linkedIssue from body (Closes #N, Fixes #N, Resolves #N)
# Count reviewRound from reviews array
ENRICHED=$(echo "$RAW" | jq '[.[] | {
    number: .number,
    title: .title,
    author: .author.login,
    isDraft: .isDraft,
    reviewDecision: .reviewDecision,
    headRefName: .headRefName,
    linkedIssue: (
        try (.body | capture("(?:Closes|Fixes|Resolves) #(?<num>[0-9]+)"; "i") | .num | tonumber)
        catch null
    ),
    reviewRound: (
        [.reviews[] | select(.author.login == "fishbowl-reviewer[bot]" and .state == "CHANGES_REQUESTED")]
        | length
    )
}]')

# --- Apply mode filters ---
JQ_FILTER='.'

if [[ "$NEEDS_FIX" == "true" ]]; then
    # PRs authored by current user with changes requested
    # GH_TOKEN sets the auth context — @me PRs have reviewDecision == CHANGES_REQUESTED
    JQ_FILTER+=' | [.[] | select(.reviewDecision == "CHANGES_REQUESTED")]'
fi

if [[ "$REVIEWABLE" == "true" ]]; then
    # Not draft, not approved, not authored by fishbowl-reviewer
    JQ_FILTER+=' | [.[] | select(
        .isDraft == false
        and .reviewDecision != "APPROVED"
        and (.author | test("fishbowl-reviewer") | not)
    )]'
fi

# Apply limit
JQ_FILTER+=" | .[:$LIMIT]"

echo "$ENRICHED" | jq "$JQ_FILTER"
