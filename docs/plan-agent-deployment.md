# Phase 1: Deploy Agent Team to GitHub Actions

## Context

Agent Fishbowl's 8-agent team runs from local shell scripts on the dev VM. Editing prompts/scripts during development can break the running agents -- there's no stable "production" version. We need agents deployed as cloud services, isolated from the dev workspace.

**Prerequisites**: None -- this is the first phase.
**Depends on**: Nothing.
**Blocks**: Phase 2 (event-driven triggers) builds on these workflows.

## Deployment Model

**Agents are cloud-deployed services.** They:
- Pull code from Git (`stable` branch), never from the dev workspace
- Run via GitHub Actions (the execution layer)
- Execute on the self-hosted runner (swappable to dedicated VM later without workflow changes)
- Are gated by a `stable` branch -- human promotes `main` -> `stable` after verifying

```
Developer workflow:
  edit locally -> push to main -> CI passes -> human promotes -> stable

Agent workflow:
  schedule/dispatch -> Actions triggers -> checkout stable -> load .env -> run agent
```

---

## Implementation Steps

### Step 1: Stage secrets for runner access

The `.env` is gitignored, so `actions/checkout` won't have it. Stage it at a fixed path:

```bash
mkdir -p ~/.config/agent-fishbowl
cp /home/fcleary/projects/agent-fishbowl/.env ~/.config/agent-fishbowl/.env
```

PEM keys are already at `~/.config/agent-fishbowl/*.pem` (absolute paths in `.env`), so they'll resolve from any working directory.

### Step 2: Update `run-agent.sh` for CI context

**File: `agents/run-agent.sh`** -- lines 32-38

Current code:
```bash
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi
```

Change to:
```bash
ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    ENV_FILE="$HOME/.config/agent-fishbowl/.env"
fi
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "WARNING: No .env found at $PROJECT_ROOT/.env or $HOME/.config/agent-fishbowl/.env"
fi
```

This makes `run-agent.sh` work both locally (dev workspace has `.env`) and in CI (checkout doesn't have `.env`, falls back to staged copy).

### Step 3: Create `stable` branch

```bash
git push origin main:stable
```

One-time setup. All agent workflows check out from `stable`.

### Step 4: Create promotion workflow

**New file: `.github/workflows/promote.yml`**

```yaml
name: Promote to Stable

on:
  workflow_dispatch:
    inputs:
      confirm:
        description: 'Type PROMOTE to confirm'
        required: true

jobs:
  promote:
    runs-on: self-hosted
    if: github.event.inputs.confirm == 'PROMOTE'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Fast-forward stable to main
        run: |
          git push origin main:stable --force-with-lease
          echo "stable branch updated to match main ($(git rev-parse --short HEAD))"
```

### Step 5: Update SRE workflow

**Rename: `.github/workflows/sre.yml` -> `.github/workflows/agent-sre.yml`**

Full updated content:
```yaml
name: Agent - SRE Health Check

on:
  schedule:
    - cron: "30 */4 * * *"   # Every 4 hours
  workflow_dispatch: {}

concurrency:
  group: agent-sre
  cancel-in-progress: false

jobs:
  health-check:
    name: Run SRE agent
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Run SRE health check
        run: scripts/run-sre.sh
```

### Step 6: Create dev-loop workflow

**New file: `.github/workflows/agent-dev-loop.yml`**

This runs the existing `run-loop.sh` (PO -> Engineer -> Reviewer) on a daily schedule. In Phase 2, this gets replaced by individual event-driven workflows.

```yaml
name: Agent - Development Loop

on:
  schedule:
    - cron: "0 8 * * *"   # Daily at 08:00 UTC
  workflow_dispatch: {}

concurrency:
  group: agent-dev-loop
  cancel-in-progress: false

jobs:
  dev-loop:
    name: Run PO -> Engineer -> Reviewer loop
    runs-on: self-hosted
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Run development loop
        run: scripts/run-loop.sh
```

`timeout-minutes: 60` because this runs up to 3 agents sequentially with a review loop.

### Step 7: Create strategic review workflow

**New file: `.github/workflows/agent-strategic.yml`**

```yaml
name: Agent - PM Strategic Review

on:
  schedule:
    - cron: "0 6 * * 1"   # Weekly, Monday 06:00 UTC
  workflow_dispatch: {}

concurrency:
  group: agent-strategic
  cancel-in-progress: false

jobs:
  strategic:
    name: Run PM strategic review
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Run PM agent
        run: scripts/run-strategic.sh
```

### Step 8: Create scans workflow

**New file: `.github/workflows/agent-scans.yml`**

```yaml
name: Agent - Tech Lead + UX Scans

on:
  schedule:
    - cron: "0 10 */3 * *"   # Every 3 days at 10:00 UTC
  workflow_dispatch: {}

concurrency:
  group: agent-scans
  cancel-in-progress: false

jobs:
  scans:
    name: Run Tech Lead + UX review
    runs-on: self-hosted
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Run scans
        run: scripts/run-scans.sh
```

### Step 9: Create triage workflow

**New file: `.github/workflows/agent-triage.yml`**

```yaml
name: Agent - Issue Triage

on:
  schedule:
    - cron: "0 */12 * * *"   # Every 12 hours
  workflow_dispatch: {}

concurrency:
  group: agent-triage
  cancel-in-progress: false

jobs:
  triage:
    name: Run triage agent
    runs-on: self-hosted
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Run triage
        run: scripts/run-triage.sh
```

### Step 10: Update CLAUDE.md

Add section documenting:
- Agents run via GitHub Actions (not local scripts for production)
- `stable` branch is the production source
- How to promote: trigger `promote.yml`
- `workflow_dispatch` for manual agent runs
- Local scripts (`run-loop.sh`, etc.) remain as dev/testing fallbacks

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `agents/run-agent.sh` | MODIFY | Add `.env` fallback path for CI |
| `.github/workflows/sre.yml` | RENAME + MODIFY | -> `agent-sre.yml`, add `ref: stable`, concurrency, env copy |
| `.github/workflows/promote.yml` | CREATE | Manual promote main -> stable |
| `.github/workflows/agent-dev-loop.yml` | CREATE | Daily PO->Engineer->Reviewer loop |
| `.github/workflows/agent-strategic.yml` | CREATE | Weekly PM review |
| `.github/workflows/agent-scans.yml` | CREATE | Tech Lead + UX every 3 days |
| `.github/workflows/agent-triage.yml` | CREATE | Triage every 12h |
| `CLAUDE.md` | MODIFY | Document agent deployment model |

**Total: 5 new files, 3 modified files**

---

## Verification

1. **Stage env**: `mkdir -p ~/.config/agent-fishbowl && cp .env ~/.config/agent-fishbowl/.env`
2. **Create stable**: `git push origin main:stable`
3. **Test promote**: Trigger `promote.yml` via Actions UI -> confirm stable matches main
4. **Test each workflow**: Trigger via `workflow_dispatch` one at a time:
   - `agent-sre.yml` -- should complete with health report
   - `agent-triage.yml` -- should complete (may find no human issues)
   - `agent-dev-loop.yml` -- should run PO check, possibly engineer, possibly reviewer
   - `agent-strategic.yml` -- should run PM review
   - `agent-scans.yml` -- should run Tech Lead + UX scans
5. **Check logs**: Verify in each run:
   - `.env` loaded successfully (GitHub App identity message)
   - PEM key accessible (token generation succeeds)
   - Agent completes without errors
6. **Verify isolation**: Edit a prompt locally (don't push). Trigger a workflow. Confirm the workflow uses the `stable` version, not local edits.
7. **Test concurrency**: Trigger same workflow twice rapidly -> second should queue, not run parallel
