"""Tests for ODPC catalog SDK helpers."""

from pathlib import Path

from open_data_products.odpc import (
    DEFAULT_CATALOG_HTML_TEMPLATE,
    build_catalog,
    build_catalog_artifacts,
    explain_catalog,
    load_object_records,
    render_catalog_html,
    render_catalog_toon,
    render_catalog_schema_json,
    search_objects,
    validate_catalog,
    write_catalog,
    write_catalog_html,
    write_catalog_toon,
    write_catalog_artifacts,
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
