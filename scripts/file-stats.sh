#!/bin/bash
# file-stats.sh — Codebase metrics for Agent Fishbowl Tech Lead agent.
# Reports file counts, files over size limits, and type breakdown.
# Outputs JSON to stdout. No external deps — pure bash + standard tools.
set -euo pipefail

# --- Defaults ---
OVER_LIMIT=500
TYPES=()
SUMMARY=false

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/file-stats.sh [OPTIONS]

Report codebase file statistics: counts, sizes, and files over limits.

Options:
  --over-limit N        Files over N lines (default: 500)
  --type TYPE           Filter by file type: py, ts, tsx, js, jsx (repeatable)
  --summary             Just counts, no per-file list
  --help                Show this help

Examples:
  # Find all files over 500 lines (tech lead default check)
  scripts/file-stats.sh

  # Check Python files over 300 lines
  scripts/file-stats.sh --type py --over-limit 300

  # Quick summary of file counts by type
  scripts/file-stats.sh --summary

Output: JSON with total_files, over_limit list, and by_type breakdown.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --over-limit) OVER_LIMIT="$2"; shift 2 ;;
        --type) TYPES+=("$2"); shift 2 ;;
        --summary) SUMMARY=true; shift ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Build find patterns ---
# Only scan source directories (not node_modules, .venv, etc.)
SEARCH_DIRS=("$PROJECT_ROOT/api" "$PROJECT_ROOT/frontend/src" "$PROJECT_ROOT/scripts")
EXCLUDE_DIRS=("node_modules" ".venv" "__pycache__" ".next" "dist" "build" ".git")

# Build find command
FIND_ARGS=()
for dir in "${SEARCH_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        FIND_ARGS+=("$dir")
    fi
done

if [[ ${#FIND_ARGS[@]} -eq 0 ]]; then
    echo '{"total_files": 0, "over_limit": [], "by_type": {}}'
    exit 0
fi

# Build exclusion patterns
PRUNE_ARGS=""
for excl in "${EXCLUDE_DIRS[@]}"; do
    if [[ -n "$PRUNE_ARGS" ]]; then
        PRUNE_ARGS="$PRUNE_ARGS -o"
    fi
    PRUNE_ARGS="$PRUNE_ARGS -name $excl"
done

# Build type filter
TYPE_FILTER=""
if [[ ${#TYPES[@]} -gt 0 ]]; then
    for t in "${TYPES[@]}"; do
        if [[ -n "$TYPE_FILTER" ]]; then
            TYPE_FILTER="$TYPE_FILTER -o"
        fi
        TYPE_FILTER="$TYPE_FILTER -name '*.${t}'"
    done
else
    TYPE_FILTER="-name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx'"
fi

# --- Find files and count lines ---
# Get all matching files with line counts
FILES_WITH_LINES=$(eval "find ${FIND_ARGS[*]} \\( $PRUNE_ARGS \\) -prune -o -type f \\( $TYPE_FILTER \\) -print" 2>/dev/null | while read -r f; do
    lines=$(wc -l < "$f" 2>/dev/null || echo "0")
    # Make path relative to project root
    relpath="${f#$PROJECT_ROOT/}"
    ext="${f##*.}"
    echo "$lines $ext $relpath"
done)

# --- Build JSON output ---
TOTAL_FILES=$(echo "$FILES_WITH_LINES" | grep -c . 2>/dev/null || echo "0")

# Files over limit
OVER_LIMIT_JSON="[]"
if [[ "$SUMMARY" != "true" ]]; then
    OVER_LIMIT_JSON=$(echo "$FILES_WITH_LINES" | awk -v limit="$OVER_LIMIT" '$1 > limit {printf "{\"path\":\"%s\",\"lines\":%d}\n", $3, $1}' | jq -s '.' 2>/dev/null || echo "[]")
fi
OVER_LIMIT_COUNT=$(echo "$FILES_WITH_LINES" | awk -v limit="$OVER_LIMIT" '$1 > limit' | wc -l)

# By type breakdown
BY_TYPE=$(echo "$FILES_WITH_LINES" | awk '{print $2}' | sort | uniq -c | awk '{printf "{\"key\":\"%s\",\"value\":%d}\n", $2, $1}' | jq -s 'from_entries' 2>/dev/null || echo "{}")

# --- Output ---
jq -n \
    --argjson total "$TOTAL_FILES" \
    --argjson over_limit_count "$OVER_LIMIT_COUNT" \
    --argjson over_limit "$OVER_LIMIT_JSON" \
    --argjson by_type "$BY_TYPE" \
    --argjson limit "$OVER_LIMIT" \
    '{
        total_files: $total,
        line_limit: $limit,
        over_limit_count: $over_limit_count,
        over_limit: $over_limit,
        by_type: $by_type
    }'
