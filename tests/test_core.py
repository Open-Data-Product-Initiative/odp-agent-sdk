"""Tests for core OpenDataProduct functionality."""

import pytest
import json
import yaml
import tempfile
from pathlib import Path
from jsonschema import Draft202012Validator

from open_data_products.odps import OpenDataProduct, ODPSValidationError
from open_data_products.odps.models import ProductDetails


class TestOpenDataProduct:
    """Test cases for OpenDataProduct class."""

    def test_init_with_product_details(self, sample_product_details):
        """Test OpenDataProduct initialization with ProductDetails."""
        product = OpenDataProduct(sample_product_details)
        assert product.product_details == sample_product_details
        assert product.schema == "https://opendataproducts.org/v4.1/schema/odps.json"
        assert product.version == "4.1"

    def test_init_with_dict(self, minimal_valid_odps_data):
        """Test OpenDataProduct initialization with dictionary data."""
        product = OpenDataProduct.from_dict(minimal_valid_odps_data)
        assert product.product_details.name == "Test Dataset"
        assert product.product_details.product_id == "test-001"
        assert product.product_details.visibility == "public"

    def test_from_dict_accepts_v41_details_and_declarative_pricing(self):
        """Test loading canonical ODPS v4.1 details and pricing shape."""
        from open_data_products import pricing_to_402

        product = OpenDataProduct.from_dict(
            {
                "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "name": "Agent Ready Product",
                            "productID": "agent-ready-product",
                            "visibility": "public",
                            "status": "production",
                            "type": "dataset",
                        }
                    },
                    "pricingPlans": {
                        "declarative": {
                            "en": [
                                {
                                    "name": "Starter",
                                    "priceCurrency": "USD",
                                    "price": "5.0",
                                    "billingDuration": "month",
                                    "unit": "Recurring",
                                }
                            ]
                        }
                    },
                },
            }
        )

        assert product.product_details.name == "Agent Ready Product"
        assert product.product_details.product_id == "agent-ready-product"
        assert product.pricing_plans.plans[0].name == "Starter"
        assert product.pricing_plans.plans[0].price_currency == "USD"
        assert pricing_to_402(product)["status"] == 402

    def test_from_dict_accepts_v41_sla_and_data_quality_declarative(self):
        """Test loading canonical ODPS v4.1 SLA and data quality shape."""
        product = OpenDataProduct.from_dict(
            {
                "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "name": "Agent Ready Product",
                            "productID": "agent-ready-product",
                            "visibility": "public",
                            "status": "production",
                            "type": "dataset",
                        }
                    },
                    "SLA": {
                        "declarative": [
                            {
                                "name": {"en": "Default SLA"},
                                "dimensions": [
                                    {
                                        "dimension": "uptime",
                                        "objective": "99.5",
                                        "unit": "percent",
                                    }
                                ],
                            }
                        ]
                    },
                    "dataQuality": {
                        "declarative": [
                            {
                                "name": {"en": "Default Data Quality"},
                                "dimensions": [
                                    {
                                        "dimension": "completeness",
                                        "objective": 95,
                                        "unit": "percentage",
                                    }
                                ],
                            }
                        ]
                    },
                },
            }
        )

        assert product.sla.profiles["declarative1"].dimensions[0].name == "uptime"
        assert (
            product.data_quality.profiles["declarative1"].dimensions[0].name
            == "completeness"
        )

    def test_from_dict_accepts_v41_data_access_array(self):
        """Test loading canonical ODPS v4.1 data access array shape."""
        product = OpenDataProduct.from_dict(
            {
                "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "name": "Agent Ready Product",
                            "productID": "agent-ready-product",
                            "visibility": "public",
                            "status": "production",
                            "type": "dataset",
                        }
                    },
                    "dataAccess": [
                        {
                            "name": {"en": "API"},
                            "description": {"en": "API access."},
                            "outputPortType": "API",
                            "format": "JSON",
                        }
                    ],
                },
            }
        )

        assert product.data_access is not None
        assert product.data_access.default.output_port_type == "API"
        assert product.data_access.default.format == "JSON"

    def test_named_odps_component_maps_validate_and_parse(self):
        """Test ODPS named components used by pricing $ref paths."""
        document = {
            "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Customer Health Signals",
                        "productID": "customer-health-signals",
                        "visibility": "organisation",
                        "status": "draft",
                        "type": "dataset",
                    }
                },
                "SLA": {
                    "declarative": {
                        "default": {
                            "name": {"en": "The Basic SLA"},
                            "description": {"en": "The basic SLA package"},
                            "dimensions": [
                                {
                                    "dimension": "uptime",
                                    "displaytitle": {"en": "Uptime"},
                                    "objective": 90,
                                    "unit": "percent",
                                    "weight": 50,
                                }
                            ],
                        },
                        "premium": {
                            "name": {"en": "The Premium SLA"},
                            "description": {"en": "The Premium SLA package"},
                            "dimensions": [
                                {
                                    "dimension": "responseTime",
                                    "objective": 100,
                                    "unit": "milliseconds",
                                    "weight": 20,
                                }
                            ],
                        },
                    }
                },
                "dataQuality": {
                    "declarative": {
                        "default": {
                            "description": "The basic data quality package",
                            "dimensions": [
                                {
                                    "dimension": "completeness",
                                    "objective": 95,
                                    "unit": "percentage",
                                }
                            ],
                        },
                        "premium": {
                            "description": "The premium data quality package",
                            "dimensions": [
                                {
                                    "dimension": "validity",
                                    "objective": 98,
                                    "unit": "percentage",
                                }
                            ],
                        },
                    }
                },
                "dataAccess": {
                    "API": {
                        "name": {"en": "API"},
                        "description": {"en": "API access."},
                        "outputPortType": "API",
                        "format": "JSON",
                    }
                },
                "paymentGateways": {
                    "default": {
                        "description": {"en": "Internal chargeback."},
                        "type": "Custom",
                        "version": "v1",
                    }
                },
                "pricingPlans": {
                    "declarative": {
                        "en": [
                            {
                                "name": "Internal Starter",
                                "priceCurrency": "EUR",
                                "price": "0",
                                "billingDuration": "month",
                                "unit": "Open-data",
                                "paymentGateway": {
                                    "$ref": "#/product/paymentGateways/default"
                                },
                                "dataQuality": {
                                    "$ref": "#/product/dataQuality/declarative/default"
                                },
                                "SLA": {"$ref": "#/product/SLA/declarative/default"},
                                "access": {"$ref": "#/product/dataAccess/API"},
                            }
                        ]
                    }
                },
            },
        }
        schema = yaml.safe_load(
            Path("open_data_products/odps/data/schema/odps.json").read_text(
                encoding="utf-8"
            )
        )
        errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: list(error.path),
        )
        assert errors == []

        product = OpenDataProduct.from_dict(document)

        assert sorted(product.sla.profiles) == ["default", "premium"]
        assert sorted(product.data_quality.profiles) == ["default", "premium"]
        assert product.data_access.default.output_port_type == "API"
        assert product.payment_gateways.named_gateways["default"].version == "v1"

    def test_v41_license_scope_shape_does_not_require_legacy_scope_of_use(self):
        """Test ODPS v4.1 license.scope shape is accepted by validation."""
        document = {
            "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Licensed Product",
                        "productID": "licensed-product",
                        "visibility": "organisation",
                        "status": "draft",
                        "type": "dataset",
                    }
                },
                "license": {
                    "scope": {
                        "definition": "Internal use for approved business workflows.",
                        "restrictions": "No resale or external redistribution.",
                        "geographicalArea": ["EU"],
                        "permanent": False,
                        "exclusive": False,
                        "rights": ["Display", "Distribution"],
                    },
                    "termination": {
                        "noticePeriod": 30,
                        "terminationConditions": "Access ends when business purpose ends.",
                    },
                    "governance": {
                        "ownership": "Revenue Operations",
                        "audit": "Usage reviewed quarterly.",
                    },
                },
            },
        }

        product = OpenDataProduct.from_dict(document)

        assert product.validate() is True

    def test_to_dict(self, sample_odps_product):
        """Test converting OpenDataProduct to dictionary."""
        data = sample_odps_product.to_dict()
        assert isinstance(data, dict)
        assert data["schema"] == "https://opendataproducts.org/v4.1/schema/odps.json"
        assert data["version"] == "4.1"
        assert "product" in data
        assert data["product"]["name"] == "Test Product"

    def test_to_json(self, sample_odps_product):
        """Test JSON serialization."""
        json_str = sample_odps_product.to_json()
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["schema"] == "https://opendataproducts.org/v4.1/schema/odps.json"
        assert data["product"]["name"] == "Test Product"

    def test_to_json_pretty(self, sample_odps_product):
        """Test pretty JSON serialization."""
        json_str = sample_odps_product.to_json(indent=2)
        assert isinstance(json_str, str)
        assert "\n" in json_str  # Should have newlines for pretty formatting

        # Verify it's still valid JSON
        data = json.loads(json_str)
        assert data["product"]["name"] == "Test Product"

    def test_to_yaml(self, sample_odps_product):
        """Test YAML serialization."""
        yaml_str = sample_odps_product.to_yaml()
        assert isinstance(yaml_str, str)

        # Verify it's valid YAML
        data = yaml.safe_load(yaml_str)
        assert data["schema"] == "https://opendataproducts.org/v4.1/schema/odps.json"
        assert data["product"]["name"] == "Test Product"

    def test_from_json(self, minimal_valid_odps_data):
        """Test creating OpenDataProduct from JSON string."""
        json_str = json.dumps(minimal_valid_odps_data)
        product = OpenDataProduct.from_json(json_str)

        assert product.product_details.name == "Test Dataset"
        assert product.product_details.product_id == "test-001"

    def test_from_yaml(self, minimal_valid_odps_data):
        """Test creating OpenDataProduct from YAML string."""
        yaml_str = yaml.dump(minimal_valid_odps_data)
        product = OpenDataProduct.from_yaml(yaml_str)

        assert product.product_details.name == "Test Dataset"
        assert product.product_details.product_id == "test-001"

    def test_load_from_json_file(self, demo_product_json_path):
        """Test loading OpenDataProduct from JSON file."""
        if demo_product_json_path.exists():
            product = OpenDataProduct.from_file(demo_product_json_path)
            assert isinstance(product, OpenDataProduct)
            assert product.product_details.name is not None

    def test_load_from_yaml_file(self, demo_product_yaml_path):
        """Test loading OpenDataProduct from YAML file."""
        if demo_product_yaml_path.exists():
            product = OpenDataProduct.from_file(demo_product_yaml_path)
            assert isinstance(product, OpenDataProduct)
            assert product.product_details.name is not None

    def test_save_json_file(self, sample_odps_product):
        """Test saving OpenDataProduct to JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            sample_odps_product.save(tmp_path)
            assert tmp_path.exists()

            # Verify content
            with open(tmp_path, "r") as f:
                data = json.load(f)
            assert data["product"]["name"] == "Test Product"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_save_yaml_file(self, sample_odps_product):
        """Test saving OpenDataProduct to YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            sample_odps_product.save(tmp_path)
            assert tmp_path.exists()

            # Verify content
            with open(tmp_path, "r") as f:
                data = yaml.safe_load(f)
            assert data["product"]["name"] == "Test Product"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_save_creates_parent_directories(self, sample_odps_product, tmp_path):
        """Test saving OpenDataProduct creates missing parent directories."""
        output = tmp_path / "deep" / "output" / "product.yaml"

        sample_odps_product.save(output)

        assert output.exists()
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        assert data["product"]["name"] == "Test Product"

    def test_validate_valid_product(self, sample_odps_product):
        """Test validation of valid product."""
        # This should not raise an exception
        result = sample_odps_product.validate()
        assert result is True

    def test_validate_invalid_product(self, invalid_odps_data):
        """Test validation of invalid product."""
        with pytest.raises(ODPSValidationError):
            product = OpenDataProduct.from_dict(invalid_odps_data)
            product.validate()

    def test_equality(self, sample_product_details):
        """Test OpenDataProduct equality."""
        product1 = OpenDataProduct(sample_product_details)
        product2 = OpenDataProduct(sample_product_details)

        # Test that both have the same product details
        assert product1.product_details == product2.product_details
        assert product1.schema == product2.schema
        assert product1.version == product2.version

    def test_repr(self, sample_odps_product):
        """Test OpenDataProduct string representation."""
        repr_str = repr(sample_odps_product)
        assert "OpenDataProduct" in repr_str
        assert "Test Product" in repr_str

    def test_hash(self, sample_odps_product):
        """Test OpenDataProduct hashing."""
        hash_val = hash(sample_odps_product)
        assert isinstance(hash_val, int)

    def test_update_product(self, sample_odps_product):
        """Test updating product details."""
        new_details = ProductDetails(
            name="Updated Product",
            product_id="updated-001",
            visibility="private",
            status="production",
            type="api",
        )

        sample_odps_product.product_details = new_details
        assert sample_odps_product.product_details.name == "Updated Product"
        assert sample_odps_product.product_details.visibility == "private"

    def test_file_not_found_error(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            OpenDataProduct.from_file(Path("nonexistent.json"))

    def test_invalid_json_error(self):
        """Test loading invalid JSON."""
        with pytest.raises((json.JSONDecodeError, ValueError, Exception)):
            OpenDataProduct.from_json("invalid json content")

    def test_invalid_yaml_error(self):
        """Test loading invalid YAML."""
        with pytest.raises((yaml.YAMLError, ValueError, Exception)):
            OpenDataProduct.from_yaml("invalid: yaml: content: [")
