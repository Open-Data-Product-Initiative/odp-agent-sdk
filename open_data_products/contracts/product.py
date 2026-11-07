"""Product-level orchestration for external Data Contracts."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import unquote, urlparse, urlunparse

import yaml

from .._io import load_mapping
from ..agent import validate_document
from .alignment import check_product_contract_alignment
from .datacontract_cli_adapter import validate_contract
from .loader import load_contract, summarize_contract, summarize_contract_document
from .models import (
    ContractMappedField,
    ProductContractAlignmentResult,
    ContractReference,
    ContractSummary,
    ContractValidationResult,
    ContractWrapProposal,
    ContractWrapResult,
    Finding,
    ProductContractReport,
)

ProductInput = Union[str, Path, Dict[str, object]]

_ODPS_V42_SCHEMA = "https://opendataproducts.org/v4.2/schema/odps.json"
_SUPPORTED_ODCS_VERSIONS = {"3.0", "3.1", "3.2"}
_SERVER_OUTPUT_PORT_TYPES = {
    "http": "API",
    "https": "API",
    "api": "API",
    "rest": "API",
    "sql": "SQL",
    "grpc": "gRPC",
    "sftp": "sFTP",
}
_ACCESS_URI_SCHEMES = {
    "API": {"http", "https"},
    "SQL": {
        "bigquery",
        "jdbc",
        "mssql",
        "mysql",
        "postgres",
        "postgresql",
        "snowflake",
    },
    "gRPC": {"grpc", "grpcs"},
    "sFTP": {"sftp"},
}
_CREDENTIAL_QUERY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "jwt",
)
_ODPS_FORMATS = {
    "TOON",
    "JSON",
    "XML",
    "CSV",
    "Excel",
    "zip",
    "plain text",
    "GraphQL",
    "MCP",
}


def wrap_contract(
    source: str,
    output: Optional[str] = None,
    *,
    inline_contract: bool = False,
    use_ai: bool = False,
    extend: bool = False,
    contract_url: Optional[str] = None,
    product_name: Optional[str] = None,
    product_id: Optional[str] = None,
    product_type: Optional[str] = None,
    language: Optional[str] = None,
    config: Optional[str] = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> ContractWrapResult:
    """Wrap an ODCS document as a conservative ODPS 4.2 draft."""
    if extend and not use_ai:
        raise ValueError("extend=True requires use_ai=True")
    contract = load_contract(source)
    metadata = _odcs_metadata(contract.document)
    resolved_uri = contract.resolved_uri or source
    reference_uri = _safe_contract_url(contract_url or resolved_uri)
    if inline_contract and _contains_credential_uri(contract.document):
        raise ValueError(
            "Cannot inline an ODCS contract containing a credential-bearing URI"
        )
    document, mapped_fields, defaults, missing, warnings = _build_odps_draft(
        contract.document,
        metadata,
        reference_uri,
        inline_contract=inline_contract,
        product_name=product_name,
        product_id=product_id,
        product_type=product_type,
        language=language,
    )
    if not inline_contract and urlparse(reference_uri).scheme == "file":
        warnings.append(
            "LOCAL_CONTRACT_REFERENCE: file URI portability is limited to systems "
            "with access to the same path"
        )
    proposals: List[ContractWrapProposal] = []
    errors: List[str] = []
    ai_enriched = False
    if use_ai:
        try:
            proposals = _generate_ai_proposals(metadata, config, extend=extend)
            ai_enriched = True
            if _apply_ai_description(document, proposals):
                warnings.append(
                    "AI_PROPOSED_DESCRIPTION_APPLIED: "
                    "product.details.en.description requires review"
                )
            _apply_ai_tags(document, proposals)
            if extend:
                _apply_ai_extended_details(document, proposals, metadata)
        except Exception as exc:
            errors.append(f"AI enrichment failed: {type(exc).__name__}")
    validation = validate_document(document)
    output_path = str(Path(output)) if output else None
    if output and not dry_run:
        destination = Path(output)
        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"Refusing to overwrite existing output: {destination}. "
                "Pass overwrite=True to replace it."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    return ContractWrapResult(
        source=contract.source or source,
        resolved_uri=resolved_uri,
        source_standard="ODCS",
        source_specification_version=metadata["specification_version"],
        contract_id=_text(contract.document.get("id")),
        contract_instance_version=_text(contract.document.get("version")),
        target_odps_version="4.2",
        output=output_path,
        inline_contract=inline_contract,
        ai_enabled=use_ai,
        ai_enriched=ai_enriched,
        document=document,
        mapped_fields=mapped_fields,
        provisional_defaults=defaults,
        missing_business_information=missing,
        ai_proposals=proposals,
        warnings=warnings,
        errors=errors,
        validation=validation,
    )


def _odcs_metadata(document: Dict[str, object]) -> Dict[str, str]:
    """Extract the ODCS metadata needed for deterministic wrapping."""
    api_version = _text(document.get("apiVersion"))
    if not api_version:
        raise ValueError("Data Contract does not declare an ODCS apiVersion")
    version = api_version.lstrip("vV")
    version_parts = version.split(".")
    supported_version = (
        ".".join(version_parts[:2]) if len(version_parts) > 1 else version
    )
    if supported_version not in _SUPPORTED_ODCS_VERSIONS:
        raise ValueError(f"Unsupported ODCS specification version: {api_version}")
    kind = _text(document.get("kind"))
    if kind != "DataContract":
        raise ValueError("ODCS document kind must be DataContract")
    description = document.get("description")
    description_mapping = description if isinstance(description, dict) else {}
    name = _text(document.get("name")) or _text(document.get("dataProduct"))
    description_text = (
        _text(description)
        or _text(description_mapping.get("purpose"))
        or _text(document.get("purpose"))
    )
    return {
        "specification_version": version,
        "name": name or "",
        "name_source": "/name" if _text(document.get("name")) else "/dataProduct",
        "description": description_text or "",
        "description_source": (
            "/description"
            if _text(description)
            else (
                "/description/purpose"
                if _text(description_mapping.get("purpose"))
                else "/purpose"
            )
        ),
        "domain": _text(document.get("domain")) or "",
        "contract_instance_version": _text(document.get("version")) or "",
    }


def _build_odps_draft(
    contract: Dict[str, object],
    metadata: Dict[str, str],
    reference_uri: str,
    *,
    inline_contract: bool,
    product_name: Optional[str],
    product_id: Optional[str],
    product_type: Optional[str],
    language: Optional[str],
) -> Tuple[
    Dict[str, object],
    List[ContractMappedField],
    List[str],
    List[str],
    List[str],
]:
    """Build the schema-valid ODPS layer without inferring business facts."""
    mapped: List[ContractMappedField] = []
    defaults: List[str] = []
    missing = [
        "business owner",
        "approved business value proposition",
        "confirmed consumers and use cases",
        "approved service commitments",
        "legal terms and access rights",
    ]
    warnings: List[str] = []
    source_id = _text(contract.get("id"))
    source_name = metadata["name"]
    details_name = product_name or source_name
    if not details_name:
        details_name = _title_from_id(product_id or source_id or "data-product")
        defaults.append("product.details.en.name")
    elif product_name is None:
        mapped.append(
            ContractMappedField(
                metadata["name_source"], "product.details.en.name", details_name
            )
        )
    details_id = product_id or _slugify(source_id or source_name or details_name)
    if product_id is None:
        defaults.append("product.details.en.productID")
    details_type = product_type or "dataset"
    if product_type is None:
        defaults.append("product.details.en.type")
    defaults.extend(
        ["product.details.en.status=draft", "product.details.en.visibility=private"]
    )
    details: Dict[str, object] = {
        "productID": details_id,
        "name": details_name,
        "visibility": "private",
        "status": "draft",
        "type": details_type,
    }
    if language:
        details["language"] = [language]
    if metadata["description"]:
        details["description"] = metadata["description"]
        mapped.append(
            ContractMappedField(
                metadata["description_source"],
                "product.details.en.description",
                metadata["description"],
            )
        )
    if metadata["domain"]:
        details["categories"] = [metadata["domain"]]
        mapped.append(
            ContractMappedField(
                "/domain", "product.details.en.categories/0", metadata["domain"]
            )
        )
    contract_profile: Dict[str, object] = {
        "type": "ODCS",
        "contractVersion": metadata["specification_version"],
    }
    mapped.append(
        ContractMappedField("/apiVersion", "product.contract.default.type", "ODCS")
    )
    mapped.append(
        ContractMappedField(
            "/apiVersion",
            "product.contract.default.contractVersion",
            metadata["specification_version"],
        )
    )
    if source_id:
        contract_profile["id"] = source_id
        mapped.append(
            ContractMappedField("/id", "product.contract.default.id", source_id)
        )
    else:
        missing.append("contract identity")
    if inline_contract:
        contract_profile["spec"] = contract
        mapped.append(
            ContractMappedField("/", "product.contract.default.spec", "inline ODCS")
        )
    else:
        contract_profile["contractURL"] = reference_uri
        mapped.append(
            ContractMappedField(
                "source location",
                "product.contract.default.contractURL",
                reference_uri,
            )
        )
    product: Dict[str, object] = {
        "details": {"en": details},
        "contract": {"default": contract_profile},
    }
    data_access = _data_access_profile(contract)
    if data_access is not None:
        product["dataAccess"] = {"default": data_access}
        mapped.append(
            ContractMappedField(
                "/servers",
                "product.dataAccess.default.outputPortType",
                str(data_access["outputPortType"]),
            )
        )
    elif contract.get("servers"):
        warnings.append(
            "DATA_ACCESS_OMITTED: source servers do not establish a supported output port type"
        )
    return (
        {"schema": _ODPS_V42_SCHEMA, "version": "4.2", "product": product},
        mapped,
        defaults,
        missing,
        warnings,
    )


def _data_access_profile(contract: Dict[str, object]) -> Optional[Dict[str, object]]:
    """Map one explicitly typed ODCS server to ODPS Data Access."""
    servers = contract.get("servers")
    values: List[Dict[str, object]]
    if isinstance(servers, dict):
        values = [item for item in servers.values() if isinstance(item, dict)]
    elif isinstance(servers, list):
        values = [item for item in servers if isinstance(item, dict)]
    else:
        values = []
    for server in values:
        output_port = _SERVER_OUTPUT_PORT_TYPES.get(
            (_text(server.get("type")) or "").lower()
        )
        if not output_port:
            continue
        url = _text(server.get("url"))
        if not url or not _is_supported_access_uri(url, output_port):
            continue
        profile: Dict[str, object] = {
            "outputPortType": output_port,
            "contract": {"$ref": "#/product/contract/default"},
            "accessURL": url,
        }
        data_format = _text(server.get("format"))
        if data_format in _ODPS_FORMATS:
            profile["format"] = data_format
        return profile
    return None


def _generate_ai_proposals(
    metadata: Dict[str, str], config: Optional[str], *, extend: bool
) -> List[ContractWrapProposal]:
    """Request bounded, explicitly unconfirmed business-layer proposals."""
    from ..generation import create_generation_client, resolve_generation_settings

    settings = resolve_generation_settings(config_path=config)
    client = create_generation_client(settings)
    source_summary = {
        "name": metadata["name"],
        "description": metadata["description"],
        "domain": metadata["domain"],
    }
    standard_fields = (
        "description, suggestedTags, valueProposition, potentialConsumers, "
        "potentialUseCases, suggestedCategories, missingBusinessInformation"
    )
    extended_fields = (
        ", productSeries, brandSlogan, versionNotes, issues, " "recommendedDataProducts"
        if extend
        else ""
    )
    prompt = (
        "Propose, do not assert, business-layer candidates for this ODCS technical "
        "contract. Do not invent owners, service commitments, legal/access rights, "
        "or actual demand. For description, restate the supplied technical purpose "
        "in concise business language without adding unsupported claims. Return a "
        "JSON object whose optional values are strings or "
        "arrays of strings with only these keys: "
        + standard_fields
        + extended_fields
        + ". suggestedTags must be "
        "concise, lowercase, hyphenated discovery terms grounded in the source "
        "summary. When included, issues and recommendedDataProducts must be "
        "absolute HTTPS URLs. "
        "Source summary:\n" + json.dumps(source_summary, sort_keys=True)
    )
    response = client(prompt, settings.model)
    parsed = json.loads(response)
    if not isinstance(parsed, dict):
        raise ValueError("AI enrichment did not return a JSON object")
    proposals: List[ContractWrapProposal] = []
    for field in (
        "description",
        "suggestedTags",
        "valueProposition",
        "potentialConsumers",
        "potentialUseCases",
        "suggestedCategories",
        "missingBusinessInformation",
        "productSeries",
        "brandSlogan",
        "versionNotes",
        "issues",
        "recommendedDataProducts",
    ):
        value = parsed.get(field)
        if isinstance(value, str) and value.strip():
            proposals.append(ContractWrapProposal(field, value.strip()))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    proposals.append(ContractWrapProposal(field, item.strip()))
    return proposals


def _apply_ai_description(
    document: Dict[str, object], proposals: List[ContractWrapProposal]
) -> bool:
    """Apply one review-required AI description to the generated ODPS draft."""
    description = next(
        (proposal.value for proposal in proposals if proposal.field == "description"),
        None,
    )
    product = document.get("product")
    if not description or not isinstance(product, dict):
        return False
    details_by_language = product.get("details")
    if not isinstance(details_by_language, dict):
        return False
    details = details_by_language.get("en")
    if not isinstance(details, dict):
        return False
    details["description"] = description
    return True


def _apply_ai_tags(
    document: Dict[str, object], proposals: List[ContractWrapProposal]
) -> bool:
    """Apply review-required AI discovery tags to the generated ODPS draft."""
    tags = [
        proposal.value for proposal in proposals if proposal.field == "suggestedTags"
    ]
    product = document.get("product")
    if not tags or not isinstance(product, dict):
        return False
    details_by_language = product.get("details")
    if not isinstance(details_by_language, dict):
        return False
    details = details_by_language.get("en")
    if not isinstance(details, dict):
        return False
    details["tags"] = list(dict.fromkeys(tags))
    return True


def _apply_ai_extended_details(
    document: Dict[str, object],
    proposals: List[ContractWrapProposal],
    metadata: Dict[str, str],
) -> None:
    """Apply extended AI product details to an explicitly requested draft."""
    details = _draft_details(document)
    if details is None:
        return
    values = _proposal_values(proposals)
    for proposal_field, detail_field in (
        ("valueProposition", "valueProposition"),
        ("productSeries", "productSeries"),
        ("brandSlogan", "brandSlogan"),
        ("versionNotes", "versionNotes"),
        ("issues", "issues"),
    ):
        if values.get(proposal_field):
            details[detail_field] = values[proposal_field][0]
    for proposal_field, detail_field in (
        ("suggestedCategories", "categories"),
        ("recommendedDataProducts", "recommendedDataProducts"),
    ):
        if values.get(proposal_field):
            existing = details.get(detail_field, [])
            existing_values = existing if isinstance(existing, list) else []
            details[detail_field] = list(
                dict.fromkeys(existing_values + values[proposal_field])
            )
    if values.get("potentialUseCases"):
        details["useCases"] = [
            {"useCase": {"useCaseTitle": value}}
            for value in values["potentialUseCases"]
        ]
    if metadata["contract_instance_version"]:
        details["productVersion"] = metadata["contract_instance_version"]


def _draft_details(document: Dict[str, object]) -> Optional[Dict[str, object]]:
    """Return the default language details from a generated product draft."""
    product = document.get("product")
    if not isinstance(product, dict):
        return None
    details_by_language = product.get("details")
    if not isinstance(details_by_language, dict):
        return None
    details = details_by_language.get("en")
    return details if isinstance(details, dict) else None


def _proposal_values(
    proposals: List[ContractWrapProposal],
) -> Dict[str, List[str]]:
    """Collect proposal values by response field."""
    values: Dict[str, List[str]] = {}
    for proposal in proposals:
        values.setdefault(proposal.field, []).append(proposal.value)
    return values


def _text(value: object) -> Optional[str]:
    """Return a non-empty string value, when present."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _slugify(value: str) -> str:
    """Produce a deterministic provisional ODPS product identifier."""
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "data-product"


def _title_from_id(value: str) -> str:
    """Produce a provisional display name from an identifier."""
    return re.sub(r"[-_]+", " ", value).strip().title()


def _is_absolute_uri(value: str) -> bool:
    """Return whether a value has a URI scheme without importing another resolver."""
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value))


def _is_supported_access_uri(value: str, output_port: str) -> bool:
    """Return whether an access URI matches the declared transport."""
    scheme = urlparse(value).scheme.lower()
    return (
        _is_absolute_uri(value)
        and not _is_credential_bearing_uri(value)
        and scheme in _ACCESS_URI_SCHEMES[output_port]
    )


def _safe_contract_url(value: str) -> str:
    """Return a serializable contract URI without credentials or fragments."""
    if _is_credential_bearing_uri(value):
        raise ValueError("Credential-bearing contract URL is not supported")
    parsed = urlparse(value)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, "")
    )


def _contains_credential_uri(value: object) -> bool:
    """Return whether nested ODCS content contains a credential-bearing URI."""
    if isinstance(value, dict):
        return any(_contains_credential_uri(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_credential_uri(item) for item in value)
    return isinstance(value, str) and _is_credential_bearing_uri(value)


def _is_credential_bearing_uri(value: str) -> bool:
    """Return whether a URI has userinfo or a sensitive query parameter."""
    parsed = urlparse(value)
    if not parsed.scheme:
        return False
    if (
        "@" in parsed.netloc
        or parsed.username
        or parsed.password
        or "?" in value
        or "#" in value
    ):
        return True
    for parameter in re.split(r"[&;]", parsed.query):
        key = unquote(parameter.split("=", 1)[0])
        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
        if normalized in {"apikey", "auth", "key"} or any(
            fragment in normalized for fragment in _CREDENTIAL_QUERY_FRAGMENTS
        ):
            return True
    return False


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
        summary=_report_summary(
            product_validation.valid, len(references), contract_valid
        ),
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
                format=_contract_reference_format(pointer, value),
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


def _contract_reference_format(pointer: str, value: Dict[str, object]) -> Optional[str]:
    """Classify ODPS v4.2 profile references without resolving external data."""
    if pointer.endswith("/product/contract") and set(value) == {"$ref"}:
        return "ContractProfileCollection"
    if "/product/contract/" in pointer and "$ref" in value:
        return "Contract"
    return _optional_str(value.get("format") or value.get("type"))


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
