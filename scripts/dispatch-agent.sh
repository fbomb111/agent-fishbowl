#!/bin/bash
# Emit a repository_dispatch event to trigger a downstream agent workflow.
# Usage: scripts/dispatch-agent.sh <event_type> [payload_json]
#
# Event types:
#   agent-po-complete       -- PO finished triaging, engineer should pick up work
#   agent-reviewer-feedback -- Reviewer requested changes, engineer should fix
#   agent-pm-feedback       -- PM flagged misalignment, PO should re-scope
set -euo pipefail

EVENT_TYPE="${1:?Usage: dispatch-agent.sh <event_type> [payload_json]}"
PAYLOAD="${2:-'{}'}"

REPO="${GITHUB_REPOSITORY:-YourMoveLabs/agent-fishbowl}"

echo "Dispatching event: $EVENT_TYPE -> $REPO"
echo "Payload: $PAYLOAD"

gh api "repos/$REPO/dispatches" \
  --input - <<EOF
{"event_type": "$EVENT_TYPE", "client_payload": $PAYLOAD}
EOF

echo "Dispatched successfully"
