"""RDF-backed DCAT inventory, intelligence, and ODPS draft conversion."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import ssl
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, build_opener

import certifi
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, FOAF, RDF, RDFS

from ..agent import validate_document
from .models import (
    DcatCatalogIntelligenceResult,
    DcatDistribution,
    DcatFinding,
    DcatRelationship,
    DcatResource,
    DcatWrapProposal,
    DcatWrapResult,
)

DCAT = "http://www.w3.org/ns/dcat#"
ADMS = "http://www.w3.org/ns/adms#"
DPROD = "https://www.omg.org/spec/DPROD/"
_UNSUPPORTED_DPROD_NAMESPACE = "https://www.omg.org/spec/DPROD/dprod/"
_HTTP_TIMEOUT_SECONDS = 10.0
_MAX_HTTP_DOCUMENT_BYTES = 5 * 1024 * 1024
_MAX_HTTP_REDIRECTS = 3
_RDF_SUFFIXES = {".rdf", ".xml", ".ttl", ".jsonld", ".json-ld", ".nt", ".n3"}
_CREDENTIAL_QUERY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "jwt",
)
_ODPS_V42_SCHEMA = "https://opendataproducts.org/v4.2/schema/odps.json"


def discover_dcat_catalog(source: str) -> DcatCatalogIntelligenceResult:
    """Analyze local or bounded remote DCAT RDF without crawling references."""
    graphs = _load_graphs(source)
    resources: Dict[str, DcatResource] = {}
    relationships: List[DcatRelationship] = []
    for graph, source_ref in graphs:
        _reject_unsupported_dprod_namespace(graph)
        for node, resource_type in _resource_nodes(graph):
            resource = _resource(graph, node, resource_type, source_ref)
            existing = resources.get(resource.id)
            if existing is None:
                resources[resource.id] = resource
            else:
                resources[resource.id] = _merge_resource(existing, resource)
            relationships.extend(_declared_relationships(graph, node, resource.id))
    inventory = sorted(resources.values(), key=lambda item: item.id)
    unique_relationships = _unique_relationships(relationships)
    findings, opportunities = _findings(inventory, unique_relationships)
    return DcatCatalogIntelligenceResult(
        sources=sorted({source_ref for _, source_ref in graphs}),
        resources=inventory,
        relationships=unique_relationships,
        findings=findings,
        product_opportunities=opportunities,
    )


def _reject_unsupported_dprod_namespace(graph: Graph) -> None:
    """Avoid silently treating a development DPROD vocabulary as Beta 2."""
    for subject, predicate, obj in graph:
        if any(
            _UNSUPPORTED_DPROD_NAMESPACE in str(value)
            for value in (subject, predicate, obj)
        ):
            raise ValueError(
                "Unsupported DPROD namespace: " + _UNSUPPORTED_DPROD_NAMESPACE
            )


def wrap_dcat_resource(
    source: str,
    resource_id: str,
    output: Optional[str] = None,
    *,
    overwrite: bool = False,
    use_ai: bool = False,
    extend: bool = False,
    config: Optional[str] = None,
    client: Optional[Callable[[str, str], str]] = None,
    model: Optional[str] = None,
) -> DcatWrapResult:
    """Create one schema-valid ODPS 4.2 draft from a selected DCAT resource."""
    intelligence = discover_dcat_catalog(source)
    resource = next(
        (item for item in intelligence.resources if item.id == resource_id), None
    )
    if resource is None:
        raise ValueError("Selected DCAT resource was not found in the supplied catalog")
    if resource.resource_type not in {"Dataset", "DatasetSeries", "DataService"}:
        raise ValueError("Only Dataset, DatasetSeries, and DataService can be wrapped")
    document, mapping_report, warnings = _odps_draft(resource, intelligence)
    proposals: List[DcatWrapProposal] = []
    ai_enriched = False
    if extend and not use_ai:
        raise ValueError("extend=True requires use_ai=True")
    if use_ai:
        try:
            proposals = _generate_ai_proposals(
                resource, client=client, model=model, config=config, extend=extend
            )
            ai_enriched = True
            _apply_ai_proposals(document, proposals, warnings)
            mapping_report["ai_generated_fields"] = [item.field for item in proposals]
        except Exception as exc:
            warnings.append("AI_ENRICHMENT_FAILED: {}".format(type(exc).__name__))
    else:
        mapping_report["ai_generated_fields"] = []
    validation = validate_document(document)
    output_path: Optional[str] = None
    if output:
        destination = Path(output)
        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"Refusing to overwrite existing output: {destination}. "
                "Pass overwrite=True to replace it."
            )
        import yaml

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        output_path = str(destination)
    return DcatWrapResult(
        source=source,
        resource_id=resource.id,
        document=document,
        mapping_report=mapping_report,
        missing_business_information=[
            "business objective",
            "consumer need and approved use cases",
            "value proposition",
            "approved product owner",
            "product lifecycle decisions",
            "operational commitments",
            "business KPIs",
        ],
        warnings=warnings,
        validation=validation,
        output=output_path,
        ai_enabled=use_ai,
        ai_enriched=ai_enriched,
        ai_proposals=proposals,
    )


def wrap_dcat_resources(
    source: str,
    resource_ids: Sequence[str],
    output: str,
    *,
    overwrite: bool = False,
    use_ai: bool = False,
    extend: bool = False,
    config: Optional[str] = None,
    client: Optional[Callable[[str, str], str]] = None,
    model: Optional[str] = None,
) -> List[DcatWrapResult]:
    """Write one ODPS draft per explicitly selected DCAT resource."""
    if not resource_ids:
        raise ValueError("Select at least one DCAT resource")
    destination = Path(output)
    if destination.exists() and not destination.is_dir():
        raise ValueError("Batch DCAT output must be a directory")
    destination.mkdir(parents=True, exist_ok=True)
    return [
        wrap_dcat_resource(
            source,
            resource_id,
            str(destination / (_slugify(resource_id) + ".yaml")),
            overwrite=overwrite,
            use_ai=use_ai,
            extend=extend,
            config=config,
            client=client,
            model=model,
        )
        for resource_id in resource_ids
    ]


def render_dcat_catalog_html(result: DcatCatalogIntelligenceResult) -> str:
    """Render a self-contained, searchable, evidence-labelled HTML report."""
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item.id),
            html.escape(item.resource_type),
            html.escape(item.publisher or "—"),
            html.escape(
                ", ".join(value for values in item.titles.values() for value in values)
                or "—"
            ),
        )
        for item in result.resources
    )
    finding_rows = (
        "".join(
            "<article><strong>{}</strong> <span>{}</span><p>{}</p><small>{}</small></article>".format(
                html.escape(item.category),
                html.escape(item.evidence_level),
                html.escape(item.explanation),
                html.escape("; ".join(item.evidence)),
            )
            for item in result.findings + result.product_opportunities
        )
        or "<p>No actionable findings were supported by the supplied metadata.</p>"
    )
    datasets = sum(item.resource_type == "Dataset" for item in result.resources)
    services = sum(item.resource_type == "DataService" for item in result.resources)
    template = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>DCAT Catalog Intelligence</title><style>:root{color-scheme:light;--ink:#17212b;--muted:#5e6872;--accent:#7436eb;--line:#dce3e8;--surface:#fff;--canvas:#fafbfc}*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;color:var(--ink);background:var(--canvas);margin:0}main{max-width:1180px;margin:auto;padding:42px 24px 72px}h1{font-size:2.7rem;letter-spacing:-.05em;margin:0}h2{margin-top:56px;color:#18093a;font-size:1.65rem}.lede{max-width:760px;color:var(--muted);font-size:1.08rem}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:26px}.metric,article,.explorer{background:var(--surface);border:1px solid var(--line);border-radius:14px}.metric{padding:20px}.metric strong{display:block;color:var(--accent);font-size:2rem}.metric span{color:var(--muted)}.toolbar{display:flex;justify-content:space-between;gap:16px;padding:18px}.toolbar input{width:min(360px,100%);font:inherit;padding:9px 12px;border:1px solid var(--line);border-radius:8px}table{width:100%;border-collapse:collapse}th,td{padding:12px 16px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-size:.78rem;text-transform:uppercase}article{border-left:4px solid var(--accent);padding:18px;margin:12px 0}article span{color:var(--muted);margin-left:8px;font-size:.9rem}small{color:var(--muted)}@media(max-width:700px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.toolbar{display:block}.toolbar input{margin-top:10px;width:100%}} </style></head><body><main><header><p>ODPS · EVIDENCE-BOUNDED REVIEW</p><h1>DCAT Catalog Intelligence</h1><p class="lede">Source facts, repeatable inferences, and review-only product proposals are shown separately. Parsing metadata does not establish DCAT-AP conformance or an approved product boundary.</p></header><section aria-labelledby="overview"><h2 id="overview">Overview</h2><div class="metrics"><div class="metric"><strong>__RESOURCES__</strong><span>Resources analyzed</span></div><div class="metric"><strong>__DATASETS__</strong><span>Datasets</span></div><div class="metric"><strong>__SERVICES__</strong><span>Data services</span></div><div class="metric"><strong>__RELATIONSHIPS__</strong><span>Declared relationships</span></div></div></section><section aria-labelledby="explorer"><h2 id="explorer">Catalog Explorer</h2><div class="explorer"><div class="toolbar"><span>Filter resource identity, type, publisher, or title.</span><input id="catalog-search" type="search" placeholder="Search catalog"></div><div style="overflow:auto"><table><thead><tr><th>Resource</th><th>Type</th><th>Publisher</th><th>Title</th></tr></thead><tbody id="catalog-rows">__ROWS__</tbody></table></div></div></section><section aria-labelledby="findings"><h2 id="findings">Intelligence Findings</h2>__FINDINGS__</section><section aria-labelledby="opportunities"><h2 id="opportunities">Product Opportunities</h2><p class="lede">Proposals identify evidence worth reviewing. They do not establish value, ownership, consumer need, or approval.</p>__OPPORTUNITIES__</section></main><script>const input=document.getElementById('catalog-search');const rows=[...document.querySelectorAll('#catalog-rows tr')];input.addEventListener('input',()=>{const term=input.value.toLowerCase().trim();rows.forEach(row=>row.hidden=Boolean(term)&&!row.textContent.toLowerCase().includes(term));});</script></body></html>"""
    return (
        template.replace("__RESOURCES__", str(len(result.resources)))
        .replace("__DATASETS__", str(datasets))
        .replace("__SERVICES__", str(services))
        .replace("__RELATIONSHIPS__", str(len(result.relationships)))
        .replace("__ROWS__", rows)
        .replace("__FINDINGS__", finding_rows)
        .replace(
            "__OPPORTUNITIES__",
            "".join(
                "<article><strong>{}</strong> <span>proposal</span><p>{}</p><small>{}</small></article>".format(
                    html.escape(item.category),
                    html.escape(item.explanation),
                    html.escape("; ".join(item.evidence)),
                )
                for item in result.product_opportunities
            )
            or "<p>No product opportunity is supported by the supplied metadata.</p>",
        )
    )


def _load_graphs(source: str) -> List[Tuple[Graph, str]]:
    """Load one file, directory, file URI, or bounded HTTP(S) RDF source."""
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        text, resolved = _load_remote(source)
        return [(_parse_rdf(text, _rdf_format(resolved)), resolved)]
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("DCAT file URI must reference the local host")
        return _load_local(Path(unquote(parsed.path)))
    if parsed.scheme:
        raise ValueError("Unsupported DCAT URI scheme")
    return _load_local(Path(source))


def _load_local(path: Path) -> List[Tuple[Graph, str]]:
    """Load supported RDF files without following linked resources."""
    paths = (
        sorted(item for item in path.iterdir() if item.suffix.lower() in _RDF_SUFFIXES)
        if path.is_dir()
        else [path]
    )
    if not paths:
        raise ValueError("No supported RDF files were found")
    loaded: List[Tuple[Graph, str]] = []
    for item in paths:
        if not item.is_file():
            continue
        text = item.read_text(encoding="utf-8")
        loaded.append(
            (_parse_rdf(text, _rdf_format(str(item))), item.resolve().as_uri())
        )
    return loaded


def _load_remote(source: str) -> Tuple[str, str]:
    """Retrieve one bounded public catalog document over HTTP(S)."""
    safe_source = _safe_http_uri(source)
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(
            HTTPSHandler(context=context), _BoundedRedirectHandler(_MAX_HTTP_REDIRECTS)
        )
        with opener.open(safe_source, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            payload = response.read(_MAX_HTTP_DOCUMENT_BYTES + 1)
            resolved = _safe_http_uri(str(response.geturl()))
    except (HTTPError, URLError, OSError, ValueError):
        raise ValueError("Could not load remote DCAT catalog") from None
    if len(payload) > _MAX_HTTP_DOCUMENT_BYTES:
        raise ValueError("Remote DCAT catalog response exceeds the maximum size")
    try:
        return payload.decode("utf-8"), resolved
    except UnicodeDecodeError:
        raise ValueError("Remote DCAT catalog is not UTF-8") from None


class _BoundedRedirectHandler(HTTPRedirectHandler):
    """Follow only a small number of credential-free HTTP redirects."""

    def __init__(self, maximum: int) -> None:
        super().__init__()
        self._maximum = maximum
        self._count = 0

    def redirect_request(  # type: ignore[override]
        self,
        request: object,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> object:
        """Reject excessive or credential-bearing redirect destinations."""
        self._count += 1
        if self._count > self._maximum:
            raise ValueError("Remote DCAT catalog redirect limit exceeded")
        return super().redirect_request(
            request, file_pointer, code, message, headers, _safe_http_uri(new_url)
        )


def _parse_rdf(text: str, rdf_format: Optional[str]) -> Graph:
    """Parse RDF text while refusing network-loaded JSON-LD contexts."""
    if rdf_format == "json-ld":
        _reject_remote_jsonld_context(text)
    graph = Graph()
    try:
        graph.parse(data=text, format=rdf_format)
    except Exception as exc:
        raise ValueError("DCAT source is not valid supported RDF") from exc
    return graph


def _reject_remote_jsonld_context(text: str) -> None:
    """Reject JSON-LD documents that would dereference external contexts."""
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("DCAT JSON-LD is not valid JSON") from exc
    contexts = _contexts(document)
    if any(
        isinstance(value, str) and urlparse(value).scheme in {"http", "https"}
        for value in contexts
    ):
        raise ValueError("Remote JSON-LD contexts are not supported")


def _contexts(value: object) -> Iterable[object]:
    """Yield JSON-LD context declarations recursively."""
    if isinstance(value, dict):
        if "@context" in value:
            context = value["@context"]
            yield from context if isinstance(context, list) else [context]
        for item in value.values():
            yield from _contexts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _contexts(item)


def _rdf_format(source: str) -> Optional[str]:
    """Infer an RDFLib parser format from a source suffix."""
    suffix = Path(urlparse(source).path).suffix.lower()
    return {
        ".ttl": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".jsonld": "json-ld",
        ".json-ld": "json-ld",
        ".nt": "nt",
        ".n3": "n3",
    }.get(suffix)


def _resource_nodes(graph: Graph) -> Iterable[Tuple[object, str]]:
    """Yield recognized DCAT resources, excluding distributions from inventory."""
    types = (
        ("DPRODDataProduct", "DPRODDataProduct"),
        ("Catalog", "Catalog"),
        ("Dataset", "Dataset"),
        ("DatasetSeries", "DatasetSeries"),
        ("DataService", "DataService"),
        ("CatalogRecord", "CatalogRecord"),
    )
    for local, label in types:
        namespace = DPROD if local == "DPRODDataProduct" else DCAT
        type_name = "DataProduct" if local == "DPRODDataProduct" else local
        for node in graph.subjects(RDF.type, URIRef(namespace + type_name)):
            yield node, label


def _resource(
    graph: Graph, node: object, resource_type: str, source: str
) -> DcatResource:
    """Extract a normalized DCAT resource without collapsing language values."""
    distributions = [
        _distribution(graph, item)
        for item in graph.objects(node, URIRef(DCAT + "distribution"))
    ]
    services = [
        _node_id(graph, item)
        for item in graph.objects(node, URIRef(DCAT + "accessService"))
    ]
    if resource_type == "DataService":
        services.extend(_texts(graph.objects(node, URIRef(DCAT + "endpointURL"))))
    return DcatResource(
        id=_node_id(graph, node),
        resource_type=resource_type,
        source_documents=[source],
        titles=_localized(
            graph.objects(node, RDFS.label)
            if resource_type == "DPRODDataProduct"
            else graph.objects(node, DCTERMS.title)
        ),
        descriptions=_localized(graph.objects(node, DCTERMS.description)),
        identifiers=_texts(graph.objects(node, DCTERMS.identifier)),
        publisher=_label(graph, _first(graph.objects(node, DCTERMS.publisher))),
        themes=_texts(graph.objects(node, URIRef(DCAT + "theme"))),
        keywords=_localized(graph.objects(node, URIRef(DCAT + "keyword"))),
        languages=_texts(graph.objects(node, DCTERMS.language)),
        distributions=distributions,
        service_urls=sorted(set(services)),
        license=(
            _node_id(graph, _first(graph.objects(node, DCTERMS.license)))
            if _first(graph.objects(node, DCTERMS.license)) is not None
            else None
        ),
        access_rights=(
            _node_id(graph, _first(graph.objects(node, DCTERMS.accessRights)))
            if _first(graph.objects(node, DCTERMS.accessRights)) is not None
            else None
        ),
        version=_text(_first(graph.objects(node, URIRef(DCAT + "version")))),
    )


def _distribution(graph: Graph, node: object) -> DcatDistribution:
    """Extract a distribution while retaining distinct access and download URLs."""
    license_node = _first(graph.objects(node, DCTERMS.license))
    return DcatDistribution(
        id=_node_id(graph, node),
        access_url=_text(_first(graph.objects(node, URIRef(DCAT + "accessURL")))),
        download_url=_text(_first(graph.objects(node, URIRef(DCAT + "downloadURL")))),
        media_type=_text(_first(graph.objects(node, URIRef(DCAT + "mediaType")))),
        format=_text(_first(graph.objects(node, DCTERMS.format))),
        license=_node_id(graph, license_node) if license_node is not None else None,
    )


def _declared_relationships(
    graph: Graph, node: object, source: str
) -> List[DcatRelationship]:
    """Return source-declared relationships only."""
    mappings = (
        ("dataset", "catalog-dataset"),
        ("service", "catalog-service"),
        ("distribution", "dataset-distribution"),
        ("accessService", "dataset-service"),
        ("inSeries", "dataset-series"),
        ("seriesMember", "series-member"),
        ("hasPart", "has-part"),
        ("relation", "related-resource"),
        ("hasVersion", "has-version"),
        ("previousVersion", "previous-version"),
    )
    items: List[DcatRelationship] = []
    for property_name, kind in mappings:
        predicate = (
            URIRef(DCAT + property_name)
            if property_name
            in {
                "dataset",
                "service",
                "distribution",
                "accessService",
                "inSeries",
                "seriesMember",
                "hasVersion",
                "previousVersion",
            }
            else DCTERMS[property_name]
        )
        for target in graph.objects(node, predicate):
            items.append(
                DcatRelationship(
                    kind, source, _node_id(graph, target), "fact", [str(predicate)]
                )
            )
    return items


def _findings(
    resources: Sequence[DcatResource], relationships: Sequence[DcatRelationship]
) -> Tuple[List[DcatFinding], List[DcatFinding]]:
    """Produce bounded source-fact and inference findings without weak-signal floods."""
    findings: List[DcatFinding] = []
    for resource in resources:
        if len(resource.source_documents) > 1:
            findings.append(
                DcatFinding(
                    "shared-iri-" + _digest(resource.id),
                    "same-resource-across-catalogs",
                    "inference",
                    [resource.id],
                    "The same resource IRI occurs in more than one supplied catalog document.",
                    list(resource.source_documents),
                    "Confirm whether the catalogs intentionally reuse one resource or publish overlapping metadata.",
                )
            )
        missing = []
        if not resource.titles:
            missing.append("title")
        if not resource.descriptions:
            missing.append("description")
        if not resource.publisher:
            missing.append("publisher")
        if (
            resource.resource_type == "Dataset"
            and not resource.distributions
            and not resource.service_urls
        ):
            missing.append("access information")
        if not resource.license:
            missing.append("license")
        if missing:
            findings.append(
                DcatFinding(
                    "gap-" + _digest(resource.id),
                    "missing-metadata",
                    "inference",
                    [resource.id],
                    "The source does not declare " + ", ".join(missing) + ".",
                    ["Absent DCAT metadata fields"],
                    "Confirm whether the missing metadata is needed for discovery, reuse, or conversion.",
                )
            )
    by_url: Dict[str, List[str]] = {}
    for resource in resources:
        for distribution in resource.distributions:
            for value in (distribution.access_url, distribution.download_url):
                if value:
                    by_url.setdefault(value, []).append(resource.id)
    for url, identifiers in by_url.items():
        unique = sorted(set(identifiers))
        if len(unique) > 1:
            findings.append(
                DcatFinding(
                    "reuse-" + _digest(url),
                    "shared-distribution",
                    "inference",
                    unique,
                    "Resources declare the same access or download URL.",
                    [url],
                    "Confirm whether this is intentional reuse or duplicate catalog metadata.",
                )
            )
    opportunities: List[DcatFinding] = []
    for relationship in relationships:
        if relationship.kind == "dataset-series":
            opportunities.append(
                DcatFinding(
                    "opportunity-" + _digest(relationship.source + relationship.target),
                    "potential-data-product-boundary",
                    "proposal",
                    [relationship.source, relationship.target],
                    "The source declares a dataset-to-series relationship, which may be useful boundary evidence but does not establish demand.",
                    relationship.evidence,
                    "Review consumer need, owner, value proposition, and lifecycle before creating a product.",
                )
            )
    return findings, opportunities


def _odps_draft(
    resource: DcatResource, intelligence: DcatCatalogIntelligenceResult
) -> Tuple[Dict[str, object], Dict[str, object], List[str]]:
    """Map only supported source metadata into a private ODPS draft."""
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
        document["product"]["dataAccess"] = {"default": access}
    elif resource.distributions or resource.service_urls:
        warnings.append(
            "DATA_ACCESS_OMITTED: DCAT metadata did not establish a safe supported access profile"
        )
    mapped = [
        "identifier",
        "title",
        "description",
        "keywords",
        "themes",
        "distribution",
    ]
    report = {
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
    report["validation_result"] = (
        "valid" if validate_document(document).valid else "invalid"
    )
    return document, report, warnings


def _generate_ai_proposals(
    resource: DcatResource,
    *,
    client: Optional[Callable[[str, str], str]],
    model: Optional[str],
    config: Optional[str],
    extend: bool,
) -> List[DcatWrapProposal]:
    """Generate bounded review-only business proposals from DCAT source facts."""
    if client is None:
        from ..generation import create_generation_client, resolve_generation_settings

        settings = resolve_generation_settings(config_path=config)
        client = create_generation_client(settings)
        model = settings.model
    if not model:
        model = "dcat-enrichment"
    permitted = ["description", "suggestedTags"]
    if extend:
        permitted.extend(
            [
                "valueProposition",
                "potentialConsumers",
                "potentialUseCases",
                "suggestedCategories",
                "missingBusinessInformation",
            ]
        )
    source_summary = {
        "id": resource.id,
        "titles": resource.titles,
        "descriptions": resource.descriptions,
        "keywords": resource.keywords,
        "themes": resource.themes,
        "publisher": resource.publisher,
    }
    prompt = (
        "Propose, do not assert, business-layer values for a DCAT resource. "
        "Do not invent ownership, demand, access rights, service commitments, "
        "or product approval. Return a JSON object with only these optional keys: "
        + ", ".join(permitted)
        + ". description is a concise proposed business description; suggestedTags "
        "contains lowercase hyphenated terms grounded in the source. Source facts:\n"
        + json.dumps(source_summary, sort_keys=True)
    )
    parsed = json.loads(client(prompt, model))
    if not isinstance(parsed, dict):
        raise ValueError("AI enrichment did not return a JSON object")
    proposals: List[DcatWrapProposal] = []
    for field in permitted:
        value = parsed.get(field)
        if isinstance(value, str) and value.strip():
            proposals.append(DcatWrapProposal(field, value.strip()))
        elif isinstance(value, list):
            proposals.extend(
                DcatWrapProposal(field, item.strip())
                for item in value
                if isinstance(item, str) and item.strip()
            )
    return proposals


def _apply_ai_proposals(
    document: Dict[str, object],
    proposals: Sequence[DcatWrapProposal],
    warnings: List[str],
) -> None:
    """Apply only safe draft-description and discovery-tag proposals."""
    product = document.get("product")
    if not isinstance(product, dict):
        return
    details_by_language = product.get("details")
    if not isinstance(details_by_language, dict):
        return
    details = details_by_language.get("en")
    if not isinstance(details, dict):
        return
    description = next(
        (item.value for item in proposals if item.field == "description"), None
    )
    if description:
        details["description"] = description
        warnings.append("AI_PROPOSED_DESCRIPTION_APPLIED: requires human review")
    tags = [item.value for item in proposals if item.field == "suggestedTags"]
    if tags:
        existing = details.get("tags")
        prior_tags = existing if isinstance(existing, list) else []
        details["tags"] = list(dict.fromkeys(prior_tags + tags))
        warnings.append("AI_PROPOSED_TAGS_APPLIED: requires human review")


def _access_profile(resource: DcatResource) -> Optional[Dict[str, object]]:
    """Map only an explicit HTTP(S) access endpoint to ODPS data access."""
    for distribution in resource.distributions:
        if distribution.access_url and _safe_access_url(distribution.access_url):
            profile: Dict[str, object] = {
                "outputPortType": "API",
                "accessURL": distribution.access_url,
            }
            if distribution.format in {"CSV", "JSON", "XML", "TOON"}:
                profile["format"] = distribution.format
            return profile
    for service_url in resource.service_urls:
        if _safe_access_url(service_url):
            return {"outputPortType": "API", "accessURL": service_url}
    return None


def _safe_access_url(value: str) -> bool:
    """Accept only credential-free HTTP(S) access references."""
    try:
        _safe_http_uri(value)
    except ValueError:
        return False
    return True


def _safe_http_uri(source: str) -> str:
    """Return an HTTP(S) URI only when it contains no credentials or fragment."""
    parsed = urlparse(source)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or "@" in parsed.netloc
        or "#" in source
        or _credential_query(parsed.query)
    ):
        raise ValueError("Credential-bearing or malformed DCAT URL is not supported")
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, "")
    )


def _credential_query(query: str) -> bool:
    """Identify credential-like query parameter keys."""
    for parameter in re.split(r"[&;]", query):
        key = re.sub(r"[^a-z0-9]", "", unquote(parameter.split("=", 1)[0]).lower())
        if key in {"apikey", "auth", "key"} or any(
            part in key for part in _CREDENTIAL_QUERY_FRAGMENTS
        ):
            return True
    return False


def _node_id(graph: Graph, node: object) -> str:
    """Return IRIs verbatim and deterministic identifiers for blank nodes."""
    if isinstance(node, BNode):
        triples = sorted(
            "{}={}".format(predicate, obj)
            for _, predicate, obj in graph.triples((node, None, None))
        )
        return "urn:odps:dcat:blank:" + _digest("|".join(triples))
    return str(node)


def _label(graph: Graph, node: Optional[object]) -> Optional[str]:
    """Return a human label or source IRI for a linked resource."""
    if node is None:
        return None
    return (
        _text(_first(graph.objects(node, FOAF.name)))
        or _text(_first(graph.objects(node, DCTERMS.title)))
        or _node_id(graph, node)
    )


def _localized(values: Iterable[object]) -> Dict[str, List[str]]:
    """Group literal values by language without discarding alternatives."""
    result: Dict[str, List[str]] = {}
    for value in values:
        if isinstance(value, Literal):
            result.setdefault(value.language or "und", []).append(str(value))
    return {language: sorted(set(items)) for language, items in result.items()}


def _texts(values: Iterable[object]) -> List[str]:
    """Normalize RDF nodes to unique string values."""
    return sorted(set(str(value) for value in values))


def _text(value: Optional[object]) -> Optional[str]:
    """Return a nonempty node text value."""
    return str(value) if value is not None and str(value).strip() else None


def _first(values: Iterable[object]) -> Optional[object]:
    """Return the first RDF term if present."""
    return next(iter(values), None)


def _first_localized(values: Dict[str, List[str]]) -> Optional[str]:
    """Prefer English source text while retaining all values in inventory."""
    for language in ("en", "und"):
        if values.get(language):
            return values[language][0]
    return next(iter(values.values()))[0] if values else None


def _merge_resource(first: DcatResource, second: DcatResource) -> DcatResource:
    """Merge repeated resource IRIs from several supplied catalog documents."""
    return DcatResource(
        id=first.id,
        resource_type=(
            "DPRODDataProduct"
            if "DPRODDataProduct" in {first.resource_type, second.resource_type}
            else first.resource_type
        ),
        source_documents=sorted(set(first.source_documents + second.source_documents)),
        titles=_merge_localized(first.titles, second.titles),
        descriptions=_merge_localized(first.descriptions, second.descriptions),
        identifiers=sorted(set(first.identifiers + second.identifiers)),
        publisher=first.publisher or second.publisher,
        themes=sorted(set(first.themes + second.themes)),
        keywords=_merge_localized(first.keywords, second.keywords),
        languages=sorted(set(first.languages + second.languages)),
        distributions=list(
            {
                item.id: item for item in first.distributions + second.distributions
            }.values()
        ),
        service_urls=sorted(set(first.service_urls + second.service_urls)),
        license=first.license or second.license,
        access_rights=first.access_rights or second.access_rights,
        version=first.version or second.version,
    )


def _merge_localized(
    first: Dict[str, List[str]], second: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """Merge language-labelled values."""
    return {
        language: sorted(set(first.get(language, []) + second.get(language, [])))
        for language in set(first) | set(second)
    }


def _unique_relationships(items: Sequence[DcatRelationship]) -> List[DcatRelationship]:
    """Remove repeated source relationships."""
    return list(
        {
            (item.kind, item.source, item.target, item.evidence_level): item
            for item in items
        }.values()
    )


def _digest(value: str) -> str:
    """Create a stable, compact identifier suffix."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _slugify(value: str) -> str:
    """Create a conservative ODPS identifier from source identity."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[-80:] or "dcat-resource"


def _title_from_id(value: str) -> str:
    """Create a human-readable fallback title."""
    return (
        re.sub(r"[-_/]+", " ", value.rsplit("/", 1)[-1]).strip().title()
        or "DCAT resource"
    )
