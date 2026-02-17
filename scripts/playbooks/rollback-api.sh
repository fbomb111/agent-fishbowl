#!/bin/bash
# Playbook: rollback-api — Roll back API to previous Container App revision.
#
# Contract:
#   Input:  None required (auto-detects previous revision)
#   Output: exit 0 = rolled back successfully, exit 1 = needs escalation
#   Stdout: human-readable log of actions taken
#
# Steps:
#   1. List revisions sorted by creation time
#   2. Identify the previous (second-most-recent active) revision
#   3. Route 100% traffic to the previous revision
#   4. Verify health endpoint responds 200
set -euo pipefail

CONTAINER_APP="ca-agent-fishbowl-api"
RESOURCE_GROUP="rg-agent-fishbowl"
HEALTH_URL="https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/health"
WAIT_SECONDS=20
MAX_RETRIES=3

log() { echo "[playbook:rollback-api $(date -u +%H:%M:%S)] $*"; }

# Step 1-2: Find previous revision
log "Finding previous revision for $CONTAINER_APP"
PREV=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "sort_by([?properties.active], &properties.createdTime)[-2].name" \
    -o tsv 2>/dev/null || echo "")

if [[ -z "$PREV" ]]; then
    log "ERROR: No previous revision found — cannot rollback"
    exit 1
fi
log "Previous revision: $PREV"

# Step 3: Route traffic to previous revision
log "Routing 100% traffic to $PREV"
if ! az containerapp ingress traffic set \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision-weight "$PREV=100" 2>/dev/null; then
    log "ERROR: Failed to set traffic weight"
    exit 1
fi
log "Traffic routed to $PREV"

# Step 4: Verify health
for attempt in $(seq 1 $MAX_RETRIES); do
    log "Waiting ${WAIT_SECONDS}s for rollback to stabilize (attempt $attempt/$MAX_RETRIES)"
    sleep "$WAIT_SECONDS"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 15 "$HEALTH_URL" 2>/dev/null || echo "000")
    log "Health check: HTTP $HTTP_CODE"

    if [[ "$HTTP_CODE" == "200" ]]; then
        log "API is healthy after rollback to $PREV"
        exit 0
    fi
done

log "API still unhealthy after rollback to $PREV (last HTTP: $HTTP_CODE)"
exit 1
