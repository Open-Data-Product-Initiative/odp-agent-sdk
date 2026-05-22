"""Static ODPS-to-Data Contract alignment checks."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .._io import load_mapping
from ..agent import validate_document
from .datacontract_cli_adapter import validate_contract
from .loader import (
    extract_contract_schema,
    extract_contract_schema_from_document,
    summarize_contract,
    summarize_contract_document,
)
from .models import (
    AlignmentFinding,
    ContractSchemaField,
    ContractSchemaModel,
    ProductContractAlignmentResult,
)

ProductInput = Union[str, Path, Dict[str, object]]
ContractInput = Union[str, Path, Dict[str, object]]


def check_product_contract_alignment(
    product_path_or_document: ProductInput,
    contract_path_or_url: ContractInput,
    *,
    run_contract_tests: bool = False,
) -> ProductContractAlignmentResult:
    """Check static alignment between an ODPS product and a Data Contract."""
    product_validation = validate_document(product_path_or_document)
    contract_valid = True
    if isinstance(contract_path_or_url, (str, Path)):
        contract_validation = validate_contract(str(contract_path_or_url))
        contract_valid = contract_validation.passed
    product_document = _load_product_mapping(product_path_or_document)
    findings: List[AlignmentFinding] = []

    _check_product_name_alignment(product_document, contract_path_or_url, findings)
    _check_schema_alignment(product_document, contract_path_or_url, findings)

    if run_contract_tests:
        findings.append(
            AlignmentFinding(
                code="LIVE_TESTS_NOT_IMPLEMENTED",
                message="Live Data Contract tests are not implemented yet.",
                severity="warning",
                recommendation="Run datacontract-cli directly for live source tests.",
            )
        )

    passed = (
        product_validation.valid
        and contract_valid
        and not _has_blocking_findings(findings)
    )
    return ProductContractAlignmentResult(
        passed=passed,
        product_valid=product_validation.valid,
        contract_valid=contract_valid,
        contract_tests_run=False,
        findings=findings,
        summary=_alignment_summary(product_validation.valid, contract_valid, findings),
    )


def _check_product_name_alignment(
    product_document: Dict[str, object],
    contract_path_or_url: ContractInput,
    findings: List[AlignmentFinding],
) -> None:
    product_name = _product_name(product_document)
    contract_name = _contract_name(contract_path_or_url)
    if product_name is None or contract_name is None:
        return
    if not _names_compatible(product_name, contract_name):
        findings.append(
            AlignmentFinding(
                code="PRODUCT_NAME_MISMATCH",
                message=(
                    f"ODPS product name '{product_name}' differs from Data "
                    f"Contract name '{contract_name}'."
                ),
                severity="warning",
                odps_path="/product/name",
                contract_path="/name",
                recommendation="Confirm whether both documents describe the same product.",
            )
        )


def _check_schema_alignment(
    product_document: Dict[str, object],
    contract_path_or_url: ContractInput,
    findings: List[AlignmentFinding],
) -> None:
    product_models = _product_schema_models(product_document)
    try:
        if isinstance(contract_path_or_url, dict):
            contract_schema = extract_contract_schema_from_document(contract_path_or_url)
        else:
            contract_schema = extract_contract_schema(str(contract_path_or_url))
    except Exception as exc:
        findings.append(
            AlignmentFinding(
                code="CONTRACT_SCHEMA_EXTRACTION_FAILED",
                message=f"Could not extract Data Contract schema: {exc}",
                severity="warning",
                recommendation="Use a local YAML or JSON contract for static alignment.",
            )
        )
        return

    if not product_models:
        findings.append(
            AlignmentFinding(
                code="ODPS_SCHEMA_NOT_FOUND",
                message="No ODPS dataset schema fields were found for comparison.",
                severity="info",
                recommendation="Add dataset fields to ODPS metadata for schema alignment.",
            )
        )
        return
    if not contract_schema.models:
        findings.append(
            AlignmentFinding(
                code="CONTRACT_SCHEMA_EMPTY",
                message="No Data Contract schema models were found for comparison.",
                severity="warning",
                recommendation="Add models and fields to the Data Contract.",
            )
        )
        return

    product_fields = _flatten_product_fields(product_models)
    contract_fields = _flatten_contract_fields(contract_schema.models)
    _compare_field_sets(product_fields, contract_fields, findings)


def _compare_field_sets(
    product_fields: Dict[str, Tuple[str, Optional[str]]],
    contract_fields: Dict[str, Tuple[ContractSchemaField, str]],
    findings: List[AlignmentFinding],
) -> None:
    product_names = set(product_fields)
    contract_names = set(contract_fields)
    for name in sorted(contract_names - product_names):
        field, model_name = contract_fields[name]
        findings.append(
            AlignmentFinding(
                code=(
                    "REQUIRED_FIELD_MISSING_IN_ODPS"
                    if field.required
                    else "SCHEMA_FIELD_MISSING_IN_ODPS"
                ),
                message=(
                    f"Data Contract field '{model_name}.{field.name}' is missing "
                    "from ODPS dataset schema metadata."
                ),
                severity="error" if field.required else "warning",
                contract_path=f"/models/{model_name}/fields/{field.name}",
                recommendation="Add the field to ODPS metadata or confirm it is contract-only.",
            )
        )
    for name in sorted(product_names - contract_names):
        model_name, _field_type = product_fields[name]
        findings.append(
            AlignmentFinding(
                code="SCHEMA_FIELD_MISSING_IN_CONTRACT",
                message=(
                    f"ODPS field '{model_name}.{name}' is missing from the "
                    "Data Contract."
                ),
                severity="warning",
                odps_path=f"/product/datasets/{model_name}/fields/{name}",
                recommendation="Add the field to the Data Contract or remove stale ODPS metadata.",
            )
        )
    for name in sorted(product_names & contract_names):
        product_model, product_type = product_fields[name]
        contract_field, contract_model = contract_fields[name]
        if not _types_compatible(product_type, contract_field.type):
            findings.append(
                AlignmentFinding(
                    code="SCHEMA_FIELD_TYPE_MISMATCH",
                    message=(
                        f"Field '{name}' has ODPS type '{product_type}' but "
                        f"Data Contract type '{contract_field.type}'."
                    ),
                    severity="warning",
                    odps_path=f"/product/datasets/{product_model}/fields/{name}",
                    contract_path=f"/models/{contract_model}/fields/{name}",
                    recommendation="Align field types or document the conversion.",
                )
            )


def _product_schema_models(document: Dict[str, object]) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    product = _mapping(document.get("product"))
    candidates = [
        product.get("datasets"),
        document.get("datasets"),
        product.get("dataSets"),
        document.get("dataSets"),
    ]
    for candidate in candidates:
        models = _models_from_candidate(candidate)
        if models:
            return models
    schema_candidate = product.get("schema") or product.get("dataSchema")
    return _models_from_candidate(schema_candidate)


def _models_from_candidate(value: object) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    if isinstance(value, dict):
        if "fields" in value or "columns" in value:
            name = _optional_str(value.get("name")) or "default"
            return {name: _fields_from_value(value.get("fields") or value.get("columns"))}
        models = {}
        for name, item in value.items():
            if isinstance(item, dict):
                fields = _fields_from_value(item.get("fields") or item.get("columns"))
                if fields:
                    models[str(name)] = fields
        return models
    if isinstance(value, list):
        models = {}
        for index, item in enumerate(value):
            if isinstance(item, dict):
                name = _optional_str(item.get("name")) or f"dataset_{index + 1}"
                fields = _fields_from_value(item.get("fields") or item.get("columns"))
                if fields:
                    models[name] = fields
        return models
    return {}


def _fields_from_value(value: object) -> List[Tuple[str, Optional[str]]]:
    if isinstance(value, dict):
        return [
            (str(name), _field_type(field))
            for name, field in value.items()
            if isinstance(field, dict)
        ]
    if isinstance(value, list):
        fields = []
        for index, field in enumerate(value):
            if isinstance(field, dict):
                name = _optional_str(field.get("name")) or f"field_{index + 1}"
                fields.append((name, _field_type(field)))
        return fields
    return []


def _flatten_product_fields(
    models: Dict[str, List[Tuple[str, Optional[str]]]],
) -> Dict[str, Tuple[str, Optional[str]]]:
    flattened = {}
    for model_name, fields in models.items():
        for field_name, field_type in fields:
            flattened[_normal_key(field_name)] = (model_name, field_type)
    return flattened


def _flatten_contract_fields(
    models: List[ContractSchemaModel],
) -> Dict[str, Tuple[ContractSchemaField, str]]:
    flattened = {}
    for model in models:
        for field in model.fields:
            flattened[_normal_key(field.name)] = (field, model.name)
    return flattened


def _field_type(field: Dict[str, object]) -> Optional[str]:
    return _optional_str(field.get("type") or field.get("dataType"))


def _load_product_mapping(product_path_or_document: ProductInput) -> Dict[str, object]:
    if isinstance(product_path_or_document, dict):
        return product_path_or_document
    return load_mapping(Path(product_path_or_document))


def _product_name(document: Dict[str, object]) -> Optional[str]:
    product = _mapping(document.get("product"))
    details = _mapping(product.get("details"))
    localized = _first_mapping_value(details)
    if localized:
        return _optional_str(localized.get("name"))
    return _optional_str(product.get("name"))


def _contract_name(contract_path_or_url: ContractInput) -> Optional[str]:
    if isinstance(contract_path_or_url, dict):
        return summarize_contract_document(contract_path_or_url).name
    contract_path = str(contract_path_or_url)
    if "://" in contract_path or not Path(contract_path).exists():
        return None
    try:
        return summarize_contract(contract_path).name
    except Exception:
        return None


def _names_compatible(left: str, right: str) -> bool:
    left_key = _normal_key(left)
    right_key = _normal_key(right)
    return left_key == right_key or left_key in right_key or right_key in left_key


def _types_compatible(left: Optional[str], right: Optional[str]) -> bool:
    if left is None or right is None:
        return True
    aliases = {
        "str": "string",
        "varchar": "string",
        "text": "string",
        "int": "integer",
        "integer": "integer",
        "long": "integer",
        "float": "number",
        "double": "number",
        "decimal": "number",
        "numeric": "number",
        "bool": "boolean",
    }
    return aliases.get(left.lower(), left.lower()) == aliases.get(
        right.lower(), right.lower()
    )


def _has_blocking_findings(findings: List[AlignmentFinding]) -> bool:
    return any(finding.severity in {"error", "critical"} for finding in findings)


def _alignment_summary(
    product_valid: bool,
    contract_valid: bool,
    findings: List[AlignmentFinding],
) -> str:
    product_state = "valid" if product_valid else "invalid"
    contract_state = "valid" if contract_valid else "invalid"
    blocking = len(
        [finding for finding in findings if finding.severity in {"error", "critical"}]
    )
    return (
        f"Product {product_state}; Data Contract {contract_state}; "
        f"{len(findings)} alignment finding(s), {blocking} blocking."
    )


def _mapping(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {}


def _first_mapping_value(value: Dict[str, object]) -> Optional[Dict[str, object]]:
    for item in value.values():
        if isinstance(item, dict):
            return item
    return None


def _normal_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None
