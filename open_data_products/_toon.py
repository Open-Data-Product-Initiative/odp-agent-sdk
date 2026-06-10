"""Small TOON rendering helpers for agent-facing exports."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Union

JsonPrimitive = Union[str, int, float, bool, None]

_UNQUOTED_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_NUMERIC_LIKE = re.compile(r"^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$", re.IGNORECASE)


def key_token(value: str) -> str:
    """Return a TOON object key token."""
    return value if _UNQUOTED_KEY.match(value) else quoted_string(value)


def quoted_string(value: str) -> str:
    """Return a double-quoted TOON string token."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def primitive_token(value: JsonPrimitive, *, delimiter: str = ",") -> str:
    """Return a TOON primitive token."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "null"
        if value == 0:
            return "0"
        return f"{value:.15g}"

    text = str(value)
    if _needs_quotes(text, delimiter):
        return quoted_string(text)
    return text


def render_fields(
    fields: Mapping[str, JsonPrimitive],
    *,
    depth: int = 0,
) -> list[str]:
    """Render object fields as TOON lines."""
    prefix = "  " * depth
    return [
        f"{prefix}{key_token(key)}: {primitive_token(value)}"
        for key, value in fields.items()
    ]


def render_table(
    key: str,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, JsonPrimitive]],
    *,
    depth: int = 0,
) -> list[str]:
    """Render a uniform primitive-object array as TOON tabular rows."""
    prefix = "  " * depth
    child_prefix = "  " * (depth + 1)
    header_fields = ",".join(key_token(field) for field in fields)
    lines = [f"{prefix}{key_token(key)}[{len(rows)}]{{{header_fields}}}:"]
    for row in rows:
        cells = [primitive_token(row.get(field), delimiter=",") for field in fields]
        lines.append(f"{child_prefix}{','.join(cells)}")
    return lines


def write_toon(path: Union[str, Path], content: str) -> None:
    """Write TOON content to a file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _needs_quotes(value: str, delimiter: str) -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if value in {"true", "false", "null", "-"}:
        return True
    if value.startswith("-"):
        return True
    if _NUMERIC_LIKE.match(value):
        return True
    if any(char in value for char in (":", '"', "\\", "[", "]", "{", "}")):
        return True
    if delimiter and delimiter in value:
        return True
    return any(ord(char) < 32 for char in value)
