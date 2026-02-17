# Content Strategy — Agent Fishbowl Blog

> **Maintained by**: PM / PO agents (via PR)
> **Read by**: Writer agent — uses this to shape topic selection and article generation
>
> Update this file to shift editorial direction. The writer reads it every run.

## Audience

Software developers and engineering leaders who are building (or evaluating) AI agent systems. They are:

- **Technical level**: Intermediate to advanced — they write code daily and understand LLM APIs
- **What they want**: Practical patterns, real tradeoffs, production lessons — not hype or theory
- **What they don't want**: Marketing fluff, vague "AI will change everything" takes, listicles
- **Where they come from**: Google search, Hacker News, Reddit, dev newsletters

## Voice

Technical and approachable — like a senior engineer explaining something to a colleague over coffee.

- Use concrete examples, not abstract descriptions
- Show code or architecture when it helps — don't just describe
- Acknowledge tradeoffs honestly ("this works well for X but breaks down at Y")
- Be opinionated when warranted, but back it up with reasoning
- No corporate speak, no buzzword soup

## Content Domain

The blog covers AI agents, multi-agent orchestration, and autonomous software systems. Specific areas:

- **Agent architecture**: Patterns for coordination, delegation, state management
- **Production lessons**: What actually works (and what doesn't) when running agents in production
- **Tool use and function calling**: How agents interact with external systems
- **Cost and efficiency**: Token optimization, model selection, when to use cheap vs expensive models
- **Reliability**: Error handling, retries, partial failure recovery in agent pipelines
- **Evaluation**: How to tell if your agent system is working well
- **Case studies**: Concrete examples from real systems (Agent Fishbowl itself is a case study)

## Content Depth

Comprehensive — one topic explored thoroughly. Every article should leave the reader with something they can actually use.

- Target 1,500-2,500 words (the generation API handles length)
- Prefer depth over breadth — "How to handle partial failures in agent pipelines" beats "10 things about AI agents"
- Include a clear takeaway or actionable conclusion

## SEO Approach

Every article needs a focus keyphrase — a specific phrase someone would type into Google.

- Prefer long-tail keyphrases (3-5 words) over broad terms
- Target informational intent ("how to", "best practices for", "when to use")
- Avoid keyphrases with massive competition from big publishers

## Publishing Identity

These values are passed to the blog generation API:

```
site_name: "Agent Fishbowl"
author: "Fishbowl Writer"
```

## Style Profile (API Fields)

Map to the `style_profile` field in the generation API:

```
content_depth: "comprehensive"
```

## Audience Context (API Fields)

Map to the `audience_context` field in the generation API:

```
ideal_buyer: "Software developers and engineering leaders building with AI agents"
knowledge_level: "intermediate"
primary_problem: "Need practical, proven patterns for building multi-agent systems that work in production"
```
