# Phase 2: Event-Driven Agent Architecture

## Context

Phase 1 deploys all agents to GitHub Actions with schedule-based triggers. Phase 2 makes the reactive agents event-driven -- they respond to GitHub events (new issues, new PRs, labels) instead of polling on fixed intervals. Periodic agents (PM, Tech Lead, UX) stay on schedules.

**Prerequisites**: Phase 1 (agent deployment) must be complete and tested.
**Depends on**: `.github/workflows/agent-dev-loop.yml` (from Phase 1) exists and is working.
**Key change**: Splits the sequential dev-loop into individual event-driven workflows.

## Agent Classification

| Agent | Trigger Type | Why |
|-------|-------------|-----|
| **Engineer** | EVENT + daily fallback | Reacts to: prioritized issues, review feedback |
| **Reviewer** | EVENT + 12h fallback | Reacts to: new PRs, engineer pushes after feedback |
| **PO** | EVENT + daily fallback | Reacts to: new `source/*` issues |
| **Triage** | EVENT + 12h fallback | Reacts to: new human-created issues |
| **PM** | SCHEDULE only | Weekly strategic review (inherently periodic) |
| **Tech Lead** | SCHEDULE only | Periodic codebase scanning |
| **UX** | SCHEDULE only | Periodic product review |
| **SRE** | DEFERRED | Alert-driven via Azure Monitor (see SRE monitoring plan) |

## Step 1: Split dev-loop into individual workflows

Delete `agent-dev-loop.yml` (the sequential `run-loop.sh` wrapper from Phase 1). Replace with three independent workflows:

### `.github/workflows/agent-po.yml`

Runs `agents/po.sh` directly (not via `run-loop.sh`). Triggered by `source/*` labels on issues + daily fallback.

```yaml
name: Agent - Product Owner

on:
  issues:
    types: [labeled]
  repository_dispatch:
    types: [agent-pm-feedback]
  schedule:
    - cron: "0 6 * * *"   # Daily 06:00 UTC fallback
  workflow_dispatch: {}

concurrency:
  group: agent-po
  cancel-in-progress: false

jobs:
  po:
    name: Run PO agent
    runs-on: self-hosted
    timeout-minutes: 30
    # Only trigger on source/* labels, not every label
    if: >
      github.event_name != 'issues' ||
      startsWith(github.event.label.name, 'source/')
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Check daily run cap
        id: cap
        run: |
          TODAY=$(date +%Y-%m-%d)
          RUNS=$(gh run list --workflow agent-po.yml --created "$TODAY" --status completed --json databaseId --jq 'length' 2>/dev/null || echo "0")
          echo "runs_today=$RUNS" >> "$GITHUB_OUTPUT"
          if [ "$RUNS" -ge 5 ]; then
            echo "Daily cap reached ($RUNS/5). Skipping."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run PO agent
        if: steps.cap.outputs.skip != 'true'
        run: agents/po.sh

      - name: Dispatch to engineer if work available
        if: steps.cap.outputs.skip != 'true' && success()
        run: |
          UNASSIGNED=$(gh issue list --state open --json assignees --jq '[.[] | select(.assignees | length == 0)] | length' 2>/dev/null || echo "0")
          if [ "$UNASSIGNED" -gt 0 ]; then
            scripts/dispatch-agent.sh "agent-po-complete" '{"chain_depth": 1}'
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### `.github/workflows/agent-engineer.yml`

Runs `agents/engineer.sh`. Triggered by PO dispatch, reviewer feedback dispatch, or daily fallback.

```yaml
name: Agent - Engineer

on:
  repository_dispatch:
    types: [agent-po-complete, agent-reviewer-feedback]
  schedule:
    - cron: "0 8 * * *"   # Daily 08:00 UTC fallback
  workflow_dispatch: {}

concurrency:
  group: agent-engineer
  cancel-in-progress: false

jobs:
  engineer:
    name: Run Engineer agent
    runs-on: self-hosted
    timeout-minutes: 30
    # Chain depth check -- prevent runaway cascading
    if: >
      github.event_name != 'repository_dispatch' ||
      github.event.client_payload.chain_depth <= 3
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Check daily run cap
        id: cap
        run: |
          TODAY=$(date +%Y-%m-%d)
          RUNS=$(gh run list --workflow agent-engineer.yml --created "$TODAY" --status completed --json databaseId --jq 'length' 2>/dev/null || echo "0")
          echo "runs_today=$RUNS" >> "$GITHUB_OUTPUT"
          if [ "$RUNS" -ge 10 ]; then
            echo "Daily cap reached ($RUNS/10). Skipping."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Engineer agent
        if: steps.cap.outputs.skip != 'true'
        run: agents/engineer.sh
```

### `.github/workflows/agent-reviewer.yml`

Runs `agents/reviewer.sh`. Triggered by new/updated PRs or 12h fallback.

```yaml
name: Agent - Reviewer

on:
  pull_request:
    types: [opened, synchronize]
  schedule:
    - cron: "0 */12 * * *"   # Every 12h fallback
  workflow_dispatch: {}

concurrency:
  group: agent-reviewer
  cancel-in-progress: false

jobs:
  review:
    name: Run Reviewer agent
    runs-on: self-hosted
    timeout-minutes: 30
    # Don't review own PRs or PRs from reviewer bot
    if: >
      github.event_name != 'pull_request' ||
      github.event.pull_request.user.login != 'fishbowl-reviewer[bot]'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Check daily run cap
        id: cap
        run: |
          TODAY=$(date +%Y-%m-%d)
          RUNS=$(gh run list --workflow agent-reviewer.yml --created "$TODAY" --status completed --json databaseId --jq 'length' 2>/dev/null || echo "0")
          echo "runs_today=$RUNS" >> "$GITHUB_OUTPUT"
          if [ "$RUNS" -ge 10 ]; then
            echo "Daily cap reached ($RUNS/10). Skipping."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Reviewer agent
        if: steps.cap.outputs.skip != 'true'
        run: agents/reviewer.sh

      - name: Dispatch feedback if changes requested
        if: steps.cap.outputs.skip != 'true' && success()
        run: |
          # Check if reviewer requested changes on any PR
          CHANGES_REQUESTED=$(gh pr list --state open --json reviewDecision \
            --jq '[.[] | select(.reviewDecision=="CHANGES_REQUESTED")] | length' 2>/dev/null || echo "0")
          if [ "$CHANGES_REQUESTED" -gt 0 ]; then
            DEPTH=${{ github.event.client_payload.chain_depth || 0 }}
            scripts/dispatch-agent.sh "agent-reviewer-feedback" "{\"chain_depth\": $((DEPTH + 1))}"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Step 2: Update Triage workflow with event trigger

Modify `agent-triage.yml` (created in Phase 1) to add `issues.opened` trigger:

```yaml
name: Agent - Issue Triage

on:
  issues:
    types: [opened]
  schedule:
    - cron: "0 */12 * * *"
  workflow_dispatch: {}

concurrency:
  group: agent-triage
  cancel-in-progress: false

jobs:
  triage:
    name: Run triage agent
    runs-on: self-hosted
    timeout-minutes: 20
    # Skip agent-created issues (they don't need triage)
    if: >
      github.event_name != 'issues' ||
      !contains(toJSON(github.event.issue.labels), 'agent-created')
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Check daily run cap
        id: cap
        run: |
          TODAY=$(date +%Y-%m-%d)
          RUNS=$(gh run list --workflow agent-triage.yml --created "$TODAY" --status completed --json databaseId --jq 'length' 2>/dev/null || echo "0")
          if [ "$RUNS" -ge 5 ]; then
            echo "Daily cap reached ($RUNS/5). Skipping."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run triage
        if: steps.cap.outputs.skip != 'true'
        run: scripts/run-triage.sh
```

## Step 3: Create dispatch helper script

**New file: `scripts/dispatch-agent.sh`**

```bash
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
  -f event_type="$EVENT_TYPE" \
  --input - <<EOF
{"event_type": "$EVENT_TYPE", "client_payload": $PAYLOAD}
EOF

echo "Dispatched successfully"
```

## Step 4: Safety Controls

### Loop Prevention

| Control | How | Where |
|---------|-----|-------|
| Concurrency groups | One instance per agent at a time | All workflow files |
| Self-trigger prevention | `if:` conditions exclude bot's own user | PO, Reviewer workflows |
| Chain depth limit | `chain_depth` in dispatch payload, skip if > 3 | Engineer workflow |
| Daily run caps | Check completed runs for today, skip if over limit | All event-driven workflows |
| Scheduled fallbacks | Schedule trigger catches anything missed by events | All workflows |

### Event Chain: The Complete Flow

```
Human/scanning agent creates source/* issue
  -> issues.labeled -> PO workflow triggers
    -> PO triages, sets priority
      -> PO dispatches "agent-po-complete"
        -> Engineer workflow triggers
          -> Engineer picks highest-priority issue, opens PR
            -> pull_request.opened -> Reviewer workflow triggers
              -> Reviewer reviews
                |-- APPROVE -> merge -> chain ends
                +-- CHANGES_REQUESTED
                   -> Reviewer dispatches "agent-reviewer-feedback"
                     -> Engineer workflow triggers (chain_depth: 2)
                       -> Engineer fixes, pushes
                         -> pull_request.synchronize -> Reviewer triggers again
                           -> Reviewer reviews (chain_depth: 3)
                             -> APPROVE or CLOSE (depth limit approaching)
```

### Cost Estimate (Event-Driven)

| Agent | Frequency | Est. Cost/Week |
|-------|-----------|---------------|
| Engineer | 5-15 event-driven runs | $8-$45 |
| Reviewer | 5-15 event-driven runs | $3-$23 |
| PO | 5-10 mixed runs | $3-$15 |
| Triage | 0-3 event-driven runs | $0-$3 |
| PM/Tech Lead/UX | 1-4 scheduled runs each | $4-$8 |
| **Total (excl. SRE)** | | **$18-$94/week** |

## Files Summary

| File | Action |
|------|--------|
| `.github/workflows/agent-po.yml` | CREATE |
| `.github/workflows/agent-engineer.yml` | CREATE |
| `.github/workflows/agent-reviewer.yml` | CREATE |
| `.github/workflows/agent-triage.yml` | MODIFY (add event triggers, daily caps) |
| `.github/workflows/agent-dev-loop.yml` | DELETE (replaced by individual workflows) |
| `scripts/dispatch-agent.sh` | CREATE |

## Verification

1. Create a test issue manually -> verify Triage triggers within minutes
2. Open a test PR from a branch -> verify Reviewer triggers
3. Add `source/test` label -> verify PO triggers
4. Verify dispatch chain: PO complete -> Engineer triggers
5. Trigger same workflow twice rapidly -> confirm concurrency queues
6. Verify daily cap: check logs show cap message after limit
7. Delete `agent-dev-loop.yml` after event chains proven
8. Monitor 48h for runaway loops or cost spikes
