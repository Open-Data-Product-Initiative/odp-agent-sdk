"""SDK-owned result models for Data Contract workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


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

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


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
        data["validations"] = [
            validation.to_dict() for validation in self.validations
        ]
        data["summaries"] = [summary.to_dict() for summary in self.summaries]
        data["alignments"] = [alignment.to_dict() for alignment in self.alignments]
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data
