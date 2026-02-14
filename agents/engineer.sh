#!/bin/bash
# Engineer agent — picks an issue, implements it, opens a draft PR.
exec "$(dirname "$0")/run-agent.sh" engineer
