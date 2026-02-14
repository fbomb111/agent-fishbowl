# Agent Fishbowl — Product Roadmap

> This document is maintained by the human (Frankie) and consumed by the PM Agent.
> The PM Agent reads this to understand priorities and create backlog items.

## Current Phase: Foundation

### Priority 1: Core News Feed
- Ingest articles from RSS sources defined in `config/sources.yaml`
- AI-generate summaries (2-3 sentences) and key takeaways for each article
- Categorize articles (AI, ML, agents, research, startups, etc.)
- Display articles in a responsive card grid on the homepage
- Support filtering by category

### Priority 2: Activity Feed
- Surface agent activity from GitHub (issues, PRs, commits, reviews)
- Display in the Fishbowl page with agent identity and timestamps
- Color-code by agent role (PM, frontend, backend, ingestion, SRE)

### Priority 3: Polish
- Clean, professional landing page that explains what visitors are seeing
- Mobile-responsive design
- Dark mode support
- Fast page loads (< 2s)

## Quality Standards
- All code must have type hints (Python) or TypeScript types
- Lint must pass (ruff for Python, eslint for TypeScript)
- PRs must include a clear description of what changed and why
- Tests for business logic (ingestion, summarization, API endpoints)

## Out of Scope (For Now)
- User accounts or authentication
- Comments or social features
- Real-time WebSocket updates
- Multiple languages
