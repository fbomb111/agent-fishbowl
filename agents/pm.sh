#!/bin/bash
# PM (Product Manager) agent — reads goals.md and evolves ROADMAP.md.
# Strategic counterpart to the PO: PM sets the vision, PO executes the backlog.
exec "$(dirname "$0")/run-agent.sh" pm
