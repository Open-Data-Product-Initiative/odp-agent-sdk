"""ODPC catalog loading, explanation, object search, and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from open_data_products._io import load_jsonl_records, load_mapping
from open_data_products._search import search_records, searchable_record_text


class NoDatesSafeLoader(yaml.SafeLoader):
    """YAML loader that keeps date-like values as strings."""


for first_char, resolvers in list(NoDatesSafeLoader.yaml_implicit_resolvers.items()):
    NoDatesSafeLoader.yaml_implicit_resolvers[first_char] = [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]


@dataclass(frozen=True)
class CatalogValidationResult:
    """Result from validating an ODPC catalog document."""

    valid: bool
    errors: List[str]


def _data_file(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath("data", *parts)


def load_catalog(path: Union[str, Path]) -> Dict[str, Any]:
    """Load an ODPC catalog from JSON or YAML."""
    return load_mapping(
        Path(path),
        yaml_loader=NoDatesSafeLoader,
        root_name="ODPC catalog",
    )


def load_schema(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load ODPC schema YAML from ``path`` or bundled package data."""
    schema_path = Path(path) if path is not None else _data_file("schema", "odpc.yaml")
    return load_mapping(schema_path, root_name="ODPC schema")


def load_object_records(
    path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Load ODPC object records from JSONL."""
    records_path = (
        Path(path) if path is not None else _data_file("catalog", "objects.jsonl")
    )
    return load_jsonl_records(records_path)


def search_objects(
    query: Optional[str] = None,
    *,
    object_id: Optional[str] = None,
    records: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search bundled ODPC object records by keyword or exact object id."""
    source_records = records if records is not None else load_object_records()
    return search_records(
        source_records,
        query,
        object_id=object_id,
        limit=limit,
        searchable_text=searchable_record_text,
    )


def render_object_records(records: List[Dict[str, Any]]) -> str:
    """Render ODPC object records in the source script text format."""
    if not records:
        return "No matching ODPC objects found.\n"

    sections = []
    for record in records:
        sections.append(
            "\n".join(
                [
                    f"{record['id']}",
                    f"  Definition: {record['definition']}",
                    f"  Required fields: {', '.join(record['requiredFields']) or '(none)'}",
                    f"  Use for: {', '.join(record['doUseFor'])}",
                    f"  Do not use for: {', '.join(record['doNotUseFor'])}",
                    f"  Example: {record['exampleFile']}",
                ]
            )
        )
    return "\n\n".join(sections) + "\n"


def lang_en(value: Any, fallback: str = "(unnamed)") -> str:
    """Return English language value or a fallback."""
    if isinstance(value, dict):
        return value.get("en") or fallback
    if isinstance(value, str):
        return value
    return fallback


def count_items(catalog: Dict[str, Any], key: str) -> int:
    """Count list items under a catalog key."""
    value = catalog.get(key, [])
    return len(value) if isinstance(value, list) else 0


def collect_ids(items: Any) -> List[str]:
    """Collect id values from a list of ODPC objects."""
    if not isinstance(items, list):
        return []
    return [
        str(item["id"])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def explain_catalog(
    document: Dict[str, Any],
    *,
    path: Union[str, Path] = "(memory)",
) -> str:
    """Render an ODPC catalog summary for humans and AI agents."""
    catalog = document.get("catalog", {}) if isinstance(document, dict) else {}
    metadata = catalog.get("metadata", {}) if isinstance(catalog, dict) else {}
    lines = [
        f"File: {path}",
        f"Schema: {document.get('schema', '(missing)') if isinstance(document, dict) else '(missing)'}",
        f"ODPC version: {document.get('version', '(missing)') if isinstance(document, dict) else '(missing)'}",
        f"Catalog id: {metadata.get('id', '(missing)')}",
        f"Catalog name: {lang_en(metadata.get('name'))}",
        f"Status: {metadata.get('status', '(not set)')}",
        f"Product references: {count_items(catalog, 'productReferences')}",
        f"Use cases: {count_items(catalog, 'useCases')}",
        f"Business objectives: {count_items(catalog, 'businessObjectives')}",
        f"Signals: {count_items(catalog, 'signals')}",
    ]

    graph = metadata.get("graph")
    if isinstance(graph, dict):
        lines.append(
            f"Graph: {graph.get('standard', '(unknown)')} "
            f"{graph.get('version', '')} {graph.get('$ref', '')}".strip()
        )
    else:
        lines.append("Graph: (not set)")

    ids = {
        "Product reference ids": collect_ids(catalog.get("productReferences", [])),
        "Use case ids": collect_ids(catalog.get("useCases", [])),
        "Business objective ids": collect_ids(catalog.get("businessObjectives", [])),
        "Signal ids": collect_ids(catalog.get("signals", [])),
    }
    for label, values in ids.items():
        if values:
            lines.append(f"{label}: {', '.join(values)}")

    hints = []
    if count_items(catalog, "productReferences") == 0:
        hints.append(
            "No productReferences found; add ProductReference objects when "
            "cataloging data products."
        )
    if graph is None:
        hints.append(
            "No graph reference found; use Catalog.metadata.graph when "
            "relationships are implemented in ODPG or another graph standard."
        )
    if hints:
        lines.append("Hints:")
        lines.extend(f"- {hint}" for hint in hints)

    return "\n".join(lines) + "\n"


def validate_catalog(
    document: Dict[str, Any],
    *,
    schema: Optional[Dict[str, Any]] = None,
) -> CatalogValidationResult:
    """Validate an ODPC catalog document against the bundled schema."""
    try:
        import jsonschema
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency: jsonschema. Install open-data-products with "
            "ODPC validation dependencies."
        ) from exc

    schema_data = schema or load_schema()
    jsonschema.Draft202012Validator.check_schema(schema_data)
    validator = jsonschema.Draft202012Validator(schema_data)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return CatalogValidationResult(valid=not messages, errors=messages)
