#!/bin/bash
# Create/update GitHub labels for the agent-fishbowl project.
# Idempotent — safe to run multiple times.
set -euo pipefail

echo "=== Setting up GitHub labels ==="

# Helper: create or update a label
ensure_label() {
    local name="$1"
    local color="$2"
    local description="$3"

    if gh label list --json name --jq '.[].name' | grep -qx "$name"; then
        gh label edit "$name" --color "$color" --description "$description"
        echo "  Updated: $name"
    else
        gh label create "$name" --color "$color" --description "$description"
        echo "  Created: $name"
    fi
}

# Domain labels (which agent handles it)
ensure_label "agent/frontend"   "1d76db" "Frontend work (React, Tailwind, pages)"
ensure_label "agent/backend"    "0075ca" "Backend work (FastAPI, services, models)"
ensure_label "agent/ingestion"  "6f42c1" "Article ingestion and processing"

# Priority labels
ensure_label "priority/high"    "d73a4a" "Do first"
ensure_label "priority/medium"  "fbca04" "Do after high-priority items"

# Type labels
ensure_label "type/feature"     "0e8a16" "New functionality"
ensure_label "type/bug"         "d73a4a" "Something broken"
ensure_label "type/chore"       "cccccc" "Maintenance, CI, docs"

# Status labels
ensure_label "status/in-progress" "fef2c0" "An agent is working on this"
ensure_label "status/blocked"     "e4e669" "Cannot proceed — needs human input"

# Review labels
ensure_label "review/approved"           "0e8a16" "Reviewer approved this PR"
ensure_label "review/changes-requested"  "e4e669" "Reviewer requested changes"

# Meta labels
ensure_label "agent-created"    "bfdadc" "Created by an agent (not human)"

echo ""
echo "=== Labels setup complete ==="
