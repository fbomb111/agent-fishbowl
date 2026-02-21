#!/bin/bash
# qa-content-freshness.sh — Check article and blog post recency against thresholds.
# Verifies content is fresh and ingestion pipeline is running regularly.
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"
REPO="${FISHBOWL_REPO:-YourMoveLabs/agent-fishbowl}"

# --- Defaults ---
ARTICLE_MAX_AGE=48
BLOG_MAX_AGE=48

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-content-freshness.sh [OPTIONS]

Check content freshness across articles, blog posts, and ingestion pipeline.

Options:
  --article-max-age HOURS  Maximum acceptable article age (default: 48)
  --blog-max-age HOURS     Maximum acceptable blog post age (default: 48)
  --base-url URL           Override API base URL
  --help                   Show this help

Examples:
  scripts/qa-content-freshness.sh
  scripts/qa-content-freshness.sh --article-max-age 72
  scripts/qa-content-freshness.sh --blog-max-age 24

Output: JSON with freshness checks for each content type, summary counts.
Exit 0 if all fresh, 1 if any stale.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --article-max-age) ARTICLE_MAX_AGE="$2"; shift 2 ;;
        --blog-max-age) BLOG_MAX_AGE="$2"; shift 2 ;;
        --base-url) API_BASE="$2"; API_PREFIX="${API_BASE}/api/fishbowl"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NOW_EPOCH=$(date +%s)

# --- Results accumulator ---
CHECKS="[]"

add_check() {
    local content_type="$1" latest_date="$2" age_hours="$3" threshold_hours="$4" total_count="$5" passed="$6"
    local entry
    entry=$(jq -n \
        --arg content_type "$content_type" \
        --arg latest_date "$latest_date" \
        --argjson age_hours "$age_hours" \
        --argjson threshold_hours "$threshold_hours" \
        --argjson total_count "$total_count" \
        --argjson passed "$passed" \
        '{
            content_type: $content_type,
            latest_date: $latest_date,
            age_hours: $age_hours,
            threshold_hours: $threshold_hours,
            total_count: $total_count,
            passed: $passed
        }')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
}

# --- Check: Articles freshness ---
ARTICLES=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/articles" 2>/dev/null || echo '{"articles":[]}')
ARTICLE_COUNT=$(echo "$ARTICLES" | jq '.articles | length')

if [[ "$ARTICLE_COUNT" -gt 0 ]]; then
    LATEST_ARTICLE=$(echo "$ARTICLES" | jq -r '[.articles[] | .published_at // .created_at // ""] | sort | reverse | .[0]')
    if [[ -n "$LATEST_ARTICLE" && "$LATEST_ARTICLE" != "null" ]]; then
        ARTICLE_EPOCH=$(date -d "$LATEST_ARTICLE" +%s 2>/dev/null || echo "0")
        ARTICLE_AGE_HOURS=$(( (NOW_EPOCH - ARTICLE_EPOCH) / 3600 ))

        if [[ "$ARTICLE_AGE_HOURS" -le "$ARTICLE_MAX_AGE" ]]; then
            add_check "articles" "$LATEST_ARTICLE" "$ARTICLE_AGE_HOURS" "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT" true
        else
            add_check "articles" "$LATEST_ARTICLE" "$ARTICLE_AGE_HOURS" "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT" false
        fi
    else
        add_check "articles" "null" "0" "$ARTICLE_MAX_AGE" "$ARTICLE_COUNT" false
    fi
else
    add_check "articles" "null" "0" "$ARTICLE_MAX_AGE" "0" false
fi

# --- Check: Blog posts freshness ---
BLOG=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/blog" 2>/dev/null || echo '{"posts":[]}')
BLOG_COUNT=$(echo "$BLOG" | jq '.posts | length')

if [[ "$BLOG_COUNT" -gt 0 ]]; then
    LATEST_BLOG=$(echo "$BLOG" | jq -r '[.posts[] | .published_at // .created_at // ""] | sort | reverse | .[0]')
    if [[ -n "$LATEST_BLOG" && "$LATEST_BLOG" != "null" ]]; then
        BLOG_EPOCH=$(date -d "$LATEST_BLOG" +%s 2>/dev/null || echo "0")
        BLOG_AGE_HOURS=$(( (NOW_EPOCH - BLOG_EPOCH) / 3600 ))

        if [[ "$BLOG_AGE_HOURS" -le "$BLOG_MAX_AGE" ]]; then
            add_check "blog" "$LATEST_BLOG" "$BLOG_AGE_HOURS" "$BLOG_MAX_AGE" "$BLOG_COUNT" true
        else
            add_check "blog" "$LATEST_BLOG" "$BLOG_AGE_HOURS" "$BLOG_MAX_AGE" "$BLOG_COUNT" false
        fi
    else
        add_check "blog" "null" "0" "$BLOG_MAX_AGE" "$BLOG_COUNT" false
    fi
else
    add_check "blog" "null" "0" "$BLOG_MAX_AGE" "0" false
fi

# --- Check: Ingestion pipeline last run ---
INGEST_RUNS=$(gh run list --repo "$REPO" --workflow="ingest.yml" --limit 1 --json status,conclusion,createdAt 2>/dev/null || echo "[]")
INGEST_COUNT=$(echo "$INGEST_RUNS" | jq 'length')

if [[ "$INGEST_COUNT" -gt 0 ]]; then
    LATEST_INGEST=$(echo "$INGEST_RUNS" | jq -r '.[0].createdAt // ""')
    INGEST_STATUS=$(echo "$INGEST_RUNS" | jq -r '.[0].status // "unknown"')
    INGEST_CONCLUSION=$(echo "$INGEST_RUNS" | jq -r '.[0].conclusion // "unknown"')

    if [[ -n "$LATEST_INGEST" ]]; then
        INGEST_EPOCH=$(date -d "$LATEST_INGEST" +%s 2>/dev/null || echo "0")
        INGEST_AGE_HOURS=$(( (NOW_EPOCH - INGEST_EPOCH) / 3600 ))

        # Pipeline should run at least daily (24 hours), allow 48h threshold for slack
        PIPELINE_THRESHOLD=48
        INGEST_HEALTHY=false

        if [[ "$INGEST_AGE_HOURS" -le "$PIPELINE_THRESHOLD" && "$INGEST_CONCLUSION" == "success" ]]; then
            INGEST_HEALTHY=true
        fi

        # Add ingestion check with extra metadata
        local entry
        entry=$(jq -n \
            --arg content_type "ingestion_pipeline" \
            --arg latest_date "$LATEST_INGEST" \
            --argjson age_hours "$INGEST_AGE_HOURS" \
            --argjson threshold_hours "$PIPELINE_THRESHOLD" \
            --arg status "$INGEST_STATUS" \
            --arg conclusion "$INGEST_CONCLUSION" \
            --argjson passed "$INGEST_HEALTHY" \
            '{
                content_type: $content_type,
                latest_date: $latest_date,
                age_hours: $age_hours,
                threshold_hours: $threshold_hours,
                status: $status,
                conclusion: $conclusion,
                passed: $passed
            }')
        CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
    else
        entry=$(jq -n \
            --arg content_type "ingestion_pipeline" \
            '{content_type: $content_type, latest_date: null, age_hours: 0, threshold_hours: 48, passed: false}')
        CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
    fi
else
    entry=$(jq -n \
        --arg content_type "ingestion_pipeline" \
        '{content_type: $content_type, latest_date: null, age_hours: 0, threshold_hours: 48, passed: false}')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
fi

# --- Summary ---
PASSED=$(echo "$CHECKS" | jq '[.[] | select(.passed == true)] | length')
FAILED=$(echo "$CHECKS" | jq '[.[] | select(.passed == false)] | length')
TOTAL=$(echo "$CHECKS" | jq 'length')

jq -n \
    --arg timestamp "$CHECKED_AT" \
    --arg base_url "$API_BASE" \
    --argjson checks "$CHECKS" \
    --argjson passed "$PASSED" \
    --argjson failed "$FAILED" \
    --argjson total "$TOTAL" \
    '{
        timestamp: $timestamp,
        base_url: $base_url,
        checks: $checks,
        passed: $passed,
        failed: $failed,
        total: $total
    }'

# Exit with appropriate code
if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
