#!/bin/bash
# Full development loop: PO → Engineer → Reviewer → (feedback) → merge
# Run once for a complete cycle, or schedule via cron for continuous operation.
#
# Usage: ./scripts/run-loop.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MAX_REVIEW_ITERATIONS=4  # Safety valve for review loop (review → fix → review → approve)

log() { echo "[loop $(date -u +%H:%M:%S)] $*"; }

log "=== Agent Fishbowl: Full Development Loop ==="
echo ""

# ── Cleanup: start from a clean main ─────────────────────────────────────────
log "Cleanup: resetting to main"
git checkout main 2>/dev/null || true
git pull origin main 2>/dev/null || true
git fetch --prune 2>/dev/null || true
echo ""

# ── Phase 1: PO triages intake + creates issues (if backlog is thin) ─────────
log "Phase 1: PO agent — triaging intake + checking backlog"
OPEN_ISSUES=$(gh issue list --state open --json number --jq 'length')

if [ "$OPEN_ISSUES" -lt 3 ]; then
    log "  Backlog has $OPEN_ISSUES open issues (< 3) — running PO agent"
    if ./agents/po.sh; then
        log "  PO agent completed successfully"
    else
        log "  PO agent exited with error (non-fatal, continuing)"
    fi
else
    log "  Backlog has $OPEN_ISSUES open issues — skipping PO"
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
else
    log "Phase 2: No work for engineer — skipping"
fi

echo ""

# ── Phase 3: Review loop ─────────────────────────────────────────────────────
# Reviewer reviews PRs. If changes requested, engineer fixes, reviewer re-reviews.
# Separate budget: PM + Engineer don't eat into review iterations.
REVIEW_ITERATION=0
while [ $REVIEW_ITERATION -lt $MAX_REVIEW_ITERATIONS ]; do
    # Find PRs that are open, non-draft, and not yet approved
    REVIEWABLE=$(gh pr list --state open --json isDraft,reviewDecision \
        --jq '[.[] | select(.isDraft==false and .reviewDecision!="APPROVED")] | length' 2>/dev/null || echo "0")

    if [ "$REVIEWABLE" -eq 0 ]; then
        log "Phase 3: No reviewable PRs — review loop done"
        break
    fi

    log "Phase 3 (review iteration $((REVIEW_ITERATION + 1))/$MAX_REVIEW_ITERATIONS): Reviewer agent ($REVIEWABLE reviewable PRs)"
    if ./agents/reviewer.sh; then
        log "  Reviewer completed successfully"
    else
        log "  Reviewer exited with error (non-fatal)"
    fi
    REVIEW_ITERATION=$((REVIEW_ITERATION + 1))

    # After review, check if engineer needs to fix something
    if [ $REVIEW_ITERATION -ge $MAX_REVIEW_ITERATIONS ]; then
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
        REVIEW_ITERATION=$((REVIEW_ITERATION + 1))
    fi
done

if [ $REVIEW_ITERATION -ge $MAX_REVIEW_ITERATIONS ]; then
    log "WARNING: Hit max review iterations ($MAX_REVIEW_ITERATIONS) — stopping review loop"
fi

echo ""
log "=== Loop complete (review iterations: $REVIEW_ITERATION/$MAX_REVIEW_ITERATIONS) ==="
