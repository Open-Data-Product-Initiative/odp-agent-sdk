"""Load and summarize external Data Contract documents."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .._io import load_mapping
from .models import (
    ContractDocument,
    ContractSchemaField,
    ContractSchemaModel,
    ContractSchemaSummary,
    ContractSummary,
    Finding,
)


def load_contract(path_or_url: str) -> ContractDocument:
    """Load a local Data Contract YAML or JSON document."""
    path = Path(path_or_url)
    if "://" in path_or_url:
        raise ValueError("Remote Data Contract URLs are not loaded by the SDK yet")
    document = load_mapping(path, root_name="Data Contract")
    return ContractDocument(
        path=str(path),
        document=document,
        contract_format=_infer_contract_format(path_or_url),
    )


def summarize_contract(path_or_url: str) -> ContractSummary:
    """Return a compact Data Contract summary."""
    contract = load_contract(path_or_url)
    return summarize_contract_document(
        contract.document,
        path=contract.path,
        contract_format=contract.contract_format,
    )


def summarize_contract_document(
    document: Dict[str, object],
    *,
    path: str = "(inline)",
    contract_format: Optional[str] = None,
) -> ContractSummary:
    """Return a compact summary for an already-loaded Data Contract."""
    models = _mapping_values(document.get("models"))
    return ContractSummary(
        path=path,
        contract_format=contract_format,
        contract_id=_optional_str(
            document.get("id")
            or document.get("contractId")
            or _mapping(document.get("info")).get("id")
        ),
        name=_optional_str(
            document.get("name")
            or _mapping(document.get("info")).get("title")
            or _mapping(document.get("info")).get("name")
        ),
        version=_optional_str(
            document.get("version")
            or _mapping(document.get("info")).get("version")
        ),
        model_count=len(models),
        field_count=sum(_field_count(model) for model in models),
        server_count=len(_mapping_values(document.get("servers"))),
    )


def explain_contract(path_or_url: str) -> str:
    """Render a compact Data Contract summary."""
    summary = summarize_contract(path_or_url)
    return (
        f"File: {summary.path}\n"
        f"Format: {summary.contract_format or '(unknown)'}\n"
        f"Contract id: {summary.contract_id or '(missing)'}\n"
        f"Name: {summary.name or '(missing)'}\n"
        f"Version: {summary.version or '(missing)'}\n"
        f"Models: {summary.model_count}\n"
        f"Fields: {summary.field_count}\n"
        f"Servers: {summary.server_count}\n"
    )


def extract_contract_schema(path_or_url: str) -> ContractSchemaSummary:
    """Extract a normalized schema summary from a local Data Contract."""
    contract = load_contract(path_or_url)
    return extract_contract_schema_from_document(
        contract.document,
        path=contract.path,
        contract_format=contract.contract_format,
    )


def extract_contract_schema_from_document(
    document: Dict[str, object],
    *,
    path: str = "(inline)",
    contract_format: Optional[str] = None,
) -> ContractSchemaSummary:
    """Extract a normalized schema summary from an already-loaded contract."""
    models = _schema_models(document.get("models"))
    findings = []
    if not models:
        findings.append(
            Finding(
                code="CONTRACT_SCHEMA_EMPTY",
                message="No schema models were found in the Data Contract.",
                severity="warning",
                source="open-data-products",
            )
        )
    return ContractSchemaSummary(
        path=path,
        contract_format=contract_format,
        models=models,
        findings=findings,
    )


def _mapping(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {}


def _mapping_values(value: object) -> List[Dict[str, object]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _field_count(model: Dict[str, object]) -> int:
    fields = model.get("fields") or model.get("columns")
    return len(list(_field_items(fields)))


def _field_items(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        return value.values()
    if isinstance(value, list):
        return value
    return []


def _schema_models(value: object) -> List[ContractSchemaModel]:
    if isinstance(value, dict):
        return [
            _schema_model(str(name), model)
            for name, model in value.items()
            if isinstance(model, dict)
        ]
    if isinstance(value, list):
        return [
            _schema_model(_model_name(model, index), model)
            for index, model in enumerate(value)
            if isinstance(model, dict)
        ]
    return []


def _schema_model(name: str, model: Dict[str, object]) -> ContractSchemaModel:
    return ContractSchemaModel(
        name=_optional_str(model.get("name")) or name,
        description=_optional_str(model.get("description")),
        fields=_schema_fields(model.get("fields") or model.get("columns")),
    )


def _schema_fields(value: object) -> List[ContractSchemaField]:
    if isinstance(value, dict):
        return [
            _schema_field(str(name), field)
            for name, field in value.items()
            if isinstance(field, dict)
        ]
    if isinstance(value, list):
        return [
            _schema_field(_field_name(field, index), field)
            for index, field in enumerate(value)
            if isinstance(field, dict)
        ]
    return []


def _schema_field(name: str, field: Dict[str, object]) -> ContractSchemaField:
    return ContractSchemaField(
        name=_optional_str(field.get("name")) or name,
        type=_optional_str(field.get("type") or field.get("dataType")),
        required=_field_required(field),
        description=_optional_str(field.get("description")),
    )


def _field_required(field: Dict[str, object]) -> bool:
    required = field.get("required")
    if isinstance(required, bool):
        return required
    nullable = field.get("nullable")
    if isinstance(nullable, bool):
        return not nullable
    return False


def _model_name(model: Dict[str, object], index: int) -> str:
    return _optional_str(model.get("name")) or f"model_{index + 1}"


def _field_name(field: Dict[str, object], index: int) -> str:
    return _optional_str(field.get("name")) or f"field_{index + 1}"


def _infer_contract_format(path_or_url: str) -> Optional[str]:
    suffix = Path(path_or_url).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    return None


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None
