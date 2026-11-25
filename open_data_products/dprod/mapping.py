"""Deterministic ODPS 4.2 to DPROD 1.0 Beta 2 export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS

from ..agent import validate_document
from .models import DprodExportResult
from .validation import DPROD_NAMESPACE, _validate_graph

DCAT = Namespace("http://www.w3.org/ns/dcat#")
DPROD = Namespace(DPROD_NAMESPACE)


def export_odps_to_dprod(
    document: Dict[str, object], *, base_iri: Optional[str] = None
) -> DprodExportResult:
    """Export a valid ODPS 4.2 definition to deterministic DPROD RDF."""
    source_validation = validate_document(document)
    if not source_validation.valid:
        raise ValueError("ODPS input must validate before DPROD export")
    product = document["product"]
    assert isinstance(product, dict)
    details_by_language = product["details"]
    assert isinstance(details_by_language, dict)
    details = details_by_language.get("en") or next(iter(details_by_language.values()))
    assert isinstance(details, dict)
    identifier = str(details["productID"])
    root = (
        (base_iri or "urn:odps:dprod:").rstrip("/")
        + "/"
        + quote(identifier, safe="-._~")
    )
    graph = Graph()
    graph.bind("dprod", DPROD)
    graph.bind("dcat", DCAT)
    node = URIRef(root)
    graph.add((node, RDF.type, DPROD.DataProduct))
    graph.add((node, RDFS.label, Literal(str(details["name"]))))
    if isinstance(details.get("description"), str):
        graph.add((node, DCTERMS.description, Literal(details["description"])))
    _export_access(graph, node, root, product.get("dataAccess"))
    turtle = str(graph.serialize(format="turtle"))
    jsonld = json.dumps(
        json.loads(str(graph.serialize(format="json-ld"))), indent=2, sort_keys=True
    )
    losses = [
        _loss(
            "/product/details/*/visibility",
            "DPROD Beta 2 has no equivalent visibility field",
        ),
        _loss(
            "/product/details/*/status",
            "ODPS lifecycle value is not mapped without a controlled DPROD lifecycle resource",
        ),
        _loss(
            "/product/contract",
            "ODPS contract profiles are not asserted as DPROD governance guarantees",
        ),
    ]
    mappings = [
        _mapping("/product/details/*/name", "rdfs:label", "exact", "literal copy"),
        _mapping(
            "/product/details/*/description",
            "dct:description",
            "conditional",
            "literal copy when present",
        ),
        _mapping(
            "/product/dataAccess/default/accessURL",
            "dcat:endpointURL",
            "conditional",
            "emit output service when present",
        ),
    ]
    return DprodExportResult(turtle, jsonld, _validate_graph(graph), mappings, losses)


def write_dprod_export(
    document: Dict[str, object], output: str, *, overwrite: bool = False
) -> Dict[str, object]:
    """Write deterministic Turtle and JSON-LD export siblings."""
    result = export_odps_to_dprod(document)
    destination = Path(output)
    root = destination.with_suffix("") if destination.suffix else destination
    turtle_path = root.with_suffix(".ttl")
    jsonld_path = root.with_suffix(".jsonld")
    for path in (turtle_path, jsonld_path):
        if path.exists() and not overwrite:
            raise FileExistsError("Refusing to overwrite existing output: " + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
    turtle_path.write_text(result.turtle, encoding="utf-8")
    jsonld_path.write_text(result.jsonld + "\n", encoding="utf-8")
    payload = result.to_dict()
    payload["turtle_output"] = str(turtle_path)
    payload["jsonld_output"] = str(jsonld_path)
    return payload


def _export_access(
    graph: Graph, product: URIRef, root: str, data_access: object
) -> None:
    """Represent one supported ODPS access profile as a DPROD output service."""
    if not isinstance(data_access, dict):
        return
    default = data_access.get("default")
    if not isinstance(default, dict) or not isinstance(default.get("accessURL"), str):
        return
    service = URIRef(root + "/services/default")
    graph.add((product, DPROD.outputPort, service))
    graph.add((service, RDF.type, DCAT.DataService))
    graph.add((service, DCAT.endpointURL, URIRef(default["accessURL"])))


def _mapping(
    source: str, target: str, classification: str, rule: str
) -> Dict[str, str]:
    """Create one machine-readable mapping record."""
    return {
        "source": source,
        "target": target,
        "classification": classification,
        "transformation_rule": rule,
        "preconditions": "",
        "information_loss": "",
        "source_standard": "ODPS 4.2",
        "target_standard": "DPROD 1.0 Beta 2",
    }


def _loss(source: str, loss: str) -> Dict[str, str]:
    """Create one explicit unsupported mapping record."""
    return {
        "source": source,
        "target": "",
        "classification": "unsupported",
        "transformation_rule": "none",
        "preconditions": "",
        "information_loss": loss,
        "source_standard": "ODPS 4.2",
        "target_standard": "DPROD 1.0 Beta 2",
    }
