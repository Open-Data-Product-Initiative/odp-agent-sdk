"""Agent-oriented helpers across the Open Data Products standards family."""

from __future__ import annotations

from jsonschema import Draft202012Validator
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from ._io import load_mapping
from .odpc import explain_catalog, load_catalog, validate_catalog
from .odpg import explain_graph, load_graph, validate_graph
from .odps import OpenDataProduct
from .odps.exceptions import ODPSValidationError
from .odpv import load_vocabulary, validate_vocabulary
from .results import Reference, ValidationResult

Document = Union[OpenDataProduct, Dict[str, Any]]
_ODPS_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "odps" / "data" / "schema" / "odps.json"
)


def load_document(path: Union[str, Path]) -> Document:
    """Load an ODPS, ODPC, or ODPG document from JSON or YAML."""
    document_path = Path(path)
    data = _load_mapping(document_path)
    spec, _kind = detect_document(data)
    if spec == "odps":
        return OpenDataProduct.from_file(document_path)
    if spec == "odpc":
        return load_catalog(document_path)
    if spec == "odpg":
        return load_graph(document_path)
    if spec == "odpv":
        return load_vocabulary(document_path)
    raise ValueError(f"Unsupported Open Data Products document: {document_path}")


def detect_document(document: Document) -> Tuple[str, str]:
    """Return ``(spec, kind)`` for an Open Data Products document."""
    if isinstance(document, OpenDataProduct):
        return "odps", "OpenDataProduct"
    if not isinstance(document, dict):
        raise ValueError("Document must be an OpenDataProduct or mapping")

    schema = str(document.get("schema", "")).lower()
    kind = str(document.get("kind", "") or "")
    if "odpc" in schema or kind == "Catalog" or "catalog" in document:
        return "odpc", kind or "Catalog"
    if "odpg" in schema or kind in {"Graph", "DataProductGraph"}:
        return "odpg", kind or "Graph"
    if "odps" in schema or "product" in document:
        return "odps", "OpenDataProduct"
    if document.get("id") == "ODPV" or "sections" in document:
        return "odpv", "Vocabulary"
    raise ValueError("Could not detect Open Data Products specification")


def validate_document(
    document: Union[Document, str, Path],
    *,
    path: Optional[Union[str, Path]] = None,
) -> ValidationResult:
    """Validate an Open Data Products document using the matching spec helper."""
    loaded = load_document(document) if isinstance(document, (str, Path)) else document
    source_path = (
        str(document) if isinstance(document, (str, Path)) else _path_str(path)
    )
    spec, kind = detect_document(loaded)

    if spec == "odps":
        raw_errors = _validate_raw_odps_document(document, path)
        if raw_errors:
            return ValidationResult(False, spec, kind, raw_errors, path=source_path)
        try:
            assert isinstance(loaded, OpenDataProduct)
            loaded.validate()
            return ValidationResult(True, spec, kind, path=source_path)
        except ODPSValidationError as exc:
            return ValidationResult(False, spec, kind, [str(exc)], path=source_path)

    if spec == "odpc":
        assert isinstance(loaded, dict)
        catalog_result = validate_catalog(loaded)
        return ValidationResult(
            valid=catalog_result.valid,
            spec=spec,
            kind=kind,
            errors=catalog_result.errors,
            path=source_path,
        )

    if spec == "odpg":
        assert isinstance(loaded, dict)
        graph_result = validate_graph(loaded)
        return ValidationResult(
            valid=graph_result.valid,
            spec=spec,
            kind=kind,
            errors=graph_result.errors,
            warnings=graph_result.warnings,
            hints=graph_result.hints,
            path=source_path,
        )

    if spec == "odpv":
        assert isinstance(loaded, dict)
        vocabulary_result = validate_vocabulary(loaded)
        return ValidationResult(
            valid=vocabulary_result.valid,
            spec=spec,
            kind=kind,
            errors=vocabulary_result.errors,
            path=source_path,
        )

    return ValidationResult(
        False,
        spec,
        kind,
        [f"Validation is not available for detected spec: {spec}"],
        path=source_path,
    )


def explain_document(
    document: Union[Document, str, Path],
    *,
    path: Optional[Union[str, Path]] = None,
) -> str:
    """Return a compact explanation for humans and AI agents."""
    loaded = load_document(document) if isinstance(document, (str, Path)) else document
    source_path = Path(document) if isinstance(document, (str, Path)) else path
    spec, _kind = detect_document(loaded)
    if spec == "odps":
        assert isinstance(loaded, OpenDataProduct)
        return explain_product(loaded, path=source_path)
    if spec == "odpc":
        assert isinstance(loaded, dict)
        return explain_catalog(loaded, path=source_path or "(memory)")
    if spec == "odpg":
        assert isinstance(loaded, dict)
        return explain_graph(loaded, path=source_path or "(memory)")
    if spec == "odpv":
        assert isinstance(loaded, dict)
        return explain_vocabulary(loaded, path=source_path)
    return f"Open Data Products document detected as {spec}.\n"


def explain_product(
    product: OpenDataProduct,
    *,
    path: Optional[Union[str, Path]] = None,
) -> str:
    """Render a compact ODPS product summary for humans and AI agents."""
    details = product.product_details
    lines = [
        f"File: {path or '(memory)'}",
        f"Schema: {product.schema}",
        f"ODPS version: {product.version}",
        f"Product id: {details.product_id}",
        f"Product name: {details.name}",
        f"Status: {details.status}",
        f"Visibility: {details.visibility}",
        f"Type: {details.type}",
        f"Components: {product.component_count}",
        f"Compliance level: {product.compliance_level}",
        f"Production ready: {product.is_production_ready}",
    ]
    if product.product_strategy:
        lines.append(f"Strategy objectives: {len(product.product_strategy.objectives)}")
        lines.append(f"Product KPIs: {len(product.product_strategy.product_kpis)}")
    if product.data_access:
        lines.append("Data access: configured")
    else:
        lines.append("Data access: (not set)")
    return "\n".join(lines) + "\n"


def explain_vocabulary(
    vocabulary: Dict[str, Any],
    *,
    path: Optional[Union[str, Path]] = None,
) -> str:
    """Render a compact ODPV vocabulary summary for humans and AI agents."""
    result = validate_vocabulary(vocabulary)
    sections = vocabulary.get("sections", [])
    lines = [
        f"File: {path or '(memory)'}",
        f"Vocabulary id: {vocabulary.get('id', '(missing)')}",
        f"Version: {vocabulary.get('version', '(missing)')}",
        f"Sections: {result.section_count}",
        f"Terms: {result.term_count}",
        f"Relationships: {result.relationship_count}",
        f"Valid: {result.valid}",
    ]
    if isinstance(sections, list) and sections:
        section_ids = [
            str(section.get("id"))
            for section in sections
            if isinstance(section, dict) and section.get("id")
        ]
        if section_ids:
            lines.append(f"Section ids: {', '.join(section_ids)}")
    return "\n".join(lines) + "\n"


def resolve_references(
    document: Union[Document, str, Path],
    *,
    path: Optional[Union[str, Path]] = None,
) -> List[Reference]:
    """Discover ``ref`` and ``$ref`` values for cross-spec traversal."""
    loaded = load_document(document) if isinstance(document, (str, Path)) else document
    source_path = (
        str(document) if isinstance(document, (str, Path)) else _path_str(path)
    )
    spec, _kind = detect_document(loaded)
    data = loaded.to_dict() if isinstance(loaded, OpenDataProduct) else loaded
    refs = []
    for pointer, key, value in _walk_references(data):
        refs.append(
            Reference(
                ref=str(value),
                pointer=pointer,
                ref_type=_reference_type(pointer, key),
                source_spec=spec,
                target_spec=_infer_target_spec(str(value)),
                source_path=source_path,
            )
        )
    return refs


def _load_mapping(path: Path) -> Dict[str, Any]:
    return load_mapping(path)


def _validate_raw_odps_document(
    document: Union[Document, str, Path],
    path: Optional[Union[str, Path]],
) -> List[str]:
    raw = _raw_mapping(document, path)
    if raw is None:
        return []
    if not _is_odps_v41(raw):
        return []

    schema = load_mapping(_ODPS_SCHEMA_PATH)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda error: list(error.path))
    return _validate_odps_v41_shape(raw) + [
        _format_schema_error(error) for error in errors
    ]


def _is_odps_v41(document: Dict[str, Any]) -> bool:
    schema = str(document.get("schema", "")).lower()
    version = str(document.get("version", ""))
    return "v4.1" in schema or version in {"4.1", "v4.1"}


def _validate_odps_v41_shape(document: Dict[str, Any]) -> List[str]:
    product = document.get("product")
    if not isinstance(product, dict):
        return []

    errors = []
    details = product.get("details")
    if not isinstance(details, dict) or not details:
        errors.append(
            "/product/details: ODPS v4.1 data products must define "
            "language-keyed details such as /product/details/en"
        )

    legacy_detail_fields = {"name", "productID", "visibility", "status", "type"}
    legacy_fields = sorted(legacy_detail_fields.intersection(product))
    if legacy_fields:
        errors.append(
            "/product: move legacy flat detail fields into "
            f"/product/details/<language>: {', '.join(legacy_fields)}"
        )

    pricing_plans = product.get("pricingPlans")
    if isinstance(pricing_plans, dict) and "plans" in pricing_plans:
        errors.append(
            "/product/pricingPlans: ODPS v4.1 pricing plans must use "
            "declarative or executable, not plans"
        )

    if "dataContract" in product:
        errors.append("/product/dataContract: ODPS v4.1 uses /product/contract")

    return errors


def _raw_mapping(
    document: Union[Document, str, Path],
    path: Optional[Union[str, Path]],
) -> Optional[Dict[str, Any]]:
    if isinstance(document, (str, Path)):
        return _load_mapping(Path(document))
    if isinstance(document, dict):
        return document
    if path is not None:
        return _load_mapping(Path(path))
    return None


def _format_schema_error(error: Any) -> str:
    path = "/".join(str(part) for part in error.absolute_path)
    pointer = f"/{path}" if path else "/"
    if error.validator == "required":
        missing = ", ".join(str(item) for item in error.validator_value)
        return f"{pointer}: required fields missing or invalid; expected {missing}"
    return f"{pointer}: {error.message}"


def _walk_references(value: Any, pointer: str = "") -> Iterable[Tuple[str, str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            child_pointer = f"{pointer}/{escaped}" if pointer else f"/{escaped}"
            if key in {"$ref", "ref", "schema"} and isinstance(item, str):
                yield child_pointer, key, item
            yield from _walk_references(item, child_pointer)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_pointer = f"{pointer}/{index}" if pointer else f"/{index}"
            yield from _walk_references(item, child_pointer)


def _reference_type(pointer: str, key: str) -> str:
    if key == "schema":
        return "schema"
    if "/nodes/" in pointer:
        return "node"
    if "/edges/" in pointer:
        return "edge"
    if "graph" in pointer.lower():
        return "graph"
    return "reference"


def _infer_target_spec(ref: str) -> Optional[str]:
    lowered = ref.lower()
    for spec in ("odps", "odpc", "odpg", "odpv"):
        if spec in lowered:
            return spec
    return None


def _path_str(path: Optional[Union[str, Path]]) -> Optional[str]:
    return str(path) if path is not None else None
