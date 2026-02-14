#!/bin/bash
# Create a properly named branch from an issue number.
# Usage: ./scripts/create-branch.sh <issue_number> [type]
# type: feat (default) or fix
#
# The branch name is derived from the issue title:
#   feat/issue-42-add-category-filter
#   fix/issue-17-api-returns-500
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "ERROR: Issue number required."
    echo "FIX: Run 'scripts/create-branch.sh <issue_number> [feat|fix]'"
    echo "Example: scripts/create-branch.sh 42"
    exit 1
fi

ISSUE_NUM="$1"
TYPE="${2:-feat}"

if [[ "$TYPE" != "feat" && "$TYPE" != "fix" ]]; then
    echo "ERROR: Branch type must be 'feat' or 'fix', got '$TYPE'"
    echo "FIX: Run 'scripts/create-branch.sh $ISSUE_NUM feat' or 'scripts/create-branch.sh $ISSUE_NUM fix'"
    exit 1
fi

# Fetch issue title from GitHub
TITLE=$(gh issue view "$ISSUE_NUM" --json title --jq '.title' 2>/dev/null)
if [ -z "$TITLE" ]; then
    echo "ERROR: Could not fetch issue #$ISSUE_NUM. Is it a valid issue?"
    echo "FIX: Check 'gh issue list' for open issues."
    exit 1
fi

# Slugify: lowercase, replace non-alphanum with dash, trim dashes, max 50 chars
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)

BRANCH="${TYPE}/issue-${ISSUE_NUM}-${SLUG}"

echo "Creating branch: $BRANCH"
git checkout -b "$BRANCH" main
echo "Branch '$BRANCH' created from main."
echo "You're now on $BRANCH — start implementing!"
