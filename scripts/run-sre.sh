#!/bin/bash
# SRE controller: routes alerts and health checks to playbooks or Claude agent.
#
# Modes (set via SRE_MODE env var):
#   alert   — Triggered by Azure Monitor via repository_dispatch.
#             ALERT_CONTEXT contains the alert payload JSON.
#             Routes to matching playbook, falls through to Claude if no match.
#   summary — Manual trigger or default. Runs full health check,
#             tries playbooks for issues found, escalates to Claude for unknowns.
#             Exits early if everything is GREEN.
#
# Usage:
#   SRE_MODE=alert ALERT_CONTEXT='{"alertRule":"5xx",...}' ./scripts/run-sre.sh
#   SRE_MODE=summary ./scripts/run-sre.sh
#   ./scripts/run-sre.sh   # defaults to summary
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MODE="${SRE_MODE:-summary}"
ALERT="${ALERT_CONTEXT:-}"
if [[ -z "$ALERT" ]]; then ALERT="{}"; fi

log() { echo "[sre $(date -u +%H:%M:%S)] $*"; }

# --- Playbook routing (health-check based) ---
# Matches health-check.sh JSON output to a playbook script.
# Returns 0 if playbook resolved the issue, 1 if escalation needed.
try_playbook() {
    local health_json="$1"
    local api_status ingest_status

    api_status=$(echo "$health_json" | jq -r '.api.status // "skipped"')
    ingest_status=$(echo "$health_json" | jq -r '.ingestion.status // "skipped"')

    if [[ "$api_status" == "unreachable" || "$api_status" == "unhealthy" ]]; then
        log "API is $api_status — running restart-api playbook"
        if HEALTH_JSON="$health_json" "$SCRIPT_DIR/playbooks/restart-api.sh"; then
            log "Playbook restart-api resolved the issue"
            return 0
        fi
        log "Playbook restart-api failed — escalating to Claude"
        return 1
    fi

    if [[ "$ingest_status" == "stale" || "$ingest_status" == "critical" ]]; then
        log "Ingestion is $ingest_status — running retrigger-ingest playbook"
        if HEALTH_JSON="$health_json" "$SCRIPT_DIR/playbooks/retrigger-ingest.sh"; then
            log "Playbook retrigger-ingest completed"
            return 0
        fi
        log "Playbook retrigger-ingest failed — escalating to Claude"
        return 1
    fi

    log "No matching playbook for current health state"
    return 1
}

# --- Playbook routing (alert-based) ---
# Matches Azure Monitor alert payloads to a playbook script.
# Returns 0 if playbook resolved the issue, 1 if escalation needed.
try_playbook_for_alert() {
    local alert_json="$1"
    local alert_rule

    alert_rule=$(echo "$alert_json" | jq -r '.alertRule // .data.essentials.alertRule // "unknown"')

    case "$alert_rule" in
        *5xx*|*error*|*availability*)
            log "Alert '$alert_rule' — running restart-api playbook"
            if HEALTH_JSON="{}" "$SCRIPT_DIR/playbooks/restart-api.sh"; then
                log "Playbook restart-api resolved the issue"
                return 0
            fi
            log "Playbook restart-api failed — escalating to Claude"
            return 1
            ;;
        *ingest*|*stale*)
            log "Alert '$alert_rule' — running retrigger-ingest playbook"
            if HEALTH_JSON="{}" "$SCRIPT_DIR/playbooks/retrigger-ingest.sh"; then
                log "Playbook retrigger-ingest completed"
                return 0
            fi
            log "Playbook retrigger-ingest failed — escalating to Claude"
            return 1
            ;;
    esac

    log "No matching playbook for alert: $alert_rule"
    return 1
}

# --- Claude escalation ---
# Invokes the full SRE agent for investigation.
run_claude() {
    log "Escalating to Claude SRE agent"
    if ./agents/sre.sh; then
        log "Claude SRE agent completed successfully"
    else
        log "Claude SRE agent exited with error (exit: $?)"
    fi
}

# --- Main ---
log "=== Agent Fishbowl: SRE Controller (mode: $MODE) ==="
echo ""

case "$MODE" in
    alert)
        log "Alert payload: $(echo "$ALERT" | jq -c '.' 2>/dev/null || echo "$ALERT")"
        echo ""
        if try_playbook_for_alert "$ALERT"; then
            log "Alert handled by playbook"
        else
            export ALERT_CONTEXT="$ALERT"
            run_claude
        fi
        ;;
    summary)
        log "Running full system health check"
        health_json=$("$SCRIPT_DIR/health-check.sh")
        overall=$(echo "$health_json" | jq -r '.overall')
        log "Health status: $overall"
        echo ""

        case "$overall" in
            GREEN)
                log "All systems healthy. No action needed."
                ;;
            *)
                log "Issues detected — attempting playbooks"
                if try_playbook "$health_json"; then
                    log "Issues resolved by playbook"
                else
                    export ALERT_CONTEXT="$health_json"
                    run_claude
                fi
                ;;
        esac
        ;;
    *)
        log "ERROR: Unknown mode '$MODE'. Use 'alert' or 'summary'."
        exit 1
        ;;
esac

echo ""
log "=== SRE controller complete ==="
