#!/usr/bin/env python3
"""Validate agent flow graph (v2) against actual workflow files and generate diagrams.

Usage:
    python scripts/validate-flow.py --validate              # CI mode: exit 0/1
    python scripts/validate-flow.py --validate --strict      # Warnings → errors too
    python scripts/validate-flow.py --mermaid                # Print Mermaid to stdout
    python scripts/validate-flow.py --mermaid -o FILE        # Write Mermaid to file
    python scripts/validate-flow.py --validate --mermaid -o docs/agent-flow.md  # Both
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_FILE = REPO_ROOT / "config" / "agent-flow.yaml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Day names for cron display
CRON_DAYS = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


# ── Data Structures ──────────────────────────────────────────────


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def merge_results(*results: CheckResult) -> CheckResult:
    merged = CheckResult()
    for r in results:
        merged.errors.extend(r.errors)
        merged.warnings.extend(r.warnings)
        merged.info.extend(r.info)
    return merged


# ── Helpers ──────────────────────────────────────────────────────


def load_flow() -> dict:
    with open(FLOW_FILE) as f:
        return yaml.safe_load(f)


def load_workflow(filename: str) -> dict | None:
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def get_wf_on(wf: dict) -> dict:
    """Extract the `on:` block (YAML parses `on:` as True key)."""
    return wf.get("on") or wf.get(True) or {}


def iter_agent_units(flow: dict) -> Iterator[tuple[str, dict, str]]:
    """Yield (label, config_unit, workflow_file) for every validatable unit.

    Regular agents yield once. Multi-job agents (like tech-lead) yield once
    per job, with label like 'tech-lead/full-scan'.
    """
    for agent_id, agent in flow.get("agents", {}).items():
        if "jobs" in agent:
            for job_id, job in agent["jobs"].items():
                label = f"{agent_id}/{job_id}"
                wf = job.get("workflow", "")
                yield label, job, wf
        elif "workflow" in agent:
            yield agent_id, agent, agent.get("workflow", "")


def all_flow_workflows(flow: dict) -> set[str]:
    """Collect every workflow filename referenced in the flow graph."""
    wfs: set[str] = set()
    for _, _, wf in iter_agent_units(flow):
        if wf:
            wfs.add(wf)
    for _, infra in flow.get("infrastructure", {}).items():
        wf = infra.get("workflow", "")
        if wf:
            wfs.add(wf)
    return wfs


def extract_wf_crons(wf_on: dict) -> list[str]:
    """Extract cron strings from a workflow's on: block."""
    schedule = wf_on.get("schedule", [])
    if isinstance(schedule, list):
        return [s.get("cron", "") for s in schedule if isinstance(s, dict)]
    return []


def extract_flow_crons(triggers: list[dict]) -> list[str]:
    """Extract cron strings from a flow graph agent's triggers."""
    return [t.get("cron", "") for t in triggers if t.get("type") == "schedule"]


def normalize_cron(cron: str) -> str:
    """Normalize cron whitespace for comparison."""
    return " ".join(cron.strip().split())


def cron_day_label(cron: str) -> str:
    """Return a human-readable day hint for a cron expression."""
    parts = cron.strip().split()
    if len(parts) >= 5:
        dow = parts[4]
        if dow == "*":
            dom = parts[2]
            if dom.startswith("*/"):
                return f"every {dom[2:]}d"
            return "daily"
        if dow in ("0", "1", "2", "3", "4", "5", "6"):
            return CRON_DAYS.get(int(dow), dow)
        if "," in dow:
            days = [CRON_DAYS.get(int(d.strip()), d) for d in dow.split(",")]
            return "/".join(days)
    return ""


def extract_wf_permissions(wf: dict) -> dict[str, str]:
    """Extract top-level permissions from a workflow."""
    perms = wf.get("permissions", {})
    if isinstance(perms, dict):
        return {k: str(v) for k, v in perms.items()}
    return {}


def extract_wf_concurrency(wf: dict) -> dict | None:
    """Extract top-level concurrency from a workflow."""
    conc = wf.get("concurrency")
    if isinstance(conc, dict):
        return conc
    return None


def _find_harness_ref_in_uses(uses: str) -> str | None:
    """Extract @version from a YourMoveLabs/agent-harness uses string.

    Supports both tag refs (@v1.5.3) and SHA-pinned refs (@sha).
    For SHA refs, the YAML comment (# v1.5.3) is stripped by the parser,
    so we return the raw @sha. The caller must handle SHA-to-tag resolution.
    """
    match = re.search(r"YourMoveLabs/agent-harness(@[\w.\-]+)", uses)
    return match.group(1) if match else None


def _find_harness_ref_in_raw_file(filename: str) -> str | None:
    """Extract the harness version from the raw workflow file.

    Handles SHA-pinned refs by reading the YAML comment:
      uses: YourMoveLabs/agent-harness@SHA  # v1.5.3
    Returns '@v1.5.3' (the version from the comment).
    Falls back to the ref after @ if no comment is present.
    """
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        for line in f:
            if "YourMoveLabs/agent-harness@" not in line:
                continue
            # Try SHA-pinned format: @sha  # vX.Y.Z
            m = re.search(
                r"YourMoveLabs/agent-harness@[a-f0-9]+\s+#\s*(v[\w.\-]+)", line
            )
            if m:
                return f"@{m.group(1)}"
            # Fallback: tag format @vX.Y.Z
            m = re.search(r"YourMoveLabs/agent-harness(@[\w.\-]+)", line)
            if m:
                return m.group(1)
    return None


def extract_harness_ref(wf: dict) -> str | None:
    """Find the YourMoveLabs/agent-harness@xxx reference in a workflow.

    Parses jobs.*.uses (reusable callers) and jobs.*.steps[*].uses (custom)
    directly instead of dumping the entire YAML to string.
    """
    for job in wf.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        # Reusable caller pattern: jobs.run.uses: ./.github/workflows/reusable-agent.yml
        # The harness ref won't be here, but check for direct harness uses
        uses = str(job.get("uses", ""))
        ref = _find_harness_ref_in_uses(uses)
        if ref:
            return ref
        # Custom workflow: jobs.run.steps[*].uses
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses", ""))
            ref = _find_harness_ref_in_uses(uses)
            if ref:
                return ref
    return None


def is_reusable_caller(wf: dict) -> bool:
    """Check if a workflow calls reusable-agent.yml via workflow_call."""
    for job in wf.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        uses = str(job.get("uses", ""))
        # Match ./.github/workflows/reusable-agent.yml or similar paths
        if uses.endswith("reusable-agent.yml"):
            return True
    return False


# ── Validation Checks ────────────────────────────────────────────


def check_workflow_exists(flow: dict) -> CheckResult:
    """Every workflow referenced in the flow graph must exist on disk."""
    r = CheckResult()
    for label, _, wf_file in iter_agent_units(flow):
        if not wf_file:
            r.errors.append(f"[{label}] Missing 'workflow' field")
        elif not (WORKFLOWS_DIR / wf_file).exists():
            r.errors.append(
                f"[{label}] Workflow not found: .github/workflows/{wf_file}"
            )
    for infra_id, infra in flow.get("infrastructure", {}).items():
        wf = infra.get("workflow", "")
        if wf and not (WORKFLOWS_DIR / wf).exists():
            r.errors.append(
                f"[infra/{infra_id}] Workflow not found: .github/workflows/{wf}"
            )
    return r


def check_orphan_workflows(flow: dict) -> CheckResult:
    """Every agent-*.yml file should have a flow graph entry."""
    r = CheckResult()
    registered = all_flow_workflows(flow)
    for path in sorted(WORKFLOWS_DIR.glob("agent-*.yml")):
        if path.name not in registered:
            r.errors.append(
                f"[orphan] .github/workflows/{path.name} has no flow graph entry"
            )
    return r


def check_schedule_crons(flow: dict) -> CheckResult:
    """Schedule crons must match between flow graph and workflow file."""
    r = CheckResult()
    for label, unit, wf_file in iter_agent_units(flow):
        wf = load_workflow(wf_file)
        if wf is None:
            continue
        wf_on = get_wf_on(wf)

        flow_crons = sorted(
            normalize_cron(c) for c in extract_flow_crons(unit.get("triggers", []))
        )
        wf_crons = sorted(normalize_cron(c) for c in extract_wf_crons(wf_on))

        if flow_crons != wf_crons:
            r.errors.append(
                f"[{label}] Schedule mismatch — "
                f"flow: {flow_crons or '(none)'}, "
                f"workflow: {wf_crons or '(none)'}"
            )
    return r


def check_repository_dispatch(flow: dict) -> CheckResult:
    """repository_dispatch event types must match between flow graph and workflow."""
    r = CheckResult()
    events = flow.get("events", {})

    for label, unit, wf_file in iter_agent_units(flow):
        wf = load_workflow(wf_file)
        if wf is None:
            continue
        wf_on = get_wf_on(wf)

        # Flow graph says this agent listens for these events
        flow_events = sorted(
            t["event"]
            for t in unit.get("triggers", [])
            if t.get("type") == "repository_dispatch"
        )

        # Workflow actually declares these types
        wf_dispatch = wf_on.get("repository_dispatch", {})
        wf_types: list[str] = []
        if isinstance(wf_dispatch, dict):
            wf_types = sorted(wf_dispatch.get("types", []))
        elif isinstance(wf_dispatch, list):
            wf_types = sorted(wf_dispatch)

        # Check flow events exist in registry
        for evt in flow_events:
            if evt not in events:
                r.errors.append(
                    f"[{label}] Trigger event '{evt}' not in events registry"
                )

        # Check bidirectional match
        for evt in flow_events:
            if evt not in wf_types:
                r.errors.append(
                    f"[{label}] Flow declares trigger '{evt}' but workflow "
                    f"types = {wf_types}"
                )
        for evt in wf_types:
            if evt not in flow_events:
                r.errors.append(
                    f"[{label}] Workflow listens for '{evt}' but flow graph "
                    f"does not declare this trigger"
                )
    return r


def check_trigger_types(flow: dict) -> CheckResult:
    """Non-dispatch trigger types (issues, pull_request, check_suite, workflow_dispatch)
    must match between flow graph and workflow."""
    r = CheckResult()
    # Trigger types we cross-check (excludes schedule and repository_dispatch
    # which have their own checks)
    CHECKED_TYPES = {"issues", "pull_request", "check_suite", "workflow_dispatch"}

    for label, unit, wf_file in iter_agent_units(flow):
        wf = load_workflow(wf_file)
        if wf is None:
            continue
        wf_on = get_wf_on(wf)

        # What the flow graph says
        flow_types = {
            t["type"]
            for t in unit.get("triggers", [])
            if t.get("type") in CHECKED_TYPES
        }

        # What the workflow actually has
        wf_types = set()
        for key in CHECKED_TYPES:
            if key in wf_on:
                wf_types.add(key)

        # Check for types in flow but not in workflow
        for t in flow_types - wf_types:
            r.errors.append(
                f"[{label}] Flow declares trigger '{t}' but workflow has no "
                f"on.{t} block"
            )

        # Check for types in workflow but not in flow
        for t in wf_types - flow_types:
            r.errors.append(
                f"[{label}] Workflow has on.{t} but flow graph doesn't declare it"
            )

        # Check trigger actions match for issues and pull_request
        for ttype in ("issues", "pull_request"):
            flow_triggers = [
                t for t in unit.get("triggers", []) if t.get("type") == ttype
            ]
            if not flow_triggers or ttype not in wf_on:
                continue

            flow_actions = set()
            for t in flow_triggers:
                flow_actions.update(t.get("actions", []))

            wf_trigger = wf_on[ttype]
            wf_actions = set()
            if isinstance(wf_trigger, dict):
                wf_actions = set(wf_trigger.get("types", []))
            # Note: GitHub uses "types:" for issues and pull_request

            # Only check if both sides specify actions
            if flow_actions and wf_actions and flow_actions != wf_actions:
                r.warnings.append(
                    f"[{label}] {ttype} actions differ — "
                    f"flow: {sorted(flow_actions)}, workflow: {sorted(wf_actions)}"
                )

    return r


def check_permissions(flow: dict) -> CheckResult:
    """Declared permissions should match the workflow's top-level permissions."""
    r = CheckResult()
    for label, unit, wf_file in iter_agent_units(flow):
        flow_perms = unit.get("permissions", {})
        if not flow_perms:
            continue  # Not all agents declare permissions in flow graph

        wf = load_workflow(wf_file)
        if wf is None:
            continue

        wf_perms = extract_wf_permissions(wf)
        if not wf_perms:
            # Reusable callers may not have top-level permissions
            if unit.get("type") == "reusable":
                continue
            # Custom workflows might rely on defaults
            continue

        # Check each flow-declared permission exists in workflow
        for perm, level in flow_perms.items():
            wf_level = wf_perms.get(perm)
            if wf_level is None:
                r.warnings.append(
                    f"[{label}] Flow declares permission '{perm}: {level}' "
                    f"but workflow doesn't declare it"
                )
            elif wf_level != level:
                r.errors.append(
                    f"[{label}] Permission mismatch for '{perm}' — "
                    f"flow: {level}, workflow: {wf_level}"
                )

        # Check workflow has permissions not in flow graph
        for perm, level in wf_perms.items():
            if perm not in flow_perms:
                r.warnings.append(
                    f"[{label}] Workflow has permission '{perm}: {level}' "
                    f"not declared in flow graph"
                )
    return r


def check_concurrency(flow: dict) -> CheckResult:
    """Concurrency groups should match between flow graph and workflow."""
    r = CheckResult()
    for label, unit, wf_file in iter_agent_units(flow):
        flow_conc = unit.get("concurrency")
        if not flow_conc:
            continue  # Reusable agents inherit concurrency

        wf = load_workflow(wf_file)
        if wf is None:
            continue

        wf_conc = extract_wf_concurrency(wf)
        if not wf_conc:
            # Check job-level concurrency
            jobs = wf.get("jobs", {})
            for job in jobs.values():
                if isinstance(job, dict) and "concurrency" in job:
                    wf_conc = job["concurrency"]
                    break

        if not wf_conc:
            continue

        flow_group = flow_conc.get("group", "")
        wf_group = wf_conc.get("group", "")

        # Workflow groups may use expressions like ${{ ... }}
        # Only compare if the workflow group is a simple string
        if "${{" not in str(wf_group):
            if flow_group != wf_group:
                r.errors.append(
                    f"[{label}] Concurrency group mismatch — "
                    f"flow: '{flow_group}', workflow: '{wf_group}'"
                )

        flow_cancel = flow_conc.get("cancel_in_progress", False)
        wf_cancel = wf_conc.get("cancel-in-progress", False)
        if flow_cancel != wf_cancel:
            r.warnings.append(
                f"[{label}] cancel_in_progress differs — "
                f"flow: {flow_cancel}, workflow: {wf_cancel}"
            )
    return r


def check_harness_refs(flow: dict) -> CheckResult:
    """All workflows must pin the global harness_ref declared in agent-flow.yaml.

    Reusable callers are exempt (they inherit from reusable-agent.yml, which
    IS validated directly). Missing global harness_ref is an error.
    """
    r = CheckResult()
    global_ref = flow.get("harness_ref", "")

    if not global_ref:
        r.errors.append(
            "[config] Missing top-level 'harness_ref' in agent-flow.yaml. "
            'Add: harness_ref: "@v1.2.0"'
        )
        return r

    # Validate reusable-agent.yml itself (the single pin for all reusable callers)
    # Use raw file reader to handle SHA-pinned refs with version comments
    reusable_ref = _find_harness_ref_in_raw_file("reusable-agent.yml")
    if reusable_ref and reusable_ref != global_ref:
        r.errors.append(
            f"[reusable-agent.yml] Harness ref is {reusable_ref}, "
            f"expected {global_ref} (from agent-flow.yaml harness_ref)"
        )

    # Validate all agent workflows
    for label, _unit, wf_file in iter_agent_units(flow):
        wf = load_workflow(wf_file)
        if wf is None:
            continue

        # Skip reusable callers — their pin is validated via reusable-agent.yml above
        if is_reusable_caller(wf):
            continue

        # Use raw file reader to handle SHA-pinned refs with version comments
        wf_ref = _find_harness_ref_in_raw_file(wf_file)
        if wf_ref is None:
            continue

        if wf_ref != global_ref:
            r.errors.append(
                f"[{label}] Harness ref is {wf_ref}, "
                f"expected {global_ref} (from agent-flow.yaml harness_ref)"
            )

    return r


def check_dispatch_targets(flow: dict) -> CheckResult:
    """Dispatch targets must exist. Events registered. Report in_agent."""
    r = CheckResult()
    events = flow.get("events", {})
    agents = flow.get("agents", {})
    infra = flow.get("infrastructure", {})

    dispatched_events: set[str] = set()
    received_events: set[str] = set()

    # Collect valid target names: top-level agents, job IDs, infrastructure
    valid_targets: set[str] = set(agents.keys()) | set(infra.keys())
    for _agent_id, agent in agents.items():
        if "jobs" in agent:
            for job_id in agent["jobs"]:
                valid_targets.add(job_id)

    # Collect received events
    for _, unit, _ in iter_agent_units(flow):
        for t in unit.get("triggers", []):
            if t.get("type") == "repository_dispatch":
                received_events.add(t["event"])

    # Check dispatch targets and events
    for label, unit, _ in iter_agent_units(flow):
        for dispatch in unit.get("dispatches", []):
            targets = dispatch.get("target", [])
            if isinstance(targets, str):
                targets = [targets]

            location = dispatch.get("location", "post_step")

            for target in targets:
                if target not in valid_targets:
                    r.errors.append(
                        f"[{label}] Dispatch target '{target}' not found in "
                        f"agents, jobs, or infrastructure"
                    )

            evt = dispatch.get("event")
            if evt:
                dispatched_events.add(evt)
                if evt not in events:
                    r.errors.append(
                        f"[{label}] Dispatch event '{evt}' not in events registry"
                    )

            if location == "in_agent":
                r.info.append(
                    f"[{label}] Dispatch to {targets} is in_agent "
                    f"(not validatable at workflow level)"
                )

    # Check for orphan events
    for evt_name, evt_config in events.items():
        evt_status = (evt_config or {}).get("status", "")
        is_exempt = evt_status in ("stub", "external")

        if evt_name not in dispatched_events and evt_name not in received_events:
            if not is_exempt:
                r.errors.append(
                    f"[events] '{evt_name}' declared but never dispatched or received"
                )
        elif evt_name not in dispatched_events and not is_exempt:
            r.warnings.append(
                f"[events] '{evt_name}' has receivers but no sender "
                f"(add 'status: stub' if intentional)"
            )

    return r


def check_job_params(flow: dict) -> CheckResult:
    """Verify that workflow with.job: parameters match flow graph job keys.

    For multi-job agents (like tech-lead), each workflow passes a `job` parameter
    to the harness via `with: { job: ... }`. This must match the job key in the
    flow YAML.
    """
    r = CheckResult()
    for agent_id, agent in flow.get("agents", {}).items():
        if "jobs" not in agent:
            continue
        for job_id, job in agent["jobs"].items():
            wf_file = job.get("workflow", "")
            wf = load_workflow(wf_file)
            if wf is None:
                continue

            # Find the step that calls agent-harness and extract with.job
            wf_job_param = _extract_harness_job_param(wf)
            if wf_job_param is None:
                r.warnings.append(
                    f"[{agent_id}/{job_id}] Could not find harness job: parameter "
                    f"in {wf_file}"
                )
                continue

            if wf_job_param != job_id:
                r.errors.append(
                    f"[{agent_id}/{job_id}] Workflow passes job: '{wf_job_param}' "
                    f"to harness but flow graph key is '{job_id}'"
                )

    return r


def _extract_harness_job_param(wf: dict) -> str | None:
    """Extract the `with.job` value from the harness step in a workflow."""
    for job in wf.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses", ""))
            if "agent-harness" in uses:
                with_block = step.get("with", {})
                if isinstance(with_block, dict) and "job" in with_block:
                    return str(with_block["job"])
    return None


def check_reusable_structure(flow: dict) -> CheckResult:
    """Agents marked as type: reusable should actually call reusable-agent.yml."""
    r = CheckResult()
    for label, unit, wf_file in iter_agent_units(flow):
        if unit.get("type") != "reusable":
            continue

        wf = load_workflow(wf_file)
        if wf is None:
            continue

        if not is_reusable_caller(wf):
            r.errors.append(
                f"[{label}] Declared type: reusable but workflow doesn't call "
                f"reusable-agent.yml"
            )

    # Also check the reverse: workflows that call reusable-agent.yml but
    # aren't marked as reusable
    for label, unit, wf_file in iter_agent_units(flow):
        if unit.get("type") == "reusable":
            continue

        wf = load_workflow(wf_file)
        if wf is None:
            continue

        if is_reusable_caller(wf):
            r.warnings.append(
                f"[{label}] Calls reusable-agent.yml but not marked type: reusable"
            )

    return r


# ── Main Validation ──────────────────────────────────────────────


def validate(flow: dict) -> CheckResult:
    """Run all validation checks."""
    return merge_results(
        check_workflow_exists(flow),
        check_orphan_workflows(flow),
        check_schedule_crons(flow),
        check_repository_dispatch(flow),
        check_trigger_types(flow),
        check_permissions(flow),
        check_concurrency(flow),
        check_harness_refs(flow),
        check_dispatch_targets(flow),
        check_job_params(flow),
        check_reusable_structure(flow),
    )


# ── Mermaid Generation ───────────────────────────────────────────


def _multi_job_node_id(agent_id: str, job_id: str) -> str:
    """Build a Mermaid node ID for a multi-job agent's job.

    Derives the prefix from the parent agent ID, so adding a second
    multi-job agent won't collide with hardcoded prefixes.
    """
    prefix = agent_id.upper().replace("-", "_")
    suffix = job_id.upper().replace("-", "_")
    return f"{prefix}_{suffix}"


def generate_mermaid(flow: dict) -> str:
    """Generate a Mermaid flowchart from the v2 flow graph."""
    agents = flow.get("agents", {})
    infra = flow.get("infrastructure", {})
    lines: list[str] = []
    lines.append("```mermaid")
    lines.append("flowchart TD")

    def node_id(name: str) -> str:
        return name.upper().replace("-", "_")

    def node_label(name: str) -> str:
        return name.replace("-", " ").title()

    # ── Subgraph: Core Dev Loop ──
    core_dev = ["triage", "product-owner", "engineer", "ops-engineer", "reviewer"]
    lines.append("")
    lines.append("    subgraph core[Core Dev Loop]")
    for a in core_dev:
        if a in agents:
            lines.append(f"        {node_id(a)}[{node_label(a)}]")
    lines.append("    end")

    # ── Subgraph: Strategic / Intelligence ──
    strategic_agents = [
        "strategic",
        "product-analyst",
        "financial-analyst",
        "marketing-strategist",
    ]
    lines.append("")
    lines.append("    subgraph strat[Strategic / Intelligence]")
    for a in strategic_agents:
        if a in agents:
            lines.append(f"        {node_id(a)}[{node_label(a)}]")
    lines.append("    end")

    # ── Subgraph: Tech Lead (multi-job) ──
    if "tech-lead" in agents and "jobs" in agents["tech-lead"]:
        lines.append("")
        lines.append("    subgraph techlead[Tech Lead]")
        for job_id, job in agents["tech-lead"]["jobs"].items():
            jid = _multi_job_node_id("tech-lead", job_id)
            jlabel = job_id.replace("-", " ").title()
            crons = extract_flow_crons(job.get("triggers", []))
            day = cron_day_label(crons[0]) if crons else ""
            suffix = f" ({day})" if day else ""
            lines.append(f"        {jid}[{jlabel}{suffix}]")
        lines.append("    end")

    # ── Subgraph: Operations ──
    ops_agents = [
        "site-reliability",
        "qa-analyst",
        "customer-ops",
        "human-ops",
        "escalation-lead",
    ]
    lines.append("")
    lines.append("    subgraph ops[Operations]")
    for a in ops_agents:
        if a in agents:
            lines.append(f"        {node_id(a)}[{node_label(a)}]")
    lines.append("    end")

    # ── Subgraph: Content ──
    content_agents = ["content-creator", "user-experience"]
    lines.append("")
    lines.append("    subgraph content[Content]")
    for a in content_agents:
        if a in agents:
            lines.append(f"        {node_id(a)}[{node_label(a)}]")
    lines.append("    end")

    # ── Subgraph: Infrastructure ──
    if infra:
        lines.append("")
        lines.append("    subgraph infra_wf[Infrastructure]")
        for iid in infra:
            lines.append(f"        {node_id(iid)}_WF[{node_label(iid)}]:::infraStyle")
        lines.append("    end")

    # ── External Trigger Nodes ──
    lines.append("")
    lines.append("    ISSUE_OPENED{{Issue Opened}}:::external")
    lines.append("    ISSUE_LABELED{{Issue Labeled}}:::external")
    lines.append("    PR_OPENED{{PR Opened}}:::external")
    lines.append("    PR_MERGED{{PR Merged}}:::external")
    lines.append("    CHECK_SUITE{{Check Suite}}:::external")
    lines.append("    AZURE_ALERT{{Azure Alert}}:::external")
    lines.append("")

    # ── Dispatch Edges ──
    # Regular agents
    for agent_id, agent in agents.items():
        if "jobs" in agent:
            continue  # Handle below
        src = node_id(agent_id)
        for dispatch in agent.get("dispatches", []):
            _draw_dispatch(lines, src, dispatch, agents, infra)

    # Multi-job agents (tech-lead etc.)
    for agent_id, agent in agents.items():
        if "jobs" not in agent:
            continue
        for job_id, job in agent["jobs"].items():
            src = _multi_job_node_id(agent_id, job_id)
            for dispatch in job.get("dispatches", []):
                _draw_dispatch(lines, src, dispatch, agents, infra)

    lines.append("")

    # ── External Trigger Edges ──
    for agent_id, agent in agents.items():
        if "jobs" in agent:
            # Tech-lead jobs don't have external triggers beyond schedule
            continue
        nid = node_id(agent_id)
        for trigger in agent.get("triggers", []):
            ttype = trigger.get("type", "")
            actions = trigger.get("actions", [])
            if ttype == "issues":
                if "opened" in actions:
                    lines.append(f"    ISSUE_OPENED -.-> {nid}")
                if "labeled" in actions or "unlabeled" in actions:
                    lines.append(f"    ISSUE_LABELED -.-> {nid}")
            elif ttype == "pull_request":
                if "opened" in actions or "synchronize" in actions:
                    lines.append(f"    PR_OPENED -.-> {nid}")
                if "closed" in actions:
                    lines.append(f"    PR_MERGED -.-> {nid}")
            elif ttype == "check_suite":
                lines.append(f"    CHECK_SUITE -.-> {nid}")
            elif ttype == "repository_dispatch":
                if trigger.get("event") == "azure-alert":
                    lines.append(f"    AZURE_ALERT -.-> {nid}")

    lines.append("")

    # ── Style Definitions ──
    lines.append("    classDef external fill:#f9f,stroke:#333,stroke-width:1px")
    lines.append("    classDef core fill:#4a9eff,stroke:#333,color:#fff")
    lines.append("    classDef strat fill:#2ecc71,stroke:#333,color:#fff")
    lines.append("    classDef opsStyle fill:#e67e22,stroke:#333,color:#fff")
    lines.append("    classDef contentStyle fill:#9b59b6,stroke:#333,color:#fff")
    lines.append("    classDef infraStyle fill:#95a5a6,stroke:#333,color:#fff")
    lines.append("    classDef techleadStyle fill:#1abc9c,stroke:#333,color:#fff")

    # ── Apply Classes ──
    for a in core_dev:
        if a in agents:
            lines.append(f"    class {node_id(a)} core")
    for a in strategic_agents:
        if a in agents:
            lines.append(f"    class {node_id(a)} strat")
    for a in ops_agents:
        if a in agents:
            lines.append(f"    class {node_id(a)} opsStyle")
    for a in content_agents:
        if a in agents:
            lines.append(f"    class {node_id(a)} contentStyle")
    if "tech-lead" in agents and "jobs" in agents["tech-lead"]:
        for job_id in agents["tech-lead"]["jobs"]:
            jid = _multi_job_node_id("tech-lead", job_id)
            lines.append(f"    class {jid} techleadStyle")

    lines.append("```")
    return "\n".join(lines)


def _resolve_node_id(target: str, agents: dict, infra: dict) -> str:
    """Resolve a dispatch target name to its Mermaid node ID."""
    if target in infra:
        return f"{target.upper().replace('-', '_')}_WF"
    if target in agents:
        return target.upper().replace("-", "_")
    # Check if target matches a job ID within a multi-job agent
    for agent_id, agent in agents.items():
        if "jobs" in agent and target in agent["jobs"]:
            return _multi_job_node_id(agent_id, target)
    return target.upper().replace("-", "_")


def _draw_dispatch(
    lines: list[str],
    src: str,
    dispatch: dict,
    agents: dict,
    infra: dict,
) -> None:
    """Draw a single dispatch edge."""
    targets = dispatch.get("target", [])
    if isinstance(targets, str):
        targets = [targets]

    condition = dispatch.get("condition", {})
    cond_type = condition.get("type", "")
    location = dispatch.get("location", "post_step")

    # Build edge label
    label_parts = []
    if cond_type == "intake_batch":
        label_parts.append(f"batch≥{condition.get('threshold', '?')}")
    elif cond_type == "unassigned_issues":
        label_parts.append("unassigned>0")
    elif cond_type == "changes_requested":
        label_parts.append("changes requested")
    elif cond_type == "idle_backlog":
        label_parts.append(f"idle, PM>{condition.get('pm_cooldown_hours', '?')}h")
    elif cond_type == "untriaged_label":
        label_parts.append(f"untriaged {condition.get('label', '?')}")
    elif cond_type == "unconditional":
        label_parts.append("always")
    elif cond_type == "agent_driven":
        label_parts.append("agent decision")
    elif cond_type:
        label_parts.append(cond_type)

    # Mark in_agent dispatches
    if location == "in_agent":
        label_parts.append("*")

    label = " ".join(label_parts)

    # Arrow style: solid for repository_dispatch, dashed for workflow_run
    method = dispatch.get("method", "")
    if location == "in_agent":
        style = "-.->"  # Always dashed for in_agent
    elif method == "repository_dispatch":
        style = "-->"
    else:
        style = "-.->"

    for target in targets:
        dst = _resolve_node_id(target, agents, infra)
        if label:
            lines.append(f'    {src} {style}|"{label}"| {dst}')
        else:
            lines.append(f"    {src} {style} {dst}")


def generate_event_table(flow: dict) -> str:
    """Generate a markdown table of all events."""
    events = flow.get("events", {})
    lines = ["| Event | Description | Status |", "|-------|-------------|--------|"]
    for name, config in sorted(events.items()):
        config = config or {}
        desc = config.get("description", "")
        status = config.get("status", "active")
        payload = config.get("payload", [])
        if payload:
            desc += f" (payload: {', '.join(payload)})"
        lines.append(f"| `{name}` | {desc} | {status} |")
    return "\n".join(lines)


def generate_schedule_table(flow: dict) -> str:
    """Generate a markdown table of agent schedules (including tech-lead jobs)."""
    agents = flow.get("agents", {})
    rows: list[tuple[str, str, str, str]] = []  # (agent, schedule, day, triggers)

    for agent_id, agent in sorted(agents.items()):
        if "jobs" in agent:
            # Multi-job: one row per job
            for job_id, job in sorted(agent["jobs"].items()):
                label = f"{agent_id}/{job_id}"
                crons = extract_flow_crons(job.get("triggers", []))
                dispatch_triggers = _format_triggers(job.get("triggers", []))
                for cron in crons:
                    day = cron_day_label(cron)
                    rows.append((label, f"`{cron}`", day, dispatch_triggers))
                if not crons:
                    rows.append((label, "---", "", dispatch_triggers))
        else:
            crons = extract_flow_crons(agent.get("triggers", []))
            dispatch_triggers = _format_triggers(agent.get("triggers", []))
            for cron in crons:
                day = cron_day_label(cron)
                rows.append((agent_id, f"`{cron}`", day, dispatch_triggers))
            if not crons:
                rows.append((agent_id, "---", "", dispatch_triggers))

    lines = [
        "| Agent | Schedule | Day | Event Triggers |",
        "|-------|----------|-----|----------------|",
    ]
    for agent, sched, day, triggers in rows:
        lines.append(f"| {agent} | {sched} | {day} | {triggers} |")
    return "\n".join(lines)


def _format_triggers(triggers: list[dict]) -> str:
    """Format non-schedule triggers as a comma-separated string."""
    parts = []
    for t in triggers:
        ttype = t.get("type", "")
        if ttype == "schedule":
            continue
        elif ttype == "repository_dispatch":
            parts.append(f"`{t.get('event', '?')}`")
        elif ttype == "pull_request":
            actions = t.get("actions", [])
            parts.append(f"PR {'/'.join(actions)}")
        elif ttype == "issues":
            actions = t.get("actions", [])
            parts.append(f"Issues {'/'.join(actions)}")
        elif ttype == "check_suite":
            parts.append("Check suite")
        elif ttype == "workflow_dispatch":
            parts.append("Manual")
    return ", ".join(parts) if parts else "---"


def generate_safety_section(flow: dict) -> str:
    """Generate safety constraints section."""
    safety = flow.get("safety", {})
    if not safety:
        return ""
    lines = ["| Constraint | Value |", "|------------|-------|"]
    for key, value in sorted(safety.items()):
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def write_doc(flow: dict, output_path: Path) -> None:
    """Write the full generated documentation file."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    mermaid = generate_mermaid(flow)
    event_table = generate_event_table(flow)
    schedule_table = generate_schedule_table(flow)
    safety_section = generate_safety_section(flow)

    header = "<!-- AUTO-GENERATED — Do not edit."
    header += " Edit config/agent-flow.yaml instead. -->"
    content = f"""{header}
<!-- Last generated: {now} -->
<!-- Regenerate: python scripts/validate-flow.py --mermaid -o docs/agent-flow.md -->

# Agent Flow Graph

Visual representation of how agents interact through dispatches, events, and triggers.

**Source of truth**: `config/agent-flow.yaml` (v2 schema)

**Legend:**
- **Blue** = Core dev loop (triage, PO, engineers, reviewers)
- **Green** = Strategic (PM, analysts)
- **Teal** = Tech Lead (multi-job agent)
- **Orange** = Operations (SRE, QA, customer ops, human ops)
- **Purple** = Content (creator, UX)
- **Grey** = Infrastructure workflows (deploy, ingest, CI)
- **Pink** = External triggers (PRs, issues, alerts)
- **Solid arrows** = `repository_dispatch` (event-based)
- **Dashed arrows** = `workflow_run` or external trigger
- **`*`** = dispatch happens inside agent session (not in workflow YAML)

{mermaid}

## Events

{event_table}

## Agent Schedules

{schedule_table}

## Safety Constraints

{safety_section}
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"Generated: {output_path}")


# ── CLI ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Validate agent flow graph (v2)")
    parser.add_argument("--validate", action="store_true", help="Run validation checks")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (for CI)",
    )
    parser.add_argument(
        "--mermaid", action="store_true", help="Generate Mermaid diagram"
    )
    parser.add_argument(
        "-o", "--output", type=str, help="Output file for Mermaid diagram"
    )
    args = parser.parse_args()

    if not args.validate and not args.mermaid:
        parser.print_help()
        sys.exit(1)

    flow = load_flow()
    exit_code = 0

    if args.validate:
        result = validate(flow)

        # Count units
        units = list(iter_agent_units(flow))
        events = flow.get("events", {})

        if result.errors:
            print(f"Flow validation FAILED ({len(result.errors)} errors):\n")
            for err in result.errors:
                print(f"  \u2717 {err}")
            exit_code = 1

        if result.warnings:
            if exit_code == 0:
                print("")
            print(f"Warnings ({len(result.warnings)}):\n")
            for warn in result.warnings:
                print(f"  \u26a0 {warn}")
            if args.strict:
                exit_code = 1

        if result.info:
            print(f"\nInfo ({len(result.info)}):\n")
            for info in result.info:
                print(f"  \u2139 {info}")

        if exit_code == 0:
            print(
                f"\nFlow validation passed — {len(units)} units, "
                f"{len(events)} events, all consistent."
            )
        print("")

    if args.mermaid:
        if args.output:
            write_doc(flow, Path(args.output))
        else:
            print(generate_mermaid(flow))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
