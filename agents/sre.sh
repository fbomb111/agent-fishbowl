#!/bin/bash
# SRE agent — monitors system health and files issues for problems.
exec "$(dirname "$0")/run-agent.sh" sre
