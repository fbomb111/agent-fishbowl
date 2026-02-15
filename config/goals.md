# Agent Fishbowl — Strategic Goals

> **Maintained by**: The human (Frankie)
> **Read by**: The PM agent — uses these to shape the roadmap
>
> These are the high-level objectives for the project. The PM agent translates
> them into concrete roadmap items and decides which metrics to track.
> Goals are ordered by priority.

## Mission

Agent Fishbowl is a real, useful product built and maintained autonomously by
AI agents in public. Every issue, PR, review, and deploy is done by agents —
and all of it is visible on GitHub.

Visitors come to watch the process. The product proves the agents are capable.

## Audience

People curious about AI agents — developers, builders, and tech-curious
observers who want to see what autonomous multi-agent systems can actually do.
They come for the fishbowl (watching agents work), and the news feed is the
real product those agents are building.

## Goal 1: Build a real product worth using

The AI news feed must be genuinely useful — not a toy or a demo. It's the proof
that agents can ship real software. If the product isn't good, the showcase
doesn't matter.

The PM should pursue sub-goals that make the news feed something people would
actually use. Examples of the kinds of sub-goals that could serve this:

- Content quality and freshness
- Source diversity and coverage
- Reading experience on desktop and mobile
- Navigation and discoverability

## Goal 2: Make the process the spectacle

This is why people visit. They want to see agents creating issues, writing code,
reviewing PRs, and shipping features. The experience of watching should be
compelling and immediately understandable — a visitor should quickly grasp what's
happening and want to keep watching.

Examples of the kinds of sub-goals that could serve this:

- Clarity of who did what and why
- Making agent decisions visible, not just their outputs
- Helping newcomers understand the team structure and workflow
- Surfacing interesting moments (disagreements, retries, creative solutions)

## Goal 3: Be transparent about how we're doing

The site should show what the team is tracking, what metrics they're using, and
how they're performing. This meta-layer is itself a showcase — it demonstrates
that the agents can set goals, measure progress, and course-correct.

The PM decides which metrics to track and how to surface them. Example categories
of metrics that might matter (the PM chooses which to pursue and when):

- Visitors and engagement (traffic, time on page, return visits)
- Content quality (freshness, accuracy, coverage breadth)
- Operational health (uptime, latency, error rates)
- Cost efficiency (infrastructure spend, AI token usage)
- SEO and discoverability (search ranking, organic traffic)
- Agent productivity (issues closed, PRs merged, cycle time)

These metrics will sometimes conflict — optimizing for content quality may
increase cost; improving uptime may slow feature velocity. The PM balances these
tradeoffs over time based on what matters most for the current phase.

## Goal 4: Maintain professional quality

The agents should produce work that meets a professional standard. This is a
supporting goal — quality serves goals 1-3. You can't have a compelling showcase
if the code is sloppy, and you can't have a useful product if it's buggy.

Examples of the kinds of sub-goals that could serve this:

- Clean, well-described PRs that pass CI
- Substantive code reviews (not rubber stamps)
- Consistent coding conventions
- Well-scoped issues with clear acceptance criteria

## Constraints

- **Agents do all implementation.** The human sets goals and adjusts agent
  workflows but does not write application code or merge PRs.
- **Ship incrementally.** Small, working improvements over big ambitious
  redesigns. A shipped feature beats a planned feature.
- **Balance cost, quality, and speed.** Don't optimize one at the expense of
  the others. The PM should be aware of infrastructure costs, AI token usage,
  and operational overhead when making roadmap decisions.
- **No user accounts or authentication.** Keep it public and simple.
- **Content domain is AI/ML news.** The feed covers AI, machine learning,
  agents, and related technology — not general news.
