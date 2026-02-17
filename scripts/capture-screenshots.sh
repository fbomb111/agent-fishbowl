#!/bin/bash
# capture-screenshots.sh — Capture production screenshots for UX review.
# Uses Playwright to screenshot every page at desktop and mobile viewports.
# Outputs JSON with file paths to stdout.
#
# Usage: scripts/capture-screenshots.sh [OPTIONS]
#
# Options:
#   --url URL          Base URL to screenshot (default: https://agentfishbowl.com)
#   --output-dir DIR   Directory for screenshots (default: /tmp/ux-screenshots)
#   --routes R1,R2     Comma-separated routes (default: /,/activity,/blog,/feedback,/goals)
#   --help             Show this help
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UX_DIR="$SCRIPT_DIR/ux"

# --- Help ---
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    head -12 "$0" | tail -10 | sed 's/^# //' | sed 's/^#//'
    exit 0
fi

# --- Install dependencies if needed ---
if [ ! -d "$UX_DIR/node_modules" ]; then
    echo "Installing Playwright dependencies..." >&2
    (cd "$UX_DIR" && npm install --silent 2>&1) >&2
fi

# --- Install Chromium browser if needed ---
if ! npx --prefix "$UX_DIR" playwright install chromium 2>&1 | grep -q "already"; then
    echo "Chromium browser installed." >&2
fi

# --- Run capture script ---
node "$UX_DIR/capture.mjs" "$@"
