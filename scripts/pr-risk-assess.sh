#!/bin/bash
# pr-risk-assess.sh — Analyze a PR's risk level for automated review gating.
# Determines whether a PR can be auto-approved or needs AI reviewer attention.
# Outputs structured JSON to stdout. Exit 0 always (risk level is in the JSON).
# Requires: gh CLI (authenticated), jq
set -euo pipefail

# --- Config ---
REPO="${FISHBOWL_REPO:-${GITHUB_REPOSITORY:-}}"
# Fall back to git remote if neither env var is set
if [[ -z "$REPO" ]]; then
    REPO=$(git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||' || echo "")
fi

# Known bot authors that produce predictable PRs
# gh CLI returns "app/NAME" format for GitHub App authors
KNOWN_BOTS=(
    "app/fishbowl-engineer"
    "app/fishbowl-ops-engineer"
    "app/fishbowl-infra-engineer"
)

# Sensitive file patterns — changes to these need AI scrutiny
SENSITIVE_PATTERNS=(
    ".github/workflows/"
    "Dockerfile"
    "docker-compose"
    "config/"
    ".env"
    "*.pem"
    "*.key"
    "scripts/"
    "action.yml"
)

# Architecture file patterns — structural changes need review
ARCHITECTURE_PATTERNS=(
    "models/"
    "routes/"
    "routers/"
    "services/"
    "middleware/"
)

# Dependency files
DEPENDENCY_FILES=(
    "requirements.txt"
    "package.json"
    "package-lock.json"
    "yarn.lock"
    "pyproject.toml"
    "poetry.lock"
)

# --- Defaults ---
PR_NUMBER=""
DIFF_THRESHOLD=300   # Lines changed above this → large_diff flag

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/pr-risk-assess.sh --pr NUMBER [OPTIONS]

Analyze a PR's risk level for automated review gating.

Options:
  --pr NUMBER         PR number to assess (required)
  --repo OWNER/REPO   Override GitHub repo
  --threshold N       Lines-changed threshold for large_diff flag (default: 300)
  --help              Show this help

Output: JSON with risk_level, auto_approvable, flags, and stats.

Risk levels:
  skip    — PR not ready for review (CI pending/failing, draft, max rounds)
  low     — Clean, auto-approvable PR
  medium  — Some concerns, but may still be OK
  high    — Needs AI reviewer attention

Examples:
  scripts/pr-risk-assess.sh --pr 42
  scripts/pr-risk-assess.sh --pr 42 --threshold 200
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr) PR_NUMBER="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --threshold) DIFF_THRESHOLD="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$PR_NUMBER" ]]; then
    echo "Error: --pr NUMBER is required" >&2
    exit 1
fi

CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Collect PR metadata ---
PR_JSON=$(gh pr view "$PR_NUMBER" --repo "$REPO" \
    --json number,title,author,isDraft,body,labels,reviewDecision,mergeable,headRefName,baseRefName,additions,deletions,changedFiles \
    2>/dev/null || echo '{}')

if [[ "$PR_JSON" == "{}" || -z "$PR_JSON" ]]; then
    jq -n --arg pr "$PR_NUMBER" --arg ts "$CHECKED_AT" '{
        pr_number: ($pr | tonumber),
        risk_level: "skip",
        auto_approvable: false,
        flags: ["pr_not_found"],
        stats: {},
        timestamp: $ts
    }'
    exit 0
fi

# Extract fields
AUTHOR=$(echo "$PR_JSON" | jq -r '.author.login // "unknown"')
IS_DRAFT=$(echo "$PR_JSON" | jq -r '.isDraft')
BODY=$(echo "$PR_JSON" | jq -r '.body // ""')
REVIEW_DECISION=$(echo "$PR_JSON" | jq -r '.reviewDecision // "none"')
ADDITIONS=$(echo "$PR_JSON" | jq -r '.additions // 0')
DELETIONS=$(echo "$PR_JSON" | jq -r '.deletions // 0')
CHANGED_FILES=$(echo "$PR_JSON" | jq -r '.changedFiles // 0')
LINES_CHANGED=$((ADDITIONS + DELETIONS))

# --- Check CI status ---
CI_STATUS="unknown"
CI_CHECKS=$(gh pr checks "$PR_NUMBER" --repo "$REPO" --json name,state,conclusion 2>/dev/null || echo "[]")
if [[ "$CI_CHECKS" != "[]" ]]; then
    FAILING=$(echo "$CI_CHECKS" | jq '[.[] | select(.conclusion == "FAILURE" or .conclusion == "failure")] | length')
    PENDING=$(echo "$CI_CHECKS" | jq '[.[] | select(.state == "PENDING" or .state == "pending" or .conclusion == null or .conclusion == "")] | length')
    PASSING=$(echo "$CI_CHECKS" | jq '[.[] | select(.conclusion == "SUCCESS" or .conclusion == "success")] | length')
    if [[ "$FAILING" -gt 0 ]]; then
        CI_STATUS="failing"
    elif [[ "$PENDING" -gt 0 ]]; then
        CI_STATUS="pending"
    elif [[ "$PASSING" -gt 0 ]]; then
        CI_STATUS="passing"
    fi
fi

# --- Check review round ---
REVIEWER_BOT="fishbowl-reviewer[bot]"
REVIEW_ROUND=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" \
    --jq "[.[] | select(.user.login == \"${REVIEWER_BOT}\" and .state == \"CHANGES_REQUESTED\")] | length" \
    2>/dev/null || echo "0")

# --- Check linked issue ---
LINKED_ISSUE=""
if echo "$BODY" | grep -qoP '(?:Closes|Fixes|Resolves)\s+#\d+'; then
    LINKED_ISSUE=$(echo "$BODY" | grep -oP '(?:Closes|Fixes|Resolves)\s+#\K\d+' | head -1)
fi

# --- Analyze changed files ---
FILE_LIST=$(gh pr diff "$PR_NUMBER" --repo "$REPO" --name-only 2>/dev/null || echo "")
FILE_TYPES=$(echo "$FILE_LIST" | sed 's/.*\.//' | sort -u | tr '\n' ',' | sed 's/,$//')

# Check for sensitive files
SENSITIVE_FOUND=false
SENSITIVE_FILES="[]"
for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    MATCHES=$(echo "$FILE_LIST" | grep -F "$pattern" 2>/dev/null || true)
    if [[ -n "$MATCHES" ]]; then
        SENSITIVE_FOUND=true
        while IFS= read -r f; do
            SENSITIVE_FILES=$(echo "$SENSITIVE_FILES" | jq --arg f "$f" '. + [$f]')
        done <<< "$MATCHES"
    fi
done

# Check for architecture files — only NEW files in key directories (not edits to existing)
ARCHITECTURE_FOUND=false
NEW_FILES=$(gh pr diff "$PR_NUMBER" --repo "$REPO" 2>/dev/null | grep -E '^\+\+\+ b/' | grep -v '/dev/null' | sed 's|^\+\+\+ b/||' || true)
# Cross-reference: files in the diff that were added (not just modified)
ADDED_FILES=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json files --jq '[.files[] | select(.status == "added") | .path] | .[]' 2>/dev/null || true)
for pattern in "${ARCHITECTURE_PATTERNS[@]}"; do
    if echo "$ADDED_FILES" | grep -qF "$pattern" 2>/dev/null; then
        ARCHITECTURE_FOUND=true
        break
    fi
done

# Check for dependency changes
DEPS_CHANGED=false
for dep_file in "${DEPENDENCY_FILES[@]}"; do
    if echo "$FILE_LIST" | grep -qF "$dep_file" 2>/dev/null; then
        DEPS_CHANGED=true
        break
    fi
done

# Check for test coverage: code files changed but no test files
CODE_FILES=$(echo "$FILE_LIST" | grep -E '\.(py|js|ts|jsx|tsx)$' | grep -vE '(test_|_test\.|\.test\.|tests/|__tests__/)' 2>/dev/null || true)
TEST_FILES=$(echo "$FILE_LIST" | grep -E '(test_|_test\.|\.test\.|tests/|__tests__/)' 2>/dev/null || true)
NO_TESTS_FOR_CODE=false
if [[ -n "$CODE_FILES" && -z "$TEST_FILES" ]]; then
    NO_TESTS_FOR_CODE=true
fi

# Check if author is a known bot
IS_BOT=false
for bot in "${KNOWN_BOTS[@]}"; do
    if [[ "$AUTHOR" == "$bot" ]]; then
        IS_BOT=true
        break
    fi
done

# --- Build flags ---
FLAGS="[]"

add_flag() {
    local flag="$1" risk="$2" detail="$3"
    FLAGS=$(echo "$FLAGS" | jq \
        --arg f "$flag" --arg r "$risk" --arg d "$detail" \
        '. + [{"flag": $f, "risk": $r, "detail": $d}]')
}

# Skip conditions
if [[ "$IS_DRAFT" == "true" ]]; then
    add_flag "draft_pr" "skip" "PR is still a draft"
fi
if [[ "$CI_STATUS" == "failing" ]]; then
    add_flag "ci_failing" "skip" "CI checks are failing"
fi
if [[ "$CI_STATUS" == "pending" ]]; then
    add_flag "ci_pending" "skip" "CI checks still running"
fi
if [[ "$REVIEW_ROUND" -ge 3 ]]; then
    add_flag "max_review_rounds" "skip" "Already had $REVIEW_ROUND review rounds (max 3)"
fi

# High risk conditions
if [[ "$LINES_CHANGED" -gt "$DIFF_THRESHOLD" ]]; then
    add_flag "large_diff" "high" "PR changes $LINES_CHANGED lines (threshold: $DIFF_THRESHOLD)"
fi
if [[ "$SENSITIVE_FOUND" == "true" ]]; then
    SENS_LIST=$(echo "$SENSITIVE_FILES" | jq -r 'join(", ")')
    add_flag "sensitive_files" "high" "Touches sensitive files: $SENS_LIST"
fi
if [[ "$ARCHITECTURE_FOUND" == "true" ]]; then
    add_flag "architecture_files" "high" "Changes to model/route/service files"
fi
if [[ "$REVIEW_ROUND" -gt 0 && "$REVIEW_ROUND" -lt 3 ]]; then
    add_flag "review_round_gt_0" "high" "Previous review round $REVIEW_ROUND — engineer already got feedback"
fi

# Medium risk conditions
if [[ "$DEPS_CHANGED" == "true" ]]; then
    add_flag "new_dependencies" "medium" "Dependency files changed"
fi
if [[ "$NO_TESTS_FOR_CODE" == "true" ]]; then
    add_flag "no_tests_for_code" "medium" "Code files changed but no test files in diff"
fi
if [[ -z "$LINKED_ISSUE" ]]; then
    add_flag "no_linked_issue" "medium" "No Closes/Fixes/Resolves #N found in PR body"
fi
if [[ "$IS_BOT" == "false" ]]; then
    add_flag "human_author" "medium" "Author ($AUTHOR) is not a known bot — human PRs get reviewed"
fi

# --- Determine risk level ---
SKIP_COUNT=$(echo "$FLAGS" | jq '[.[] | select(.risk == "skip")] | length')
HIGH_COUNT=$(echo "$FLAGS" | jq '[.[] | select(.risk == "high")] | length')
MEDIUM_COUNT=$(echo "$FLAGS" | jq '[.[] | select(.risk == "medium")] | length')

if [[ "$SKIP_COUNT" -gt 0 ]]; then
    RISK_LEVEL="skip"
elif [[ "$HIGH_COUNT" -gt 0 ]]; then
    RISK_LEVEL="high"
elif [[ "$MEDIUM_COUNT" -ge 3 ]]; then
    RISK_LEVEL="high"
elif [[ "$MEDIUM_COUNT" -gt 0 ]]; then
    RISK_LEVEL="medium"
else
    RISK_LEVEL="low"
fi

# --- Determine auto-approvable ---
AUTO_APPROVABLE=false
if [[ "$RISK_LEVEL" == "low" ]]; then
    # All low-risk criteria met: no flags, CI passing, bot author, linked issue, first review
    if [[ "$CI_STATUS" == "passing" && "$IS_BOT" == "true" && -n "$LINKED_ISSUE" && "$REVIEW_ROUND" -eq 0 ]]; then
        AUTO_APPROVABLE=true
    fi
fi

# --- Output ---
jq -n \
    --argjson pr "$PR_NUMBER" \
    --arg risk "$RISK_LEVEL" \
    --argjson auto "$AUTO_APPROVABLE" \
    --argjson flags "$FLAGS" \
    --arg author "$AUTHOR" \
    --argjson is_bot "$IS_BOT" \
    --arg ci_status "$CI_STATUS" \
    --argjson review_round "$REVIEW_ROUND" \
    --arg linked_issue "${LINKED_ISSUE:-null}" \
    --argjson lines_changed "$LINES_CHANGED" \
    --argjson additions "$ADDITIONS" \
    --argjson deletions "$DELETIONS" \
    --argjson changed_files "$CHANGED_FILES" \
    --arg file_types "$FILE_TYPES" \
    --argjson sensitive_found "$SENSITIVE_FOUND" \
    --argjson architecture_found "$ARCHITECTURE_FOUND" \
    --argjson deps_changed "$DEPS_CHANGED" \
    --argjson no_tests "$NO_TESTS_FOR_CODE" \
    --arg ts "$CHECKED_AT" \
    --argjson threshold "$DIFF_THRESHOLD" \
    '{
        pr_number: $pr,
        risk_level: $risk,
        auto_approvable: $auto,
        flags: $flags,
        stats: {
            author: $author,
            is_bot: $is_bot,
            ci_status: $ci_status,
            review_round: $review_round,
            linked_issue: (if $linked_issue == "null" then null else ($linked_issue | tonumber) end),
            lines_changed: $lines_changed,
            additions: $additions,
            deletions: $deletions,
            changed_files: $changed_files,
            file_types: $file_types,
            sensitive_files_touched: $sensitive_found,
            architecture_files_touched: $architecture_found,
            dependency_files_changed: $deps_changed,
            no_tests_for_code: $no_tests,
            diff_threshold: $threshold
        },
        timestamp: $ts
    }'
