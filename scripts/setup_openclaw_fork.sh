#!/bin/bash
# Setup script for trajectoryRL/openclaw fork integration
# This script clones the fork and installs our mock tools plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_DIR="$(dirname "$SCRIPT_DIR")"
OPENCLAW_DIR="${SANDBOX_DIR}/openclaw"

echo "=============================================="
echo "Trajectory Sandbox - OpenClaw Fork Setup"
echo "=============================================="

# Clone the fork if not exists
if [ ! -d "$OPENCLAW_DIR" ]; then
    echo "Cloning trajectoryRL/openclaw fork..."
    git clone https://github.com/trajectoryRL/openclaw.git "$OPENCLAW_DIR"
else
    echo "OpenClaw fork already cloned at $OPENCLAW_DIR"
    echo "Pulling latest changes..."
    cd "$OPENCLAW_DIR"
    git pull
fi

cd "$OPENCLAW_DIR"

# Copy our plugin to extensions/
echo ""
echo "Installing trajectory-sandbox-tools plugin..."
PLUGIN_SRC="${SANDBOX_DIR}/openclaw-plugin"
PLUGIN_DST="${OPENCLAW_DIR}/extensions/trajectory-sandbox-tools"

if [ -d "$PLUGIN_DST" ]; then
    rm -rf "$PLUGIN_DST"
fi

cp -r "$PLUGIN_SRC" "$PLUGIN_DST"
echo "Plugin installed to: $PLUGIN_DST"

# Create a sandbox-specific config
echo ""
echo "Creating sandbox configuration..."
CONFIG_FILE="${SANDBOX_DIR}/config/openclaw.sandbox.json"
mkdir -p "${SANDBOX_DIR}/config"

cat > "$CONFIG_FILE" << 'EOF'
{
  "agent": {
    "model": "anthropic/claude-sonnet-4"
  },
  "plugins": {
    "entries": {
      "trajectory-sandbox-tools": {
        "enabled": true,
        "config": {
          "mockServerUrl": "http://host.docker.internal:3001",
          "scenario": "inbox_triage"
        }
      }
    }
  },
  "tools": {
    "deny": ["exec", "process", "browser", "canvas", "nodes", "cron", "gateway", "web_search", "web_fetch"],
    "allow": ["inbox_list", "email_draft", "email_send", "calendar_read", "memory_read", "memory_write"]
  },
  "agents": {
    "defaults": {
      "workspace": "/workspace"
    }
  }
}
EOF

echo "Sandbox config created: $CONFIG_FILE"

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Build OpenClaw Docker image:"
echo "   cd $OPENCLAW_DIR"
echo "   ./docker-setup.sh"
echo ""
echo "2. Or build manually:"
echo "   docker build -t openclaw:sandbox -f Dockerfile ."
echo ""
echo "3. Start mock tools server (in another terminal):"
echo "   cd $SANDBOX_DIR"
echo "   python scripts/run_mock_server.py"
echo ""
echo "4. Copy AGENTS.md to workspace:"
echo "   cp ${SANDBOX_DIR}/fixtures/inbox_triage/AGENTS.md.baseline ~/openclaw/workspace/AGENTS.md"
echo ""
