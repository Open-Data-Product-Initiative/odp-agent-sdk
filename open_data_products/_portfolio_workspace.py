"""Workspace document helpers for Portfolio workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ._io import load_mapping
from ._portfolio_values import text


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


def product_spec_paths(root: Path) -> List[Path]:
    """Return supported ODPS product files in a workspace."""
    product_dir = root / "odps" / "products"
    return sorted(
        [
            *product_dir.glob("*.yaml"),
            *product_dir.glob("*.yml"),
            *product_dir.glob("*.json"),
        ]
    )


def product_details(document: Dict[str, Any]) -> Dict[str, Any]:
    """Return the preferred ODPS product details mapping."""
    product = document.get("product")
    if not isinstance(product, dict):
        return {}
    details = product.get("details")
    if isinstance(details, dict) and isinstance(details.get("en"), dict):
        return details["en"]
    return product


def load_product_specs(root: Path) -> Dict[str, Dict[str, Any]]:
    """Load valid product documents keyed by product identifier."""
    products: Dict[str, Dict[str, Any]] = {}
    for path in product_spec_paths(root):
        try:
            document = load_mapping(path, root_name="ODPS product")
        except ValueError:
            continue
        details = product_details(document)
        products[text(details.get("productID") or details.get("id"), path.stem)] = {
            "path": path,
            "document": document,
        }
    return products
