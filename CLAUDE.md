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
- **Agent Runtime**: GitHub Agentic Workflows (Claude engine)
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
  ROADMAP.md            Product vision (PM agent reads this)
.github/workflows/      CI + agent workflows
```

## Agent Roles

Each agent has a specific domain and runs via GitHub Agentic Workflows:

| Agent | Domain | Trigger |
|-------|--------|---------|
| PM Agent | Backlog grooming, issue creation | Scheduled (Mon/Wed/Fri) |
| Frontend Agent | UI components, pages, styling | Issue labeled `agent/frontend` |
| Backend Agent | API endpoints, services, models | Issue labeled `agent/backend` |
| Ingestion Agent | RSS fetching, AI summarization | Issue labeled `agent/ingestion` |
| SRE Agent | CI health, deployment monitoring | Scheduled (every 6 hours) |

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

## Key Patterns

- **No database**: Articles stored as JSON in Azure Blob Storage with a manifest index
- **Activity feed**: Read-through cache of GitHub API data (5-min TTL)
- **Agent coordination**: PM creates issues with labels → engineering agents pick up labeled issues → open draft PRs → human reviews and merges
- **Safe outputs only**: Agents create draft PRs (never merge), create issues, add comments. All writes go through GitHub's safe-output system.

## Development

```bash
# API
cd api && pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Both via Docker
docker-compose up
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
- Maintains `config/ROADMAP.md` (product vision)
- Reviews and merges all PRs (final quality gate)
- Adjusts agent workflows and guardrails
- Does NOT write application code
