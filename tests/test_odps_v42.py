"""ODPS v4.2 profile, schema-routing, and round-trip coverage."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from open_data_products.agent import resolve_references, validate_document
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import (
    ContractReference,
    DataAccessMethod,
    DataContract,
    ProductDetails,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_yaml_fixture() -> dict:
    return yaml.safe_load((FIXTURES / "odps_v42_profiles.yaml").read_text())


def test_v42_yaml_profiles_validate_and_round_trip() -> None:
    document = _load_yaml_fixture()

    assert validate_document(document).valid is True
    product = OpenDataProduct.from_dict(document)
    assert product.data_contract.default.id == "CONTRACT-001"
    assert product.data_contract.additional_profiles["restricted"].dollar_ref == (
        "contracts/restricted.yaml"
    )
    assert product.data_access.additional_methods["agent"].output_port_type == "AI"
    assert product.data_access.default.contract.dollar_ref == "#/product/contract/default"

    serialized = product.to_dict()
    assert validate_document(serialized).valid is True
    assert serialized["product"]["contract"]["restricted"] == {
        "$ref": "contracts/restricted.yaml"
    }


def test_v42_json_external_packages_validate_and_round_trip() -> None:
    document = json.loads((FIXTURES / "odps_v42_profiles.json").read_text())

    assert validate_document(document).valid is True
    product = OpenDataProduct.from_dict(document)
    assert product.data_contract.dollar_ref == "https://example.org/contracts/profiles.yaml"
    assert product.data_access.dollar_ref == "https://example.org/access/profiles.yaml"
    assert product.to_dict()["product"]["contract"] == document["product"]["contract"]
    assert product.to_dict()["product"]["dataAccess"] == document["product"]["dataAccess"]
    refs = resolve_references(document)
    assert {reference.ref_type for reference in refs} >= {
        "schema",
        "contract-profile-package",
        "data-access-profile-package",
    }


def test_v42_rejects_singleton_contract_and_invalid_bindings() -> None:
    document = _load_yaml_fixture()
    document["product"]["contract"] = {"id": "CONTRACT-001", "type": "ODCS"}
    errors = validate_document(document).errors
    assert errors
    assert any("contract" in error for error in errors)

    document = _load_yaml_fixture()
    document["product"]["dataAccess"]["default"]["contract"] = {
        "$ref": "#/product/details/en"
    }
    errors = validate_document(document).errors
    assert any("invalid-contract-target" in error for error in errors)


def test_v42_enforces_profile_defaults_output_type_and_uri_format() -> None:
    document = _load_yaml_fixture()
    document["product"]["contract"] = {"restricted": {"id": "C", "type": "ODCS"}}
    assert validate_document(document).valid is False

    document = _load_yaml_fixture()
    document["product"]["dataAccess"]["agent"].pop("outputPortType")
    document["product"]["dataAccess"]["default"]["accessURL"] = "not a uri"
    errors = validate_document(document).errors
    assert errors
    assert any("outputPortType" in error or "uri" in error for error in errors)


def test_v42_python_api_generates_profile_collections() -> None:
    product = OpenDataProduct(
        ProductDetails("Orders", "orders", "public", "draft", "dataset"),
        version="4.2",
    )
    product.add_contract_profile("default", DataContract(id="ORDERS", type="ODCS"))
    product.add_contract_profile("restricted", DataContract(id="ORDERS-R", type="DCS"))
    product.add_data_access_profile(
        "default",
        DataAccessMethod(
            output_port_type="API",
            contract=ContractReference("#/product/contract/default"),
        ),
    )
    product.add_data_access_profile(
        "agent", DataAccessMethod(output_port_type="AI", specification="MCP", format="MCP")
    )

    document = product.to_dict()
    assert document["schema"].endswith("/v4.2/schema/odps.json")
    assert list(document["product"]["contract"]) == ["default", "restricted"]
    assert list(document["product"]["dataAccess"]) == ["default", "agent"]
    assert validate_document(document).valid is True
    assert product.validate() is True
