"""ODPC v1.1 AI-product profile loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

from jsonschema import Draft202012Validator, FormatChecker

from open_data_products._io import load_mapping

from .catalog import CatalogValidationResult, NoDatesSafeLoader


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
                (field for field in error.validator_value if field not in error.instance),
                None,
            )
            if missing:
                location = f"{location}.{missing}"
        messages.append(f"{location}: {error.message}")
    return CatalogValidationResult(valid=not messages, errors=messages)

