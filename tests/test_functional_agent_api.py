"""Functional tests for the public cross-spec Agent API."""

from pathlib import Path
from typing import Dict, Tuple

import pytest
import yaml

from open_data_products import (
    check_product_contract_alignment,
    detect_document,
    explain_document,
    extract_contract_schema,
    generate_product_contract_report,
    list_resources,
    load_document,
    load_summary,
    resolve_references,
    resolve_product_contracts,
    summarize_contract,
    validate_contract,
    validate_document,
)

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]


def _odpc_catalog() -> Dict[str, object]:
    return {
        "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
        "version": "1.0",
        "kind": "Catalog",
        "catalog": {
            "metadata": {
                "id": "CAT-FUNCTIONAL-001",
                "name": {"en": "Functional Catalog"},
                "description": {"en": "Functional catalog fixture."},
            }
        },
    }


@pytest.fixture()
def functional_paths(tmp_path: Path) -> Dict[str, Tuple[Path, str]]:
    odpc_path = tmp_path / "catalog.yaml"
    odpc_path.write_text(yaml.safe_dump(_odpc_catalog()), encoding="utf-8")
    return {
        "odps": (
            REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml",
            "OpenDataProduct",
        ),
        "odpc": (odpc_path, "Catalog"),
        "odpg": (
            REPO_ROOT / "open_data_products" / "odpg" / "data" / "graph" / "graph.yaml",
            "Graph",
        ),
        "odpv": (
            REPO_ROOT / "open_data_products" / "odpv" / "data" / "vocab" / "odpv.yaml",
            "Vocabulary",
        ),
    }


def test_agent_api_workflow_across_all_specs(
    functional_paths: Dict[str, Tuple[Path, str]]
) -> None:
    for expected_spec, (path, expected_kind) in functional_paths.items():
        document = load_document(path)
        spec, kind = detect_document(document)
        result = validate_document(path)
        explanation = explain_document(document, path=path)
        references = resolve_references(document, path=path)
        metadata = load_summary(path)

        assert spec == expected_spec
        assert kind == expected_kind
        assert result.valid is True
        assert result.spec == expected_spec
        assert result.kind == expected_kind
        assert str(path) in explanation
        assert metadata["spec"] == expected_spec
        assert metadata["kind"] == expected_kind
        assert metadata["byte_size"] > 0
        assert isinstance(references, list)


def test_resource_registry_functional_paths_exist() -> None:
    resources = list_resources()

    assert resources
    assert all(Path(resource.path).is_file() for resource in resources)
    assert {resource.spec for resource in resources} == {
        "generation",
        "odps",
        "odpc",
        "odpg",
        "odpv",
    }


def test_contract_api_workflow_with_native_odps_contract(tmp_path: Path) -> None:
    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
  contract:
    type: DCS
    spec:
      name: Orders
      models:
        orders:
          fields:
            order_id:
              type: string
              required: true
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
""",
        encoding="utf-8",
    )

    references = resolve_product_contracts(product)
    validation = validate_contract(str(contract))
    summary = summarize_contract(str(contract))
    schema = extract_contract_schema(str(contract))
    alignment = check_product_contract_alignment(product, str(contract))
    report = generate_product_contract_report(product)

    assert references[0].inline_spec is not None
    assert validation.passed is False
    assert validation.findings[0].code == "DATACONTRACT_CLI_NOT_INSTALLED"
    assert summary.name == "Orders"
    assert schema.model_count == 1
    assert schema.field_count == 1
    assert alignment.passed is False
    assert alignment.contract_valid is False
    assert report.passed is True
    assert report.contract_count == 1
    assert report.alignments[0].passed is True
