#!/usr/bin/env bash
# Bump the harness version across all agent workflows.
#
# Usage: scripts/bump-harness.sh v1.3.0
#
# Updates:
#   1. config/agent-flow.yaml  (global harness_ref)
#   2. .github/workflows/*.yml (all YourMoveLabs/agent-harness@xxx references)
#   3. docs/agent-flow.md      (regenerated diagram)
#
# After running, review changes with `git diff` and commit.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v1.3.0"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (vX.Y.Z or 'main')
if [[ ! "$NEW_VERSION" =~ ^(v[0-9]+\.[0-9]+\.[0-9]+|main)$ ]]; then
    echo "Error: Version must be vX.Y.Z (e.g., v1.3.0) or 'main'"
    exit 1
fi

NEW_REF="@${NEW_VERSION}"

echo "Bumping harness to ${NEW_REF}..."
echo ""

# 1. Update agent-flow.yaml global harness_ref
echo "1. Updating config/agent-flow.yaml..."
sed -i "s|^harness_ref: \"@[^\"]*\"|harness_ref: \"${NEW_REF}\"|" \
    "${REPO_ROOT}/config/agent-flow.yaml"

# 2. Update all workflow files
echo "2. Updating workflow files..."
count=0
for wf in "${REPO_ROOT}"/.github/workflows/*.yml; do
    if grep -q "YourMoveLabs/agent-harness@" "$wf"; then
        sed -i "s|YourMoveLabs/agent-harness@[^ ]*|YourMoveLabs/agent-harness@${NEW_VERSION}|g" "$wf"
        echo "   $(basename "$wf")"
        count=$((count + 1))
    fi
done
echo "   Updated ${count} workflow files."

# 3. Regenerate diagram
echo "3. Regenerating docs/agent-flow.md..."
python3 "${REPO_ROOT}/scripts/validate-flow.py" --mermaid -o "${REPO_ROOT}/docs/agent-flow.md"

# 4. Validate
echo "4. Running validation..."
echo ""
python3 "${REPO_ROOT}/scripts/validate-flow.py" --validate

echo ""
echo "Done. Review changes with: git diff"
