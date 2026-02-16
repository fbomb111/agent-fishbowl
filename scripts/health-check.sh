#!/bin/bash
# health-check.sh — System health check for Agent Fishbowl SRE agent.
# Checks API health, ingestion freshness, deployment status, and GitHub rate limits.
# Outputs JSON to stdout. Uses GH_TOKEN from environment for GitHub checks.
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
HEALTH_URL="${API_BASE}/api/fishbowl/health"
ARTICLES_URL="${API_BASE}/api/fishbowl/articles"
INGEST_WORKFLOW="${FISHBOWL_INGEST_WORKFLOW:-ingest.yml}"
DEPLOY_WORKFLOW="${FISHBOWL_DEPLOY_WORKFLOW:-deploy.yml}"

# Freshness thresholds (hours)
FRESH_THRESHOLD=12
STALE_THRESHOLD=24

# --- Defaults ---
CHECK_API=true
CHECK_INGESTION=true
CHECK_DEPLOYS=true
CHECK_GITHUB=true

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/health-check.sh [OPTIONS]

Check Agent Fishbowl system health: API, ingestion, deploys, GitHub.

Options:
  --api-only            Only check API health
  --ingestion-only      Only check ingestion freshness
  --deploys-only        Only check deployment status
  --github-only         Only check GitHub health (rate limits, workflow failures)
  --all                 Full check (default)
  --help                Show this help

Examples:
  # Full system health check (SRE primary use case)
  scripts/health-check.sh

  # Quick API check
  scripts/health-check.sh --api-only

Output: JSON object with overall status (GREEN/YELLOW/RED) and per-subsystem details.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-only) CHECK_API=true; CHECK_INGESTION=false; CHECK_DEPLOYS=false; CHECK_GITHUB=false; shift ;;
        --ingestion-only) CHECK_API=false; CHECK_INGESTION=true; CHECK_DEPLOYS=false; CHECK_GITHUB=false; shift ;;
        --deploys-only) CHECK_API=false; CHECK_INGESTION=false; CHECK_DEPLOYS=true; CHECK_GITHUB=false; shift ;;
        --github-only) CHECK_API=false; CHECK_INGESTION=false; CHECK_DEPLOYS=false; CHECK_GITHUB=true; shift ;;
        --all) CHECK_API=true; CHECK_INGESTION=true; CHECK_DEPLOYS=true; CHECK_GITHUB=true; shift ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Helper: compute hours since a timestamp ---
hours_since() {
    local ts="$1"
    local now_epoch
    local ts_epoch
    now_epoch=$(date +%s)
    # Handle both ISO formats (with and without timezone)
    ts_epoch=$(date -d "$ts" +%s 2>/dev/null || date -d "${ts%Z}" +%s 2>/dev/null || echo "0")
    if [[ "$ts_epoch" == "0" ]]; then
        echo "999"
        return
    fi
    echo $(( (now_epoch - ts_epoch) / 3600 ))
}

# --- Check: API ---
api_result='{"status":"skipped"}'
if [[ "$CHECK_API" == "true" ]]; then
    HTTP_CODE=0
    RESPONSE_TIME=0
    BODY=""

    # Measure response time and capture status code
    HTTP_RESPONSE=$(curl -s -o /tmp/health_body -w "%{http_code} %{time_total}" \
        --connect-timeout 10 --max-time 15 \
        "$HEALTH_URL" 2>/dev/null) || true

    if [[ -n "$HTTP_RESPONSE" ]]; then
        HTTP_CODE=$(echo "$HTTP_RESPONSE" | awk '{print $1}')
        RESPONSE_TIME=$(echo "$HTTP_RESPONSE" | awk '{printf "%.0f", $2 * 1000}')
        BODY=$(cat /tmp/health_body 2>/dev/null || echo "")
    fi

    if [[ "$HTTP_CODE" == "200" ]]; then
        API_STATUS="healthy"
    elif [[ "$HTTP_CODE" == "0" ]]; then
        API_STATUS="unreachable"
    else
        API_STATUS="unhealthy"
    fi

    api_result=$(jq -n \
        --arg status "$API_STATUS" \
        --argjson code "$HTTP_CODE" \
        --argjson time "$RESPONSE_TIME" \
        '{status: $status, http_code: $code, response_time_ms: $time}')
fi

# --- Check: Ingestion ---
ingestion_result='{"status":"skipped"}'
if [[ "$CHECK_INGESTION" == "true" ]]; then
    ARTICLES_JSON=$(curl -sf --connect-timeout 10 --max-time 15 "$ARTICLES_URL" 2>/dev/null || echo '{"articles":[]}')

    ARTICLE_COUNT=$(echo "$ARTICLES_JSON" | jq '[.articles // []] | .[0] | length' 2>/dev/null || echo "0")
    NEWEST_ARTICLE=$(echo "$ARTICLES_JSON" | jq -r '[.articles // []] | .[0] | .[0].published_at // "unknown"' 2>/dev/null || echo "unknown")

    HOURS_SINCE=999
    if [[ "$NEWEST_ARTICLE" != "unknown" && "$NEWEST_ARTICLE" != "null" ]]; then
        HOURS_SINCE=$(hours_since "$NEWEST_ARTICLE")
    fi

    if [[ "$HOURS_SINCE" -le "$FRESH_THRESHOLD" ]]; then
        INGEST_STATUS="fresh"
    elif [[ "$HOURS_SINCE" -le "$STALE_THRESHOLD" ]]; then
        INGEST_STATUS="stale"
    else
        INGEST_STATUS="critical"
    fi

    # Check recent ingest workflow runs
    INGEST_RUNS=$(gh run list --workflow="$INGEST_WORKFLOW" --limit 3 --json status,conclusion,createdAt 2>/dev/null || echo "[]")

    ingestion_result=$(jq -n \
        --arg status "$INGEST_STATUS" \
        --arg newest "$NEWEST_ARTICLE" \
        --argjson count "$ARTICLE_COUNT" \
        --argjson hours "$HOURS_SINCE" \
        --argjson runs "$INGEST_RUNS" \
        '{status: $status, newest_article: $newest, article_count: $count, hours_since_newest: $hours, recent_workflow_runs: $runs}')
fi

# --- Check: Deploys ---
deploys_result='{"status":"skipped"}'
if [[ "$CHECK_DEPLOYS" == "true" ]]; then
    DEPLOY_RUNS=$(gh run list --workflow="$DEPLOY_WORKFLOW" --limit 5 --json status,conclusion,createdAt,headBranch 2>/dev/null || echo "[]")

    LAST_SUCCESS=$(echo "$DEPLOY_RUNS" | jq -r '[.[] | select(.conclusion == "success")] | .[0].createdAt // "none"' 2>/dev/null || echo "none")
    RECENT_FAILURES=$(echo "$DEPLOY_RUNS" | jq '[.[] | select(.conclusion == "failure")] | length' 2>/dev/null || echo "0")

    if [[ "$RECENT_FAILURES" == "0" ]]; then
        DEPLOY_STATUS="passing"
    elif [[ "$LAST_SUCCESS" != "none" ]]; then
        DEPLOY_STATUS="degraded"
    else
        DEPLOY_STATUS="failing"
    fi

    deploys_result=$(jq -n \
        --arg status "$DEPLOY_STATUS" \
        --arg last_success "$LAST_SUCCESS" \
        --argjson runs "$DEPLOY_RUNS" \
        '{status: $status, last_success: $last_success, recent_runs: $runs}')
fi

# --- Check: GitHub ---
github_result='{"status":"skipped"}'
if [[ "$CHECK_GITHUB" == "true" ]]; then
    RATE_LIMIT=$(gh api /rate_limit --jq '{core: .resources.core, graphql: .resources.graphql}' 2>/dev/null || echo '{"core":{"remaining":0,"limit":0},"graphql":{"remaining":0,"limit":0}}')

    RATE_REMAINING=$(echo "$RATE_LIMIT" | jq '.core.remaining' 2>/dev/null || echo "0")
    RATE_TOTAL=$(echo "$RATE_LIMIT" | jq '.core.limit' 2>/dev/null || echo "0")

    # Count failed workflows in last 24h
    ALL_RUNS=$(gh run list --limit 20 --json workflowName,conclusion,createdAt 2>/dev/null || echo "[]")
    FAILED_24H=$(echo "$ALL_RUNS" | jq '[.[] | select(.conclusion == "failure")] | length' 2>/dev/null || echo "0")

    github_result=$(jq -n \
        --argjson remaining "$RATE_REMAINING" \
        --argjson total "$RATE_TOTAL" \
        --argjson failed "$FAILED_24H" \
        '{rate_limit_remaining: $remaining, rate_limit_total: $total, failed_workflows_24h: $failed}')
fi

# --- Compute overall status ---
OVERALL="GREEN"

# RED conditions
if [[ "$CHECK_API" == "true" ]]; then
    api_status=$(echo "$api_result" | jq -r '.status')
    if [[ "$api_status" == "unreachable" || "$api_status" == "unhealthy" ]]; then
        OVERALL="RED"
    fi
fi
if [[ "$CHECK_INGESTION" == "true" ]]; then
    ingest_status=$(echo "$ingestion_result" | jq -r '.status')
    if [[ "$ingest_status" == "critical" ]]; then
        OVERALL="RED"
    fi
fi
if [[ "$CHECK_DEPLOYS" == "true" ]]; then
    deploy_status=$(echo "$deploys_result" | jq -r '.status')
    if [[ "$deploy_status" == "failing" ]]; then
        OVERALL="RED"
    fi
fi

# YELLOW conditions (only if not already RED)
if [[ "$OVERALL" == "GREEN" ]]; then
    if [[ "$CHECK_INGESTION" == "true" ]]; then
        ingest_status=$(echo "$ingestion_result" | jq -r '.status')
        if [[ "$ingest_status" == "stale" ]]; then
            OVERALL="YELLOW"
        fi
    fi
    if [[ "$CHECK_DEPLOYS" == "true" ]]; then
        deploy_status=$(echo "$deploys_result" | jq -r '.status')
        if [[ "$deploy_status" == "degraded" ]]; then
            OVERALL="YELLOW"
        fi
    fi
fi

# --- Output ---
jq -n \
    --arg checked_at "$CHECKED_AT" \
    --arg overall "$OVERALL" \
    --argjson api "$api_result" \
    --argjson ingestion "$ingestion_result" \
    --argjson deploys "$deploys_result" \
    --argjson github "$github_result" \
    '{
        checked_at: $checked_at,
        overall: $overall,
        api: $api,
        ingestion: $ingestion,
        deploys: $deploys,
        github: $github
    }'
