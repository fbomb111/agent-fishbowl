#!/bin/bash
# Full development loop: PM → Engineer → Reviewer → (feedback) → merge
# Run once for a complete cycle, or schedule via cron for continuous operation.
#
# Usage: ./scripts/run-loop.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MAX_ITERATIONS=5   # Safety valve — max total agent invocations per loop
ITERATION=0

log() { echo "[loop $(date -u +%H:%M:%S)] $*"; }

log "=== Agent Fishbowl: Full Development Loop ==="
log "Max iterations: $MAX_ITERATIONS"
echo ""

# ── Phase 1: PM creates issues (if backlog is thin) ──────────────────────────
log "Phase 1: PM agent — checking backlog"
OPEN_ISSUES=$(gh issue list --state open --json number --jq 'length')

if [ "$OPEN_ISSUES" -lt 3 ]; then
    log "  Backlog has $OPEN_ISSUES open issues (< 3) — running PM agent"
    if ./agents/pm.sh; then
        log "  PM agent completed successfully"
    else
        log "  PM agent exited with error (non-fatal, continuing)"
    fi
    ITERATION=$((ITERATION + 1))
else
    log "  Backlog has $OPEN_ISSUES open issues — skipping PM"
fi

echo ""

# ── Phase 2: Engineer picks up work ──────────────────────────────────────────
# Engineer checks for review feedback first (Step 0 in prompt), then new issues
NEEDS_FEEDBACK=$(gh pr list --state open --author "@me" --json reviewDecision \
    --jq '[.[] | select(.reviewDecision=="CHANGES_REQUESTED")] | length' 2>/dev/null || echo "0")

UNASSIGNED=$(gh issue list --state open --json assignees \
    --jq '[.[] | select(.assignees | length == 0)] | length' 2>/dev/null || echo "0")

if [ "$NEEDS_FEEDBACK" -gt 0 ] || [ "$UNASSIGNED" -gt 0 ]; then
    log "Phase 2: Engineer agent (feedback PRs: $NEEDS_FEEDBACK, unassigned issues: $UNASSIGNED)"
    if ./agents/engineer.sh; then
        log "  Engineer completed successfully"
    else
        log "  Engineer exited with error (non-fatal, continuing)"
    fi
    ITERATION=$((ITERATION + 1))
else
    log "Phase 2: No work for engineer — skipping"
fi

echo ""

# ── Phase 3: Review loop ─────────────────────────────────────────────────────
# Reviewer reviews PRs. If changes requested, engineer fixes, reviewer re-reviews.
# Loop until no more reviewable PRs or we hit MAX_ITERATIONS.
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    # Find PRs that are open, non-draft, and not yet approved
    REVIEWABLE=$(gh pr list --state open --json isDraft,reviewDecision \
        --jq '[.[] | select(.isDraft==false and .reviewDecision!="APPROVED")] | length' 2>/dev/null || echo "0")

    if [ "$REVIEWABLE" -eq 0 ]; then
        log "Phase 3: No reviewable PRs — review loop done"
        break
    fi

    log "Phase 3 (iteration $((ITERATION + 1))/$MAX_ITERATIONS): Reviewer agent ($REVIEWABLE reviewable PRs)"
    if ./agents/reviewer.sh; then
        log "  Reviewer completed successfully"
    else
        log "  Reviewer exited with error (non-fatal)"
    fi
    ITERATION=$((ITERATION + 1))

    # After review, check if engineer needs to fix something
    if [ $ITERATION -ge $MAX_ITERATIONS ]; then
        break
    fi

    NEEDS_FEEDBACK=$(gh pr list --state open --json reviewDecision \
        --jq '[.[] | select(.reviewDecision=="CHANGES_REQUESTED")] | length' 2>/dev/null || echo "0")

    if [ "$NEEDS_FEEDBACK" -gt 0 ]; then
        log "Phase 3: Engineer fixing review feedback ($NEEDS_FEEDBACK PRs)"
        if ./agents/engineer.sh; then
            log "  Engineer completed successfully"
        else
            log "  Engineer exited with error (non-fatal)"
        fi
        ITERATION=$((ITERATION + 1))
    fi
done

if [ $ITERATION -ge $MAX_ITERATIONS ]; then
    log "WARNING: Hit max iterations ($MAX_ITERATIONS) — stopping loop"
fi

echo ""
log "=== Loop complete ($ITERATION agent invocations) ==="
