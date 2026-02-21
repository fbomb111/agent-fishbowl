#!/bin/bash
# qa-content-freshness.sh — Check content freshness across articles, blog posts, and ingestion pipeline.
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
# Requires: curl, jq, gh CLI
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"
REPO="${FISHBOWL_REPO:-YourMoveLabs/agent-fishbowl}"

# --- Defaults ---
ARTICLE_MAX_AGE=48
BLOG_MAX_AGE=48
INGEST_MAX_AGE=72

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-content-freshness.sh [OPTIONS]

Check content freshness across articles, blog posts, and ingestion pipeline.

Options:
  --article-max-age HOURS  Max age for articles (default: 48)
  --blog-max-age HOURS     Max age for blog posts (default: 48)
  --ingest-max-age HOURS   Max age for ingestion runs (default: 72)
  --base-url URL           Override API base URL
  --repo OWNER/REPO        Override GitHub repo (default: YourMoveLabs/agent-fishbowl)
  --help                   Show this help

Examples:
  scripts/qa-content-freshness.sh
  scripts/qa-content-freshness.sh --article-max-age 72
  scripts/qa-content-freshness.sh --base-url https://agentfishbowl.com

Output: JSON with freshness data and pass/fail per content type.
Requires: curl, jq, gh CLI (authenticated)
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --article-max-age) ARTICLE_MAX_AGE="$2"; shift 2 ;;
        --blog-max-age) BLOG_MAX_AGE="$2"; shift 2 ;;
        --ingest-max-age) INGEST_MAX_AGE="$2"; shift 2 ;;
        --base-url) API_BASE="$2"; API_PREFIX="${API_BASE}/api/fishbowl"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NOW_EPOCH=$(date +%s)

# --- Results accumulator ---
CHECKS="[]"

add_check() {
    local content_type="$1" passed="$2" latest_date="$3" age_hours="$4" threshold_hours="$5" total_count="${6:-0}"
    local entry
    entry=$(jq -n \
        --arg type "$content_type" \
        --argjson passed "$passed" \
        --arg latest "$latest_date" \
        --argjson age "$age_hours" \
        --argjson threshold "$threshold_hours" \
        --argjson count "$total_count" \
        '{
            content_type: $type,
            passed: $passed,
            latest_date: $latest,
            age_hours: $age,
            threshold_hours: $threshold,
            total_count: $count
        }')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
}

# --- Check: articles ---
ARTICLES=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/articles" 2>/dev/null || echo '[]')
ARTICLE_COUNT=$(echo "$ARTICLES" | jq 'length')

if [[ "$ARTICLE_COUNT" -eq 0 ]]; then
    add_check "articles" false "null" 0 "$ARTICLE_MAX_AGE" 0
else
    # Find the newest article
    LATEST_ARTICLE=$(echo "$ARTICLES" | jq -r '
        [.[] | select(.published_date != null) | .published_date] | sort | last // null')

    if [[ "$LATEST_ARTICLE" == "null" || -z "$LATEST_ARTICLE" ]]; then
        add_check "articles" false "null" 0 "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT"
    else
        # Calculate age in hours
        LATEST_EPOCH=$(date -d "$LATEST_ARTICLE" +%s 2>/dev/null || echo "0")
        AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))

        if [[ "$AGE_HOURS" -le "$ARTICLE_MAX_AGE" ]]; then
            add_check "articles" true "$LATEST_ARTICLE" "$AGE_HOURS" "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT"
        else
            add_check "articles" false "$LATEST_ARTICLE" "$AGE_HOURS" "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT"
        fi
    fi
fi

# --- Check: blog ---
BLOG=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/blog" 2>/dev/null || echo '{"posts":[]}')
BLOG_COUNT=$(echo "$BLOG" | jq '.posts | length')

if [[ "$BLOG_COUNT" -eq 0 ]]; then
    add_check "blog" false "null" 0 "$BLOG_MAX_AGE" 0
else
    # Find the newest blog post
    LATEST_BLOG=$(echo "$BLOG" | jq -r '
        [.posts[] | select(.published_at != null) | .published_at] | sort | last // null')

    if [[ "$LATEST_BLOG" == "null" || -z "$LATEST_BLOG" ]]; then
        add_check "blog" false "null" 0 "$BLOG_MAX_AGE" "$BLOG_COUNT"
    else
        # Calculate age in hours
        LATEST_EPOCH=$(date -d "$LATEST_BLOG" +%s 2>/dev/null || echo "0")
        AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))

        if [[ "$AGE_HOURS" -le "$BLOG_MAX_AGE" ]]; then
            add_check "blog" true "$LATEST_BLOG" "$AGE_HOURS" "$BLOG_MAX_AGE" "$BLOG_COUNT"
        else
            add_check "blog" false "$LATEST_BLOG" "$AGE_HOURS" "$BLOG_MAX_AGE" "$BLOG_COUNT"
        fi
    fi
fi

# --- Check: ingestion pipeline ---
INGEST_RUNS=$(gh run list --repo "$REPO" --workflow=ingest.yml --limit 1 --json createdAt,conclusion 2>/dev/null || echo "[]")
INGEST_COUNT=$(echo "$INGEST_RUNS" | jq 'length')

if [[ "$INGEST_COUNT" -eq 0 ]]; then
    add_check "ingestion_pipeline" false "null" 0 "$INGEST_MAX_AGE" 0
else
    LATEST_INGEST=$(echo "$INGEST_RUNS" | jq -r '.[0].createdAt // null')
    INGEST_CONCLUSION=$(echo "$INGEST_RUNS" | jq -r '.[0].conclusion // "unknown"')

    if [[ "$LATEST_INGEST" == "null" || -z "$LATEST_INGEST" ]]; then
        add_check "ingestion_pipeline" false "null" 0 "$INGEST_MAX_AGE" 0
    else
        # Calculate age in hours
        LATEST_EPOCH=$(date -d "$LATEST_INGEST" +%s 2>/dev/null || echo "0")
        AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))

        # Pass if within threshold AND conclusion is success
        if [[ "$AGE_HOURS" -le "$INGEST_MAX_AGE" && "$INGEST_CONCLUSION" == "success" ]]; then
            add_check "ingestion_pipeline" true "$LATEST_INGEST" "$AGE_HOURS" "$INGEST_MAX_AGE" 1
        else
            add_check "ingestion_pipeline" false "$LATEST_INGEST" "$AGE_HOURS" "$INGEST_MAX_AGE" 1
        fi
    fi
fi

# --- Summary ---
PASSED=$(echo "$CHECKS" | jq '[.[] | select(.passed == true)] | length')
FAILED=$(echo "$CHECKS" | jq '[.[] | select(.passed == false)] | length')
TOTAL=$(echo "$CHECKS" | jq 'length')

jq -n \
    --arg timestamp "$CHECKED_AT" \
    --arg base_url "$API_BASE" \
    --arg repo "$REPO" \
    --argjson checks "$CHECKS" \
    --argjson passed "$PASSED" \
    --argjson failed "$FAILED" \
    --argjson total "$TOTAL" \
    '{
        timestamp: $timestamp,
        base_url: $base_url,
        repo: $repo,
        checks: $checks,
        passed: $passed,
        failed: $failed,
        total: $total
    }'

# Exit with appropriate code
if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
