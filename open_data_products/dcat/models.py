"""Structured results for DCAT catalog intelligence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from ..results import ValidationResult


@dataclass(frozen=True)
class DcatDistribution:
    """One DCAT distribution attached to a resource."""

    id: str
    access_url: Optional[str] = None
    download_url: Optional[str] = None
    media_type: Optional[str] = None
    format: Optional[str] = None
    license: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DcatResource:
    """A normalized DCAT catalog resource."""

    id: str
    resource_type: str
    source_documents: List[str]
    titles: Dict[str, List[str]] = field(default_factory=dict)
    descriptions: Dict[str, List[str]] = field(default_factory=dict)
    identifiers: List[str] = field(default_factory=list)
    publisher: Optional[str] = None
    themes: List[str] = field(default_factory=list)
    keywords: Dict[str, List[str]] = field(default_factory=dict)
    languages: List[str] = field(default_factory=list)
    distributions: List[DcatDistribution] = field(default_factory=list)
    service_urls: List[str] = field(default_factory=list)
    license: Optional[str] = None
    access_rights: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        data = asdict(self)
        data["distributions"] = [item.to_dict() for item in self.distributions]
        return data


@dataclass(frozen=True)
class DcatRelationship:
    """A declared or derived catalog relationship."""

    kind: str
    source: str
    target: str
    evidence_level: str
    evidence: List[str]

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DcatFinding:
    """An evidence-bounded catalog intelligence finding."""

    id: str
    category: str
    evidence_level: str
    related_resources: List[str]
    explanation: str
    evidence: List[str]
    suggested_next_step: str

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DcatWrapProposal:
    """One review-required AI enrichment proposal."""

    field: str
    value: str
    provenance: str = "ai"
    review_status: str = "proposed"

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True)
class DcatCatalogIntelligenceResult:
    """Normalized DCAT inventory, relationships, and findings."""

    sources: List[str]
    resources: List[DcatResource]
    relationships: List[DcatRelationship]
    findings: List[DcatFinding]
    product_opportunities: List[DcatFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return {
            "sources": list(self.sources),
            "resources": [item.to_dict() for item in self.resources],
            "relationships": [item.to_dict() for item in self.relationships],
            "findings": [item.to_dict() for item in self.findings],
            "product_opportunities": [
                item.to_dict() for item in self.product_opportunities
            ],
        }


@dataclass(frozen=True)
class DcatWrapResult:
    """A conservative DCAT-to-ODPS 4.2 draft result."""

    source: str
    resource_id: str
    document: Dict[str, object]
    mapping_report: Dict[str, object]
    missing_business_information: List[str]
    warnings: List[str]
    validation: ValidationResult
    output: Optional[str] = None
    ai_enabled: bool = False
    ai_enriched: bool = False
    ai_proposals: List[DcatWrapProposal] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return JSON-compatible data."""
        return {
            "source": self.source,
            "resource_id": self.resource_id,
            "document": self.document,
            "mapping_report": self.mapping_report,
            "missing_business_information": list(self.missing_business_information),
            "warnings": list(self.warnings),
            "validation": self.validation.to_dict(),
            "output": self.output,
            "ai_enabled": self.ai_enabled,
            "ai_enriched": self.ai_enriched,
            "ai_proposals": [item.to_dict() for item in self.ai_proposals],
        }
