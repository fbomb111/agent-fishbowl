#!/bin/bash
# Triage agent — validates human-created issues before they enter the PO's intake queue.
exec "$(dirname "$0")/run-agent.sh" triage
