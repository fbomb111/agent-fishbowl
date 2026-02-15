#!/bin/bash
# check-duplicates.sh — Issue duplicate detection for Agent Fishbowl agents.
# Uses word-overlap Jaccard similarity on normalized issue titles.
# No external deps — pure bash + jq. Outputs JSON to stdout.
set -euo pipefail

# --- Defaults ---
THRESHOLD=60
STATE="open"

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/check-duplicates.sh "TITLE TEXT" [OPTIONS]

Find existing issues similar to the given title using word-overlap matching.

Arguments:
  TITLE                 The title text to check for duplicates (required)

Options:
  --threshold N         Similarity threshold 0-100 (default: 60)
  --state STATE         open (default), all (includes recently closed)
  --help                Show this help

Examples:
  # Check if "Add category filter" has duplicates
  scripts/check-duplicates.sh "Add category filter"

  # Check against all issues (including closed), lower threshold
  scripts/check-duplicates.sh "Dark mode support" --state all --threshold 40

Output: JSON array of similar issues sorted by similarity score (highest first).
        Empty array [] if no duplicates found above threshold.
EOF
    exit 0
}

# --- Parse args ---
TITLE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        --state) STATE="$2"; shift 2 ;;
        --help|-h) usage ;;
        -*)  echo "Unknown option: $1" >&2; exit 1 ;;
        *)
            if [[ -z "$TITLE" ]]; then
                TITLE="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$TITLE" ]]; then
    echo "Error: title argument is required" >&2
    echo "Usage: scripts/check-duplicates.sh \"TITLE TEXT\" [OPTIONS]" >&2
    exit 1
fi

# --- Fetch existing issues ---
if [[ "$STATE" == "all" ]]; then
    OPEN=$(gh issue list --state open --json number,title --limit 50 2>/dev/null || echo "[]")
    CLOSED=$(gh issue list --state closed --json number,title --limit 30 2>/dev/null || echo "[]")
    # Merge and tag with state
    ISSUES=$(jq -n --argjson open "$OPEN" --argjson closed "$CLOSED" \
        '[$open[] | . + {state: "open"}] + [$closed[] | . + {state: "closed"}]')
else
    RAW=$(gh issue list --state "$STATE" --json number,title --limit 50 2>/dev/null || echo "[]")
    ISSUES=$(echo "$RAW" | jq '[.[] | . + {state: "'"$STATE"'"}]')
fi

# --- Compute similarity using jq ---
# Jaccard similarity on normalized words (lowercase, split on non-alphanumeric)
echo "$ISSUES" | jq --arg query "$TITLE" --argjson threshold "$THRESHOLD" '
# Normalize: lowercase, split on non-alpha, remove short words (stop words)
def normalize:
    ascii_downcase
    | gsub("[^a-z0-9 ]"; " ")
    | split(" ")
    | map(select(length > 2))
    | unique;

($query | normalize) as $query_words |
[.[] | . as $issue |
    ($issue.title | normalize) as $title_words |
    # Jaccard: intersection / union
    ([$query_words[], $title_words[]] | unique | length) as $union |
    ([$query_words[] | select(. as $w | $title_words | index($w))] | length) as $intersection |
    (if $union > 0 then ($intersection * 100 / $union) else 0 end) as $similarity |
    select($similarity >= $threshold) |
    {
        number: $issue.number,
        title: $issue.title,
        state: $issue.state,
        similarity: ($similarity | floor)
    }
] | sort_by(-.similarity)'
