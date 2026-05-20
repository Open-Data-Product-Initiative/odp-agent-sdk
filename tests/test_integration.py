"""Integration tests that work with actual implementation."""

import json
import tempfile
from pathlib import Path

from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductDetails, UseCase


class TestIntegration:
    """Simple integration tests to verify the library works."""

    def test_create_basic_product(self):
        """Test creating a basic ODPS product."""
        details = ProductDetails(
            name="Test Dataset",
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(details)

        # Basic assertions
        assert product.product_details.name == "Test Dataset"
        assert product.product_details.product_id == "test-001"
        assert product.schema == "https://opendataproducts.org/v4.1/schema/odps.json"
        assert product.version == "4.1"

    def test_product_with_use_case(self):
        """Test product with use cases."""
        use_case = UseCase(title="Analytics", description="For data analysis")

        details = ProductDetails(
            name="Analytics Dataset",
            product_id="analytics-001",
            visibility="public",
            status="production",
            type="dataset",
            use_cases=[use_case],
        )

        product = OpenDataProduct(details)

        assert len(product.product_details.use_cases) == 1
        assert product.product_details.use_cases[0].title == "Analytics"

    def test_json_serialization(self):
        """Test JSON serialization works."""
        details = ProductDetails(
            name="JSON Test",
            product_id="json-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(details)
        json_str = product.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["product"]["name"] == "JSON Test"
        assert data["product"]["productID"] == "json-001"

    def test_yaml_serialization(self):
        """Test YAML serialization works."""
        details = ProductDetails(
            name="YAML Test",
            product_id="yaml-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(details)
        yaml_str = product.to_yaml()

        # Should contain expected content
        assert "YAML Test" in yaml_str
        assert "yaml-001" in yaml_str

    def test_roundtrip_json(self):
        """Test JSON roundtrip serialization."""
        details = ProductDetails(
            name="Roundtrip Test",
            product_id="roundtrip-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        original = OpenDataProduct(details)
        json_str = original.to_json()
        restored = OpenDataProduct.from_json(json_str)

        assert restored.product_details.name == original.product_details.name
        assert (
            restored.product_details.product_id == original.product_details.product_id
        )

    def test_roundtrip_preserves_complex_optional_components(self):
        """Test JSON roundtrip preserves parsed optional component data."""
        source = {
            "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
            "version": "4.1",
            "product": {
                "name": "Complex Roundtrip",
                "productID": "complex-roundtrip-001",
                "visibility": "public",
                "status": "draft",
                "type": "dataset",
                "SLA": {
                    "$ref": "#/components/sla/default",
                    "profiles": {
                        "default": {
                            "dimensions": [
                                {
                                    "name": "uptime",
                                    "objective": 99.9,
                                    "unit": "percent",
                                }
                            ],
                            "monitoring_specification": {"check": "uptime"},
                            "support_contact": "Data Ops",
                            "support_phone": "+12125551234",
                            "support_email": "ops@example.com",
                            "service_hours": "24/7",
                            "documentation_url": "https://example.com/sla",
                            "$ref": "#/components/sla/profiles/default",
                        }
                    },
                },
                "dataQuality": {
                    "$ref": "#/components/data-quality/default",
                    "profiles": {
                        "default": {
                            "dimensions": [
                                {
                                    "name": "accuracy",
                                    "objective": 95,
                                    "unit": "percent",
                                    "display_title": "Accuracy",
                                    "description": "Accepted rows",
                                }
                            ],
                            "quality_checks": {"tool": "great-expectations"},
                            "$ref": "#/components/data-quality/profiles/default",
                        }
                    },
                },
                "paymentGateways": {
                    "$ref": "#/components/payment-gateways",
                    "gateways": [
                        {
                            "name": {"en": "Stripe"},
                            "url": "https://pay.example.com",
                            "specification": {"provider": "stripe"},
                            "description": {"en": "Card payments"},
                            "version": "2024-01",
                            "reference": "stripe-default",
                            "executableSpecifications": {"openapi": "3.1.0"},
                            "$ref": "#/components/payment-gateways/stripe",
                        }
                    ],
                    "named_gateways": {
                        "default": {
                            "name": "Invoice",
                            "url": "https://invoice.example.com",
                        }
                    },
                },
            },
        }

        restored = OpenDataProduct.from_dict(source)
        product = restored.to_dict()["product"]

        assert product["SLA"] == source["product"]["SLA"]
        assert product["dataQuality"] == source["product"]["dataQuality"]
        assert product["paymentGateways"] == source["product"]["paymentGateways"]

    def test_serialization_cache_keys_include_document_hash(self):
        """Test serialization cache tracks the document hash it was created for."""
        details = ProductDetails(
            name="Cache Test",
            product_id="cache-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(details)
        first_hash = product._generate_hash()

        first_json = product.to_json()
        second_json = product.to_json()

        assert first_json == second_json
        assert (first_hash, "json", 2) in product._serialization_cache

    def test_mutation_helpers_invalidate_serialization_cache(self):
        """Test mutation helpers clear cached hashes and serialized output."""
        details = ProductDetails(
            name="Cache Mutation Test",
            product_id="cache-mutation-001",
            visibility="public",
            status="draft",
            type="dataset",
        )
        product = OpenDataProduct(details)

        product.to_json()
        assert product._serialization_cache
        assert product._hash_cache is not None

        product.add_license(scope_of_use="internal")

        assert product._serialization_cache == {}
        assert product._validation_cache == {}
        assert product._hash_cache is None
        assert '"license"' in product.to_json()

    def test_save_and_load(self):
        """Test saving to file and loading back."""
        details = ProductDetails(
            name="File Test",
            product_id="file-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        original = OpenDataProduct(details)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            original.save(tmp_path)
            loaded = OpenDataProduct.from_file(tmp_path)

            assert loaded.product_details.name == "File Test"
            assert loaded.product_details.product_id == "file-001"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_validation_passes(self):
        """Test that valid product passes validation."""
        details = ProductDetails(
            name="Valid Product",
            product_id="valid-001",
            visibility="public",
            status="production",
            type="dataset",
        )

        product = OpenDataProduct(details)

        # Should validate successfully
        result = product.validate()
        assert result is True

    def test_demo_files_exist_and_load(self):
        """Test that demo files can be loaded if they exist."""
        demo_json = Path("examples/demo_product.json")
        demo_yaml = Path("examples/demo_product.yaml")

        if demo_json.exists():
            product = OpenDataProduct.from_file(demo_json)
            assert isinstance(product, OpenDataProduct)
            assert product.product_details.name is not None
            print(f"✓ Successfully loaded {demo_json}")

        if demo_yaml.exists():
            product = OpenDataProduct.from_file(demo_yaml)
            assert isinstance(product, OpenDataProduct)
            assert product.product_details.name is not None
            print(f"✓ Successfully loaded {demo_yaml}")

    def test_complex_product(self):
        """Test creating a more complex product with multiple features."""
        details = ProductDetails(
            name="Complex Analytics Dataset",
            product_id="complex-001",
            visibility="organisation",
            status="production",
            type="dataset",
            description="A comprehensive dataset for analytics",
            categories=["analytics", "sales"],
            tags=["quarterly", "revenue", "b2b"],
            language=["en", "es"],
            standards=["ISO 8601"],
        )

        product = OpenDataProduct(details)

        # Should serialize and validate
        json_str = product.to_json()
        yaml_str = product.to_yaml()
        result = product.validate()

        assert len(json_str) > 100  # Should have substantial content
        assert len(yaml_str) > 100
        assert result is True
        assert "analytics" in product.product_details.categories
        assert "en" in product.product_details.language
