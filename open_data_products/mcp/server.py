"""Minimal stdio JSON-RPC 2.0 MCP server.

Implements just enough of MCP to be usable from Claude Code, Codex CLI, and
other compatible hosts. Uses no third-party MCP package: the wire protocol is
JSON-RPC 2.0 over stdio per the MCP spec.

Methods:
- ``initialize``           — handshake
- ``tools/list``           — return registered tools (sans handlers)
- ``tools/call``           — invoke a handler by name
- ``shutdown`` / ``exit``  — clean termination

Run: ``python -m open_data_products.mcp.server`` or ``open-data-products serve``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional, TextIO

from .. import __version__
from .tools import TOOLS, get_tool

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "open-data-products", "version": __version__}


def _public_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": tool["inputSchema"],
    }


def handle(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Dispatch a single JSON-RPC request. Returns None for notifications."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
        return _ok(request_id, result)

    if method == "tools/list":
        return _ok(request_id, {"tools": [_public_tool(t) for t in TOOLS]})

    if method == "tools/call":
        name = params.get("name")
        tool = get_tool(name) if name else None
        if tool is None:
            return _err(request_id, -32601, f"Unknown tool: {name}")
        try:
            envelope = tool["handler"](params.get("arguments") or {})
        except Exception as exc:
            envelope = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"error": type(exc).__name__, "message": str(exc)}
                        ),
                    }
                ],
                "isError": True,
            }
        return _ok(request_id, envelope)

    if method in {"shutdown", "exit"}:
        return _ok(request_id, {})

    if request_id is None:
        return None  # notification we don't handle

    return _err(request_id, -32601, f"Method not found: {method}")


def _ok(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _err(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Run the stdio JSON-RPC loop until EOF or ``exit``."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_err(None, -32700, "Parse error")) + "\n")
            stdout.flush()
            continue
        response = handle(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
        if request.get("method") == "exit":
            break
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(serve())
