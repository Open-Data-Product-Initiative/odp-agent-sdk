"""ODPC catalog loading, explanation, object search, and validation helpers."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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


SCHEMA_URI = "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml"
OBJECT_COLLECTIONS = {
    "productReference": "productReferences",
    "useCase": "useCases",
    "businessObjective": "businessObjectives",
    "signal": "signals",
}
CATALOG_COLLECTIONS = tuple(OBJECT_COLLECTIONS.values())
METADATA_KEYS = ("metadata", "catalogMetadata")
HTML_PLACEHOLDERS = (
    "title",
    "catalog_header",
    "summary",
    "product_references",
    "use_cases",
    "business_objectives",
    "signals",
)
HTML_FIELDS = {
    "productReferences": (
        ("Product ID", "productID"),
        ("Version", "productVersion"),
        ("Status", "status"),
        ("Visibility", "visibility"),
    ),
    "useCases": (
        ("Status", "status"),
        ("Priority", "priority"),
        ("Decision", "decision"),
        ("Expected outcome", "expectedOutcome"),
    ),
    "businessObjectives": (
        ("Status", "status"),
        ("Priority", "priority"),
    ),
    "signals": (
        ("Type", "type"),
        ("Strength", "strength"),
        ("Confidence", "confidence"),
        ("Status", "status"),
    ),
}
HTML_SECTION_TITLES = {
    "productReferences": "Product References",
    "useCases": "Use Cases",
    "businessObjectives": "Business Objectives",
    "signals": "Signals",
}


def _data_file(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath("data", *parts)


DEFAULT_CATALOG_HTML_TEMPLATE = _data_file("templates", "catalog.html")


def load_catalog(path: Union[str, Path]) -> Dict[str, Any]:
    """Load an ODPC catalog from JSON or YAML."""
    return load_mapping(
        Path(path),
        yaml_loader=NoDatesSafeLoader,
        root_name="ODPC catalog",
    )


def iter_catalog_input_files(
    input_dir: Union[str, Path],
    *,
    recursive: bool = True,
) -> List[Path]:
    """Return YAML and JSON catalog fragment files under ``input_dir``."""
    root = Path(input_dir)
    patterns = ("*.yaml", "*.yml", "*.json")
    paths: List[Path] = []
    for pattern in patterns:
        paths.extend(root.rglob(pattern) if recursive else root.glob(pattern))
    return sorted(path for path in paths if path.is_file())


def lang_string(value: Any) -> Dict[str, Any]:
    """Return a language string mapping for scalar input."""
    if isinstance(value, dict):
        return value
    return {"en": value}


def default_catalog_metadata(
    *,
    catalog_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Return default metadata for a generated ODPC catalog."""
    return {
        "id": catalog_id or "CAT-GENERATED",
        "name": lang_string(name or "Generated ODPC Catalog"),
        "description": lang_string(
            description or "Generated from ODPC YAML fragments."
        ),
    }


def append_catalog_items(
    target: Dict[str, List[Any]],
    collection: str,
    items: Any,
) -> None:
    """Append list items into a catalog collection."""
    if isinstance(items, list):
        target[collection].extend(item for item in items if item is not None)


def as_lang_string(value: Any, fallback: str) -> Dict[str, Any]:
    """Return a language string, falling back when input is blank."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return {"en": value}
    return {"en": fallback}


def product_details(product: Dict[str, Any]) -> Dict[str, Any]:
    """Return the most useful ODPS product details mapping."""
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            return english
    return product


def product_reference_from_product(
    document: Dict[str, Any],
    source_path: Union[str, Path],
    input_dir: Union[str, Path],
) -> Optional[Dict[str, Any]]:
    """Build an ODPC ProductReference from an ODPS product document."""
    product = document.get("product")
    if not isinstance(product, dict):
        return None

    path = Path(source_path)
    details = product_details(product)
    product_id = (
        details.get("productID")
        or product.get("productID")
        or details.get("id")
        or product.get("id")
        or path.stem
    )
    product_version = (
        details.get("productVersion")
        or product.get("productVersion")
        or details.get("version")
        or product.get("version")
        or document.get("version")
        or "1.0.0"
    )
    reference_path = path.relative_to(Path(input_dir)).as_posix()
    product_format = "json" if path.suffix.lower() == ".json" else "yaml"
    reference = {
        "id": str(details.get("id") or product.get("id") or product_id),
        "productID": str(product_id),
        "productVersion": str(product_version),
        "name": as_lang_string(
            details.get("name") or product.get("name"), str(product_id)
        ),
        "description": as_lang_string(
            details.get("description") or product.get("description"),
            f"Reference to {product_id}.",
        ),
        "productModel": {
            "standard": "ODPS",
            "version": str(document.get("version") or "4.1"),
            "format": product_format,
            "$ref": reference_path,
        },
    }
    for key in ("visibility", "status", "type"):
        value = details.get(key) or product.get(key)
        if value:
            reference[key] = value
    return reference


def collect_catalog_document(
    document: Dict[str, Any],
    source_path: Union[str, Path],
    input_dir: Union[str, Path],
    catalog: Dict[str, List[Any]],
    metadata_candidates: List[Dict[str, Any]],
    embedded_metadata_candidates: List[Dict[str, Any]],
) -> None:
    """Collect ODPC catalog parts from a document."""
    if not isinstance(document, dict):
        raise ValueError(
            f"{source_path}: expected a YAML or JSON object at the document root"
        )

    nested_catalog = document.get("catalog")
    if isinstance(nested_catalog, dict):
        metadata = nested_catalog.get("metadata")
        if isinstance(metadata, dict):
            embedded_metadata_candidates.append(metadata)
        for collection in CATALOG_COLLECTIONS:
            append_catalog_items(catalog, collection, nested_catalog.get(collection))
        return

    for metadata_key in METADATA_KEYS:
        metadata = document.get(metadata_key)
        if isinstance(metadata, dict):
            metadata_candidates.append(metadata)

    for object_key, collection in OBJECT_COLLECTIONS.items():
        item = document.get(object_key)
        if item is not None:
            catalog[collection].append(item)

    product_reference = product_reference_from_product(document, source_path, input_dir)
    if product_reference:
        catalog["productReferences"].append(product_reference)

    for collection in CATALOG_COLLECTIONS:
        append_catalog_items(catalog, collection, document.get(collection))


def build_catalog(
    input_dir: Union[str, Path],
    *,
    recursive: bool = True,
    output_path: Optional[Union[str, Path]] = None,
    catalog_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one ODPC catalog from catalog fragments in a folder."""
    root = Path(input_dir)
    output = Path(output_path).resolve() if output_path is not None else None
    catalog: Dict[str, List[Any]] = {
        collection: [] for collection in CATALOG_COLLECTIONS
    }
    metadata_candidates: List[Dict[str, Any]] = []
    embedded_metadata_candidates: List[Dict[str, Any]] = []

    for path in iter_catalog_input_files(root, recursive=recursive):
        if output is not None and path.resolve() == output:
            continue
        collect_catalog_document(
            load_catalog(path),
            path,
            root,
            catalog,
            metadata_candidates,
            embedded_metadata_candidates,
        )

    if metadata_candidates:
        metadata = dict(metadata_candidates[0])
    elif embedded_metadata_candidates:
        metadata = dict(embedded_metadata_candidates[0])
    else:
        metadata = default_catalog_metadata(
            catalog_id=catalog_id,
            name=name,
            description=description,
        )
    if catalog_id:
        metadata["id"] = catalog_id
    if name:
        metadata["name"] = lang_string(name)
    if description:
        metadata["description"] = lang_string(description)

    populated_catalog = {key: value for key, value in catalog.items() if value}
    return {
        "schema": SCHEMA_URI,
        "version": "1.0",
        "kind": "Catalog",
        "catalog": {"metadata": metadata, **populated_catalog},
    }


def write_catalog(
    path: Union[str, Path],
    document: Dict[str, Any],
) -> None:
    """Write an ODPC catalog document as YAML."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def text_value(value: Any, fallback: str = "") -> str:
    """Return text from a scalar or English language string."""
    if isinstance(value, dict):
        return str(value.get("en") or fallback)
    if value is None:
        return fallback
    return str(value)


def escaped_text(value: Any, fallback: str = "") -> str:
    """Return HTML-escaped text."""
    return html.escape(text_value(value, fallback))


def render_html_link(value: Any) -> str:
    """Render an escaped link when a value is present."""
    if not value:
        return ""
    escaped = html.escape(str(value), quote=True)
    return f'<a href="{escaped}">{escaped}</a>'


def render_catalog_header(document: Dict[str, Any]) -> str:
    """Render the catalog HTML header fragment."""
    catalog = document.get("catalog", {})
    metadata = catalog.get("metadata", {}) if isinstance(catalog, dict) else {}
    graph = metadata.get("graph") if isinstance(metadata, dict) else None
    lines = [
        '<header class="odp-header">',
        f"<h1>{escaped_text(metadata.get('name'), 'ODPC Catalog')}</h1>",
        f'<p class="odp-id">{escaped_text(metadata.get("id"))}</p>',
        f'<p class="odp-description">{escaped_text(metadata.get("description"))}</p>',
    ]
    if isinstance(graph, dict):
        lines.append(
            '<p class="odp-graph">'
            f"Graph: {escaped_text(graph.get('standard'))} "
            f"{escaped_text(graph.get('version'))} "
            f"{render_html_link(graph.get('$ref'))}</p>"
        )
    lines.append("</header>")
    return "\n".join(lines)


def render_catalog_summary(document: Dict[str, Any]) -> str:
    """Render the catalog count summary fragment."""
    catalog = document.get("catalog", {})
    counts = {
        "Product References": count_items(catalog, "productReferences"),
        "Use Cases": count_items(catalog, "useCases"),
        "Business Objectives": count_items(catalog, "businessObjectives"),
        "Signals": count_items(catalog, "signals"),
    }
    items = "".join(
        f'<li><span class="odp-count">{count}</span><span>{html.escape(label)}</span></li>'
        for label, count in counts.items()
    )
    return f'<section class="odp-summary"><h2>Summary</h2><ul>{items}</ul></section>'


def render_catalog_card(
    item: Any,
    fields: Tuple[Tuple[str, str], ...],
) -> str:
    """Render one catalog item card."""
    if not isinstance(item, dict):
        return ""

    lines = [
        '<article class="odp-card">',
        f"<h3>{escaped_text(item.get('name'), item.get('id', '(unnamed)'))}</h3>",
        f'<p class="odp-id">{escaped_text(item.get("id"))}</p>',
    ]
    description = escaped_text(item.get("description"))
    if description:
        lines.append(f"<p>{description}</p>")

    facts = []
    for label, key in fields:
        value = item.get(key)
        if value:
            facts.append(f"<dt>{html.escape(label)}</dt><dd>{escaped_text(value)}</dd>")
    product_model = item.get("productModel")
    if isinstance(product_model, dict):
        facts.append(
            "<dt>Product model</dt>"
            f"<dd>{escaped_text(product_model.get('standard'))} "
            f"{escaped_text(product_model.get('version'))} "
            f"{render_html_link(product_model.get('$ref'))}</dd>"
        )
    if facts:
        lines.append(f'<dl class="odp-facts">{"".join(facts)}</dl>')

    tags = item.get("tags")
    if isinstance(tags, list) and tags:
        tag_items = "".join(f"<li>{html.escape(str(tag))}</li>" for tag in tags)
        lines.append(f'<ul class="odp-tags">{tag_items}</ul>')

    lines.append("</article>")
    return "\n".join(lines)


def render_catalog_section(
    title: str,
    items: Any,
    fields: Tuple[Tuple[str, str], ...],
) -> str:
    """Render one HTML catalog section."""
    if not isinstance(items, list) or not items:
        return (
            f'<section class="odp-section"><h2>{html.escape(title)}</h2>'
            "<p>No entries.</p></section>"
        )
    cards = "\n".join(render_catalog_card(item, fields) for item in items)
    return (
        f'<section class="odp-section"><h2>{html.escape(title)}</h2>{cards}</section>'
    )


def render_catalog_html(document: Dict[str, Any]) -> str:
    """Render a standalone browser-viewable ODPC catalog HTML document."""
    catalog = document.get("catalog", {})
    metadata = catalog.get("metadata", {}) if isinstance(catalog, dict) else {}
    fragments = {
        "title": escaped_text(metadata.get("name"), "ODPC Catalog"),
        "catalog_header": render_catalog_header(document),
        "summary": render_catalog_summary(document),
        "product_references": render_catalog_section(
            "Product References",
            catalog.get("productReferences", []) if isinstance(catalog, dict) else [],
            HTML_FIELDS["productReferences"],
        ),
        "use_cases": render_catalog_section(
            "Use Cases",
            catalog.get("useCases", []) if isinstance(catalog, dict) else [],
            HTML_FIELDS["useCases"],
        ),
        "business_objectives": render_catalog_section(
            "Business Objectives",
            catalog.get("businessObjectives", []) if isinstance(catalog, dict) else [],
            HTML_FIELDS["businessObjectives"],
        ),
        "signals": render_catalog_section(
            "Signals",
            catalog.get("signals", []) if isinstance(catalog, dict) else [],
            HTML_FIELDS["signals"],
        ),
    }
    rendered = DEFAULT_CATALOG_HTML_TEMPLATE.read_text(encoding="utf-8")
    for placeholder in HTML_PLACEHOLDERS:
        rendered = rendered.replace("{{ " + placeholder + " }}", fragments[placeholder])
    return rendered


def write_catalog_html(
    path: Union[str, Path],
    document: Dict[str, Any],
) -> None:
    """Write an ODPC catalog as standalone HTML."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_catalog_html(document), encoding="utf-8")


def load_schema(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load ODPC schema YAML from ``path`` or bundled package data."""
    schema_path = Path(path) if path is not None else _data_file("schema", "odpc.yaml")
    return load_mapping(schema_path, root_name="ODPC schema")


def render_catalog_schema_json(
    schema: Optional[Dict[str, Any]] = None,
) -> str:
    """Render the canonical ODPC schema as derived formatted JSON."""
    return json.dumps(schema or load_schema(), indent=2) + "\n"


def build_catalog_artifacts(
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build derived ODPC catalog artifact contents."""
    return {"odpc.json": render_catalog_schema_json(schema)}


def write_catalog_artifacts(
    output_dir: Union[str, Path],
    *,
    schema: Optional[Dict[str, Any]] = None,
    check: bool = False,
) -> List[Path]:
    """Write or check derived ODPC catalog artifacts under ``output_dir``."""
    root = Path(output_dir)
    changed = []
    for relative_name, content in build_catalog_artifacts(schema).items():
        relative_path = Path(relative_name)
        path = root / relative_path
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        changed.append(relative_path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed


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
