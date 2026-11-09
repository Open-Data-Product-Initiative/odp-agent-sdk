"""Neutral source metadata to conservative ODPS 4.2 draft conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .rdf import safe_access_url

_ODPS_V42_SCHEMA = "https://opendataproducts.org/v4.2/schema/odps.json"


@dataclass(frozen=True)
class DraftDistribution:
    """One source distribution usable for conservative access mapping."""

    access_url: Optional[str] = None
    download_url: Optional[str] = None
    format: Optional[str] = None


@dataclass(frozen=True)
class DraftResource:
    """Neutral source facts supported by the ODPS draft mapper."""

    id: str
    source_documents: List[str]
    titles: Dict[str, List[str]] = field(default_factory=dict)
    descriptions: Dict[str, List[str]] = field(default_factory=dict)
    identifiers: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    keywords: Dict[str, List[str]] = field(default_factory=dict)
    distributions: List[DraftDistribution] = field(default_factory=list)
    service_urls: List[str] = field(default_factory=list)


def build_odps_draft(
    resource: DraftResource,
    *,
    is_valid: Callable[[Dict[str, object]], bool],
) -> Tuple[Dict[str, object], Dict[str, object], List[str]]:
    """Map supported source metadata into a private ODPS draft only."""
    name = _first_localized(resource.titles) or _title_from_id(
        resource.identifiers[0] if resource.identifiers else resource.id
    )
    details: Dict[str, object] = {
        "productID": _slugify(
            resource.identifiers[0] if resource.identifiers else resource.id
        ),
        "name": name,
        "visibility": "private",
        "status": "draft",
        "type": "dataset",
    }
    description = _first_localized(resource.descriptions)
    if description:
        details["description"] = description
    tags = sorted({value for values in resource.keywords.values() for value in values})
    if tags:
        details["tags"] = tags
    if resource.themes:
        details["categories"] = resource.themes
    document: Dict[str, object] = {
        "schema": _ODPS_V42_SCHEMA,
        "version": "4.2",
        "product": {"details": {"en": details}},
    }
    warnings: List[str] = []
    access = _access_profile(resource)
    if access:
        product = document["product"]
        if isinstance(product, dict):
            product["dataAccess"] = {"default": access}
    elif resource.distributions or resource.service_urls:
        warnings.append(
            "DATA_ACCESS_OMITTED: source metadata did not establish a safe supported access profile"
        )
    mapped = [
        "identifier",
        "title",
        "description",
        "keywords",
        "themes",
        "distribution",
    ]
    report: Dict[str, object] = {
        "source_resource_identifier": resource.id,
        "source_catalog": resource.source_documents,
        "applied_mapping_rules": mapped,
        "mapped_fields": [
            item
            for item in mapped
            if item in {"identifier", "title"}
            or (item == "description" and description)
            or (item == "keywords" and tags)
            or (item == "themes" and resource.themes)
            or (item == "distribution" and access)
        ],
        "source_information_not_represented": [
            "source IRI",
            "publisher approval status",
            "multilingual values",
            "access-rights interpretation",
        ],
        "defaults_introduced": [
            "product.details.en.status=draft",
            "product.details.en.visibility=private",
            "product.details.en.type=dataset",
        ],
        "validation_result": "pending",
        "odpv_profile": "ODPV-DCAT-3 is draft and is not asserted as conformance",
    }
    report["validation_result"] = "valid" if is_valid(document) else "invalid"
    return document, report, warnings


def _access_profile(resource: DraftResource) -> Optional[Dict[str, object]]:
    """Map only an explicit HTTP(S) endpoint to ODPS data access."""
    for distribution in resource.distributions:
        if distribution.access_url and safe_access_url(distribution.access_url):
            profile: Dict[str, object] = {
                "outputPortType": "API",
                "accessURL": distribution.access_url,
            }
            if distribution.format in {"CSV", "JSON", "XML", "TOON"}:
                profile["format"] = distribution.format
            return profile
    for service_url in resource.service_urls:
        if safe_access_url(service_url):
            return {"outputPortType": "API", "accessURL": service_url}
    return None


def _first_localized(values: Dict[str, List[str]]) -> Optional[str]:
    """Return the first deterministic localized value."""
    for language in sorted(values):
        if values[language]:
            return values[language][0]
    return None


def _title_from_id(value: str) -> str:
    """Create a readable fallback name from an identifier."""
    return value.rstrip("/#").rsplit("/", 1)[-1].replace("-", " ").title()


def _slugify(value: str) -> str:
    """Create a deterministic conservative ODPS identifier."""
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in value
    )
    return "-".join(item for item in normalized.split("-") if item) or "draft-product"
