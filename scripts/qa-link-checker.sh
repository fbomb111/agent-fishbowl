#!/bin/bash
# qa-link-checker.sh — Validate article source URLs resolve.
# Fetches all articles from the API and performs HEAD requests to verify each link is accessible.
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"

# --- Defaults ---
TIMEOUT=10
MAX_ARTICLES=""

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-link-checker.sh [OPTIONS]

Validate article source URLs resolve (2xx/3xx responses).

Options:
  --timeout SECONDS    Per-URL timeout (default: 10)
  --max-articles N     Limit articles to check (default: all)
  --base-url URL       Override API base URL
  --help               Show this help

Examples:
  scripts/qa-link-checker.sh
  scripts/qa-link-checker.sh --max-articles 20
  scripts/qa-link-checker.sh --timeout 5

Output: JSON with per-article URL checks, summary counts.
Exit 0 if all pass, 1 if any fail.
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
ARTICLES=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/articles" 2>/dev/null || echo '{"articles":[]}')

# Apply limit if specified
if [[ -n "$MAX_ARTICLES" ]]; then
    ARTICLES=$(echo "$ARTICLES" | jq --argjson limit "$MAX_ARTICLES" '{articles: .articles[0:$limit]}')
fi

ARTICLE_COUNT=$(echo "$ARTICLES" | jq '.articles | length')

# --- Results accumulator ---
CHECKS="[]"

# --- Check each article URL ---
for i in $(seq 0 $((ARTICLE_COUNT - 1))); do
    ARTICLE_ID=$(echo "$ARTICLES" | jq -r ".articles[$i].id // \"unknown\"")
    ARTICLE_TITLE=$(echo "$ARTICLES" | jq -r ".articles[$i].title // \"untitled\"")
    SOURCE_URL=$(echo "$ARTICLES" | jq -r ".articles[$i].source_url // .articles[$i].url // \"\"")

    if [[ -z "$SOURCE_URL" || "$SOURCE_URL" == "null" ]]; then
        # No URL to check — record as a failure
        entry=$(jq -n \
            --arg article_id "$ARTICLE_ID" \
            --arg title "$ARTICLE_TITLE" \
            --arg url "null" \
            --argjson status_code 0 \
            --argjson passed false \
            '{article_id: $article_id, title: $title, url: $url, status_code: $status_code, passed: $passed}')
        CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
        continue
    fi

    # Perform HEAD request with timeout
    HTTP_CODE=$(curl -sf --head --max-time "$TIMEOUT" --connect-timeout "$TIMEOUT" \
        -w '%{http_code}' -o /dev/null "$SOURCE_URL" 2>/dev/null || echo "0")

    # Accept 2xx or 3xx as success
    PASSED=false
    if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 400 ]]; then
        PASSED=true
    fi

    entry=$(jq -n \
        --arg article_id "$ARTICLE_ID" \
        --arg title "$ARTICLE_TITLE" \
        --arg url "$SOURCE_URL" \
        --argjson status_code "$HTTP_CODE" \
        --argjson passed "$PASSED" \
        '{article_id: $article_id, title: $title, url: $url, status_code: $status_code, passed: $passed}')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
done

# --- Summary ---
PASSED=$(echo "$CHECKS" | jq '[.[] | select(.passed == true)] | length')
FAILED=$(echo "$CHECKS" | jq '[.[] | select(.passed == false)] | length')
TOTAL=$(echo "$CHECKS" | jq 'length')

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
