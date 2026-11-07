"""Discover review-only portfolio candidates from ODCS contracts."""

from __future__ import annotations

from hashlib import sha256
import html
import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

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
    client: object = None,
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
    result = ContractDiscoveryResult(
        source_id=root.name or "contracts",
        inventory=inventory,
        relationships=relationships,
        candidates=candidates,
        ai_enabled=use_ai,
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
        records.append(_inventory_record(path, root))
    return records


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
