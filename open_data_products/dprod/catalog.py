"""DPROD inventory and conservative ODPS 4.2 conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS

from .._interop.odps_draft import (
    DraftDistribution,
    DraftResource,
    build_odps_draft,
)
from .._interop.rdf import load_graphs, safe_access_url
from ..agent import validate_document
from .models import (
    DprodCatalogResult,
    DprodProduct,
    DprodRelationship,
    DprodResource,
    DprodWrapResult,
)
from .validation import DPROD_NAMESPACE, _reject_unsupported_namespace, validate_dprod

DCAT = "http://www.w3.org/ns/dcat#"
ODRL = "http://www.w3.org/ns/odrl/2/"
PROV = "http://www.w3.org/ns/prov#"


def discover_dprod_catalog(source: str) -> DprodCatalogResult:
    """Inventory explicit DPROD products from safe RDF inputs only."""
    validation = validate_dprod(source)
    if validation.parse_errors:
        return DprodCatalogResult([], [], validation)
    products: Dict[str, DprodProduct] = {}
    resources: Dict[str, DprodResource] = {}
    relationships: List[DprodRelationship] = []
    sources: List[str] = []
    for graph, source_ref in load_graphs(source, label="DPROD source"):
        _reject_unsupported_namespace(graph)
        sources.append(source_ref)
        for resource in _inventory_resources(graph, source_ref):
            current = resources.get(resource.id)
            resources[resource.id] = (
                _merge_resource(current, resource) if current else resource
            )
        relationships.extend(_relationships(graph))
        for node in graph.subjects(RDF.type, URIRef(DPROD_NAMESPACE + "DataProduct")):
            product = _product(graph, node, source_ref)
            products[product.id] = _merge(products.get(product.id), product)
    return DprodCatalogResult(
        sorted(set(sources)),
        sorted(products.values(), key=lambda item: item.id),
        validation,
        sorted(resources.values(), key=lambda item: item.id),
        _unique_relationships(relationships),
    )


def wrap_dprod_resource(
    source: str,
    resource_id: str,
    output: Optional[str] = None,
    *,
    overwrite: bool = False,
) -> DprodWrapResult:
    """Create a conservative ODPS 4.2 draft from one explicit DPROD product."""
    inventory = discover_dprod_catalog(source)
    if not inventory.validation.conforms:
        raise ValueError(
            "DPROD source does not conform to the pinned Beta 2 SHACL profile"
        )
    product = next(
        (item for item in inventory.products if item.id == resource_id), None
    )
    if product is None:
        raise ValueError(
            "Selected DPROD DataProduct was not found in the supplied source"
        )
    resource = _as_draft_resource(source, product)
    document, base_report, warnings = build_odps_draft(
        resource, is_valid=lambda value: validate_document(value).valid
    )
    warnings.extend(_conversion_warnings(product))
    mappings = _dprod_to_odps_mappings(product, document)
    report = {
        "profile": "DPROD 1.0 Beta 2 to ODPS 4.2",
        "source_resource_identifier": product.id,
        "mappings": mappings,
        "base_dcat_draft_report": base_report,
        "semantic_equivalence": "not asserted",
    }
    output_path: Optional[str] = None
    if output:
        destination = Path(output)
        if destination.exists() and not overwrite:
            raise FileExistsError(
                "Refusing to overwrite existing output: " + str(destination)
            )
        import yaml

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
        )
        output_path = str(destination)
    return DprodWrapResult(
        source=source,
        resource_id=product.id,
        document=document,
        mapping_report=report,
        missing_business_information=[
            "consumer need and approved use cases",
            "value proposition",
            "data product owner",
            "operational commitments",
            "business KPIs",
        ],
        warnings=warnings,
        validation=validate_document(document),
        output=output_path,
    )


def _product(graph: Graph, node: object, source: str) -> DprodProduct:
    """Extract DPROD facts without inferring a product boundary."""
    return DprodProduct(
        id=str(node),
        source_documents=[source],
        labels=_literals(graph.objects(node, RDFS.label)),
        descriptions=_literals(graph.objects(node, DCTERMS.description)),
        purposes=_literals(graph.objects(node, URIRef(DPROD_NAMESPACE + "purpose"))),
        owners=_terms(
            graph.objects(node, URIRef(DPROD_NAMESPACE + "dataProductOwner"))
        ),
        domains=_terms(graph.objects(node, URIRef(DPROD_NAMESPACE + "domain"))),
        lifecycle_statuses=_terms(
            graph.objects(node, URIRef(DPROD_NAMESPACE + "lifecycleStatus"))
        ),
        input_ports=_terms(graph.objects(node, URIRef(DPROD_NAMESPACE + "inputPort"))),
        output_ports=_terms(
            graph.objects(node, URIRef(DPROD_NAMESPACE + "outputPort"))
        ),
        input_datasets=_terms(
            graph.objects(node, URIRef(DPROD_NAMESPACE + "inputDataset"))
        ),
        output_datasets=_terms(
            graph.objects(node, URIRef(DPROD_NAMESPACE + "outputDataset"))
        ),
        policies=_terms(graph.objects(node, URIRef(ODRL + "hasPolicy"))),
    )


def _inventory_resources(graph: Graph, source: str) -> Iterable[DprodResource]:
    """Yield typed product, data, service, distribution, agent, and policy nodes."""
    types = (
        (DPROD_NAMESPACE + "DataProduct", "DataProduct"),
        (DCAT + "Dataset", "Dataset"),
        (DCAT + "DataService", "DataService"),
        (DCAT + "Distribution", "Distribution"),
        (PROV + "Agent", "Agent"),
        (ODRL + "Policy", "Policy"),
    )
    for type_iri, resource_type in types:
        for node in graph.subjects(RDF.type, URIRef(type_iri)):
            yield DprodResource(
                id=str(node),
                resource_type=resource_type,
                source_documents=[source],
                labels=_literals(graph.objects(node, RDFS.label)),
                descriptions=_literals(graph.objects(node, DCTERMS.description)),
            )


def _relationships(graph: Graph) -> List[DprodRelationship]:
    """Return only links explicitly declared by the DPROD/DCAT source graph."""
    mappings = (
        (DPROD_NAMESPACE + "dataProductOwner", "product-owner"),
        (DPROD_NAMESPACE + "inputPort", "product-input-port"),
        (DPROD_NAMESPACE + "outputPort", "product-output-port"),
        (DPROD_NAMESPACE + "inputDataset", "product-input-dataset"),
        (DPROD_NAMESPACE + "outputDataset", "product-output-dataset"),
        (ODRL + "hasPolicy", "product-policy"),
        (DCAT + "distribution", "dataset-distribution"),
        (DCAT + "accessService", "distribution-service"),
        (DPROD_NAMESPACE + "isDistributionOf", "distribution-dataset"),
        (DPROD_NAMESPACE + "isAccessServiceOf", "service-distribution"),
        (DPROD_NAMESPACE + "protocol", "service-protocol"),
        (DPROD_NAMESPACE + "securitySchemaType", "service-security-schema"),
        (
            DPROD_NAMESPACE + "informationSensitivityClassification",
            "dataset-sensitivity-classification",
        ),
    )
    return [
        DprodRelationship(kind, str(subject), str(target), predicate)
        for predicate, kind in mappings
        for subject, target in graph.subject_objects(URIRef(predicate))
    ]


def _as_draft_resource(source: str, product: DprodProduct) -> DraftResource:
    """Project only compatible DPROD facts into the neutral draft builder."""
    graph = Graph()
    for loaded, _source_ref in load_graphs(source, label="DPROD source"):
        for triple in loaded:
            graph.add(triple)
    endpoints = []
    for port in product.output_ports:
        endpoints.extend(
            _terms(graph.objects(URIRef(port), URIRef(DCAT + "endpointURL")))
        )
    distributions = []
    for dataset in product.output_datasets:
        for distribution in graph.objects(
            URIRef(dataset), URIRef(DCAT + "distribution")
        ):
            distributions.append(
                DraftDistribution(
                    access_url=_first(
                        graph.objects(distribution, URIRef(DCAT + "accessURL"))
                    ),
                    download_url=_first(
                        graph.objects(distribution, URIRef(DCAT + "downloadURL"))
                    ),
                    format=_first(graph.objects(distribution, DCTERMS.format)),
                )
            )
    return DraftResource(
        id=product.id,
        source_documents=product.source_documents,
        titles={"und": product.labels},
        descriptions={"und": product.descriptions},
        themes=product.domains,
        distributions=distributions,
        service_urls=sorted(
            value for value in set(endpoints) if safe_access_url(value)
        ),
    )


def _conversion_warnings(product: DprodProduct) -> List[str]:
    """Report facts that cannot safely become ODPS promises."""
    warnings: List[str] = []
    if product.input_ports or product.output_ports:
        warnings.append(
            "DPROD port declarations are not assumed equivalent to ODPS data access profiles"
        )
    if product.purposes:
        warnings.append(
            "DPROD purpose is retained in mapping evidence; no ODPS business objective was manufactured"
        )
    if product.owners:
        warnings.append(
            "DPROD owner was not mapped without ODPS-compatible accountable-party details"
        )
    if product.policies:
        warnings.append(
            "DPROD ODRL policy references are retained as unsupported governance evidence"
        )
    return warnings


def _dprod_to_odps_mappings(
    product: DprodProduct, document: Dict[str, object]
) -> List[Dict[str, str]]:
    """Return versioned mapping transparency for each relevant source concept."""
    rules = [
        (
            "rdfs:label",
            "/product/details/en/name",
            "exact",
            "first source label",
            "label exists",
            "other labels retained in provenance",
        ),
        (
            "dct:description",
            "/product/details/en/description",
            "exact",
            "first source description",
            "description exists",
            "other descriptions retained in provenance",
        ),
        (
            "dprod:domain",
            "/product/details/en/categories",
            "conditional",
            "source IRI list",
            "domain is an IRI",
            "business semantics not established",
        ),
        (
            "dprod:outputPort",
            "/product/dataAccess/default",
            "conditional",
            "endpoint URL only",
            "credential-free HTTP(S) endpoint",
            "port semantics are not equivalent to access",
        ),
        (
            "dprod:purpose",
            "",
            "unsupported",
            "none",
            "",
            "ODPS objective approval is absent",
        ),
        (
            "dprod:dataProductOwner",
            "",
            "unsupported",
            "none",
            "ODPS accountable-party fields are incomplete",
            "owner role is not approved ownership",
        ),
        (
            "dprod:inputPort",
            "",
            "unsupported",
            "none",
            "",
            "ODPS has no equivalent input-port model",
        ),
        (
            "dprod:lifecycleStatus",
            "",
            "unsupported",
            "none",
            "",
            "lifecycle vocabulary has no safe ODPS status equivalence",
        ),
        (
            "dprod:informationSensitivityClassification",
            "",
            "partial",
            "retain in mapping evidence",
            "classification appears on an output dataset",
            "ODPS 4.2 has no like-for-like sensitivity classification field",
        ),
        (
            "dprod:protocol",
            "",
            "partial",
            "retain in mapping evidence",
            "protocol appears on an output service",
            "protocol does not establish an ODPS access contract",
        ),
        (
            "dprod:securitySchemaType",
            "",
            "unsupported",
            "none",
            "",
            "security schema does not establish ODPS access guarantees",
        ),
        (
            "odrl:hasPolicy",
            "",
            "unsupported",
            "none",
            "",
            "policy meaning is not mapped",
        ),
    ]
    return [
        {
            "source": source,
            "target": target,
            "classification": classification,
            "transformation_rule": rule,
            "preconditions": precondition,
            "information_loss": loss,
            "source_standard": "DPROD 1.0 Beta 2",
            "target_standard": "ODPS 4.2",
        }
        for source, target, classification, rule, precondition, loss in rules
    ]


def _terms(values: Iterable[object]) -> List[str]:
    """Return sorted unique RDF identifiers without stringifying structure early."""
    return sorted({str(item) for item in values})


def _literals(values: Iterable[object]) -> List[str]:
    """Return only literal values from RDF source facts."""
    return sorted({str(item) for item in values if isinstance(item, Literal)})


def _first(values: Iterable[object]) -> Optional[str]:
    """Return a stable first RDF value."""
    return next(iter(_terms(values)), None)


def _merge(first: Optional[DprodProduct], second: DprodProduct) -> DprodProduct:
    """Merge repeated product IRIs across supplied documents."""
    if first is None:
        return second
    fields = {
        "source_documents",
        "labels",
        "descriptions",
        "purposes",
        "owners",
        "domains",
        "lifecycle_statuses",
        "input_ports",
        "output_ports",
        "input_datasets",
        "output_datasets",
        "policies",
    }
    data = {name: getattr(first, name) for name in first.__dataclass_fields__}
    for name in fields:
        data[name] = sorted(set(getattr(first, name) + getattr(second, name)))
    return DprodProduct(**data)


def _merge_resource(first: DprodResource, second: DprodResource) -> DprodResource:
    """Merge repeated RDF resource identities across source documents."""
    return DprodResource(
        id=first.id,
        resource_type=first.resource_type,
        source_documents=sorted(set(first.source_documents + second.source_documents)),
        labels=sorted(set(first.labels + second.labels)),
        descriptions=sorted(set(first.descriptions + second.descriptions)),
    )


def _unique_relationships(
    relationships: Iterable[DprodRelationship],
) -> List[DprodRelationship]:
    """Return stable unique declared relationship records."""
    return sorted(
        set(relationships), key=lambda item: (item.kind, item.source, item.target)
    )
