"""Discover review-only portfolio candidates from ODCS contracts."""

from __future__ import annotations

from hashlib import sha256
import html
import json
from pathlib import Path
import re
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .loader import (
    extract_contract_schema_from_document,
    load_contract,
    summarize_contract_document,
)
from .models import (
    ContractDiscoveryResult,
    ContractInventoryRecord,
    ContractRelationship,
    DiscoveryArtifact,
    Finding,
    IntelligenceFinding,
    ProductCandidate,
)

PathLike = Union[str, Path]
_CONTRACT_SUFFIXES = {".json", ".yaml", ".yml"}
_BUSINESS_QUESTIONS = [
    "Which business objective does this candidate support?",
    "Which consumer need justifies this product boundary?",
    "Who is accountable for approving ownership and scope?",
]
_STANDALONE_QUESTIONS = [
    "Which consumer need confirms this contract should be offered as a data product?",
    "Who is accountable for approving ownership and product scope?",
]
_RATIONALISATION_QUESTIONS = [
    "Which contract should be the canonical resource?",
    "Who approves consolidation, deprecation, or retained parallel ownership?",
]


def discover_contract_portfolio(
    *,
    output: PathLike,
    directory: Optional[PathLike] = None,
    source_id: Optional[str] = None,
    portfolio_path: Optional[PathLike] = None,
    use_ai: bool = False,
    client: Optional[Callable[[str, str], str]] = None,
    model: str = "contract-discovery",
    source_settings: Optional[Mapping[str, object]] = None,
) -> ContractDiscoveryResult:
    """Discover review-only candidates from exactly one contract source."""
    if (directory is None) == (source_id is None):
        raise ValueError("Provide exactly one of directory or source_id")
    if source_id is not None:
        return ContractDiscoveryResult(
            source_id=source_id,
            source_status="source_not_implemented",
            inventory=[],
            relationships=[],
            candidates=[],
            warnings=["Configured API contract sources are not implemented yet."],
        )

    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError("Contract directory does not exist")
    inventory = _scan_directory(root)
    relationships, candidates = _analyze_inventory(inventory)
    intelligence_findings = _derive_intelligence_findings(inventory, relationships)
    intelligence_summary = _intelligence_summary(
        inventory, relationships, intelligence_findings, candidates
    )
    ai_proposals = []
    warnings = []
    if use_ai:
        if client is None:
            raise ValueError("AI discovery requires a configured generation client")
        ai_proposals, warnings = _propose_candidates_with_ai(
            inventory, relationships, client, model
        )
    result = ContractDiscoveryResult(
        source_id=root.name or "contracts",
        inventory=inventory,
        relationships=relationships,
        candidates=candidates,
        intelligence_findings=intelligence_findings,
        intelligence_summary=intelligence_summary,
        ai_enabled=use_ai,
        ai_proposals=ai_proposals,
        warnings=warnings,
    )
    artifacts = _write_artifacts(result, Path(output))
    return ContractDiscoveryResult(
        source_id=result.source_id,
        inventory=result.inventory,
        relationships=result.relationships,
        candidates=result.candidates,
        intelligence_findings=result.intelligence_findings,
        intelligence_summary=result.intelligence_summary,
        source_status=result.source_status,
        artifacts=artifacts,
        warnings=result.warnings,
        ai_enabled=result.ai_enabled,
        ai_proposals=result.ai_proposals,
    )


def _scan_directory(root: Path) -> List[ContractInventoryRecord]:
    """Return one inventory record for each supported source file."""
    records = []
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.suffix.lower() not in _CONTRACT_SUFFIXES:
            continue
        if not _has_odcs_markers(path):
            continue
        records.append(_inventory_record(path, root))
    return records


def _has_odcs_markers(path: Path) -> bool:
    """Return whether a source file is plausibly an ODCS contract."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return "DataContract" in text and "apiVersion" in text


def _inventory_record(path: Path, root: Path) -> ContractInventoryRecord:
    """Normalize one source document without exposing its local path."""
    reference = path.relative_to(root).as_posix()
    logical_id = _logical_id(reference)
    try:
        contract = load_contract(str(path))
    except ValueError as exc:
        return ContractInventoryRecord(
            logical_id=logical_id,
            source_reference=reference,
            status="invalid",
            findings=[Finding("CONTRACT_UNREADABLE", str(exc), "warning")],
        )
    document = contract.document
    if not _is_odcs(document):
        return ContractInventoryRecord(
            logical_id=logical_id,
            source_reference=reference,
            status="unsupported",
            findings=[
                Finding(
                    "CONTRACT_UNSUPPORTED",
                    "Document is not a supported ODCS DataContract.",
                    "warning",
                )
            ],
        )
    summary = summarize_contract_document(document, path=reference)
    schema = extract_contract_schema_from_document(document, path=reference)
    description = document.get("description")
    description = description if isinstance(description, dict) else {}
    servers = _mapping_list(document.get("servers"))
    return ContractInventoryRecord(
        logical_id=logical_id,
        source_reference=reference,
        status="loaded",
        contract_id=summary.contract_id,
        name=summary.name,
        version=summary.version,
        odcs_version=str(document.get("apiVersion")),
        domain=_text(document.get("domain")),
        owner=_owner_from_document(document),
        lifecycle_status=_text(document.get("status")),
        purpose=_text(description.get("purpose") or document.get("purpose")),
        tags=_text_list(document.get("tags")),
        technical_interfaces=_server_values(servers, "type"),
        technical_resources=_server_values(servers, "server"),
        server_count=len(servers),
        model_count=schema.model_count,
        field_count=schema.field_count,
        fingerprint=_canonical_contract_hash(document),
        schema_signature=_schema_signature(schema),
        findings=schema.findings,
    )


def _is_odcs(document: Mapping[str, object]) -> bool:
    """Return whether a parsed mapping declares an ODCS v3 contract."""
    return str(document.get("kind", "")).lower() == "datacontract" and str(
        document.get("apiVersion", "")
    ).startswith("v3")


def _logical_id(reference: str) -> str:
    """Return a stable logical source identifier."""
    return "contract-" + sha256(reference.encode("utf-8")).hexdigest()[:12]


def _canonical_contract_hash(document: Mapping[str, object]) -> str:
    """Return a stable fingerprint for one complete contract document."""
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _schema_signature(schema: object) -> List[str]:
    """Return sorted model-field-type signatures from an extracted schema."""
    models = getattr(schema, "models", [])
    signatures = []
    for model in models:
        fields = ",".join(
            "{}:{}".format(field.name, field.type or "")
            for field in sorted(model.fields, key=lambda item: item.name)
        )
        signatures.append("{}|{}".format(model.name, fields))
    return sorted(signatures)


def _text(value: object) -> Optional[str]:
    """Return a non-empty text value."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _text_list(value: object) -> List[str]:
    """Return stable non-empty text values from a list."""
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _mapping_list(value: object) -> List[Mapping[str, object]]:
    """Return mapping items from a list without preserving arbitrary values."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _server_values(servers: Sequence[Mapping[str, object]], key: str) -> List[str]:
    """Return stable declared server identifiers without locations or credentials."""
    return sorted(
        {
            value
            for server in servers
            for value in [_text(server.get(key))]
            if value is not None
        }
    )


def _owner_from_document(document: Mapping[str, object]) -> Optional[str]:
    """Return a declared owner from root metadata or an ODCS owner team entry."""
    direct = _text(document.get("owner"))
    if direct is not None:
        return direct
    for member in _mapping_list(document.get("team")):
        if _text(member.get("role")) != "owner":
            continue
        return _text(member.get("name")) or _text(member.get("username"))
    return None


def _analyze_inventory(
    inventory: Sequence[ContractInventoryRecord],
) -> Tuple[List[ContractRelationship], List[ProductCandidate]]:
    """Produce deterministic relationships and review-only candidates."""
    loaded = [record for record in inventory if record.status == "loaded"]
    relationships = []
    for index, source in enumerate(loaded):
        for target in loaded[index + 1 :]:
            if source.fingerprint and source.fingerprint == target.fingerprint:
                relationships.append(
                    ContractRelationship(
                        source_id=source.logical_id,
                        target_id=target.logical_id,
                        kind="exact_duplicate",
                        evidence_class="inferred",
                        rationale="Matching canonical contract fingerprint.",
                    )
                )
                continue
            shared_resources = sorted(
                resource
                for resource in (
                    set(source.technical_resources) & set(target.technical_resources)
                )
                if _is_specific_technical_resource(resource)
            )
            if shared_resources:
                relationships.append(
                    ContractRelationship(
                        source_id=source.logical_id,
                        target_id=target.logical_id,
                        kind="shared_technical_resource",
                        evidence_class="source_fact",
                        rationale="Both contracts declare technical resource names: {}.".format(
                            ", ".join(shared_resources)
                        ),
                        score=1.0,
                    )
                )
            shared = sorted(set(source.schema_signature) & set(target.schema_signature))
            if shared:
                relationships.append(
                    ContractRelationship(
                        source_id=source.logical_id,
                        target_id=target.logical_id,
                        kind="schema_overlap",
                        evidence_class="inferred",
                        rationale="Shared normalized schema signatures: {}.".format(
                            ", ".join(shared)
                        ),
                        score=len(shared)
                        / float(
                            max(
                                len(source.schema_signature),
                                len(target.schema_signature),
                            )
                        ),
                    )
                )
            shared_tokens = _shared_capability_tokens(source, target)
            if shared_tokens:
                relationships.append(
                    ContractRelationship(
                        source_id=source.logical_id,
                        target_id=target.logical_id,
                        kind="shared_domain_capability",
                        evidence_class="inferred",
                        rationale=(
                            "Shared domain '{}' and capability terms: {}.".format(
                                source.domain, ", ".join(shared_tokens)
                            )
                        ),
                        score=len(shared_tokens)
                        / float(
                            max(
                                len(_capability_tokens(source.name)),
                                len(_capability_tokens(target.name)),
                            )
                        ),
                    )
                )
    boundary_candidates = [
        ProductCandidate(
            candidate_id="candidate-"
            + relationship.source_id[-6:]
            + "-"
            + relationship.target_id[-6:],
            status="proposed",
            evidence_class=relationship.evidence_class,
            supporting_contract_ids=[relationship.source_id, relationship.target_id],
            rationale=relationship.rationale,
            unresolved_questions=list(_BUSINESS_QUESTIONS),
            score=relationship.score,
            opportunity_type="boundary_proposal",
        )
        for relationship in relationships
        if relationship.kind == "shared_domain_capability"
    ]
    standalone_candidates = [
        ProductCandidate(
            candidate_id="candidate-standalone-" + record.logical_id[-12:],
            status="proposed",
            evidence_class="source_fact",
            supporting_contract_ids=[record.logical_id],
            rationale=(
                "Contract declares name '{}', domain '{}', and purpose '{}'."
            ).format(record.name, record.domain, record.purpose),
            unresolved_questions=list(_STANDALONE_QUESTIONS),
            opportunity_type="standalone_product_candidate",
        )
        for record in loaded
        if record.name is not None
        and record.domain is not None
        and record.purpose is not None
    ]
    rationalisation_candidates = [
        ProductCandidate(
            candidate_id="candidate-rationalisation-"
            + relationship.source_id[-6:]
            + "-"
            + relationship.target_id[-6:],
            status="proposed",
            evidence_class=relationship.evidence_class,
            supporting_contract_ids=[relationship.source_id, relationship.target_id],
            rationale=relationship.rationale,
            unresolved_questions=list(_RATIONALISATION_QUESTIONS),
            score=relationship.score,
            opportunity_type="rationalisation_opportunity",
        )
        for relationship in relationships
        if relationship.kind == "exact_duplicate"
    ]
    return (
        relationships,
        standalone_candidates + boundary_candidates + rationalisation_candidates,
    )


def _derive_intelligence_findings(
    inventory: Sequence[ContractInventoryRecord],
    relationships: Sequence[ContractRelationship],
) -> List[IntelligenceFinding]:
    """Return source-linked deterministic intelligence findings."""
    findings = []
    for record in inventory:
        if record.status != "loaded":
            continue
        for field_name, value, label in (
            ("domain", record.domain, "domain"),
            ("owner", record.owner, "owner"),
            ("purpose", record.purpose, "purpose"),
        ):
            if value is None:
                findings.append(
                    _intelligence_finding(
                        category="information_gap",
                        kind="missing_" + field_name,
                        evidence_class="source_fact",
                        source_contract_ids=[record.logical_id],
                        evidence=[
                            "{} is not declared in the contract metadata.".format(label)
                        ],
                        rationale="Contract does not declare a {}.".format(label),
                        why_it_matters=(
                            "Missing {} limits reliable governance and product review."
                        ).format(label),
                        suggested_action=(
                            "Add the accountable {} before making product or reuse decisions."
                        ).format(label),
                    )
                )
    for relationship in relationships:
        category = "reuse" if relationship.kind == "exact_duplicate" else "similarity"
        why_it_matters, suggested_action = _relationship_action(relationship.kind)
        findings.append(
            _intelligence_finding(
                category=category,
                kind=relationship.kind,
                evidence_class=relationship.evidence_class,
                source_contract_ids=[relationship.source_id, relationship.target_id],
                evidence=[relationship.rationale],
                rationale=relationship.rationale,
                why_it_matters=why_it_matters,
                suggested_action=suggested_action,
                score=relationship.score,
            )
        )
    return findings


def _intelligence_finding(
    *,
    category: str,
    kind: str,
    evidence_class: str,
    source_contract_ids: List[str],
    evidence: List[str],
    rationale: str,
    why_it_matters: str,
    suggested_action: str,
    score: float = 1.0,
) -> IntelligenceFinding:
    """Create one stable source-linked intelligence finding."""
    key = "|".join([category, kind] + sorted(source_contract_ids))
    return IntelligenceFinding(
        finding_id="finding-" + sha256(key.encode("utf-8")).hexdigest()[:12],
        category=category,
        kind=kind,
        evidence_class=evidence_class,
        source_contract_ids=list(source_contract_ids),
        evidence=list(evidence),
        rationale=rationale,
        why_it_matters=why_it_matters,
        suggested_action=suggested_action,
        score=score,
    )


def _relationship_action(kind: str) -> Tuple[str, str]:
    """Return conservative investigation guidance for one relationship kind."""
    actions = {
        "exact_duplicate": (
            "Duplicate contracts can diverge and create avoidable maintenance or consumer confusion.",
            "Review whether the contracts should consolidate or designate one canonical resource.",
        ),
        "schema_overlap": (
            "Overlapping schema can indicate duplicated resources or complementary interfaces that need clearer boundaries.",
            "Review whether the shared schema represents reuse, duplication, or a documented interface dependency.",
        ),
        "shared_technical_resource": (
            "A shared declared technical resource can create common operational or governance dependencies.",
            "Review whether the contracts should share ownership, access controls, or lifecycle coordination.",
        ),
        "shared_domain_capability": (
            "A shared domain and capability signal can justify investigating a common product boundary.",
            "Confirm consumer needs, accountable ownership, and intended product scope before grouping the contracts.",
        ),
    }
    return actions.get(
        kind,
        (
            "The relationship needs human interpretation before it can affect a portfolio decision.",
            "Review the supporting contract evidence.",
        ),
    )


def _intelligence_summary(
    inventory: Sequence[ContractInventoryRecord],
    relationships: Sequence[ContractRelationship],
    findings: Sequence[IntelligenceFinding],
    candidates: Sequence[ProductCandidate],
) -> Dict[str, int]:
    """Return compact counts for the intelligence overview."""
    return {
        "contracts_analyzed": len(
            [record for record in inventory if record.status == "loaded"]
        ),
        "relationships_detected": len(relationships),
        "reuse_findings": len(
            [finding for finding in findings if finding.category == "reuse"]
        ),
        "information_gap_findings": len(
            [finding for finding in findings if finding.category == "information_gap"]
        ),
        "proposed_product_groups": len(
            [
                item
                for item in candidates
                if item.opportunity_type == "boundary_proposal"
            ]
        ),
        "product_opportunities": len(candidates),
        "standalone_product_candidates": len(
            [
                item
                for item in candidates
                if item.opportunity_type == "standalone_product_candidate"
            ]
        ),
        "rationalisation_opportunities": len(
            [
                item
                for item in candidates
                if item.opportunity_type == "rationalisation_opportunity"
            ]
        ),
    }


def _shared_capability_tokens(
    source: ContractInventoryRecord, target: ContractInventoryRecord
) -> List[str]:
    """Return meaningful shared name terms when contracts declare one domain."""
    if not source.domain or source.domain != target.domain:
        return []
    shared = sorted(_capability_tokens(source.name) & _capability_tokens(target.name))
    return shared if len(shared) >= 2 else []


def _is_specific_technical_resource(resource: str) -> bool:
    """Exclude generic environment and platform labels from resource matches."""
    generic = {
        "api",
        "athena",
        "bigquery",
        "databricks",
        "development",
        "local",
        "postgres",
        "production",
        "staging",
    }
    return resource.strip().lower() not in generic


def _capability_tokens(name: Optional[str]) -> set:
    """Return stable name terms suitable for conservative similarity checks."""
    if not name:
        return set()
    ignored = {"contract", "data", "test", "unit", "view", "v1", "v2", "v3"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", name.lower())
        if len(token) > 1 and token not in ignored
    }


def _propose_candidates_with_ai(
    inventory: Sequence[ContractInventoryRecord],
    relationships: Sequence[ContractRelationship],
    client: Callable[[str, str], str],
    model: str,
) -> Tuple[List[ProductCandidate], List[str]]:
    """Return review-only AI suggestions backed by known inventory IDs."""
    eligible = [record for record in inventory if record.status == "loaded"]
    known_ids = [record.logical_id for record in eligible]
    if not known_ids:
        return [], ["AI discovery requires at least one loaded contract."]
    eligible_relationships = [
        relationship.to_dict()
        for relationship in relationships
        if relationship.source_id in known_ids and relationship.target_id in known_ids
    ]
    if not eligible_relationships:
        return [], ["AI discovery found no technical evidence for contract groupings."]
    prompt = json.dumps(
        {
            "task": "Suggest review-only data product grouping candidates from technical evidence.",
            "inventory": [record.to_dict() for record in eligible],
            "allowedContractIds": known_ids,
            "technicalRelationships": eligible_relationships,
            "requirements": [
                "Return JSON with a suggestions array.",
                "Every suggestion needs at least two distinct contractIds and a rationale.",
                "Each contractIds value must be copied verbatim from allowedContractIds.",
                "Only group contractIds joined by technicalRelationships.",
                "Do not use source contract IDs, contract names, or file paths.",
                "Do not propose a contract solely because it is empty or missing metadata.",
                "Do not claim business objectives, ownership, or approval.",
                "Return at most 20 suggestions.",
            ],
        },
        sort_keys=True,
    )
    try:
        response = _parse_ai_json(client(prompt, model))
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], ["AI discovery returned invalid JSON."]
    suggestions = response.get("suggestions") if isinstance(response, dict) else None
    if not isinstance(suggestions, list):
        return [], ["AI discovery response did not contain suggestions."]
    known_id_set = set(known_ids)
    proposals = []
    warnings = []
    for index, suggestion in enumerate(suggestions, start=1):
        if not isinstance(suggestion, dict):
            warnings.append(
                "AI discovery suggestion {} is not an object.".format(index)
            )
            continue
        identifiers = suggestion.get("contractIds")
        rationale = _text(suggestion.get("rationale"))
        if (
            not isinstance(identifiers, list)
            or not identifiers
            or not all(isinstance(identifier, str) for identifier in identifiers)
            or rationale is None
        ):
            warnings.append(
                "AI discovery suggestion {} is missing contract IDs or rationale.".format(
                    index
                )
            )
            continue
        unknown = sorted(set(identifiers) - known_id_set)
        if unknown:
            warnings.append(
                "AI discovery suggestion {} references unknown contract IDs.".format(
                    index
                )
            )
            continue
        if len(set(identifiers)) < 2:
            warnings.append(
                "AI discovery suggestion {} must group at least two contracts.".format(
                    index
                )
            )
            continue
        if not _has_relationship_evidence(identifiers, relationships):
            warnings.append(
                "AI discovery suggestion {} has no technical relationship evidence.".format(
                    index
                )
            )
            continue
        candidate_key = "|".join(sorted(identifiers)) + "|" + rationale
        proposals.append(
            ProductCandidate(
                candidate_id="ai-candidate-"
                + sha256(candidate_key.encode("utf-8")).hexdigest()[:12],
                status="proposed",
                evidence_class="proposed",
                supporting_contract_ids=list(identifiers),
                rationale=rationale,
                unresolved_questions=list(_BUSINESS_QUESTIONS),
                opportunity_type="boundary_proposal",
            )
        )
    return proposals, warnings


def _parse_ai_json(response: str) -> object:
    """Parse a JSON object, allowing one complete Markdown code fence."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("AI discovery response has an incomplete code fence")
        text = "\n".join(lines[1:-1]).strip()
    return json.loads(text)


def _has_relationship_evidence(
    identifiers: Sequence[str], relationships: Sequence[ContractRelationship]
) -> bool:
    """Return whether a suggested grouping has inventory relationship evidence."""
    identifiers_set = set(identifiers)
    return any(
        relationship.source_id in identifiers_set
        and relationship.target_id in identifiers_set
        for relationship in relationships
    )


def _unclassified_contracts(
    inventory: Sequence[ContractInventoryRecord],
    candidates: Sequence[ProductCandidate],
) -> List[ContractInventoryRecord]:
    """Return loaded contracts without a current opportunity signal."""
    classified_ids = {
        identifier
        for candidate in candidates
        for identifier in candidate.supporting_contract_ids
    }
    return [
        record
        for record in inventory
        if record.status == "loaded" and record.logical_id not in classified_ids
    ]


def _write_artifacts(
    result: ContractDiscoveryResult, output: Path
) -> List[DiscoveryArtifact]:
    """Write deterministic JSON and a safe human-readable report."""
    output.mkdir(parents=True, exist_ok=True)
    inventory_path = output / "contract-inventory.json"
    candidates_path = output / "product-candidates.json"
    intelligence_path = output / "contract-intelligence.json"
    report_path = output / "discovery-report.html"
    _write_json(
        inventory_path,
        {
            "kind": "ContractInventory",
            "source_id": result.source_id,
            "contracts": [item.to_dict() for item in result.inventory],
        },
    )
    _write_json(
        intelligence_path,
        {
            "kind": "ContractIntelligence",
            "source_id": result.source_id,
            "summary": result.intelligence_summary,
            "interface_analysis": _interface_analysis(result.inventory),
            "findings": [item.to_dict() for item in result.intelligence_findings],
        },
    )
    _write_json(
        candidates_path,
        {
            "kind": "ProductCandidates",
            "source_id": result.source_id,
            "relationships": [item.to_dict() for item in result.relationships],
            "candidates": [item.to_dict() for item in result.candidates],
            "ai_proposals": [item.to_dict() for item in result.ai_proposals],
            "unclassified_contracts": [
                {
                    "logical_id": record.logical_id,
                    "name": record.name or record.contract_id,
                    "source_reference": record.source_reference,
                    "reason": "No current standalone, boundary, or rationalisation signal.",
                }
                for record in _unclassified_contracts(
                    result.inventory, result.candidates
                )
            ],
        },
    )
    report_path.write_text(_render_report(result), encoding="utf-8")
    return [
        DiscoveryArtifact("contract-inventory", "contract-inventory.json"),
        DiscoveryArtifact("contract-intelligence", "contract-intelligence.json"),
        DiscoveryArtifact("product-candidates", "product-candidates.json"),
        DiscoveryArtifact("discovery-report", "discovery-report.html"),
    ]


def _write_json(path: Path, value: object) -> None:
    """Write sorted JSON with a terminal newline."""
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _interface_type_records(
    inventory: Sequence[ContractInventoryRecord],
) -> List[Tuple[str, List[ContractInventoryRecord]]]:
    """Group loaded contracts by their declared interface type."""
    records_by_type: Dict[str, List[ContractInventoryRecord]] = {}
    for record in inventory:
        if record.status != "loaded":
            continue
        for interface_type in record.technical_interfaces:
            records_by_type.setdefault(interface_type, []).append(record)
    return sorted(records_by_type.items(), key=lambda item: (-len(item[1]), item[0]))


def _interface_analysis(
    inventory: Sequence[ContractInventoryRecord],
    interface_types: Optional[
        Sequence[Tuple[str, List[ContractInventoryRecord]]]
    ] = None,
) -> Dict[str, object]:
    """Return source-fact interface counts and their declaring contracts."""
    loaded = [record for record in inventory if record.status == "loaded"]
    grouped = list(interface_types or _interface_type_records(loaded))
    declared_ids = {record.logical_id for _, records in grouped for record in records}
    return {
        "interface_type_count": len(grouped),
        "contracts_with_declared_interface": len(declared_ids),
        "contracts_with_one_interface": sum(
            1 for record in loaded if len(record.technical_interfaces) == 1
        ),
        "contracts_with_multiple_interfaces": sum(
            1 for record in loaded if len(record.technical_interfaces) > 1
        ),
        "contracts_without_declared_interface": len(loaded) - len(declared_ids),
        "types": [
            {
                "interface_type": interface_type,
                "contract_count": len(records),
                "contracts": [
                    {
                        "logical_id": record.logical_id,
                        "name": record.name or record.contract_id,
                        "source_reference": record.source_reference,
                    }
                    for record in records
                ],
            }
            for interface_type, records in grouped
        ],
    }


def _render_report(result: ContractDiscoveryResult) -> str:
    """Render a self-contained evidence-led intelligence report."""
    inventory_by_id = {item.logical_id: item for item in result.inventory}
    interface_types = _interface_type_records(result.inventory)
    interface_analysis = _interface_analysis(result.inventory, interface_types)
    relationships_by_contract: Dict[str, List[Tuple[str, ContractRelationship]]] = {}
    for relationship in result.relationships:
        relationship_id = _relationship_id(relationship)
        for identifier in (relationship.source_id, relationship.target_id):
            relationships_by_contract.setdefault(identifier, []).append(
                (relationship_id, relationship)
            )
    gaps_by_contract: Dict[str, List[IntelligenceFinding]] = {}
    for finding in result.intelligence_findings:
        if finding.category != "information_gap":
            continue
        for identifier in finding.source_contract_ids:
            gaps_by_contract.setdefault(identifier, []).append(finding)

    summary = result.intelligence_summary
    overview = "".join(
        _metric_card(label, summary.get(key, 0), note)
        for label, key, note in (
            ("Contracts analyzed", "contracts_analyzed", "Loaded ODCS contracts"),
            (
                "Relationships detected",
                "relationships_detected",
                "Evidence-backed links",
            ),
            ("Reuse or duplication", "reuse_findings", "Exact duplicate evidence"),
            (
                "Product opportunities",
                "product_opportunities",
                "Require human review",
            ),
        )
    )
    priority_findings = "".join(
        _priority_finding(finding, inventory_by_id)
        for finding in result.intelligence_findings
        if finding.category in {"reuse", "similarity"}
    )
    rows = "".join(
        _contract_explorer_row(
            item,
            relationships_by_contract.get(item.logical_id, []),
            gaps_by_contract.get(item.logical_id, []),
        )
        for item in result.inventory
    )
    interface_rows = "".join(
        _interface_analysis_row(interface_type, records)
        for interface_type, records in interface_types
    )
    relationship_details = "".join(
        _relationship_detail(
            _relationship_id(relationship), relationship, inventory_by_id
        )
        for relationship in result.relationships
    )
    finding_details = "".join(
        _finding_detail(finding, inventory_by_id)
        for finding in result.intelligence_findings
    )
    opportunities = list(result.candidates) + list(result.ai_proposals)
    opportunity_sections = "".join(
        _opportunity_section(
            opportunity_type,
            title,
            description,
            [
                candidate
                for candidate in opportunities
                if candidate.opportunity_type == opportunity_type
            ],
            inventory_by_id,
        )
        for opportunity_type, title, description in (
            (
                "standalone_product_candidate",
                "Standalone product candidates",
                "One contract declares a name, domain, and purpose. Human review still decides whether it becomes a data product.",
            ),
            (
                "boundary_proposal",
                "Boundary proposals",
                "Related contracts have repeatable shared-domain and capability evidence, but a shared product boundary needs human approval.",
            ),
            (
                "rationalisation_opportunity",
                "Rationalisation opportunities",
                "Exact duplicate evidence suggests consolidation or a canonical contract decision, not a new data product.",
            ),
        )
    )
    unclassified_contracts = _unclassified_contracts(result.inventory, opportunities)
    unclassified_rows = "".join(
        _unclassified_contract_row(record) for record in unclassified_contracts
    )
    return (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Contract Intelligence</title>
<style>
:root { color-scheme:light; --purple:#7436EB; --purple-deep:#18093A; --purple-soft:#F1EBFF; --ink:#170C31; --muted:#66647D; --line:#E7E3EF; --surface:#FFFFFF; --canvas:#FEFDFE; --warning:#91550B; --warning-bg:#FFF8E8; }
* { box-sizing:border-box; } body { margin:0; background:var(--canvas); color:var(--ink); font:17px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; } main { max-width:1580px; margin:auto; padding:30px 58px 72px; }
.report-header { display:flex; justify-content:space-between; align-items:center; gap:24px; min-height:58px; } .brand-lockup { display:flex; align-items:center; gap:28px; } .brand-mark { color:var(--purple-deep); font-size:28px; font-style:italic; font-weight:950; letter-spacing:-.12em; line-height:1; } .brand-divider { width:1px; height:35px; background:var(--line); } .brand-name { color:var(--muted); font-size:20px; font-weight:650; } .report-source { color:var(--muted); font-size:13px; overflow-wrap:anywhere; text-align:right; }
.eyebrow { margin:0 0 12px; color:var(--purple); font-size:14px; font-weight:850; letter-spacing:.09em; } .section-heading { margin:0; color:var(--ink); font-size:46px; letter-spacing:-.055em; line-height:1.06; } .summary { max-width:1000px; margin:17px 0 0; color:var(--muted); font-size:20px; line-height:1.45; } .report-section { margin-top:66px; }
.tabs { display:flex; gap:28px; overflow:auto; margin-top:34px; border-bottom:1px solid var(--line); } [role="tab"] { appearance:none; background:transparent; border:0; border-bottom:3px solid transparent; color:var(--muted); cursor:pointer; font:inherit; font-size:15px; font-weight:800; padding:13px 0 12px; white-space:nowrap; } [role="tab"]:hover { color:var(--ink); } [role="tab"][aria-selected="true"] { border-color:var(--purple); color:var(--purple); } [role="tab"]:focus-visible { outline:3px solid var(--purple-soft); outline-offset:-3px; } [role="tabpanel"] { margin-top:0; } [role="tabpanel"][hidden] { display:none; }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; margin-top:32px; } .surface-card { background:var(--surface); border:1px solid var(--line); border-radius:20px; } .metric { min-height:166px; padding:26px 28px; } .metric strong { display:block; color:var(--purple); font-size:42px; letter-spacing:-.05em; line-height:1; } .metric span { display:block; font-size:17px; font-weight:800; margin-top:16px; } .metric small { color:var(--muted); display:block; font-size:14px; margin-top:4px; }
.priority-findings, .opportunities { display:grid; grid-template-columns:repeat(auto-fit,minmax(350px,1fr)); gap:28px; margin-top:58px; } .evidence-card, .empty-state { background:var(--surface); border:1px solid var(--line); border-radius:20px; padding:28px 30px 30px; box-shadow:0 10px 26px rgba(35, 19, 73, .025); } .finding-title { display:flex; align-items:center; gap:17px; margin:0; color:var(--ink); font-size:25px; letter-spacing:-.035em; line-height:1.2; text-transform:capitalize; } .finding-accent { display:block; width:7px; height:38px; flex:none; border-radius:999px; background:var(--purple); box-shadow:0 0 0 3px var(--purple-soft); } .finding-contracts { display:grid; gap:18px; margin-top:27px; } .contract-entry strong { display:block; color:var(--ink); font-size:17px; line-height:1.3; } .contract-entry span, .contract-record span { color:var(--muted); display:block; font-size:14px; line-height:1.45; overflow-wrap:anywhere; } .finding-divider { height:1px; margin:26px 0 22px; background:var(--line); } .evidence-copy, .action-copy { margin:0; color:#302847; font-size:16px; line-height:1.55; } .action-copy { margin-top:15px; } .evidence-copy strong, .action-copy strong { color:var(--ink); }
.explorer { margin-top:32px; overflow:hidden; } .toolbar { display:flex; justify-content:space-between; align-items:end; gap:16px; padding:20px 24px; border-bottom:1px solid var(--line); } .meta { color:var(--muted); font-size:14px; } input { width:min(400px,100%); margin-top:4px; border:1px solid #CCC4D9; border-radius:10px; padding:10px 12px; color:var(--ink); font:inherit; } input:focus { outline:3px solid var(--purple-soft); border-color:var(--purple); } .table-wrap { overflow:auto; } table { width:100%; border-collapse:collapse; min-width:810px; } th { color:var(--muted); font-size:12px; letter-spacing:.06em; text-align:left; text-transform:uppercase; background:#FCFBFE; } th, td { padding:15px 20px; border-bottom:1px solid var(--line); vertical-align:top; } tr:last-child td { border-bottom:0; } .contract-name { color:var(--ink); font-weight:800; } .source { color:var(--muted); font-size:13px; overflow-wrap:anywhere; } .badge { display:inline-block; margin-top:5px; padding:2px 8px; border-radius:999px; background:var(--purple-soft); color:#5621B6; font-size:12px; font-weight:800; }
.relationship-link { display:block; color:#5621B6; font-size:14px; margin:3px 0; text-decoration:none; } .relationship-link:hover { text-decoration:underline; } .gap { color:var(--warning); } .details { margin-top:24px; } details { background:var(--surface); border:1px solid var(--line); border-radius:14px; margin:10px 0; padding:15px 18px; } details:target { border-color:var(--purple); box-shadow:0 0 0 3px var(--purple-soft); } summary { cursor:pointer; color:var(--ink); font-weight:800; } .evidence { color:var(--muted); margin:10px 0 0; }
.interface-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; margin-top:32px; } .interface-summary .metric { min-height:132px; } .interface-register { margin-top:28px; overflow:hidden; } .interface-table { min-width:980px; } .interface-type { color:var(--ink); font-weight:850; } .interface-count { color:var(--purple); font-size:21px; font-weight:850; letter-spacing:-.02em; white-space:nowrap; } .interface-contracts { display:grid; gap:12px; } .interface-contract strong { display:block; color:var(--ink); font-size:15px; } .interface-contract span { color:var(--muted); display:block; font-size:13px; overflow-wrap:anywhere; }
.opportunity-section { margin-top:52px; } .opportunity-section:first-child { margin-top:42px; } .opportunity-section h3, .unclassified-section h3 { margin:0; color:var(--ink); font-size:27px; letter-spacing:-.035em; } .opportunity-description { max-width:900px; margin:8px 0 0; color:var(--muted); } .opportunity-section .opportunities { margin-top:22px; } .opportunity { position:relative; } .opportunity .label { margin-bottom:19px; } .label { color:var(--purple); font-size:13px; font-weight:850; letter-spacing:.07em; } .opportunity .finding-contracts { margin-top:22px; } .contract-group h4 { margin:0; color:var(--ink); font-size:15px; } .contract-record { padding-top:13px; } .contract-number { color:var(--purple)!important; font-size:12px!important; font-weight:850; letter-spacing:.07em; } .contract-record strong { display:block; color:var(--ink); font-size:17px; line-height:1.3; } .review-note { margin-top:22px; padding:14px 15px; border-radius:12px; background:var(--warning-bg); color:var(--warning); font-size:15px; line-height:1.5; } .unclassified-section { margin-top:62px; } .unclassified-section .summary { margin-top:8px; } .unclassified-register { margin-top:24px; overflow:hidden; } .unclassified-register table { min-width:640px; } .unclassified-reason { color:var(--muted); font-size:14px; } .legend { display:flex; flex-wrap:wrap; gap:18px; color:var(--muted); font-size:14px; margin-top:26px; } .legend b { color:var(--ink); }
@media (max-width:900px) { main { padding:26px 28px 56px; } .report-source { display:none; } .section-heading { font-size:39px; } .metrics, .interface-summary { grid-template-columns:repeat(2,minmax(0,1fr)); } } @media (max-width:620px) { main { padding:22px 18px 42px; } .brand-lockup { gap:16px; } .brand-name { font-size:16px; } .report-section { margin-top:46px; } .section-heading { font-size:34px; } .summary { font-size:18px; } .tabs { gap:19px; } .metrics, .interface-summary, .priority-findings, .opportunities { grid-template-columns:1fr; } .priority-findings, .opportunities { gap:16px; margin-top:34px; } .evidence-card, .empty-state { border-radius:16px; padding:23px 21px; } .finding-title { font-size:22px; } .toolbar { align-items:stretch; flex-direction:column; } input { width:100%; } }
</style></head><body><main>
<header class="report-header"><div class="brand-lockup"><div class="brand-mark" aria-label="ODPS">ODPS</div><span class="brand-divider" aria-hidden="true"></span><div class="brand-name">Data Contract Intelligence</div></div><div class="report-source">Source: __SOURCE__</div></header>
<div class="tabs" role="tablist" aria-label="Data Contract Intelligence views"><button id="tab-overview" role="tab" aria-selected="true" aria-controls="panel-overview">What the contracts reveal</button><button id="tab-priority-findings" role="tab" aria-selected="false" aria-controls="panel-priority-findings">Priority findings</button><button id="tab-explorer" role="tab" aria-selected="false" aria-controls="panel-explorer">Contract Intelligence Explorer</button><button id="tab-interfaces" role="tab" aria-selected="false" aria-controls="panel-interfaces">Interface analysis</button><button id="tab-opportunities" role="tab" aria-selected="false" aria-controls="panel-opportunities">Product opportunities</button></div>
<section id="panel-overview" class="report-section" role="tabpanel" aria-labelledby="tab-overview"><p class="eyebrow">OVERVIEW</p><h2 class="section-heading">What the contracts reveal</h2><div class="metrics">__METRICS__</div><p class="summary">__SUMMARY__</p></section>
<section id="panel-priority-findings" class="report-section" role="tabpanel" aria-labelledby="tab-priority-findings" hidden><p class="eyebrow">ACTIONABLE EVIDENCE</p><h2 class="section-heading">Priority findings</h2><p class="summary">Each finding includes the contracts, source references, matching evidence, and next action.</p><div class="priority-findings">__PRIORITY_FINDINGS__</div></section>
<section id="panel-explorer" class="report-section" role="tabpanel" aria-labelledby="tab-explorer" hidden><p class="eyebrow">EXPLORE THE EVIDENCE</p><h2 class="section-heading">Contract Intelligence Explorer</h2><p class="summary">Contracts, relationships, and missing information.</p><div class="surface-card explorer"><div class="toolbar"><span class="meta">Select a relationship or gap to inspect supporting evidence below.</span><label><span class="meta">Search</span><input id="contract-search" type="search" placeholder="Contract, domain, finding, or source"></label></div><div class="table-wrap"><table><thead><tr><th>Contract</th><th>Domain / owner</th><th>Interfaces</th><th>Relationships</th><th>Missing information</th></tr></thead><tbody id="contract-rows">__ROWS__</tbody></table></div></div><div class="details" aria-label="Relationship and finding evidence">__RELATIONSHIP_DETAILS____FINDING_DETAILS__</div></section>
<section id="panel-interfaces" class="report-section" role="tabpanel" aria-labelledby="tab-interfaces" hidden><p class="eyebrow">DECLARED TECHNICAL INTERFACES</p><h2 class="section-heading">Interface Analysis</h2><p class="summary">__INTERFACE_TYPE_COUNT__ declared interface types. __INTERFACE_CONTRACT_COUNT__ contracts declare at least one interface: __SINGLE_INTERFACE_COUNT__ contracts declare one interface and __MULTIPLE_INTERFACE_COUNT__ contracts declare multiple interfaces. __INTERFACE_MISSING_COUNT__ contracts do not declare an interface. Counts show how many contracts declare each type; each source contract remains visible below.</p><div class="interface-summary"><div class="surface-card metric"><strong>__INTERFACE_TYPE_COUNT__</strong><span>Declared interface types</span><small>Distinct values in contract servers</small></div><div class="surface-card metric"><strong>__SINGLE_INTERFACE_COUNT__</strong><span>Contracts with one interface</span><small>One declared server type</small></div><div class="surface-card metric"><strong>__MULTIPLE_INTERFACE_COUNT__</strong><span>Contracts with multiple interfaces</span><small>More than one declared server type</small></div><div class="surface-card metric"><strong>__INTERFACE_MISSING_COUNT__</strong><span>Contracts without an interface</span><small>No declared server type</small></div></div><div class="surface-card interface-register"><div class="table-wrap"><table class="interface-table"><thead><tr><th>Interface type</th><th>Declared by</th><th>Contracts</th></tr></thead><tbody>__INTERFACE_ROWS__</tbody></table></div></div></section>
<section id="panel-opportunities" class="report-section" role="tabpanel" aria-labelledby="tab-opportunities" hidden><p class="eyebrow">REVIEW ONLY</p><h2 class="section-heading">Product Opportunities</h2><p class="summary">Three different decisions are shown separately: whether one contract may stand alone, whether related contracts need a shared boundary, and whether duplicates need rationalisation.</p><div class="opportunity-sections">__OPPORTUNITY_SECTIONS__</div><div class="unclassified-section"><h3>No current opportunity signal · __UNCLASSIFIED_COUNT__ contracts</h3><p class="summary">These contracts do not currently have enough declared evidence for a standalone candidate, boundary proposal, or rationalisation opportunity. This is not a failure.</p><div class="surface-card unclassified-register"><div class="table-wrap"><table><thead><tr><th>Contract</th><th>Source reference</th><th>Why it is unclassified</th></tr></thead><tbody>__UNCLASSIFIED_ROWS__</tbody></table></div></div></div><div class="legend"><span><b>Source fact</b> is declared in a contract.</span><span><b>Inference</b> is a repeatable analysis rule.</span><span><b>Proposal</b> needs a human decision.</span></div></section>
</main><script>
const tabs=[...document.querySelectorAll('[role="tab"]')]; const panels=[...document.querySelectorAll('[role="tabpanel"]')]; function activateTab(tab){tabs.forEach(item=>{const active=item===tab;item.setAttribute('aria-selected',String(active));document.getElementById(item.getAttribute('aria-controls')).hidden=!active;});} tabs.forEach(tab=>tab.addEventListener('click',()=>activateTab(tab))); const search=document.getElementById('contract-search'); const rows=[...document.querySelectorAll('#contract-rows tr')]; search.addEventListener('input',()=>{const term=search.value.toLowerCase().trim(); rows.forEach(row=>{row.hidden=term!==''&&!row.textContent.toLowerCase().includes(term);});});
</script></body></html>""".replace("__SOURCE__", _escape(result.source_id))
        .replace("__METRICS__", overview)
        .replace("__SUMMARY__", _escape(_report_summary(summary)))
        .replace("__PRIORITY_FINDINGS__", priority_findings)
        .replace("__ROWS__", rows)
        .replace("__RELATIONSHIP_DETAILS__", relationship_details)
        .replace("__FINDING_DETAILS__", finding_details)
        .replace(
            "__INTERFACE_TYPE_COUNT__",
            str(interface_analysis["interface_type_count"]),
        )
        .replace(
            "__INTERFACE_CONTRACT_COUNT__",
            str(interface_analysis["contracts_with_declared_interface"]),
        )
        .replace(
            "__SINGLE_INTERFACE_COUNT__",
            str(interface_analysis["contracts_with_one_interface"]),
        )
        .replace(
            "__MULTIPLE_INTERFACE_COUNT__",
            str(interface_analysis["contracts_with_multiple_interfaces"]),
        )
        .replace(
            "__INTERFACE_MISSING_COUNT__",
            str(interface_analysis["contracts_without_declared_interface"]),
        )
        .replace("__INTERFACE_ROWS__", interface_rows)
        .replace("__OPPORTUNITY_SECTIONS__", opportunity_sections)
        .replace("__UNCLASSIFIED_COUNT__", str(len(unclassified_contracts)))
        .replace("__UNCLASSIFIED_ROWS__", unclassified_rows)
    )


def _metric_card(label: str, value: int, note: str) -> str:
    """Render one compact overview metric."""
    return '<div class="surface-card metric"><strong>{}</strong><span>{}</span><small>{}</small></div>'.format(
        value, _escape(label), _escape(note)
    )


def _interface_analysis_row(
    interface_type: str, records: Sequence[ContractInventoryRecord]
) -> str:
    """Render one declared interface type and every supporting contract."""
    contracts = "".join(
        '<div class="interface-contract"><strong>{}</strong><span>{}</span></div>'.format(
            _escape(record.name or record.contract_id or record.logical_id),
            _escape(record.source_reference),
        )
        for record in records
    )
    return (
        '<tr><td><span class="interface-type">{}</span></td>'
        '<td><span class="interface-count">{} contracts</span></td>'
        '<td><div class="interface-contracts">{}</div></td></tr>'
    ).format(_escape(interface_type), len(records), contracts)


def _priority_finding(
    finding: IntelligenceFinding,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one self-contained actionable finding in the overview."""
    contracts = "".join(
        '<div class="contract-entry"><strong>{}</strong><span>{}</span></div>'.format(
            _escape(
                inventory.get(
                    identifier, ContractInventoryRecord("", identifier, "unknown")
                ).name
                or identifier
            ),
            _escape(
                inventory.get(
                    identifier, ContractInventoryRecord("", identifier, "unknown")
                ).source_reference
            ),
        )
        for identifier in finding.source_contract_ids
    )
    return (
        '<article class="evidence-card priority-finding"><h3 class="finding-title">'
        '<span class="finding-accent" aria-hidden="true"></span>{}</h3>'
        '<div class="finding-contracts">{}</div><div class="finding-divider"></div>'
        '<p class="evidence-copy"><strong>Evidence:</strong> {}</p>'
        '<p class="action-copy"><strong>Next:</strong> {}</p></article>'
    ).format(
        _escape(finding.kind.replace("_", " ")),
        contracts,
        _escape(" ".join(finding.evidence)),
        _escape(finding.suggested_action),
    )


def _report_summary(summary: Mapping[str, int]) -> str:
    """Explain intelligence counts without treating ungrouped contracts as failures."""
    return (
        "{} information gaps were recorded. Ungrouped contracts are not a failure: "
        "they need more source evidence before a product boundary can be proposed."
    ).format(summary.get("information_gap_findings", 0))


def _contract_explorer_row(
    record: ContractInventoryRecord,
    relationships: Sequence[Tuple[str, ContractRelationship]],
    gaps: Sequence[IntelligenceFinding],
) -> str:
    """Render one searchable contract explorer row."""
    relationship_links = (
        "".join(
            '<a class="relationship-link" data-relationship-id="{}" href="#relationship-{}">{}</a>'.format(
                _escape(identifier), _escape(identifier), _escape(relationship.kind)
            )
            for identifier, relationship in relationships
        )
        or '<span class="meta">None detected</span>'
    )
    gap_text = (
        "".join(
            '<a class="relationship-link gap" data-finding-id="{}" href="#finding-{}">Missing {}</a>'.format(
                _escape(finding.finding_id),
                _escape(finding.finding_id),
                _escape(finding.kind.replace("missing_", "")),
            )
            for finding in gaps
        )
        or '<span class="meta">None recorded</span>'
    )
    domain_owner = (
        " / ".join(value for value in (record.domain, record.owner) if value) or "—"
    )
    interfaces = ", ".join(record.technical_interfaces) or "—"
    return (
        '<tr data-contract-row><td><div class="contract-name">{}</div><div class="source">{}</div><span class="badge">{}</span></td>'
        "<td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>"
    ).format(
        _escape(record.name or record.contract_id or "Unnamed contract"),
        _escape(record.source_reference),
        _escape(record.status),
        _escape(domain_owner),
        _escape(interfaces),
        relationship_links,
        gap_text,
    )


def _relationship_id(relationship: ContractRelationship) -> str:
    """Return a stable safe anchor identifier for one relationship."""
    key = "|".join([relationship.kind, relationship.source_id, relationship.target_id])
    return sha256(key.encode("utf-8")).hexdigest()[:12]


def _relationship_detail(
    identifier: str,
    relationship: ContractRelationship,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render inspectable evidence for one relationship."""
    source = inventory.get(relationship.source_id)
    target = inventory.get(relationship.target_id)
    names = " ↔ ".join(
        _escape(item.name or item.contract_id or item.source_reference)
        for item in (source, target)
        if item is not None
    )
    why_it_matters, suggested_action = _relationship_action(relationship.kind)
    return (
        '<details id="relationship-{}"><summary>{}: {}</summary>'
        '<p class="evidence">{}</p><p class="evidence"><strong>Why it matters:</strong> {}</p>'
        '<p class="evidence"><strong>Suggested action:</strong> {}</p>'
        '<p class="evidence">Evidence class: {} · Score: {:.2f}</p></details>'
    ).format(
        _escape(identifier),
        _escape(relationship.kind.replace("_", " ")),
        names,
        _escape(relationship.rationale),
        _escape(why_it_matters),
        _escape(suggested_action),
        _escape(relationship.evidence_class),
        relationship.score,
    )


def _finding_detail(
    finding: IntelligenceFinding,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one expandable source-linked intelligence finding."""
    sources = ", ".join(
        _escape(
            inventory.get(
                identifier, ContractInventoryRecord("", identifier, "unknown")
            ).name
            or identifier
        )
        for identifier in finding.source_contract_ids
    )
    evidence = " ".join(_escape(item) for item in finding.evidence)
    return (
        '<details id="finding-{}"><summary>{}</summary><p class="evidence"><strong>Contracts:</strong> {}</p>'
        '<p class="evidence"><strong>Evidence:</strong> {}</p><p class="evidence"><strong>Why it matters:</strong> {}</p>'
        '<p class="evidence"><strong>Suggested action:</strong> {}</p></details>'
    ).format(
        _escape(finding.finding_id),
        _escape(finding.kind.replace("_", " ")),
        sources,
        evidence,
        _escape(finding.why_it_matters),
        _escape(finding.suggested_action),
    )


def _opportunity_card(
    candidate: ProductCandidate,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one proposed product opportunity without confirming it."""
    contracts = "".join(
        _opportunity_contract_record(index, identifier, inventory)
        for index, identifier in enumerate(candidate.supporting_contract_ids, start=1)
    )
    return (
        '<article class="evidence-card opportunity"><div class="label">{} · HUMAN REVIEW REQUIRED</div>'
        '<h3 class="finding-title"><span class="finding-accent" aria-hidden="true"></span>'
        "{}</h3>"
        '<div class="finding-contracts contract-group"><h4>{} ({})</h4>{}</div>'
        '<div class="finding-divider"></div><p class="evidence-copy"><strong>Evidence:</strong> {}</p>'
        '<div class="review-note"><strong>Missing business context:</strong> {}</div></article>'
    ).format(
        _escape(candidate.evidence_class),
        _escape(_opportunity_title(candidate)),
        _escape(_opportunity_contract_label(candidate)),
        len(candidate.supporting_contract_ids),
        contracts,
        _escape(candidate.rationale),
        _escape("; ".join(candidate.unresolved_questions)),
    )


def _opportunity_section(
    opportunity_type: str,
    title: str,
    description: str,
    candidates: Sequence[ProductCandidate],
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one explicit opportunity decision type."""
    cards = "".join(_opportunity_card(candidate, inventory) for candidate in candidates)
    if not cards:
        cards = (
            '<div class="empty-state"><strong>No {} detected</strong>'
            "<p>No contract currently meets this conservative evidence rule.</p></div>"
        ).format(_escape(title.lower()))
    return (
        '<section class="opportunity-section" data-opportunity-type="{}"><h3>{}</h3>'
        '<p class="opportunity-description">{}</p><div class="opportunities">{}</div></section>'
    ).format(_escape(opportunity_type), _escape(title), _escape(description), cards)


def _opportunity_title(candidate: ProductCandidate) -> str:
    """Return a decision-focused title for one opportunity type."""
    titles = {
        "standalone_product_candidate": "Standalone product candidate",
        "boundary_proposal": "Boundary proposal",
        "rationalisation_opportunity": "Rationalisation opportunity",
    }
    return titles.get(candidate.opportunity_type, "Product opportunity")


def _opportunity_contract_label(candidate: ProductCandidate) -> str:
    """Return the correct supporting-contract label for an opportunity."""
    if candidate.opportunity_type == "standalone_product_candidate":
        return "Supporting contract"
    return "Supporting contracts"


def _opportunity_contract_record(
    index: int,
    identifier: str,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one named source contract within a proposed group."""
    record = inventory.get(
        identifier, ContractInventoryRecord("", identifier, "unknown")
    )
    return (
        '<div class="contract-record"><span class="contract-number">Contract {}</span>'
        "<strong>{}</strong><span>{}</span></div>"
    ).format(
        index,
        _escape(record.name or record.contract_id or identifier),
        _escape(record.source_reference),
    )


def _unclassified_contract_row(record: ContractInventoryRecord) -> str:
    """Render one contract with no current opportunity signal."""
    return (
        '<tr><td><strong>{}</strong></td><td class="source">{}</td>'
        '<td class="unclassified-reason">No current standalone, boundary, or rationalisation signal.</td></tr>'
    ).format(
        _escape(record.name or record.contract_id or record.logical_id),
        _escape(record.source_reference),
    )


def _escape(value: object) -> str:
    """Escape a human-facing report value."""
    return html.escape(str(value), quote=True)
