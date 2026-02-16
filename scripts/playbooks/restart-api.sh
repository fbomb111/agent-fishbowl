#!/bin/bash
# Playbook: restart-api — Restart the Container App when API is unhealthy/unreachable.
#
# Contract:
#   Input:  HEALTH_JSON env var (health-check output, may be empty for alert-triggered runs)
#   Output: exit 0 = resolved, exit 1 = needs escalation
#   Stdout: human-readable log of actions taken
#
# Steps:
#   1. Get the active revision name
#   2. Restart the active revision
#   3. Wait for container to come up
#   4. Verify health endpoint responds 200
set -euo pipefail

CONTAINER_APP="ca-agent-fishbowl-api"
RESOURCE_GROUP="rg-agent-fishbowl"
HEALTH_URL="https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/health"
WAIT_SECONDS=30
MAX_RETRIES=3

log() { echo "[playbook:restart-api $(date -u +%H:%M:%S)] $*"; }

# Step 1: Get active revision
log "Getting active revision for $CONTAINER_APP"
REVISION=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?properties.active].name | [0]" \
    -o tsv 2>/dev/null || echo "")

if [[ -z "$REVISION" ]]; then
    log "ERROR: Could not find active revision"
    exit 1
fi
log "Active revision: $REVISION"

# Step 2: Restart the revision
log "Restarting revision $REVISION"
if ! az containerapp revision restart \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$REVISION" 2>/dev/null; then
    log "ERROR: Failed to restart revision"
    exit 1
fi
log "Restart command sent"

# Step 3-4: Wait and verify health
for attempt in $(seq 1 $MAX_RETRIES); do
    log "Waiting ${WAIT_SECONDS}s for container to come up (attempt $attempt/$MAX_RETRIES)"
    sleep "$WAIT_SECONDS"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 15 "$HEALTH_URL" 2>/dev/null || echo "000")
    log "Health check: HTTP $HTTP_CODE"

    if [[ "$HTTP_CODE" == "200" ]]; then
        log "API is healthy after restart"
        exit 0
    fi
done

log "API still unhealthy after $MAX_RETRIES attempts (last HTTP: $HTTP_CODE)"
exit 1
