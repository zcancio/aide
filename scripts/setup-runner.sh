#!/bin/bash
# AIde — Self-Hosted GitHub Actions Runner Setup
# Run on your Ubuntu server: bash setup-runner.sh
#
# Prerequisites:
#   - Ubuntu 22.04+ with sudo access
#   - GitHub personal access token (or runner registration token)
#
# What this installs:
#   - Docker (for Postgres test containers)
#   - Node.js 20 (required by Claude Code)
#   - Claude Code (npm install)
#   - Python 3.12
#   - GitHub Actions runner (as a systemd service)

set -euo pipefail

echo "============================================"
echo "  AIde — Self-Hosted Runner Setup"
echo "============================================"
echo ""

# ── Config ──────────────────────────────────────
GITHUB_REPO="zcancio/aide"
RUNNER_DIR="/opt/actions-runner"
RUNNER_USER="runner"
RUNNER_VERSION="2.322.0"

# ── Prompt for GitHub runner token ──────────────
echo "Go to: https://github.com/${GITHUB_REPO}/settings/actions/runners/new"
echo "Copy the token shown in the configure step."
echo ""
read -p "Paste your GitHub runner registration token: " RUNNER_TOKEN
echo ""

# ── System packages ─────────────────────────────
echo "==> Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    curl \
    git \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    jq

# ── Docker ──────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "==> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
else
    echo "==> Docker already installed"
fi

# ── Python 3.12 ─────────────────────────────────
if ! python3.12 --version &> /dev/null; then
    echo "==> Installing Python 3.12..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
else
    echo "==> Python 3.12 already installed"
fi

# Make python3.12 the default python3
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 || true

# ── Node.js 20 (required by Claude Code) ────────
if ! node --version 2>/dev/null | grep -q "v20\|v22"; then
    echo "==> Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "==> Node.js already installed: $(node --version)"
fi

# ── Claude Code ─────────────────────────────────
echo "==> Installing Claude Code..."
sudo npm install -g @anthropic-ai/claude-code

# ── Create runner user ──────────────────────────
if ! id "$RUNNER_USER" &>/dev/null; then
    echo "==> Creating runner user..."
    sudo useradd -m -s /bin/bash "$RUNNER_USER"
fi

# Add runner to docker group so it can start containers
sudo usermod -aG docker "$RUNNER_USER"

# ── Install GitHub Actions Runner ────────────────
echo "==> Installing GitHub Actions runner..."
sudo mkdir -p "$RUNNER_DIR"
sudo chown "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"

cd "$RUNNER_DIR"

# Download runner
sudo -u "$RUNNER_USER" curl -sL -o actions-runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
sudo -u "$RUNNER_USER" tar xzf actions-runner.tar.gz
rm actions-runner.tar.gz

# Install dependencies
sudo ./bin/installdependencies.sh

# Configure runner
sudo -u "$RUNNER_USER" ./config.sh \
    --url "https://github.com/${GITHUB_REPO}" \
    --token "$RUNNER_TOKEN" \
    --name "aide-builder" \
    --labels "self-hosted,linux,aide" \
    --unattended \
    --replace

# Install as systemd service
sudo ./svc.sh install "$RUNNER_USER"
sudo ./svc.sh start

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "Runner status:"
sudo ./svc.sh status
echo ""
echo "Next steps:"
echo "  1. Authenticate Claude Code:"
echo "     sudo -u $RUNNER_USER claude auth login"
echo ""
echo "  2. Verify runner is online:"
echo "     https://github.com/${GITHUB_REPO}/settings/actions/runners"
echo ""
echo "  3. Push your repo and open an issue with @claude"
echo ""
