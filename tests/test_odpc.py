"""Tests for ODPC catalog SDK helpers."""

from pathlib import Path

from open_data_products.odpc import (
    explain_catalog,
    load_object_records,
    search_objects,
    validate_catalog,
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
