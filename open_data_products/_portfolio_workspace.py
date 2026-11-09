"""Workspace document helpers for Portfolio workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ._io import load_mapping


def load_optional_mapping(path: Path) -> Dict[str, Any]:
    """Load a mapping when a workspace artifact exists."""
    if not path.exists():
        return {}
    return load_mapping(path, root_name="Portfolio")


def empty_catalog() -> Dict[str, Any]:
    """Return the default empty catalog document."""
    return {"catalog": {"metadata": {"name": {"en": "Portfolio"}}}}


def empty_graph() -> Dict[str, Any]:
    """Return the default empty graph document."""
    return {"graph": {"metadata": {}, "nodes": [], "edges": []}}
