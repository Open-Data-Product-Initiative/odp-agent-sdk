"""Shared helpers for the unified CLI."""

from __future__ import annotations

import json
import sys
from typing import List, Optional


def split_csv(value: Optional[str]) -> List[str]:
    """Return non-empty comma-separated values with surrounding whitespace removed."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def print_error_payload(
    error: object,
    *,
    as_json: bool,
    spec: str = "cli",
    kind: str = "Error",
) -> None:
    """Print an error in JSON or stderr form."""
    message = str(error)
    if as_json:
        print(
            json.dumps(
                {
                    "spec": spec,
                    "kind": kind,
                    "valid": False,
                    "error": message,
                },
                indent=2,
            )
        )
        return
    print(message, file=sys.stderr)
