#!/bin/bash
# Run Trajectory Sandbox
#
# Usage:
#   ./scripts/run.sh [baseline|optimized]
#
# Prerequisites:
#   - export ANTHROPIC_API_KEY="sk-ant-..."

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_DIR="$(dirname "$SCRIPT_DIR")"

cd "$SANDBOX_DIR"

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: Set ANTHROPIC_API_KEY or OPENAI_API_KEY"
    echo ""
    echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
    exit 1
fi

# Copy AGENTS.md variant
VARIANT="${1:-baseline}"
if [ "$VARIANT" == "baseline" ]; then
    echo "Using AGENTS.md.baseline"
    cp fixtures/inbox_triage/AGENTS.md.baseline workspace/AGENTS.md
elif [ "$VARIANT" == "optimized" ]; then
    echo "Using AGENTS.md.optimized"
    cp fixtures/inbox_triage/AGENTS.md.optimized workspace/AGENTS.md
else
    echo "Unknown variant: $VARIANT"
    echo "Usage: ./scripts/run.sh [baseline|optimized]"
    exit 1
fi

# Copy USER.md
cp fixtures/inbox_triage/USER.md workspace/USER.md

echo ""
echo "=============================================="
echo "Starting Trajectory Sandbox"
echo "=============================================="
echo ""
echo "AGENTS.md variant: $VARIANT"
echo ""
echo "Dashboard: http://localhost:18789/?token=sandbox-token-12345"
echo "Mock tools: http://localhost:3001"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Build and run
docker-compose up --build
