#!/usr/bin/env python3
"""Acquire bounded DCAT metadata samples without downloading data resources."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import ssl
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

DCAT = "http://www.w3.org/ns/dcat#"
DCT = "http://purl.org/dc/terms/"
SOURCES = {
    "europe": {
        "url": "https://data.europa.eu/sparql",
        "profile": "DCAT-AP (declared by source where available)",
        "sparql": True,
    },
    "govdata": {
        "url": "https://www.govdata.de/ckan/catalog/catalog.rdf",
        "profile": "DCAT-AP.de (declared by source where available)",
        "sparql": False,
    },
    "finland": {
        "url": "https://www.avoindata.fi/data/catalog.ttl",
        "profile": "Finnish DCAT-AP extension (declared by source where available)",
        "sparql": False,
    },
    "switzerland": {
        "url": "https://opendata.swiss/catalog.jsonld",
        "profile": "DCAT-AP CH (declared by source where available)",
        "sparql": False,
    },
}


def main() -> int:
    """Write a bounded source snapshot and manifest for one operational catalog."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("--output", required=True, help="Snapshot directory")
    parser.add_argument("--limit", type=int, default=25, help="Dataset limit (1-50)")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum metadata response size",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error("--limit must be between 1 and 50")
    if args.max_bytes <= 0:
        parser.error("--max-bytes must be positive")

    metadata = SOURCES[args.source]
    try:
        graph, source_url = _load_source(metadata, args.limit, args.max_bytes)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    selected = list(graph.subjects(RDF.type, URIRef(DCAT + "Dataset")))[: args.limit]
    snapshot = _bounded_subgraph(graph, selected)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    snapshot_path = output / (args.source + ".ttl")
    snapshot_path.write_text(snapshot.serialize(format="turtle"), encoding="utf-8")
    payload = snapshot_path.read_bytes()
    manifest = {
        "source": args.source,
        "source_url": source_url,
        "declared_profile": metadata["profile"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "dataset_limit": args.limit,
        "selected_dataset_ids": [str(item) for item in selected],
        "snapshot": snapshot_path.name,
        "sha256": sha256(payload).hexdigest(),
        "license_or_reuse_hints": _license_hints(snapshot, selected),
        "note": "Metadata only; no dataset contents were retrieved.",
    }
    (output / (args.source + ".manifest.json")).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _load_source(
    metadata: Dict[str, object], limit: int, max_bytes: int
) -> Tuple[Graph, str]:
    """Retrieve bounded RDF metadata from one configured operational source."""
    url = str(metadata["url"])
    if bool(metadata["sparql"]):
        query = """CONSTRUCT { ?dataset ?property ?value . }
WHERE { ?dataset a <http://www.w3.org/ns/dcat#Dataset> ; ?property ?value . }
LIMIT %d""" % limit
        url = url + "?" + urlencode({"query": query, "format": "text/turtle"})
    request = Request(
        url,
        headers={
            "Accept": "text/turtle, application/rdf+xml, application/ld+json",
            "User-Agent": "open-data-products-dcat-sampler/0.7",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=20, context=context) as response:
        content = response.read(max_bytes + 1)
        resolved_url = str(response.geturl())
        content_type = response.headers.get_content_type()
    if len(content) > max_bytes:
        raise ValueError(
            "Catalog response exceeded --max-bytes; do not retrieve an unbounded archive"
        )
    if content_type == "text/html":
        raise ValueError("Catalog endpoint returned HTML instead of RDF metadata")
    graph = Graph()
    graph.parse(data=content.decode("utf-8"), format=_format(resolved_url))
    return graph, resolved_url


def _bounded_subgraph(graph: Graph, datasets: Iterable[URIRef]) -> Graph:
    """Retain selected datasets plus direct distribution, service, and catalog evidence."""
    result = Graph()
    selected = set(datasets)
    related = set(selected)
    for dataset in selected:
        related.update(graph.objects(dataset, URIRef(DCAT + "distribution")))
        related.update(graph.objects(dataset, URIRef(DCAT + "accessService")))
        related.update(graph.objects(dataset, URIRef(DCAT + "inSeries")))
    for node in related:
        for triple in graph.triples((node, None, None)):
            result.add(triple)
    for catalog in graph.subjects(RDF.type, URIRef(DCAT + "Catalog")):
        for dataset in selected:
            if (catalog, URIRef(DCAT + "dataset"), dataset) in graph:
                result.add((catalog, RDF.type, URIRef(DCAT + "Catalog")))
                result.add((catalog, URIRef(DCAT + "dataset"), dataset))
    return result


def _license_hints(graph: Graph, datasets: Iterable[URIRef]) -> List[str]:
    """Return declared license IRIs or literals without interpreting their terms."""
    values = set()
    for dataset in datasets:
        values.update(
            str(item) for item in graph.objects(dataset, URIRef(DCT + "license"))
        )
        for distribution in graph.objects(dataset, URIRef(DCAT + "distribution")):
            values.update(
                str(item)
                for item in graph.objects(distribution, URIRef(DCT + "license"))
            )
    return sorted(values)


def _format(source: str) -> str:
    """Infer the RDF parser from a configured source URL."""
    lowered = source.lower().split("?", 1)[0]
    if lowered.endswith(".rdf") or lowered.endswith(".xml"):
        return "xml"
    if lowered.endswith(".jsonld") or lowered.endswith(".json-ld"):
        return "json-ld"
    return "turtle"


if __name__ == "__main__":
    raise SystemExit(main())
