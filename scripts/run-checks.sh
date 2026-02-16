#!/bin/bash
# Run all quality checks (ruff + tsc + eslint + convention lint)
# Exit codes: 0 = all pass, 1 = failures found
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FAILED=0

# Activate Python venv if it exists (for ruff)
if [ -f "$PROJECT_ROOT/api/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/api/.venv/bin/activate"
fi

echo "=== Agent Fishbowl Quality Checks ==="
echo ""

# --- Python (ruff) ---
echo "▸ ruff check (Python lint)"
if ! command -v ruff &>/dev/null; then
    echo "  SKIP: ruff not installed"
    echo "  FIX: Run 'pip install ruff' or create a venv in api/.venv with ruff installed."
else
    if ! ruff check "$PROJECT_ROOT/api/"; then
        FAILED=1
        echo "  FAIL: ruff check found issues"
        echo "  FIX: Run 'ruff check --fix api/' to auto-fix, then review changes."
    else
        echo "  PASS"
    fi

    echo ""
    echo "▸ ruff format --check (Python formatting)"
    if ! ruff format --check "$PROJECT_ROOT/api/"; then
        FAILED=1
        echo "  FAIL: ruff format found unformatted files"
        echo "  FIX: Run 'ruff format api/' to auto-format."
    else
        echo "  PASS"
    fi
fi

# --- TypeScript (tsc + eslint) ---
echo ""
echo "▸ tsc --noEmit (TypeScript typecheck)"
if ! (cd "$PROJECT_ROOT/frontend" && npx tsc --noEmit); then
    FAILED=1
    echo "  FAIL: TypeScript type errors found"
    echo "  FIX: Read the error messages above, fix type issues in the reported files."
else
    echo "  PASS"
fi

echo ""
echo "▸ eslint (TypeScript lint)"
if ! (cd "$PROJECT_ROOT/frontend" && npx eslint .); then
    FAILED=1
    echo "  FAIL: eslint found issues"
    echo "  FIX: Run 'cd frontend && npx eslint --fix .' to auto-fix."
else
    echo "  PASS"
fi

# --- Convention checks ---
echo ""
echo "▸ Convention lint"
LINT_SCRIPT="${HARNESS_ROOT:-$SCRIPT_DIR/../.harness}/scripts/lint-conventions.sh"
if [ -f "$LINT_SCRIPT" ]; then
    if ! bash "$LINT_SCRIPT"; then
        FAILED=1
    fi
else
    echo "  SKIP: lint-conventions.sh not found (run via harness or set HARNESS_ROOT)"
fi

echo ""
if [ $FAILED -ne 0 ]; then
    echo "=== SOME CHECKS FAILED ==="
    echo "Fix the issues above before opening a PR."
    exit 1
else
    echo "=== ALL CHECKS PASSED ==="
    exit 0
fi
