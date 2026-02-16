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
ensure_label "priority/low"     "e4e669" "Low priority — do when convenient"

# Type labels
ensure_label "type/feature"     "0e8a16" "New functionality"
ensure_label "type/bug"         "d73a4a" "Something broken"
ensure_label "type/chore"       "cccccc" "Maintenance, CI, docs"
ensure_label "type/refactor"    "7057ff" "Code refactoring or architecture improvement"
ensure_label "type/ux"          "f9d0c4" "User experience improvement"

# Source labels (which agent created the intake)
ensure_label "source/roadmap"          "c5def5" "From product roadmap"
ensure_label "source/tech-lead"        "d4c5f9" "From tech lead code review"
ensure_label "source/ux-review"        "f9d0c4" "From UX agent review"
ensure_label "source/triage"           "c2e0c6" "Validated by triage agent"
ensure_label "source/reviewer-backlog" "fef2c0" "Rework from closed PR"
ensure_label "source/sre"              "d73a4a" "From SRE monitoring"

# Status labels
ensure_label "status/in-progress" "fef2c0" "An agent is working on this"
ensure_label "status/blocked"     "e4e669" "Cannot proceed — needs human input"
ensure_label "status/needs-info"  "e4e669" "Needs more information from reporter"

# Review labels
ensure_label "review/approved"           "0e8a16" "Reviewer approved this PR"
ensure_label "review/changes-requested"  "e4e669" "Reviewer requested changes"

# PM feedback labels
ensure_label "pm/misaligned"    "d876e3" "PM flagged: issue misinterprets roadmap intent"

# Harness labels
ensure_label "harness/request"  "ff9800" "Agent needs a harness capability (tool, permission, config)"

# Meta labels
ensure_label "agent-created"    "bfdadc" "Created by an agent (not human)"

echo ""
echo "=== Labels setup complete ==="
