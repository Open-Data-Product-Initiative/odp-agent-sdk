"""Workspace document helpers for Portfolio workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from ._io import load_mapping
from ._portfolio_values import change_list_count, text


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


def write_yaml(
    path: Path, document: Dict[str, Any], *, allow_unicode: bool = False
) -> tuple:
    """Write YAML and classify the artifact change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(document, sort_keys=False, allow_unicode=allow_unicode)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(content, encoding="utf-8")
    return path, (
        "unchanged" if previous == content else "updated" if existed else "created"
    )


def write_text(path: Path, content: str) -> tuple:
    """Write text and classify the artifact change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(content, encoding="utf-8")
    return path, (
        "unchanged" if previous == content else "updated" if existed else "created"
    )


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


def load_version_report(path: Path) -> Dict[str, Any]:
    """Load a version report when available and valid."""
    if not path.exists():
        return {}
    try:
        return load_mapping(path, root_name="Portfolio version report")
    except ValueError:
        return {}


def version_report_summary(report: Dict[str, Any]) -> str:
    """Summarize artifact changes from a version report."""
    changes = []
    for key, label in (
        ("created", "created"),
        ("updated", "updated"),
        ("removed", "removed"),
    ):
        count = change_list_count(report.get(key))
        if count:
            changes.append(f"{count} {label}")
    return ", ".join(changes)


def portfolio_versions(root: Path, portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return saved version metadata or discover version reports."""
    versions = []
    for item in (
        portfolio.get("versions", [])
        if isinstance(portfolio.get("versions"), list)
        else []
    ):
        if not isinstance(item, dict):
            continue
        version_id = str(item.get("id") or item.get("version") or "")
        html_path = str(item.get("html") or f"versions/{version_id}/index.html")
        if version_id:
            report = load_version_report((root / html_path).parent / "report.json")
            versions.append(
                {
                    "id": version_id,
                    "type": str(
                        item.get("type")
                        or item.get("runType")
                        or report.get("kind")
                        or "snapshot"
                    ),
                    "summary": str(
                        item.get("summary") or version_report_summary(report) or ""
                    ),
                    "html": html_path,
                    "report": report,
                }
            )
    if versions:
        return versions
    for path in (
        sorted((root / "versions").glob("*/index.html"))
        if (root / "versions").exists()
        else []
    ):
        report = load_version_report(path.parent / "report.json")
        versions.append(
            {
                "id": path.parent.name,
                "type": str(report.get("kind") or "snapshot"),
                "summary": version_report_summary(report),
                "html": path.relative_to(root).as_posix(),
                "report": report,
            }
        )
    return versions
