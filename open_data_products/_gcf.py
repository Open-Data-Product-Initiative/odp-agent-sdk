"""Small GCF rendering helpers for agent-facing exports."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Union

GcfPrimitive = Union[str, int, float, bool, None]


def primitive_token(value: GcfPrimitive) -> str:
    """Return a GCF primitive token."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "-"
        if value == 0:
            return "0"
        return f"{value:.15g}"

    text = str(value)
    if _needs_quotes(text):
        return _quoted_string(text)
    return text


def write_gcf(path: Union[str, Path], content: str) -> None:
    """Write GCF content to a file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _quoted_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _needs_quotes(value: str) -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if value in {"-", "~", "^"}:
        return True
    if any(char in value for char in ("|", '"', "\\", "\n", "\r", "\t")):
        return True
    return any(ord(char) < 32 for char in value)
