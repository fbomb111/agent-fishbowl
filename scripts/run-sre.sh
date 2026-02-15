#!/bin/bash
# SRE health check: monitors system health, files issues for problems
# Run every 2-4 hours to keep response times low for production issues.
#
# Usage: ./scripts/run-sre.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

log() { echo "[sre $(date -u +%H:%M:%S)] $*"; }

log "=== Agent Fishbowl: SRE Health Check ==="
echo ""

# Quick pre-flight: verify the API endpoint is reachable before burning an agent run
API_URL="https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$API_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "000" ]; then
    log "WARNING: API unreachable (connection failed) — running SRE agent for full diagnostics"
elif [ "$HTTP_CODE" != "200" ]; then
    log "WARNING: API returned HTTP $HTTP_CODE — running SRE agent for full diagnostics"
else
    log "API responding (HTTP 200) — running SRE agent for full health check"
fi

echo ""

if ./agents/sre.sh; then
    log "  SRE agent completed successfully"
else
    log "  SRE agent exited with error"
fi

echo ""
log "=== SRE health check complete ==="
