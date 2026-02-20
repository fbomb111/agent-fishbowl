#!/bin/bash
# qa-api-consistency.sh — Validate internal consistency of Agent Fishbowl API responses.
# Checks that the API's own numbers add up, required fields are present, and no duplicates exist.
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"

# Known agent roles (union of all endpoints)
KNOWN_ROLES=(
    content-creator customer-ops engineer human-ops ops-engineer
    pm po qa-analyst reviewer sre tech-lead triage ux
)
# Service accounts that appear in by_agent but aren't agent roles
KNOWN_SERVICE_ACCOUNTS=(github-actions human)

# --- Defaults ---
RUN_ALL=true
ENDPOINT_FILTER=""

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-api-consistency.sh [OPTIONS]

Validate internal consistency of Agent Fishbowl API responses.

Options:
  --endpoint NAME   Run checks for a single endpoint (health, usage, activity, goals, articles, blog, stats)
  --base-url URL    Override API base URL
  --help            Show this help

Examples:
  scripts/qa-api-consistency.sh
  scripts/qa-api-consistency.sh --endpoint usage
  scripts/qa-api-consistency.sh --base-url https://agentfishbowl.com

Output: JSON with pass/fail per check, summary counts, exit code 0 (all pass) or 1 (any fail).
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --endpoint) ENDPOINT_FILTER="$2"; RUN_ALL=false; shift 2 ;;
        --base-url) API_BASE="$2"; API_PREFIX="${API_BASE}/api/fishbowl"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

should_check() {
    [[ "$RUN_ALL" == "true" ]] || [[ "$ENDPOINT_FILTER" == "$1" ]]
}

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Results accumulator ---
CHECKS="[]"

add_check() {
    local endpoint="$1" check="$2" passed="$3"
    shift 3
    # Remaining args are key-value pairs for extra fields
    local extra="{}"
    while [[ $# -ge 2 ]]; do
        local k="$1" v="$2"
        shift 2
        # Try to parse v as JSON; if it fails, treat as string
        if echo "$v" | jq . >/dev/null 2>&1; then
            extra=$(echo "$extra" | jq --arg k "$k" --argjson v "$v" '. + {($k): $v}')
        else
            extra=$(echo "$extra" | jq --arg k "$k" --arg v "$v" '. + {($k): $v}')
        fi
    done
    local entry
    entry=$(jq -n \
        --arg endpoint "$endpoint" \
        --arg check "$check" \
        --argjson passed "$passed" \
        --argjson extra "$extra" \
        '{endpoint: $endpoint, check: $check, passed: $passed} + $extra')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
}

# --- Check: /health ---
if should_check "health"; then
    HEALTH=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/health" 2>/dev/null || echo '{}')
    STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')
    if [[ "$STATUS" == "ok" ]]; then
        add_check "/health" "status_is_ok" true
    else
        add_check "/health" "status_is_ok" false "actual" "\"$STATUS\""
    fi
fi

# --- Check: /activity/usage ---
if should_check "usage"; then
    USAGE=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/activity/usage" 2>/dev/null || echo '{"total_runs":0,"by_role":[]}')

    # Check 1: total_runs == sum of by_role[].run_count
    TOTAL_RUNS=$(echo "$USAGE" | jq '.total_runs // 0')
    SUM_ROLE_RUNS=$(echo "$USAGE" | jq '[.by_role[].run_count] | add // 0')
    if [[ "$TOTAL_RUNS" == "$SUM_ROLE_RUNS" ]]; then
        add_check "/activity/usage" "total_runs_matches_sum" true
    else
        add_check "/activity/usage" "total_runs_matches_sum" false \
            "expected" "$SUM_ROLE_RUNS" "actual" "$TOTAL_RUNS"
    fi

    # Check 2: No duplicate role names
    ROLE_COUNT=$(echo "$USAGE" | jq '[.by_role[].role] | length')
    UNIQUE_COUNT=$(echo "$USAGE" | jq '[.by_role[].role] | unique | length')
    if [[ "$ROLE_COUNT" == "$UNIQUE_COUNT" ]]; then
        add_check "/activity/usage" "no_duplicate_roles" true
    else
        DUPES=$(echo "$USAGE" | jq '[.by_role[].role] | group_by(.) | map(select(length > 1) | .[0])')
        add_check "/activity/usage" "no_duplicate_roles" false "duplicates" "$DUPES"
    fi

    # Check 3: All roles in known roster
    ALL_KNOWN=("${KNOWN_ROLES[@]}" "${KNOWN_SERVICE_ACCOUNTS[@]}")
    KNOWN_JSON=$(printf '%s\n' "${ALL_KNOWN[@]}" | jq -R . | jq -s .)
    UNKNOWN=$(echo "$USAGE" | jq --argjson known "$KNOWN_JSON" \
        '[.by_role[].role] | map(select(. as $r | $known | index($r) | not))')
    UNKNOWN_COUNT=$(echo "$UNKNOWN" | jq 'length')
    if [[ "$UNKNOWN_COUNT" == "0" ]]; then
        add_check "/activity/usage" "all_roles_known" true
    else
        add_check "/activity/usage" "all_roles_known" false "unknown_roles" "$UNKNOWN"
    fi
fi

# --- Check: /activity?mode=threaded ---
if should_check "activity"; then
    ACTIVITY=$(curl -sf --connect-timeout 10 --max-time 30 "${API_PREFIX}/activity?mode=threaded" 2>/dev/null || echo '{"threads":[]}')

    # Check 4: No pr_opened events with url: null
    NULL_PR_URLS=$(echo "$ACTIVITY" | jq '[.threads[].events[] | select(.type == "pr_opened" and (.url == null or .url == ""))] | length')
    if [[ "$NULL_PR_URLS" == "0" ]]; then
        add_check "/activity?mode=threaded" "no_null_pr_urls" true
    else
        add_check "/activity?mode=threaded" "no_null_pr_urls" false "count" "$NULL_PR_URLS"
    fi

    # Check 5: No duplicate events within a thread (same type+description)
    DUPE_THREADS=$(echo "$ACTIVITY" | jq '
        [.threads[] |
            .subject_number as $sn |
            [.events[] | {type, description}] |
            group_by({type, description}) |
            map(select(length > 1)) |
            select(length > 0) |
            {subject: $sn, duplicate_count: (map(length) | add)}
        ] | length')
    if [[ "$DUPE_THREADS" == "0" ]]; then
        add_check "/activity?mode=threaded" "no_duplicate_events" true
    else
        add_check "/activity?mode=threaded" "no_duplicate_events" false "threads_with_dupes" "$DUPE_THREADS"
    fi
fi

# --- Check: /goals ---
if should_check "goals"; then
    GOALS=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/goals" 2>/dev/null || echo '{"metrics":{}}')

    # Check 6: commits.7d >= sum of by_agent commits
    COMMITS_7D=$(echo "$GOALS" | jq '.metrics.commits."7d" // 0')
    SUM_AGENT_COMMITS=$(echo "$GOALS" | jq '[.metrics.by_agent | to_entries[].value.commits] | add // 0')
    if [[ "$COMMITS_7D" -ge "$SUM_AGENT_COMMITS" ]]; then
        add_check "/goals" "commits_7d_gte_agent_sum" true
    else
        add_check "/goals" "commits_7d_gte_agent_sum" false \
            "commits_7d" "$COMMITS_7D" "agent_sum" "$SUM_AGENT_COMMITS"
    fi

    # Check 7: All agents in by_agent exist in known roster + service accounts
    ALL_KNOWN=("${KNOWN_ROLES[@]}" "${KNOWN_SERVICE_ACCOUNTS[@]}")
    KNOWN_JSON=$(printf '%s\n' "${ALL_KNOWN[@]}" | jq -R . | jq -s .)
    UNKNOWN_AGENTS=$(echo "$GOALS" | jq --argjson known "$KNOWN_JSON" \
        '[.metrics.by_agent | keys[] | select(. as $a | $known | index($a) | not)]')
    UNKNOWN_AGENT_COUNT=$(echo "$UNKNOWN_AGENTS" | jq 'length')
    if [[ "$UNKNOWN_AGENT_COUNT" == "0" ]]; then
        add_check "/goals" "all_agents_known" true
    else
        add_check "/goals" "all_agents_known" false "unknown_agents" "$UNKNOWN_AGENTS"
    fi
fi

# --- Check: /articles ---
if should_check "articles"; then
    ARTICLES=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/articles" 2>/dev/null || echo '{"articles":[]}')

    # Check 8: No duplicate article IDs
    ID_COUNT=$(echo "$ARTICLES" | jq '[.articles[].id] | length')
    UNIQUE_ID_COUNT=$(echo "$ARTICLES" | jq '[.articles[].id] | unique | length')
    if [[ "$ID_COUNT" == "$UNIQUE_ID_COUNT" ]]; then
        add_check "/articles" "no_duplicate_ids" true
    else
        DUPE_COUNT=$((ID_COUNT - UNIQUE_ID_COUNT))
        add_check "/articles" "no_duplicate_ids" false "duplicate_count" "$DUPE_COUNT"
    fi
fi

# --- Check: /blog ---
if should_check "blog"; then
    BLOG=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/blog" 2>/dev/null || echo '{"posts":[]}')

    # Check 9: Posts have non-empty title, slug, id
    BAD_POSTS=$(echo "$BLOG" | jq '[.posts[] | select(
        (.title // "" | length) == 0 or
        (.slug // "" | length) == 0 or
        (.id // "" | tostring | length) == 0
    )] | length')
    if [[ "$BAD_POSTS" == "0" ]]; then
        add_check "/blog" "posts_have_required_fields" true
    else
        add_check "/blog" "posts_have_required_fields" false "posts_missing_fields" "$BAD_POSTS"
    fi
fi

# --- Check: /stats ---
if should_check "stats"; then
    STATS_RESPONSE=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/stats" 2>/dev/null || echo "")
    if [[ -n "$STATS_RESPONSE" ]] && echo "$STATS_RESPONSE" | jq . >/dev/null 2>&1; then
        add_check "/stats" "returns_valid_json" true
    else
        add_check "/stats" "returns_valid_json" false
    fi
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
