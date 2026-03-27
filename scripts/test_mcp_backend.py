#!/usr/bin/env python3
"""
Test MCP backend and tool dispatch (no server needed).

Usage:
    cd clawbench
    python scripts/test_mcp_backend.py
    python scripts/test_mcp_backend.py -s morning_brief
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> bool:
    global passed, failed
    status = PASS if ok else FAIL
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    if ok:
        passed += 1
    else:
        failed += 1
    return ok


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def test_email(backend):
    section("Email")

    emails = backend.email_list()
    check("email_list returns list", isinstance(emails, list))
    if emails:
        check("email has id", "id" in emails[0])
        check("email has sender", "sender" in emails[0])
        check("email has subject", "subject" in emails[0])
        check("email has date", "date" in emails[0])
        check("email has flags", "flags" in emails[0])

        msg_id = emails[0]["id"]
        full = backend.email_read(msg_id)
        check("email_read returns dict", isinstance(full, dict))
        check("email_read has body", "body" in full)
        check("email_read has sender", "sender" in full)

    check("email_read not found returns None", backend.email_read("nonexistent") is None)

    sent = backend.email_send("a@b.com", "Hi", "Hello")
    check("email_send returns id", "id" in sent)
    check("email_send status is sent", sent.get("status") == "sent")

    draft = backend.email_draft("a@b.com", "Hi", "Hello")
    check("email_draft returns id", "id" in draft)
    check("email_draft status is draft", draft.get("status") == "draft")


def test_calendar(backend):
    section("Calendar")

    events = backend.calendar_list()
    check("calendar_list returns list", isinstance(events, list))
    if events:
        check("event has id", "id" in events[0])
        check("event has title", "title" in events[0])
        check("event has start", "start" in events[0])
        check("event has end", "end" in events[0])

    results = backend.calendar_search("standup")
    check("calendar_search returns list", isinstance(results, list))

    created = backend.calendar_create("Test Event", "2pm", "30m")
    check("calendar_create returns id", "id" in created)
    check("calendar_create status confirmed", created.get("status") == "confirmed")


def test_tasks(backend):
    section("Tasks")

    tasks = backend.tasks_list()
    check("tasks_list returns list", isinstance(tasks, list))
    if tasks:
        check("task has id", "id" in tasks[0])
        check("task has title", "title" in tasks[0])
        check("task has status", "status" in tasks[0])

        task_id = tasks[0]["id"]
        detail = backend.task_get(task_id)
        check("task_get returns dict", isinstance(detail, dict))
        check("task_get has id", detail.get("id") == task_id)

        # Filter
        statuses = {t.get("status", "").lower() for t in tasks}
        if statuses:
            one_status = next(iter(statuses))
            filtered = backend.tasks_list(status=one_status)
            check(
                f"tasks_list filter status={one_status}",
                all(t.get("status", "").lower() == one_status for t in filtered),
            )

    check("task_get not found returns None", backend.task_get("nonexistent") is None)

    created = backend.task_create("New task", "high", "alice")
    check("task_create returns id", "id" in created)

    updated = backend.task_update("task_1", status="done")
    check("task_update returns id", updated.get("id") == "task_1")
    check("task_update applies field", updated.get("status") == "done")


def test_slack(backend):
    section("Slack")

    channels = backend.slack_channels()
    check("slack_channels returns list", isinstance(channels, list))

    if channels:
        ch_name = channels[0].get("name", "").lstrip("#")
        messages = backend.slack_read(ch_name)
        check("slack_read returns list", isinstance(messages, list))
        if messages:
            check("message has author", "author" in messages[0])
            check("message has text", "text" in messages[0])

    sent = backend.slack_send("#general", "Hello")
    check("slack_send returns id", "id" in sent)

    member = backend.slack_member("nonexistent_user")
    check("slack_member returns dict", isinstance(member, dict))
    check("slack_member has name", "name" in member)


def test_memory(backend):
    section("Memory")

    results = backend.memory_search("sprint")
    check("memory_search returns list", isinstance(results, list))
    if results:
        check("result has snippet", "snippet" in results[0])
        check("result has path", "path" in results[0])
        check("result has citation", "citation" in results[0])

    mem = backend.memory_read("MEMORY.md")
    check("memory_read returns dict", isinstance(mem, dict))
    check("memory_read has text or error", "text" in mem or "error" in mem)


def test_irreversible_flags(backend):
    """Test that write operations set _irreversible flag."""
    section("Irreversible Flags")

    os.environ["FIXTURES_PATH"] = str(backend.fixtures_path)
    os.environ["SCENARIO"] = backend.scenario
    os.environ.setdefault("LOG_PATH", "/tmp/clawbench-test-logs")
    os.makedirs(os.environ["LOG_PATH"], exist_ok=True)

    from clawbench.mock_tools.server import TOOL_HANDLERS

    write_tools = {
        "email_send": {"to": "a@b.com", "subject": "Hi", "body": "Hello"},
        "calendar_create": {"title": "Test", "when": "2pm"},
        "task_create": {"title": "Test"},
        "task_update": {"task_id": "t1", "status": "done"},
        "slack_send": {"to": "#general", "message": "Hello"},
    }
    for name, args in write_tools.items():
        if name in TOOL_HANDLERS:
            result = TOOL_HANDLERS[name](args, backend.scenario)
            check(f"{name} sets _irreversible", result.get("_irreversible") is True)


def test_empty_fixtures(backend):
    """Test that missing fixtures return empty lists, not errors."""
    section("Empty Fixture Handling")

    from clawbench.mcp.backend import MockBackend
    empty = MockBackend(backend.fixtures_path, "nonexistent_scenario")

    check("email_list empty scenario", empty.email_list() == [])
    check("email_read empty scenario", empty.email_read("msg_1") is None)
    check("calendar_list empty scenario", empty.calendar_list() == [])
    check("calendar_search empty scenario", empty.calendar_search("test") == [])
    check("tasks_list empty scenario", empty.tasks_list() == [])
    check("task_get empty scenario", empty.task_get("t1") is None)
    check("slack_channels empty scenario", empty.slack_channels() == [])
    check("slack_read empty scenario", empty.slack_read("general") == [])
    check("memory_search empty scenario", empty.memory_search("test") == [])
    mem = empty.memory_read("nonexistent.md")
    check("memory_read empty scenario has error", "error" in mem)


def test_mock_server_handlers(backend):
    """Test MCP handlers in mock_tools/server.py."""
    section("Mock Server MCP Handlers")

    os.environ["FIXTURES_PATH"] = str(backend.fixtures_path)
    os.environ["SCENARIO"] = backend.scenario
    os.environ.setdefault("LOG_PATH", "/tmp/clawbench-test-logs")
    os.makedirs(os.environ["LOG_PATH"], exist_ok=True)

    from clawbench.mock_tools.server import TOOL_HANDLERS

    mcp_tools = ["email_list", "email_read", "calendar_list", "tasks_list",
                  "slack_channels", "slack_read", "memory_read"]
    for name in mcp_tools:
        check(f"handler registered: {name}", name in TOOL_HANDLERS)

    result = TOOL_HANDLERS["email_list"]({}, backend.scenario)
    check("email_list returns list", isinstance(result, list))

    result = TOOL_HANDLERS["calendar_list"]({}, backend.scenario)
    check("calendar_list returns list", isinstance(result, list))

    result = TOOL_HANDLERS["email_read"]({"message_id": "nonexistent"}, backend.scenario)
    check("email_read not found has error", "error" in result)

    result = TOOL_HANDLERS["task_get"]({"task_id": "nonexistent"}, backend.scenario)
    check("task_get not found has error", "error" in result)


def test_output_compat(backend):
    """Test that backend output matches what server.py mock handlers produce."""
    section("Output Compatibility with server.py")

    os.environ["FIXTURES_PATH"] = str(backend.fixtures_path)
    os.environ["SCENARIO"] = backend.scenario
    os.environ.setdefault("LOG_PATH", "/tmp/clawbench-test-logs")
    os.makedirs(os.environ["LOG_PATH"], exist_ok=True)

    from clawbench.mock_tools.server import handle_exec, load_fixture

    # email_list: backend should produce same data as handle_exec himalaya list
    mock_result = handle_exec({"command": "himalaya envelope list"}, backend.scenario)
    mock_emails = json.loads(mock_result["aggregated"])
    backend_emails = backend.email_list()
    check(
        "email_list matches himalaya envelope list",
        mock_emails == backend_emails,
    )

    # email_read: compare fields
    inbox = load_fixture(backend.scenario, "inbox.json") or []
    if inbox:
        msg_id = inbox[0]["id"]
        mock_result = handle_exec({"command": f"himalaya message read {msg_id}"}, backend.scenario)
        mock_text = mock_result["aggregated"]
        backend_email = backend.email_read(msg_id)

        # Mock returns formatted text, backend returns raw dict
        # Verify the backend dict contains the same data
        check(
            "email_read sender matches",
            backend_email["sender"] in mock_text,
        )
        check(
            "email_read subject matches",
            backend_email["subject"] in mock_text,
        )

    # calendar_list: backend should match gcalcli agenda items
    mock_result = handle_exec({"command": "gcalcli agenda"}, backend.scenario)
    mock_events = json.loads(mock_result["aggregated"])["items"]
    backend_events = backend.calendar_list()
    check(
        "calendar_list matches gcalcli agenda",
        mock_events == backend_events,
    )

    # tasks_list: backend should match notion query results
    tasks = load_fixture(backend.scenario, "tasks.json")
    if tasks is not None:
        mock_result = handle_exec(
            {"command": "curl -X POST https://api.notion.so/v1/databases/db/query"}, backend.scenario
        )
        mock_tasks = json.loads(mock_result["aggregated"])["results"]
        backend_tasks = backend.tasks_list()
        check(
            "tasks_list matches notion query",
            mock_tasks == backend_tasks,
        )


ALL_SCENARIOS = [
    "client_escalation",
    "inbox_to_action",
    "inbox_triage",
    "morning_brief",
    "team_standup",
]


def run_scenario(fixtures_path: str, scenario: str):
    """Run all tests for a single scenario."""
    from clawbench.mcp.backend import MockBackend
    backend = MockBackend(fixtures_path, scenario)

    print(f"\n{'═' * 60}")
    print(f"  {scenario}")
    print(f"{'═' * 60}")

    test_email(backend)
    test_calendar(backend)
    test_tasks(backend)
    test_slack(backend)
    test_memory(backend)
    test_irreversible_flags(backend)
    test_empty_fixtures(backend)
    test_mock_server_handlers(backend)
    test_output_compat(backend)


def main():
    parser = argparse.ArgumentParser(description="Test MCP backend")
    parser.add_argument("--scenario", "-s", default=None,
                        help="Single scenario (default: all)")
    parser.add_argument("--fixtures", "-f", default=None)
    args = parser.parse_args()

    fixtures_path = args.fixtures
    if not fixtures_path:
        for candidate in [
            Path(__file__).resolve().parent.parent / "fixtures",
            Path("./fixtures"),
        ]:
            if candidate.exists():
                fixtures_path = str(candidate)
                break

    if not fixtures_path or not Path(fixtures_path).exists():
        print("ERROR: Cannot find fixtures. Use --fixtures.")
        sys.exit(1)

    scenarios = [args.scenario] if args.scenario else ALL_SCENARIOS

    print(f"\n{'═' * 60}")
    print(f"  MCP Backend Tests")
    print(f"  Scenarios: {', '.join(scenarios)}")
    print(f"{'═' * 60}")

    for scenario in scenarios:
        fixture_dir = Path(fixtures_path) / scenario
        if not fixture_dir.exists():
            print(f"\n  SKIP: {scenario} (no fixtures)")
            continue
        run_scenario(fixtures_path, scenario)

    print(f"\n{'═' * 60}")
    total = passed + failed
    if failed == 0:
        print(f"  ALL {total} TESTS PASSED ({len(scenarios)} scenarios)")
    else:
        print(f"  {passed}/{total} passed, {failed} FAILED")
    print(f"{'═' * 60}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
