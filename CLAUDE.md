# Agent Fishbowl — Project Context

## Overview

Agent Fishbowl is an AI-curated news feed built and maintained by a team of AI agents. The project demonstrates multi-agent orchestration in the open — every issue, PR, commit, and review is done by agents coordinating through GitHub.

**Repository**: `fbomb111/agent-fishbowl` (public)
**Main Branch**: `main`

## Architecture

- **Backend**: FastAPI (Python 3.12) — `api/`
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS — `frontend/`
- **Storage**: Azure Blob Storage (articles as JSON, no database)
- **Activity Feed**: GitHub API (cached by FastAPI) — agents' GitHub activity IS the data
- **Agent Runtime**: Claude Code CLI sessions with role-specific prompts
- **Hosting**: Azure Container Apps (API) + Azure Static Web Apps (frontend)

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
  ROADMAP.md            Product vision (PM agent reads + updates)
  goals.md              Strategic goals (PM agent reads)
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
  pm.sh                 Product Manager — strategic roadmap (Phase 3)
  prompts/              Role-specific prompt files
  logs/                 Run logs (gitignored)
scripts/                Deterministic operations
  run-loop.sh           Dev loop (PO → Engineer → Reviewer)
  run-scans.sh          Scanning agents (Tech Lead + UX)
  run-triage.sh         Triage human issues
  run-checks.sh         All quality checks (ruff + tsc + eslint + conventions)
  create-branch.sh      Create branch from issue number
  lint-conventions.sh   Convention checks with agent-friendly errors
  setup-labels.sh       Create GitHub labels (idempotent)
.claude/commands/       Claude Code skills (AI-guided workflows)
  pick-issue.md         Find + claim highest-priority issue
  open-pr.md            Create draft PR with proper format
.github/workflows/      CI + agent workflows
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
| `status/in-progress` | An agent is working on this |
| `status/blocked` | Cannot proceed — needs human input |
| `status/needs-info` | Needs more information from reporter |
| `review/approved` | Reviewer approved this PR |
| `review/changes-requested` | Reviewer requested changes |
| `agent-created` | Created by an agent (not human) |

## Agent Team

| Role | Identity | Cadence | One-liner |
|------|----------|---------|-----------|
| **PO** | `fishbowl-po[bot]` | Every 24-48h | Central intake funnel — triages all inputs into a prioritized backlog |
| **Engineer** | `fishbowl-engineer[bot]` | Part of dev loop | Picks issues, implements code, opens PRs |
| **Reviewer** | `fishbowl-reviewer[bot]` | Part of dev loop | Reviews PRs, approves+merges or requests changes |
| **Tech Lead** | `fishbowl-techlead[bot]` | Every 3-4 days | Sets technical standards, identifies architecture needs |
| **PM** | `fishbowl-pm[bot]` | Weekly (Phase 3) | Strategic goals and roadmap evolution |
| **Triage** | `fishbowl-triage[bot]` | Every 12-24h | Validates human-created issues |
| **UX** | `fishbowl-ux[bot]` | Weekly | Reviews product UX, creates improvement issues |

### Information Flow

All roads lead to the PO. No agent bypasses the PO to create work for the engineer.

```
PM (strategy) → updates ROADMAP.md → PO (tactical) reads roadmap + source/* intake → backlog
Tech Lead, UX, Triage → create source/* intake issues → PO triages → backlog
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
| `run-loop.sh` | Dev loop (PO → Engineer → Reviewer) | Manually or via cron (every 24-48h) |
| `run-scans.sh` | Scanning agents (Tech Lead + UX) | Every 3-4 days |
| `run-triage.sh` | Triage human-created issues | Every 12-24h |
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
- **Per-role tool allowlists**: Non-code agents can't Write/Edit application code. Tech lead can only modify `config/` and `scripts/`. PM can only modify `config/`.
- **Full autonomy**: Agents handle the complete cycle. The human monitors and adjusts workflows, but does not manually merge or write code.

## Development

### Running Locally
```bash
# API
cd api && pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

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

# Individual agents
agents/po.sh          # Triage intake + create issues from roadmap
agents/engineer.sh    # Pick issue and implement
agents/reviewer.sh    # Review and merge PRs
agents/tech-lead.sh   # Set standards + create architecture issues
agents/triage.sh      # Validate human-created issues
agents/ux.sh          # Review product UX
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
- Maintains `config/goals.md` (strategic objectives) and `config/ROADMAP.md` (until PM agent is built in Phase 3)
- Monitors the loop execution and agent quality
- Adjusts agent workflows, prompts, and guardrails
- Creates GitHub Apps for new agent identities
- Intervenes when agents are stuck or going sideways
- Does NOT write application code or manually merge PRs (agents handle the full cycle)
