#!/bin/bash
# PO (Product Owner) agent — triages intake and maintains the prioritized backlog.
exec "$(dirname "$0")/run-agent.sh" po
