"""Shared MCP response serialization and path-redaction helpers."""

from __future__ import annotations

import json
from typing import Any, Dict


def envelope(text: str) -> Dict[str, Any]:
    """Wrap text in the MCP content envelope."""
    return {"content": [{"type": "text", "text": text}]}


def json_envelope(payload: Any) -> Dict[str, Any]:
    """Serialize one JSON payload in the MCP content envelope."""
    return envelope(json.dumps(payload, indent=2, default=str))


def redact_local_paths(value: Any) -> Any:
    """Remove local filesystem locations from MCP responses."""
    if isinstance(value, dict):
        return {key: redact_local_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_local_paths(item) for item in value]
    if isinstance(value, str) and value.startswith("file://"):
        return "file://<local-contract>"
    return value
