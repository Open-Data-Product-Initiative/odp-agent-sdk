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
    ProductCandidate,
)

PathLike = Union[str, Path]
_CONTRACT_SUFFIXES = {".json", ".yaml", ".yml"}
_BUSINESS_QUESTIONS = [
    "Which business objective does this candidate support?",
    "Which consumer need justifies this product boundary?",
    "Who is accountable for approving ownership and scope?",
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
    return ContractInventoryRecord(
        logical_id=logical_id,
        source_reference=reference,
        status="loaded",
        contract_id=summary.contract_id,
        name=summary.name,
        version=summary.version,
        odcs_version=str(document.get("apiVersion")),
        domain=_text(document.get("domain")),
        owner=_text(document.get("owner")),
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
                continue
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
    candidates = [
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
        )
        for relationship in relationships
    ]
    return relationships, candidates


def _shared_capability_tokens(
    source: ContractInventoryRecord, target: ContractInventoryRecord
) -> List[str]:
    """Return meaningful shared name terms when contracts declare one domain."""
    if not source.domain or source.domain != target.domain:
        return []
    shared = sorted(_capability_tokens(source.name) & _capability_tokens(target.name))
    return shared if len(shared) >= 2 else []


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


def _write_artifacts(
    result: ContractDiscoveryResult, output: Path
) -> List[DiscoveryArtifact]:
    """Write deterministic JSON and a safe human-readable report."""
    output.mkdir(parents=True, exist_ok=True)
    inventory_path = output / "contract-inventory.json"
    candidates_path = output / "product-candidates.json"
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
        candidates_path,
        {
            "kind": "ProductCandidates",
            "source_id": result.source_id,
            "relationships": [item.to_dict() for item in result.relationships],
            "candidates": [item.to_dict() for item in result.candidates],
            "ai_proposals": [item.to_dict() for item in result.ai_proposals],
        },
    )
    report_path.write_text(_render_report(result), encoding="utf-8")
    return [
        DiscoveryArtifact("contract-inventory", "contract-inventory.json"),
        DiscoveryArtifact("product-candidates", "product-candidates.json"),
        DiscoveryArtifact("discovery-report", "discovery-report.html"),
    ]


def _write_json(path: Path, value: object) -> None:
    """Write sorted JSON with a terminal newline."""
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _render_report(result: ContractDiscoveryResult) -> str:
    """Render a small static review report without raw documents."""
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item.source_reference),
            html.escape(item.status),
            html.escape(item.name or ""),
        )
        for item in result.inventory
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>Contract discovery</title></head><body>"
        "<h1>Contract discovery</h1><table><thead>"
        "<tr><th>Source</th><th>Status</th><th>Name</th></tr>"
        "</thead><tbody>{}</tbody></table></body></html>".format(rows)
    )
