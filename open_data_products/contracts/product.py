"""Product-level orchestration for external Data Contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .._io import load_mapping
from ..agent import validate_document
from .alignment import check_product_contract_alignment
from .datacontract_cli_adapter import validate_contract
from .loader import summarize_contract, summarize_contract_document
from .models import (
    ProductContractAlignmentResult,
    ContractReference,
    ContractSummary,
    ContractValidationResult,
    Finding,
    ProductContractReport,
)

ProductInput = Union[str, Path, Dict[str, object]]


def resolve_product_contracts(
    product_path_or_document: ProductInput,
) -> List[ContractReference]:
    """Resolve conventional Data Contract references from an ODP product."""
    document = _load_product_mapping(product_path_or_document)
    references = [
        reference
        for pointer, value in _walk(document)
        for reference in _reference_from_value(pointer, value)
    ]
    return _dedupe_references(references)


def generate_product_contract_report(
    product_path_or_document: ProductInput,
    contract_path: Optional[str] = None,
) -> ProductContractReport:
    """Validate an ODP product and its external Data Contract references."""
    product_validation = validate_document(product_path_or_document)
    references = resolve_product_contracts(product_path_or_document)
    if contract_path is not None:
        references = [
            ContractReference(
                href=contract_path,
                pointer="(argument)",
                format=_infer_contract_format(contract_path),
            )
        ]

    findings: List[Finding] = []
    validations: List[ContractValidationResult] = []
    summaries: List[ContractSummary] = []
    alignments: List[ProductContractAlignmentResult] = []
    if not references:
        findings.append(
            Finding(
                code="CONTRACT_REFERENCE_MISSING",
                message="No Data Contract reference was found for this product.",
                severity="warning",
                source="open-data-products",
            )
        )

    for reference in references:
        contract_input = _contract_input(product_path_or_document, reference)
        validations.append(_validate_reference_contract(reference, contract_input))
        summary = _summarize_reference_contract(reference, contract_input)
        if summary is not None:
            summaries.append(summary)
        alignments.append(
            check_product_contract_alignment(product_path_or_document, contract_input)
        )

    contract_valid = bool(validations) and all(
        validation.passed for validation in validations
    )
    alignment_passed = all(alignment.passed for alignment in alignments)
    passed = product_validation.valid and contract_valid and alignment_passed
    findings.extend(_contract_validation_findings(validations))
    return ProductContractReport(
        passed=passed,
        product_valid=product_validation.valid,
        contract_count=len(references),
        contract_valid=contract_valid,
        contract_tests_run=False,
        references=references,
        validations=validations,
        summaries=summaries,
        alignments=alignments,
        findings=findings,
        summary=_report_summary(product_validation.valid, len(references), contract_valid),
    )


def _load_product_mapping(product_path_or_document: ProductInput) -> Dict[str, object]:
    if isinstance(product_path_or_document, dict):
        return product_path_or_document
    return load_mapping(Path(product_path_or_document))


def _walk(value: object, pointer: str = "") -> Iterable[Tuple[str, object]]:
    yield pointer or "/", value
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            child_pointer = f"{pointer}/{escaped}" if pointer else f"/{escaped}"
            yield from _walk(item, child_pointer)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_pointer = f"{pointer}/{index}" if pointer else f"/{index}"
            yield from _walk(item, child_pointer)


def _reference_from_value(pointer: str, value: object) -> List[ContractReference]:
    if not isinstance(value, dict):
        return []
    pointer_key = pointer.lower()
    if "datacontract" not in pointer_key and "contract" not in pointer_key:
        return []
    references = []
    href = (
        value.get("href")
        or value.get("url")
        or value.get("path")
        or value.get("ref")
        or value.get("$ref")
        or value.get("contractURL")
        or value.get("contractUrl")
    )
    if href is not None:
        references.append(
            ContractReference(
                href=str(href),
                pointer=pointer,
                format=_optional_str(value.get("format") or value.get("type")),
            )
        )
    spec = value.get("spec")
    if isinstance(spec, dict):
        references.append(
            ContractReference(
                href=f"(inline:{pointer}/spec)",
                pointer=f"{pointer}/spec",
                format=_optional_str(value.get("format") or value.get("type")),
                inline_spec=spec,
            )
        )
    return references


def _dedupe_references(references: List[ContractReference]) -> List[ContractReference]:
    seen = set()
    unique = []
    for reference in references:
        key = (reference.href, reference.pointer)
        if key not in seen:
            unique.append(reference)
            seen.add(key)
    return unique


def _summarize_if_local(path_or_url: str) -> Optional[ContractSummary]:
    if "://" in path_or_url or not Path(path_or_url).exists():
        return None
    try:
        return summarize_contract(path_or_url)
    except Exception:
        return None


def _contract_input(
    product_path_or_document: ProductInput,
    reference: ContractReference,
) -> Union[str, Dict[str, object]]:
    if reference.inline_spec is not None:
        return reference.inline_spec
    return _resolve_contract_href(product_path_or_document, reference.href)


def _validate_reference_contract(
    reference: ContractReference,
    contract_input: Union[str, Dict[str, object]],
) -> ContractValidationResult:
    if isinstance(contract_input, dict):
        return ContractValidationResult(
            passed=True,
            tool="open-data-products",
            contract_format=reference.format,
            findings=[
                Finding(
                    code="INLINE_CONTRACT_STATIC_ONLY",
                    message=(
                        "Inline ODPS contract spec was used for static SDK checks; "
                        "datacontract-cli lint was not run."
                    ),
                    severity="info",
                    source="open-data-products",
                )
            ],
        )
    return validate_contract(contract_input)


def _summarize_reference_contract(
    reference: ContractReference,
    contract_input: Union[str, Dict[str, object]],
) -> Optional[ContractSummary]:
    if isinstance(contract_input, dict):
        return summarize_contract_document(
            contract_input,
            path=reference.href,
            contract_format=reference.format,
        )
    return _summarize_if_local(contract_input)


def _resolve_contract_href(
    product_path_or_document: ProductInput,
    href: str,
) -> str:
    if "://" in href or Path(href).is_absolute():
        return href
    if isinstance(product_path_or_document, (str, Path)):
        return str(Path(product_path_or_document).parent / href)
    return href


def _contract_validation_findings(
    validations: List[ContractValidationResult],
) -> List[Finding]:
    findings = []
    for validation in validations:
        if not validation.passed:
            findings.extend(validation.findings)
    return findings


def _report_summary(
    product_valid: bool,
    contract_count: int,
    contract_valid: bool,
) -> str:
    product_state = "valid" if product_valid else "invalid"
    if contract_count == 0:
        return f"Product {product_state}; no Data Contract references found."
    contract_state = "valid" if contract_valid else "invalid"
    return (
        f"Product {product_state}; {contract_count} Data Contract reference(s); "
        f"contracts {contract_state}; live tests not run."
    )


def _infer_contract_format(path_or_url: str) -> Optional[str]:
    suffix = Path(path_or_url).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    return None


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None
