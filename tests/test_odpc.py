"""Tests for ODPC catalog SDK helpers."""

from pathlib import Path

import yaml

from open_data_products.odpc import (
    DEFAULT_CATALOG_HTML_TEMPLATE,
    build_catalog,
    build_catalog_artifacts,
    explain_catalog,
    load_object_records,
    render_catalog_gcf,
    render_catalog_html,
    render_catalog_toon,
    render_catalog_schema_json,
    search_objects,
    validate_catalog,
    write_catalog,
    write_catalog_gcf,
    write_catalog_html,
    write_catalog_toon,
    write_catalog_artifacts,
)
from open_data_products.agent import detect_document, validate_document
from open_data_products.odpc import (
    load_ai_product,
    validate_ai_product,
    validate_ai_product_bundle,
)

VALID_CATALOG = {
    "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
    "version": "1.0",
    "kind": "Catalog",
    "catalog": {
        "metadata": {
            "id": "CAT-001",
            "name": {"en": "Urban Mobility Data Product Catalog"},
            "description": {"en": "Catalog of urban mobility data products."},
        }
    },
}


VALID_AI_PRODUCT = {
    "schema": "https://opendataproducts.org/odpc-v1.1/schema/ai-product.yaml",
    "version": "1.1",
    "kind": "AIProduct",
    "aiProduct": {
        "productID": "policy-knowledge-assistant",
        "productVersion": "1.0.0",
        "name": {"en": "Policy Knowledge Assistant"},
        "description": {"en": "Answers policy questions from approved material."},
        "purpose": {"en": "Improve access to policy guidance with human escalation."},
        "owner": {"team": "Knowledge Management"},
        "productType": "rag",
        "governance": {
            "autonomyLevel": "assistive",
            "humanOversight": {"required": True, "requirements": [{"en": "Review source changes."}]},
            "consequentialActionApproval": {"required": False, "requirements": [{"en": "The assistant takes no consequential action."}]},
            "riskClassification": "limited",
            "knownLimitations": [{"en": "Sources can be out of date."}],
        },
        "evaluation": [{
            "id": "GROUNDEDNESS",
            "name": {"en": "Grounded answer review"},
            "measurementMethod": {"en": "Expert review of sampled answers."},
            "targetValue": "Pass",
            "unit": "review outcome",
            "status": "planned",
        }],
    },
}


def test_validate_odpc_v1_1_ai_product_and_report_missing_governance_path():
    valid = validate_ai_product(VALID_AI_PRODUCT)

    assert valid.valid
    assert valid.errors == []

    incomplete = {**VALID_AI_PRODUCT, "aiProduct": {**VALID_AI_PRODUCT["aiProduct"]}}
    del incomplete["aiProduct"]["governance"]

    invalid = validate_ai_product(incomplete)

    assert not invalid.valid
    assert any("aiProduct.governance" in error for error in invalid.errors)


def test_agent_api_detects_and_validates_an_odpc_v1_1_ai_product(tmp_path):
    path = tmp_path / "ai-product.yaml"
    path.write_text(yaml.safe_dump(VALID_AI_PRODUCT, sort_keys=False), encoding="utf-8")

    loaded = load_ai_product(path)
    result = validate_document(loaded)

    assert detect_document(loaded) == ("odpc", "AIProduct")
    assert result.valid
    assert result.spec == "odpc"
    assert result.kind == "AIProduct"
    assert result.version == "1.1"


def test_odpc_v1_1_catalog_and_bundle_require_matching_ai_product_identity():
    product = VALID_AI_PRODUCT["aiProduct"]
    catalog = {
        "schema": "https://opendataproducts.org/odpc-v1.1/schema/odpc.yaml",
        "version": "1.1",
        "kind": "Catalog",
        "catalog": {
            "metadata": {"id": "CAT-AI-001", "name": {"en": "AI Products"}, "description": {"en": "AI product portfolio."}},
            "nodes": [
                {"node": {"kind": "aiProduct", "id": "AI-001", **product}},
                {"node": {"kind": "productReference", "id": "AI-PR-001", "productID": product["productID"], "productVersion": product["productVersion"], "name": product["name"], "description": product["description"], "productCategory": "ai_product", "productModel": {"standard": "ODPC", "version": "1.1", "profile": "AIProduct", "format": "yaml", "schema": "https://opendataproducts.org/odpc-v1.1/schema/ai-product.yaml", "$ref": "ai-products/policy-knowledge-assistant.odpc.yaml"}}},
            ],
        },
    }
    graph = {
        "schema": "https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml",
        "version": "1.0",
        "kind": "Graph",
        "graph": {"metadata": {"id": "graph-ai", "name": {"en": "AI graph"}, "description": {"en": "AI product graph."}}, "nodes": [{"id": "AI-001", "type": "AIProduct", "$ref": "ai-products/policy-knowledge-assistant.odpc.yaml"}], "edges": []},
    }

    assert validate_catalog(catalog).valid
    assert validate_ai_product_bundle(VALID_AI_PRODUCT, catalog, graph).valid

    catalog["catalog"]["nodes"][1]["node"]["productID"] = "wrong-id"

    invalid = validate_ai_product_bundle(VALID_AI_PRODUCT, catalog, graph)

    assert not invalid.valid
    assert any("productID" in error for error in invalid.errors)


def test_search_objects_returns_product_reference_by_id():
    matches = search_objects(object_id="ProductReference")

    assert len(matches) == 1
    assert matches[0]["id"] == "ProductReference"
    assert "productModel" in matches[0]["requiredFields"]


def test_search_objects_returns_keyword_matches():
    matches = search_objects("business operational analytical policy user needs")

    assert [match["id"] for match in matches] == ["UseCase"]


def test_search_objects_honors_limit():
    matches = search_objects("catalog data", limit=1)

    assert len(matches) == 1


def test_load_object_records_reads_bundled_records():
    records = load_object_records()

    assert len(records) == 6
    assert {record["id"] for record in records} >= {"Catalog", "Signal"}


def test_render_catalog_schema_json_matches_bundled_schema():
    rendered = render_catalog_schema_json()

    assert rendered.endswith("\n")
    assert '"$schema": "https://json-schema.org/draft/2020-12/schema"' in rendered
    assert '"Catalog"' in rendered


def test_build_catalog_artifacts_returns_derived_schema_artifact():
    artifacts = build_catalog_artifacts()

    assert sorted(artifacts) == ["odpc.json"]
    assert artifacts["odpc.json"] == render_catalog_schema_json()


def test_write_catalog_artifacts_can_check_and_generate_to_target_directory(tmp_path):
    output_dir = tmp_path / "deep" / "artifacts"
    changed = write_catalog_artifacts(output_dir, check=True)

    assert changed == [Path("odpc.json")]

    written = write_catalog_artifacts(output_dir)
    assert written == changed

    assert write_catalog_artifacts(output_dir, check=True) == []


def test_build_catalog_collects_fragments_and_product_references(tmp_path):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "metadata.yaml").write_text(
        """
catalogMetadata:
  id: CAT-BUILT
  name:
    en: Built Catalog
  description:
    en: Built from fragments.
""",
        encoding="utf-8",
    )
    (fragments / "product.yaml").write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Customer Product
      productID: customer-product
      status: production
      visibility: internal
      type: dataset
""",
        encoding="utf-8",
    )
    (fragments / "use_case.yaml").write_text(
        """
useCase:
  id: UC-001
  name:
    en: Customer Retention
  description:
    en: Improve retention analytics.
""",
        encoding="utf-8",
    )

    document = build_catalog(fragments)

    assert document["kind"] == "Catalog"
    assert document["catalog"]["metadata"]["id"] == "CAT-BUILT"
    assert document["catalog"]["useCases"][0]["id"] == "UC-001"
    reference = document["catalog"]["productReferences"][0]
    assert reference["productID"] == "customer-product"
    assert reference["name"] == {"en": "Customer Product"}
    assert reference["status"] == "production"
    assert reference["visibility"] == "internal"
    assert reference["productModel"]["$ref"] == "product.yaml"


def test_write_catalog_creates_parent_directories(tmp_path):
    output = tmp_path / "deep" / "catalog" / "catalog.yaml"

    write_catalog(output, VALID_CATALOG)

    assert output.read_text(encoding="utf-8").startswith(
        "schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml"
    )


def test_render_and_write_catalog_html(tmp_path):
    html = render_catalog_html(VALID_CATALOG)

    assert DEFAULT_CATALOG_HTML_TEMPLATE.name == "catalog.html"
    assert DEFAULT_CATALOG_HTML_TEMPLATE.exists()
    assert html.startswith("<!doctype html>")
    assert "Urban Mobility Data Product Catalog" in html
    assert '<section class="odp-summary">' in html
    assert '<span class="odp-count">0</span><span>Product References</span>' in html
    assert "Product References" in html

    output = tmp_path / "deep" / "html" / "catalog.html"
    write_catalog_html(output, VALID_CATALOG)

    assert output.read_text(encoding="utf-8") == html


def test_render_and_write_catalog_toon(tmp_path):
    catalog = {
        **VALID_CATALOG,
        "catalog": {
            **VALID_CATALOG["catalog"],
            "productReferences": [
                {
                    "id": "PR-001",
                    "productID": "customer-product",
                    "productVersion": "1.0.0",
                    "name": {"en": "Customer Product"},
                    "description": {"en": "Trusted customer analytics."},
                    "status": "production",
                    "visibility": "internal",
                }
            ],
            "useCases": [
                {
                    "id": "UC-001",
                    "name": {"en": "Customer Retention"},
                    "description": {"en": "Improve retention decisions."},
                    "priority": "high",
                }
            ],
        },
    }

    toon = render_catalog_toon(catalog)

    assert toon.startswith(
        'schema: "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml"\n'
    )
    assert (
        "productReferences[1]{id,productID,productVersion,name,description,status,visibility}:"
        in toon
    )
    assert (
        "PR-001,customer-product,1.0.0,Customer Product,Trusted customer analytics.,production,internal"
        in toon
    )
    assert (
        "useCases[1]{id,name,description,status,priority,decision,expectedOutcome}:"
        in toon
    )
    assert (
        "UC-001,Customer Retention,Improve retention decisions.,null,high,null,null"
        in toon
    )

    output = tmp_path / "deep" / "toon" / "catalog.toon"
    write_catalog_toon(output, catalog)

    assert output.read_text(encoding="utf-8") == toon


def test_render_and_write_catalog_gcf(tmp_path):
    catalog = {
        **VALID_CATALOG,
        "catalog": {
            **VALID_CATALOG["catalog"],
            "productReferences": [
                {
                    "id": "PR-001",
                    "productID": "customer-product",
                    "productVersion": "1.0.0",
                    "name": {"en": "Customer Product"},
                    "description": {"en": "Trusted customer analytics."},
                    "status": "production",
                    "visibility": "internal",
                }
            ],
            "useCases": [
                {
                    "id": "UC-001",
                    "name": {"en": "Customer Retention"},
                    "description": {"en": "Improve retention decisions."},
                    "priority": "high",
                }
            ],
        },
    }

    gcf = render_catalog_gcf(catalog)

    assert gcf.startswith(
        "GCF profile=generic tool=open-data-products kind=odpc-catalog\n"
    )
    assert "schema=https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml\n" in gcf
    assert "id=CAT-001\n" in gcf
    assert "name=Urban Mobility Data Product Catalog\n" in gcf
    assert (
        "## productReferences [1]{id,productID,productVersion,name,description,status,visibility}\n"
        in gcf
    )
    assert (
        "PR-001|customer-product|1.0.0|Customer Product|"
        "Trusted customer analytics.|production|internal" in gcf
    )
    assert (
        "## useCases [1]{id,name,description,status,priority,decision,expectedOutcome}\n"
        in gcf
    )
    assert "UC-001|Customer Retention|Improve retention decisions.|-|high|-|-" in gcf

    output = tmp_path / "deep" / "gcf" / "catalog.gcf"
    write_catalog_gcf(output, catalog)

    assert output.read_text(encoding="utf-8") == gcf


def test_explain_catalog_renders_summary_for_catalog_document():
    summary = explain_catalog(VALID_CATALOG, path=Path("catalog.yaml"))

    assert "File: catalog.yaml" in summary
    assert "Catalog id: CAT-001" in summary
    assert "Catalog name: Urban Mobility Data Product Catalog" in summary
    assert "Product references: 0" in summary
    assert "Graph: (not set)" in summary


def test_validate_catalog_accepts_valid_catalog_document():
    result = validate_catalog(VALID_CATALOG)

    assert result.valid is True
    assert result.errors == []


def test_validate_catalog_reports_invalid_catalog_document():
    result = validate_catalog({"version": "1.0"})

    assert result.valid is False
    assert any("<root>" in error for error in result.errors)
