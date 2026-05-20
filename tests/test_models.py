"""Tests for ODPS data models."""

from open_data_products.odps.models import (
    ProductDetails,
    UseCase,
    DataContract,
    SLA,
    DataQuality,
    PricingPlans,
    License,
    DataAccess,
    DataHolder,
    PaymentGateways,
    DataAccessMethod,
    PricingPlan,
    PaymentGateway,
)


class TestProductDetails:
    """Test cases for ProductDetails model."""

    def test_minimal_product_details(self):
        """Test creating ProductDetails with minimal required fields."""
        details = ProductDetails(
            name="Test Product",
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        assert details.name == "Test Product"
        assert details.product_id == "test-001"
        assert details.visibility == "public"
        assert details.status == "draft"
        assert details.type == "dataset"

    def test_full_product_details(self):
        """Test creating ProductDetails with many fields."""
        use_case = UseCase(title="Analytics Use Case", description="For data analysis")

        details = ProductDetails(
            name="Complete Test Product",
            product_id="test-complete-001",
            visibility="organisation",
            status="production",
            type="dataset",
            description="A comprehensive test product",
            categories=["analytics", "reporting"],
            tags=["test", "demo"],
            brand="Test Brand",
            keywords=["data", "analysis"],
            themes=["business"],
            geography="US",
            language=["en", "es"],
            homepage="https://example.com",
            created="2023-01-01T00:00:00Z",
            updated="2023-12-31T23:59:59Z",
            standards=["ISO 8601"],
            issues="https://example.com/issues",
            value_proposition="Provides valuable insights",
            logo_url="https://example.com/logo.png",
            product_series="v2",
            product_version="2.1.0",
            version_notes="Bug fixes and improvements",
            content_sample="Sample data content",
            brand_slogan="Your data, your insights",
            use_cases=[use_case],
        )

        assert details.name == "Complete Test Product"
        assert details.categories == ["analytics", "reporting"]
        assert details.language == ["en", "es"]
        assert len(details.use_cases) == 1
        assert details.use_cases[0].title == "Analytics Use Case"

    def test_product_details_defaults(self):
        """Test ProductDetails default values."""
        details = ProductDetails(
            name="Defaults Test",
            product_id="defaults-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        # Check defaults
        assert details.description is None
        assert details.categories == []
        assert details.tags == []
        assert details.language == []
        assert details.use_cases == []

    def test_product_details_validation_via_creation(self):
        """Test that ProductDetails validates inputs during creation."""
        # This tests that the dataclass accepts the inputs correctly
        # Since it's a simple dataclass, validation would be handled elsewhere

        # Valid values should work
        details = ProductDetails(
            name="Valid Product",
            product_id="valid-001",
            visibility="public",
            status="production",
            type="dataset",
        )
        assert details is not None


class TestUseCase:
    """Test cases for UseCase model."""

    def test_basic_use_case(self):
        """Test creating basic UseCase."""
        use_case = UseCase(title="Analytics", description="Data analysis and reporting")

        assert use_case.title == "Analytics"
        assert use_case.description == "Data analysis and reporting"
        assert use_case.url is None

    def test_use_case_with_url(self):
        """Test UseCase with optional URL."""
        use_case = UseCase(
            title="ML Training",
            description="Machine learning model training",
            url="https://example.com/ml-guide",
        )

        assert use_case.title == "ML Training"
        assert use_case.url == "https://example.com/ml-guide"


class TestDataContract:
    """Test cases for DataContract model."""

    def test_basic_data_contract(self):
        """Test basic data contract."""
        contract = DataContract(
            contract_url="https://example.com/schema.json", type="ODCS"
        )

        assert contract.contract_url == "https://example.com/schema.json"
        assert contract.type == "ODCS"

    def test_data_contract_defaults(self):
        """Test data contract with defaults."""
        contract = DataContract()

        assert contract.id is None
        assert contract.type is None
        assert contract.contract_version is None


class TestDataAccessMethod:
    """Test cases for DataAccessMethod model."""

    def test_data_access_method(self):
        """Test creating a data access method."""
        method = DataAccessMethod()

        # DataAccessMethod exists and can be instantiated
        assert method is not None


class TestPricingPlan:
    """Test cases for PricingPlan model."""

    def test_pricing_plan(self):
        """Test creating a pricing plan."""
        plan = PricingPlan(name="Basic Plan", price_currency="USD")

        assert plan.name == "Basic Plan"
        assert plan.price_currency == "USD"
        assert plan.price is None  # Optional field


class TestLicense:
    """Test cases for License model."""

    def test_license(self):
        """Test creating a license."""
        license_obj = License(scope_of_use="commercial")

        assert license_obj.scope_of_use == "commercial"
        assert license_obj.permanent is True  # Default value
        assert license_obj.exclusive is False  # Default value


class TestDataHolder:
    """Test cases for DataHolder model."""

    def test_data_holder(self):
        """Test creating a data holder."""
        holder = DataHolder(name="Data Corp", email="contact@datacorp.com")

        assert holder.name == "Data Corp"
        assert holder.email == "contact@datacorp.com"
        assert holder.url is None  # Optional field


class TestModelIntegration:
    """Integration tests for models working together."""

    def test_product_with_use_cases(self):
        """Test ProductDetails with UseCase objects."""
        use_cases = [
            UseCase(
                title="Business Intelligence",
                description="Generate business reports and dashboards",
            ),
            UseCase(
                title="Predictive Analytics",
                description="Build predictive models for forecasting",
                url="https://example.com/forecasting",
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

        assert len(details.use_cases) == 2
        assert details.use_cases[0].title == "Business Intelligence"
        assert details.use_cases[1].url == "https://example.com/forecasting"

    def test_product_with_multiple_languages(self):
        """Test ProductDetails with multiple languages."""
        details = ProductDetails(
            name="International Dataset",
            product_id="intl-001",
            visibility="public",
            status="production",
            type="dataset",
            language=["en", "es", "fr", "de"],
            geography="EU",
        )

        assert "en" in details.language
        assert "es" in details.language
        assert "fr" in details.language
        assert "de" in details.language
        assert details.geography == "EU"

    def test_product_with_comprehensive_metadata(self):
        """Test ProductDetails with comprehensive metadata."""
        details = ProductDetails(
            name="Comprehensive Dataset",
            product_id="comp-001",
            visibility="organisation",
            status="production",
            type="dataset",
            description="A dataset with comprehensive metadata",
            categories=["analytics", "sales", "marketing"],
            tags=["quarterly", "revenue", "customer", "b2b"],
            brand="Data Corp",
            keywords=["sales", "analytics", "quarterly", "revenue"],
            themes=["business", "finance"],
            geography="US",
            language=["en"],
            homepage="https://datacorp.com/products/comp-001",
            logo_url="https://datacorp.com/logo.png",
            standards=["ISO 8601", "ISO 3166"],
            product_version="2.1.0",
            version_notes="Added new customer segments and improved data quality",
            brand_slogan="Data that drives decisions",
        )

        # Verify all fields are set correctly
        assert details.name == "Comprehensive Dataset"
        assert "analytics" in details.categories
        assert "quarterly" in details.tags
        assert "sales" in details.keywords
        assert "business" in details.themes
        assert details.brand == "Data Corp"
        assert details.product_version == "2.1.0"

    def test_dataclass_behavior(self):
        """Test that models behave as proper dataclasses."""
        details1 = ProductDetails(
            name="Test",
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        details2 = ProductDetails(
            name="Test",
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        # Should be equal (dataclass provides __eq__)
        assert details1 == details2

        # Should have proper string representation
        repr_str = repr(details1)
        assert "ProductDetails" in repr_str
        assert "test-001" in repr_str

    def test_model_instantiation(self):
        """Test that all model classes can be instantiated."""
        models = [
            UseCase(title="Test", description="Test description"),
            ProductDetails(
                name="Test",
                product_id="test",
                visibility="public",
                status="draft",
                type="dataset",
            ),
            DataContract(),
            SLA(),
            DataQuality(),
            PricingPlans(),
            License(scope_of_use="internal"),
            DataAccess(default=DataAccessMethod()),
            DataHolder(name="Test Corp", email="test@example.com"),
            PaymentGateways(),
            DataAccessMethod(),
            PricingPlan(name="Test Plan", price_currency="USD"),
            PaymentGateway(name="Test Gateway", url="https://payments.example.com"),
        ]

        # All models should instantiate without error
        for model in models:
            assert model is not None
