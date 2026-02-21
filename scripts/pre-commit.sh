#!/bin/bash
# pre-commit.sh — Auto-fix + quality gate + commit.
# Usage: scripts/pre-commit.sh "type(scope): description (#N)"
# Only commits if ALL checks pass.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MSG="${1:-}"
if [ -z "$MSG" ]; then
    echo "Usage: scripts/pre-commit.sh \"commit message\""
    exit 1
fi

# Phase 1: Auto-fix
echo "=== Auto-fix Phase ==="
if command -v ruff &>/dev/null; then
    ruff check --fix "$PROJECT_ROOT/api/" 2>/dev/null || true
    ruff format "$PROJECT_ROOT/api/" 2>/dev/null || true
fi
if [ -d "$PROJECT_ROOT/frontend" ]; then
    (cd "$PROJECT_ROOT/frontend" && npx eslint --fix . 2>/dev/null) || true
fi

# Stage auto-fix changes
git add -A

# Phase 2: Quality gate
echo ""
echo "=== Quality Gate ==="
if ! "$SCRIPT_DIR/run-checks.sh"; then
    echo ""
    echo "=== COMMIT BLOCKED — fix issues above ==="
    exit 1
fi

# Phase 3: Commit (only reached if all checks pass)
echo ""
echo "=== Committing ==="
git add -A
PRECOMMIT_WRAPPER=1 git commit -m "$MSG"
echo "=== Done ==="
