#!/bin/bash
# Check project conventions that ruff/eslint don't cover.
# Error messages are written to be read by AI agents — each includes a FIX instruction.
set -uo pipefail

FAILED=0

# --- Branch name convention ---
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

if [ -n "$BRANCH" ] && [ "$BRANCH" != "main" ]; then
    if ! echo "$BRANCH" | grep -qE '^(feat|fix|chore)/issue-[0-9]+-'; then
        echo "ERROR: Branch name '$BRANCH' doesn't match the required pattern."
        echo "  PATTERN: feat/issue-{N}-description, fix/issue-{N}-description, or chore/issue-{N}-description"
        echo "  FIX: Create a new branch with: scripts/create-branch.sh <issue_number> [feat|fix]"
        echo "  Example: scripts/create-branch.sh 42 feat"
        FAILED=1
    fi
fi

# --- PR description must reference an issue (only check if we're in a PR context) ---
# This runs during `gh pr create` validation or CI — skip if no PR context
if [ -n "${GITHUB_HEAD_REF:-}" ] || [ -n "${PR_BODY:-}" ]; then
    BODY="${PR_BODY:-}"
    if [ -z "$BODY" ] && command -v gh &>/dev/null; then
        BODY=$(gh pr view --json body --jq '.body' 2>/dev/null || echo "")
    fi
    if [ -n "$BODY" ]; then
        if ! echo "$BODY" | grep -qiE '(closes|fixes|resolves)\s+#[0-9]+'; then
            echo "ERROR: PR description must reference an issue."
            echo "  PATTERN: Include 'Closes #N', 'Fixes #N', or 'Resolves #N' in the PR body."
            echo "  FIX: Edit the PR description to add 'Closes #<issue_number>' on its own line."
            FAILED=1
        fi
    fi
fi

# --- File size guard (agents sometimes generate bloated files) ---
MAX_LINES=500
LARGE_FILES=$(find api/ frontend/src/ -path 'api/.venv' -prune -o -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" \) -exec awk -v max="$MAX_LINES" -v f="{}" 'END { if (NR > max) print f " (" NR " lines)" }' {} \; 2>/dev/null)

if [ -n "$LARGE_FILES" ]; then
    echo "WARNING: Files exceeding $MAX_LINES lines:"
    echo "$LARGE_FILES" | while read -r line; do echo "  $line"; done
    echo "  GUIDELINE: Large files are harder to maintain. Consider splitting into smaller modules."
    echo "  This is a warning, not a failure."
fi

if [ $FAILED -ne 0 ]; then
    exit 1
else
    echo "  PASS (conventions)"
    exit 0
fi
