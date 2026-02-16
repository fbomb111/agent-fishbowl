#!/bin/bash
# Playbook: retrigger-ingest — Re-trigger the ingestion workflow when articles are stale.
#
# Contract:
#   Input:  HEALTH_JSON env var (health-check output, may be empty for alert-triggered runs)
#   Output: exit 0 = workflow triggered, exit 1 = failed to trigger
#   Stdout: human-readable log of actions taken
#
# This playbook does NOT wait for ingestion to complete (it takes several minutes).
# The next health check or alert will verify freshness.
set -euo pipefail

INGEST_WORKFLOW="ingest.yml"

log() { echo "[playbook:retrigger-ingest $(date -u +%H:%M:%S)] $*"; }

# Check if ingest workflow recently failed (don't re-trigger a broken pipeline)
log "Checking recent ingest workflow status"
LAST_CONCLUSION=$(gh run list --workflow="$INGEST_WORKFLOW" --limit 1 --json conclusion --jq '.[0].conclusion' 2>/dev/null || echo "unknown")

if [[ "$LAST_CONCLUSION" == "failure" ]]; then
    log "Last ingest run FAILED — not re-triggering a broken pipeline"
    log "This needs engineer investigation"
    exit 1
fi

# Trigger the workflow
log "Re-triggering $INGEST_WORKFLOW (last run: $LAST_CONCLUSION)"
if ! gh workflow run "$INGEST_WORKFLOW" 2>/dev/null; then
    log "ERROR: Failed to trigger workflow"
    exit 1
fi

log "Ingest workflow triggered successfully"
exit 0
