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
        if relationship.kind == "shared_domain_capability"
    ]
    return relationships, candidates


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
        "proposed_product_groups": len(candidates),
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


def _render_report(result: ContractDiscoveryResult) -> str:
    """Render a self-contained evidence-led intelligence report."""
    inventory_by_id = {item.logical_id: item for item in result.inventory}
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
                "Proposed product groups",
                "proposed_product_groups",
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
    opportunity_cards = "".join(
        _opportunity_card(candidate, inventory_by_id)
        for candidate in list(result.candidates) + list(result.ai_proposals)
    )
    if not opportunity_cards:
        opportunity_cards = (
            '<div class="empty-state"><strong>No proposed product groups</strong>'
            "<p>This is not a failure. No relationship currently meets the "
            "conservative grouping rule; review contract metadata and evidence "
            "before proposing a product boundary.</p></div>"
        )
    return (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Contract Intelligence</title>
<style>
:root { color-scheme: light; --purple:#6D28D9; --purple-soft:#F3E8FF; --ink:#1F1530; --muted:#675D72; --line:#E7E0EB; --surface:#FFFFFF; --canvas:#FAF8FC; --warning:#A16207; --warning-bg:#FFFBEB; }
* { box-sizing:border-box; } body { margin:0; background:var(--canvas); color:var(--ink); font:15px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width:1240px; margin:auto; padding:36px 24px 56px; } header { display:flex; justify-content:space-between; align-items:end; gap:24px; border-bottom:1px solid var(--line); padding-bottom:22px; }
.eyebrow { margin:0 0 5px; color:var(--purple); font-size:12px; font-weight:800; letter-spacing:.1em; } h1 { margin:0; font-size:32px; line-height:1.15; letter-spacing:-.03em; } h2 { margin:0; font-size:21px; letter-spacing:-.015em; } .subtitle, .meta { color:var(--muted); } .meta { font-size:13px; white-space:nowrap; }
section { margin-top:30px; } .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:14px; } .metric { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:16px; } .metric strong { display:block; color:var(--purple); font-size:29px; line-height:1; } .metric span { display:block; font-weight:750; margin-top:9px; } .metric small { color:var(--muted); display:block; margin-top:3px; }
.summary { max-width:780px; margin:14px 0 0; color:var(--muted); } .explorer { background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow:hidden; } .toolbar { display:flex; justify-content:space-between; gap:16px; padding:16px; border-bottom:1px solid var(--line); } input { width:min(360px,100%); border:1px solid #CFC4D7; border-radius:7px; padding:9px 11px; font:inherit; } input:focus { outline:3px solid var(--purple-soft); border-color:var(--purple); }
.priority-findings { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:10px; margin-top:16px; } .priority-finding { background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--purple); border-radius:7px; padding:13px; } .priority-finding h4 { margin:0; font-size:15px; } .priority-contracts { margin:8px 0; color:var(--ink); font-size:13px; } .priority-contracts span { color:var(--muted); display:block; font-size:12px; overflow-wrap:anywhere; } .priority-evidence, .priority-action { color:var(--muted); display:block; font-size:13px; margin-top:6px; }
.tabs { display:flex; gap:4px; overflow:auto; margin-top:24px; border-bottom:1px solid var(--line); } [role="tab"] { appearance:none; background:transparent; border:0; border-bottom:3px solid transparent; color:var(--muted); cursor:pointer; font:inherit; font-weight:750; padding:11px 14px 9px; white-space:nowrap; } [role="tab"]:hover { color:var(--ink); } [role="tab"][aria-selected="true"] { border-color:var(--purple); color:var(--purple); } [role="tab"]:focus-visible { outline:3px solid var(--purple-soft); outline-offset:-3px; } [role="tabpanel"] { margin-top:24px; } [role="tabpanel"][hidden] { display:none; }
.table-wrap { overflow:auto; } table { width:100%; border-collapse:collapse; min-width:810px; } th { color:var(--muted); font-size:12px; letter-spacing:.04em; text-align:left; text-transform:uppercase; background:#FCFBFD; } th, td { padding:12px 16px; border-bottom:1px solid var(--line); vertical-align:top; } tr:last-child td { border-bottom:0; } .contract-name { font-weight:750; } .source { color:var(--muted); font-size:12px; overflow-wrap:anywhere; } .badge { display:inline-block; padding:2px 7px; border-radius:999px; background:var(--purple-soft); color:#5B21B6; font-size:12px; font-weight:750; }
.relationship-link { display:block; color:#5B21B6; font-size:13px; margin:2px 0; text-decoration:none; } .relationship-link:hover { text-decoration:underline; } .gap { color:var(--warning); font-size:13px; margin:2px 0; } .details { margin-top:14px; } details { background:var(--surface); border:1px solid var(--line); border-radius:8px; margin:8px 0; padding:12px 14px; } details:target { border-color:var(--purple); box-shadow:0 0 0 3px var(--purple-soft); } summary { cursor:pointer; font-weight:750; } .evidence { color:var(--muted); margin:8px 0 0; }
.opportunities { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:14px; margin-top:14px; } .opportunity, .empty-state { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:18px; } .opportunity { border-top:3px solid var(--purple); } .opportunity h3 { margin:0; font-size:18px; } .opportunity p { color:var(--muted); } .label { color:var(--purple); font-size:12px; font-weight:800; letter-spacing:.06em; } .contract-group { margin:12px 0; } .contract-group h4 { margin:0 0 7px; font-size:14px; } .contract-record { border-top:1px solid var(--line); padding:8px 0; } .contract-record:first-of-type { border-top:0; } .contract-number { color:var(--purple); font-size:12px; font-weight:800; letter-spacing:.05em; } .contract-record strong, .contract-record span { display:block; } .contract-record span { color:var(--muted); font-size:12px; overflow-wrap:anywhere; } .review-note { margin:12px 0 0; padding:10px; border-radius:7px; background:var(--warning-bg); color:#854D0E; font-size:13px; }
.legend { display:flex; flex-wrap:wrap; gap:16px; color:var(--muted); font-size:13px; margin-top:16px; } .legend b { color:var(--ink); } @media (max-width:760px) { main { padding:24px 14px 40px; } header { align-items:start; flex-direction:column; } .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); } .toolbar { flex-direction:column; } input { width:100%; } } @media (max-width:420px) { .metrics { grid-template-columns:1fr; } h1 { font-size:27px; } }
</style></head><body><main>
<header><div><p class="eyebrow">DATA CONTRACT INTELLIGENCE</p><h1>Portfolio discovery review</h1><p class="subtitle">Evidence-led contract intelligence. Product groups remain proposals until reviewed.</p></div><div class="meta">Source: __SOURCE__</div></header>
<div class="tabs" role="tablist" aria-label="Data Contract Intelligence views"><button id="tab-overview" role="tab" aria-selected="true" aria-controls="panel-overview">What the contracts reveal</button><button id="tab-priority-findings" role="tab" aria-selected="false" aria-controls="panel-priority-findings">Priority findings</button><button id="tab-explorer" role="tab" aria-selected="false" aria-controls="panel-explorer">Contract Intelligence Explorer</button><button id="tab-opportunities" role="tab" aria-selected="false" aria-controls="panel-opportunities">Product opportunities</button></div>
<section id="panel-overview" role="tabpanel" aria-labelledby="tab-overview"><p class="eyebrow">OVERVIEW</p><h2>What the contracts reveal</h2><div class="metrics">__METRICS__</div><p class="summary">__SUMMARY__</p></section>
<section id="panel-priority-findings" role="tabpanel" aria-labelledby="tab-priority-findings" hidden><p class="eyebrow">ACTIONABLE EVIDENCE</p><h2>Priority findings</h2><p class="summary">Each finding includes the contracts, source references, matching evidence, and next action.</p><div class="priority-findings">__PRIORITY_FINDINGS__</div></section>
<section id="panel-explorer" role="tabpanel" aria-labelledby="tab-explorer" hidden><p class="eyebrow">EXPLORE THE EVIDENCE</p><h2>Contract Intelligence Explorer</h2><p class="summary">Contracts, relationships, and missing information.</p><div class="explorer"><div class="toolbar"><span class="meta">Select a relationship or gap to inspect supporting evidence below.</span><label><span class="meta">Search</span><input id="contract-search" type="search" placeholder="Contract, domain, finding, or source"></label></div><div class="table-wrap"><table><thead><tr><th>Contract</th><th>Domain / owner</th><th>Interfaces</th><th>Relationships</th><th>Missing information</th></tr></thead><tbody id="contract-rows">__ROWS__</tbody></table></div></div><div class="details" aria-label="Relationship and finding evidence">__RELATIONSHIP_DETAILS____FINDING_DETAILS__</div></section>
<section id="panel-opportunities" role="tabpanel" aria-labelledby="tab-opportunities" hidden><p class="eyebrow">REVIEW ONLY</p><h2>Product Opportunities</h2><p class="summary">Proposed groups for human review.</p><div class="opportunities">__OPPORTUNITIES__</div><div class="legend"><span><b>Source fact</b> is declared in a contract.</span><span><b>Inference</b> is a repeatable analysis rule.</span><span><b>Proposal</b> needs a human decision.</span></div></section>
</main><script>
const tabs=[...document.querySelectorAll('[role="tab"]')]; const panels=[...document.querySelectorAll('[role="tabpanel"]')]; function activateTab(tab){tabs.forEach(item=>{const active=item===tab;item.setAttribute('aria-selected',String(active));document.getElementById(item.getAttribute('aria-controls')).hidden=!active;});} tabs.forEach(tab=>tab.addEventListener('click',()=>activateTab(tab))); const search=document.getElementById('contract-search'); const rows=[...document.querySelectorAll('#contract-rows tr')]; search.addEventListener('input',()=>{const term=search.value.toLowerCase().trim(); rows.forEach(row=>{row.hidden=term!==''&&!row.textContent.toLowerCase().includes(term);});});
</script></body></html>""".replace("__SOURCE__", _escape(result.source_id))
        .replace("__METRICS__", overview)
        .replace("__SUMMARY__", _escape(_report_summary(summary)))
        .replace("__PRIORITY_FINDINGS__", priority_findings)
        .replace("__ROWS__", rows)
        .replace("__RELATIONSHIP_DETAILS__", relationship_details)
        .replace("__FINDING_DETAILS__", finding_details)
        .replace("__OPPORTUNITIES__", opportunity_cards)
    )


def _metric_card(label: str, value: int, note: str) -> str:
    """Render one compact overview metric."""
    return '<div class="metric"><strong>{}</strong><span>{}</span><small>{}</small></div>'.format(
        value, _escape(label), _escape(note)
    )


def _priority_finding(
    finding: IntelligenceFinding,
    inventory: Mapping[str, ContractInventoryRecord],
) -> str:
    """Render one self-contained actionable finding in the overview."""
    contracts = "".join(
        "<div><strong>{}</strong><span>{}</span></div>".format(
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
        '<article class="priority-finding"><h4>{}</h4><div class="priority-contracts">{}</div>'
        '<span class="priority-evidence"><strong>Evidence:</strong> {}</span>'
        '<span class="priority-action"><strong>Next:</strong> {}</span></article>'
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
        '<article class="opportunity"><div class="label">{} · HUMAN REVIEW REQUIRED</div>'
        "<h3>Proposed grouping · {} contracts</h3><p>{}</p>"
        '<div class="contract-group"><h4>Contracts in this group ({})</h4>{}</div>'
        '<div class="review-note">Missing business context: {}</div></article>'
    ).format(
        _escape(candidate.evidence_class),
        len(candidate.supporting_contract_ids),
        _escape(candidate.rationale),
        len(candidate.supporting_contract_ids),
        contracts,
        _escape("; ".join(candidate.unresolved_questions)),
    )


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


def _escape(value: object) -> str:
    """Escape a human-facing report value."""
    return html.escape(str(value), quote=True)
