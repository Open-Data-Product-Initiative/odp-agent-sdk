"""ARWS-style agent manifest generation.

Renders the SDK's MCP tool registry as the discovery payload an agent host
fetches from ``/.well-known/agent-manifest.json`` per
agenticpatterns.veso.ai/arws.
"""

from __future__ import annotations

from typing import Any, Dict

from .tools import TOOLS


def generate_agent_manifest() -> Dict[str, Any]:
    """Return the ARWS manifest for this SDK."""
    return {
        "name": "open-data-products",
        "description": (
            "Validate, explain, traverse, and search Open Data Products documents "
            "(ODPS, ODPC, ODPG, ODPV)."
        ),
        "version": _package_version(),
        "auth": {"type": "none"},
        "tools": [_describe(tool) for tool in TOOLS],
    }


def _describe(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "class": tool["class"],
        "inputSchema": tool["inputSchema"],
    }


def _package_version() -> str:
    from .. import __version__

    return __version__


__all__ = ["generate_agent_manifest"]
