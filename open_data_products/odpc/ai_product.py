"""ODPC v1.1 AI-product profile loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

from jsonschema import Draft202012Validator, FormatChecker

from open_data_products._io import load_mapping

from .catalog import CatalogValidationResult, NoDatesSafeLoader, validate_catalog

AI_PRODUCT_SCHEMA_URL = "https://opendataproducts.org/odpc-v1.1/schema/ai-product.yaml"


def _data_file(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath("data", *parts)


def load_ai_product(path: Union[str, Path]) -> Dict[str, Any]:
    """Load an ODPC v1.1 AI-product profile from JSON or YAML."""
    return load_mapping(
        Path(path),
        yaml_loader=NoDatesSafeLoader,
        root_name="ODPC AI product",
    )


def load_ai_product_schema() -> Dict[str, Any]:
    """Load the bundled ODPC v1.1 AI-product profile schema."""
    return load_mapping(
        _data_file("schema", "v1.1", "ai-product.yaml"),
        root_name="ODPC v1.1 AI-product schema",
    )


def validate_ai_product(document: Dict[str, Any]) -> CatalogValidationResult:
    """Validate an ODPC v1.1 AI-product profile."""
    schema = load_ai_product_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    messages = []
    for error in errors:
        location = "$." + ".".join(map(str, error.path)) if error.path else "$"
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = next(
                (
                    field
                    for field in error.validator_value
                    if field not in error.instance
                ),
                None,
            )
            if missing:
                location = f"{location}.{missing}"
        messages.append(f"{location}: {error.message}")
    return CatalogValidationResult(valid=not messages, errors=messages)


ODPC_V11_CATALOG_SCHEMA_URL = "https://opendataproducts.org/odpc-v1.1/schema/odpc.yaml"


def _profile_error_prefix(errors: List[str], prefix: str) -> List[str]:
    return [f"{prefix}: {error}" for error in errors]


def validate_ai_product_bundle(
    profile: Dict[str, Any],
    catalog: Dict[str, Any],
    graph: Dict[str, Any],
) -> CatalogValidationResult:
    """Validate a profile, catalog, and graph as one ODPC AI-product bundle."""
    from open_data_products.odpg import validate_graph

    errors = _profile_error_prefix(validate_ai_product(profile).errors, "profile")
    errors.extend(_profile_error_prefix(validate_catalog(catalog).errors, "catalog"))
    graph_result = validate_graph(graph)
    errors.extend(_profile_error_prefix(graph_result.errors, "graph"))
    if errors:
        return CatalogValidationResult(valid=False, errors=errors)

    product = profile["aiProduct"]
    nodes = catalog["catalog"]["nodes"]
    inline = next(
        (entry["node"] for entry in nodes if entry["node"].get("kind") == "aiProduct"),
        None,
    )
    reference = next(
        (
            entry["node"]
            for entry in nodes
            if entry["node"].get("kind") == "productReference"
        ),
        None,
    )
    graph_node = next(
        (node for node in graph["graph"]["nodes"] if node.get("type") == "AIProduct"),
        None,
    )
    if inline is None:
        errors.append("catalog: missing aiProduct node")
    if reference is None:
        errors.append("catalog: missing AI-product productReference")
    if graph_node is None:
        errors.append("graph: missing AIProduct node")
    if errors:
        return CatalogValidationResult(valid=False, errors=errors)

    for field in ("productID", "productVersion"):
        values = (product[field], inline[field], reference[field])
        if len(set(values)) != 1:
            errors.append(
                f"bundle.{field}: profile, inline node, and product reference must match"
            )
    model = reference["productModel"]
    if (model["standard"], model["version"], model["profile"]) != (
        "ODPC",
        "1.1",
        "AIProduct",
    ):
        errors.append("bundle.productModel: reference must declare ODPC 1.1 AIProduct")
    if graph_node["$ref"] != model["$ref"]:
        errors.append(
            "bundle.$ref: graph and product reference must target the same profile"
        )
    return CatalogValidationResult(valid=not errors, errors=errors)
