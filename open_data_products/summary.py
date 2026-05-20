"""Lightweight artifact-reference summaries for ODP documents.

Returns metadata only — never the parsed body — so agents can pass references
through their context window without paying the token cost of the full file.
Aligns with the artifact-driven design rule from agenticpatterns.veso.ai/context-management.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Union

from ._io import load_mapping
from .agent import detect_document


def load_summary(path: Union[str, Path]) -> Dict[str, Any]:
    """Return a fixed-shape, document-body-free reference for ``path``.

    Keys: ``path``, ``byte_size``, ``line_count``, ``sha256``, ``spec``,
    ``kind``, ``id``. ``spec`` falls back to ``"unknown"`` when detection
    cannot resolve the document.
    """
    p = Path(path)
    raw = p.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    spec = "unknown"
    kind = ""
    doc_id = ""
    try:
        data = load_mapping(p)
        spec, kind = detect_document(data)
        doc_id = _extract_id(data)
    except Exception:
        pass

    return {
        "path": str(p),
        "byte_size": len(raw),
        "line_count": _line_count(text),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "spec": spec,
        "kind": kind,
        "id": doc_id,
    }


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _extract_id(data: Dict[str, Any]) -> str:
    for key in ("id", "productID"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    product = data.get("product")
    if isinstance(product, dict):
        for key in ("productID", "id"):
            value = product.get(key)
            if isinstance(value, str):
                return value
    catalog = data.get("catalog")
    if isinstance(catalog, dict):
        meta = catalog.get("metadata")
        if isinstance(meta, dict):
            value = meta.get("id")
            if isinstance(value, str):
                return value
    graph = data.get("graph")
    if isinstance(graph, dict):
        meta = graph.get("metadata")
        if isinstance(meta, dict):
            value = meta.get("id")
            if isinstance(value, str):
                return value
    return ""
