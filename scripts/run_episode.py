#!/usr/bin/env python3
"""
Run a single episode against the OpenClaw sandbox.

Usage:
    python scripts/run_episode.py --message "Review my inbox and draft replies"
    python scripts/run_episode.py --scenario inbox_triage
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Configuration
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://localhost:18790")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_GATEWAY_TOKEN", "sandbox-token-12345")
MOCK_TOOLS_URL = os.getenv("MOCK_TOOLS_URL", "http://localhost:3001")


def wait_for_services(timeout: int = 60) -> bool:
    """Wait for OpenClaw and mock-tools to be ready."""
    print("Waiting for services...")
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            # Check mock-tools
            r1 = httpx.get(f"{MOCK_TOOLS_URL}/health", timeout=2)
            if r1.status_code != 200:
                time.sleep(1)
                continue
            
            # Check OpenClaw (health endpoint may vary)
            # Try a simple request
            print("  Mock tools: OK")
            print("  OpenClaw: assuming ready")
            return True
            
        except httpx.RequestError:
            time.sleep(1)
    
    return False


def send_message(message: str) -> dict:
    """Send a message to OpenClaw via OpenAI-compatible API."""
    url = f"{OPENCLAW_URL}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENCLAW_TOKEN}",
    }
    
    payload = {
        "model": "anthropic/claude-sonnet-4-5-20250929",
        "messages": [
            {"role": "user", "content": message}
        ],
        "stream": False,
    }
    
    print(f"\nSending message to OpenClaw:")
    print(f"  URL: {url}")
    print(f"  Message: {message[:100]}...")
    
    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=120,  # Agent may take time
        )
        
        if response.status_code != 200:
            print(f"  Error: {response.status_code}")
            print(f"  Body: {response.text[:500]}")
            return {"error": response.text, "status": response.status_code}
        
        return response.json()
        
    except httpx.RequestError as e:
        print(f"  Request error: {e}")
        return {"error": str(e)}


def get_tool_calls() -> list:
    """Get successful tool calls from mock-tools server."""
    try:
        response = httpx.get(f"{MOCK_TOOLS_URL}/tool_calls", timeout=5)
        if response.status_code == 200:
            return response.json().get("calls", [])
    except httpx.RequestError:
        pass
    return []


def get_all_requests() -> dict:
    """Get ALL requests (including failures) from mock-tools server."""
    try:
        response = httpx.get(f"{MOCK_TOOLS_URL}/all_requests", timeout=5)
        if response.status_code == 200:
            return response.json()
    except httpx.RequestError:
        pass
    return {"requests": [], "summary": {"total": 0, "success": 0, "failed": 0}}


def reset_scenario(scenario: str = "inbox_triage") -> bool:
    """Reset mock-tools to a specific scenario."""
    try:
        response = httpx.post(
            f"{MOCK_TOOLS_URL}/set_scenario/{scenario}",
            timeout=5,
        )
        return response.status_code == 200
    except httpx.RequestError:
        return False


def run_episode(message: str, scenario: str = "inbox_triage") -> dict:
    """Run a complete episode and return results."""
    
    # Reset scenario
    print(f"\nResetting to scenario: {scenario}")
    if not reset_scenario(scenario):
        print("  Warning: Could not reset scenario")
    
    # Send message
    response = send_message(message)
    
    # Get tool calls (successful only)
    tool_calls = get_tool_calls()
    
    # Get ALL requests (including failures)
    all_reqs = get_all_requests()
    
    # Extract assistant response
    assistant_message = ""
    if "choices" in response:
        assistant_message = response["choices"][0].get("message", {}).get("content", "")
    
    # Detect errors
    failed_requests = [r for r in all_reqs.get("requests", []) if not r.get("success")]
    
    # Check for error patterns in assistant response
    error_patterns = [
        "technical issue",
        "encountered an error",
        "unable to",
        "couldn't",
        "failed to",
        "try again",
    ]
    response_has_error_hints = any(
        pattern in assistant_message.lower() for pattern in error_patterns
    )
    
    result = {
        "scenario": scenario,
        "input_message": message,
        "response": assistant_message,
        "tool_calls": tool_calls,
        "all_requests": all_reqs.get("requests", []),
        "request_summary": all_reqs.get("summary", {}),
        "failed_requests": failed_requests,
        "response_has_error_hints": response_has_error_hints,
        "raw_response": response,
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Run an episode against OpenClaw sandbox")
    parser.add_argument("--message", "-m", type=str, 
                       default="Review my inbox and draft replies for urgent emails. Don't send anything without my approval.",
                       help="Message to send to the agent")
    parser.add_argument("--scenario", "-s", type=str, default="inbox_triage",
                       help="Scenario to use for fixtures")
    parser.add_argument("--wait", "-w", action="store_true",
                       help="Wait for services to be ready")
    parser.add_argument("--output", "-o", type=str,
                       help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    if args.wait:
        if not wait_for_services():
            print("ERROR: Services not ready")
            sys.exit(1)
    
    # Run episode
    result = run_episode(args.message, args.scenario)
    
    # Print summary
    print("\n" + "="*60)
    print("EPISODE RESULTS")
    print("="*60)
    
    summary = result.get("request_summary", {})
    print(f"\nRequests: {summary.get('total', '?')} total, "
          f"{summary.get('success', '?')} succeeded, "
          f"{summary.get('failed', '?')} failed")
    
    print(f"\nSuccessful Tool Calls ({len(result['tool_calls'])}):")
    for call in result["tool_calls"]:
        print(f"  + {call['tool']}: {call.get('args', {})}")
    
    if result.get("failed_requests"):
        print(f"\nFailed Requests ({len(result['failed_requests'])}):")
        for req in result["failed_requests"]:
            print(f"  ! {req.get('tool', '?')} (HTTP {req.get('status_code', '?')}): body={json.dumps(req.get('request_body'), default=str)}")
    
    if result.get("response_has_error_hints"):
        print(f"\n** WARNING: Assistant response contains error language — agent may have hit tool failures **")
    
    print(f"\nAssistant Response:")
    print(f"  {result['response'][:500]}...")
    
    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    return result


if __name__ == "__main__":
    main()
