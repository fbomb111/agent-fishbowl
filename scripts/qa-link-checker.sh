#!/bin/bash
# qa-link-checker.sh — Validate article source URLs resolve (no broken links).
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
# Requires: curl, jq
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"

# --- Defaults ---
TIMEOUT=10
MAX_ARTICLES=0  # 0 = all

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-link-checker.sh [OPTIONS]

Validate article source URLs resolve (no broken links).

Options:
  --timeout SECONDS    Per-URL timeout (default: 10)
  --max-articles N     Limit articles to check (default: all)
  --base-url URL       Override API base URL
  --help               Show this help

Examples:
  scripts/qa-link-checker.sh
  scripts/qa-link-checker.sh --max-articles 20
  scripts/qa-link-checker.sh --timeout 5

Output: JSON with pass/fail per URL and summary counts.
Requires: curl, jq
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --max-articles) MAX_ARTICLES="$2"; shift 2 ;;
        --base-url) API_BASE="$2"; API_PREFIX="${API_BASE}/api/fishbowl"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Fetch articles ---
ARTICLES=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/articles" 2>/dev/null || echo '[]')
ARTICLE_COUNT=$(echo "$ARTICLES" | jq 'length')

if [[ "$ARTICLE_COUNT" -eq 0 ]]; then
    jq -n \
        --arg timestamp "$CHECKED_AT" \
        --arg base_url "$API_BASE" \
        '{
            timestamp: $timestamp,
            base_url: $base_url,
            articles_checked: 0,
            checks: [],
            passed: 0,
            failed: 0,
            total: 0
        }'
    exit 0
fi

# Limit articles if requested
if [[ "$MAX_ARTICLES" -gt 0 && "$ARTICLE_COUNT" -gt "$MAX_ARTICLES" ]]; then
    ARTICLES=$(echo "$ARTICLES" | jq --argjson max "$MAX_ARTICLES" '.[:$max]')
    ARTICLE_COUNT="$MAX_ARTICLES"
fi

# --- Check each URL ---
CHECKS="[]"
PASSED=0
FAILED=0

while IFS= read -r article; do
    ARTICLE_ID=$(echo "$article" | jq -r '.id // "unknown"')
    URL=$(echo "$article" | jq -r '.source_url // empty')

    if [[ -z "$URL" || "$URL" == "null" ]]; then
        # Article has no source URL — skip
        continue
    fi

    # Perform HEAD request to check if URL resolves
    HTTP_CODE=$(curl -sf -L -I --max-time "$TIMEOUT" --connect-timeout "$TIMEOUT" \
        -w "%{http_code}" -o /dev/null "$URL" 2>/dev/null || echo "000")

    # Check if status is 2xx or 3xx (success)
    PASSED_CHECK=false
    if [[ "$HTTP_CODE" =~ ^[23][0-9]{2}$ ]]; then
        PASSED_CHECK=true
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi

    # Add to checks array
    CHECK_ENTRY=$(jq -n \
        --arg id "$ARTICLE_ID" \
        --arg url "$URL" \
        --arg code "$HTTP_CODE" \
        --argjson passed "$PASSED_CHECK" \
        '{
            article_id: $id,
            url: $url,
            status_code: $code,
            passed: $passed
        }')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$CHECK_ENTRY" '. + [$e]')

done < <(echo "$ARTICLES" | jq -c '.[]')

TOTAL=$((PASSED + FAILED))

# --- Output ---
jq -n \
    --arg timestamp "$CHECKED_AT" \
    --arg base_url "$API_BASE" \
    --argjson articles_checked "$ARTICLE_COUNT" \
    --argjson checks "$CHECKS" \
    --argjson passed "$PASSED" \
    --argjson failed "$FAILED" \
    --argjson total "$TOTAL" \
    '{
        timestamp: $timestamp,
        base_url: $base_url,
        articles_checked: $articles_checked,
        checks: $checks,
        passed: $passed,
        failed: $failed,
        total: $total
    }'

# Exit with appropriate code
if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
