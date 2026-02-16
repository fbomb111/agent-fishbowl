# Agent Fishbowl — Project Context

## Overview

Agent Fishbowl is an AI-curated news feed built and maintained by a team of AI agents. The project demonstrates multi-agent orchestration in the open — every issue, PR, commit, and review is done by agents coordinating through GitHub.

**Repository**: `YourMoveLabs/agent-fishbowl` (public)
**Main Branch**: `main`

## Architecture

- **Backend**: FastAPI (Python 3.12) — `api/`
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS — `frontend/`
- **Storage**: Azure Blob Storage (articles as JSON, no database)
- **Activity Feed**: GitHub API (cached by FastAPI) — agents' GitHub activity IS the data
- **Agent Runtime**: Claude Code CLI sessions with role-specific prompts
- **Hosting**: Azure Container Apps (API) + Azure Static Web Apps (frontend)

## Agent Deployment

Agents are deployed as GitHub Actions workflows running on the self-hosted runner. They pull code from the `stable` branch — never from the dev workspace.

**Branches:**
- `main` — active development, CI tests pass
- `stable` — production agent code, human-promoted from main

**Promotion:** Trigger the `promote.yml` workflow (Actions UI → Run workflow → type "PROMOTE"). This fast-forwards `stable` to match `main`.

**Workflows** (all in `.github/workflows/`):

| Workflow | Agents | Triggers | Cap |
|----------|--------|----------|-----|
| `agent-po.yml` | PO | `issues.labeled` (source/*) + PM dispatch + daily | 5/day |
| `agent-engineer.yml` | Engineer | PO/Reviewer dispatch + daily | 10/day |
| `agent-reviewer.yml` | Reviewer | `pull_request` (opened/sync) + 12h | 10/day |
| `agent-triage.yml` | Triage | `issues.opened` + 12h | 5/day |
| `agent-sre.yml` | SRE | `repository_dispatch` (azure-alert) + 4h schedule | — |
| `agent-strategic.yml` | PM | Weekly Mon 06:00 UTC | — |
| `agent-scans.yml` | Tech Lead + UX | Every 3 days | — |
| `promote.yml` | — | Manual only | — |

**Event Chain:**
```
source/* issue → PO → dispatch → Engineer → opens PR → Reviewer
                                              ↑ changes requested ↓
                                              ← dispatch feedback ←
```

**Safety Controls:**
- Concurrency groups prevent parallel runs of the same agent
- Chain depth limit (max 3) prevents runaway dispatch cascading
- Daily caps per agent prevent cost blowouts
- Self-trigger prevention via `if:` conditions on bot events
- `scripts/dispatch-agent.sh` handles agent-to-agent chaining

**Environment:** Agent .env is staged at `~/.config/agent-fishbowl/.env` on the runner. Workflows copy it into the checkout. PEM keys are already at `~/.config/agent-fishbowl/*.pem`.

**Local scripts remain** as dev/testing fallbacks (`scripts/run-loop.sh`, etc.). Production runs via GitHub Actions.

### Alert Bridge (Azure Function → GitHub)

Real-time alerting bridge: Azure Monitor detects problems → fires alert → Action Group webhooks to an Azure Function → Function dispatches `azure-alert` to GitHub → `agent-sre.yml` triggers with alert context.

**Flow:**
```
Container App metrics → Alert Rule fires → Action Group webhook
  → func-fishbowl-alert-bridge (Azure Function)
    → reads GitHub PAT from Key Vault (via Managed Identity)
      → POST repos/{repo}/dispatches (event_type: azure-alert)
        → agent-sre.yml triggers → run-sre.sh routes to playbooks/Claude
```

**Azure Resources** (all in `rg-agent-fishbowl`):

| Resource | Name | Purpose |
|----------|------|---------|
| Function App | `func-fishbowl-alert-bridge` | HTTP trigger, parses alert, dispatches to GitHub |
| Key Vault | `kv-fishbowl-sre` | Stores GitHub PAT (`github-dispatch-token`) |
| App Insights | `fishbowl-appinsights` | Function App telemetry |
| Storage Account | `stfuncfishbowl` | Functions runtime storage |
| Action Group | `fishbowl-alerts` | Webhook to Function App |

**Alert Rules:**

| Alert | Metric | Condition | Window | Severity |
|-------|--------|-----------|--------|----------|
| `fishbowl-api-5xx` | Requests (5xx) | > 5 total | 5 min | Sev 1 |
| `fishbowl-container-restarts` | RestartCount | > 2 total | 1 hour | Sev 2 |
| `fishbowl-api-no-traffic` | Requests | < 1 total | 15 min | Sev 0 |

**Function Code:** `functions/alert_bridge/__init__.py`
- Parses Azure Monitor Common Alert Schema
- Reads GitHub PAT from Key Vault via Managed Identity (`id-agent-fishbowl`)
- Falls back to `GITHUB_TOKEN` env var for local dev
- Deploy: `cd functions && func azure functionapp publish func-fishbowl-alert-bridge --python`

## Project Structure

```
api/                    FastAPI backend
  main.py               App entry point
  config.py             Settings (env vars)
  routers/              API route handlers
    articles.py         GET /api/articles
    activity.py         GET /api/activity
  services/             Business logic
  models/               Pydantic models
    article.py          Article data models
frontend/               Next.js frontend
  src/app/              Pages (App Router)
    page.tsx            News feed (home)
    fishbowl/page.tsx   Activity feed
  src/components/       React components
  src/lib/api.ts        API client
config/                 Configuration
  sources.yaml          RSS feed sources
  goals.md              Strategic goals (human-maintained, PM agent reads)
  conventions.md        Technical standards (Tech Lead maintains)
  ux-standards.md       UX checklist (UX agent reads — Phase 2)
agents/                 Agent runner infrastructure
  run-agent.sh          Shared runner (per-role tool allowlists)
  po.sh                 Product Owner — triages intake, prioritizes backlog
  engineer.sh           Engineer — picks issues, implements, opens PRs
  reviewer.sh           Reviewer — reviews PRs, merges or requests changes
  tech-lead.sh          Tech Lead — sets standards, spots architecture needs
  triage.sh             Triage — validates human-created issues
  ux.sh                 UX Reviewer — reviews product UX
  pm.sh                 Product Manager — reads goals.md, manages GitHub Project roadmap
  sre.sh                SRE — monitors system health, files issues for problems
  prompts/              Role-specific prompt files
  logs/                 Run logs (gitignored)
functions/              Azure Function (alert bridge)
  alert_bridge/         HTTP trigger: Azure Monitor → GitHub dispatch
  host.json             Functions runtime config
  requirements.txt      Python dependencies
scripts/                Deterministic operations
  run-loop.sh           Dev loop (PO → Engineer → Reviewer)
  run-scans.sh          Scanning agents (Tech Lead + UX)
  run-triage.sh         Triage human issues
  run-strategic.sh      PM strategic review (weekly)
  run-checks.sh         All quality checks (ruff + tsc + eslint + conventions)
  create-branch.sh      Create branch from issue number
  lint-conventions.sh   Convention checks with agent-friendly errors
  setup-labels.sh       Create GitHub labels (idempotent)
.claude/commands/       Claude Code skills (AI-guided workflows)
  pick-issue.md         Find + claim highest-priority issue
  open-pr.md            Create draft PR with proper format
.github/workflows/      CI + agent deployment workflows
  promote.yml           Promote main → stable
  agent-po.yml          PO (event-driven: source/* labels + dispatch)
  agent-engineer.yml    Engineer (event-driven: PO/Reviewer dispatch)
  agent-reviewer.yml    Reviewer (event-driven: PR opened/sync)
  agent-triage.yml      Triage (event-driven: issues.opened + 12h)
  agent-strategic.yml   PM review (weekly schedule)
  agent-scans.yml       Tech Lead + UX (every 3 days schedule)
```

## Git Workflow

### Branch Naming
- Features: `feat/issue-{N}-short-description`
- Bug fixes: `fix/issue-{N}-short-description`
- Use `scripts/create-branch.sh <issue_number> [feat|fix]` to create branches automatically.

### Commit Messages
Format: `type(scope): description (#issue)`

Examples:
- `feat(api): add category filter endpoint (#42)`
- `fix(frontend): fix mobile layout overflow (#17)`
- `chore(ci): add type-check step to workflow (#5)`

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`
Scopes: `api`, `frontend`, `ci`, `config`

### Pull Requests
- Create as **ready** (not draft) — the reviewer agent reviews and merges
- Title: concise, under 70 characters
- Body MUST include `Closes #N` to link the issue
- Must pass `scripts/run-checks.sh` before opening
- Include a summary of what changed and why

## Label Taxonomy

| Label | Purpose |
|-------|---------|
| `agent/frontend` | Frontend work (React, Tailwind, pages) |
| `agent/backend` | Backend work (FastAPI, services, models) |
| `agent/ingestion` | Article ingestion and processing |
| `priority/high` | Do first |
| `priority/medium` | Do after high-priority items |
| `priority/low` | Low priority — do when convenient |
| `type/feature` | New functionality |
| `type/bug` | Something broken |
| `type/chore` | Maintenance, CI, docs |
| `type/refactor` | Code refactoring or architecture improvement |
| `type/ux` | User experience improvement |
| `source/roadmap` | From product roadmap |
| `source/tech-lead` | From tech lead code review |
| `source/ux-review` | From UX agent review |
| `source/triage` | Validated by triage agent |
| `source/reviewer-backlog` | Rework from closed PR |
| `source/sre` | From SRE monitoring |
| `status/in-progress` | An agent is working on this |
| `status/blocked` | Cannot proceed — needs human input |
| `status/needs-info` | Needs more information from reporter |
| `review/approved` | Reviewer approved this PR |
| `review/changes-requested` | Reviewer requested changes |
| `pm/misaligned` | PM flagged: issue misinterprets roadmap intent |
| `agent-created` | Created by an agent (not human) |

## Agent Team

| Role | Identity | Cadence | One-liner |
|------|----------|---------|-----------|
| **PO** | `fishbowl-po[bot]` | Event-driven + daily | Central intake funnel — triages all inputs into a prioritized backlog |
| **Engineer** | `fishbowl-engineer[bot]` | Event-driven + daily | Picks issues, implements code, opens PRs |
| **Reviewer** | `fishbowl-reviewer[bot]` | Event-driven + 12h | Reviews PRs, approves+merges or requests changes |
| **Tech Lead** | `fishbowl-techlead[bot]` | Every 3-4 days | Sets technical standards, identifies architecture needs |
| **PM** | `fishbowl-pm[bot]` | Weekly | Strategic goals and GitHub Project roadmap management |
| **Triage** | `fishbowl-triage[bot]` | Every 12-24h | Validates human-created issues |
| **UX** | `fishbowl-ux[bot]` | Weekly | Reviews product UX, creates improvement issues |
| **SRE** | `fishbowl-sre[bot]` | Every 4h | Monitors system health, files issues for problems |

### Information Flow

All roads lead to the PO. No agent bypasses the PO to create work for the engineer.

```
PM (strategy) → manages GitHub Project roadmap → PO (tactical) reads project items + source/* intake → backlog
PM reviews PO's source/roadmap issues → pm/misaligned if off-target → PO re-scopes
Tech Lead, UX, Triage → create source/* intake issues → PO triages → backlog
SRE → monitors health, creates source/sre issues for failures → PO triages → backlog
Engineer claims issues → opens PR → Reviewer merges (or backlogs via source/reviewer-backlog → PO)
```

## Agent Coordination Rules

- **Never pick an assigned issue.** If it has an assignee, skip it.
- **Never modify another agent's open PR.** If they have a branch, leave it alone.
- **One task per run.** Pick one issue or fix one PR's feedback, not both.
- **Reviewer merges.** Only the reviewer agent approves and squash-merges PRs. No other agent merges.
- **Engineer creates ready PRs** (not drafts) so the reviewer can act on them.
- **Max 2 review rounds.** If a PR still has issues after 2 rounds of change requests, the reviewer either approves with caveats or closes and backlogs.
- **Comment your progress.** When you start an issue, comment. When you open a PR, comment on the issue with a link.
- **All intake flows through the PO.** Scanning agents (tech lead, UX, triage) create issues with `source/*` labels. Only the PO sets final priority.
- **Scanning agents never set `priority/high`.** They use `priority/medium`. The PO decides what's urgent.
- **Preserve `source/*` labels.** These track where issues originated. Don't remove them.

## Available Tools

### Scripts (`scripts/`)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `dispatch-agent.sh` | Dispatch repository_dispatch event to trigger downstream agent | Agent-to-agent chaining |
| `health-check.sh` | Full system health check (API, ingestion, deploys, GitHub) | SRE runs |
| `workflow-status.sh` | GitHub Actions workflow run summary | SRE investigation |
| `find-issues.sh` | Find existing issues by label | SRE dedup check |
| `playbooks/restart-api.sh` | Auto-restart Container App revision | Automated remediation |
| `playbooks/retrigger-ingest.sh` | Re-trigger ingest workflow | Automated remediation |
| `run-loop.sh` | Dev loop (PO → Engineer → Reviewer) | Local dev/testing fallback |
| `run-scans.sh` | Scanning agents (Tech Lead + UX) | Every 3-4 days |
| `run-triage.sh` | Triage human-created issues | Every 12-24h |
| `run-strategic.sh` | PM strategic review (goals → roadmap) | Weekly |
| `run-sre.sh` | SRE health check (API, ingestion, deploys) | Every 4 hours |
| `run-checks.sh` | Quality checks (ruff + tsc + eslint + conventions) | Before every PR |
| `create-branch.sh` | Create named branch from issue number | When starting work on an issue |
| `lint-conventions.sh` | Check branch naming, PR format, file sizes | Runs as part of run-checks.sh |
| `setup-labels.sh` | Create/update GitHub labels | Setup only |

### Skills (`.claude/commands/`)

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `/pick-issue` | Find highest-priority unassigned issue, assign it, create branch | Start of engineer run |
| `/open-pr` | Create draft PR with proper format and issue reference | After implementing a change |

### GitHub CLI (`gh`)

Agents use `gh` for all GitHub operations:
- `gh issue list` / `gh issue view` / `gh issue create` / `gh issue edit`
- `gh pr create` / `gh pr view` / `gh pr list`
- `gh pr review` (for reviewer agent)

## Code Conventions

### Backend
- Python 3.12, type hints required
- FastAPI routers in `api/routers/`, services in `api/services/`
- Pydantic models for all data shapes
- Format with `ruff format`, lint with `ruff check`

### Frontend
- TypeScript strict mode
- React Server Components by default, `"use client"` only when needed
- Tailwind CSS for styling (no CSS modules)
- Components in `src/components/`, pages in `src/app/`

### General
- Keep files under 500 lines — split into modules if larger
- Don't add features beyond what the issue asks for
- Run `scripts/run-checks.sh` before committing

## Key Patterns

- **No database**: Articles stored as JSON in Azure Blob Storage with a manifest index
- **Activity feed**: Read-through cache of GitHub API data (5-min TTL)
- **Agent coordination**: PO triages intake → creates prioritized issues → engineer picks up → opens PR → reviewer reviews → may request changes → engineer fixes → reviewer approves and merges → CI/CD deploys
- **Intake pipeline**: Scanning agents (tech lead, UX, triage) create `source/*` issues → PO triages and prioritizes → engineer works → reviewer gates quality
- **Per-role tool allowlists**: Non-code agents can't Write/Edit application code. Tech lead can only modify `config/` and `scripts/`. PM has read-only codebase access plus `gh` for managing the GitHub Project roadmap — no Write/Edit/git, no Glob/Grep. PM understands product through outcomes, not code. SRE has curl, az CLI, gh, and python3 for health checks and diagnostics — no Write/Edit.
- **PM↔PO feedback loop**: PM reviews `source/roadmap` issues for alignment. If misaligned, PM labels `pm/misaligned` with a comment. PO re-scopes before the engineer picks it up.
- **Full autonomy**: Agents handle the complete cycle. The human monitors and adjusts workflows, but does not manually merge or write code.

## Development

### Local Dev (Dev Server via SSH Tunnel)

The dev server is a remote Azure VM accessed via SSH tunnel. Agent Fishbowl shares nginx with Captain AI and other apps.

**Port Assignments:**
- API: port 8500 (uvicorn)
- Frontend: port 3010 (Next.js dev)

**Access URLs (from Mac via SSH tunnel at `localhost:8080`):**
- Frontend: `http://localhost:8080/fishbowl/`
- Activity: `http://localhost:8080/fishbowl/activity/`
- API: `http://localhost:8080/api/fishbowl/articles`
- Health: `http://localhost:8080/api/fishbowl/health`

**Quick Start:**
```bash
# API (from project root)
api/.venv/bin/uvicorn api.main:app --reload --port 8500

# Frontend (separate terminal)
cd frontend && npm run dev   # runs on port 3010

# Run article ingestion
api/.venv/bin/python -m scripts.ingest
```

**VS Code:** Open `agent-fishbowl.code-workspace`, use "Full Stack: Fishbowl" compound launch.

**Nginx config:** `/etc/nginx/sites-available/captain-ai` (fishbowl routes section)

### Running Standalone (no nginx)
```bash
# API
cd api && pip install -r requirements.txt
uvicorn api.main:app --reload --port 8500

# Frontend
cd frontend && npm install && npm run dev

# Both via Docker
docker-compose up

# Quality checks
scripts/run-checks.sh
```

### Running the Agent Loop
```bash
# Full dev cycle (PO → Engineer → Reviewer → merge)
scripts/run-loop.sh

# Scanning agents (tech lead + UX — run every 3-4 days)
scripts/run-scans.sh

# Triage human issues (run every 12-24h)
scripts/run-triage.sh

# PM strategic review (run weekly)
scripts/run-strategic.sh

# SRE health check (run every 4 hours)
scripts/run-sre.sh

# Individual agents
agents/pm.sh          # Evaluate goals + manage GitHub Project roadmap
agents/po.sh          # Triage intake + create issues from roadmap project
agents/engineer.sh    # Pick issue and implement
agents/reviewer.sh    # Review and merge PRs
agents/tech-lead.sh   # Set standards + create architecture issues
agents/triage.sh      # Validate human-created issues
agents/ux.sh          # Review product UX
agents/sre.sh         # Monitor system health
```

## Blob Storage Schema

```
articles/
  index.json              Feed manifest (article summaries)
  2026/02/{slug}.json     Individual articles
  sources.json            Source metadata
```

## The Human Role

The human (Frankie) is the engineering leader:
- Maintains `config/goals.md` (strategic objectives — the PM agent reads these to evolve the roadmap)
- Monitors the loop execution and agent quality
- Adjusts agent workflows, prompts, and guardrails
- Creates GitHub Apps for new agent identities
- Intervenes when agents are stuck or going sideways
- Does NOT write application code or manually merge PRs (agents handle the full cycle)
