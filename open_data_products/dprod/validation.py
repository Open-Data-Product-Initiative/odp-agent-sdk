"""Offline validation against pinned DPROD 1.0 Beta 2 SHACL shapes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SH

from .._interop.rdf import load_graphs
from .models import DprodValidationResult, DprodViolation

DPROD_NAMESPACE = "https://www.omg.org/spec/DPROD/"
_DEVELOPMENT_NAMESPACE = "https://www.omg.org/spec/DPROD/dprod/"
_DATA_PRODUCT = URIRef(DPROD_NAMESPACE + "DataProduct")
_DATA_DIRECTORY = Path(__file__).resolve().parent / "data"


def validate_dprod(source: str) -> DprodValidationResult:
    """Validate supplied RDF with local OMG Beta 2 shapes and no imports."""
    try:
        loaded = load_graphs(source, label="DPROD source")
    except ValueError as exc:
        message = str(exc)
        if "Remote JSON-LD contexts" in message:
            raise
        return DprodValidationResult(False, parse_errors=[message])
    data_graph = Graph()
    for graph, _source in loaded:
        _reject_unsupported_namespace(graph)
        for triple in graph:
            data_graph.add(triple)
    return _validate_graph(data_graph)


def _validate_graph(data_graph: Graph) -> DprodValidationResult:
    """Validate an already-safe RDF graph with the bundled profile."""
    shapes = _graph_from_asset("dprod-shapes.ttl")
    ontology = _graph_from_asset("dprod-ontology.ttl")
    conforms, results, _text = validate(
        data_graph,
        shacl_graph=shapes,
        ont_graph=ontology,
        inference="none",
        advanced=False,
        meta_shacl=False,
        do_owl_imports=False,
        serialize_report_graph=False,
    )
    violations = _violations(results, data_graph)
    return DprodValidationResult(bool(conforms), violations=violations)


def _graph_from_asset(name: str) -> Graph:
    """Load one bundled normative RDF artifact."""
    graph = Graph()
    graph.parse(str(_DATA_DIRECTORY / name), format="turtle")
    return graph


def _reject_unsupported_namespace(graph: Graph) -> None:
    """Reject development vocabulary use rather than silently remapping it."""
    for subject, predicate, obj in graph:
        if any(
            _DEVELOPMENT_NAMESPACE in str(value) for value in (subject, predicate, obj)
        ):
            raise ValueError("Unsupported DPROD namespace: " + _DEVELOPMENT_NAMESPACE)


def _violations(results: Graph, data_graph: Graph) -> List[DprodViolation]:
    """Normalize SHACL result nodes without returning report graph bodies."""
    normalized: List[DprodViolation] = []
    for result in results.subjects(RDF.type, SH.ValidationResult):
        focus = _value(results, result, SH.focusNode)
        path = _value(results, result, SH.resultPath)
        normalized.append(
            DprodViolation(
                severity=_local_name(_value(results, result, SH.resultSeverity)),
                source_node=focus or "",
                property_path=path or "",
                message=_value(results, result, SH.resultMessage) or "SHACL violation",
                product_uri=_associated_product(data_graph, focus),
            )
        )
    return sorted(
        normalized,
        key=lambda item: (item.source_node, item.property_path, item.message),
    )


def _value(graph: Graph, subject: object, predicate: URIRef) -> Optional[str]:
    """Return the first lexical RDF value."""
    value = next(graph.objects(subject, predicate), None)
    return str(value) if value is not None else None


def _local_name(value: Optional[str]) -> str:
    """Return a stable compact severity label."""
    if not value:
        return "Violation"
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _associated_product(graph: Graph, focus: Optional[str]) -> Optional[str]:
    """Associate a result node with its explicit DPROD product when possible."""
    if not focus:
        return None
    node = URIRef(focus)
    if (node, RDF.type, _DATA_PRODUCT) in graph:
        return focus
    for predicate in _dprod_product_properties():
        for product in graph.subjects(predicate, node):
            if (product, RDF.type, _DATA_PRODUCT) in graph:
                return str(product)
    return None


def _dprod_product_properties() -> Iterable[URIRef]:
    """Yield properties that attach source nodes to an explicit product."""
    return (
        URIRef(DPROD_NAMESPACE + name)
        for name in (
            "dataProductOwner",
            "inputPort",
            "outputPort",
            "inputDataset",
            "outputDataset",
            "lifecycleStatus",
        )
    )
