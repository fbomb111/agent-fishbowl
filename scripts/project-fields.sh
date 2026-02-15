#!/bin/bash
# project-fields.sh — GitHub Project field ID mapping for Agent Fishbowl agents.
# Returns a clean name→ID mapping for project fields and their options.
# Outputs JSON to stdout. Uses GH_TOKEN from environment.
set -euo pipefail

# --- Defaults ---
PROJECT=1
OWNER="YourMoveLabs"

# --- Help ---
usage() {
    cat <<'EOF'
Usage: scripts/project-fields.sh [OPTIONS]

Get GitHub Project field IDs and option IDs in a clean mapping.

Options:
  --project N           Project number (default: 1)
  --owner OWNER         Org owner (default: YourMoveLabs)
  --help                Show this help

Examples:
  # Get field mapping for default project
  scripts/project-fields.sh

  # Get field mapping and extract Priority P1 option ID
  scripts/project-fields.sh | jq '.fields.Priority.options["P1 - Must Have"]'

Output: JSON object with project_id and fields mapping (field name → {id, options}).
         Options map option name → option ID for single-select fields.
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project) PROJECT="$2"; shift 2 ;;
        --owner) OWNER="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Fetch field list ---
RAW=$(gh project field-list "$PROJECT" --owner "$OWNER" --format json 2>/dev/null)

if [[ -z "$RAW" ]] || [[ "$RAW" == "null" ]]; then
    echo '{"error": "Failed to fetch project fields"}' >&2
    exit 1
fi

# --- Fetch project ID ---
# gh project view returns project metadata including the node ID
PROJECT_VIEW=$(gh project view "$PROJECT" --owner "$OWNER" --format json 2>/dev/null || echo '{}')
PROJECT_ID=$(echo "$PROJECT_VIEW" | jq -r '.id // "unknown"')

# --- Transform into clean mapping ---
# Input format from gh: { "fields": [ { "name": "Priority", "id": "PVTSSF_...", "type": "ProjectV2SingleSelectField", "options": [...] }, ... ] }
# Output format: { "project_id": "...", "fields": { "Priority": { "id": "...", "options": { "P1 - Must Have": "id", ... } } } }
echo "$RAW" | jq --arg pid "$PROJECT_ID" '{
    project_id: $pid,
    fields: (
        .fields
        | map(select(.type == "ProjectV2SingleSelectField"))
        | map({
            key: .name,
            value: {
                id: .id,
                options: (
                    .options
                    | map({key: .name, value: .id})
                    | from_entries
                )
            }
        })
        | from_entries
    )
}'
