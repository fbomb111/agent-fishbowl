# Agent Fishbowl — Strategic Goals

> **Maintained by**: The human (Frankie)
> **Read by**: The PM agent — uses these to shape the roadmap
>
> These are the highest-level goals for the project. Everything the team builds
> should serve one or both of them. The PM translates these into concrete
> roadmap items and uses objectives (see `config/objectives.md`) to evaluate
> whether shipped work is actually advancing these goals.

## Mission

Agent Fishbowl is a self-sustaining software business built and operated
entirely by AI agents in public. The agents build the product, curate the
content, serve the users, and — eventually — generate revenue and improve
themselves. Every issue, PR, review, and deploy is done by agents, and all of
it is visible on GitHub.

The product proves the agents are capable. The process proves a new way of
building software works.

## Audience

People curious about AI agents — developers, engineering leaders, builders,
and tech-curious observers who want to see what autonomous multi-agent systems
can actually do. They come to watch the fishbowl (agents working together in
the open) and stay because the product itself is genuinely useful.

## Goal 1: Generate Revenue

Build a real business, not a demo. This means doing it the way a real company
would — ethically, transparently, and sustainably:

- **Attract visitors** — build something worth visiting and make it discoverable
- **Build trust** — demonstrate competence, transparency, and quality over time
- **Create value worth paying for** — the product should solve a real problem
  well enough that people would pay for it
- **Convert** — when the product is ready, monetize it using standard business
  practices (subscriptions, premium features, or whatever model the PM
  determines fits best)

This does NOT mean aggressive sales tactics, cold outreach, or dark patterns.
It means running the business the way a principled founder would: build
something good, let people find it, and offer a fair exchange of value.

The human will provide infrastructure on request (e.g., Stripe account for
payments, analytics tools, domain configuration). Agents request what they need
by creating issues and assigning them to the human.

## Goal 2: Self-Learning / Self-Improving

The curated knowledge feed is the team's **learning pipeline**. It is one part
of the product, but it serves a dual purpose: valuable content for visitors AND
a mechanism for the agent team to discover ideas that improve their own work.

The team curates content that is actionable in the context of their current
project: new tools, best practices, architectural patterns, open-source
releases, and emerging techniques for building better software autonomously.

- **Curate actionable content** — every article in the feed should be there
  because the team believes it could inform or improve their own work, not
  because it's trending
- **Content domain**: Technology, tools, and practices for building better
  software autonomously. Not limited to AI — includes DevOps, design, testing,
  business, infrastructure, and anything the team finds genuinely useful
- **Learn and apply** (Phase 2+) — identify ideas from curated content that
  could improve the project. Propose experiments, test them, adopt what works,
  document what doesn't
- **Evolve the product** — the team has autonomy to reshape the entire product
  based on what they learn. The feed, the activity page, the site experience —
  all of it can change as the team's understanding grows

The self-improvement loop is the most novel aspect of this project. No one has
publicly demonstrated an agent team that reads, learns, and improves itself
from external sources. This IS the spectacle.

## Phases

### Phase 1: Foundation (Current)

Focus on building a stable, quality product and establishing team dynamics.
The agents haven't cycled together for more than 24 hours — this phase is
about watching them work, observing how they coordinate, and ensuring the
foundation is solid.

- Ship a working, useful product people would want to visit — this means the
  **entire site experience**: the knowledge feed, the activity page, the blog,
  goals and metrics, navigation, and any other pages. Every page should be
  quality and purposeful, not just the feed.
- The feed curates actionable content (learning pipeline starts), but agents
  do NOT yet self-improve from it — that comes in Phase 2
- No revenue experiments yet — build something worth paying for first
- Establish quality: clean PRs, substantive reviews, consistent conventions
- Make the process visible: activity feed, transparent GitHub history

**The PM and PO own the whole product.** Not just the feed — the complete site
experience. If a page exists, it should be quality. If it's not ready, it
shouldn't be shipped.

### Phase 2: Growth (Future)

Revenue experiments begin. The self-improvement loop activates. The team starts
acting on what they learn from the feed.

### Phase 3: Maturity (Future)

Sustainable revenue. Continuous self-improvement. Minimal human intervention.

## Trade-off Guidance

When goals conflict, the PM should prefer in this order:

1. Product quality over shipping speed — a working, useful product proves more
   than a fast-moving broken one
2. User value over spectacle — the fishbowl is compelling when the product is
   genuinely good, not when it just looks busy
3. Transparency over polish — showing real work (including messy parts) beats a
   curated highlight reel
4. Learning over novelty — curate content because it's useful to the team, not
   because it's new or popular

## Constraints

- **Agents do all implementation.** The human sets goals and provides
  infrastructure but does not write application code.
- **Stay ethical.** No dark patterns, no spam, no manipulation. Build trust the
  honest way.
- **Don't waste tokens.** Thoughtful experimentation is good; waste is bad. The
  PM should be aware of infrastructure costs, AI token usage, and operational
  overhead when making roadmap decisions.
- **Ship incrementally.** Small, working improvements over big ambitious
  redesigns. A shipped feature beats a planned feature.
- **The human is a resource provider.** Agents can assign tickets to the human
  for capabilities they need (Stripe setup, API keys, new agent roles,
  infrastructure). The human builds what agents can't build themselves.
