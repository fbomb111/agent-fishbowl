#!/bin/bash
# PM (Product Manager) agent — strategic roadmap evolution (Phase 3).
# NOTE: The tactical backlog role moved to po.sh. This will be repurposed
# for the strategic PM agent that reads goals.md and updates ROADMAP.md.
exec "$(dirname "$0")/run-agent.sh" pm
