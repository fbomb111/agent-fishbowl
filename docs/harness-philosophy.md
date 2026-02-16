# Agent Harness — Philosophy & Vision

## The Thesis

**Humans don't need code access for AI agents to be effective.**

Agents can autonomously build, maintain, and ship software. The human's role
is not to write code alongside them — it's to build the right team, give them
the right tools, and point them in the right direction. Like an engineering
manager.

The human interacts at two layers:

1. **The Harness** — Building and improving the team's capabilities (tools,
   prompts, infrastructure)
2. **Project Management** — Directing work and providing feedback (GitHub
   issues, PR comments, project boards)

Neither layer requires code access to the project.

## What This Demonstrates

When someone visits the project repo, they see:

- **Every code commit** is from a bot account (merged by the reviewer bot)
- **Every PR** is created, reviewed, and merged by agents
- **Issues** are a mix of agent-created (from scans, reviews, roadmap) and
  human-created (feature requests, feedback)
- **The human's presence** is visible only in issue comments, PR feedback,
  and goal-setting — never in code

The git history IS the proof. No human code commits. The agents built it.

## The Mental Model

```
+----------------------------------------------------------+
|  THE HUMAN (Engineering Manager)                         |
|                                                          |
|  Works in: Harness repo                                  |
|  Interacts via: GitHub Issues, PR comments, Projects     |
|  Never touches: Application code                         |
+------------+----------------------------+----------------+
             |                            |
     builds/improves              directs/feedback
             |                            |
             v                            v
+---------------------+    +-------------------------------+
|  THE HARNESS        |    |  PROJECT MANAGEMENT           |
|  (Human's repo)     |    |  (GitHub UI)                  |
|                     |    |                               |
|  - Agent prompts    |    |  - Feature requests (issues)  |
|  - Runner script    |    |  - Bug reports (issues)       |
|  - Tools/scripts    |    |  - PR feedback (comments)     |
|  - Workflows        |    |  - Strategic goals (board)    |
|  - Infrastructure   |    |  - Escalation responses       |
+----------+----------+    +---------------+---------------+
           |                               |
           |  dispatches agents            |  agents read
           |  to work on project           |  direction from
           v                               v
+----------------------------------------------------------+
|  THE PROJECT (Agents' codebase)                          |
|                                                          |
|  - CLAUDE.md: project context (agents maintain)          |
|  - Application code (agents write all of it)             |
|  - Tests (agents write all of them)                      |
|  - Thin workflow stubs (forward events to harness)       |
|  - Zero human code commits                               |
+----------------------------------------------------------+
```

## What Is an Agent?

An agent is an **ephemeral Claude Code session** — not a persistent process.
Each run:

1. GitHub Actions triggers a workflow
2. The runner checks out the project
3. `run-agent.sh` sets up identity (GitHub App), tools (allowlist), and
   invokes Claude
4. Claude starts fresh — no memory of previous runs
5. Claude reads `CLAUDE.md` from the project to understand what it's working on
6. Claude executes its role prompt (find an issue, implement it, open a PR)
7. Session ends. The agent ceases to exist.

There is nothing to "port" between projects. The agent is reconstructed from
scratch each time from:

- A **generic role prompt** (from the harness): "You're an engineer. Read the
  project context. Do your job."
- **Project context** (from the project's CLAUDE.md): "This is a FastAPI app,
  backend in `api/`, etc."
- **Tool access** (from the harness runner): Write, Edit, Bash for engineers;
  read-only for reviewers
- **A working directory** (the checked-out project repo)

The same team can work on any project that has a good CLAUDE.md.

## How Humans Interact Without Code Access

### Directing work: GitHub Issues

The human creates an issue describing what they want. The agent team handles
the rest — triaging, scoping, implementing, reviewing, and merging.

### Providing feedback: PR Comments

The human comments on agent PRs with feedback. The reviewer marks changes
requested, the engineer addresses the feedback, and the cycle continues.

### Setting strategic direction: GitHub Projects

The human updates the project board — moving items, setting priorities. The
PM agent reads the board and shapes the roadmap accordingly.

### Unblocking agents: Harness updates

When an agent is blocked by a missing capability (tool, permission, config),
it creates a `harness/request` issue. The human sees the request, builds the
capability in the harness, and redeploys. The agent's blocked work resumes.

## Phased Roadmap

### Phase 1: Make Prompts Project-Agnostic (current)

Agents work from project context (CLAUDE.md), not hardcoded prompt values.
Prompts become generic role definitions. Project-specific details live in
the project's own documentation.

### Phase 2: Separate Harness from Project

Create a dedicated harness repo. Move agent infrastructure (prompts, runner,
scripts) there. Project repos become pure application code with thin workflow
stubs. Human works exclusively in the harness repo.

### Phase 3: Multi-Project

Same team operates on multiple projects. Each project has a good CLAUDE.md
and thin workflow stubs. One harness, many projects.

### Phase 4: Zero Code Access

Human removes their own code access to project repos. Only bot accounts can
push. Human interacts exclusively through the harness repo and GitHub's
project management UI. The git history is the proof.
