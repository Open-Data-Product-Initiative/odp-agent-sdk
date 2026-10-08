"""ODPS v4.2 normalization coverage for portfolio-generated products."""

from open_data_products.portfolio import _normalize_odps_product


def test_v42_portfolio_normalization_adds_default_access_profile() -> None:
    document = {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
        "version": "4.2",
        "product": {
            "details": {
                "en": {
                    "name": "Orders",
                    "productID": "orders",
                    "visibility": "public",
                    "status": "draft",
                    "type": "dataset",
                }
            },
            "dataAccess": {
                "API": {
                    "outputPortType": "API",
                    "format": "JSON",
                }
            },
            "pricingPlans": {
                "declarative": {
                    "en": [{"access": {"$ref": "#/product/dataAccess/API"}}]
                }
            },
        },
    }

    _normalize_odps_product(document)

    assert list(document["product"]["dataAccess"]) == ["default"]
    assert document["product"]["dataAccess"]["default"]["outputPortType"] == "API"
    assert document["product"]["pricingPlans"]["declarative"]["en"][0][
        "access"
    ] == {"$ref": "#/product/dataAccess/default"}


def test_v42_portfolio_normalization_preserves_external_access_references() -> None:
    document = {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
        "version": "4.2",
        "product": {
            "details": {
                "en": {
                    "name": "Orders",
                    "productID": "orders",
                    "visibility": "public",
                    "status": "draft",
                    "type": "dataset",
                }
            },
            "dataAccess": {"default": {"$ref": "profiles/default.yaml"}},
        },
    }

    _normalize_odps_product(document)

    assert document["product"]["dataAccess"] == {
        "default": {"$ref": "profiles/default.yaml"}
    }


def test_v42_portfolio_normalization_keeps_primary_profile_first() -> None:
    document = {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
        "version": "4.2",
        "product": {
            "dataAccess": {
                "API": {"outputPortType": "API", "format": "JSON"},
                "bulk": {"outputPortType": "bulk", "format": "CSV"},
            }
        },
    }

    _normalize_odps_product(document)

    assert list(document["product"]["dataAccess"]) == ["default", "bulk"]
