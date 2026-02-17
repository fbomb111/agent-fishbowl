#!/bin/bash
# Provision a fresh Ubuntu 24.04 VM as a GitHub Actions self-hosted runner
# for the Agent Fishbowl project.
#
# Usage (on the new VM):
#   curl -sL <raw-url> | bash
#   — or —
#   scp this file to the VM and run: bash setup.sh
#
# After running this script, you still need to:
#   1. Copy secrets:  scp ~/.config/agent-harness/.env and PEM keys
#   2. Register the GitHub Actions runner (see bottom of this script)
#   3. Log in to Claude Code: claude (one-time interactive auth)
set -euo pipefail

echo "=== Agent VM Provisioning ==="
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# --- System updates ---
echo "▸ Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# --- Core tools ---
echo "▸ Installing core tools (jq, curl, openssl, unzip)..."
sudo apt-get install -y -qq jq curl openssl unzip software-properties-common apt-transport-https ca-certificates gnupg

# --- Git ---
echo "▸ Installing Git..."
sudo apt-get install -y -qq git

# --- Python 3.12 ---
echo "▸ Installing Python 3.12..."
sudo apt-get install -y -qq python3 python3-pip python3-venv
python3 --version

# --- Node.js 20 (via NodeSource) ---
echo "▸ Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y -qq nodejs
node --version
npm --version

# --- GitHub CLI ---
echo "▸ Installing GitHub CLI..."
(type -p wget >/dev/null || sudo apt-get install wget -y -qq) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O"$out" https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat "$out" | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli-stable.list > /dev/null \
  && sudo apt-get update -qq \
  && sudo apt-get install -y -qq gh
gh --version

# --- Azure CLI ---
echo "▸ Installing Azure CLI..."
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az --version | head -1

# --- Docker ---
echo "▸ Installing Docker..."
sudo apt-get install -y -qq docker.io
sudo usermod -aG docker "$USER"
docker --version

# --- Claude Code ---
echo "▸ Installing Claude Code..."
sudo npm install -g @anthropic-ai/claude-code
claude --version 2>/dev/null || echo "  (Claude Code installed — run 'claude' to authenticate)"

# --- Create config directories ---
echo "▸ Creating config directories..."
mkdir -p ~/.config/agent-harness
mkdir -p ~/.config/agent-fishbowl
chmod 700 ~/.config/agent-fishbowl  # PEM keys live here

# --- Create project directory ---
echo "▸ Creating project directory..."
mkdir -p ~/projects

echo ""
echo "=== Provisioning Complete ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "Installed:"
echo "  Node.js:    $(node --version)"
echo "  Python:     $(python3 --version 2>&1)"
echo "  Git:        $(git --version)"
echo "  GitHub CLI: $(gh --version | head -1)"
echo "  Azure CLI:  $(az --version | head -1)"
echo "  Docker:     $(docker --version)"
echo ""
echo "=== Next Steps ==="
echo ""
echo "1. Copy secrets from dev VM:"
echo "   scp ~/.config/agent-harness/.env fcleary@$(hostname -I | awk '{print $1}'):~/.config/agent-harness/.env"
echo "   scp ~/.config/agent-fishbowl/*.pem fcleary@$(hostname -I | awk '{print $1}'):~/.config/agent-fishbowl/"
echo ""
echo "2. Clone the project:"
echo "   git clone https://github.com/YourMoveLabs/agent-fishbowl.git ~/projects/agent-fishbowl"
echo "   cd ~/projects/agent-fishbowl && git checkout stable"
echo "   python3 -m venv .venv && source .venv/bin/activate && pip install ruff"
echo ""
echo "3. Register the GitHub Actions runner:"
echo "   mkdir -p ~/fishbowl-runner && cd ~/fishbowl-runner"
echo "   RUNNER_VERSION=\$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/v//')"
echo "   curl -o actions-runner.tar.gz -L \"https://github.com/actions/runner/releases/download/v\${RUNNER_VERSION}/actions-runner-linux-x64-\${RUNNER_VERSION}.tar.gz\""
echo "   tar xzf actions-runner.tar.gz"
echo "   ./config.sh --url https://github.com/YourMoveLabs/agent-fishbowl --token <REG_TOKEN> --name fishbowl-agents --labels self-hosted,Linux,X64 --work _work"
echo "   sudo ./svc.sh install && sudo ./svc.sh start"
echo ""
echo "4. Authenticate Claude Code (one-time):"
echo "   claude"
echo ""
echo "5. (On dev VM) Deregister old runner:"
echo "   cd ~/agent-fishbowl-runner && sudo ./svc.sh stop && sudo ./svc.sh uninstall"
echo "   ./config.sh remove --token <REMOVE_TOKEN>"
