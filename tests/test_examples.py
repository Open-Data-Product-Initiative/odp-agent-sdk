"""Tests using demo files and examples."""

import pytest
import json
import yaml

from pathlib import Path

from open_data_products.odpc import build_catalog, render_catalog_html, validate_catalog
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductDetails

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDemoFiles:
    """Test cases using demo product files."""

    def test_load_demo_json(self, demo_product_json_path):
        """Test loading demo product from JSON file."""
        if not demo_product_json_path.exists():
            pytest.skip("Demo JSON file not found")

        product = OpenDataProduct.from_file(demo_product_json_path)

        # Verify basic properties
        assert isinstance(product, OpenDataProduct)
        assert product.schema == "https://opendataproducts.org/v4.0/schema/odps.json"
        assert product.version == "4.0"

        # Verify product details
        assert product.product_details.name is not None
        assert product.product_details.product_id is not None
        assert product.product_details.visibility in [
            "public",
            "private",
            "organisation",
        ]
        assert product.product_details.status in ["draft", "production", "deprecated"]
        assert product.product_details.type in [
            "dataset",
            "api",
            "ml-model",
            "algorithm",
        ]

    def test_load_demo_yaml(self, demo_product_yaml_path):
        """Test loading demo product from YAML file."""
        if not demo_product_yaml_path.exists():
            pytest.skip("Demo YAML file not found")

        product = OpenDataProduct.from_file(demo_product_yaml_path)

        # Verify basic properties
        assert isinstance(product, OpenDataProduct)
        assert product.schema == "https://opendataproducts.org/v4.0/schema/odps.json"
        assert product.version == "4.0"

        # Verify product details exist
        assert product.product_details.name is not None
        assert product.product_details.product_id is not None

    def test_demo_json_yaml_equivalence(
        self, demo_product_json_path, demo_product_yaml_path
    ):
        """Test that JSON and YAML demo files contain equivalent data."""
        if not (demo_product_json_path.exists() and demo_product_yaml_path.exists()):
            pytest.skip("Both demo files not found")

        json_product = OpenDataProduct.from_file(demo_product_json_path)
        yaml_product = OpenDataProduct.from_file(demo_product_yaml_path)

        # Should have same basic properties
        assert json_product.schema == yaml_product.schema
        assert json_product.version == yaml_product.version
        assert json_product.product_details.name == yaml_product.product_details.name
        assert (
            json_product.product_details.product_id
            == yaml_product.product_details.product_id
        )

    def test_demo_product_validation(self, demo_product_json_path):
        """Test that demo product passes validation."""
        if not demo_product_json_path.exists():
            pytest.skip("Demo JSON file not found")

        product = OpenDataProduct.from_file(demo_product_json_path)

        # Should validate successfully
        result = product.validate()
        assert result is True

    def test_demo_product_serialization_roundtrip(self, demo_product_json_path):
        """Test demo product serialization roundtrip."""
        if not demo_product_json_path.exists():
            pytest.skip("Demo JSON file not found")

        # Load original
        original_product = OpenDataProduct.from_file(demo_product_json_path)

        # Serialize to JSON and back
        json_str = original_product.to_json()
        json_product = OpenDataProduct.from_json(json_str)

        # Should be equivalent
        assert (
            json_product.product_details.name == original_product.product_details.name
        )
        assert (
            json_product.product_details.product_id
            == original_product.product_details.product_id
        )

        # Serialize to YAML and back
        yaml_str = original_product.to_yaml()
        yaml_product = OpenDataProduct.from_yaml(yaml_str)

        # Should be equivalent
        assert (
            yaml_product.product_details.name == original_product.product_details.name
        )
        assert (
            yaml_product.product_details.product_id
            == original_product.product_details.product_id
        )

    def test_demo_product_has_expected_fields(self, demo_product_json_data):
        """Test that demo product contains expected ODPS v4.0 fields."""
        # Should have schema and version
        assert demo_product_json_data.get("schema") is not None
        assert demo_product_json_data.get("version") == "4.0"

        # Should have product section
        product_data = demo_product_json_data.get("product", {})
        assert "name" in product_data
        assert "productID" in product_data
        assert "visibility" in product_data
        assert "status" in product_data
        assert "type" in product_data

    def test_demo_product_optional_components(self, demo_product_json_data):
        """Test demo product optional components."""
        # Check for optional components that might be present
        optional_components = [
            "dataContract",
            "sla",
            "dataQuality",
            "pricingPlans",
            "license",
            "dataAccess",
            "dataHolder",
            "paymentGateways",
        ]

        present_components = []
        for component in optional_components:
            if component in demo_product_json_data:
                present_components.append(component)

        # Should have some optional components for a complete demo
        # (This is informational - not all demos need all components)
        print(f"Demo product includes components: {present_components}")


class TestODPCExamples:
    """Test cases using ODPC catalog build examples."""

    def test_odpc_catalog_html_example_matches_generated_output(self):
        """Test that the committed ODPC HTML sample matches the build helper."""
        fragments = REPO_ROOT / "examples" / "odpc_catalog_fragments"
        sample_html = REPO_ROOT / "examples" / "odpc_catalog.html"

        document = build_catalog(fragments)
        result = validate_catalog(document)

        assert result.valid is True
        assert sample_html.read_text(encoding="utf-8") == render_catalog_html(document)
        assert "Example ODPC Catalog" in sample_html.read_text(encoding="utf-8")


class TestGenerationSourceExamples:
    """Test cases using source documents for local generation."""

    def test_generation_source_docs_are_available(self):
        """Test that mixed source docs exist for local LLM generation."""
        source_dir = (
            REPO_ROOT
            / "open_data_products"
            / "generation"
            / "source_docs"
        )

        markdown_files = sorted(source_dir.glob("*.md"))
        text_files = sorted(source_dir.glob("*.txt"))
        combined_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [*markdown_files, *text_files]
        )

        assert source_dir.is_dir()
        assert len(markdown_files) >= 5
        assert len(text_files) >= 4
        assert "Airport Operations Performance Data Product" in combined_text
        assert "Passenger Flow and Queue Data Product" in combined_text
        assert "Flight Connection Reliability Data Product" in combined_text
        assert "Flight Delay Risk Monitoring" in combined_text
        assert "Passenger Connection Protection" in combined_text
        assert "Reduce Departure Delay Minutes" in combined_text
        assert "Turnaround Delay Spike Signal" in combined_text
        assert "Security Queue Surge Signal" in combined_text
        assert "Inbound Connection Risk Signal" in combined_text
        assert "Baggage Belt Congestion Signal" in combined_text

    def test_generated_fragments_are_generic_odpc_files(self):
        """Test that generated outputs are generic fragment files."""
        from open_data_products.odpc import build_catalog, validate_catalog
        from open_data_products.odpg import validate_graph

        fragments_dir = REPO_ROOT / "open_data_products" / "generation" / "fragments"
        graph_path = fragments_dir / "odpg_graph.yaml"

        fragment_roots = {
            path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in fragments_dir.glob("*.yaml")
            if path.name != "odpg_graph.yaml"
        }

        assert fragments_dir.is_dir()
        assert not any(path.is_dir() for path in fragments_dir.iterdir())
        assert {next(iter(document)) for document in fragment_roots.values()} == {
            "productReference",
            "useCase",
            "businessObjective",
            "signal",
        }

        catalog = build_catalog(fragments_dir)
        assert validate_catalog(catalog).valid is True

        graph = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
        assert validate_graph(graph).valid is True
        assert all("#/" not in node["$ref"] for node in graph["graph"]["nodes"])


class TestExampleUsage:
    """Test cases based on example usage patterns."""

    def test_basic_usage_example(self):
        """Test the basic usage example from documentation."""
        # Create product details
        details = ProductDetails(
            name="My Dataset",
            product_id="dataset-001",
            visibility="public",
            status="production",
            type="dataset",
        )

        # Create ODPS document
        product = OpenDataProduct(details)

        # Validate and export
        assert product.validate() is True
        json_str = product.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_advanced_usage_example(self):
        """Test advanced usage with multiple components."""
        # Create comprehensive product details
        details = ProductDetails(
            name="Advanced Analytics Dataset",
            product_id="analytics-v2",
            visibility="organisation",
            status="production",
            type="dataset",
            description="Advanced analytics dataset with comprehensive metadata",
            categories=["analytics", "business-intelligence"],
            tags=["sales", "revenue", "forecasting"],
            language=["en"],
            geography="US",
            created="2023-01-01T00:00:00Z",
            updated="2023-12-31T23:59:59Z",
        )

        # Create product
        product = OpenDataProduct(details)

        # Should validate
        assert product.validate() is True

        # Should serialize properly
        data = product.to_dict()
        assert data["product"]["name"] == "Advanced Analytics Dataset"
        assert "analytics" in data["product"]["categories"]

    def test_minimal_valid_product(self):
        """Test creating minimal valid ODPS product."""
        details = ProductDetails(
            name="Minimal Product",
            product_id="minimal-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(details)

        # Should be valid even with minimal fields
        assert product.validate() is True

        # Should serialize to valid JSON
        json_data = json.loads(product.to_json())
        assert (
            json_data["schema"] == "https://opendataproducts.org/v4.1/schema/odps.json"
        )
        assert json_data["version"] == "4.1"

    def test_product_with_use_cases(self):
        """Test product with use cases."""
        from open_data_products.odps.models import UseCase

        use_cases = [
            UseCase(
                title="Business Intelligence",
                description="Generate business reports and dashboards",
            ),
            UseCase(
                title="Predictive Analytics",
                description="Build predictive models for forecasting",
            ),
        ]

        details = ProductDetails(
            name="Multi-Purpose Dataset",
            product_id="multi-001",
            visibility="public",
            status="production",
            type="dataset",
            use_cases=use_cases,
        )

        product = OpenDataProduct(details)

        assert product.validate() is True
        assert len(product.product_details.use_cases) == 2
        assert product.product_details.use_cases[0].title == "Business Intelligence"

    def test_international_product_example(self):
        """Test product with international metadata."""
        details = ProductDetails(
            name="International Dataset",
            product_id="intl-001",
            visibility="public",
            status="production",
            type="dataset",
            description="Dataset with international standards compliance",
            language=["en", "es", "fr"],  # Multi-language support
            geography="EU",  # European market
            standards=["ISO 8601", "ISO 3166"],  # International standards
        )

        product = OpenDataProduct(details)

        assert product.validate() is True
        assert "es" in product.product_details.language
        assert "fr" in product.product_details.language

    def test_api_product_example(self):
        """Test API-type data product."""
        details = ProductDetails(
            name="Customer API",
            product_id="customer-api-v1",
            visibility="organisation",
            status="production",
            type="api",
            description="RESTful API for customer data access",
            homepage="https://api.example.com/customers",
            product_version="1.2.0",
        )

        product = OpenDataProduct(details)

        assert product.validate() is True
        assert product.product_details.type == "api"
        assert product.product_details.homepage == "https://api.example.com/customers"

    def test_ml_model_product_example(self):
        """Test ML model type data product."""
        details = ProductDetails(
            name="Sales Prediction Model",
            product_id="sales-ml-v3",
            visibility="private",
            status="production",
            type="ml-model",
            description="Machine learning model for sales forecasting",
            categories=["machine-learning", "forecasting"],
            product_version="3.1.0",
            version_notes="Improved accuracy with new features",
        )

        product = OpenDataProduct(details)

        assert product.validate() is True
        assert product.product_details.type == "ml-model"
        assert "machine-learning" in product.product_details.categories
