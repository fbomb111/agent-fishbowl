#!/bin/bash
# Shared agent runner — invokes Claude CLI with a role-specific prompt.
# Usage: ./agents/run-agent.sh <role>
# Roles: po, engineer, reviewer, tech-lead, triage, ux, pm, sre
set -euo pipefail

ROLE="${1:-}"
if [ -z "$ROLE" ]; then
    echo "Usage: $0 <role>"
    echo "Roles: po, engineer, reviewer, tech-lead, triage, ux, pm, sre"
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

# --- GitHub App Identity (per-role) ---
# Each role has its own GitHub App for distinct identity on GitHub.
# .env vars: GITHUB_APP_<ROLE>_ID, GITHUB_APP_<ROLE>_INSTALLATION_ID, etc.
ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    ENV_FILE="$HOME/.config/agent-fishbowl/.env"
fi
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
else
    echo "WARNING: No .env found at $PROJECT_ROOT/.env or $HOME/.config/agent-fishbowl/.env"
fi

# Convert role to uppercase for env var lookup (handle hyphens → underscores)
ROLE_UPPER=$(echo "$ROLE" | tr '[:lower:]-' '[:upper:]_')
APP_ID_VAR="GITHUB_APP_${ROLE_UPPER}_ID"
APP_INSTALL_VAR="GITHUB_APP_${ROLE_UPPER}_INSTALLATION_ID"
APP_KEY_VAR="GITHUB_APP_${ROLE_UPPER}_KEY_PATH"
APP_USER_VAR="GITHUB_APP_${ROLE_UPPER}_USER_ID"
APP_BOT_VAR="GITHUB_APP_${ROLE_UPPER}_BOT_NAME"

APP_ID="${!APP_ID_VAR:-}"
APP_INSTALL="${!APP_INSTALL_VAR:-}"
APP_KEY="${!APP_KEY_VAR:-}"
APP_USER_ID="${!APP_USER_VAR:-0}"
APP_BOT_NAME="${!APP_BOT_VAR:-fishbowl-${ROLE}}"

if [ -n "$APP_ID" ] && [ -n "$APP_INSTALL" ] && [ -n "$APP_KEY" ]; then
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/scripts/github-app-token.sh"

    GH_TOKEN=$(get_github_app_token "$APP_ID" "$APP_INSTALL" "$APP_KEY")
    if [ -z "$GH_TOKEN" ] || [ "$GH_TOKEN" = "null" ]; then
        echo "ERROR: Failed to generate GitHub App token for role: $ROLE"
        exit 1
    fi
    export GH_TOKEN

    BOT_DISPLAY="${APP_BOT_NAME}[bot]"
    BOT_EMAIL="${APP_USER_ID}+${APP_BOT_NAME}[bot]@users.noreply.github.com"
    export GIT_AUTHOR_NAME="$BOT_DISPLAY"
    export GIT_AUTHOR_EMAIL="$BOT_EMAIL"
    export GIT_COMMITTER_NAME="$BOT_DISPLAY"
    export GIT_COMMITTER_EMAIL="$BOT_EMAIL"

    echo "GitHub App: $BOT_DISPLAY (role: $ROLE)"
else
    echo "WARNING: No GitHub App for role '$ROLE' — using default identity"
    echo "  Need: ${APP_ID_VAR}, ${APP_INSTALL_VAR}, ${APP_KEY_VAR} in .env"
fi

echo ""
echo "=== Agent Fishbowl: ${ROLE} agent ==="
echo "Prompt: $PROMPT_FILE"
echo "Log: $LOG_FILE"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

cd "$PROJECT_ROOT"

# Use project-level git hooks (pre-commit auto-formats Python)
git config core.hooksPath .githooks

# --- Per-role tool allowlists ---
# Different roles get different tool permissions to prevent scope creep.
# Non-code agents lose Write/Edit to ensure they can't modify application code.
COMMON_TOOLS="Bash(gh:*),Bash(git:*),Bash(cat:*),Read,Glob,Grep"

case "$ROLE" in
    engineer)
        # Full access — implements code changes
        ALLOWED_TOOLS="Bash(gh:*),Bash(git:*),Bash(ruff:*),Bash(npx:*),Bash(pip:*),Bash(scripts/*),Bash(cat:*),Bash(chmod:*),Read,Write,Edit,Glob,Grep"
        ;;
    tech-lead)
        # Can write conventions and lint scripts, but not application code
        ALLOWED_TOOLS="${COMMON_TOOLS},Bash(ruff:*),Bash(npx:*),Bash(pip:*),Bash(scripts/*),Write,Edit"
        ;;
    pm)
        # Strategic agent: reads goals, manages GitHub Project roadmap via gh
        # scripts/* for project-fields.sh and roadmap-status.sh (read-only GitHub data)
        # No Glob/Grep — PM understands product through outcomes, not code
        # No Write/Edit/git — PM doesn't modify codebase files
        ALLOWED_TOOLS="Bash(gh:*),Bash(cat:*),Bash(scripts/*),Read"
        ;;
    sre)
        # Operational agent: monitors health, checks Azure resources, creates issues
        # scripts/* for health-check.sh, workflow-status.sh, find-issues.sh
        # No Write/Edit — SRE doesn't modify code. It reads, monitors, and creates issues.
        ALLOWED_TOOLS="Bash(curl:*),Bash(az:*),Bash(gh:*),Bash(python3:*),Bash(cat:*),Bash(date:*),Bash(scripts/*),Read"
        ;;
    po|reviewer|triage|ux)
        # Read-only + GitHub CLI — no file editing
        ALLOWED_TOOLS="${COMMON_TOOLS},Bash(scripts/*)"
        ;;
    *)
        # Fallback: read-only + GitHub CLI
        ALLOWED_TOOLS="${COMMON_TOOLS}"
        ;;
esac

echo "Tools: ${ROLE} allowlist"

# Run Claude in non-interactive mode with the role prompt.
# -p: pass prompt directly (not via stdin)
# --print: non-interactive, output only
# CLAUDE.md is loaded automatically by Claude Code.
claude --print \
    --allowedTools "$ALLOWED_TOOLS" \
    -p "$(cat "$PROMPT_FILE")" \
    2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=== ${ROLE} agent finished (exit: $EXIT_CODE) ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

exit $EXIT_CODE
