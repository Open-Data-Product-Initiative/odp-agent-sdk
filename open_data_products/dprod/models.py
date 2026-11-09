"""Structured DPROD 1.0 Beta 2 validation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from ..results import ValidationResult


@dataclass(frozen=True)
class DprodViolation:
    """One SHACL result from the pinned normative profile."""

    severity: str
    source_node: str
    property_path: str
    message: str
    product_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DprodValidationResult:
    """Offline DPROD parsing and SHACL validation result."""

    conforms: bool
    profile_version: str = "1.0 Beta 2"
    violations: List[DprodViolation] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    semantic_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return {
            "conforms": self.conforms,
            "profile_version": self.profile_version,
            "violations": [item.to_dict() for item in self.violations],
            "parse_errors": list(self.parse_errors),
            "semantic_warnings": list(self.semantic_warnings),
        }


@dataclass(frozen=True)
class DprodProduct:
    """One explicit DPROD data product and its declared links."""

    id: str
    source_documents: List[str]
    labels: List[str] = field(default_factory=list)
    descriptions: List[str] = field(default_factory=list)
    purposes: List[str] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    lifecycle_statuses: List[str] = field(default_factory=list)
    input_ports: List[str] = field(default_factory=list)
    output_ports: List[str] = field(default_factory=list)
    input_datasets: List[str] = field(default_factory=list)
    output_datasets: List[str] = field(default_factory=list)
    policies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DprodResource:
    """One normalized DPROD or linked RDF resource."""

    id: str
    resource_type: str
    source_documents: List[str]
    labels: List[str] = field(default_factory=list)
    descriptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DprodRelationship:
    """One source-declared DPROD relationship."""

    kind: str
    source: str
    target: str
    evidence: str

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DprodCatalogResult:
    """Explicit DPROD product inventory from supplied RDF documents."""

    sources: List[str]
    products: List[DprodProduct]
    validation: DprodValidationResult
    resources: List[DprodResource] = field(default_factory=list)
    relationships: List[DprodRelationship] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return {
            "sources": list(self.sources),
            "products": [item.to_dict() for item in self.products],
            "validation": self.validation.to_dict(),
            "resources": [item.to_dict() for item in self.resources],
            "relationships": [item.to_dict() for item in self.relationships],
        }


@dataclass(frozen=True)
class DprodWrapResult:
    """A traceable DPROD-to-ODPS draft conversion result."""

    source: str
    resource_id: str
    document: Dict[str, object]
    mapping_report: Dict[str, object]
    missing_business_information: List[str]
    warnings: List[str]
    validation: ValidationResult
    output: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DprodExportResult:
    """A deterministic ODPS-to-DPROD representation and loss report."""

    turtle: str
    jsonld: str
    validation: DprodValidationResult
    mappings: List[Dict[str, str]]
    losses: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)
