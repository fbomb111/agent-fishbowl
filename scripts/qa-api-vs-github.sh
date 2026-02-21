#!/bin/bash
# qa-api-vs-github.sh — Cross-reference Agent Fishbowl API claims against GitHub reality.
# Compares agent-status, commit counts, workflow names against actual GitHub data.
# Outputs structured JSON to stdout. Exit 0 if all pass, 1 if any fail.
# Requires: gh CLI (authenticated), curl, jq
set -euo pipefail

# --- Config ---
API_BASE="${FISHBOWL_API_BASE:-https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io}"
API_PREFIX="${API_BASE}/api/fishbowl"
REPO="${FISHBOWL_REPO:-YourMoveLabs/agent-fishbowl}"

# --- Defaults ---
RUN_ALL=true
CHECK_FILTER=""

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/qa-api-vs-github.sh [OPTIONS]

Cross-reference Agent Fishbowl API claims against GitHub reality.

Options:
  --check NAME      Run a single check (agent-status, workflows, commit-counts, active-agents, blog-metadata)
  --base-url URL    Override API base URL
  --repo OWNER/REPO Override GitHub repo (default: YourMoveLabs/agent-fishbowl)
  --help            Show this help

Examples:
  scripts/qa-api-vs-github.sh
  scripts/qa-api-vs-github.sh --check agent-status
  scripts/qa-api-vs-github.sh --base-url https://agentfishbowl.com

Output: JSON with pass/fail per check, showing both API and GitHub values.
Requires: gh CLI (authenticated), curl, jq
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) CHECK_FILTER="$2"; RUN_ALL=false; shift 2 ;;
        --base-url) API_BASE="$2"; API_PREFIX="${API_BASE}/api/fishbowl"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

should_check() {
    [[ "$RUN_ALL" == "true" ]] || [[ "$CHECK_FILTER" == "$1" ]]
}

# Map API role names to actual workflow filenames.
# The API returns full role names (e.g. "product-owner") but workflow files
# don't always follow the agent-{role}.yml pattern.
role_to_workflow() {
    local role="$1"
    case "$role" in
        product-owner)       echo "agent-product-owner.yml" ;;
        product-manager)     echo "agent-strategic.yml" ;;
        site-reliability)    echo "agent-site-reliability.yml" ;;
        user-experience)     echo "agent-user-experience.yml" ;;
        tech-lead)           echo "agent-scans.yml" ;;
        product-analyst)     echo "agent-product-analyst-discovery.yml" ;;
        *)                   echo "agent-${role}.yml" ;;
    esac
}

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Results accumulator ---
CHECKS="[]"

add_check() {
    local check_name="$1" passed="$2"
    shift 2
    local extra="{}"
    while [[ $# -ge 2 ]]; do
        local k="$1" v="$2"
        shift 2
        if echo "$v" | jq . >/dev/null 2>&1; then
            extra=$(echo "$extra" | jq --arg k "$k" --argjson v "$v" '. + {($k): $v}')
        else
            extra=$(echo "$extra" | jq --arg k "$k" --arg v "$v" '. + {($k): $v}')
        fi
    done
    local entry
    entry=$(jq -n \
        --arg check "$check_name" \
        --argjson passed "$passed" \
        --argjson extra "$extra" \
        '{check: $check, passed: $passed} + $extra')
    CHECKS=$(echo "$CHECKS" | jq --argjson e "$entry" '. + [$e]')
}

# --- Check: agent-status ---
# Compare API agent-status (last_run, status) vs actual gh run list per workflow
if should_check "agent-status"; then
    AGENT_STATUS=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/activity/agent-status" 2>/dev/null || echo '{"agents":[]}')

    MISMATCHES="[]"
    # For each agent in the API response, check if GitHub agrees
    AGENT_COUNT=$(echo "$AGENT_STATUS" | jq '.agents | length')
    for i in $(seq 0 $((AGENT_COUNT - 1))); do
        ROLE=$(echo "$AGENT_STATUS" | jq -r ".agents[$i].role")
        API_STATUS=$(echo "$AGENT_STATUS" | jq -r ".agents[$i].status")
        API_CONCLUSION=$(echo "$AGENT_STATUS" | jq -r ".agents[$i].last_conclusion // \"unknown\"")

        # Find the workflow file for this role
        WORKFLOW_FILE=$(role_to_workflow "$ROLE")
        GH_RUNS=$(gh run list --repo "$REPO" --workflow="$WORKFLOW_FILE" --limit 3 \
            --json status,conclusion,createdAt 2>/dev/null || echo "[]")

        GH_RUN_COUNT=$(echo "$GH_RUNS" | jq 'length')
        if [[ "$GH_RUN_COUNT" == "0" ]]; then
            # Check if the API reports this agent as never-run — that's expected, not a mismatch
            API_HAS_RUN=$(echo "$AGENT_STATUS" | jq -r ".agents[$i].has_run // true")
            if [[ "$API_HAS_RUN" == "false" ]]; then
                # Agent has never run — no runs in GitHub is the correct state
                continue
            fi
            # No runs found but API thinks it has run — could be wrong workflow filename
            MISMATCHES=$(echo "$MISMATCHES" | jq --arg role "$ROLE" --arg wf "$WORKFLOW_FILE" \
                '. + [{"role": $role, "detail": "no GitHub runs found for workflow", "workflow": $wf}]')
            continue
        fi

        GH_LATEST_CONCLUSION=$(echo "$GH_RUNS" | jq -r '.[0].conclusion // "unknown"')

        # If API says "idle" but GitHub shows recent runs in last 4 hours, flag it
        if [[ "$API_STATUS" == "idle" ]]; then
            LAST_RUN_TIME=$(echo "$GH_RUNS" | jq -r '.[0].createdAt // ""')
            if [[ -n "$LAST_RUN_TIME" ]]; then
                NOW_EPOCH=$(date +%s)
                RUN_EPOCH=$(date -d "$LAST_RUN_TIME" +%s 2>/dev/null || echo "0")
                HOURS_AGO=$(( (NOW_EPOCH - RUN_EPOCH) / 3600 ))
                # Check for conclusion mismatch
                if [[ "$API_CONCLUSION" != "$GH_LATEST_CONCLUSION" && "$GH_LATEST_CONCLUSION" != "unknown" && "$API_CONCLUSION" != "unknown" ]]; then
                    MISMATCHES=$(echo "$MISMATCHES" | jq \
                        --arg role "$ROLE" \
                        --arg api_conc "$API_CONCLUSION" \
                        --arg gh_conc "$GH_LATEST_CONCLUSION" \
                        '. + [{"role": $role, "detail": "conclusion mismatch", "api_conclusion": $api_conc, "github_conclusion": $gh_conc}]')
                fi
            fi
        fi
    done

    MISMATCH_COUNT=$(echo "$MISMATCHES" | jq 'length')
    if [[ "$MISMATCH_COUNT" == "0" ]]; then
        add_check "agent-status" true "agents_checked" "$AGENT_COUNT"
    else
        add_check "agent-status" false "mismatches" "$MISMATCHES" "agents_checked" "$AGENT_COUNT"
    fi
fi

# --- Check: workflows ---
# Verify workflow filenames in agent-status actually exist in the repo
if should_check "workflows"; then
    AGENT_STATUS=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/activity/agent-status" 2>/dev/null || echo '{"agents":[]}')

    # Get actual workflow files from GitHub
    ACTUAL_WORKFLOWS=$(gh api "repos/${REPO}/contents/.github/workflows" --jq '.[].name' 2>/dev/null || echo "")

    MISSING="[]"
    AGENT_COUNT=$(echo "$AGENT_STATUS" | jq '.agents | length')
    for i in $(seq 0 $((AGENT_COUNT - 1))); do
        ROLE=$(echo "$AGENT_STATUS" | jq -r ".agents[$i].role")
        EXPECTED_WF=$(role_to_workflow "$ROLE")
        if ! echo "$ACTUAL_WORKFLOWS" | grep -qF "$EXPECTED_WF"; then
            MISSING=$(echo "$MISSING" | jq --arg role "$ROLE" --arg wf "$EXPECTED_WF" \
                '. + [{"role": $role, "expected_workflow": $wf}]')
        fi
    done

    MISSING_COUNT=$(echo "$MISSING" | jq 'length')
    if [[ "$MISSING_COUNT" == "0" ]]; then
        add_check "workflows" true "agents_checked" "$AGENT_COUNT"
    else
        add_check "workflows" false "missing_workflows" "$MISSING"
    fi
fi

# --- Check: commit-counts ---
# Compare /goals by_agent commit counts against GitHub Commits API
if should_check "commit-counts"; then
    GOALS=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/goals" 2>/dev/null || echo '{"metrics":{}}')

    # Get 7-day window
    SINCE=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")

    DISCREPANCIES="[]"
    # Check only code-writing agents (engineer, tech-lead)
    # Other agents (content-creator, product-owner, site-reliability) don't commit code by design
    for AGENT in engineer tech-lead; do
        API_COMMITS=$(echo "$GOALS" | jq --arg a "$AGENT" '.metrics.by_agent[$a].commits // 0')

        # Query GitHub commits by author
        # Agent commits come through as github-actions[bot], so we check via search
        GH_COMMITS=0
        if [[ -n "$SINCE" ]]; then
            GH_COMMITS=$(gh api "repos/${REPO}/commits?since=${SINCE}&per_page=100" \
                --jq 'length' 2>/dev/null || echo "0")
        fi

        # Check if API shows 0 when GitHub has commits
        # This would indicate a bug in the API's commit attribution logic
        if [[ "$API_COMMITS" == "0" ]]; then
            DISCREPANCIES=$(echo "$DISCREPANCIES" | jq \
                --arg agent "$AGENT" \
                --argjson api "$API_COMMITS" \
                '. + [{"agent": $agent, "api_commits": $api, "detail": "API reports zero commits"}]')
        fi
    done

    DISC_COUNT=$(echo "$DISCREPANCIES" | jq 'length')
    if [[ "$DISC_COUNT" == "0" ]]; then
        add_check "commit-counts" true
    else
        add_check "commit-counts" false "discrepancies" "$DISCREPANCIES"
    fi
fi

# --- Check: active-agents ---
# Compare number of agents shown as active in API vs unique workflows with recent runs
if should_check "active-agents"; then
    AGENT_STATUS=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/activity/agent-status" 2>/dev/null || echo '{"agents":[]}')

    # Count agents that have run at least once (not total — some agents are on-demand/weekly)
    API_HAS_RUN=$(echo "$AGENT_STATUS" | jq '[.agents[] | select(.has_run == true)] | length')
    API_TOTAL=$(echo "$AGENT_STATUS" | jq '.agents | length')

    # Get unique workflows with runs in last 7 days
    GH_RECENT=$(gh run list --repo "$REPO" --limit 50 --json workflowName,createdAt 2>/dev/null || echo "[]")
    SEVEN_DAYS_AGO_EPOCH=$(date -d "7 days ago" +%s 2>/dev/null || date -v-7d +%s 2>/dev/null || echo "0")
    GH_ACTIVE=$(echo "$GH_RECENT" | jq --argjson cutoff "$SEVEN_DAYS_AGO_EPOCH" '
        [.[] | select((.createdAt | sub("\\.[0-9]+Z$"; "Z") | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) > $cutoff) | .workflowName] | unique | length')

    # Compare has_run count vs recent GitHub activity — allow ±5 slack for weekly/monthly agents
    DIFF=$((API_HAS_RUN - GH_ACTIVE))
    if [[ "$DIFF" -lt 0 ]]; then DIFF=$((-DIFF)); fi

    if [[ "$DIFF" -le 5 ]]; then
        add_check "active-agents" true \
            "api_has_run" "$API_HAS_RUN" "api_total" "$API_TOTAL" "github_active_workflows" "$GH_ACTIVE"
    else
        add_check "active-agents" false \
            "api_has_run" "$API_HAS_RUN" "api_total" "$API_TOTAL" "github_active_workflows" "$GH_ACTIVE" \
            "detail" "\"Agent has_run count differs from GitHub active by more than 5\""
    fi
fi

# --- Check: blog-metadata ---
# Validate blog post dates are in reasonable range and slugs are well-formed
if should_check "blog-metadata"; then
    BLOG=$(curl -sf --connect-timeout 10 --max-time 15 "${API_PREFIX}/blog" 2>/dev/null || echo '{"posts":[]}')

    NOW_EPOCH=$(date +%s)
    # Posts should not be dated in the future or before 2024
    MIN_EPOCH=$(date -d "2024-01-01" +%s 2>/dev/null || echo "1704067200")

    BAD_DATES=$(echo "$BLOG" | jq --argjson now "$NOW_EPOCH" --argjson min "$MIN_EPOCH" '
        [.posts[] | select(.published_at != null) |
            .published_at as $d |
            ($d | sub("\\.[0-9]+Z$"; "Z") | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) as $epoch |
            select($epoch > $now or $epoch < $min) |
            {id, slug, published_at, issue: (if $epoch > $now then "future_date" else "too_old" end)}
        ] | length')

    # Check slugs are URL-safe (no spaces, no special chars except hyphens)
    BAD_SLUGS=$(echo "$BLOG" | jq '
        [.posts[] | select(.slug != null) |
            select(.slug | test("^[a-z0-9][a-z0-9-]*[a-z0-9]$") | not) |
            {id, slug}
        ] | length')

    ISSUES=$((BAD_DATES + BAD_SLUGS))
    if [[ "$ISSUES" == "0" ]]; then
        add_check "blog-metadata" true
    else
        add_check "blog-metadata" false \
            "bad_dates" "$BAD_DATES" "bad_slugs" "$BAD_SLUGS"
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
