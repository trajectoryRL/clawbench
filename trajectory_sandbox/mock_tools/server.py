"""
Mock Tool Server - Serves deterministic tool responses from fixtures.

This server exposes tools that OpenClaw can call. Responses are read from
fixture files to ensure reproducibility.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock-tools")

app = FastAPI(title="Mock Tools Server")

FIXTURES_PATH = Path(os.getenv("FIXTURES_PATH", "./fixtures"))
LOG_PATH = Path(os.getenv("LOG_PATH", "./logs"))
CURRENT_SCENARIO = os.getenv("SCENARIO", "inbox_triage")

# Ensure log directory exists
LOG_PATH.mkdir(parents=True, exist_ok=True)

# Tool call log (successful calls)
tool_calls: list[dict] = []

# ALL requests log (including failures)
all_requests: list[dict] = []


@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    """Middleware: log every POST /tools/* request body for debugging."""
    body_bytes = b""
    body_json = None

    if request.method == "POST" and request.url.path.startswith("/tools/"):
        body_bytes = await request.body()
        try:
            body_json = json.loads(body_bytes) if body_bytes else None
        except (json.JSONDecodeError, ValueError):
            body_json = {"_raw": body_bytes.decode("utf-8", errors="replace")}

        logger.debug(
            "REQUEST  %s %s  body=%s",
            request.method,
            request.url.path,
            json.dumps(body_json, default=str),
        )

    response = await call_next(request)

    if request.method == "POST" and request.url.path.startswith("/tools/"):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "tool": request.url.path.replace("/tools/", ""),
            "request_body": body_json,
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
        }
        all_requests.append(entry)

        # Write to debug log file
        debug_log = LOG_PATH / f"{CURRENT_SCENARIO}_all_requests.jsonl"
        with open(debug_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

        if response.status_code >= 400:
            logger.warning(
                "FAILED   %s %s  status=%d  body=%s",
                request.method,
                request.url.path,
                response.status_code,
                json.dumps(body_json, default=str),
            )

    return response


def load_fixture(scenario: str, filename: str) -> Any:
    """Load a fixture file for the current scenario."""
    path = FIXTURES_PATH / scenario / filename
    if not path.exists():
        raise HTTPException(404, f"Fixture not found: {path}")
    with open(path) as f:
        return json.load(f)


def log_tool_call(tool: str, args: dict, result: Any):
    """Log a successful tool call for later analysis."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "tool": tool,
        "args": args,
        "result_summary": str(result)[:200],
    }
    tool_calls.append(entry)
    
    # Also write to file
    log_file = LOG_PATH / f"{CURRENT_SCENARIO}_calls.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


# =============================================================================
# Tool Models
# =============================================================================

# Response models (used for return type serialization)

class InboxListResponse(BaseModel):
    messages: list[dict]

class EmailDraftResponse(BaseModel):
    draft_id: str
    preview: str

class EmailSendResponse(BaseModel):
    status: str
    draft_id: str

class CalendarReadResponse(BaseModel):
    events: list[dict]

class MemoryReadResponse(BaseModel):
    content: str | None
    exists: bool

class MemoryWriteResponse(BaseModel):
    success: bool


# =============================================================================
# Tool Endpoints
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "ok", "scenario": CURRENT_SCENARIO}


@app.post("/set_scenario/{scenario}")
async def set_scenario(scenario: str):
    """Set the current scenario (for fixture loading)."""
    global CURRENT_SCENARIO
    CURRENT_SCENARIO = scenario
    tool_calls.clear()
    all_requests.clear()
    logger.info("Scenario reset to: %s (tool_calls and all_requests cleared)", scenario)
    return {"scenario": CURRENT_SCENARIO}


@app.get("/tool_calls")
async def get_tool_calls():
    """Get all tool calls made in current session (successful only)."""
    return {"calls": tool_calls}


@app.get("/all_requests")
async def get_all_requests():
    """Get ALL requests including failures — use this for debugging."""
    return {
        "requests": all_requests,
        "summary": {
            "total": len(all_requests),
            "success": sum(1 for r in all_requests if r["success"]),
            "failed": sum(1 for r in all_requests if not r["success"]),
        },
    }


@app.post("/tools/inbox.list")
async def inbox_list(request: Request):
    """List inbox messages."""
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("inbox.list raw body: %s", json.dumps(data, default=str))

    inbox = load_fixture(CURRENT_SCENARIO, "inbox.json")
    
    messages = [
        {
            "id": msg["id"],
            "sender": msg["sender"],
            "subject": msg["subject"],
            "snippet": msg.get("body", "")[:100],
            "received_ts": msg.get("received_ts", ""),
            "labels": msg.get("labels", []),
            "is_urgent": msg.get("is_urgent", False),
        }
        for msg in inbox
    ]
    
    log_tool_call("inbox.list", data, {"count": len(messages)})
    return InboxListResponse(messages=messages)


@app.post("/tools/email.draft")
async def email_draft(request: Request):
    """Draft a reply to an email.
    
    Accepts flexible input and logs the raw body for debugging.
    Looks for message_id/instructions in the body, with fallbacks
    for common alternative field names the LLM might use.
    """
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("email.draft raw body: %s", json.dumps(data, default=str))

    # Extract message_id — try common alternatives
    message_id = (
        data.get("message_id")
        or data.get("messageId")
        or data.get("email_id")
        or data.get("emailId")
        or data.get("id")
        or "unknown"
    )

    # Extract instructions — try common alternatives
    instructions = (
        data.get("instructions")
        or data.get("body")
        or data.get("content")
        or data.get("text")
        or data.get("reply")
        or data.get("message")
        or "No instructions provided"
    )

    draft_id = f"draft_{message_id}"
    preview = f"[Draft reply to {message_id}]: {instructions[:100]}..."

    log_tool_call("email.draft", {"message_id": message_id, "instructions": instructions, "_raw": data}, {"draft_id": draft_id})
    return EmailDraftResponse(draft_id=draft_id, preview=preview)


@app.post("/tools/email.send")
async def email_send(request: Request):
    """Send a drafted email. IRREVERSIBLE - requires approval.
    
    Accepts flexible input with fallbacks for common field names.
    """
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("email.send raw body: %s", json.dumps(data, default=str))

    draft_id = (
        data.get("draft_id")
        or data.get("draftId")
        or data.get("id")
        or "unknown"
    )

    log_tool_call("email.send", {"draft_id": draft_id, "_raw": data}, {"status": "sent"})
    return EmailSendResponse(status="sent", draft_id=draft_id)


@app.post("/tools/calendar.read")
async def calendar_read(request: Request):
    """Read calendar events."""
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("calendar.read raw body: %s", json.dumps(data, default=str))

    try:
        calendar = load_fixture(CURRENT_SCENARIO, "calendar.json")
    except HTTPException:
        calendar = []
    
    events = calendar
    log_tool_call("calendar.read", data, {"count": len(events)})
    return CalendarReadResponse(events=events)


@app.post("/tools/memory.read")
async def memory_read(request: Request):
    """Read from memory/filesystem."""
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("memory.read raw body: %s", json.dumps(data, default=str))

    req_path = data.get("path") or data.get("key") or ""
    try:
        path = FIXTURES_PATH / CURRENT_SCENARIO / "memory" / req_path
        if path.exists():
            content = path.read_text()
            log_tool_call("memory.read", data, {"exists": True})
            return MemoryReadResponse(content=content, exists=True)
    except Exception:
        pass
    
    log_tool_call("memory.read", data, {"exists": False})
    return MemoryReadResponse(content=None, exists=False)


@app.post("/tools/memory.write")
async def memory_write(request: Request):
    """Write to memory/filesystem."""
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    logger.info("memory.write raw body: %s", json.dumps(data, default=str))

    # In mock mode, we just log but don't actually write
    log_tool_call("memory.write", data, {"success": True})
    return MemoryWriteResponse(success=True)


# =============================================================================
# MCP-style tool listing (for OpenClaw discovery)
# =============================================================================

@app.get("/tools")
async def list_tools():
    """List available tools in MCP-compatible format."""
    return {
        "tools": [
            {
                "name": "inbox.list",
                "description": "List inbox messages with id, sender, subject, snippet",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "email.draft",
                "description": "Draft a reply to an email",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string", "description": "ID of email to reply to"},
                        "instructions": {"type": "string", "description": "Instructions for the draft"},
                    },
                    "required": ["message_id", "instructions"],
                },
            },
            {
                "name": "email.send",
                "description": "Send a drafted email. IRREVERSIBLE - requires user approval first!",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "draft_id": {"type": "string", "description": "ID of draft to send"},
                    },
                    "required": ["draft_id"],
                },
            },
            {
                "name": "calendar.read",
                "description": "Read calendar events",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                    },
                },
            },
            {
                "name": "memory.read",
                "description": "Read a file from memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to read"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "memory.write",
                "description": "Write a file to memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
