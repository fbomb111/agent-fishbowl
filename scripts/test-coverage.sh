#!/bin/bash
# Run test suite with coverage reporting.
# Outputs: pass/fail counts, coverage summary, and per-file coverage.
# Installs deps if needed (safe to run on fresh checkout).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/api"

# --- Setup ---
echo "=== Test Coverage Report ==="
echo ""

# Activate venv if available
if [ -f "$API_DIR/.venv/bin/activate" ]; then
    source "$API_DIR/.venv/bin/activate"
fi

# Ensure deps are installed (idempotent, fast if already installed)
if ! python -c "import pytest_cov" &>/dev/null 2>&1; then
    echo "▸ Installing test dependencies..."
    pip install -q -r "$API_DIR/requirements.txt" 2>&1 | tail -3
    echo ""
fi

# --- Backend (pytest + coverage) ---
echo "▸ Backend tests (pytest --cov)"
echo ""

cd "$API_DIR"
python -m pytest tests/ \
    --cov \
    --cov-report=term-missing:skip-covered \
    -q --tb=short 2>&1

BACKEND_EXIT=$?

echo ""

# --- Frontend (vitest) ---
echo "▸ Frontend tests (vitest)"
echo ""

cd "$PROJECT_ROOT/frontend"
if npx vitest run --reporter=verbose 2>&1; then
    FRONTEND_EXIT=0
else
    FRONTEND_EXIT=$?
fi

echo ""

# --- Summary ---
echo "=== Summary ==="
if [ $BACKEND_EXIT -eq 0 ]; then
    echo "  Backend:  PASS"
else
    echo "  Backend:  FAIL (exit $BACKEND_EXIT)"
fi
if [ $FRONTEND_EXIT -eq 0 ]; then
    echo "  Frontend: PASS"
else
    echo "  Frontend: FAIL (exit $FRONTEND_EXIT)"
fi

if [ $BACKEND_EXIT -ne 0 ] || [ $FRONTEND_EXIT -ne 0 ]; then
    exit 1
fi
exit 0
