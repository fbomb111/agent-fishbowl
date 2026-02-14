#!/bin/bash
# Shared agent runner — invokes Claude CLI with a role-specific prompt.
# Usage: ./agents/run-agent.sh <role>
# Roles: engineer, pm, reviewer, sre
set -euo pipefail

ROLE="${1:-}"
if [ -z "$ROLE" ]; then
    echo "Usage: $0 <role>"
    echo "Roles: engineer, pm, reviewer, sre"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROMPT_FILE="$SCRIPT_DIR/prompts/${ROLE}.md"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/${ROLE}-$(date +%Y%m%d-%H%M%S).log"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE"
    echo "Available roles:"
    ls "$SCRIPT_DIR/prompts/"*.md 2>/dev/null | xargs -I {} basename {} .md
    exit 1
fi

mkdir -p "$LOG_DIR"

echo "=== Agent Fishbowl: ${ROLE} agent ==="
echo "Prompt: $PROMPT_FILE"
echo "Log: $LOG_FILE"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

cd "$PROJECT_ROOT"

# Run Claude in non-interactive mode with the role prompt.
# --print: non-interactive, output only
# --prompt-file: role-specific instructions
# CLAUDE.md is loaded automatically by Claude Code.
claude --print \
    --prompt-file "$PROMPT_FILE" \
    --allowedTools "Bash(scripts/*),Bash(gh *),Bash(git *),Bash(ruff *),Bash(npx *),Read,Write,Edit,Glob,Grep,Skill" \
    2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=== ${ROLE} agent finished (exit: $EXIT_CODE) ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

exit $EXIT_CODE
