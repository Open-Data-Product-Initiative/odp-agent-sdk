"""Shared value helpers for Portfolio workflows and rendering."""

from __future__ import annotations

import html
from typing import Any, Dict, List

from .odpc.catalog import text_value


def as_list(mapping: Any, key: str) -> List[Dict[str, Any]]:
    """Return mapping items when a key contains a list of mappings."""
    if not isinstance(mapping, dict):
        return []
    value = mapping.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def count(mapping: Any, key: str) -> int:
    """Count mapping items for a list-valued key."""
    return len(as_list(mapping, key))


def text(value: Any, fallback: str = "") -> str:
    """Return localized text as a display string."""
    return text_value(value, fallback)


def escape(value: str) -> str:
    """Escape text for an HTML element."""
    return html.escape(value)


def escape_attr(value: str) -> str:
    """Escape text for an HTML attribute."""
    return html.escape(value, quote=True)
