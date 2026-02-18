# Agent Fishbowl — Objectives & Signals

> **Maintained by**: The human (Frankie)
> **Read by**: PM agent — uses these to evaluate whether shipped work serves the goals
> **Cadence**: PM evaluates signals daily; human reviews and adjusts monthly
> **Last updated**: 2026-02-18

## How This Works

Objectives are time-bounded outcomes the project is working toward. Each has
**signals** — observable indicators the PM watches to assess progress. Signals
inform the PM's judgment; they are not targets to optimize for.

The PM reads this file alongside `goals.md` and reports an assessment for each
objective: **on-track**, **at-risk**, or **off-track**, with evidence.

## Current Phase: Foundation

The team has not yet cycled together for more than 24 hours. This phase is
about establishing a stable product, observing team dynamics, and building
the learning pipeline. Revenue and self-improvement come in Phase 2.

---

### Objective 1: Ship a stable, useful product

**Serves Goal**: 1 (Revenue) — must build something worth paying for before
we can charge for it

"The product" means the **complete site experience** — not just the feed.
Every shipped page (feed, activity, blog, goals, about, etc.) should be
quality and purposeful. The PM and PO own all of it.

**Signals** (PM evaluates these):
- Content freshness: Are new articles appearing at a regular cadence?
- Source diversity: Are articles drawn from multiple sources, not dominated by one?
- Content quality: Do AI summaries accurately represent the source articles?
  Are they useful, not just reformatted headlines?
- Site availability: Is the product accessible and responsive? (`scripts/health-check.sh`)
- UX quality: Is the reading experience clean on desktop and mobile?
  Are navigation, search, and filtering functional?
- Site-wide navigation: Are all sections (feed, activity, blog, goals)
  accessible, connected, and easy to move between?
- Page quality: Are all shipped pages functional and polished? Does each page
  serve a clear purpose?
- Cross-section coherence: Does the site feel like a unified product, not
  a collection of disconnected pages?

**Anti-signals** (warns PM something is wrong):
- No new articles in 24+ hours (stale feed)
- >80% of articles from one source (single-source dominance)
- Health checks failing or returning errors
- Broken layout, unreadable content, or missing images
- Pages with placeholder content, broken navigation, or no clear purpose
- Sections that feel disconnected from the rest of the site

---

### Objective 2: Curate an actionable learning feed

**Serves Goal**: 2 (Self-Learning) — the feed should contain content the team
finds genuinely useful for improving their own project

**Signals** (PM evaluates these):
- Content relevance: Are articles about technology, tools, and practices that
  could inform this project? (not just trending AI news)
- Actionability: Could the team point to a curated article and say "this is
  relevant to something we're building or could build"?
- Domain breadth: Does the feed cover multiple domains the team cares about
  (architecture, DevOps, testing, design, business) — not just one topic?

**Anti-signals** (warns PM something is wrong):
- Feed dominated by hype articles with no actionable content
- No connection between curated content and the project's actual work
- Content that reads like generic aggregation rather than team curation

---

### Objective 3: Make the fishbowl experience compelling

**Serves Goal**: Both — the process IS the spectacle, and trust drives revenue

**Signals** (PM evaluates these):
- Activity visibility: Are agent actions showing in the activity feed?
  Can a visitor see what's happening?
- Agent diversity: Are multiple agent roles visible in recent activity
  (not just engineer)? PM, PO, Reviewer, SRE, Tech Lead should all appear
- Decision clarity: Can a visitor understand *why* an agent did something,
  not just *what*? (issues have descriptions, PRs have summaries, reviews
  have substance)
- Team coordination: Is the intake flow working? (PM → PO → Engineer →
  Reviewer → merge → deploy)

**Anti-signals** (warns PM something is wrong):
- No visible activity for 24+ hours (silent fishbowl)
- Only one agent type showing activity (broken coordination)
- Issues or PRs with no descriptions (opaque decisions)
- Reviewer rubber-stamping without substantive review

---

### Objective 4: Establish quality foundations

**Serves Goal**: Both — quality is the foundation for revenue and learning

**Signals** (PM evaluates these):
- CI passing: Are checks passing on PRs before merge?
- Review quality: Are reviews substantive (comments, change requests) not
  just auto-approvals?
- Convention adherence: Is the codebase consistent in style and structure?
- Issue scoping: Do issues have clear descriptions and acceptance criteria?

**Anti-signals** (warns PM something is wrong):
- PRs merging with failing CI
- Reviewer approving everything without comments
- Growing code quality debt (Tech Lead flagging recurring issues)
- Vague issues leading to misaligned implementations
