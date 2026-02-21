# Agent Fishbowl — Project Context

## Overview

Agent Fishbowl is a self-sustaining software business built and operated by a team of AI agents. The product is a curated knowledge feed — technology, tools, and practices for building better software autonomously. Every issue, PR, commit, and review is done by agents coordinating through GitHub. The content is curated by the team because they find it actionable for their own project.

**Project Repo**: `YourMoveLabs/agent-fishbowl` (public) — application code, project context, workflow stubs
**Harness Repo**: `YourMoveLabs/agent-harness` (public) — agent prompts, runner, scripts, composite action
**Main Branch**: `main`

### GitHub Project (Roadmap)

The product roadmap is managed as a GitHub Project:

```
PROJECT_NUMBER: 1
OWNER: YourMoveLabs
```

Each roadmap item has fields: **Priority** (P1/P2/P3), **Goal**, **Phase**, and **Roadmap Status** (Proposed/Active/Done/Deferred). The PM agent manages roadmap items; the PO agent creates issues from them.

## Architecture

- **Backend**: FastAPI (Python 3.12) — `api/`
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS — `frontend/`
- **Storage**: Azure Blob Storage (articles as JSON, no database)
- **Activity Feed**: GitHub API (cached by FastAPI) — agents' GitHub activity IS the data
- **Agent Runtime**: Claude Code CLI sessions with role-specific prompts
- **Hosting**: Azure Container Apps (API) + Azure Static Web Apps (frontend)

## Agent Deployment

Agents are deployed as GitHub Actions workflows running on the self-hosted runner. They run from `main` — the same branch they push to. There is no promotion gate; safety comes from automated rollback and SRE remediation.

**Workflows** (all in `.github/workflows/`):

| Workflow | Agents | Triggers | Protection |
|----------|--------|----------|------------|
| `agent-triage.yml` | Triage | `issues.opened` + daily + manual | agent-created filter |
| `agent-product-owner.yml` | PO | PM/reviewer dispatch + 2x daily | Concurrency group |
| `agent-engineer.yml` | Engineer | PO/reviewer dispatch + PR merged + CI | chain_depth ≤ 5, concurrency |
| `agent-ops-engineer.yml` | Ops Engineer | PO dispatch + issue labeled | concurrency (reusable) |
| `agent-reviewer.yml` | Reviewer | PR dispatch + 12h sweep | Max 3 rounds/PR, concurrency |
| `agent-strategic.yml` | PM | Daily 06:00 + manual | Concurrency group |
| `agent-scans.yml` | Tech Lead | Daily full scan | Concurrency group |
| `agent-tech-lead-*.yml` | Tech Lead | Daily specialized scans (11 jobs) | Per-job concurrency |
| `agent-site-reliability.yml` | SRE | `repository_dispatch` (azure-alert) + 4h schedule | Concurrency group |
| `agent-content-creator.yml` | Content Creator | Daily 10am UTC + manual | Concurrency group |
| `agent-user-experience.yml` | UX | PO dispatch + manual | concurrency (reusable) |
| `agent-product-analyst.yml` | Product Analyst | Daily + manual | concurrency (reusable) |
| `agent-financial-analyst.yml` | Financial Analyst | Daily + manual | concurrency (reusable) |
| `agent-marketing-strategist.yml` | Marketing Strategist | Weekly + manual | concurrency (reusable) |
| `agent-qa-analyst.yml` | QA Analyst | Daily + manual | Concurrency group |
| `agent-customer-ops.yml` | Customer Ops | Every 4h + manual | concurrency (reusable) |
| `agent-human-ops.yml` | Human Ops | Weekly + manual | concurrency (reusable) |
| `agent-escalation-lead.yml` | Escalation Lead | Weekly + disputes | concurrency (reusable) |

**Event Chain:**
```
Human/PM creates issue → Triage → PO prioritizes → dispatches Engineer
Engineer works issue → opens PR → Reviewer reviews (max 3 rounds)
  → Approve → PR merged → dispatches Engineer for next issue
  → Request changes → dispatches Engineer to fix
PM reviews daily → adjusts roadmap → dispatches PO
```

**Safety Controls:**
- Concurrency groups prevent parallel runs of the same agent
- Chain depth limit (max 5) prevents runaway dispatch cascading
- Review round limit (max 3 per PR) prevents reviewer loops
- Fork guard on reviewer (security: self-hosted runner)
- Auto-rollback on deploy failure (Container App revision rollback)
- `.harness/scripts/dispatch-agent.sh` handles agent-to-agent chaining (from harness checkout)

**Environment:** Agent .env is staged at `~/.config/agent-harness/.env` on the runner. The harness composite action copies it into the checkout. PEM keys are at `~/.config/agent-harness/*.pem`.

### Alert Bridge (Azure Function → GitHub)

Real-time alerting bridge: Azure Monitor detects problems → fires alert → Action Group webhooks to an Azure Function → Function dispatches `azure-alert` to GitHub → `agent-sre.yml` triggers with alert context.

**Flow:**
```
Container App metrics → Alert Rule fires → Action Group webhook
  → func-fishbowl-alert-bridge (Azure Function)
    → reads fishbowl-sre PEM from Key Vault (via Managed Identity)
      → mints JWT → exchanges for installation access token
        → POST repos/{repo}/dispatches (event_type: azure-alert)
          → agent-sre.yml triggers → run-sre.sh routes to playbooks/Claude
```

**Auth:** Uses `fishbowl-sre` GitHub App (App ID: `2868629`, Installation ID: `110315536`). PEM key stored in Key Vault as `fishbowl-sre-pem`. No PATs — tokens are short-lived installation tokens minted per-invocation.

**Azure Resources** (all in `rg-agent-fishbowl`):

| Resource | Name | Purpose |
|----------|------|---------|
| Function App | `func-fishbowl-alert-bridge` | HTTP trigger, parses alert, dispatches to GitHub |
| Key Vault | `kv-fishbowl-sre` | Stores SRE GitHub App PEM key (`fishbowl-sre-pem`) |
| App Insights | `fishbowl-appinsights` | Function App telemetry |
| Storage Account | `stfuncfishbowl` | Functions runtime storage |
| Action Group | `fishbowl-alerts` | Webhook to Function App |

**Alert Rules:**

| Alert | Metric | Condition | Window | Severity |
|-------|--------|-----------|--------|----------|
| `fishbowl-api-5xx` | Requests (5xx) | > 5 total | 5 min | Sev 1 |
| `fishbowl-container-restarts` | RestartCount | > 2 total | 1 hour | Sev 2 |

**Function Code:** `functions/alert_bridge/__init__.py`
- Parses Azure Monitor Common Alert Schema
- Authenticates as `fishbowl-sre[bot]` GitHub App (PEM from Key Vault → JWT → installation token)
- Falls back to local PEM file via `GITHUB_APP_SRE_KEY_PATH` for local dev
- Deploy: `cd functions && func azure functionapp publish func-fishbowl-alert-bridge --python`

## Project Structure

```
api/                    FastAPI backend
  main.py               App entry point + health check endpoint
  config.py             Settings (env vars)
  routers/              API route handlers
    articles.py         Articles CRUD + ingest trigger
    activity.py         Activity feed, agent status, usage stats
    blog.py             Blog post management (list, get, create, update, delete)
    feedback.py         User feedback submission
    goals.py            Goals dashboard data
    stats.py            Team statistics
  services/             Business logic
    blob_storage.py     Azure Blob Storage client
    cache.py            In-memory cache with TTL
    feedback.py         Feedback persistence
    github_activity.py  GitHub activity feed
    github_events.py    GitHub event parsing
    github_status.py    Agent status from GitHub
    goals.py            Goals data aggregation
    goals_metrics.py    Goals metrics computation
    goals_parser.py     Goals markdown parser
    goals_roadmap.py    Roadmap status for goals
    http_client.py      Shared HTTP client
    llm.py              LLM integration (article analysis)
    stats.py            Team statistics aggregation
    usage_storage.py    Usage tracking storage
    ingestion/          Article ingestion pipeline
      orchestrator.py   Ingestion orchestration
      rss.py            RSS feed fetching
      scraper.py        Web page scraping
      analyzer.py       Content analysis
      dedup.py          Duplicate detection
  models/               Pydantic models
    article.py          Article data models
    blog.py             Blog post models
    feedback.py         Feedback models
frontend/               Next.js frontend
  src/app/              Pages (App Router)
    page.tsx            Home — article feed
    activity/page.tsx   Activity feed (agent GitHub activity)
    blog/page.tsx       Blog listing
    blog/[slug]/page.tsx Blog post viewer
    feedback/page.tsx   Feedback form
    goals/page.tsx      Goals dashboard
    team/page.tsx       Team page
  src/components/       React components
  src/lib/              Shared utilities
    api.ts              API client
    agents.ts           Agent metadata
    constants.ts        App constants
    formatTokens.ts     Token formatting
    navigation.ts       Navigation helpers
    timeUtils.ts        Time formatting
config/                 Configuration
  agent-flow.yaml       Agent flow graph — SINGLE SOURCE OF TRUTH (v2 schema)
  sources.yaml          RSS feed sources
  goals.md              Strategic goals and trade-off guidance (human-maintained, PM reads)
  objectives.md         Time-bounded objectives with signals (human-maintained, PM evaluates)
  conventions.md        Technical standards (Tech Lead maintains)
  content-strategy.md   Content strategy (Content Creator reads)
  ux-standards.md       UX checklist (UX agent reads)
functions/              Azure Function (alert bridge)
  alert_bridge/         HTTP trigger: Azure Monitor → GitHub dispatch
  host.json             Functions runtime config
  requirements.txt      Python dependencies
docs/
  agent-flow.md         AUTO-GENERATED Mermaid diagram + tables (from agent-flow.yaml)
scripts/                Project-specific scripts
  validate-flow.py      Validate flow graph + generate diagram (CI enforced)
  health-check.sh       Full system health check (API, ingestion, deploys, GitHub)
  run-checks.sh         All quality checks (ruff + tsc + eslint + conventions)
  pre-commit.sh         Auto-fix + check + commit
  create-branch.sh      Create branch from issue number
  worktree-manager.sh   Manage git worktrees for concurrent sessions
  bump-harness.sh       Bump harness version across workflows
  git-cleanup.sh        Clean up merged branches
  capture-screenshots.sh  Capture page screenshots
  pr-risk-assess.sh     PR risk assessment
  qa-api-consistency.sh API consistency checks
  qa-api-vs-github.sh   API vs GitHub data comparison
  playbooks/            SRE automated remediation playbooks
    restart-api.sh      Auto-restart Container App revision
    rollback-api.sh     Roll back to previous Container App revision
    retrigger-ingest.sh Re-trigger ingest workflow
  seed_articles.py      Seed initial articles
  ingest.py             Article ingestion
.claude/commands/       Claude Code skills (AI-guided workflows)
  pick-issue.md         Find + claim highest-priority issue
  open-pr.md            Create PR with proper format
  add-agent.md          Add agent to fishbowl team
.github/workflows/      CI + agent deployment (thin stubs → harness)
  ci.yml                CI: lint, typecheck, flow validation + diagram freshness
  deploy.yml            Deploy API + frontend to Azure
  ingest.yml            Article ingestion pipeline
  release.yml           Release management
  reusable-agent.yml    Shared agent runner (role or entry-point)
  pr-manager.yml        PR risk assessment + auto-approve
  qa-triage.yml         Post-deploy QA triage
  project-auto-add.yml  Auto-add issues to GitHub Project
  human-escalation.yml  Human escalation workflow
  maintenance.yml       Maintenance tasks
  agent-triage.yml      Triage (issues.opened + daily)
  agent-product-owner.yml PO (dispatch + 2x daily)
  agent-engineer.yml    Engineer (dispatch + PR merge + CI)
  agent-ops-engineer.yml Ops Engineer (dispatch + issue labeled)
  agent-reviewer.yml    Reviewer (PR dispatch + 12h sweep)
  agent-strategic.yml   PM (daily schedule)
  agent-scans.yml       Tech Lead: full scan (daily)
  agent-tech-lead-*.yml Tech Lead specialized jobs (11 workflows)
  agent-site-reliability.yml SRE (every 4h + azure alerts)
  agent-content-creator.yml  Content Creator (daily)
  agent-user-experience.yml  UX (on-demand via PO dispatch)
  agent-product-analyst.yml  Product Analyst (daily)
  agent-financial-analyst.yml Financial Analyst (daily)
  agent-marketing-strategist.yml Marketing Strategist (weekly)
  agent-qa-analyst.yml  QA Analyst (daily)
  agent-customer-ops.yml Customer Ops (every 4h)
  agent-human-ops.yml   Human Ops (weekly)
  agent-escalation-lead.yml Escalation Lead (weekly + disputes)
```

### Harness Repo (YourMoveLabs/agent-harness)

The harness is checked out to `.harness/` during workflow runs via composite action.

```
action.yml              Composite action (the bridge between repos)
agents/
  run-agent.sh          Core runner (identity, tools, Claude invocation)
  prompts/{role}.md     Generic role prompts (read CLAUDE.md for project context)
config/
  roles.json            Central role configuration (tools, partials, instances)
scripts/
  dispatch-agent.sh     Agent-to-agent chaining (repository_dispatch)
  run-sre.sh            SRE controller (playbook routing + Claude escalation)
  run-scans.sh          Tech Lead + UX scan orchestration
  run-strategic.sh      PM strategic review orchestration
  run-triage.sh         Triage pre-check orchestration
  find-issues.sh        Agent tool: issue queries
  find-prs.sh           Agent tool: PR queries
  check-duplicates.sh   Agent tool: duplicate detection
  project-fields.sh     Agent tool: GitHub Project field mapping
  roadmap-status.sh     Agent tool: roadmap status
  workflow-status.sh    Agent tool: workflow queries
  file-stats.sh         Agent tool: codebase metrics
  setup-labels.sh       Label bootstrapping
  lint-conventions.sh   Convention enforcement
docs/philosophy.md      Full thesis on why this exists
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
| `role/engineer` | Routed to engineer agent for code changes |
| `role/ops` | Routed to ops-engineer agent for Azure operations |
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
| `harness/request` | Agent needs a harness capability (tool, permission, config) |
| `agent-created` | Created by an agent (not human) |

## Agent Team

| Role | Identity | Cadence | One-liner |
|------|----------|---------|-----------|
| **PO** | `fishbowl-po[bot]` | Event-driven + 2x daily | Central intake funnel — triages all inputs into a prioritized backlog |
| **Engineer** | `fishbowl-engineer[bot]` | Event-driven (dispatch + PR merge) | Picks issues, implements application code, opens PRs |
| **Ops Engineer** | `fishbowl-ops-engineer[bot]` | Event-driven (dispatch + unblock) | Azure resource management via `az` CLI — scaling, env vars, ACR, health checks |
| **Reviewer** | `fishbowl-reviewer[bot]` | Event-driven + 12h | Reviews PRs, approves+merges or requests changes |
| **Tech Lead** | `fishbowl-techlead[bot]` | Daily (11 specialized jobs) | Sets technical standards, identifies architecture/debt/security needs |
| **PM** | `fishbowl-pm[bot]` | Daily | Strategic goals and GitHub Project roadmap management |
| **Triage** | `fishbowl-triage[bot]` | Event-driven (issues.opened) + daily | Validates human-created issues |
| **UX** | `fishbowl-ux[bot]` | On-demand (PO dispatch) | Reviews product UX, creates improvement issues |
| **SRE** | `fishbowl-sre[bot]` | Every 4h + alerts | Monitors system health, files issues for problems |
| **Content Creator** | `fishbowl-content-creator[bot]` | Daily 10am UTC | Generates one blog post per day via Captain AI headless API |
| **Product Analyst** | `fishbowl-product-analyst[bot]` | Daily | Analyzes product metrics and usage patterns |
| **Financial Analyst** | `fishbowl-financial-analyst[bot]` | Daily | Tracks costs, revenue signals, and financial health |
| **Marketing Strategist** | `fishbowl-marketing-strategist[bot]` | Weekly | Marketing strategy and growth analysis |
| **QA Analyst** | `fishbowl-qa-analyst[bot]` | Daily | Deep QA sweeps, post-deploy verification |
| **Customer Ops** | `fishbowl-customer-ops[bot]` | Every 4h | Customer feedback monitoring and response |
| **Human Ops** | `fishbowl-human-ops[bot]` | Weekly | Human escalation coordination |
| **Escalation Lead** | `fishbowl-escalation-lead[bot]` | Weekly + disputes | Resolves agent disagreements and stuck situations |

### Information Flow

All roads lead to the PO. No agent bypasses the PO to create work for the engineer.

```
PM (strategy) → manages GitHub Project roadmap → PO (tactical) reads project items + source/* intake → backlog
PM reviews PO's source/roadmap issues → pm/misaligned if off-target → PO re-scopes
Tech Lead, UX, QA, Product Analyst, Triage → create source/* intake issues → PO triages → backlog
SRE → monitors health, creates source/sre issues for failures → PO triages → backlog
Engineer claims issues → opens PR → Reviewer merges (or backlogs via source/reviewer-backlog → PO)
Escalation Lead → resolves agent disputes and stuck situations
```

## Agent Coordination Rules

- **Never pick an assigned issue.** If it has an assignee, skip it.
- **Never modify another agent's open PR.** If they have a branch, leave it alone.
- **One task per run.** Pick one issue or fix one PR's feedback, not both.
- **Reviewer merges.** Only the reviewer agent approves and squash-merges PRs. No other agent merges.
- **Engineer creates ready PRs** (not drafts) so the reviewer can act on them.
- **Max 3 review rounds.** If a PR still has issues after 3 rounds, the reviewer either approves with caveats, files a future-work ticket, or closes and backlogs.
- **Comment your progress.** When you start an issue, comment. When you open a PR, comment on the issue with a link.
- **All intake flows through the PO.** Scanning agents (tech lead, UX, triage) create issues with `source/*` labels. Only the PO sets final priority.
- **Scanning agents never set `priority/high`.** They use `priority/medium`. The PO decides what's urgent.
- **Preserve `source/*` labels.** These track where issues originated. Don't remove them.

## Agent Flow Graph (`config/agent-flow.yaml`)

The flow graph is the **single source of truth** for how agents interact. CI validates it against actual workflow files and blocks merges when they drift.

**Schema version**: v2

### Required Fields (per agent)

| Field | Type | Description |
|-------|------|-------------|
| `workflow` | string | GitHub Actions workflow filename |
| `type` | `custom` \| `reusable` | Whether it uses `reusable-agent.yml` or has custom steps |
| `harness_ref` | string | Harness version pin (e.g., `@v1.2.0`, `@main`) |
| `timeout` | int | Job timeout in minutes |
| `permissions` | map | Required GitHub token permissions |
| `concurrency` | map | Concurrency group config (omit for reusable — inherits) |
| `triggers` | list | Event triggers matching the workflow's `on:` block |
| `dispatches` | list | Outbound edges to other agents |

### Dispatch `location` Field

| Value | Meaning | Validated? |
|-------|---------|-----------|
| `post_step` | Happens in a workflow step (YAML) | Yes — CI cross-checks |
| `in_agent` | Happens inside Claude session via `scripts/dispatch-agent.sh` | No — informational only |

### Multi-Job Agents

Agents like `tech-lead` run multiple scheduled jobs, each with its own workflow file. Instead of one `workflow:` field, they use a `jobs:` map:

```yaml
tech-lead:
  role: tech-lead
  harness_ref: "@main"
  jobs:
    scans:
      workflow: agent-scans.yml
      triggers: [...]
      dispatches: [...]
    architecture-review:
      workflow: agent-tech-lead-architecture.yml
      # ...
```

Each job is validated independently. Dispatch targets can reference job IDs (e.g., `scans`).

### Commands

```bash
# Validate flow graph against workflows (CI runs this)
python scripts/validate-flow.py --validate

# Validate with warnings as errors
python scripts/validate-flow.py --validate --strict

# Regenerate diagram (must commit the result)
python scripts/validate-flow.py --mermaid -o docs/agent-flow.md

# Both at once
python scripts/validate-flow.py --validate --mermaid -o docs/agent-flow.md
```

### CI Enforcement

The `flow-validation` CI job runs two checks:
1. **Validation**: All 10+ checks pass (schedules, triggers, permissions, concurrency, dispatch targets, etc.)
2. **Diagram freshness**: The committed `docs/agent-flow.md` matches what the generator produces

### When Adding or Modifying Agents

1. Update `config/agent-flow.yaml` **first**
2. Create/modify the workflow file
3. Run `python scripts/validate-flow.py --validate` to check consistency
4. Run `python scripts/validate-flow.py --mermaid -o docs/agent-flow.md` to regenerate the diagram
5. Commit all three files together

## Available Tools

### Project Scripts (`scripts/`)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate-flow.py` | Validate flow graph + generate Mermaid diagram | After modifying agents/workflows |
| `health-check.sh` | Full system health check (API, ingestion, deploys, GitHub) | SRE runs |
| `run-checks.sh` | Quality checks (ruff + tsc + eslint + conventions) | Before every PR |
| `create-branch.sh` | Create named branch from issue number | When starting work on an issue |
| `playbooks/restart-api.sh` | Auto-restart Container App revision | Automated remediation |
| `playbooks/rollback-api.sh` | Roll back to previous Container App revision | Automated remediation |
| `playbooks/retrigger-ingest.sh` | Re-trigger ingest workflow | Automated remediation |

### Harness Scripts (via `.harness/scripts/` in CI, or `$HARNESS_ROOT/scripts/` locally)

Agent tools, orchestration scripts, and infrastructure scripts live in the harness repo (`YourMoveLabs/agent-harness`). During workflow runs, they're available at `.harness/scripts/`. See the harness README for the full list.

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

### Running Agents Locally

Requires both repos cloned side by side:

```bash
# Clone both repos
git clone git@github.com:YourMoveLabs/agent-harness.git
git clone git@github.com:YourMoveLabs/agent-fishbowl.git

# Run an individual agent
cd agent-fishbowl
HARNESS_ROOT=../agent-harness PROJECT_ROOT=$(pwd) ../agent-harness/agents/run-agent.sh engineer

# Run orchestration scripts
HARNESS_ROOT=../agent-harness PROJECT_ROOT=$(pwd) ../agent-harness/scripts/run-scans.sh
HARNESS_ROOT=../agent-harness PROJECT_ROOT=$(pwd) ../agent-harness/scripts/run-sre.sh
```

In production, agents run via GitHub Actions workflows which use the composite action to check out the harness automatically.

### Worktree Isolation (Concurrent Claude Code Sessions)

When running multiple Claude Code sessions on the dev server, each session MUST use a separate worktree to avoid file conflicts. The main checkout stays on `main` and is never worked in directly.

**Directory layout:**
```
/home/fcleary/projects/
  agent-fishbowl/           ← main checkout (stays on main, shared .git database)
  agent-fishbowl-trees/     ← worktree container
    agent-1/                ← worktree 1 (own branch, own files, .env symlinked)
    agent-2/                ← worktree 2
    ...
```

**Managing worktrees:**
```bash
# Create 5 agent worktrees (one-time setup)
scripts/worktree-manager.sh setup 5

# Create a named worktree
scripts/worktree-manager.sh create my-feature feat/issue-42

# List all worktrees
scripts/worktree-manager.sh list

# Remove one worktree
scripts/worktree-manager.sh remove agent-3

# Remove all worktrees
scripts/worktree-manager.sh clean
```

**Key rules:**
- Open each Claude Code window in a different `agent-fishbowl-trees/agent-N/` directory
- Git operations (branch, commit, push) are fully isolated per worktree
- `.env` is symlinked from the main checkout — one file, always in sync
- The same branch cannot be checked out in two worktrees simultaneously (git enforces this)
- To reset a worktree to latest main: `git fetch origin && git checkout --detach origin/main`

## Infrastructure Reference

```
API Container App:  ca-agent-fishbowl-api
Resource Group:     rg-agent-fishbowl
API Health:         https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/health
Articles Endpoint:  https://ca-agent-fishbowl-api.victoriousground-9f7e15f3.eastus.azurecontainerapps.io/api/fishbowl/articles
Repository:         YourMoveLabs/agent-fishbowl
Ingest Workflow:    ingest.yml
Deploy Workflow:    deploy.yml
```

## Blob Storage Schema

```
articles/
  index.json              Feed manifest (article summaries)
  2026/02/{slug}.json     Individual articles
  sources.json            Source metadata
```

## The Human Role

The human operates as a board member, not a manager. They interact at two layers:

1. **The Harness** (`agent-harness` repo): Building and improving the team's capabilities (prompts, tools, workflows, infrastructure)
2. **Strategic Governance**: Setting direction via goals and objectives, reviewing PM signal reports monthly

**What the human does:**
- Sets strategic direction via `config/goals.md` — mission, goals, constraints, trade-off guidance
- Defines success criteria via `config/objectives.md` — time-bounded objectives with signals the PM evaluates
- Reviews monthly — reads PM signal reports, adjusts objectives when the project learns what works
- Adjusts agent capabilities via the harness — tuning roles, refining prompts, adding tools
- Responds to `harness/request` issues when agents need capabilities they don't have
- Intervenes when agents are stuck — the remediation story is as important as the success story

**What the human does NOT do:**
- Write application code or manually merge PRs (agents handle the full cycle)
- Manage daily work — the PM handles strategic prioritization, the PO manages the backlog
- Bypass the agent team to make code changes directly

**Escalation**: When an agent is blocked by a missing capability (tool, permission, config), it creates an issue with the `harness/request` label. The human builds the capability, updates the harness, and the agent's work resumes.

For the full philosophy, see `docs/philosophy.md` in the [agent-harness](https://github.com/YourMoveLabs/agent-harness) repo.
