"""ODPR document validation helpers."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import json
import re
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

import yaml
from jsonschema import Draft202012Validator

PathLike = Union[str, Path]
ODPR_SCHEMA_URI = "https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml"
DEFAULT_ODPR_SCHEMA = Path(__file__).resolve().parent / "data" / "schema" / "odpr.yaml"
ROOT_KINDS = {"Recipe", "Provider", "RecipeCatalog"}
RUNTIME_KINDS = {"RecipeRunPlan", "RecipeRunManifest", "RecipeInspection"}
SECRET_KEY_MARKERS = (
    "apikey",
    "secret",
    "token",
    "password",
    "authorization",
    "bearer",
    "privatekey",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
)


def load_odpr_data(path: PathLike) -> Mapping[str, object]:
    """Load an ODPR YAML or JSON document."""
    document_path = Path(path)
    if not document_path.is_file():
        raise FileNotFoundError(f"ODPR document not found: {document_path}")
    text = document_path.read_text(encoding="utf-8")
    if document_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("ODPR document must be a YAML or JSON mapping.")
    return data


@lru_cache(maxsize=1)
def load_odpr_schema() -> Mapping[str, object]:
    """Load the bundled ODPR JSON Schema."""
    return load_odpr_data(DEFAULT_ODPR_SCHEMA)


def validate_odpr_document(path: PathLike) -> Dict[str, object]:
    """Validate an ODPR Recipe, Provider, or RecipeCatalog document."""
    document_path = Path(path)
    errors: List[str] = []
    warnings: List[str] = []
    data: Mapping[str, object] = {}
    try:
        data = load_odpr_data(document_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        errors.append(str(exc))

    if data:
        errors.extend(_schema_errors(data))
        _validate_root(data, errors)
        for location, reason in find_embedded_secrets(data):
            errors.append(
                f"{location}: embedded secret or API key is not allowed ({reason})"
            )
        kind = data.get("kind")
        if kind == "Recipe":
            _validate_recipe_root(data, errors)
        elif kind == "Provider":
            _validate_provider_root(data, errors)
        elif kind == "RecipeCatalog":
            _validate_catalog_root(data, errors)

    return {
        "mode": "validate",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "schemaValidation": "draft-2020-12",
        "kind": data.get("kind") if data else None,
        "path": str(document_path),
    }


def _schema_errors(data: Mapping[str, object]) -> List[str]:
    validator = Draft202012Validator(load_odpr_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    formatted = []
    for error in errors:
        location = _format_path(list(error.path))
        if location:
            formatted.append(f"{location}: {error.message}")
        else:
            formatted.append(error.message)
    return formatted


def find_embedded_secrets(
    value: object,
    path: Optional[Sequence[object]] = None,
) -> List[Tuple[str, str]]:
    """Return locations that look like raw embedded secrets."""
    current_path = list(path or [])
    findings: List[Tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = current_path + [key]
            if _is_secret_key(key):
                findings.append((_format_path(child_path), "secret-like field name"))
            findings.extend(find_embedded_secrets(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_embedded_secrets(child, current_path + [index]))
    elif _contains_secret_value(value):
        findings.append((_format_path(current_path), "secret-like value"))
    return findings


def _validate_root(data: Mapping[str, object], errors: List[str]) -> None:
    schema = data.get("schema")
    if schema != ODPR_SCHEMA_URI:
        errors.append(f"schema must be {ODPR_SCHEMA_URI}")
    if data.get("version") != "1.0":
        errors.append("version must be 1.0")
    kind = data.get("kind")
    if kind in RUNTIME_KINDS:
        errors.append(f"{kind} is not an ODPR v1 root kind")
    elif kind not in ROOT_KINDS:
        errors.append("kind must be one of Recipe, Provider, or RecipeCatalog")


def _validate_recipe_root(data: Mapping[str, object], errors: List[str]) -> None:
    recipe = _mapping(data.get("recipe"))
    if not recipe:
        errors.append("recipe must be a mapping")
        return
    metadata = _mapping(recipe.get("metadata"))
    _require_string(metadata, "id", "recipe.metadata.id", errors)
    if "name" not in metadata:
        errors.append("recipe.metadata.name is required")
    _require_string(recipe, "version", "recipe.version", errors)
    _require_string(recipe, "type", "recipe.type", errors)
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("recipe.steps must contain at least one step")


def _validate_provider_root(data: Mapping[str, object], errors: List[str]) -> None:
    provider = _mapping(data.get("provider"))
    if not provider:
        errors.append("provider must be a mapping")
        return
    _require_string(provider, "id", "provider.id", errors)
    _require_string(provider, "provider", "provider.provider", errors)


def _validate_catalog_root(data: Mapping[str, object], errors: List[str]) -> None:
    catalog = _mapping(data.get("recipeCatalog"))
    if not catalog:
        errors.append("recipeCatalog must be a mapping")
        return
    metadata = _mapping(catalog.get("metadata"))
    _require_string(metadata, "id", "recipeCatalog.metadata.id", errors)
    if "name" not in metadata:
        errors.append("recipeCatalog.metadata.name is required")
    _require_string(catalog, "version", "recipeCatalog.version", errors)
    group_ids = _catalog_group_ids(catalog.get("groups"), errors)
    recipes = catalog.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        errors.append("recipeCatalog.recipes must contain at least one entry")
        return
    recipe_ids: Set[str] = set()
    forbidden = {"steps", "status", "runId", "logs", "plannedWrites"}
    for index, entry in enumerate(recipes):
        if not isinstance(entry, dict):
            errors.append(f"recipeCatalog.recipes[{index}] must be a mapping")
            continue
        for key in sorted(forbidden.intersection(entry)):
            errors.append(f"recipeCatalog.recipes[{index}].{key} must not be included")
        for required in ("path", "id", "version", "type", "name"):
            if required not in entry:
                errors.append(f"recipeCatalog.recipes[{index}].{required} is required")
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            if entry_id in recipe_ids:
                errors.append(f"recipeCatalog.recipes[{index}].id must be unique")
            recipe_ids.add(entry_id)
        group_ref = entry.get("groupRef")
        if isinstance(group_ref, str) and group_ref not in group_ids:
            errors.append(
                f"recipeCatalog.recipes[{index}].groupRef must match a declared group"
            )


def _catalog_group_ids(value: object, errors: List[str]) -> Set[str]:
    if value is None:
        return set()
    if not isinstance(value, list):
        errors.append("recipeCatalog.groups must be an array")
        return set()
    group_ids: Set[str] = set()
    for index, group in enumerate(value):
        if not isinstance(group, dict):
            errors.append(f"recipeCatalog.groups[{index}] must be a mapping")
            continue
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id.strip():
            errors.append(f"recipeCatalog.groups[{index}].id is required")
            continue
        if group_id in group_ids:
            errors.append(f"recipeCatalog.groups[{index}].id must be unique")
        group_ids.add(group_id)
        if "name" not in group:
            errors.append(f"recipeCatalog.groups[{index}].name is required")
    return group_ids


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _require_string(
    value: Mapping[str, object],
    key: str,
    label: str,
    errors: List[str],
) -> None:
    if not isinstance(value.get(key), str) or not str(value.get(key)).strip():
        errors.append(f"{label} is required")


def _is_secret_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if normalized.endswith("ref"):
        return False
    return any(marker in normalized for marker in SECRET_KEY_MARKERS)


def _contains_secret_value(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def _format_path(parts: Sequence[object]) -> str:
    if not parts:
        return ""
    formatted = str(parts[0])
    for part in parts[1:]:
        if isinstance(part, int):
            formatted += f"[{part}]"
        else:
            formatted += f".{part}"
    return formatted
