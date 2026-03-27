#!/usr/bin/env python3
"""
Test that GLM-5-TEE can call each MCP tool individually.

Sends a simple prompt for each tool and checks if the model actually
calls it. No scoring — just "did the tool get called?"

Requires running services (mock-tools + openclaw gateway).

Usage:
    # Start services first
    python scripts/test_mcp_tool_calls.py --wait
    python scripts/test_mcp_tool_calls.py --base-url http://localhost:18789
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

# Each test: (tool_name, prompt, expected_tool_in_calls)
TOOL_TESTS = [
    ("email_list", "Use the email_list tool to list my emails.", "email_list"),
    ("email_read", "Use the email_read tool to read email msg_101.", "email_read"),
    ("email_draft", "Use the email_draft tool to draft an email to test@test.com with subject 'Hello' and body 'Hi there'.", "email_draft"),
    ("calendar_list", "Use the calendar_list tool to show my calendar.", "calendar_list"),
    ("calendar_search", "Use the calendar_search tool to find meetings about 'standup'.", "calendar_search"),
    ("tasks_list", "Use the tasks_list tool to list all tasks.", "tasks_list"),
    ("task_get", "Use the task_get tool to get details for task TC-950.", "task_get"),
    ("slack_channels", "Use the slack_channels tool to list Slack channels.", "slack_channels"),
    ("slack_read", "Use the slack_read tool to read messages from the platform-engineering channel.", "slack_read"),
    ("slack_member", "Use the slack_member tool to look up user c_001.", "slack_member"),
    ("memory_search", "Use the memory_search tool to search for 'sprint goals'.", "memory_search"),
    ("memory_read", "Use the memory_read tool to read the file memory/clients.md.", "memory_read"),
]


def reset_scenario(mock_url: str, scenario: str):
    try:
        httpx.post(f"{mock_url}/set_scenario/{scenario}", timeout=5)
    except Exception:
        pass


def get_tool_calls(mock_url: str) -> list:
    try:
        r = httpx.get(f"{mock_url}/tool_calls", timeout=5)
        return r.json().get("calls", [])
    except Exception:
        return []


def get_all_requests(mock_url: str) -> list:
    try:
        r = httpx.get(f"{mock_url}/all_requests", timeout=5)
        return r.json().get("requests", [])
    except Exception:
        return []


def send_message(openclaw_url: str, token: str, message: str, model: str) -> dict:
    session_key = f"tool-test-{int(time.time() * 1000)}"
    try:
        r = httpx.post(
            f"{openclaw_url}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": 500,
                "stream": False,
            },
            timeout=120,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def wait_for_services(openclaw_url: str, mock_url: str, timeout: int = 120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r1 = httpx.get(f"{mock_url}/health", timeout=3)
            r2 = httpx.get(f"{openclaw_url}/health", timeout=3)
            if r1.status_code == 200 and r2.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    parser = argparse.ArgumentParser(description="Test individual MCP tool calls")
    parser.add_argument("--base-url", default="http://localhost:18789", help="OpenClaw gateway URL")
    parser.add_argument("--mock-url", default="http://localhost:3001", help="Mock tools URL")
    parser.add_argument("--token", default="sandbox-token-12345", help="Gateway auth token")
    parser.add_argument("--model", default=None, help="Model ID (auto-detect from config)")
    parser.add_argument("--scenario", default="client_escalation", help="Scenario for fixtures")
    parser.add_argument("--wait", action="store_true", help="Wait for services")
    parser.add_argument("--tools", nargs="*", help="Only test specific tools")
    args = parser.parse_args()

    if args.wait:
        print("Waiting for services...")
        if not wait_for_services(args.base_url, args.mock_url):
            print("ERROR: Services not ready")
            sys.exit(1)

    # Auto-detect model from health endpoint
    model = args.model
    if not model:
        model = os.environ.get("CLAWBENCH_DEFAULT_MODEL", "chutes/zai-org/GLM-5-TEE")

    tests = TOOL_TESTS
    if args.tools:
        tests = [t for t in TOOL_TESTS if t[0] in args.tools]

    print(f"\n{'═' * 60}")
    print(f"  MCP Tool Call Tests")
    print(f"  Model: {model}")
    print(f"  Scenario: {args.scenario}")
    print(f"  Tools: {len(tests)}")
    print(f"{'═' * 60}\n")

    passed = 0
    failed = 0
    skipped = 0

    for tool_name, prompt, expected_tool in tests:
        # Reset mock server state
        reset_scenario(args.mock_url, args.scenario)

        print(f"  Testing {tool_name}...", end=" ", flush=True)

        # Send message
        response = send_message(args.base_url, args.token, prompt, model)

        if "error" in response and "choices" not in response:
            print(f"[{SKIP}] API error: {str(response.get('error', ''))[:60]}")
            skipped += 1
            continue

        # Check mock server for tool calls
        time.sleep(0.5)  # brief settle
        calls = get_tool_calls(args.mock_url)
        requests = get_all_requests(args.mock_url)

        tool_names_called = [c.get("tool") for c in calls]
        tool_names_requested = [r.get("tool") for r in requests]

        # Check if the expected tool was called
        called = expected_tool in tool_names_called or expected_tool in tool_names_requested

        if called:
            print(f"[{PASS}] called={tool_names_called or tool_names_requested}")
            passed += 1
        else:
            # Show what the model said instead
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            snippet = content[:80].replace("\n", " ")
            print(f"[{FAIL}] not called. Response: {snippet}...")
            failed += 1

    print(f"\n{'═' * 60}")
    total = passed + failed + skipped
    print(f"  {passed}/{total} passed, {failed} failed, {skipped} skipped")
    print(f"{'═' * 60}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
