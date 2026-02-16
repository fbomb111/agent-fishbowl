# SRE Monitoring Infrastructure Plan

## Context

The current SRE agent polls every 4 hours via `scripts/run-sre.sh`, which runs a full Claude Code session to check health. This is expensive (~$21-42/week) and reactive only every 4 hours. The goal is to replace this with proper Azure monitoring infrastructure that:

1. **Detects issues in real-time** (not every 4 hours)
2. **Only invokes the AI SRE agent when something is actually wrong** (not for routine checks)
3. **Provides dashboards and alerts** for human visibility

**Prerequisites**: Phase 1 (agent deployment) should be complete so `agent-sre.yml` exists.
**Depends on**: Azure resources in `rg-agent-fishbowl` resource group.
**Independent of**: Phase 2 (event-driven) -- can be implemented in parallel.

## Target Architecture

```
Azure Monitor Alerts (real-time)
  |-- Container App health -> Alert -> Action Group -> webhook/dispatch
  |-- API response time -> Alert -> Action Group -> webhook/dispatch
  |-- Error rate spike -> Alert -> Action Group -> webhook/dispatch
  +-- Ingestion staleness -> Alert -> Action Group -> webhook/dispatch
                                       |
                              GitHub repository_dispatch
                                       |
                              agent-sre.yml (event-driven)
                                       |
                              SRE agent investigates + creates issues
```

## What to Monitor

### Application Health

| Metric | Source | Alert Condition | Severity |
|--------|--------|----------------|----------|
| API availability | Container App health probe | < 100% for 5 min | Critical |
| API response time | App Insights / Container App metrics | p95 > 5s for 10 min | Warning |
| HTTP 5xx rate | Container App metrics | > 5% of requests for 5 min | Critical |
| Container restarts | Container App metrics | > 2 restarts in 1 hour | Warning |

### Ingestion Pipeline

| Metric | Source | Alert Condition | Severity |
|--------|--------|----------------|----------|
| Ingestion freshness | Custom metric (last successful run) | > 12 hours since last success | Warning |
| Ingestion workflow failures | GitHub Actions | 2 consecutive failures | Critical |
| Article count stagnation | Azure Blob Storage | No new blobs for 24h | Warning |

### Infrastructure

| Metric | Source | Alert Condition | Severity |
|--------|--------|----------------|----------|
| Container App CPU | Container App metrics | > 80% for 15 min | Warning |
| Container App memory | Container App metrics | > 80% for 15 min | Warning |
| GitHub Actions runner | Custom (heartbeat check) | No heartbeat for 30 min | Critical |
| GitHub API rate limit | Custom metric | < 500 remaining | Warning |

## Azure Resources to Create

### 1. Application Insights

Enable for the Container App (`ca-agent-fishbowl-api`). Provides:
- Request logging (latency, status codes, exceptions)
- Dependency tracking (Azure Blob, GitHub API calls)
- Custom metrics (ingestion staleness, article counts)

```bash
az monitor app-insights component create \
  --app fishbowl-appinsights \
  --location eastus \
  --resource-group rg-agent-fishbowl \
  --kind web
```

### 2. Alert Rules

Create Azure Monitor alert rules for each metric above. Example for API availability:

```bash
az monitor metrics alert create \
  --name "fishbowl-api-availability" \
  --resource-group rg-agent-fishbowl \
  --scopes <container-app-resource-id> \
  --condition "avg Percentage < 99" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 1 \
  --action-group fishbowl-alerts
```

### 3. Action Group

Create an action group that triggers a GitHub `repository_dispatch` via webhook:

```bash
az monitor action-group create \
  --name fishbowl-alerts \
  --resource-group rg-agent-fishbowl \
  --short-name fb-alerts \
  --action webhook sre-dispatch "https://api.github.com/repos/YourMoveLabs/agent-fishbowl/dispatches" \
    useCommonAlertSchema=true
```

The webhook would need a GitHub token for authentication. Alternatively, use an Azure Function as a middleware:

```
Azure Alert -> Action Group -> Azure Function -> gh api dispatches -> agent-sre.yml
```

The Azure Function approach is more secure (token stored in Key Vault, not in the alert config).

### 4. Dashboard

Create an Azure Dashboard or Grafana dashboard with:
- API response time (p50, p95, p99) over 24h
- Error rate (5xx) over 24h
- Ingestion status (last success, article count)
- Container health (CPU, memory, restarts)
- Agent activity (workflow runs today, costs estimate)

## SRE Agent Updates

### Updated `agent-sre.yml` (event-driven)

```yaml
name: Agent - SRE

on:
  repository_dispatch:
    types: [azure-alert-critical, azure-alert-warning]
  schedule:
    - cron: "0 6 * * *"   # Daily health summary (not investigative)
  workflow_dispatch: {}

concurrency:
  group: agent-sre
  cancel-in-progress: false

jobs:
  sre:
    name: Run SRE agent
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          ref: stable

      - name: Load agent env
        run: cp ~/.config/agent-fishbowl/.env .env

      - name: Determine run mode
        id: mode
        run: |
          if [ "${{ github.event_name }}" = "repository_dispatch" ]; then
            echo "mode=investigate" >> "$GITHUB_OUTPUT"
            echo "alert=${{ toJSON(github.event.client_payload) }}" >> "$GITHUB_OUTPUT"
          else
            echo "mode=summary" >> "$GITHUB_OUTPUT"
          fi

      - name: Run SRE agent
        run: scripts/run-sre.sh
        env:
          SRE_MODE: ${{ steps.mode.outputs.mode }}
          ALERT_PAYLOAD: ${{ steps.mode.outputs.alert }}
```

### Updated `scripts/run-sre.sh`

Add mode awareness:
- **`investigate` mode** (triggered by alert): Full Claude agent, focused on the specific alert. Higher urgency.
- **`summary` mode** (daily schedule): Quick bash-only health summary. Only invokes Claude if something looks off.

```bash
if [ "${SRE_MODE:-summary}" = "summary" ]; then
    # Quick bash health check
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
      https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/health)
    if [ "$API_STATUS" = "200" ]; then
        echo "Health: GREEN. Skipping full SRE agent."
        exit 0
    fi
    echo "Health: DEGRADED (API status: $API_STATUS). Running full SRE agent."
fi

# Full SRE agent (investigate mode or degraded summary)
agents/sre.sh
```

### Updated `agents/prompts/sre.md`

Add alert context awareness:
- If `ALERT_PAYLOAD` env var is set, the agent focuses on investigating that specific alert
- If no alert, agent does a broader health scan
- Agent can access App Insights logs via `az monitor app-insights query`

## Cost Impact

| Component | Monthly Cost |
|-----------|-------------|
| Application Insights (basic) | ~$5-15 (depends on data volume) |
| Alert rules (5-10 rules) | Free (included in Azure Monitor) |
| Action group (webhook) | Free |
| Azure Function middleware | ~$0 (consumption plan, minimal invocations) |
| SRE agent (event-driven) | ~$5-20/month (only runs on alerts + daily summary) |
| **Total** | **~$10-35/month** |

**Savings vs current**: Current SRE polls 6x/day x 7 days = 42 runs/week at ~$0.50-1.00 each = $21-42/week. Event-driven SRE + daily summary = ~$2-5/week. **Saves $15-37/week.**

## Implementation Order

1. Create Application Insights resource + connect to Container App
2. Create alert rules for critical metrics (API availability, 5xx rate)
3. Create action group with Azure Function middleware
4. Update `run-sre.sh` with mode awareness (summary vs investigate)
5. Update `agent-sre.yml` with `repository_dispatch` trigger
6. Add warning-level alerts (latency, ingestion, resources)
7. Create dashboard
8. Reduce SRE schedule from every 4h to daily summary
9. Monitor for 1 week, tune alert thresholds

## Files Summary

| File | Action |
|------|--------|
| `.github/workflows/agent-sre.yml` | MODIFY (add repository_dispatch, run mode) |
| `scripts/run-sre.sh` | MODIFY (add mode awareness, bash pre-check) |
| `agents/prompts/sre.md` | MODIFY (add alert context awareness) |

## Azure Resources

| Resource | Type | Purpose |
|----------|------|---------|
| `fishbowl-appinsights` | Application Insights | Request logging, metrics |
| `fishbowl-alerts` | Action Group | Route alerts to GitHub |
| 5-10 alert rules | Monitor Alert Rules | Real-time detection |
| Optional: Azure Function | Function App | Secure webhook middleware |
| Optional: Dashboard | Azure Dashboard | Visual monitoring |
