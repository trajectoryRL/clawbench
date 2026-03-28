"""
Backend adapters for ClawBench MCP tools.

MockBackend reads fixture files. RealBackend (future) calls live APIs.
Both implement the same interface so the MCP server doesn't care which
is active.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class ToolBackend(Protocol):
    """Interface that all backends must implement."""

    # Email
    def email_list(self) -> list[dict]: ...
    def email_read(self, message_id: str) -> dict | None: ...
    def email_send(self, to: str, subject: str, body: str) -> dict: ...
    def email_draft(self, to: str, subject: str, body: str) -> dict: ...

    # Calendar
    def calendar_list(self) -> list[dict]: ...
    def calendar_search(self, query: str) -> list[dict]: ...
    def calendar_create(self, title: str, when: str, duration: str) -> dict: ...

    # Tasks
    def tasks_list(self, status: str, priority: str, assignee: str) -> list[dict]: ...
    def task_get(self, task_id: str) -> dict | None: ...
    def task_create(self, title: str, priority: str, assignee: str) -> dict: ...
    def task_update(self, task_id: str, **fields: str) -> dict: ...

    # Slack
    def slack_channels(self) -> list[dict]: ...
    def slack_read(self, channel: str, limit: int) -> list[dict]: ...
    def slack_send(self, to: str, message: str) -> dict: ...
    def slack_member(self, user_id: str) -> dict: ...

    # Memory
    def memory_search(self, query: str, max_results: int) -> list[dict]: ...
    def memory_read(self, path: str, from_line: int, num_lines: int) -> dict: ...


class MockBackend:
    """Reads fixture JSON files. Deterministic, no external dependencies."""

    def __init__(self, fixtures_path: str | Path, scenario: str):
        self.fixtures_path = Path(fixtures_path)
        self.scenario = scenario

    def _load(self, filename: str) -> Any | None:
        path = self.fixtures_path / self.scenario / filename
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def set_scenario(self, scenario: str):
        self.scenario = scenario

    # -- Email -------------------------------------------------------------

    def email_list(self) -> list[dict]:
        inbox = self._load("inbox.json") or []
        return [
            {
                "id": msg.get("id"),
                "sender": msg.get("sender"),
                "subject": msg.get("subject"),
                "date": msg.get("received_ts", ""),
                "flags": msg.get("labels", []),
            }
            for msg in inbox
        ]

    def email_read(self, message_id: str) -> dict | None:
        inbox = self._load("inbox.json") or []
        return next((e for e in inbox if str(e.get("id")) == message_id), None)

    def email_send(self, to: str, subject: str, body: str) -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return {"id": f"sent_{ts}", "status": "sent", "to": to, "subject": subject}

    def email_draft(self, to: str, subject: str, body: str) -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return {"id": f"draft_{ts}", "status": "draft"}

    # -- Calendar ----------------------------------------------------------

    def calendar_list(self) -> list[dict]:
        return self._load("calendar.json") or []

    def calendar_search(self, query: str) -> list[dict]:
        events = self._load("calendar.json") or []
        q = query.lower()
        return [
            e for e in events
            if q in e.get("title", "").lower()
            or q in e.get("location", "").lower()
            or q in e.get("notes", "").lower()
            or q in json.dumps(e.get("attendees", [])).lower()
        ]

    def calendar_create(self, title: str, when: str, duration: str) -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return {"id": f"evt_{ts}", "status": "confirmed", "title": title}

    # -- Tasks -------------------------------------------------------------

    def tasks_list(self, status: str = "", priority: str = "", assignee: str = "") -> list[dict]:
        tasks = self._load("tasks.json") or []
        if status:
            tasks = [t for t in tasks if t.get("status", "").lower() == status.lower()]
        if priority:
            tasks = [t for t in tasks if t.get("priority", "").lower() == priority.lower()]
        if assignee:
            tasks = [t for t in tasks if t.get("assignee", "").lower() == assignee.lower()]
        return tasks

    def task_get(self, task_id: str) -> dict | None:
        tasks = self._load("tasks.json") or []
        item = next((t for t in tasks if str(t.get("id")) == task_id), None)
        if not item:
            docs = self._load("documents.json") or []
            item = next((d for d in docs if str(d.get("id")) == task_id), None)
        return item

    def task_create(self, title: str, priority: str = "", assignee: str = "") -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return {"id": f"page_{ts}", "status": "created", "title": title}

    def task_update(self, task_id: str, **fields: str) -> dict:
        return {"id": task_id, "status": "updated", **fields}

    # -- Slack -------------------------------------------------------------

    def slack_channels(self) -> list[dict]:
        return self._load("slack_channels.json") or []

    def slack_read(self, channel: str, limit: int = 50) -> list[dict]:
        messages = self._load("slack_messages.json") or []
        channels = self._load("slack_channels.json") or []
        ch = channel.lstrip("#")
        resolved = {ch}
        for c in channels:
            if c.get("id", "").lstrip("#") == ch or c.get("name", "").lstrip("#") == ch:
                resolved.add(c.get("name", "").lstrip("#"))
                resolved.add(c.get("id", "").lstrip("#"))
        filtered = [
            m for m in messages
            if m.get("channel", "").lstrip("#") in resolved
            or m.get("channelId", "").lstrip("#") in resolved
        ]
        return filtered[:limit]

    def slack_send(self, to: str, message: str) -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return {"id": f"slack_msg_{ts}", "to": to, "status": "sent"}

    def slack_member(self, user_id: str) -> dict:
        contacts = self._load("contacts.json") or []
        member = next(
            (c for c in contacts if c.get("slack_id") == user_id or c.get("id") == user_id),
            None,
        )
        return member or {"id": user_id, "name": "Unknown User"}

    # -- Memory ------------------------------------------------------------

    def memory_search(self, query: str, max_results: int = 5) -> list[dict]:
        results = []
        base = self.fixtures_path / self.scenario

        memory_dir = base / "memory"
        if memory_dir.exists():
            for fpath in sorted(memory_dir.iterdir()):
                if not fpath.is_file():
                    continue
                content = fpath.read_text()
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if any(word in line.lower() for word in query.lower().split()):
                        start = max(0, i - 1)
                        end = min(len(lines), i + 3)
                        snippet = "\n".join(lines[start:end])
                        rel_path = f"memory/{fpath.name}"
                        results.append({
                            "snippet": snippet,
                            "path": rel_path,
                            "startLine": start + 1,
                            "endLine": end,
                            "score": 0.85,
                            "citation": f"{rel_path}#L{start + 1}-L{end}",
                        })
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

        mem_md = base / "MEMORY.md"
        if mem_md.exists() and len(results) < max_results:
            content = mem_md.read_text()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if any(word in line.lower() for word in query.lower().split()):
                    start = max(0, i - 1)
                    end = min(len(lines), i + 3)
                    snippet = "\n".join(lines[start:end])
                    results.append({
                        "snippet": snippet,
                        "path": "MEMORY.md",
                        "startLine": start + 1,
                        "endLine": end,
                        "score": 0.80,
                        "citation": f"MEMORY.md#L{start + 1}-L{end}",
                    })
                    if len(results) >= max_results:
                        break

        return results

    def memory_read(self, path: str, from_line: int = 1, num_lines: int = 100) -> dict:
        base = self.fixtures_path / self.scenario
        for fpath in [base / path, base / "memory" / path]:
            resolved = fpath.resolve()
            if resolved.exists() and resolved.is_file():
                content = resolved.read_text()
                lines = content.split("\n")
                start = max(0, from_line - 1)
                end = start + num_lines
                text = "\n".join(lines[start:end])
                return {"path": path, "text": text}
        return {"path": path, "text": "", "error": f"File not found: {path}"}
