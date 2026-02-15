#!/bin/bash
# find-issues.sh — Deterministic issue query helper for Agent Fishbowl agents.
# Wraps `gh issue list` with structured filtering, label exclusion, and priority sorting.
# Outputs JSON to stdout. Uses GH_TOKEN from environment.
set -euo pipefail

# --- Defaults ---
STATE="open"
SORT="created"
LIMIT=20
UNASSIGNED=false
LABELS=()
NO_LABELS=()

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/find-issues.sh [OPTIONS]

Find GitHub issues with filtering and sorting.

Options:
  --unassigned          Only issues with no assignee
  --label LABEL         Filter by label (repeatable)
  --no-label LABEL      Exclude issues with label (repeatable)
  --state STATE         open (default), closed, all
  --sort priority       Sort by priority/high > medium > low, bugs > features, oldest first
  --sort created        Sort by creation date (default)
  --limit N             Max results (default: 20)
  --help                Show this help

Examples:
  # Find highest-priority unassigned issue (engineer use case)
  scripts/find-issues.sh --unassigned --sort priority

  # Find intake issues from scanning agents (PO use case)
  scripts/find-issues.sh --label "source/tech-lead" --label "source/ux-review"

  # Find issues without priority labels (PO triage use case)
  scripts/find-issues.sh --no-label "priority/high" --no-label "priority/medium" --no-label "priority/low"

  # Find closed issues (duplicate checking)
  scripts/find-issues.sh --state closed --limit 30

Output: JSON array of issue objects with number, title, labels, assignees, created_at.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --unassigned) UNASSIGNED=true; shift ;;
        --label) LABELS+=("$2"); shift 2 ;;
        --no-label) NO_LABELS+=("$2"); shift 2 ;;
        --state) STATE="$2"; shift 2 ;;
        --sort) SORT="$2"; shift 2 ;;
        --limit) LIMIT="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Build gh command ---
GH_ARGS=(issue list --state "$STATE" --json "number,title,labels,assignees,createdAt" --limit 100)

# Add label filters (gh supports multiple --label flags)
for label in "${LABELS[@]}"; do
    GH_ARGS+=(--label "$label")
done

# --- Fetch issues ---
RAW=$(gh "${GH_ARGS[@]}" 2>/dev/null || echo "[]")

# --- Apply jq filters and sorting ---
# Build the jq filter pipeline
JQ_FILTER='.'

# Flatten label names for easier filtering
JQ_FILTER+=' | [.[] | . + {label_names: [.labels[].name]}]'

# Filter: unassigned only
if [[ "$UNASSIGNED" == "true" ]]; then
    JQ_FILTER+=' | [.[] | select(.assignees | length == 0)]'
fi

# Filter: exclude issues with specific labels
for no_label in "${NO_LABELS[@]}"; do
    JQ_FILTER+=" | [.[] | select(.label_names | index(\"$no_label\") | not)]"
done

# Sort
if [[ "$SORT" == "priority" ]]; then
    # Priority sort: high > medium > low > unlabeled, then bugs > features > chores, then oldest first
    JQ_FILTER+=' | [.[] | . + {
        priority_rank: (
            if (.label_names | index("priority/high")) then 0
            elif (.label_names | index("priority/medium")) then 1
            elif (.label_names | index("priority/low")) then 2
            else 3 end
        ),
        type_rank: (
            if (.label_names | index("type/bug")) then 0
            elif (.label_names | index("type/feature")) then 1
            elif (.label_names | index("type/chore")) then 2
            elif (.label_names | index("type/refactor")) then 3
            else 4 end
        )
    }] | sort_by(.priority_rank, .type_rank, .createdAt)'
else
    # Default: sort by creation date (oldest first)
    JQ_FILTER+=' | sort_by(.createdAt)'
fi

# Limit results
JQ_FILTER+=" | .[:$LIMIT]"

# Clean output: remove internal fields, format labels as string array
JQ_FILTER+=' | [.[] | {
    number: .number,
    title: .title,
    labels: .label_names,
    assignees: [.assignees[].login],
    created_at: .createdAt
}]'

echo "$RAW" | jq "$JQ_FILTER"
