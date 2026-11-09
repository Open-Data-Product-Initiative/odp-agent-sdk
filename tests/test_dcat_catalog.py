"""DCAT catalog intelligence and conservative ODPS draft coverage."""

from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from open_data_products.cli import main

pytestmark = pytest.mark.functional

CATALOG_TURTLE = """\
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://catalog.example/> a dcat:Catalog ;
  dct:title "Example catalog"@en ;
  dcat:dataset <https://catalog.example/datasets/air> .

<https://catalog.example/datasets/air> a dcat:Dataset ;
  dct:identifier "air-quality" ;
  dct:title "Air quality"@en, "Luftqualität"@de ;
  dct:description "Daily air measurements."@en ;
  dct:publisher <https://catalog.example/organisations/environment> ;
  dcat:keyword "air"@en, "environment"@en ;
  dcat:theme <https://example.org/themes/environment> ;
  dcat:distribution [
    a dcat:Distribution ;
    dcat:accessURL <https://data.example/air> ;
    dcat:downloadURL <https://data.example/air.csv> ;
    dct:format "CSV" ;
    dcat:mediaType "text/csv"
  ] .

<https://catalog.example/organisations/environment> a foaf:Organization ;
  foaf:name "Environment Office" .
"""


def _catalog_file(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.ttl"
    path.write_text(CATALOG_TURTLE, encoding="utf-8")
    return path


def test_discover_dcat_catalog_preserves_facts_and_multilingual_values(
    tmp_path: Path,
) -> None:
    """DCAT ingestion keeps facts distinct from derived findings."""
    from open_data_products.dcat import discover_dcat_catalog

    result = discover_dcat_catalog(str(_catalog_file(tmp_path)))

    dataset = next(item for item in result.resources if item.id.endswith("/air"))
    assert dataset.resource_type == "Dataset"
    assert dataset.titles == {"en": ["Air quality"], "de": ["Luftqualität"]}
    assert dataset.distributions[0].download_url == "https://data.example/air.csv"
    assert dataset.distributions[0].access_url == "https://data.example/air"
    assert all(finding.evidence_level != "proposal" for finding in result.findings)
    assert any(
        relation.kind == "dataset-distribution" and relation.evidence_level == "fact"
        for relation in result.relationships
    )
    assert any(
        relation.kind == "catalog-dataset"
        and relation.evidence_level == "fact"
        and relation.target.endswith("/air")
        for relation in result.relationships
    )


def test_wrap_dcat_dataset_creates_a_valid_draft_without_inventing_context(
    tmp_path: Path,
) -> None:
    """A selected DCAT dataset becomes a schema-valid private ODPS draft."""
    from open_data_products.dcat import wrap_dcat_resource

    result = wrap_dcat_resource(
        str(_catalog_file(tmp_path)), "https://catalog.example/datasets/air"
    )

    assert result.validation.valid
    assert result.document["product"]["details"]["en"]["status"] == "draft"
    assert "approved product owner" in result.missing_business_information
    access = result.document["product"]["dataAccess"]["default"]
    assert access["accessURL"] == "https://data.example/air"
    assert access["outputPortType"] == "API"
    assert result.mapping_report["source_information_not_represented"]


def test_dcat_cli_and_mcp_share_the_catalog_intelligence_result(
    capsys, tmp_path: Path
) -> None:
    """CLI and MCP expose the same safe catalog analysis implementation."""
    from open_data_products.mcp.server import handle

    source = _catalog_file(tmp_path)
    report = tmp_path / "catalog-intelligence.html"

    exit_code = main(
        [
            "portfolio",
            "discover-dcat",
            str(source),
            "--output",
            str(report),
            "--json",
        ]
    )

    assert exit_code == 0
    assert report.is_file()
    assert '"resources"' in capsys.readouterr().out
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": "discover-dcat",
            "method": "tools/call",
            "params": {
                "name": "discover_dcat_catalog",
                "arguments": {"source": str(source)},
            },
        }
    )
    assert response is not None
    payload = response["result"]["content"][0]["text"]
    assert "Air quality" in payload


def test_wrap_dcat_resources_writes_one_draft_per_explicit_selection(
    tmp_path: Path,
) -> None:
    """Batch conversion remains limited to the resource IRIs selected by the caller."""
    from open_data_products.dcat import wrap_dcat_resources

    results = wrap_dcat_resources(
        str(_catalog_file(tmp_path)),
        ["https://catalog.example/datasets/air"],
        str(tmp_path / "drafts"),
    )

    assert len(results) == 1
    assert results[0].output is not None
    assert Path(results[0].output).is_file()


def test_wrap_dcat_cli_uses_the_selected_resource_only(capsys, tmp_path: Path) -> None:
    """The product CLI exposes deterministic selected-resource conversion."""
    source = _catalog_file(tmp_path)
    output = tmp_path / "air.yaml"

    exit_code = main(
        [
            "product",
            "wrap-dcat",
            "--input",
            str(source),
            "--resource",
            "https://catalog.example/datasets/air",
            "--output",
            str(output),
            "--json",
        ]
    )

    assert exit_code == 0
    assert output.is_file()
    assert '"results"' in capsys.readouterr().out


def test_wrap_dcat_marks_ai_enrichment_as_a_review_required_proposal(
    tmp_path: Path,
) -> None:
    """Generated business language is visible as a proposal, never a source fact."""
    from open_data_products.dcat import wrap_dcat_resource

    result = wrap_dcat_resource(
        str(_catalog_file(tmp_path)),
        "https://catalog.example/datasets/air",
        use_ai=True,
        client=lambda _prompt, _model: (
            '{"description":"A proposed air-quality data product.",'
            '"suggestedTags":["air-quality"]}'
        ),
        model="test-model",
    )

    assert result.ai_enriched is True
    assert result.ai_proposals[0].review_status == "proposed"
    assert any(
        warning.startswith("AI_PROPOSED_DESCRIPTION_APPLIED")
        for warning in result.warnings
    )
    assert result.mapping_report["ai_generated_fields"] == [
        "description",
        "suggestedTags",
    ]


def test_dcat_supports_rdfxml_and_inline_jsonld_without_remote_contexts(
    tmp_path: Path,
) -> None:
    """RDF/XML and JSON-LD parse without allowing context retrieval."""
    from open_data_products.dcat import discover_dcat_catalog

    rdfxml = tmp_path / "catalog.rdf"
    rdfxml.write_text(
        """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dcat="http://www.w3.org/ns/dcat#" xmlns:dct="http://purl.org/dc/terms/">
 <dcat:Dataset rdf:about="https://example.test/xml"><dct:title>XML data</dct:title></dcat:Dataset>
</rdf:RDF>""",
        encoding="utf-8",
    )
    jsonld = tmp_path / "catalog.jsonld"
    jsonld.write_text(
        """{
  "@context": {"dcat": "http://www.w3.org/ns/dcat#", "dct": "http://purl.org/dc/terms/"},
  "@id": "https://example.test/jsonld", "@type": "dcat:Dataset", "dct:title": "JSON-LD data"
}""",
        encoding="utf-8",
    )
    unsafe = tmp_path / "unsafe.jsonld"
    unsafe.write_text(
        '{"@context": "https://example.test/context.jsonld", "@id": "https://example.test/x"}',
        encoding="utf-8",
    )

    assert len(discover_dcat_catalog(str(rdfxml)).resources) == 1
    assert len(discover_dcat_catalog(str(jsonld)).resources) == 1
    with pytest.raises(ValueError, match="Remote JSON-LD contexts"):
        discover_dcat_catalog(str(unsafe))


def test_dcat_reports_a_repeated_resource_iri_across_catalog_documents(
    tmp_path: Path,
) -> None:
    """A shared IRI is an evidence-backed reuse signal, not a duplicate verdict."""
    from open_data_products.dcat import discover_dcat_catalog

    first = tmp_path / "first.ttl"
    second = tmp_path / "second.ttl"
    first.write_text(CATALOG_TURTLE, encoding="utf-8")
    second.write_text(
        CATALOG_TURTLE.replace(
            "https://catalog.example/>", "https://catalog-two.example/>"
        ),
        encoding="utf-8",
    )

    result = discover_dcat_catalog(str(tmp_path))

    assert any(
        finding.category == "same-resource-across-catalogs"
        and finding.evidence_level == "inference"
        for finding in result.findings
    )


def test_dcat_remote_loading_allows_only_a_bounded_redirect_chain() -> None:
    """Remote catalog intake rejects redirect chains beyond the documented cap."""
    from open_data_products.dcat import discover_dcat_catalog

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            count = int(self.path.rsplit("/", 1)[-1].split(".", 1)[0])
            if count:
                self.send_response(302)
                self.send_header("Location", "/redirect/{}.ttl".format(count - 1))
                self.end_headers()
                return
            payload = CATALOG_TURTLE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/turtle")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = "http://127.0.0.1:{}".format(server.server_port)
        assert len(discover_dcat_catalog(origin + "/redirect/3.ttl").resources) == 2
        with pytest.raises(ValueError, match="Could not load remote DCAT catalog"):
            discover_dcat_catalog(origin + "/redirect/4.ttl")
    finally:
        server.shutdown()
        thread.join()
