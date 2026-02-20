#!/usr/bin/env bash
# Delete local branches whose remote tracking branch has been deleted.
# Safe: only targets branches marked [gone] in git branch -vv output.

set -euo pipefail

git fetch --prune

gone_branches=$(git branch -vv | grep ': gone]' | awk '{print $1}' || true)

if [ -z "$gone_branches" ]; then
    echo "No stale branches to clean up."
    exit 0
fi

echo "Deleting merged branches with deleted remotes:"
echo "$gone_branches"
echo ""

for branch in $gone_branches; do
    git branch -D "$branch"
done

echo "Done. Cleaned $(echo "$gone_branches" | wc -l) branches."
