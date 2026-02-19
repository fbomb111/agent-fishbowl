#!/usr/bin/env python3
"""Validate agent flow graph against actual workflow files and generate diagrams.

Usage:
    python scripts/validate-flow.py --validate          # CI mode: exit 0/1
    python scripts/validate-flow.py --mermaid           # Print Mermaid to stdout
    python scripts/validate-flow.py --mermaid -o FILE   # Write Mermaid to file
    python scripts/validate-flow.py --validate --mermaid -o docs/agent-flow.md  # Both
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_FILE = REPO_ROOT / "config" / "agent-flow.yaml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def load_flow() -> dict:
    with open(FLOW_FILE) as f:
        return yaml.safe_load(f)


def load_workflow(filename: str) -> dict | None:
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def validate(flow: dict) -> list[str]:
    """Run all validation checks. Returns list of error messages."""
    errors: list[str] = []
    events = flow.get("events", {})
    agents = flow.get("agents", {})

    # Track which events are dispatched and which are received
    dispatched_events: set[str] = set()
    received_events: set[str] = set()

    for agent_id, agent in agents.items():
        workflow_file = agent.get("workflow")
        if not workflow_file:
            errors.append(f"[{agent_id}] Missing 'workflow' field")
            continue

        # Check workflow file exists
        if not (WORKFLOWS_DIR / workflow_file).exists():
            errors.append(
                f"[{agent_id}] Workflow file not found: .github/workflows/{workflow_file}"
            )

        # Load actual workflow to cross-check triggers
        wf = load_workflow(workflow_file)
        if wf is None:
            continue

        wf_on = wf.get("on") or wf.get(True) or {}

        # Check repository_dispatch triggers match
        flow_dispatch_events = [
            t["event"]
            for t in agent.get("triggers", [])
            if t.get("type") == "repository_dispatch"
        ]
        for evt in flow_dispatch_events:
            received_events.add(evt)

            # Verify event is in the registry
            if evt not in events:
                errors.append(
                    f"[{agent_id}] Trigger event '{evt}' not in events registry"
                )

            # Verify workflow actually declares this event type
            wf_dispatch = wf_on.get("repository_dispatch", {})
            wf_types = []
            if isinstance(wf_dispatch, dict):
                wf_types = wf_dispatch.get("types", [])
            elif isinstance(wf_dispatch, list):
                wf_types = wf_dispatch

            if evt not in wf_types:
                errors.append(
                    f"[{agent_id}] Flow declares trigger event '{evt}' but "
                    f"{workflow_file} on.repository_dispatch.types = {wf_types}"
                )

        # Check for undeclared repository_dispatch types in the workflow
        wf_dispatch = wf_on.get("repository_dispatch", {})
        wf_types = []
        if isinstance(wf_dispatch, dict):
            wf_types = wf_dispatch.get("types", [])
        for wf_evt in wf_types:
            if not any(
                t.get("event") == wf_evt
                for t in agent.get("triggers", [])
                if t.get("type") == "repository_dispatch"
            ):
                errors.append(
                    f"[{agent_id}] Workflow {workflow_file} listens for '{wf_evt}' "
                    f"but flow graph does not declare this trigger"
                )

        # Check dispatch targets exist and events are registered
        for dispatch in agent.get("dispatches", []):
            targets = dispatch.get("target", [])
            if isinstance(targets, str):
                targets = [targets]

            for target in targets:
                # Skip non-agent targets (like 'ingest')
                if target not in agents and target != "ingest":
                    errors.append(
                        f"[{agent_id}] Dispatch target '{target}' not found in agents"
                    )

            evt = dispatch.get("event")
            if evt:
                dispatched_events.add(evt)
                if evt not in events:
                    errors.append(
                        f"[{agent_id}] Dispatch event '{evt}' not in events registry"
                    )

    # Check for orphan events (in registry but never dispatched or received)
    for evt_name, evt_config in events.items():
        evt_status = (evt_config or {}).get("status", "")
        is_exempt = evt_status in ("stub", "external")
        if evt_name not in dispatched_events and not is_exempt:
            if evt_name not in received_events:
                errors.append(
                    f"[events] '{evt_name}' declared but never dispatched or received"
                )
            # Event received but never dispatched (and not stub)
            elif evt_name not in dispatched_events:
                errors.append(
                    f"[events] '{evt_name}' has receivers but no sender "
                    f"(add 'status: stub' if intentional)"
                )

    return errors


def generate_mermaid(flow: dict) -> str:
    """Generate a Mermaid flowchart from the flow graph."""
    agents = flow.get("agents", {})
    lines: list[str] = []
    lines.append("```mermaid")
    lines.append("flowchart TD")

    # Categorize agents for subgraph grouping
    core_dev = {
        "triage",
        "product-owner",
        "engineer",
        "infra-engineer",
        "reviewer",
    }
    strategic = {
        "strategic",
        "scans",
        "product-analyst",
        "financial-analyst",
        "marketing-strategist",
    }
    ops = {
        "site-reliability",
        "qa-analyst",
        "customer-ops",
        "human-ops",
        "escalation-lead",
    }
    content = {"content-creator", "user-experience"}

    def node_id(name: str) -> str:
        return name.upper().replace("-", "_")

    def node_label(name: str) -> str:
        return name.replace("-", " ").title()

    # Define all nodes with shapes
    for agent_id in agents:
        nid = node_id(agent_id)
        label = node_label(agent_id)
        lines.append(f"    {nid}[{label}]")

    lines.append("")

    # External trigger nodes
    lines.append("    PR_EVENT{{PR Opened}}:::external")
    lines.append("    PR_MERGED{{PR Merged}}:::external")
    lines.append("    ISSUE_OPENED{{Issue Opened}}:::external")
    lines.append("    AZURE_ALERT{{Azure Alert}}:::external")
    lines.append("    CI_FAILURE{{CI Failure}}:::external")
    lines.append("")

    # Draw dispatch edges
    for agent_id, agent in agents.items():
        src = node_id(agent_id)

        for dispatch in agent.get("dispatches", []):
            targets = dispatch.get("target", [])
            if isinstance(targets, str):
                targets = [targets]

            condition = dispatch.get("condition", {})
            cond_type = condition.get("type", "")

            # Build edge label
            if cond_type == "intake_batch":
                label = f"batch≥{condition.get('threshold', '?')}"
            elif cond_type == "unassigned_issues":
                label = "unassigned>0"
            elif cond_type == "changes_requested":
                label = "changes requested"
            elif cond_type == "idle_backlog":
                label = f"idle, PM>{condition.get('pm_cooldown_hours', '?')}h"
            elif cond_type == "untriaged_label":
                label = f"untriaged {condition.get('label', '?')}"
            elif cond_type == "unconditional":
                label = "always"
            elif cond_type == "agent_driven":
                label = "agent decision"
            else:
                label = cond_type or ""

            method = dispatch.get("method", "")
            style = "-->" if method == "repository_dispatch" else "-.->"

            for target in targets:
                if target == "ingest":
                    lines.append(f'    {src} {style}|"{label}"| INGEST_WF[Ingest]')
                elif target in agents:
                    dst = node_id(target)
                    lines.append(f'    {src} {style}|"{label}"| {dst}')

    lines.append("")

    # Draw external trigger edges
    for agent_id, agent in agents.items():
        nid = node_id(agent_id)
        for trigger in agent.get("triggers", []):
            ttype = trigger.get("type", "")
            if ttype == "pull_request" or ttype.startswith("pull_request"):
                actions = trigger.get("actions", [])
                if "opened" in actions or "synchronize" in actions:
                    lines.append(f"    PR_EVENT -.-> {nid}")
            if ttype == "pull_request.closed":
                lines.append(f"    PR_MERGED -.-> {nid}")
            if ttype == "issues.opened":
                lines.append(f"    ISSUE_OPENED -.-> {nid}")
            if ttype == "repository_dispatch" and trigger.get("event") == "azure-alert":
                lines.append(f"    AZURE_ALERT -.-> {nid}")
            if ttype == "check_suite.completed":
                lines.append(f"    CI_FAILURE -.-> {nid}")

    lines.append("")

    # Style classes
    lines.append("    classDef external fill:#f9f,stroke:#333,stroke-width:1px")
    lines.append("    classDef core fill:#4a9eff,stroke:#333,color:#fff")
    lines.append("    classDef strat fill:#2ecc71,stroke:#333,color:#fff")
    lines.append("    classDef opsStyle fill:#e67e22,stroke:#333,color:#fff")
    lines.append("    classDef contentStyle fill:#9b59b6,stroke:#333,color:#fff")

    # Apply classes
    for agent_id in agents:
        nid = node_id(agent_id)
        if agent_id in core_dev:
            lines.append(f"    class {nid} core")
        elif agent_id in strategic:
            lines.append(f"    class {nid} strat")
        elif agent_id in ops:
            lines.append(f"    class {nid} opsStyle")
        elif agent_id in content:
            lines.append(f"    class {nid} contentStyle")

    lines.append("```")
    return "\n".join(lines)


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
    """Generate a markdown table of agent schedules."""
    agents = flow.get("agents", {})
    lines = [
        "| Agent | Schedule | Dispatch Triggers |",
        "|-------|----------|-------------------|",
    ]
    for agent_id, agent in sorted(agents.items()):
        schedules = []
        dispatch_triggers = []
        for t in agent.get("triggers", []):
            if t.get("type") == "schedule":
                schedules.append(t.get("cron", "?"))
            elif t.get("type") == "repository_dispatch":
                dispatch_triggers.append(f"`{t.get('event', '?')}`")
            elif t.get("type") in ("pull_request", "pull_request.closed"):
                dispatch_triggers.append("PR event")
            elif t.get("type") == "issues.opened":
                dispatch_triggers.append("Issue opened")
            elif t.get("type") == "check_suite.completed":
                dispatch_triggers.append("CI failure")
            elif t.get("type") == "workflow_dispatch":
                dispatch_triggers.append("Manual only")

        sched_str = ", ".join(f"`{s}`" for s in schedules) if schedules else "—"
        disp_str = ", ".join(dispatch_triggers) if dispatch_triggers else "—"
        lines.append(f"| {agent_id} | {sched_str} | {disp_str} |")
    return "\n".join(lines)


def write_doc(flow: dict, output_path: Path) -> None:
    """Write the full generated documentation file."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    mermaid = generate_mermaid(flow)
    event_table = generate_event_table(flow)
    schedule_table = generate_schedule_table(flow)

    content = f"""<!-- AUTO-GENERATED — Do not edit. Edit config/agent-flow.yaml instead. -->
<!-- Last generated: {now} -->
<!-- Regenerate: python scripts/validate-flow.py --mermaid -o docs/agent-flow.md -->

# Agent Flow Graph

Visual representation of how agents interact through dispatches, events, and triggers.

**Legend:**
- **Blue** = Core dev loop (triage, PO, engineers, reviewers)
- **Green** = Strategic (PM, scans, analysts)
- **Orange** = Operations (SRE, QA, customer ops, human ops)
- **Purple** = Content (creator, UX)
- **Pink** = External triggers (PRs, issues, alerts)
- **Solid arrows** = `repository_dispatch` (event-based)
- **Dashed arrows** = `workflow_run` or external trigger

{mermaid}

## Events

{event_table}

## Agent Schedules

{schedule_table}
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"Generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate agent flow graph")
    parser.add_argument("--validate", action="store_true", help="Run validation checks")
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
        errors = validate(flow)
        if errors:
            print(f"Flow validation FAILED ({len(errors)} errors):\n")
            for err in errors:
                print(f"  ✗ {err}")
            exit_code = 1
        else:
            print(
                f"Flow validation passed — {len(flow.get('agents', {}))} agents, "
                f"{len(flow.get('events', {}))} events, all consistent."
            )

    if args.mermaid:
        if args.output:
            write_doc(flow, Path(args.output))
        else:
            print(generate_mermaid(flow))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
