#!/bin/bash
# Run all quality checks (ruff + pytest + tsc + eslint + convention lint + flow validation)
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

# --- Python tests (pytest) ---
echo ""
echo "▸ pytest (Python tests)"
if ! command -v pytest &>/dev/null && ! python -m pytest --version &>/dev/null 2>&1; then
    echo "  SKIP: pytest not installed"
    echo "  FIX: Run 'pip install pytest' or install from requirements.txt."
else
    if ! (cd "$PROJECT_ROOT/api" && python -m pytest tests/ -x -q --tb=short); then
        FAILED=1
        echo "  FAIL: Tests failed"
        echo "  FIX: Read failures above, fix the code, run 'cd api && pytest tests/ -x' again."
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

# --- Flow validation ---
echo ""
echo "▸ Flow validation"
if [ -f "$PROJECT_ROOT/scripts/validate-flow.py" ]; then
    if ! python "$PROJECT_ROOT/scripts/validate-flow.py" --validate; then
        FAILED=1
        echo "  FAIL: Flow graph validation failed"
        echo "  FIX: Read errors above, fix config/agent-flow.yaml."
    else
        echo "  PASS"
    fi
else
    echo "  SKIP: validate-flow.py not found"
fi

# --- Shell script lint (shellcheck) ---
echo ""
echo "▸ shellcheck (Shell scripts)"
if command -v shellcheck &>/dev/null; then
    if ! shellcheck "$PROJECT_ROOT"/scripts/*.sh; then
        FAILED=1
        echo "  FAIL: shellcheck found issues"
        echo "  FIX: Read errors above, fix the reported shell script issues."
    else
        echo "  PASS"
    fi
else
    echo "  SKIP: shellcheck not installed"
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
