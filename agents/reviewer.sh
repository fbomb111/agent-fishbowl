#!/bin/bash
# Reviewer agent — reviews PRs, approves and merges or requests changes.
exec "$(dirname "$0")/run-agent.sh" reviewer
