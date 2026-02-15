#!/bin/bash
# Strategic review: PM evaluates goals and evolves the roadmap
# Run weekly to keep the roadmap aligned with strategic goals.
#
# Usage: ./scripts/run-strategic.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

log() { echo "[strategic $(date -u +%H:%M:%S)] $*"; }

log "=== Agent Fishbowl: Strategic Review ==="
echo ""

# Ensure goals.md exists — the PM agent needs it
if [ ! -f config/goals.md ]; then
    log "ERROR: config/goals.md not found — PM agent cannot run without strategic goals"
    exit 1
fi

log "Running PM agent — evaluating goals and roadmap alignment"
if ./agents/pm.sh; then
    log "  PM agent completed successfully"
else
    log "  PM agent exited with error"
fi

echo ""
log "=== Strategic review complete ==="
