# Add Agent to Fishbowl Team

Add a new AI agent to the Agent Fishbowl system. Creates all required files across both repos, updates cross-references, and outputs a human setup checklist.

**Reference doc**: `/home/fcleary/projects/agent-harness/docs/adding-an-agent.md`

## Input

The user provides agent details — either inline, as a structured spec, or conversationally. Extract these fields:

| Field | Required | Example |
|-------|----------|---------|
| `role` | Yes | `product-analyst` (kebab-case slug) |
| `display_name` | Yes | `Product Analyst` |
| `purpose` | Yes | One-line: "Owns Goal 3: market research, pricing, revenue" |
| `goals` | Yes | Which goal(s): 1, 2, 3, or multiple |
| `voice` | Yes | 2-3 sentences describing persona |
| `tool_category` | Yes | `read-only`, `api-caller`, `strategic`, `code-writer`, `code-reviewer` |
| `schedule` | Yes | Cron expression or "event-driven" with trigger types |
| `reports_to` | Yes | `pm` (proposals), `po` (intake issues), `independent`, or `none` |
| `creates_intake` | Yes | `true/false` — does it create `source/{role}` issues? |
| `partials` | No | Which prompt partials to include: `reflection`, `knowledge-base`, or both. Default: both. |
| `special_tools` | No | Extra env vars: `STRIPE_SECRET_KEY`, `ANALYTICS_API_KEY`, etc. |
| `blob_container` | No | If it uploads to blob storage, container name |
| `steps_summary` | Yes | Brief list of the main workflow steps (will be expanded into full prompt) |
| `rules_summary` | No | Any role-specific rules beyond the standard set |
| `jobs` | No | List of focused job names if the agent has multiple concerns (e.g., `["architecture-review", "security-scan"]`). Creates identity + job files instead of monolithic prompt. |
| `credentials` | No | GitHub App ID, Installation ID, User ID, Bot Name, PEM path (if pre-generated) |

If any required field is missing, ask the user before proceeding.

## Execution

### Phase 0: Generate Avatar

**Do this FIRST, before any file creation.**

Generate a Robohash avatar for the agent. Download the image and show it to the user:

```bash
curl -L -o /tmp/fishbowl-{role}.png "https://robohash.org/fishbowl-{role}?set=set1&size=256x256"
```

Show the image to the user (use the Read tool on the PNG file — Claude Code can display images).

Tell the user:
> Here's the avatar for **{Display Name}** (`fishbowl-{role}`). You'll use this when creating the GitHub App.

**PAUSE HERE.** Ask the user:
> Ready to proceed? If you want a different avatar, tell me and I'll regenerate. Otherwise, I'll create the agent files next. If you already have the GitHub App credentials, provide them now — otherwise I'll give you the setup checklist at the end.

Wait for user confirmation before continuing.

### Phase 1: Create Harness Files

All in `/home/fcleary/projects/agent-harness`:

**1. Create prompt files**

Choose based on whether `jobs` was provided:

**Path A — Single-focus agent (no `jobs` field, default):**

Create monolithic prompt: `agents/prompts/{role}.md`

```markdown
# {Display Name} Agent

You are the {Display Name} Agent. Your job is {purpose}. You do NOT {anti-patterns based on role}. You must complete ALL steps below.

**First**: Read `CLAUDE.md` to understand the project's architecture, current phase, and domain.

## Voice

{voice}

## Sandbox Compatibility

You run inside Claude Code's headless sandbox. Follow these rules for **all** Bash commands:

- **One simple command per call.** Each must start with an allowed binary.
- **No variable assignments at the start.** `RESPONSE=$(curl ...)` will be denied. Call the command directly and remember the output.
- **No compound operators.** `&&`, `||`, `;` are blocked. Use separate tool calls.
- **No file redirects.** `>` and `>>` are blocked. Use pipes (`|`) or API calls instead.
- **Your memory persists between calls.** You don't need shell variables — remember values and substitute them directly.

## Available Tools

| Tool | Purpose | Example |
|------|---------|---------|
{tools table based on tool_category}

## Step 1: {First step}
{...expand from steps_summary...}

## Step N: STOP
**STOP here.** One {unit of work} per run.

## Rules
- **Always label issues with `agent-created`.**
- **One {unit} per run.**
{role-specific rules}
```

**Path B — Multi-job agent (`jobs` field provided):**

Create identity file: `agents/prompts/identities/{role}.md`

```markdown
# {Display Name} Agent

You are the {Display Name} Agent. {purpose}.

**First**: Read `CLAUDE.md` to understand the project's architecture, current phase, and domain.

## Voice

{voice}

## Sandbox Compatibility
{same sandbox section as Path A}

## Available Tools

| Tool | Purpose | Example |
|------|---------|---------|
{tools table based on tool_category}

## Common Steps

### Always: {steps that run every invocation regardless of job}
{e.g., process escalation issues, check for blockers}

### Last: Report
{reporting template — same structure every run}

## Output Rules
{action limits, label requirements, authority boundaries}
```

Create one job file per job: `agents/prompts/jobs/{role}/{job}.md`

```markdown
# Job: {Job Display Name}

## Focus
{one-paragraph description of what this job evaluates}

## Steps

### 1. {First step}
{specific instructions}

### 2. {Second step}
{specific instructions}

## What to look for
- {evaluation criteria}
- {patterns to flag}

## Output
- {deliverables and limits, e.g., "Max 2 issues labeled source/tech-lead,type/refactor"}
```

Also create `agents/prompts/jobs/{role}/full.md` as a migration bridge containing all steps combined, for backward-compatible runs without `--job`.

**Sandbox section**: Include for all agents EXCEPT `code-writer` category (engineer doesn't need it since it has full tool access).

**Tools table by category**:

- `read-only`: `gh` (issues, PRs), `cat`, `scripts/*`, Read, Glob, Grep
- `api-caller`: `curl` (APIs), `az` (blob storage), `gh`, `jq`, `date`, `scripts/*`, Read, Glob, Grep
- `strategic`: `gh` (project management), `cat`, `scripts/*`, Read
- `code-writer`: `gh`, `git`, `ruff`, `npx`, `pip`, `scripts/*`, Read, Write, Edit, Glob, Grep
- `code-reviewer`: Same as read-only + `ruff`, `npx`, `pip`, Write, Edit

**2. Add role to `config/roles.json`**

This is the **single source of truth** for tool allowlists and prompt partials. Add an entry under `"roles"`:

```json
"your-new-role": {
  "tools": "${API}",
  "partials": ["reflection", "knowledge-base"]
}
```

**Tool presets** (defined in `_tool_presets`):

| Preset | Expands to |
|--------|-----------|
| `${COMMON}` | `Bash(gh:*),Bash(git:*),Bash(cat:*),Read,Glob,Grep` |
| `${API}` | `Bash(curl:*),Bash(az:*),Bash(gh:*),Bash(jq:*),Bash(cat:*),Bash(date:*),Bash(scripts/*),Read,Glob,Grep` |

**Tool categories mapped to config values:**

| Category | `tools` value |
|----------|---------------|
| `read-only` | `${COMMON},Bash(scripts/*)` |
| `api-caller` | `${API}` |
| `strategic` | `Bash(gh:*),Bash(cat:*),Bash(scripts/*),Read` |
| `code-writer` | `Bash(gh:*),Bash(git:*),Bash(ruff:*),Bash(npx:*),Bash(pip:*),Bash(scripts/*),Bash(cat:*),Bash(chmod:*),Read,Write,Edit,Glob,Grep` |
| `code-reviewer` | `${COMMON},Bash(ruff:*),Bash(npx:*),Bash(pip:*),Bash(scripts/*),Write,Edit` |

**Config fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `tools` | Yes | `--allowedTools` string. Use `${COMMON}` or `${API}` presets, or specify explicitly. |
| `partials` | Yes | Array: `["reflection", "knowledge-base"]`, `["knowledge-base"]`, or `[]`. |
| `prompt_role` | No | Override prompt file lookup (e.g., `"po"` → uses `prompts/po.md`). |
| `deprecated` | No | Name of the replacement role. Prints warning at runtime. |

**3. Create orchestration script (if needed): `scripts/run-{role}.sh`**

Create this if the agent needs pre-flight checks (e.g., verifying config files exist, checking API availability). Follow the `run-strategic.sh` or `run-product-analyst.sh` pattern. Make executable.

Skip if the agent is simple and can run directly via `role` input.

**4. Edit `docs/project-board-readme.md`**

Add to "The Team" section:

```markdown
**{Display Name}** — {One-sentence description for a public audience.}
```

### Phase 2: Create Fishbowl Files

All in `/home/fcleary/projects/agent-fishbowl`:

**5. Create workflow: `.github/workflows/agent-{role}.yml`**

Choose from these templates:

**Simple agent (uses reusable workflow — preferred for most agents):**
```yaml
name: "Agent: {Display Name}"

on:
  schedule:
    - cron: "{schedule}"
  workflow_dispatch: {}

permissions:
  contents: read
  issues: write

jobs:
  run:
    uses: ./.github/workflows/reusable-agent.yml
    with:
      role: {role}
    secrets: inherit
```

> **WARNING**: When using the reusable workflow (`reusable-agent.yml`), do NOT add a
> workflow-level `concurrency:` block. The reusable workflow already defines
> `concurrency: group: agent-{role}` at the job level. Having both creates a deadlock
> where the workflow-level lock prevents the inner job from acquiring the same group,
> causing instant failure with no runner assigned.
>
> Only use workflow-level `concurrency:` when the agent defines its own job (the
> "Agent with post-dispatch steps" and "Job-specific agent" templates below).

**Agent with orchestration script:**
```yaml
name: "Agent: {Display Name}"

on:
  schedule:
    - cron: "{schedule}"
  workflow_dispatch: {}

permissions:
  contents: read
  issues: write

jobs:
  run:
    uses: ./.github/workflows/reusable-agent.yml
    with:
      entry-point: scripts/run-{role}.sh
    secrets: inherit
```

**Agent with post-dispatch steps (needs its own job definition):**
```yaml
name: "Agent: {Display Name}"

on:
  schedule:
    - cron: "{schedule}"
  workflow_dispatch: {}

permissions:
  contents: read
  issues: write
  actions: write

concurrency:
  group: agent-{role}
  cancel-in-progress: false

jobs:
  run:
    name: Run {Display Name} agent
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      # Harness ref must match harness_ref in config/agent-flow.yaml
      - name: Run {Display Name} agent
        uses: YourMoveLabs/agent-harness@v1.2.0
        with:
          role: {role}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Dispatch PO if intake batch ready
        if: success()
        run: |
          INTAKE=$(gh issue list --state open --json labels \
            --jq '[.[] | select(
              (.labels | map(.name) | any(test("^source/"))) and
              (.labels | map(.name) | any(test("^priority/")) | not)
            )] | length')
          if [ "$INTAKE" -ge 5 ]; then
            echo "Batch ready: $INTAKE unprocessed intake items — dispatching PO"
            gh workflow run agent-product-owner.yml
          else
            echo "Only $INTAKE unprocessed items — accumulating (threshold: 5)"
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Job-specific agent (one workflow per job, for multi-job agents):**
```yaml
name: "Agent: {Display Name} — {Job Name}"

on:
  schedule:
    - cron: "{job_schedule}"
  workflow_dispatch: {}

permissions:
  contents: read
  issues: write

concurrency:
  group: agent-{role}-{job}
  cancel-in-progress: false

jobs:
  run:
    name: Run {Display Name} — {Job Name}
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      # Harness ref must match harness_ref in config/agent-flow.yaml
      - name: Run {Display Name} — {Job Name}
        uses: YourMoveLabs/agent-harness@v1.2.0
        with:
          role: {role}
          job: {job}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Each job gets its own workflow file (`agent-{role}-{job}.yml`), its own cron schedule, and its own concurrency group. This gives full visibility in the GitHub Actions UI.

Adjust triggers for event-driven agents (add `repository_dispatch`, `pull_request`, etc.).
Add `actions: write` permission if the agent dispatches other workflows.

**5b. Update flow graph: `config/agent-flow.yaml`**

This is the single source of truth for how agents interact. Add the new agent node:

```yaml
  {role}:
    workflow: agent-{role}.yml
    triggers:
      - type: schedule
        cron: "{schedule}"
    dispatches: []  # Add dispatch edges if this agent triggers others
```

For multi-job agents with separate workflow files, add each job workflow as a separate reference or note the job structure in the agent's node.

If the agent dispatches to other agents, add dispatch entries:
```yaml
    dispatches:
      - target: product-owner
        method: workflow_run
        condition:
          type: intake_batch
          threshold: 5
```

If a new `repository_dispatch` event type is introduced, register it in the `events` section:
```yaml
events:
  new-event-name:
    description: "What this event means"
    payload: [chain_depth]  # if applicable
```

Validate and regenerate:
```bash
cd /home/fcleary/projects/agent-fishbowl
python scripts/validate-flow.py --validate
python scripts/validate-flow.py --mermaid -o docs/agent-flow.md
```

The validator checks that workflow files match the declared topology — CI will fail if the flow graph is inconsistent.

**6. Create labels (if `creates_intake` is true)**

```bash
cd /home/fcleary/projects/agent-fishbowl
gh label create "source/{role}" --color "c5def5" --description "From {Display Name} agent"
```

### Phase 3: Update Cross-References

**7. Edit fishbowl `CLAUDE.md`** — Update these sections:

a. **Workflows table** (~line 37): Add a row:
```
| `agent-{role}.yml` | {Display Name} | {triggers description} | Concurrency group |
```

b. **Project structure** (~line 147): Add under `.github/workflows/`:
```
  agent-{role}.yml    {Display Name} ({cadence description})
```

c. **Label taxonomy** (~line 225): If creates `source/*` issues:
```
| `source/{role}` | From {display name} agent |
```

d. **Agent Team table** (~line 242): Add row:
```
| **{Display Name}** | `fishbowl-{role}[bot]` | {cadence} | {one-liner purpose} |
```

e. **Information Flow** (~line 258): Add to the coordination diagram if the agent has a distinct flow.

**8. Edit other agent prompts** (conditional, in agent-harness):

- **If `reports_to` is `po`** (creates intake for PO):
  - Edit `agents/prompts/product-owner.md`: Add `scripts/find-issues.sh --label "source/{role}"` to Step 3 intake scan
  - Edit `agents/prompts/triage.md`: Add `--no-label "source/{role}"` to Step 1 exclusion filter

- **If `reports_to` is `pm`** (creates proposals for PM):
  - Edit `agents/prompts/product-manager.md`: Add a review step for `source/{role}` issues

### Phase 4: Configure Credentials

**If credentials were provided** (App ID, Installation ID, User ID, PEM path), configure them directly. **If not**, ask the user and print the GitHub App setup checklist.

#### 4a. Lookup missing credentials (automated)

If only App ID is provided, look up the rest via GitHub API:

```bash
# Installation ID
gh api /orgs/YourMoveLabs/installations --jq '.installations[] | select(.app_slug == "fishbowl-{role}") | .id'

# User ID
gh api /users/fishbowl-{role}%5Bbot%5D --jq '.id'
```

#### 4b. Configure Runner VM (20.127.56.119)

SSH to the runner VM and add credentials to `~/.config/agent-harness/.env`:

```bash
ssh fcleary@20.127.56.119 'cat >> ~/.config/agent-harness/.env << EOF
GITHUB_APP_{ROLE_UPPER}_ID={app_id}
GITHUB_APP_{ROLE_UPPER}_INSTALLATION_ID={installation_id}
GITHUB_APP_{ROLE_UPPER}_KEY_PATH=/home/fcleary/.config/agent-fishbowl/{role}.pem
GITHUB_APP_{ROLE_UPPER}_USER_ID={user_id}
GITHUB_APP_{ROLE_UPPER}_BOT_NAME={role}
EOF'
```

Verify: `ssh fcleary@20.127.56.119 "grep {ROLE_UPPER} ~/.config/agent-harness/.env"`

#### 4c. Sync Dev Server (172.191.162.114 — this machine)

Add the SAME entries to `~/.config/agent-harness/.env` with adjusted PEM path (`~/.config/agent-harness/` instead of `~/.config/agent-fishbowl/`):

```bash
cat >> ~/.config/agent-harness/.env << EOF
GITHUB_APP_{ROLE_UPPER}_ID={app_id}
GITHUB_APP_{ROLE_UPPER}_INSTALLATION_ID={installation_id}
GITHUB_APP_{ROLE_UPPER}_KEY_PATH=/home/fcleary/.config/agent-harness/{role}.pem
GITHUB_APP_{ROLE_UPPER}_USER_ID={user_id}
GITHUB_APP_{ROLE_UPPER}_BOT_NAME={role}
EOF
```

**Both VMs must stay in sync.** The runner VM is the canonical source. PEM paths differ between VMs:
- Runner: `~/.config/agent-fishbowl/{role}.pem`
- Dev server: `~/.config/agent-harness/{role}.pem`

#### 4d. PEM Key Distribution

Ask the user to upload the PEM to the **dev server** (this machine). The standard location is:

```
~/.config/agent-harness/{role}.pem
```

Tell the user:
> Please SCP the PEM key to the dev server:
> ```
> scp fishbowl-{role}.*.pem fcleary@172.191.162.114:~/.config/agent-harness/{role}.pem
> ```
> Let me know when it's uploaded and I'll transfer it to the runner VM.

**PAUSE** — wait for user confirmation.

After the user confirms, verify the PEM exists on the dev server:

```bash
ls -la ~/.config/agent-harness/{role}.pem
```

#### 4e. Transfer PEM to Runner VM

Copy the PEM from dev server to runner VM (different path on runner):

```bash
scp ~/.config/agent-harness/{role}.pem fcleary@20.127.56.119:~/.config/agent-fishbowl/{role}.pem
```

Verify it landed:

```bash
ssh fcleary@20.127.56.119 "ls -la ~/.config/agent-fishbowl/{role}.pem"
```

#### 4f. Sync any missing PEMs

While we're at it, check if any PEMs are missing between the two VMs and sync them. Dev server is the source of truth — transfer any missing keys to the runner:

```bash
# Compare PEM inventories
echo "=== Dev server PEMs ==="
ls ~/.config/agent-harness/*.pem

echo "=== Runner VM PEMs ==="
ssh fcleary@20.127.56.119 "ls ~/.config/agent-fishbowl/*.pem"
```

For any PEM that exists on dev but not on runner:
```bash
scp ~/.config/agent-harness/{missing}.pem fcleary@20.127.56.119:~/.config/agent-fishbowl/{missing}.pem
```

#### 4g. Human Setup (if GitHub App doesn't exist yet)

Print this checklist only if the user needs to create the GitHub App:

```
## GitHub App Setup for {Display Name}

1. Go to https://github.com/settings/apps/new
2. Name: fishbowl-{role} (fishbowl- prefix required for GitHub global uniqueness)
3. Avatar: Use the robohash image generated in Phase 0
4. Permissions: Issues (Read & Write), Contents (Read), Pull Requests (Read)
5. Install on: YourMoveLabs/agent-fishbowl
6. Generate private key
7. Provide: App ID, PEM file location
```

{If blob_container}: #### Blob Storage
```
az storage container create --account-name agentfishbowlstorage --name {blob_container} --auth-mode login
```

{If special_tools}: #### API Keys
Add to `~/.config/agent-harness/.env` on BOTH VMs:
{list each special tool env var}

#### Harness Tag
After pushing harness changes, create and push a new tag:
```
git tag -a vX.Y.Z -m "vX.Y.Z: Add {Display Name} agent"
git push origin main --tags
```
Then bump all fishbowl workflows to the new tag:
```
scripts/bump-harness.sh vX.Y.Z
```

### Phase 5: Commit (Don't Push)

Stage and commit changes in both repos. Use this message format:

**Harness**: `Add {Display Name} agent ({purpose summary})`
**Fishbowl**: `Add {Display Name} agent workflow + CLAUDE.md update`

Do NOT push — let the user review first. Report what was committed in each repo.

## Batch Mode

When processing multiple agents from a single document:

1. **Phase 0 first for ALL agents**: Generate all robohash avatars upfront and show them to the user
2. **PAUSE**: Let the user create all GitHub Apps with the avatars
3. **Collect credentials**: Ask the user for all credentials at once
4. Process agents one at a time in the order listed
5. After each agent, report what was created
6. Cross-reference updates accumulate (each agent adds to CLAUDE.md, project-board-readme.md, etc.)
7. Commit after ALL agents are processed (one commit per repo with all changes)
8. The harness tag is created once at the end, after all agents
9. Update ALL fishbowl workflows to the new harness tag at the end

## Notes

- **Harness version authority**: `config/agent-flow.yaml` → top-level `harness_ref` field is the single source of truth
- When bumping the harness: run `scripts/bump-harness.sh <new-version>` — it updates all workflow files, the config, and regenerates the diagram. CI validates consistency.
- When creating a **reusable workflow caller**, no harness ref appears in the file — it's inherited from `reusable-agent.yml`
- When creating a **custom workflow** (with post-steps), copy the ref from `config/agent-flow.yaml` `harness_ref` into the `uses:` line
- Agents with `tool_category: code-writer` don't need the sandbox compatibility section in their prompt
- Hyphens in role slugs become underscores in env var names: `product-analyst` → `PRODUCT_ANALYST`
- Robohash URL format: `https://robohash.org/fishbowl-{role}?set=set1&size=256x256`
- **No wrapper scripts** — the old `agents/{role}.sh` pattern has been replaced by `config/roles.json` + `role` input on the action
- **Jobs model**: Agents with multiple concerns can use `--job` to focus each invocation. Identity files live in `agents/prompts/identities/`, job files in `agents/prompts/jobs/{role}/`. The harness assembles identity + job + partials at runtime. Most agents don't need jobs — only split when an agent has distinct responsibilities that benefit from separate schedules or focused context.
- **Credential naming**: GitHub Apps use `fishbowl-{role}` for global uniqueness. PEM files and `BOT_NAME` use bare `{role}` (no prefix). The harness defaults `BOT_NAME` to the role slug if not set.
- **Naming conventions**: See `docs/adding-an-agent.md` in agent-harness for full naming table
