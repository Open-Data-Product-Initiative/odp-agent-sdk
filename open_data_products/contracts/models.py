"""SDK-owned result models for Data Contract workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from ..results import ValidationResult


@dataclass(frozen=True)
class Finding:
    """A normalized contract finding."""

    code: str
    message: str
    severity: str
    path: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractToolAvailability:
    """Detected datacontract-cli adapter availability."""

    python_package: bool
    cli_executable: Optional[str] = None
    tool_version: Optional[str] = None

    @property
    def available(self) -> bool:
        """Return whether any supported adapter path is available."""
        return self.python_package or self.cli_executable is not None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["available"] = self.available
        return data


@dataclass(frozen=True)
class ContractValidationResult:
    """Normalized result for static Data Contract validation."""

    passed: bool
    tool: str
    tool_version: Optional[str] = None
    contract_format: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)
    raw: Optional[object] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data


@dataclass(frozen=True)
class ContractExportResult:
    """Normalized result for Data Contract export."""

    exported: bool
    format: str
    content: object = None
    tool: str = "datacontract-cli"
    tool_version: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)
    raw: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data


@dataclass(frozen=True)
class ContractSchemaField:
    """Normalized Data Contract schema field."""

    name: str
    type: Optional[str] = None
    required: bool = False
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractSchemaModel:
    """Normalized Data Contract schema model."""

    name: str
    fields: List[ContractSchemaField] = field(default_factory=list)
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["fields"] = [field.to_dict() for field in self.fields]
        return data


@dataclass(frozen=True)
class ContractSchemaSummary:
    """Normalized schema summary extracted from a Data Contract."""

    path: str
    contract_format: Optional[str]
    models: List[ContractSchemaModel] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

    @property
    def model_count(self) -> int:
        """Return the number of schema models."""
        return len(self.models)

    @property
    def field_count(self) -> int:
        """Return the number of schema fields."""
        return sum(len(model.fields) for model in self.models)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["models"] = [model.to_dict() for model in self.models]
        data["findings"] = [finding.to_dict() for finding in self.findings]
        data["model_count"] = self.model_count
        data["field_count"] = self.field_count
        return data


@dataclass(frozen=True)
class ContractDocument:
    """Loaded external Data Contract document."""

    path: str
    document: Dict[str, object]
    contract_format: Optional[str] = None
    source: Optional[str] = None
    resolved_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractInventoryRecord:
    """Technical evidence found for one source contract."""

    logical_id: str
    source_reference: str
    status: str
    contract_id: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    odcs_version: Optional[str] = None
    domain: Optional[str] = None
    owner: Optional[str] = None
    lifecycle_status: Optional[str] = None
    purpose: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    model_count: int = 0
    field_count: int = 0
    fingerprint: Optional[str] = None
    schema_signature: List[str] = field(default_factory=list)
    validation_status: str = "unavailable"
    findings: List[Finding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data


@dataclass(frozen=True)
class ContractRelationship:
    """Evidence-backed relationship between discovered contracts."""

    source_id: str
    target_id: str
    kind: str
    evidence_class: str
    rationale: str
    score: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class IntelligenceFinding:
    """One source-linked finding from contract intelligence analysis."""

    finding_id: str
    category: str
    kind: str
    evidence_class: str
    source_contract_ids: List[str]
    rationale: str
    score: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ProductCandidate:
    """Review-only grouping candidate derived from technical evidence."""

    candidate_id: str
    status: str
    evidence_class: str
    supporting_contract_ids: List[str]
    rationale: str
    unresolved_questions: List[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class DiscoveryArtifact:
    """Logical metadata for one generated discovery artifact."""

    artifact_id: str
    kind: str

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractDiscoveryResult:
    """Result of one contract portfolio discovery run."""

    source_id: str
    inventory: List[ContractInventoryRecord]
    relationships: List[ContractRelationship]
    candidates: List[ProductCandidate]
    intelligence_findings: List[IntelligenceFinding] = field(default_factory=list)
    intelligence_summary: Dict[str, int] = field(default_factory=dict)
    source_status: str = "loaded"
    artifacts: List[DiscoveryArtifact] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    ai_enabled: bool = False
    ai_proposals: List[ProductCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "kind": "ContractDiscovery",
            "source_id": self.source_id,
            "source_status": self.source_status,
            "inventory": [item.to_dict() for item in self.inventory],
            "relationships": [item.to_dict() for item in self.relationships],
            "intelligence_findings": [
                item.to_dict() for item in self.intelligence_findings
            ],
            "intelligence_summary": dict(self.intelligence_summary),
            "candidates": [item.to_dict() for item in self.candidates],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "warnings": list(self.warnings),
            "ai_enabled": self.ai_enabled,
            "ai_proposals": [item.to_dict() for item in self.ai_proposals],
        }


@dataclass(frozen=True)
class ContractMappedField:
    """One deterministic ODCS-to-ODPS field mapping."""

    source: str
    target: str
    value: str

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractWrapProposal:
    """An unconfirmed business-layer proposal from optional enrichment."""

    field: str
    value: str
    provenance: str = "ai"
    review_status: str = "proposed"

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractWrapResult:
    """Structured result for an ODCS-to-ODPS product draft."""

    source: str
    resolved_uri: str
    source_standard: str
    source_specification_version: str
    contract_id: Optional[str]
    contract_instance_version: Optional[str]
    target_odps_version: str
    output: Optional[str]
    inline_contract: bool
    ai_enabled: bool
    ai_enriched: bool
    document: Dict[str, object]
    mapped_fields: List[ContractMappedField] = field(default_factory=list)
    provisional_defaults: List[str] = field(default_factory=list)
    missing_business_information: List[str] = field(default_factory=list)
    ai_proposals: List[ContractWrapProposal] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(False, "odps", "OpenDataProduct")
    )

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "source": self.source,
            "resolved_uri": self.resolved_uri,
            "source_standard": self.source_standard,
            "source_specification_version": self.source_specification_version,
            "contract_id": self.contract_id,
            "contract_instance_version": self.contract_instance_version,
            "target_odps_version": self.target_odps_version,
            "output": self.output,
            "inline_contract": self.inline_contract,
            "ai_enabled": self.ai_enabled,
            "ai_enriched": self.ai_enriched,
            "document": self.document,
            "mapped_fields": [item.to_dict() for item in self.mapped_fields],
            "provisional_defaults": list(self.provisional_defaults),
            "missing_business_information": list(self.missing_business_information),
            "ai_proposals": [item.to_dict() for item in self.ai_proposals],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "validation": self.validation.to_dict(),
        }


@dataclass(frozen=True)
class ContractSummary:
    """Compact Data Contract summary for humans and agents."""

    path: str
    contract_format: Optional[str]
    contract_id: Optional[str]
    name: Optional[str]
    version: Optional[str]
    model_count: int
    field_count: int
    server_count: int

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ContractReference:
    """Reference from an ODP product to an external Data Contract."""

    href: str
    pointer: str
    format: Optional[str] = None
    inline_spec: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class AlignmentFinding:
    """A product-to-contract alignment finding."""

    code: str
    message: str
    severity: str
    odps_path: Optional[str] = None
    contract_path: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ProductContractAlignmentResult:
    """Static ODPS-to-Data Contract alignment result."""

    passed: bool
    product_valid: bool
    contract_valid: bool
    contract_tests_run: bool
    findings: List[AlignmentFinding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data


@dataclass(frozen=True)
class ProductContractReport:
    """Static product-level Data Contract report."""

    passed: bool
    product_valid: bool
    contract_count: int
    contract_valid: bool
    contract_tests_run: bool
    references: List[ContractReference] = field(default_factory=list)
    validations: List[ContractValidationResult] = field(default_factory=list)
    summaries: List[ContractSummary] = field(default_factory=list)
    alignments: List[ProductContractAlignmentResult] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["references"] = [reference.to_dict() for reference in self.references]
        data["validations"] = [validation.to_dict() for validation in self.validations]
        data["summaries"] = [summary.to_dict() for summary in self.summaries]
        data["alignments"] = [alignment.to_dict() for alignment in self.alignments]
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data
