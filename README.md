[![CI](https://github.com/YourMoveLabs/agent-fishbowl/actions/workflows/ci.yml/badge.svg)](https://github.com/YourMoveLabs/agent-fishbowl/actions/workflows/ci.yml)
[![Deploy](https://github.com/YourMoveLabs/agent-fishbowl/actions/workflows/deploy.yml/badge.svg)](https://github.com/YourMoveLabs/agent-fishbowl/actions/workflows/deploy.yml)
[![Issues](https://img.shields.io/github/issues/YourMoveLabs/agent-fishbowl)](https://github.com/YourMoveLabs/agent-fishbowl/issues)
[![PRs](https://img.shields.io/github/issues-pr/YourMoveLabs/agent-fishbowl)](https://github.com/YourMoveLabs/agent-fishbowl/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/YourMoveLabs/agent-fishbowl)](https://github.com/YourMoveLabs/agent-fishbowl/commits/main)

# Agent Fishbowl: Product Document

## What This Is

A self-sustaining software business built and operated entirely by AI agents in public. The project serves two purposes simultaneously:

1. **The Product**: A curated knowledge feed — technology, tools, and practices for building better software autonomously. The content is curated by the agent team because they find it actionable for their own project, not because it's trending.
2. **The Showcase**: A live, transparent window into how a team of AI agents builds, maintains, and evolves that product — visible through a public activity feed and a fully public GitHub repository.

The orchestration is the point. The product is the proof it works.

## Why This Exists

The industry knows how to use AI agents as solo coding assistants. What nobody is demonstrating publicly is a team of AI agents that builds a real business — orchestrating across a shared codebase the way an engineering leader manages a team, with role separation, a prioritized backlog, coordinated execution, code review, deployment, and continuous maintenance.

This project proves that capability in the open. The agents plan work, execute across their domains, review and deploy code, curate content they find useful for their own improvement, and eventually generate revenue. The value is in showing the full pattern functioning end-to-end, not in the complexity of any individual feature.

### Target Audience

- Engineering leaders and hiring managers evaluating AI-native development practices
- AI engineers curious about multi-agent orchestration patterns
- The broader developer community following the evolution of agentic workflows

## The Product: Curated Knowledge Feed

### What It Does

A curated feed of technology, tools, and practices for building better software autonomously. Content is ingested from sources the agent team selects, summarized by AI, and presented through a clean web interface with rich previews. The content domain is not fixed — the team curates what they find actionable for their own project, which naturally evolves over time.

### Core Features

- **Article Ingestion**: Pulls articles from configured sources (RSS feeds, blogs, publication APIs) on a scheduled cadence
- **AI Summarization**: Each article gets an AI-generated excerpt, key takeaways, and categorization
- **Rich Previews**: Display card for each article includes title, source, summary, relevant image/thumbnail, publish date, and link to original
- **Feed Interface**: Clean, responsive web UI that displays the curated feed with filtering and search
- **API Layer**: Backend API serving the feed data, managing ingestion state, and handling summarization pipeline

### Why This Product

- **Immediately legible**: Anyone visiting understands what they're looking at in seconds. No explanation needed.
- **Visually verifiable**: You can see when it's working (new articles appear, summaries make sense) and when it's broken
- **Self-reinforcing**: The product feeds back into the team's capabilities. Agents curate content that helps them build better software, which improves the product, which produces better content.
- **Cleanly separable domains**: Ingestion, summarization/processing, backend API, frontend UI, infrastructure/DevOps — each maps naturally to a distinct agent role
- **Generates ongoing work**: There are always new sources to add, UI improvements to make, edge cases in parsing, summarization quality to improve, tests to write, documentation to update. The PM agent will always have something reasonable to prioritize.

The product does not need to be architecturally complex. The complexity lives in the orchestration pattern, not the application. Even a minor feature — adding category filters, improving card layouts, adding a new content source — requires agents to coordinate through the Git workflow: branching, committing, reviewing, and deploying together. That coordination is the point.

## The Showcase: Agent Fishbowl

### The Experience

Visitors see two things:

1. **The Product** — the live AI news feed, functioning as a real application
2. **The Activity Feed** — a real-time(ish) stream of what the agents are doing: planning sessions, task pickups, commits, PR reviews, deployments, monitoring alerts, and fixes. Think of it as a read-only Slack channel for an AI engineering team.

The GitHub repository is fully public. Every issue, PR, commit, comment, review, and agent interaction is visible and inspectable. The activity feed is a curated, human-readable view of that underlying repository activity.

### What People Should Take Away

- This person knows how to define outcomes and let agents figure out execution
- This person can set up a repeatable workflow where work is planned, executed, reviewed, and deployed by agents
- This person understands the orchestration layer: how to structure agent roles, set guardrails, and intervene when things go sideways
- This person operates like an engineering leader, not just a developer who uses Copilot

## Agent Architecture

There are three distinct modes of agent operation running against this codebase. Together they form the complete pattern: strategic planning, coordinated execution, and autonomous maintenance.

### 1. The Product Manager Agent

**Mode**: Scheduled, strategic cadence (e.g., daily or every 48 hours)

**Responsibility**: Owns the backlog. Reviews the current state of the product, evaluates what's been accomplished, identifies what needs attention, and prioritizes the next body of work. Creates and updates GitHub Issues with clear descriptions and acceptance criteria.

**Inputs**: The product roadmap/goals (a lightweight document maintained by the human), current state of the codebase and product, recent activity and completed work.

**Outputs**: Groomed and prioritized backlog items as GitHub Issues.

### 2. The Engineering Team Agents

**Mode**: Task-driven, triggered by backlog items on a working cadence

**Responsibility**: Pick up prioritized work, plan the approach, execute across their respective domains, commit code, open PRs, and participate in review. Each agent owns a domain area:

- **Frontend Agent**: UI components, styling, user-facing features
- **Backend Agent**: API endpoints, data models, business logic
- **Ingestion Agent**: Data pipeline, source connectors, content processing
- **DevOps Agent**: CI/CD, deployment, infrastructure, monitoring setup

**Inputs**: A prioritized issue from the backlog with acceptance criteria.

**Outputs**: Branches, commits, pull requests, code reviews, and working software.

### 3. The Continuous Maintenance Agent

**Mode**: Autonomous, running on a lightweight scheduled loop independent of the task-driven workflow

**Responsibility**: The site reliability engineer. Monitors the health of the deployed application and the repository. Catches regressions, investigates CI failures, flags documentation drift, identifies test coverage gaps, and proposes fixes. Does not wait for the PM to prioritize work — it keeps the lights on.

**Inputs**: CI/CD status, deployment health, test results, code quality signals.

**Outputs**: Issues for discovered problems, PRs for fixes, comments/alerts on existing PRs, status reports.

## The Human Role

The human (Frankie) operates as a board member, not a manager:

- **Sets strategic direction** via `config/goals.md` — mission, goals, constraints, and trade-off guidance that the PM agent consumes daily
- **Defines success criteria** via `config/objectives.md` — time-bounded objectives with signals the PM evaluates to assess whether shipped work actually serves the goals
- **Reviews monthly** — reads PM signal reports, adjusts objectives when the project learns something new about what works
- **Adjusts agent capabilities** via the harness — tuning roles, refining prompts, adding tools, improving infrastructure
- **Intervenes when agents are stuck** — the remediation story is as important as the success story
- **Narrates the journey** through LinkedIn posts, blog entries, and discussions

The human does not write application code, approve deployments, or manage daily work. The PM handles strategic prioritization, the PO manages the backlog, and the engineering team executes autonomously.

## Cadence and Cost Management

Agents operate on deliberate intervals, not continuously, to manage token costs:

- **PM Agent**: Runs once every 24-48 hours
- **Engineering Team**: Executes in focused bursts, perhaps 1-2 task cycles per day
- **Continuous Agent**: Lightweight monitoring checks on a frequent schedule (e.g., every few hours), with heavier analysis less frequently

The exact cadences will be tuned based on cost and activity levels. The goal is enough visible activity that the fishbowl feels alive without burning money on unnecessary runs.

## Success Criteria

### The Product Works
- The AI news feed is live and accessible
- New content appears regularly with quality summaries
- The UI is clean and responsive
- The API is stable

### The Orchestration Pattern Is Visible
- The public activity feed shows a clear stream of agent work
- The GitHub repo tells a legible story through issues, PRs, commits, and reviews
- Different agent roles are distinguishable in their contributions
- The end-to-end pattern is evident: planning -> execution -> review -> deployment -> working product

### The Narrative Lands
- A hiring manager visiting for 5 minutes understands what they're seeing
- The repo demonstrates engineering leadership patterns, not just code generation
- Failures, recoveries, and human interventions are visible and tell a good story
- The project stands apart from every other "I built X with AI" demo by showing the full plan-execute-review-deploy pattern with a team of agents

## What This Document Is For

This product doc defines the what and why. It will be handed off to a Claude Code agent to generate a detailed implementation plan covering: repository structure, technology choices, agent workflow definitions, the activity feed architecture, deployment strategy, and a phased build plan.

The implementation plan is where the how gets decided.
