import json
from pathlib import Path

import yaml

from open_data_products import (
    explain_document,
    get_resource,
    list_resources,
    load_document,
    resolve_references,
    validate_document,
)
from open_data_products.cli import main
from open_data_products.odpg import explain_graph, load_graph, validate_graph
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import DataAccessMethod, ProductDetails
from open_data_products.odpv import load_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[1]


def sample_odps_product():
    product = OpenDataProduct(
        ProductDetails(
            name="Agent Ready Product",
            product_id="agent-ready-product",
            visibility="public",
            status="production",
            type="dataset",
        )
    )
    product.add_data_access(
        DataAccessMethod(
            name={"en": "API"},
            output_port_type="API",
            access_url="https://example.com/api",
        )
    )
    return product


def test_unified_load_validate_and_explain_odps(tmp_path):
    path = REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml"

    loaded = load_document(path)
    result = validate_document(path)
    summary = explain_document(loaded, path=path)

    assert isinstance(loaded, OpenDataProduct)
    assert result.valid is True
    assert result.spec == "odps"
    assert result.kind == "OpenDataProduct"
    assert "Agent Ready Product" in summary


def test_unified_validate_and_explain_odpc():
    catalog = {
        "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
        "version": "1.0",
        "kind": "Catalog",
        "catalog": {
            "metadata": {
                "id": "CAT-001",
                "name": {"en": "Agent Catalog"},
                "description": {"en": "Catalog for agent testing."},
            }
        },
    }

    result = validate_document(catalog)
    summary = explain_document(catalog)

    assert result.valid is True
    assert result.spec == "odpc"
    assert result.kind == "Catalog"
    assert "Catalog id: CAT-001" in summary


def test_odpg_schema_validation_accepts_bundled_graph():
    graph = load_graph()

    result = validate_graph(graph)

    assert result.valid is True
    assert result.spec == "odpg"
    assert result.kind == "Graph"


def test_explain_graph_summarizes_agent_relevant_counts():
    summary = explain_graph(load_graph(), path=Path("graph.yaml"))

    assert "Graph id: GRAPH-AVIATION-001" in summary
    assert "Nodes: 9" in summary
    assert "Edges: 13" in summary
    assert "Relationship types:" in summary


def test_resolve_references_finds_cross_spec_references():
    graph = load_graph()
    refs = resolve_references(graph)

    assert any(ref.ref_type == "node" for ref in refs)
    assert any(ref.pointer.endswith("/graph/nodes/0/$ref") for ref in refs)


def test_agent_document_preparation_preserves_explicit_path_for_loaded_document():
    product = sample_odps_product()

    result = validate_document(product, path=Path("memory-product.yaml"))
    summary = explain_document(product, path=Path("memory-product.yaml"))
    refs = resolve_references(product, path=Path("memory-product.yaml"))

    assert result.path == "memory-product.yaml"
    assert "File: memory-product.yaml" in summary
    assert all(ref.source_path == "memory-product.yaml" for ref in refs)


def test_resources_are_listable_and_retrievable():
    resources = list_resources()

    assert any(resource.id == "odpg.schema.yaml" for resource in resources)
    assert any(resource.id == "generation.prompt.system" for resource in resources)
    assert get_resource("odpv.terms").id == "odpv.terms"
    assert get_resource("generation.prompt.system").type == "prompt"


def test_resource_registry_paths_are_unique_and_existing():
    resources = list_resources()
    ids = [resource.id for resource in resources]

    assert len(ids) == len(set(ids))
    assert all(Path(resource.path).is_file() for resource in resources)


def test_unified_validate_and_explain_odpv():
    vocabulary = load_vocabulary()

    result = validate_document(vocabulary)
    summary = explain_document(vocabulary)

    assert result.valid is True
    assert result.spec == "odpv"
    assert result.kind == "Vocabulary"
    assert "Terms: 59" in summary


def test_top_level_cli_json_validate_and_explain(tmp_path, capsys):
    path = REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml"

    assert main(["validate", str(path), "--json"]) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["valid"] is True
    assert validate_payload["spec"] == "odps"

    assert main(["explain", str(path), "--json"]) == 0
    explain_payload = json.loads(capsys.readouterr().out)
    assert explain_payload["spec"] == "odps"
    assert "Agent Ready Product" in explain_payload["summary"]


def test_unified_validate_rejects_legacy_flat_odps_file(tmp_path):
    path = tmp_path / "legacy-flat-product.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
                "version": "4.1",
                "product": {
                    "name": "Agent Ready Product",
                    "productID": "agent-ready-product",
                    "visibility": "public",
                    "status": "production",
                    "type": "dataset",
                },
            }
        ),
        encoding="utf-8",
    )

    result = validate_document(path)

    assert result.valid is False
    assert result.spec == "odps"
    assert any("product/details" in error for error in result.errors)


def test_top_level_cli_resources_json(capsys):
    assert main(["resources", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert any(resource["id"] == "odpc.schema.yaml" for resource in payload)
    assert any(resource["id"] == "odps.schema.json" for resource in payload)
