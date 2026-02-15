#!/bin/bash
# Triage: process human-created issues
# Run every 12-24 hours to keep response times low for external contributors.
#
# Usage: ./scripts/run-triage.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

log() { echo "[triage $(date -u +%H:%M:%S)] $*"; }

log "=== Agent Fishbowl: Triage ==="
echo ""

# Check if there are any unprocessed human issues before running the agent
HUMAN_ISSUES=$(gh issue list --state open --json number,labels \
    --jq '[.[] | select(
        ([.labels[].name] | index("agent-created") | not) and
        ([.labels[].name] | map(startswith("source/")) | any | not)
    )] | length')

if [ "$HUMAN_ISSUES" -gt 0 ]; then
    log "Found $HUMAN_ISSUES unprocessed human issue(s) — running triage agent"
    if ./agents/triage.sh; then
        log "  Triage agent completed successfully"
    else
        log "  Triage agent exited with error"
    fi
else
    log "No unprocessed human issues — skipping triage"
fi

echo ""
log "=== Triage complete ==="
